# DecisionForge Architecture

## 1. What DecisionForge is

DecisionForge is a local-first, portfolio-quality application that demonstrates a
**constrained multi-agent architecture** while keeping Claude token/API usage to a
minimum.

A user submits a request. An **OrchestratorAgent** classifies it and selects
exactly one of three specialist agents. That specialist does the work. Everything
after the specialist returns is deterministic Python.

```
User
  |
  v
OrchestratorAgent            (1 Claude call: classification only)
  |
  v
select exactly one route
  |
  +--> ResearchAgent   \
  +--> ComparisonAgent  }  (1 Claude call: the selected specialist only)
  +--> BriefAgent      /
  |
  v
deterministic Python        (validation, formatting, storage, events, UI)
  |
  v
Result
```

## 2. Hard architectural rules

1. **Maximum LLM calls per normal request = 2** — one orchestrator call, one
   specialist call.
2. The orchestrator selects **exactly one** specialist.
3. Specialists **never** call other agents — not the orchestrator, not each
   other, not themselves, not any future agent.
4. **No agent loops.**
5. **No LLM retry loops.**
6. **No parallel LLM execution.**
7. **No multi-stage LLM pipeline.**
8. All business logic after the selected specialist is **deterministic**.
9. A specialist may later use tools (search, fetch). **Tools are deterministic
   Python operations, not agents** — they do not count toward the LLM-call limit.
10. `ModelProvider` remains the only vendor abstraction; agents never import an
    SDK.
11. **Mock mode is the cost-safe development default.**

If a specialist fails, the failure is surfaced through ordinary Python error
handling. No other agent is invoked automatically.

## 3. The delegation graph

```
                         Orchestrator
                        /     |      \
                       /      |       \
                Research  Comparison  Brief
                   |         |          |
                   +---------+----------+
                             |
                   deterministic Python
                             |
                           result
```

There are no edges between the specialists. The orchestrator is the only node
allowed to choose an outgoing edge, and it chooses exactly one. Each specialist
is a **leaf agent**: it makes one model call and returns a structured result;
it cannot delegate. Everything below the specialists is deterministic Python.
This models controlled parent/sub-agent routing without an open-ended agent
graph.

### The runtime request path (implemented)

`DecisionForgeDispatcher` (`app/orchestration/dispatcher.py`) is the complete
single-hop path:

```
User
 -> DispatchRequest
 -> OrchestratorAgent.run()          # 1 LLM call — semantic routing
 -> RoutingDecision.route
 -> DecisionForgeDispatcher          # deterministic Python owns selection
 -> [RESEARCH/COMPARISON only] SearchProvider.search()  # 0 LLM calls (tool, §13)
 -> exactly one specialist .run()    # 1 LLM call — the work
 -> DispatchResult
```

Once the orchestrator returns a `RoutingDecision`, **deterministic Python owns
specialist selection** — a single `if route is …` chain, no second semantic step.
An optional deterministic search step (§13) may add network I/O between routing
and the specialist call, but never a model call.

- **Maximum 2 LLM calls** per request (1 orchestrator + 1 specialist; search is 0).
- **No fallback agent** — if the specialist, provider, or parsing fails, the
  error propagates; the dispatcher never tries another route or agent.
- **No retry**, **no loop**, **no parallel execution** — the path is strictly
  sequential.
- **Missing brief context fails deterministically**: if the route is `brief`
  and `provided_context` is absent/blank, the dispatcher raises
  `MissingBriefContextError` *after* the (already-made) orchestrator call and
  makes **no** specialist call. It never invents context or re-routes.

Semantic routing, specialist behavior, and deterministic dispatch are still
built and tested as separate units.

## 4. The four agents

### OrchestratorAgent (implemented)

`app/agents/orchestrator.py`. `BaseAgent[RoutingInput, RoutingDecision]`.

- Depends only on `ModelProvider` (constructor argument).
- Makes **one** `generate_structured(..., response_model=RoutingDecision)` call.
- Returns a `RoutingDecision` — nothing else.
- Does **not** answer the request, research, compare, write a brief, call tools,
  touch `RunState`, loop, retry, or invoke a specialist.
