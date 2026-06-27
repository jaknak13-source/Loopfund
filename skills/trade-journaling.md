# Skill: Trade Journaling

How to record every decision so the fund LEARNS instead of repeating mistakes. Log the
reasoning at decision time, then grade it against reality. The journal turns outcomes
into edge; an unrecorded decision teaches nothing.

1. Log at DECISION time, before the outcome is known (no hindsight editing). For each
   decision — including NO_ACTION — record: date, name, direction, size, entry/stop,
   thesis in one line, the catalyst, the confidence, and the citations
   (evidence-verification). Capture the EUR figures (`fx_rate`) so review is base-currency.
2. Write the EXPECTED OUTCOME and FALSIFIER explicitly: what you expect to happen, by
   when, and the specific fact/price that would prove you wrong. This is the yardstick
   you'll grade against — vague expectations can't be scored.
3. Snapshot the inputs you acted on: `price`/`history` levels, `estimate_fair_value`
   output, key `fundamentals`, the macro backdrop (`macro_snapshot`, `fred_series`).
   Future-you needs to see what you actually knew, not reconstruct it.
4. REVIEW vs actual on a cadence and at every exit: did the thesis play out, did the
   catalyst fire, did the falsifier trigger? Re-pull `price`/`history` and compare to the
   expected outcome. Score the DECISION quality separately from the P&L — a good process
   can lose money and a bad one can get lucky; reward process.
5. Tag the lesson: was the error in thesis, sizing, timing, an ignored risk, or just
   variance? Honest attribution (operating norms: truth > optimism) — don't relabel a
   process failure as bad luck.
6. Feed lessons back: surface recurring tags with `random_memory` / `list_skills`,
   read the relevant skill with `get_skill`, and apply the fix to the next decision.
7. When a pattern PROVES OUT across multiple independent journal entries (not one lucky
   trade), distill it and call `propose_skill` so it becomes durable fund knowledge.
   Require corroboration: a repeatable, evidence-backed pattern — not a single win.

PITFALLS:
- Outcome bias: judging a decision by its P&L. A correct process that lost to variance
  is a KEEP; a sloppy process that won is still a fix-it. Grade the decision, not the dice.
- Hindsight rewriting: editing the thesis after you know the result erases the lesson.
  The decision-time entry is immutable.
- Only journaling trades: NO_ACTION and passes are decisions too — log the ones you
  skipped and why, or you'll never learn what you correctly avoided.
- Proposing a skill off one win. `propose_skill` needs a pattern that repeated with
  evidence; promoting noise pollutes the skill base.
