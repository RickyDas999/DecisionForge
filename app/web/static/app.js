"use strict";

/* DecisionForge UI — vanilla JS. Renders a completed run from a single POST
   response: a non-technical result view, a deterministic execution-path
   diagram, and an expandable technical panel. No framework, no build step. */

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

let CONFIG = {
  model_provider: "mock",
  search_provider: "none",
  search_enabled: false,
  persistence_enabled: false,
  max_llm_calls: 2,
};

const SEARCH_ELIGIBLE_ROUTES = new Set(["research", "comparison"]);

// ---- human-readable labels ------------------------------------------------
const ROUTE_LABEL = { research: "Research", comparison: "Comparison", brief: "Brief" };
const SPECIALIST_LABEL = {
  research: "Research Agent",
  comparison: "Comparison Agent",
  brief: "Brief Agent",
};
const SKILL_LABEL = {
  research: "Research",
  comparison: "Comparison",
  "executive-brief": "Executive Brief",
};
const ROUTE_WHY_PREFIX = {
  research: "Your request asks to investigate a topic, so DecisionForge routed it to the Research Agent.",
  comparison: "Your request compares options and weighs tradeoffs, so DecisionForge routed it to the Comparison Agent.",
  brief: "Your request asks to transform supplied material into a brief, so DecisionForge routed it to the Brief Agent.",
};

const EVENT_LABEL = {
  "run.started": () => "Request started",
  "route.selected": (ev) =>
    `Orchestrator selected the ${SPECIALIST_LABEL[ev.metadata?.route] || "specialist"}`,
  "search.started": () => "Search tool started",
  "search.completed": (ev) =>
    `Search evidence gathered${
      ev.metadata?.result_count != null ? ` (${ev.metadata.result_count} results)` : ""
    }`,
  "specialist.started": (ev) =>
    `${SPECIALIST_LABEL[ev.metadata?.route] || "Specialist"} started`,
  "specialist.completed": (ev) =>
    `${SPECIALIST_LABEL[ev.metadata?.route] || "Specialist"} completed`,
  "run.completed": () => "Request completed",
  "run.failed": (ev) => `Request failed${ev.message ? ` (${ev.message})` : ""}`,
};

const EXAMPLES = {
  research: {
    request:
      "Research the current landscape of vector databases for a small AI startup.",
    context: "",
  },
  comparison: {
    request:
      "Compare PostgreSQL and MongoDB for a small SaaS startup expecting rapid growth.",
    context: "",
  },
  brief: {
    request: "Create an executive brief from the context below.",
    context:
      "Over the last quarter the team evaluated three approaches to our data " +
      "pipeline. Approach A shipped fastest but has limited observability. " +
      "Approach B is more operationally complex but scales cleanly to 10x " +
      "volume. Approach C is a managed service that removes ops burden at " +
      "roughly 1.6x the monthly cost. Leadership needs to pick a direction " +
      "before the next planning cycle.",
  },
};

// ---- API ----------------------------------------------------------------
async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

// ---- small builders ---------------------------------------------------
function chip(text, cls) {
  return el("span", `chip${cls ? " " + cls : ""}`, text);
}
function chipKV(label, value, cls) {
  const c = el("span", `chip${cls ? " " + cls : ""}`);
  c.appendChild(el("span", "lbl", label + " "));
  c.appendChild(document.createTextNode(value));
  return c;
}
function block(label, valueNode) {
  const b = el("div", "result-block");
  b.appendChild(el("div", "k", label));
  b.appendChild(valueNode);
  return b;
}
function list(items, { link } = {}) {
  const ul = el("ul");
  (items || []).forEach((it) => {
    const li = el("li");
    if (link && /^https?:\/\//i.test(String(it))) {
      const a = el("a", null, String(it));
      a.href = String(it);
      a.target = "_blank";
      a.rel = "noopener";
      li.appendChild(a);
    } else {
      li.textContent = String(it);
    }
    ul.appendChild(li);
  });
  if (!items || !items.length) ul.appendChild(el("li", "em", "(none)"));
  return ul;
}

