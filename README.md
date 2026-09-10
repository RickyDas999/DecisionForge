# DecisionForge

A local-first, multi-agent research and decision intelligence platform. Given a
decision-oriented question (for example, *"Should our startup use PostgreSQL or
MongoDB?"*), the finished system coordinates specialized agents to plan research,
gather and judge evidence, analyze tradeoffs and risks, and produce a structured
decision brief.

## Phase 0 scope

Phase 0 is **architecture scaffolding only**. It contains:

- the project skeleton and package layout
- core Pydantic domain models (planning, research, judging, analysis, brief, state, events)
- abstract agent, model-provider, tool, skill, and transport contracts
- shared `RunState` and the `RunStatus` lifecycle enum
- explicit workflow state-transition validation
- bounded `WorkflowConfig` limits
- architecture documentation
- tests for the models, transitions, and config

There is **no LLM functionality yet** — no Anthropic/Claude calls, no concrete
agents, no web search, no HTTP, no API, no frontend, no database, no
orchestration engine. See `docs/architecture.md` for what each later phase adds.

## Requirements

- Python 3.12

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Test

```bash
pytest
```

All tests should pass. They exercise model construction, validation bounds, and
the state-transition rules — no network access is involved.
