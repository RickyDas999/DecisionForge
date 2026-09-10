---
name: comparison
description: >-
  Compares two or more alternatives, evaluates tradeoffs across relevant
  dimensions, and produces a structured recommendation with confidence and
  limitations. Relevant for comparison, tradeoff analysis, option evaluation,
  alternatives assessment, and decision-analysis requests.
---

# Comparison skill

Apply this skill when the request is to compare options, weigh tradeoffs, or
recommend one alternative over others.

## Produce

- The options actually under consideration, each with concrete advantages and
  disadvantages.
- The important tradeoffs — the dimensions where the options genuinely diverge.
- A recommendation when one is justified; otherwise state clearly that a single
  recommendation is not warranted.
- A `confidence` value and explicit `limitations`.

## Rules

- Identify meaningful, decision-relevant options — do not invent strawmen.
- Compare on dimensions that matter for this decision, not a generic checklist.
- Avoid false equivalence: if one option is clearly better for the stated
  context, say so.
- Surface context-dependent tradeoffs (team skills, scale, timeline, budget).
- If current external evidence (benchmarks, pricing) would be needed and none was
  supplied, record that in `limitations` and lower `confidence` accordingly.
- Do not perform live research, delegate, or call another agent.

A reusable framework lives in `references/comparison-framework.md` and is loaded
only on explicit request.