// ---- per-route result rendering -------------------------------------
function renderResearch(r) {
  const f = document.createDocumentFragment();
  f.appendChild(block("Topic", el("p", null, r.topic)));
  f.appendChild(block("Summary", el("p", null, r.summary)));
  f.appendChild(block("Key findings", list(r.key_findings)));
  f.appendChild(block("Sources", list(r.sources, { link: true })));
  f.appendChild(block("Limitations", list(r.limitations)));
  return f;
}

function renderComparison(r) {
  const f = document.createDocumentFragment();
  f.appendChild(block("Question", el("p", null, r.question)));
  const opts = el("div");
  (r.options || []).forEach((o) => {
    const card = el("div", "option-card");
    card.appendChild(el("h4", null, o.name));
    const pc = el("div", "pros-cons");
    pc.appendChild(block("Advantages", list(o.advantages)));
    pc.appendChild(block("Disadvantages", list(o.disadvantages)));
    card.appendChild(pc);
    opts.appendChild(card);
  });
  f.appendChild(block("Options", opts));
  f.appendChild(block("Key tradeoffs", list(r.important_tradeoffs)));

  const rec = el("div", "rec-card");
  rec.appendChild(el("div", "k", "Recommendation"));
  rec.appendChild(el("p", null, r.recommendation));
  f.appendChild(rec);

  f.appendChild(block("Rationale", el("p", null, r.rationale)));
  f.appendChild(block("Limitations", list(r.limitations)));
  return f;
}

function renderBrief(r) {
  const f = document.createDocumentFragment();
  f.appendChild(block("Title", el("p", null, r.title)));
  f.appendChild(block("Executive summary", el("p", null, r.executive_summary)));
  f.appendChild(block("Key points", list(r.key_points)));
  if (r.recommendation) {
    const rec = el("div", "rec-card");
    rec.appendChild(el("div", "k", "Recommendation"));
    rec.appendChild(el("p", null, r.recommendation));
    f.appendChild(rec);
  }
  f.appendChild(block("Action items", list(r.action_items)));
  return f;
}

function renderResultBody(run) {
  const body = $("result-body");
  body.replaceChildren();
  if (run.status === "failed" || !run.result) {
    const box = el("div", "error-box");
    box.appendChild(el("strong", null, "This run failed"));
    if (run.error) box.appendChild(el("p", null, run.error));
    box.appendChild(
      el("p", "em", "The orchestrator did not fall back to another agent — one route, one attempt.")
    );
    body.appendChild(box);
    return;
  }
  const fn = { research: renderResearch, comparison: renderComparison, brief: renderBrief }[run.route];
  body.appendChild(fn ? fn(run.result) : el("pre", null, JSON.stringify(run.result, null, 2)));
}

// ---- chips (primary view) ------------------------------------------
function renderChips(run) {
  const row = $("result-chips");
  row.replaceChildren();
  row.appendChild(chip(run.status, run.status === "completed" ? "ok" : "err"));
  if (run.route) row.appendChild(chipKV("Route", ROUTE_LABEL[run.route] || run.route, "accent"));
  if (run.route) row.appendChild(chipKV("Specialist", SPECIALIST_LABEL[run.route] || run.selected_specialist));
  if (run.selected_skill) row.appendChild(chipKV("Skill", SKILL_LABEL[run.selected_skill] || run.selected_skill));
  row.appendChild(chip(searchChipText(run)));
  const conf = run.result && typeof run.result.confidence === "number" ? run.result.confidence : null;
  if (conf != null) row.appendChild(chipKV("Confidence", `${Math.round(conf * 100)}%`));
  row.appendChild(chipKV("LLM calls", `${run.llm_calls} / ${run.llm_calls_max} max`, "accent"));
}

