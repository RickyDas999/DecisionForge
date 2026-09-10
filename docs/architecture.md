# DecisionForge Architecture

## 1. What DecisionForge is

DecisionForge is a local-first, portfolio-quality multi-agent research and
decision intelligence platform. A user submits a decision-oriented question such
as *"Should our startup use PostgreSQL or MongoDB?"* and the system coordinates a
small set of specialized agents to research the question, evaluate the quality of
the evidence, analyze the tradeoffs and risks, and emit a structured decision
brief.

The project exists to demonstrate — independently, in Python, with Claude as the
eventual LLM provider — the architectural principles of high-performance
multi-agent systems: specialized agents, hierarchical delegation, deterministic
orchestration, sequential and parallel workflows, bounded iterative loops, shared
typed state, structured outputs, reusable Agent Skills with progressive
disclosure, tool use, observability, and eventual local-vs-remote execution.

It is deliberately **not** an unrestricted agent swarm. The orchestrator owns
workflow control and delegation; specialist agents never arbitrarily call other
agents.

## 2. The intended multi-agent workflow

```
User request
    -> PlannerAgent                     (normalize question, identify options, build research tracks)
    -> ResearchAgent x N (parallel)     (one instance per independent research track)
    -> Research aggregation             (deterministic merge of track results)
    -> JudgeAgent                       (structured verdict on evidence quality)
         |- rejected -> follow-up ResearchAgent pass -> JudgeAgent again
         |             (repeat until approved or max_research_iterations reached)
         '- approved -> continue
    -> AnalysisAgent (PRIMARY mode)     (option assessments + recommendation)
    -> AnalysisAgent (RISK) + AnalysisAgent (ALTERNATIVES)   (parallel)
    -> WriterAgent                      (assemble the FinalBrief)
    -> Deterministic validation         (retry writing up to max_validation_attempts)
    -> Final result
```

Approximately five core LLM agent implementations back this workflow:

| Agent           | Responsibility                                                        | Reuse                                              |
| --------------- | -------------------------------------------------------------------- | ------------------------------------------------- |
| `PlannerAgent`  | Understand and normalize the decision, identify options, build tracks | single instance                                   |
| `ResearchAgent` | Execute one research track                                            | instantiated per track; instances run concurrently |
| `JudgeAgent`    | Evaluate evidence, decide sufficiency, emit follow-up queries         | single instance, invoked once per loop iteration  |
| `AnalysisAgent` | Decision analysis                                                     | reused in `PRIMARY`, `RISK`, `ALTERNATIVES` modes  |
| `WriterAgent`   | Produce the final structured brief                                    | single instance                                   |

## 3. Why the system separates intelligence from orchestration

A single all-knowing orchestrator prompt is brittle, hard to test, expensive to
run, and impossible to reason about. DecisionForge instead splits the system
along a clean seam:

- **LLMs handle semantic judgment.**
- **Deterministic Python handles workflow mechanics.**

This keeps each half simple, independently testable, and cheap to operate. Most
of the workflow logic can be exercised with a mock model provider and no paid API
usage.

## 4. Why semantic reasoning is delegated to LLM agents

Some sub-problems have no deterministic solution: understanding user intent,
deciding what to research, judging whether evidence is strong enough, weighing
tradeoffs, and articulating a recommendation. These are delegated to LLM agents,
each with a narrow, well-scoped responsibility and a typed output contract.

## 5. Why deterministic Python owns workflow sequencing

Running agents in sequence, running independent agents in parallel, incrementing
and bounding loop counters, transitioning state, retrying, timing out, persisting
results, and emitting events are all mechanical concerns with correct, testable,
deterministic implementations. Putting them in code (not a prompt) makes the
system predictable and debuggable, and prevents runaway cost or infinite loops.

## 6. Why agents use typed contracts instead of arbitrary prose handoffs

Every agent consumes a Pydantic input model and returns a Pydantic output model.
Structured handoffs mean:

- the orchestrator can branch deterministically (e.g. on `JudgeResult.approved`)
  and reuse fields directly (e.g. `JudgeResult.follow_up_queries`)
- outputs can be validated, persisted, rendered in a UI, and exported
- an agent can later move behind an HTTP boundary without changing callers
- tests can assert on fields instead of parsing free text

Prose handoffs would make all of the above fragile.

## 7. How RunState acts as shared state

`app/models/state.py` defines `RunState`: a single typed container carrying the
run id, original query, current `RunStatus`, research iteration counter, and the
accumulated artifacts (`research_plan`, `research_results`, `judge_result`,
`analysis`, `risk_analysis`, `alternatives_analysis`, `final_brief`), plus errors
and timezone-aware UTC timestamps.

Each orchestration stage reads the fields it needs from `RunState` and writes its
result back. In Phase 0 it is a plain data model — deliberately not a service,
repository, or event emitter.

## 8. How future sequential workflows will work

A sequential workflow is an ordered list of stages. The deterministic engine (a
later phase) will, for each stage: validate the `RunStatus` transition via
`validate_transition`, emit a `workflow.status.changed` event, invoke the stage's
agent through the `AgentClient` transport, write the typed result into `RunState`,
and advance. Any stage failure transitions the run to `FAILED`.

