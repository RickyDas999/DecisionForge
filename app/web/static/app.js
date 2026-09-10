"use strict";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

// ---- rendering --------------------------------------------------------------
function statusChip(status) {
  return el("span", `chip status-${status}`, status);
}

function metaRow(run) {
  const row = $("result-meta");
  row.replaceChildren();
  row.appendChild(statusChip(run.status));
  if (run.route) row.appendChild(el("span", "chip", `route: ${run.route}`));
  if (run.selected_specialist)
    row.appendChild(el("span", "chip", run.selected_specialist));
  row.appendChild(
    el("span", "chip", run.search_used ? "search: used" : "search: none")
  );
}

function block(label, valueNode) {
  const b = el("div", "result-block");
  b.appendChild(el("div", "k", label));
  b.appendChild(valueNode);
  return b;
}

function list(items) {
  const ul = el("ul");
  (items || []).forEach((it) => ul.appendChild(el("li", null, String(it))));
  if (!items || !items.length) ul.appendChild(el("li", "em", "(none)"));
  return ul;
}

function renderResearch(r) {
  const f = document.createDocumentFragment();
  f.appendChild(block("Topic", el("p", null, r.topic)));
  f.appendChild(block("Summary", el("p", null, r.summary)));
  f.appendChild(block("Key findings", list(r.key_findings)));
  f.appendChild(block("Limitations", list(r.limitations)));
  f.appendChild(block("Sources", list(r.sources)));
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
  f.appendChild(block("Recommendation", el("p", null, r.recommendation)));
  f.appendChild(block("Rationale", el("p", null, r.rationale)));
  f.appendChild(block("Important tradeoffs", list(r.important_tradeoffs)));
  f.appendChild(
    block("Confidence", el("p", null, `${(r.confidence * 100).toFixed(0)}%`))
  );
  f.appendChild(block("Limitations", list(r.limitations)));
  return f;
}

function renderBrief(r) {
  const f = document.createDocumentFragment();
  f.appendChild(block("Title", el("p", null, r.title)));
  f.appendChild(block("Executive summary", el("p", null, r.executive_summary)));
  f.appendChild(block("Key points", list(r.key_points)));
  if (r.recommendation)
    f.appendChild(block("Recommendation", el("p", null, r.recommendation)));
  f.appendChild(block("Action items", list(r.action_items)));
  return f;
}

function renderResult(run) {
  const body = $("result-body");
  body.replaceChildren();

  if (run.status === "failed" || !run.result) {
    const box = el("div", "error-box");
    box.appendChild(el("strong", null, "Run failed"));
    if (run.error) box.appendChild(el("p", null, run.error));
    body.appendChild(box);
    return;
  }
  const byRoute = {
    research: renderResearch,
    comparison: renderComparison,
    brief: renderBrief,
  };
  const fn = byRoute[run.route];
  body.appendChild(fn ? fn(run.result) : el("pre", null, JSON.stringify(run.result, null, 2)));
}

function renderTrace(events) {
  const ol = $("trace");
  ol.replaceChildren();
  (events || []).forEach((ev) => {
    const li = el("li");
    li.appendChild(el("span", "et", ev.event_type));
    if (ev.message) li.appendChild(el("span", "em", ` ${ev.message}`));
    li.appendChild(el("span", "ts", new Date(ev.timestamp).toLocaleTimeString()));
    ol.appendChild(li);
  });
}

function showRun(run, events) {
  metaRow(run);
  renderResult(run);
  renderTrace(events || []);
  $("result-panel").hidden = false;
  $("result-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showError(status, data) {
  $("result-meta").replaceChildren(statusChip("failed"));
  const body = $("result-body");
  body.replaceChildren();
  const box = el("div", "error-box");
  box.appendChild(el("strong", null, `HTTP ${status} — ${data.error_type || "error"}`));
  box.appendChild(el("p", null, data.detail || "Request failed."));
  body.appendChild(box);
  $("trace").replaceChildren();
  $("result-panel").hidden = false;
  if (data.run_id) openRun(data.run_id, /*keepError*/ true);
}

// ---- data flow -------------------------------------------------------------
async function openRun(runId, keepError) {
  // Only used for the recent-runs list (persistence enabled). In stateless
  // mode this 404s and we simply do nothing.
  const { ok, data } = await api("GET", `/api/runs/${encodeURIComponent(runId)}`);
  if (!ok) return;
  if (keepError) {
    renderTrace(data.events || []);
  } else {
    showRun(data, data.events || []);
  }
}

async function loadRecent() {
  const { ok, data } = await api("GET", "/api/runs");
  const ul = $("recent-list");
  ul.replaceChildren();
  if (!ok || !data.runs || !data.runs.length) {
    ul.appendChild(el("li", "empty", "No runs yet."));
    return;
  }
  data.runs.forEach((r) => {
    const li = el("li");
    li.appendChild(el("span", "rq", r.request_preview));
    li.appendChild(el("span", "rt", r.route || "—"));
    li.appendChild(el("span", "rs", r.status));
    li.appendChild(el("span", "rd", new Date(r.created_at).toLocaleString()));
    li.addEventListener("click", () => openRun(r.run_id));
    ul.appendChild(li);
  });
}

async function submit(evt) {
  evt.preventDefault();
  const btn = $("submit-btn");
  btn.disabled = true;
  try {
    const userRequest = $("user_request").value.trim();
    const context = $("provided_context").value.trim();
    const { ok, status, data } = await api("POST", "/api/runs", {
      user_request: userRequest,
      provided_context: context || null,
    });
    if (ok) {
      // POST returns the full run + its event trace — render directly, no
      // follow-up request (works whether or not persistence is enabled).
      showRun(data, data.events || []);
    } else if (status === 422) {
      showError(422, { error_type: "ValidationError", detail: "Request cannot be empty." });
    } else {
      showError(status, data);
    }
    await loadRecent();
  } finally {
    btn.disabled = false;
  }
}

$("run-form").addEventListener("submit", submit);
$("demo-note").textContent =
  "Default server runs offline (DemoModelProvider). Responses are canned; " +
  "routing, search, persistence and the event trace are real.";
loadRecent();