- `OrchestratorAgent.run()` never contains `if route == ...: call specialist`.
  That deterministic dispatch layer is a later phase.

The three specialists are all **implemented** as leaf agents. Each takes only a
`ModelProvider` in its constructor, makes exactly one
`generate_structured(...)` call in `run()`, does no network I/O, uses no tools,
and never invokes another agent, retries, or loops. Real search/fetch tools are
a later phase.

### ResearchAgent (implemented)

`app/agents/research.py`. `BaseAgent[ResearchInput, ResearchResponse]`,
`name = "research"`.

For requests that primarily ask to investigate, gather facts, explain via
research, find current information, or summarize a topic. It has **no live data
source yet**: its prompt forbids claiming to have performed web/live research or
fabricating citations when no evidence is supplied in
`ResearchInput.provided_context`, and requires it to record that gap in
`limitations`. When deterministic tool code later produces evidence text, it will
be passed in through `provided_context` — one specialist call, no new agent.

### ComparisonAgent (implemented)

`app/agents/comparison.py`. `BaseAgent[ComparisonInput, ComparisonResponse]`,
`name = "comparison"`.

For requests to compare two or more options, evaluate tradeoffs, choose between
alternatives, or recommend one. Produces a structured comparison (options with
advantages/disadvantages, tradeoffs, recommendation, rationale, `confidence`
0.0–1.0, limitations). If current external evidence would be needed and none was
supplied, it says so in `limitations`.

### BriefAgent (implemented)

`app/agents/brief.py`. `BaseAgent[BriefInput, BriefResponse]`, `name = "brief"`.

For requests where the user already supplies context/material and wants it turned
into an executive brief, decision memo, or polished summary. `BriefInput`
**requires** `provided_context` (non-blank) — the agent transforms supplied
material, it does not gather it. Its prompt forbids introducing unsupported
facts, performing research, or calling another agent.

## 5. Models

### Routing models — `app/models/routing.py`

- **`AgentRoute`** — a `str` enum with **exactly** `RESEARCH`, `COMPARISON`,
  `BRIEF`. There is no `unknown` route; the orchestrator commits to the dominant
  intent.
- **`RoutingInput`** — `{ user_request: str }`, rejected if empty/whitespace.
- **`RoutingDecision`** — `{ route: AgentRoute, reasoning: str }`. `reasoning` is
  a short, shareable classification rationale for debugging (e.g. "The user is
  explicitly comparing two databases"). It is **not** a private chain-of-thought
  trace.

Route validity is enforced by Pydantic: a model response with a route outside the
enum fails through the provider's existing `StructuredOutputError` path. There is
no fuzzy matching and no silent remapping of invalid names.

### Specialist models — `app/models/specialists.py`

New, current-architecture models — they deliberately do **not** reuse the legacy
pipeline result models.

- **`ResearchInput`** — `{ user_request (non-blank), provided_context: str | None }`.
- **`ResearchResponse`** — `{ topic, summary, key_findings[], limitations[],
  sources[] }`. `sources` is empty until real tools exist.
- **`ComparisonInput`** — `{ user_request (non-blank), provided_context: str | None }`.
- **`ComparisonOption`** — `{ name, advantages[], disadvantages[] }`.
- **`ComparisonResponse`** — `{ question, options[], recommendation, rationale,
  important_tradeoffs[], confidence (0.0–1.0), limitations[] }`.
- **`BriefInput`** — `{ user_request (non-blank), provided_context (non-blank,
  required) }`.
- **`BriefResponse`** — `{ title, executive_summary, key_points[],
  recommendation: str | None, action_items[] }`.

`provided_context` on research/comparison exists so future deterministic tool
code can inject evidence text and then call exactly one specialist — it adds no
agent.

## 6. Routing semantics

| Route        | Choose when the primary request is to...                                   |
| ------------ | -------------------------------------------------------------------------- |
| `research`   | investigate, gather facts, explain via research, find current information  |
| `comparison` | compare 2+ choices, evaluate tradeoffs, choose between alternatives        |
| `brief`      | transform supplied context/material into a memo, brief, or polished summary |

Priority when a request could fit more than one:

1. Explicitly comparing alternatives / choosing between options -> `comparison`.
2. Otherwise, primarily gathering or investigating information -> `research`.
3. Otherwise, supplying source material and asking to transform it -> `brief`.

Routing is intentionally **LLM-backed** (not keyword matching) to demonstrate
semantic delegation.

## 7. Why intelligence is separated from orchestration

**LLMs handle semantic tasks:** determining user intent, specialist reasoning,
producing structured output.

**Python handles deterministic application behavior:** routing on the
orchestrator's output, validating the route, invoking exactly one specialist,
formatting results, validating structured outputs, error handling, and (later)
storage, events, and UI.

This keeps the token budget predictable, the system debuggable, and the control
flow explicit.

## 8. Why typed contracts instead of prose handoffs

Every agent consumes a Pydantic input model and returns a Pydantic output model.
Deterministic code can branch on `RoutingDecision.route` directly, validate every
structured output, and later persist, render, and export results. An agent can
move behind an HTTP boundary without changing its callers. Prose handoffs would
make all of that fragile.

## 9. Shared runtime context

`AgentRuntimeContext` (`app/agents/base.py`) is a small dataclass
(`run_id`, `iteration`) passed to `agent.run()`. It deliberately does not carry
model clients, tools, databases, or skill registries.

`RunState` (`app/models/state.py`) will become the deterministic state container
threaded through the deterministic post-processing steps. It is a plain data
model today, not a service.

## 10. Model provider layer

Agents depend only on the abstract `ModelProvider` (`app/providers/model.py`):

```
Agent  ->  ModelProvider  ->  (MockModelProvider | AnthropicModelProvider)  ->  anthropic SDK
```

- **`MockModelProvider`** replays queued responses, records every call, performs
  no I/O. Entire workflows and agent tests run against it for free.
- **`AnthropicModelProvider`** wraps `anthropic.AsyncAnthropic`, does no work at
  import time, makes no network request in `__init__`, and for structured output
  embeds the response model's JSON Schema in the prompt then validates the reply
  with Pydantic. It does **not** repair malformed output or retry — that is not
  the provider's job (and, under the reframe, nothing else's either: a failed
  request surfaces as an error).
