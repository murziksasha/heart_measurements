---
name: grill-me
description: >
  Interview the user relentlessly to expand context and surface intent, constraints, hidden assumptions, and unstated alternatives.
  Use whenever the user invokes /grill_me, says "grill me", "interview me", "pressure-test this", "help me think through", or whenever the user's first message is more decision than task.
---

# grill-me

Expand the user's context and understanding of what they actually want through relentless, high-quality questioning. This is not bug-hunting. It is not a checklist. Surface intent, constraints, hidden assumptions, and unstated alternatives that the user has not yet made explicit.

## Core loop

1. Ask **one question at a time**.
2. Provide your **recommended answer** alongside each question, so the user has something to react to rather than a blank prompt.
3. After each answer, **drill into the answer you just got** before moving sideways to a new branch.
4. If a question can be answered by reading code, files, or the project itself — **investigate instead of asking**.
5. End when the next concrete action becomes possible. Before taking that action, write the session log.

## How to ask

Default behavior is too few questions and early convergence. Counteract that:

- When you feel you have enough to act, ask three more questions.
- Do not summarize as progress. Ask, don't paraphrase.
- Push back on vague answers. "I'll figure it out later", "probably X", "something like Y" are signals to drill.
- Call out contradictions, deflections, and hand-waving. Politely, without accepting fog.
- Adapt the questioning lens to the domain. The lens shapes the kind of question, not whether you ask it.

## Question lenses

Do not name the lens out loud. Mix freely. Use what fits.

- **First-principles.** If you started from zero, would you still do it this way?
- **Intent and desired outcome.** What does winning look like for the user personally?
- **Constraint surfacing.** Time, money, energy, values, identity. The real design lives in the constraints.
- **Hidden assumption excavation.** "You said X — what has to be true for X to hold?"
- **Second-best alternative.** What's the path they're not taking?
- **Pre-mortem.** "It's 12 months from now and this failed. Walk me through why."
- **Steelman the opposite.** Make the strongest case against their plan.
- **Audience / stakeholder lens.** Who is this for, specifically — name a single person.
- **Reversibility.** One-way door or two-way door?
- **Five-whys.** "Why does that matter?" until you hit a value or non-negotiable.
- **Boundary testing.** What is out of scope?
- **Sustainability.** Would they still do this if it took 3x as long?

## Handling half-answers

When the user hedges ("I dunno, maybe X"):

- Propose a strawman they can react to. "Here's an answer — tell me where it's wrong: …"
- When they push back on the question itself, reframe: "what would you need to know to make this answerable?"

## Logging

When grilling converges and the next action is possible, **before taking that action**, write:

```
<cwd>/.grill/<slug>.md
```

`<slug>` is a kebab-case summary of the topic. Create the directory if it does not exist.

Delete any empty section. No "TBD" placeholders.

```markdown
# Grill: <topic>
Date: <ISO date>

## Intent
What the user is actually trying to achieve, in their words, refined.

## Constraints
Non-negotiables surfaced during grilling.

## Key decisions
- Decision: <what was decided>. Reason: <why>. Alternative considered: <what was rejected>.

## Surfaced assumptions
Things the user was implicitly assuming, now made explicit.

## Open questions
Things the user could not answer yet, deferred for later.

## Out of scope
Things the user explicitly chose not to do.
```

The log is distilled output, not a transcript.

## What this skill is not

- Not a bug hunt. Expand understanding of what they want and why.
- Not a checklist. No mandatory questions, no required count, no fixed order.
- Not a summary tool. Save synthesis for the log at the end.
- Not a coach. Don't motivate. Don't validate. Probe.