function searchChipText(run) {
  if (run.search_used) {
    const ev = (run.events || []).find((e) => e.event_type === "search.completed");
    const n = ev && ev.metadata ? ev.metadata.result_count : null;
    return n != null ? `Search: used (${n} results)` : "Search: used";
  }
  if (!SEARCH_ELIGIBLE_ROUTES.has(run.route)) {
    return "Search: not used for this route";
  }
  // route is search-eligible but no evidence was gathered
  return CONFIG.search_enabled
    ? "Search: available, no results"
    : "Search: not configured on this server";
}

function renderWhy(run) {
  const card = $("why-card");
  if (!run.route) {
    card.hidden = true;
    return;
  }
  const prefix = ROUTE_WHY_PREFIX[run.route] || "";
  const reasoning = run.routing_reasoning ? ` ${run.routing_reasoning}` : "";
  $("why-text").textContent = (prefix + reasoning).trim();
  card.hidden = false;
}

// ---- deterministic execution-path diagram --------------------------
function renderFlow(run) {
  const flow = $("flow");
  flow.replaceChildren();
  if (!run.route) {
    flow.hidden = true;
    return;
  }
  const stages = [{ t: "Your request", c: "" }, { t: "Orchestrator", c: "" }];
  stages.push({ t: `${ROUTE_LABEL[run.route]} route`, c: "route" });
  if (run.selected_skill) stages.push({ t: `${SKILL_LABEL[run.selected_skill]} skill`, c: "" });
  if (run.search_used) {
    const ev = (run.events || []).find((e) => e.event_type === "search.completed");
    const n = ev && ev.metadata ? ev.metadata.result_count : null;
    stages.push({ t: `Search evidence${n != null ? ` (${n})` : ""}`, c: "" });
  }
  stages.push({ t: SPECIALIST_LABEL[run.route], c: "specialist" });
  stages.push({ t: run.status === "completed" ? "Result" : "Failed", c: "" });

  stages.forEach((s, i) => {
    if (i) flow.appendChild(el("span", "arrow", "→"));
    flow.appendChild(el("span", `stage${s.c ? " " + s.c : ""}`, s.t));
  });
  flow.hidden = false;
}

// ---- technical panel ----------------------------------------------
function dlRow(dl, key, val) {
  dl.appendChild(el("dt", null, key));
  dl.appendChild(el("dd", null, String(val)));
}

function renderTech(run) {
  const ex = $("tech-execution");
  ex.replaceChildren();
  dlRow(ex, "run id", run.run_id);
  dlRow(ex, "route", run.route || "—");
  dlRow(ex, "specialist", run.selected_specialist || "—");
  dlRow(ex, "skill", run.selected_skill || "—");
  dlRow(ex, "search used", String(run.search_used));
  dlRow(ex, "search provider", CONFIG.search_provider);
  dlRow(ex, "persistence", CONFIG.persistence_enabled ? "sqlite (local)" : "stateless");
  dlRow(ex, "model provider", CONFIG.model_provider);

  const cost = $("tech-cost");
  cost.replaceChildren();
  dlRow(cost, "LLM calls used", run.llm_calls);
  dlRow(cost, "max allowed", `${run.llm_calls_max}  (1 routing + 1 specialist)`);
  dlRow(cost, "retries", "0");
  dlRow(cost, "fallback agents", "0");
  dlRow(cost, "parallel LLM calls", "0");

  const trace = $("trace");
  trace.replaceChildren();
  (run.events || []).forEach((ev) => {
    const li = el("li");
    const labeler = EVENT_LABEL[ev.event_type];
    li.appendChild(document.createTextNode(labeler ? labeler(ev) : ev.event_type));
    li.appendChild(el("span", "raw", ev.event_type));
    if (ev.timestamp) li.appendChild(el("span", "ts", new Date(ev.timestamp).toLocaleTimeString()));
    trace.appendChild(li);
  });

  $("raw-json").textContent = JSON.stringify(run.result ?? { error: run.error }, null, 2);
}