- **`ModelConfig`** defaults to `provider="mock"`. `create_model_provider()` with
  the default config returns a `MockModelProvider` and makes no network call.
  Anthropic is reached only when `MODEL_PROVIDER=anthropic` is set together with
  `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`, and only when code actually calls a
  `generate_*` method.
- **`.env`** — `ModelConfig.from_env()` (no explicit `env` mapping) loads the
  nearest `.env` file at or above the working directory via the tiny
  dependency-free loader in `app/env.py`, so credentials can live in a
  git-ignored `.env` instead of the shell. Real environment variables always
  win over the file. Tests pass an explicit `env=` mapping and never read
  `.env`, so the automated suite stays hermetic and zero-cost.

## 11. Local-first, optional remote later

`AgentClient` (`app/transport/base.py`) is an abstract
`invoke(agent_name, payload) -> BaseModel`. Today every agent runs in-process.
Later, a specialist could run as an HTTP/A2A-style service behind the same
interface without changing the orchestrator or the dispatch layer. No transport
client is implemented yet.

## 12. Agent Skills and progressive disclosure

DecisionForge ships a small **local** Agent Skills system. Skills live on disk
under `skills/`:

```
skills/
  research/           SKILL.md  references/research-guidelines.md
  comparison/          SKILL.md  references/comparison-framework.md
  executive-brief/     SKILL.md  references/brief-template.md  scripts/validate_brief.py
```

Each `SKILL.md` is YAML frontmatter (`name`, `description`) followed by a
Markdown instruction body. `LocalSkillRegistry` (`app/skills/local.py`) reads
this tree with **plain deterministic file I/O** — no LLM, no `ModelProvider`, no
network, no agent.

### The three stages

| Stage | Method | Loads |
|---|---|---|
| 1 — Discovery | `registry.discover()` | `name` + `description` for every skill. Nothing else — not the body, not references, not scripts. |
| 2 — Activation | `registry.load(name)` | metadata + the `SKILL.md` body + the *filenames* of available references and scripts (not their contents). |
| 3 — Extension | `registry.load_reference(name, file)` / `registry.get_script_path(name, file)` | one reference's text / one script's path, **only** when code explicitly asks. Scripts are never executed by the registry. |

