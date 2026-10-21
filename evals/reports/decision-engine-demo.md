# Eval report: decision-engine-demo

30 cases · 1 errors · 59 LLM calls · charged $0.00000 · $0.00031/case if live · p50 latency 1 ms

| metric | score | n | Δ vs demo |
|---|---|---|---|
| route_accuracy | 0.93 | 30 | = |
| contract_pass | 0.97 | 30 | = |
| option_recall | 0.83 | 12 | +0.83 |
| recommendation_match | 0.71 | 7 | +0.71 |
| rubric_coverage | 0.13 | 30 | +0.11 |
| decision_completeness | 1.00 | 11 |  |

## Cases

| case | route | route_accuracy | contract_pass | option_recall | recommendation_match | rubric_coverage | decision_completeness | cost if live |
|---|---|---|---|---|---|---|---|---|
| cmp-postgres-mongo | comparison | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 1.00 | $0.00045 |
| cmp-aws-gcp | comparison | 1.00 | 1.00 | 1.00 | — | 0.50 | 1.00 | $0.00043 |
| cmp-fastapi-flask | comparison | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | $0.00043 |
| cmp-react-vue-svelte | comparison | 1.00 | 1.00 | 1.00 | — | 0.50 | 1.00 | $0.00051 |
| cmp-kafka-rabbitmq | comparison | 1.00 | 1.00 | 1.00 | — | 0.00 | 1.00 | $0.00044 |
| cmp-monolith-microservices | comparison | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | $0.00046 |
| cmp-build-buy-auth | comparison | 1.00 | 1.00 | 0.50 | 1.00 | 0.50 | 1.00 | $0.00044 |
| cmp-pinecone-pgvector | comparison | 1.00 | 1.00 | 1.00 | — | 0.67 | 1.00 | $0.00045 |
| cmp-k8s-ecs | comparison | 1.00 | 1.00 | 1.00 | 0.00 | 0.50 | 1.00 | $0.00045 |
| cmp-redis-memcached | comparison | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | $0.00043 |
| cmp-graphql-rest | **research** (want comparison) | 0.00 | 1.00 | 0.00 | — | 0.00 | — | $0.00026 |
| cmp-claude-model-tier | comparison | 1.00 | 1.00 | 0.50 | 0.00 | 0.33 | 1.00 | $0.00046 |
| res-vector-dbs | research | 1.00 | 1.00 | — | — | 0.00 | — | $0.00026 |
| res-observability | research | 1.00 | 1.00 | — | — | 0.00 | — | $0.00026 |
| res-edge-computing | research | 1.00 | 1.00 | — | — | 0.00 | — | $0.00026 |
| res-rag-eval | research | 1.00 | 1.00 | — | — | 0.00 | — | $0.00026 |
| res-prompt-injection | research | 1.00 | 1.00 | — | — | 0.00 | — | $0.00026 |
| res-sqlite-prod | research | 1.00 | 1.00 | — | — | 0.00 | — | $0.00026 |
| res-feature-flags | research | 1.00 | 1.00 | — | — | 0.00 | — | $0.00026 |
| res-llm-caching | research | 1.00 | 1.00 | — | — | 0.50 | — | $0.00026 |
| res-zero-trust | **brief** (want research) | 0.00 | 0.00 | — | — | 0.00 | — | $0.00008 |
| res-wasm | research | 1.00 | 1.00 | — | — | 0.00 | — | $0.00026 |
| brf-caching-findings | brief | 1.00 | 1.00 | — | — | 0.00 | — | $0.00021 |
| brf-vendor-memo | brief | 1.00 | 1.00 | — | — | 0.00 | — | $0.00021 |
| brf-slo-summary | brief | 1.00 | 1.00 | — | — | 0.00 | — | $0.00021 |
| brf-hiring-plan | brief | 1.00 | 1.00 | — | — | 0.00 | — | $0.00021 |
| brf-incident | brief | 1.00 | 1.00 | — | — | 0.00 | — | $0.00021 |
| brf-security-audit | brief | 1.00 | 1.00 | — | — | 0.00 | — | $0.00021 |
| brf-pricing-test | brief | 1.00 | 1.00 | — | — | 0.00 | — | $0.00021 |
| brf-migration-status | brief | 1.00 | 1.00 | — | — | 0.00 | — | $0.00021 |

## Errors

- `res-zero-trust`: MissingBriefContextError: Brief requests require provided context.
