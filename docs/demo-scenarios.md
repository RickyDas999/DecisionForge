# DecisionForge — Demo Scenarios

Three scenarios for the live demo. Each runs entirely offline in the default
server (`python scripts/web_demo.py` or the Vercel deployment with
`MODEL_PROVIDER=mock`) — routing, the search tool, skill selection, persistence
and the event trace are all real; only the model text is canned.

> **Recommended primary scenario: Comparison.** It exercises every part of the
> architecture in one request — semantic routing, specialist selection, the
> deterministic search tool, an Agent Skill, structured output, a recommendation
> with a confidence value, and the two-call ceiling.

---

## 1. Comparison — the main demo

**Input (Request field):**

```
Compare PostgreSQL and MongoDB for a small SaaS startup expecting rapid growth.
```

**Context:** none.

| | |
|---|---|
| Expected route | `comparison` |
| Specialist | Comparison Agent |
| Agent Skill | `comparison` |
| Search | **runs** — Comparison is search-eligible (offline canned results in demo mode; DuckDuckGo if `SEARCH_PROVIDER=duckduckgo`) |
| LLM calls | 2 / 2 (1 routing + 1 specialist) |
| Result contains | options with advantages/disadvantages, key tradeoffs, a recommendation, rationale, **confidence**, limitations |
| Event trace | `run.started → route.selected → search.started → search.completed → specialist.started → specialist.completed → run.completed` |

**Code worth showing for this scenario**

- `app/agents/orchestrator.py` — the routing prompt + one structured call.
- `app/orchestration/dispatcher.py` — `dispatch()`: orchestrator call, then the
  `if route is …` chain, then exactly one specialist call.
- `app/agents/comparison.py` — a leaf specialist: one model call, no delegation,
  the skill body appended to its system prompt.
- `app/tools/policy.py` — `SEARCH_ENABLED_ROUTES = {RESEARCH, COMPARISON}` (Brief
  is absent — a static set, no LLM decides).
- `app/skills/mapping.py` — the static `route → skill` table.

---

## 2. Research

**Input:**

```
Research the current landscape of vector databases for a small AI startup.
```

**Context:** none.

| | |
|---|---|
| Expected route | `research` |
| Specialist | Research Agent |
| Agent Skill | `research` |
| Search | runs (research is search-eligible) |
| LLM calls | 2 / 2 |
| Result contains | topic, summary, key findings, sources, limitations |

**Point to make:** the Research Agent's prompt forbids claiming live research or
inventing citations when no evidence is supplied — it records that in
`limitations`. Show `app/agents/research.py` and `app/tools/context.py`
(`build_search_context` / `combine_contexts`, with the deterministic size caps).

---

## 3. Brief

**Input (Request field):**

```
Create an executive brief from the context below.
```

**Context (required):**

```
Over the last quarter the team evaluated three approaches to our data pipeline.
Approach A shipped fastest but has limited observability. Approach B is more
operationally complex but scales cleanly to 10x volume. Approach C is a managed
service that removes ops burden at roughly 1.6x the monthly cost. Leadership
needs to pick a direction before the next planning cycle.
```

| | |
|---|---|
| Expected route | `brief` |
| Specialist | Brief Agent |
| Agent Skill | `executive-brief` |
| Search | **skipped** — Brief never searches (it transforms supplied material) |
| LLM calls | 2 / 2 |
| Result contains | title, executive summary, key points, optional recommendation, action items |
| Event trace | `run.started → route.selected → specialist.started → specialist.completed → run.completed` (no `search.*`) |

**Point to make:** submit the Brief request **without** context first — the API
returns a clean `400 MissingBriefContextError` and the run is recorded as failed
with **no** specialist call and **no** retry. Then add the context and re-run.
Show `app/orchestration/dispatcher.py` (the brief branch) and
`app/orchestration/exceptions.py`.

---

## Contrast table (say this out loud during the demo)

| | Research | Comparison | Brief |
|---|---|---|---|
| Skill | `research` | `comparison` | `executive-brief` |
| Search runs? | yes | yes | **no** |
| Needs context? | optional | optional | **required** |
| LLM calls | 2 | 2 | 2 |