Malformed frontmatter raises `InvalidSkillError`; an unknown skill raises
`SkillNotFoundError`; an unknown reference/script raises
`SkillResourceNotFoundError`. Reference/script names are checked for path
traversal.

### Why there is no LLM skill selection

The orchestrator has **already** made the one semantic decision that matters —
which specialist handles the request. The skill follows deterministically from
that route via a static table (`app/skills/mapping.py`):

```
AgentRoute.RESEARCH    -> "research"
AgentRoute.COMPARISON  -> "comparison"
AgentRoute.BRIEF       -> "executive-brief"
```

```
RoutingDecision.route
   -> ROUTE_SKILLS[route]              (static Python dict, free)
   -> LocalSkillRegistry.load(name)    (file read)
   -> SkillDefinition.instructions
   -> injected into the selected specialist's system prompt
```

Asking Claude to pick a skill would be a third semantic step and more tokens for
no benefit.

### What reaches Claude

`create_dispatcher(provider, skill_registry)` builds each specialist **skill-aware**:
the specialist's constructor takes `skill_instructions: str | None`, and its
system prompt becomes `<base role prompt>` + `--- Activated skill: <name> ---` +
`<that skill's SKILL.md body>`. For a comparison request, the `ComparisonAgent`
call carries the comparison base prompt and the comparison `SKILL.md` body — and
**not** the research or executive-brief bodies, **not** any reference or script
file, and **not** skill metadata for other skills. Tests in
`tests/skills/test_skill_isolation.py` enforce this.

### Cost

Skill loading is file I/O. It issues **zero** `ModelProvider` calls. A full
successful request is still exactly **2** LLM calls (1 orchestrator + 1
specialist) — `tests/skills/test_skill_isolation.py` re-proves this for a
skill-aware dispatch.

`skills/executive-brief/scripts/validate_brief.py` is a deterministic structural
check (`title` non-empty, `executive_summary` non-empty, ≥1 `key_points`) — no
LLM, no imports of Anthropic/network libraries, no correction loop.

## 13. Deterministic tool layer (search)

DecisionForge can gather current external evidence for a specialist **before**
its single model call. This is a *tool*, not an agent.

```
OrchestratorAgent            (Claude call #1 — routing)
   -> AgentRoute
   -> deterministic search policy      (static set: RESEARCH, COMPARISON)
   -> SearchProvider.search(user_request)   (ordinary Python / network — 0 LLM calls)
   -> build_search_context(...)             (deterministic string assembly)
   -> combine_contexts(user_context, search_context)
   -> selected specialist       (Claude call #2 — the work)
   -> DispatchResult
```

### Tools are not agents

`SearchProvider` (`app/tools/search.py`) is an abstract
`search(query, *, max_results=5) -> SearchResponse`. It imports no
`ModelProvider`, no agent, no Anthropic SDK, no skill code, no dispatcher code
(verified by test). There is **no** Anthropic `tool_use`, **no** model-exposed
tool schema, and **no** ReAct loop. Claude never decides whether or when a tool
runs — deterministic Python does, before the specialist call.

- `MockSearchProvider` — replays queued `SearchResponse` objects, records calls,
  zero network. Every automated test uses it.
- `DuckDuckGoSearchProvider` — optional, free, **no API key**. The `ddgs` package
  is imported lazily inside `search()`; construction and import do nothing and
  reach no network. Missing dependency → `SearchConfigurationError`.
- `SearchConfig` defaults to `provider="mock"`. Real search is selected only by
  an explicit `SEARCH_PROVIDER=duckduckgo` / config — never auto-enabled because
  a package happens to be installed.

### Which routes search

`app/tools/policy.py`: `SEARCH_ENABLED_ROUTES = {RESEARCH, COMPARISON}`. **BRIEF
never searches** — it is a pure transformation of user-supplied material, and a
brief request makes zero search calls (the search step runs *after* routing, so
nothing is fetched for a brief). This is a static frozenset; no LLM is consulted.

### The search query

The query is the user's request verbatim
(`search_provider.search(request.user_request)`). No extra Claude call generates
or refines it.

