# DecisionForge

A local-first, portfolio-quality application that demonstrates a **constrained
multi-agent architecture** while keeping Claude token/API usage low.

## How it works

```
User request
   -> OrchestratorAgent   classifies the request (1 Claude call)
   -> exactly one of:
        ResearchAgent      investigate / gather / explain a topic
        ComparisonAgent    compare options, evaluate tradeoffs, recommend
        BriefAgent         turn supplied context into an executive brief / memo
      (the selected specialist: 1 Claude call)
   -> deterministic Python   validation, formatting, storage, events, UI
   -> Result
```

- **One OrchestratorAgent + three specialist agents.**
- **Single-hop routing:** the orchestrator selects exactly one specialist; the
  specialists never call other agents.
- **At most 2 LLM calls per request** (orchestrator + one specialist). No agent
  loops, no LLM retry loops, no parallel LLM calls, no multi-stage pipeline.
- **Mock or Anthropic model provider**, behind one `ModelProvider` abstraction —
  agents never import a vendor SDK.
- **Zero-cost mock development mode** is the default.

> An earlier design was a larger multi-stage research/judge/analysis/writer
> pipeline. It was intentionally removed to minimize cost, latency, and
> complexity, and is **not** planned for this version. See
> `docs/architecture.md` -> "Architecture Reframe".

## Status (Phase 2)

Implemented:

- the model-provider layer (`MockModelProvider`, `AnthropicModelProvider`, config,
  factory)
- the routing schema (`AgentRoute`, `RoutingInput`, `RoutingDecision`)
- `OrchestratorAgent` (single structured model call -> `RoutingDecision`)

Not implemented yet:

- the three specialist agents (`ResearchAgent`, `ComparisonAgent`, `BriefAgent`)
- the deterministic dispatch that invokes the selected specialist
- deterministic post-processing, persistence, events, UI

## Model provider & cost

- **Mock is the default and needs no credentials.** The test suite and the
  default demo make no network calls.
- **Anthropic mode is opt-in:** set `MODEL_PROVIDER=anthropic` with
  `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`, and install the extra
  (`pip install -e ".[anthropic]"`). This uses the Anthropic API and **may incur
  charges billed to your Anthropic account**.
- An Anthropic API key/account is **separate** from a Claude Code / Claude.ai
  subscription and is billed differently.

## Requirements

- Python 3.12

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional, only for real Anthropic calls: `pip install -e ".[dev,anthropic]"`.

## Test

```bash
pytest
```

All tests pass and make **no** network calls (the Anthropic SDK is fully faked in
tests).

## Demos (zero cost)

```bash
python scripts/orchestrator_demo.py     # routes 3 sample requests via MockModelProvider
python scripts/model_smoke_test.py      # exercises both provider methods via MockModelProvider
```

Each script has an explicit `--live` mode that makes real, potentially billable
Anthropic requests and requires `MODEL_PROVIDER=anthropic` plus credentials.
`orchestrator_demo.py --live "<request>"` makes exactly one call. Do not run
`--live` unless you intend to spend API credit.
