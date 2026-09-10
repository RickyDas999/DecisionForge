# DecisionForge

A local-first, multi-agent research and decision intelligence platform. Given a
decision-oriented question (for example, *"Should our startup use PostgreSQL or
MongoDB?"*), the finished system coordinates specialized agents to plan research,
gather and judge evidence, analyze tradeoffs and risks, and produce a structured
decision brief.

## Status

The project is being built in phases. See `docs/architecture.md` for the full
design.

- **Phase 0 — architecture scaffolding.** Package layout, core Pydantic domain
  models, abstract contracts (agent, model provider, tool, skill, transport),
  shared `RunState` + `RunStatus`, workflow state-transition validation, bounded
  `WorkflowConfig`, event contracts, tests.
- **Phase 1 — the model-provider layer.** A vendor-neutral `ModelProvider`
  interface with two implementations: `MockModelProvider` (deterministic, offline,
  free) and `AnthropicModelProvider` (real Claude access). Provider
  configuration, a construction factory, provider exceptions, and an optional
  manual smoke-test script.

### Not built yet

- No DecisionForge agents exist (`PlannerAgent`, `ResearchAgent`, `JudgeAgent`,
  `AnalysisAgent`, `WriterAgent`).
- No working multi-agent workflow or orchestration engine exists.
- No persistence, API, or frontend exists.

## The model provider

Future agents depend only on `app.providers.model.ModelProvider`. They call
`generate_text(...)` / `generate_structured(..., response_model=SomeModel)` and
never touch a vendor SDK directly.

- **Mock mode is the default and requires no credentials.** `ModelConfig`
  defaults to `provider="mock"`; the default factory returns `MockModelProvider`;
  the test suite makes no network calls.
- **Anthropic mode is opt-in.** Set `MODEL_PROVIDER=anthropic` together with
  `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`. This uses the Anthropic API and
  **may incur API charges billed to your Anthropic account**. Install the extra
  with `pip install -e ".[anthropic]"`.
- An **Anthropic API key/account is separate from a Claude Code / Claude.ai
  subscription.** Subscription usage does not grant API access and is billed
  differently.

## Requirements

- Python 3.12

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional, only for real Anthropic calls:

```bash
pip install -e ".[dev,anthropic]"
```

## Test

```bash
pytest
```

All tests pass and make **no** network calls. They cover the domain models,
state transitions, workflow config, and both model providers (the Anthropic SDK
is fully faked).

Optional manual smoke test (mock mode — no network, no cost):

```bash
python scripts/model_smoke_test.py
```

The `--live` flag on that script makes real, potentially billable Anthropic
requests and requires `MODEL_PROVIDER=anthropic` plus credentials. Do not run it
unless you intend to spend API credit.