### Context size is bounded before it reaches Claude

`build_search_context` (`app/tools/context.py`) renders results as compact plain
text with deterministic caps: **≤ 5 results**, **≤ 500 characters per snippet**,
**≈ 2,500 characters total** (trailing results are dropped whole, with a
one-line `[search context truncated: …]` marker; at least one result always
survives). No LLM compresses or ranks anything. `combine_contexts` merges
user-supplied context and search context under `USER-PROVIDED CONTEXT` /
`SEARCH EVIDENCE` headings — user content is never dropped or reordered.

### Failure behaviour

If a configured search provider raises, the error propagates and the request
stops. The orchestrator call has already happened (1 LLM call); **no** specialist
is called, **no** retry, **no** alternate provider, **no** re-route, **no** other
agent. `tests/orchestration/test_dispatcher_search.py` asserts exactly this.

### Cost

Search adds network I/O but **zero** `ModelProvider` calls. A successful request
is still exactly **2** LLM calls: `orchestrator = 1`, selected `specialist = 1`,
`search = 0`. Search evidence is placed in the specialist's *user* prompt; the
route's skill body remains the only skill content in its *system* prompt (skill
isolation is re-proved with search active).

Page fetching / crawling is deliberately **not** implemented — snippets are
enough to demonstrate the tool architecture.

## 14. Architecture Reframe

**An earlier version of this document described a different system.** That design
is no longer the target and is not planned for the current portfolio version.

The earlier design was a multi-stage research-and-decision pipeline with:

- a `PlannerAgent` that decomposed the question into research tracks
- multiple `ResearchAgent` instances running in parallel
- research aggregation
- a `JudgeAgent` that scored evidence and emitted follow-up queries
- a bounded `Judge -> Research -> Judge` loop
- separate `AnalysisAgent`, risk-analysis, and alternatives-analysis passes
  (the latter two in parallel)
- a `WriterAgent` as a downstream pipeline stage
- deterministic validation with a bounded `Writer` retry loop

It was removed **deliberately** to minimize cost, latency, and complexity:

- token spend per request was unbounded (the Judge loop) and always multi-call
- parallel and sequential LLM stages multiplied API cost and failure modes
- the value of the extra stages did not justify the cost for a portfolio project

### What is gone (do not implement, do not add placeholders for)

`PlannerAgent`, `JudgeAgent`, standalone `AnalysisAgent`, `RiskAgent`,
`AlternativesAgent`, `WriterAgent` as a pipeline stage, the Research/Judge loop,
Judge->Research feedback, bounded agent loops, iterative refinement, automatic
critique, parallel research agents, parallel risk/alternatives agents, sequential
LLM pipelines, research aggregation, synthesis pipelines, automatic agent
retries, workflow-level LLM retries, multi-agent fan-out/fan-in, autonomous agent
conversations, and arbitrary peer transfers.

### Legacy models still in the tree

These Phase 0 models describe the removed pipeline and are kept **only** so the
existing Phase 0/1 tests keep passing:

`app/models/planning.py` (`PlannerInput`, `ResearchPlan`, `ResearchTrack`),
`app/models/research.py` (`ResearchFinding`, `ResearchResult`, `ResearchTask`,
`Source`), `app/models/judging.py` (`JudgeInput`, `JudgeResult`),
`app/models/analysis.py` (`AnalysisMode`, `AnalysisInput`, `OptionAssessment`,
`DecisionAnalysis`, `SecondaryAnalysisInput`, `RiskAnalysis`,
`AlternativesAnalysis`), `app/models/brief.py` (legacy `BriefInput`,
`FinalBrief`), and the multi-stage members of `RunStatus` /
`app/orchestration/transitions.py`.

The legacy `BriefInput` in `app/models/brief.py` is no longer re-exported from
`app/models/__init__.py` (small, safe cleanup — it had no importers outside its
own module); `app.models.BriefInput` now resolves to the current-architecture
model in `app/models/specialists.py`. The legacy class is still importable
directly as `app.models.brief.BriefInput` so the Phase 0 tests are undisturbed.

**Rules for legacy code:** do not build new functionality on it; do not treat its
presence as evidence the old design is planned. A dedicated, controlled cleanup
phase will remove it. The specialist agents (`research`, `comparison`, `brief`)
use their own fresh, minimal models in `app/models/specialists.py`.

