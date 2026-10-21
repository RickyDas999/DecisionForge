# Eval report: adaptive-calibration-demo

36 cases · 1 errors · 79 LLM calls · charged $0.00000 · $0.00042/case if live · p50 latency 1 ms

| metric | score | n | Δ vs decision-engine-demo |
|---|---|---|---|
| route_accuracy | 0.94 | 36 | +0.01 |
| contract_pass | 0.97 | 36 | +0.01 |
| option_recall | 0.81 | 18 | -0.03 |
| recommendation_match | 0.38 | 13 | -0.33 |
| rubric_coverage | 0.13 | 36 | +0.01 |
| decision_completeness | 1.00 | 17 | = |

## Calibration

13 clear-cut comparisons · Brier 0.54 · ECE 0.59

| confidence | n | mean confidence | accuracy |
|---|---|---|---|
| 0.6-0.8 | 2 | 0.71 | 1.00 |
| 0.8-1.0 | 11 | 0.92 | 0.27 |

## Cases

| case | route | route_accuracy | contract_pass | option_recall | recommendation_match | rubric_coverage | decision_completeness | cost if live |
|---|---|---|---|---|---|---|---|---|
| cmp-postgres-mongo | comparison | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 1.00 | $0.00045 |
| cmp-aws-gcp | comparison | 1.00 | 1.00 | 1.00 | — | 0.50 | 1.00 | $0.00077 |
| cmp-fastapi-flask | comparison | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | $0.00043 |
| cmp-react-vue-svelte | comparison | 1.00 | 1.00 | 1.00 | — | 0.50 | 1.00 | $0.00095 |
| cmp-kafka-rabbitmq | comparison | 1.00 | 1.00 | 1.00 | — | 0.00 | 1.00 | $0.00080 |
| cmp-monolith-microservices | comparison | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 1.00 | $0.00084 |
| cmp-build-buy-auth | comparison | 1.00 | 1.00 | 0.50 | 1.00 | 0.50 | 1.00 | $0.00044 |
| cmp-pinecone-pgvector | comparison | 1.00 | 1.00 | 1.00 | — | 0.67 | 1.00 | $0.00045 |
| cmp-k8s-ecs | comparison | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | $0.00082 |
| cmp-redis-memcached | comparison | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | $0.00079 |
| cmp-graphql-rest | **research** (want comparison) | 0.00 | 1.00 | 0.00 | — | 0.00 | — | $0.00026 |
| cmp-claude-model-tier | comparison | 1.00 | 1.00 | 0.50 | 0.00 | 0.33 | 1.00 | $0.00084 |
| cmp-sqlite-desktop | comparison | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 1.00 | $0.00044 |
| cmp-static-site | comparison | 1.00 | 1.00 | 0.00 | 0.00 | 0.50 | 1.00 | $0.00046 |
| cmp-sqs-kafka-small | comparison | 1.00 | 1.00 | 1.00 | 0.00 | 0.50 | 1.00 | $0.00046 |
| cmp-python-c-script | comparison | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 1.00 | $0.00043 |
| cmp-bcrypt-sha256 | comparison | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 1.00 | $0.00081 |
| cmp-sso-build-google | comparison | 1.00 | 1.00 | 0.50 | 0.00 | 0.00 | 1.00 | $0.00045 |
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
