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
                  OrchestratorAgent
                 /       |        \
                /        |         \
        ResearchAgent  ComparisonAgent  BriefAgent
```

There are no edges between the specialists. The orchestrator is the only node
allowed to choose an outgoing edge, and it chooses exactly one. This models
controlled parent/sub-agent routing without an open-ended agent graph.

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

### ResearchAgent (not implemented)

For requests that primarily ask to investigate, gather facts, explain via
research, find current information, or summarize a topic from external
information. May later use free search/fetch **tools** (still one LLM call).

### ComparisonAgent (not implemented)

For requests that ask to compare two or more options, evaluate tradeoffs, choose
between alternatives, or recommend one. Produces a structured comparison.

### BriefAgent (not implemented)

For requests where the user already supplies context/material and wants it turned
into an executive brief, decision memo, or polished summary. It works only from
the supplied context; if there is not enough material, it says so in its
structured result. It never calls `ResearchAgent` or any other agent first.

## 5. Routing models

`app/models/routing.py`:

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

## 11. Local-first, optional remote later

`AgentClient` (`app/transport/base.py`) is an abstract
`invoke(agent_name, payload) -> BaseModel`. Today every agent runs in-process.
Later, a specialist could run as an HTTP/A2A-style service behind the same
interface without changing the orchestrator or the dispatch layer. No transport
client is implemented yet.

## 12. Agent Skills (later)

`app/skills/base.py` defines the skill contracts. The future runtime will use
progressive disclosure — load metadata for discovery, the `SKILL.md` body on
activation, references/scripts only when needed. No skill runtime exists yet.

## 13. Architecture Reframe

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
`AlternativesAnalysis`), `app/models/brief.py` (`BriefInput`, `FinalBrief`), and
the multi-stage members of `RunStatus` / `app/orchestration/transitions.py`.

**Rules for legacy code:** do not build new functionality on it; do not treat its
presence as evidence the old design is planned. A dedicated, controlled cleanup
phase will remove it. New specialist agents (`research`, `comparison`, `brief`)
will get their own fresh, minimal models.

### What the project still demonstrates

Parent/orchestrator + specialist hierarchy, constrained single-hop delegation,
specialized agents, structured Pydantic outputs, shared runtime context, the
model-provider abstraction, local-first execution, and — later — Agent Skills
with progressive disclosure, tool use, optional remote transport, execution
tracing, and persistence. The project does **not** aim to mechanically implement
every multi-agent pattern (no `SequentialAgent` / `ParallelAgent` / `LoopAgent`
abstractions).

## 14. Build status

### Implemented

- **Phase 0** — package skeleton; contracts (`BaseAgent` + `AgentRuntimeContext`,
  `ModelProvider`, `BaseTool` + `ToolResult`, `SkillRegistry`, `AgentClient`);
  `RunState` / `RunStatus`; `WorkflowConfig`; event contracts; tests. *(Some
  models are now legacy — see §13.)*
- **Phase 1** — `ModelProvider` layer: `ModelConfig` + `ModelProviderType`,
  provider exceptions, `MockModelProvider`, `AnthropicModelProvider`,
  `create_model_provider` factory, `scripts/model_smoke_test.py`, provider tests.
- **Phase 2** — routing foundation: `AgentRoute` / `RoutingInput` /
  `RoutingDecision`, `OrchestratorAgent` + system prompt, orchestrator tests,
  `scripts/orchestrator_demo.py`, this reframed document.

### Not implemented yet

- `ResearchAgent`, `ComparisonAgent`, `BriefAgent`
- the deterministic dispatch layer that turns a `RoutingDecision` into exactly
  one specialist call
- deterministic post-processing (formatting, validation, storage)
- persistence, events wiring, HTTP transport, UI