### What the project still demonstrates

Parent/orchestrator + specialist hierarchy, constrained single-hop delegation,
specialized agents, structured Pydantic outputs, shared runtime context, the
model-provider abstraction, local-first execution, local Agent Skills with
progressive disclosure (§12), and — later — tool use, optional remote transport,
execution tracing, and persistence. The project does **not** aim to mechanically
implement every multi-agent pattern (no `SequentialAgent` / `ParallelAgent` /
`LoopAgent` abstractions).

## 15. Build status

### Implemented

- **Phase 0** — package skeleton; contracts (`BaseAgent` + `AgentRuntimeContext`,
  `ModelProvider`, `BaseTool` + `ToolResult`, `SkillRegistry`, `AgentClient`);
  `RunState` / `RunStatus`; `WorkflowConfig`; event contracts; tests. *(Some
  models are now legacy — see §14.)*
- **Phase 1** — `ModelProvider` layer: `ModelConfig` + `ModelProviderType`,
  provider exceptions, `MockModelProvider`, `AnthropicModelProvider`,
  `create_model_provider` factory, `scripts/model_smoke_test.py`, provider tests.
- **Phase 2** — routing foundation: `AgentRoute` / `RoutingInput` /
  `RoutingDecision`, `OrchestratorAgent` + system prompt, orchestrator tests,
  `scripts/orchestrator_demo.py`, this reframed document.
- **Phase 3** — the three leaf specialists: `app/models/specialists.py`
  (`ResearchInput`/`ResearchResponse`, `ComparisonInput`/`ComparisonOption`/
  `ComparisonResponse`, `BriefInput`/`BriefResponse`), `ResearchAgent`,
  `ComparisonAgent`, `BriefAgent` (each one `ModelProvider` call, no tools, no
  delegation), their mock tests, `tests/models/test_specialist_models.py`, and
  `scripts/specialists_demo.py`.
- **Phase 4** — single-hop dispatch: `app/models/dispatch.py` (`DispatchRequest`,
  `DispatchResult`), `DecisionForgeDispatcher` + `app/orchestration/exceptions.py`
  (`DispatchError`, `MissingBriefContextError`, `UnexpectedRouteError`),
  `app/runtime.py` (`create_dispatcher`), dispatcher tests including the explicit
  two-call-maximum test, and the first end-to-end demo
  `scripts/dispatch_demo.py`. Routing, specialist behavior, and dispatch are
  still each covered by their own unit tests.
- **Phase 5** — local Agent Skills (§12): the `skills/` tree with three
  `SKILL.md` files, `LocalSkillRegistry` (discover / load / `load_reference` /
  `get_script_path`) + `app/skills/exceptions.py`, the static
  `app/skills/mapping.py` route→skill table, `skill_instructions` on each
  specialist, `create_dispatcher(provider, skill_registry)` wiring, the
  deterministic `validate_brief.py` skill script, `scripts/skills_demo.py`, and
  `tests/skills/` (registry, mapping, isolation + two-call re-proof, validator).
  Depends on PyYAML.
- **Phase 6** — deterministic search-tool layer (§13): `app/models/search.py`
  (`SearchResult`, `SearchResponse`), `app/tools/search.py` (`SearchProvider`,
  `MockSearchProvider`, optional no-key `DuckDuckGoSearchProvider`, `SearchConfig`
  + factory), `app/tools/context.py` (`build_search_context`, `combine_contexts`,
  size caps), `app/tools/policy.py` (`SEARCH_ENABLED_ROUTES`),
  `app/tools/exceptions.py`, dispatcher + `create_dispatcher` `search_provider`
  wiring, small research/comparison prompt notes, `scripts/tools_demo.py`,
  updated `scripts/dispatch_demo.py`, and `tests/tools/` + search dispatcher
  tests. Optional `ddgs` dependency (`[search]` extra).

### Not implemented yet

- full webpage fetching / scraping / crawling
- autonomous / model-driven tool use
- deterministic post-processing beyond result assembly (formatting, storage)
- persistence, events wiring, HTTP/A2A transport, UI
