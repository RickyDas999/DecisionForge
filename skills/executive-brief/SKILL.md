---
name: executive-brief
description: >-
  Transforms user-supplied material into a concise, structured executive brief,
  decision memo, or leadership summary. Relevant for executive briefs, decision
  memos, leadership summaries, and concise professional synthesis of existing
  context.
---

# Executive brief skill

Apply this skill when the user has already supplied the source material and wants
it turned into a polished, leadership-facing brief.

## Produce

- A short, specific title.
- An executive summary that states the situation and the decision at hand.
- Key points: the few facts a leader needs, drawn from the supplied material.
- A recommendation only when the supplied material supports one.
- Action items that follow from the material.

## Rules

- Use only the information in the supplied context.
- Preserve the meaning of the source; do not soften or overstate it.
- Emphasize decision-relevant facts; drop incidental detail.
- Do not introduce facts, figures, or claims that are not in the source.
- Do not perform research, delegate, or call another agent.
- Keep it concise and readable for a non-technical executive audience.

The preferred structure is described in `references/brief-template.md`; a
deterministic structural check is available at `scripts/validate_brief.py`. Both
are loaded only on explicit request.
