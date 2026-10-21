# Eval report: demo

30 cases · 1 errors · 59 LLM calls · charged $0.00000 · $0.00025/case if live · p50 latency 1 ms

| metric | score | n |
|---|---|---|
| route_accuracy | 0.93 | 30 |
| contract_pass | 0.97 | 30 |
| option_recall | 0.00 | 12 |
| recommendation_match | 0.00 | 7 |
| rubric_coverage | 0.02 | 30 |

## Cases

| case | route | route_accuracy | contract_pass | option_recall | recommendation_match | rubric_coverage | cost if live |
|---|---|---|---|---|---|---|---|
| cmp-postgres-mongo | comparison | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | $0.00029 |
| cmp-aws-gcp | comparison | 1.00 | 1.00 | 0.00 | — | 0.00 | $0.00028 |
| cmp-fastapi-flask | comparison | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | $0.00029 |
| cmp-react-vue-svelte | comparison | 1.00 | 1.00 | 0.00 | — | 0.00 | $0.00029 |
| cmp-kafka-rabbitmq | comparison | 1.00 | 1.00 | 0.00 | — | 0.00 | $0.00029 |
| cmp-monolith-microservices | comparison | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | $0.00029 |
| cmp-build-buy-auth | comparison | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | $0.00028 |
| cmp-pinecone-pgvector | comparison | 1.00 | 1.00 | 0.00 | — | 0.00 | $0.00029 |
| cmp-k8s-ecs | comparison | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | $0.00029 |
| cmp-redis-memcached | comparison | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | $0.00028 |
| cmp-graphql-rest | **research** (want comparison) | 0.00 | 1.00 | 0.00 | — | 0.00 | $0.00026 |
| cmp-claude-model-tier | comparison | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | $0.00029 |
| res-vector-dbs | research | 1.00 | 1.00 | — | — | 0.00 | $0.00026 |
| res-observability | research | 1.00 | 1.00 | — | — | 0.00 | $0.00026 |
| res-edge-computing | research | 1.00 | 1.00 | — | — | 0.00 | $0.00026 |
| res-rag-eval | research | 1.00 | 1.00 | — | — | 0.00 | $0.00026 |
| res-prompt-injection | research | 1.00 | 1.00 | — | — | 0.00 | $0.00026 |
| res-sqlite-prod | research | 1.00 | 1.00 | — | — | 0.00 | $0.00026 |
| res-feature-flags | research | 1.00 | 1.00 | — | — | 0.00 | $0.00026 |
| res-llm-caching | research | 1.00 | 1.00 | — | — | 0.50 | $0.00026 |
| res-zero-trust | **brief** (want research) | 0.00 | 0.00 | — | — | 0.00 | $0.00008 |
| res-wasm | research | 1.00 | 1.00 | — | — | 0.00 | $0.00026 |
| brf-caching-findings | brief | 1.00 | 1.00 | — | — | 0.00 | $0.00021 |
| brf-vendor-memo | brief | 1.00 | 1.00 | — | — | 0.00 | $0.00021 |
| brf-slo-summary | brief | 1.00 | 1.00 | — | — | 0.00 | $0.00021 |
| brf-hiring-plan | brief | 1.00 | 1.00 | — | — | 0.00 | $0.00021 |
| brf-incident | brief | 1.00 | 1.00 | — | — | 0.00 | $0.00021 |
| brf-security-audit | brief | 1.00 | 1.00 | — | — | 0.00 | $0.00021 |
| brf-pricing-test | brief | 1.00 | 1.00 | — | — | 0.00 | $0.00021 |
| brf-migration-status | brief | 1.00 | 1.00 | — | — | 0.00 | $0.00021 |

## Errors

- `res-zero-trust`: MissingBriefContextError: Brief requests require provided context.
