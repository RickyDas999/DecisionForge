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

## Status (Phase 7)

Implemented:

- the model-provider layer (`MockModelProvider`, `AnthropicModelProvider`, config,
  factory)
- the routing schema (`AgentRoute`, `RoutingInput`, `RoutingDecision`)
- `OrchestratorAgent` (single structured model call -> `RoutingDecision`)
- the three **leaf** specialist agents — `ResearchAgent`, `ComparisonAgent`,
  `BriefAgent` — each one structured model call, no delegation
- current-architecture structured models (`app/models/{specialists,dispatch,search}.py`)
- **`DecisionForgeDispatcher`** — the deterministic single-hop path: one
  orchestrator call, then exactly one specialist call, then a typed
  `DispatchResult`. No fallback, no retry, no loop, no parallelism.
- **local Agent Skills** — a `skills/` tree with YAML-frontmatter `SKILL.md`
  files and three-stage progressive disclosure, a deterministic
  `LocalSkillRegistry`, a **static route→skill mapping** (no LLM picks the
  skill), and skill-aware specialist prompts.
- **deterministic search-tool layer** — a `SearchProvider` abstraction with an
  offline `MockSearchProvider` (the default) and an **optional no-key**
  `DuckDuckGoSearchProvider`. When a search provider is configured, the RESEARCH
  and COMPARISON routes gather external evidence *before* their single model
  call and pass it in via `provided_context` (deterministically size-capped);
  **BRIEF never searches**. Search adds **zero** LLM calls; a search failure
  stops the request with no retry and no fallback.
- **local SQLite persistence + execution tracing** — `DecisionForgeService`
  wraps the dispatcher, records each run (`RunRecord`: route, selected
  specialist, search usage, status, serialized result, error, timestamps) and a
  chronological event stream (`run.started` → `route.selected` →
  optional `search.*` → `specialist.*` → `run.completed` / `run.failed`) into a
  local `sqlite3` database. Deterministic file I/O — **zero** model calls; a
  failed run is stored and the original exception is re-raised unchanged.
- demos: `scripts/persistence_demo.py`, `scripts/tools_demo.py`,
  `scripts/skills_demo.py`, `scripts/dispatch_demo.py`; all zero-cost by default.

Not claimed: DecisionForge has **no autonomous research** — Claude never decides
to call a tool; deterministic Python does, once, before the specialist.

Not implemented yet:

- web UI (the persisted run + event history is the foundation for it)
- HTTP/A2A transport
- full webpage scraping / crawling
- autonomous / model-driven tool use

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
python scripts/dispatch_demo.py         # END-TO-END: request -> orchestrator -> [search] -> one specialist -> result
python scripts/persistence_demo.py      # one run persisted to a temp SQLite DB + its event stream
python scripts/tools_demo.py            # search tool: MockSearchProvider + build_search_context (file/CPU only)
python scripts/skills_demo.py           # Agent Skills: discovery -> activation -> extension (file I/O only)
python scripts/orchestrator_demo.py     # routes 3 sample requests via MockModelProvider
python scripts/specialists_demo.py      # runs all 3 leaf specialists via MockModelProvider
python scripts/model_smoke_test.py      # exercises both provider methods via MockModelProvider
```

Database location: `DECISIONFORGE_DB_PATH`, else `./data/decisionforge.db`
(`data/` and `*.db` are git-ignored).

Each script has an explicit `--live` mode that makes real, potentially billable
Anthropic requests and requires `MODEL_PROVIDER=anthropic` plus credentials.
`dispatch_demo.py --live "<request>"` makes **at most 2** calls (orchestrator +
one specialist; `--context "..."` needed if routing picks brief);
`orchestrator_demo.py --live "<request>"` makes exactly one call;
`specialists_demo.py --live --agent <name> "<request>"` makes exactly one call
(and `--agent brief` also needs `--context "..."`). Do not run `--live` unless
you intend to spend API credit.

`tools_demo.py --real-search "<query>"` performs **one live DuckDuckGo search**
(no Anthropic call, no key) — install the extra with `pip install -e ".[search]"`.
The `--live` dispatch demo does not run search; use `tools_demo.py` to exercise
the real search provider on its own.
