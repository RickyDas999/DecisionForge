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

## Status (Phase 5)

Implemented:

- the model-provider layer (`MockModelProvider`, `AnthropicModelProvider`, config,
  factory)
- the routing schema (`AgentRoute`, `RoutingInput`, `RoutingDecision`)
- `OrchestratorAgent` (single structured model call -> `RoutingDecision`)
- the three **leaf** specialist agents — `ResearchAgent`, `ComparisonAgent`,
  `BriefAgent` — each one structured model call, no tools, no delegation
- current-architecture structured result models (`app/models/specialists.py`,
  `app/models/dispatch.py`)
- **`DecisionForgeDispatcher`** — the deterministic single-hop path: one
  orchestrator call, then exactly one specialist call, then a typed
  `DispatchResult`. No fallback, no retry, no loop, no parallelism.
- **local Agent Skills** — a `skills/` tree with YAML-frontmatter `SKILL.md`
  files and three-stage progressive disclosure (discovery = metadata only,
  activation = one `SKILL.md` body, extension = references/scripts on explicit
  demand), a deterministic `LocalSkillRegistry`, a **static route→skill mapping**
  (no LLM picks the skill), and skill-aware specialist prompts that receive only
  their own skill's instructions.
- demos: `scripts/skills_demo.py` (progressive disclosure) and
  `scripts/dispatch_demo.py` (end-to-end); both zero-cost by default.

Not implemented yet:

- real web search / fetch tools (feeding `provided_context`)
- persistence / run history
- web UI
- optional HTTP/A2A transport

## Model provider & cost

- **Mock is the default and needs no credentials.** The test suite and the
  default demos make no network calls.
- **Anthropic mode is opt-in:** set `MODEL_PROVIDER=anthropic` with
  `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`, and install the extra
  (`pip install -e ".[anthropic]"`). This uses the Anthropic API and **may incur
  charges billed to your Anthropic account**.
- An Anthropic API key/account is **separate** from a Claude Code / Claude.ai
  subscription and is billed differently.

### Using a `.env` file

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
# then edit .env:
#   MODEL_PROVIDER=anthropic
#   ANTHROPIC_API_KEY=sk-ant-...
#   ANTHROPIC_MODEL=<a-model-id>
```

`ModelConfig.from_env()` (used by every `--live` script path) auto-loads the
nearest `.env` at or above the working directory. Real environment variables
always take precedence over the file, and `.env` is git-ignored so your key is
never committed. Automated tests and the default (mock) demos do not read `.env`
and stay zero-cost.

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
python scripts/dispatch_demo.py         # END-TO-END: request -> orchestrator -> one specialist -> result
python scripts/skills_demo.py           # Agent Skills: discovery -> activation -> extension (file I/O only)
python scripts/orchestrator_demo.py     # routes 3 sample requests via MockModelProvider
python scripts/specialists_demo.py      # runs all 3 leaf specialists via MockModelProvider
python scripts/model_smoke_test.py      # exercises both provider methods via MockModelProvider
```

Each script has an explicit `--live` mode that makes real, potentially billable
Anthropic requests and requires `MODEL_PROVIDER=anthropic` plus credentials.
`dispatch_demo.py --live "<request>"` makes **at most 2** calls (orchestrator +
one specialist; `--context "..."` needed if routing picks brief);
`orchestrator_demo.py --live "<request>"` makes exactly one call;
`specialists_demo.py --live --agent <name> "<request>"` makes exactly one call
(and `--agent brief` also needs `--context "..."`). Do not run `--live` unless
you intend to spend API credit.