// ---- orchestration ----------------------------------------------
function showRun(run) {
  $("loading").hidden = true;
  renderChips(run);
  renderWhy(run);
  renderResultBody(run);
  renderFlow(run);
  renderTech(run);
  const p = $("result-panel");
  p.hidden = false;
  p.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showError(status, data) {
  $("loading").hidden = true;
  $("result-chips").replaceChildren(chip("failed", "err"));
  $("why-card").hidden = true;
  $("flow").hidden = true;
  const body = $("result-body");
  body.replaceChildren();
  const box = el("div", "error-box");
  box.appendChild(el("strong", null, `HTTP ${status} — ${data.error_type || "error"}`));
  box.appendChild(el("p", null, data.detail || "The request could not be completed."));
  box.appendChild(el("p", "em", "No retry, no fallback agent — the error is surfaced as-is."));
  body.appendChild(box);
  $("tech-execution").replaceChildren();
  $("tech-cost").replaceChildren();
  $("trace").replaceChildren();
  $("raw-json").textContent = JSON.stringify(data, null, 2);
  const p = $("result-panel");
  p.hidden = false;
  p.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadRecent() {
  const { ok, data } = await api("GET", "/api/runs");
  const ul = $("recent-list");
  ul.replaceChildren();
  $("recent-note").textContent = CONFIG.persistence_enabled
    ? "(stored locally)"
    : "(not stored on this deployment)";
  if (!ok || !data.runs || !data.runs.length) {
    ul.appendChild(el("li", "empty", CONFIG.persistence_enabled ? "No runs yet." : "History is disabled in stateless mode."));
    return;
  }
  data.runs.forEach((r) => {
    const li = el("li");
    li.appendChild(el("span", "rq", r.request_preview));
    li.appendChild(el("span", "rt", ROUTE_LABEL[r.route] || r.route || "—"));
    li.appendChild(el("span", "rs", r.status));
    li.appendChild(el("span", "rd", new Date(r.created_at).toLocaleString()));
    li.addEventListener("click", () => openRun(r.run_id));
    ul.appendChild(li);
  });
}

async function openRun(runId) {
  const { ok, data } = await api("GET", `/api/runs/${encodeURIComponent(runId)}`);
  if (ok) showRun(data);
}

async function submit(evt) {
  evt.preventDefault();
  const btn = $("submit-btn");
  btn.disabled = true;
  $("result-panel").hidden = true;
  $("loading").hidden = false;
  $("loading").scrollIntoView({ behavior: "smooth", block: "center" });
  try {
    const userRequest = $("user_request").value.trim();
    const context = $("provided_context").value.trim();
    const { ok, status, data } = await api("POST", "/api/runs", {
      user_request: userRequest,
      provided_context: context || null,
    });
    if (ok) showRun(data);
    else if (status === 422)
      showError(422, { error_type: "ValidationError", detail: "The request cannot be empty." });
    else showError(status, data);
    await loadRecent();
  } catch (err) {
    showError(0, { error_type: "NetworkError", detail: String(err) });
  } finally {
    btn.disabled = false;
  }
}

// ---- init -----------------------------------------------------
function wireExamples() {
  document.querySelectorAll(".ex").forEach((b) => {
    b.addEventListener("click", () => {
      const ex = EXAMPLES[b.dataset.example];
      if (!ex) return;
      $("user_request").value = ex.request;
      $("provided_context").value = ex.context;
      $("user_request").focus();
    });
  });
}

async function init() {
  wireExamples();
  $("run-form").addEventListener("submit", submit);
  const { ok, data } = await api("GET", "/api/health");
  if (ok) CONFIG = { ...CONFIG, ...data };
  $("demo-note").textContent =
    CONFIG.model_provider === "mock"
      ? "This server runs offline (deterministic demo provider). Routing, the search tool, skill selection, persistence and the event trace are all real — only the model outputs are canned."
      : `Model provider: ${CONFIG.model_provider}. Each request makes at most 2 real LLM calls.`;
  await loadRecent();
}

init();