## 9. How future parallel workflows will work

Where stages are independent, the engine will fan them out concurrently
(`asyncio.gather` or a bounded task group) and then deterministically aggregate
the results. Two places use this:

- the initial research fan-out — up to `max_parallel_researchers` `ResearchAgent`
  instances, one per `ResearchTrack`
- secondary analysis — `RISK` and `ALTERNATIVES` `AnalysisAgent` passes together

Concurrency is owned by the engine, not by the agents.

## 10. Why parallel agents should operate on independent subtasks

Parallelism is only safe when tasks do not depend on each other's output and do
not write the same state. `PlannerAgent` deliberately decomposes the question into
*independent* research tracks so the fan-out is race-free: each `ResearchAgent`
instance owns one track and produces one `ResearchResult`, and aggregation is a
pure deterministic merge afterward. The same reasoning applies to the risk and
alternatives analyses, which read the same inputs but produce disjoint outputs.

## 11. How the bounded Judge/research loop is intended to work

1. Aggregate the current `research_results`.
2. Invoke `JudgeAgent` -> `JudgeResult`.
3. If `approved` is true, emit `judge.approved` and leave the loop.
4. Otherwise emit `judge.rejected`, increment `research_iteration`, and — if the
   counter is still below `max_research_iterations` — run another `ResearchAgent`
   pass seeded with `JudgeResult.follow_up_queries`, then return to step 1.
5. If the iteration cap is reached first, the loop exits with the best evidence so
   far and the workflow continues to analysis (the cap always wins).

The LLM decides *whether* evidence is sufficient and *what* to ask next; Python
decides *how many times* the loop may run.

## 12. Why loops have hard maximum iteration limits

An LLM judge can, in principle, never be satisfied. `WorkflowConfig`
(`max_research_iterations`, `max_validation_attempts`) puts a deterministic
ceiling on every loop so a run always terminates, cost stays bounded, and latency
is predictable. These limits are defined in Phase 0, before any loop engine
exists, precisely so that no later loop can be written without one.

## 13. How Agent Skills will later support progressive disclosure

`app/skills/base.py` defines the contract for reusable Agent Skills
(`research`, `source-quality`, `decision-analysis`, `executive-brief`). The future
runtime will load skill context in three stages:

- **Stage 1 — Discovery:** load only `SkillMetadata` (name, description) so an
  agent can tell whether a skill is relevant.
- **Stage 2 — Activation:** load the full `SkillDefinition` (the `SKILL.md` body /
  `instructions`) only when the skill is actually needed.
- **Stage 3 — Extension:** load `references` and `scripts` only when a task
  requires them.

This keeps prompt context small until depth is genuinely required. Phase 0 ships
the contracts only — no `SKILL.md` parsing, directory scanning, or script
execution.

## 14. How local-first execution will later support optional remote agents

`app/transport/base.py` defines `AgentClient` with a single
`invoke(agent_name, payload) -> BaseModel` method. Orchestration depends only on
this interface, so the same workflow code works whether an agent runs in-process
or over HTTP:

```
AgentClient
├── LocalAgentClient   (later: call the agent object directly, in-process)
└── HttpAgentClient    (later: POST the payload to an agent service)
```

Similarly, agents depend on the `ModelProvider` abstraction rather than any
specific vendor SDK, so `MockProvider` / `AnthropicProvider` / `LocalProvider` are
interchangeable. Neither client nor any provider is implemented in Phase 0.

## 15. What Phase 0 contains — and what it intentionally does not

### Contains

- project skeleton and packaging (`pyproject.toml`, `.gitignore`, `.env.example`)
- core Pydantic domain models: `planning`, `research`, `judging`, `analysis`,
  `brief`, `events`, `state`
- abstract contracts: `BaseAgent` + `AgentRuntimeContext`, `ModelProvider`,
  `BaseTool` + `ToolResult`, `SkillRegistry` + `SkillMetadata` /
  `SkillDefinition`, `AgentClient`
- `RunState` and the `RunStatus` lifecycle enum
- explicit `validate_transition` state-machine rules + `InvalidStateTransition`
- `WorkflowConfig` with bounded defaults
- `EventType` / `WorkflowEvent` contracts
- this document and `README.md`
- tests for models, validation bounds, transitions, and config

### Intentionally does NOT contain

- any Anthropic API / Claude SDK usage
- any concrete agent (`PlannerAgent`, `ResearchAgent`, `JudgeAgent`,
  `AnalysisAgent`, `WriterAgent`)
- web search or HTTP fetching
- FastAPI, SSE/WebSockets, or any frontend
- SQLite / SQLAlchemy / persistence
- HTTP agent services or `LocalAgentClient` / `HttpAgentClient` implementations
- the orchestration engine: sequential, parallel, or loop execution; retries;
  timeout handling
- a real Agent Skills loader or real validation scripts
- an event bus
- Docker, Kubernetes, Redis, Celery, message queues, vector databases, auth

Phase 0 has no working application behavior — only interfaces, models, basic
validation, and tests.
