---
name: research
description: >-
  Investigates a topic, gathers and synthesizes facts, explains subject matter,
  and distinguishes supplied external evidence from model knowledge. Relevant for
  research, investigation, fact gathering, topic explanation, background briefing,
  and evidence synthesis requests.
---

# Research skill

Apply this skill when the request is to investigate, explain, or summarize a
topic.

## Produce

- A focused summary framed around the user's actual question.
- Key findings as discrete, decision-relevant statements.
- Explicit limitations, especially the absence of live or primary evidence.

## Rules

- Use only the supplied context plus general model knowledge.
- If external research context is supplied, synthesize it carefully and cite it
  in `sources`.
- If no external evidence is supplied:
  - do not claim that live, web, or primary-source research was performed;
  - do not fabricate citations — leave `sources` empty;
  - note the missing evidence in `limitations`.
- Separate claims from the evidence that supports them.
- Prefer specific, verifiable statements over broad generalizations.
- Do not overstate how current the information is.
- Do not delegate, call another agent, or propose a multi-step workflow.

Deeper guidance lives in `references/research-guidelines.md` and is loaded only
on explicit request.
