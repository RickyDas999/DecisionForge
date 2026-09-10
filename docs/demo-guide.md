# DecisionForge — 10-Minute Live Demo Guide

A practical run sheet. No slide deck — the frontend and the code are the visuals.

**Before you start**

- Serve locally: `python scripts/web_demo.py` → open `http://127.0.0.1:8000`
  (offline, zero cost), or open the Vercel URL with `MODEL_PROVIDER=mock`.
- Have an editor open with these files pre-loaded (see 6:30–8:30):
  `app/agents/orchestrator.py`, `app/orchestration/dispatcher.py`,
  `app/agents/comparison.py`, `app/skills/mapping.py`, `app/tools/policy.py`,
  `api/index.py`.
- Full scenario detail: `docs/demo-scenarios.md`.

---

## 0:00 – 1:00 · The problem

- People ask software-decision questions ("Postgres or Mongo?", "research X",
  "turn this into a brief"). A single generic prompt handles all of them poorly
  and unpredictably; a full agent swarm is expensive and hard to reason about.
- **DecisionForge**: a small, constrained multi-agent system. One orchestrator
  classifies the request and routes it to **exactly one** of three specialists.
  Deterministic Python does everything else.
- The headline constraint: **at most two LLM calls per request** — 1 to route,
  1 to answer.

## 1:00 – 3:30 · Run the main request (Comparison)

- On the page, click the **Comparison** example (or paste):
  *"Compare PostgreSQL and MongoDB for a small SaaS startup expecting rapid
  growth."*
- Click **Run request**. Talk through the loading state: routing → selecting a
  specialist → processing.
- When it returns, point at the chips: **Route: Comparison**, **Specialist:
  Comparison Agent**, **Skill: Comparison**, **Search: used**, **Confidence**,
  **LLM calls: 2 / 2**.

## 3:30 – 5:00 · Explain the result (non-technical)

- Read the **"Why this agent?"** card — this is the orchestrator's own routing
  reasoning, shown verbatim (no second LLM call to explain it).
- Walk the result: the **options** with advantages/disadvantages, the **key
  tradeoffs**, the **recommendation** and **rationale**, and the **confidence**
  the model reported.
- Note **Limitations** — the system is explicit about what it doesn't know.

## 5:00 – 6:30 · Expand "Technical details"

- Open the **Technical details** panel.
- **Execution:** run id, route, specialist class, skill, search used, persistence
  mode, model provider.
- **Cost controls:** LLM calls used = 2, max allowed = 2, retries = 0, fallback
  agents = 0, parallel LLM calls = 0.
- **Event trace:** friendly labels with the raw event id beside each —
  `run.started → route.selected → search.started → search.completed →
  specialist.started → specialist.completed → run.completed`.
- Point at the **execution-path diagram** above the panel: it's built from
  deterministic run metadata — it only shows stages that actually ran (do a Brief
  request later and it has no Search stage).

## 6:30 – 8:30 · Switch to code (4–6 files only)

1. **`app/agents/orchestrator.py`** — semantic routing. One system prompt, one
   `generate_structured(response_model=RoutingDecision)` call. No dispatch logic
   here.
2. **`app/orchestration/dispatcher.py`** — deterministic dispatch. `dispatch()`:
   one orchestrator call, an `if route is …` chain, then exactly one specialist
   call. No retry, no loop, no fallback (grep the file for those words — only in
   the docstring).
3. **`app/agents/comparison.py`** — specialist isolation. A leaf agent: one model
   call, no imports of other agents, the route's SKILL.md body appended to its
   own system prompt.
4. **`app/skills/mapping.py`** — `ROUTE_SKILLS`, a static dict. The orchestrator
   already decided the route, so the skill is fixed — no LLM picks it.
   (Optionally open `skills/comparison/SKILL.md` to show the progressive-
   disclosure format: frontmatter for discovery, body on activation.)
5. **`app/tools/policy.py`** — `SEARCH_ENABLED_ROUTES = {RESEARCH, COMPARISON}`.
   Brief is absent. `app/tools/context.py` shows the deterministic size caps on
   the evidence before it reaches the model.
6. **`api/index.py`** — the Vercel entrypoint: import-safe, exposes `app`,
   `app/web/deployment.py` reads config from env. Stateless (`NullRunRepository`)
   on Vercel; SQLite locally.

## 8:30 – 9:30 · Architecture choices

- **Single-hop:** parent → one child. Controlled delegation without an open-ended
  agent graph.
- **Two-call ceiling:** predictable cost and latency; easy to reason about.
- **Deterministic tools & skills:** search and skill selection are plain Python —
  zero extra model calls, fully testable. The LLM only does semantic work.
- **Progressive skill disclosure:** discovery loads metadata, activation loads
  one SKILL.md body, extension loads references/scripts only on request.
- **Persistence for tracing:** SQLite run + event history (local); the web
  response carries the full trace so the deployed version needs no database.

## 9:30 – 10:00 · Wrap up

- What this demonstrates: constrained hierarchical delegation, structured
  outputs, deterministic orchestration, an evaluation harness
  (`python scripts/eval_demo.py`), ~300 tests, and a Vercel deployment.
- Extensibility: a fourth specialist is a new `AgentRoute` value + a leaf agent +
  one row in `ROUTE_SKILLS`; a real search backend is one `SearchProvider`
  implementation; durable cloud history is one `RunRepository` implementation.
- What it deliberately is **not**: an autonomous multi-step agent. No loops, no
  self-critique, no tool-use decisions by the model.
