# Plan of Action — Anjali, 2026-08-05

## Why this exists

After the client feedback on the first full-scope MCTS output (see
[client_feedback_2026-08-04.md](client_feedback_2026-08-04.md)), I noticed I'd
been relying on Claude to make sense of the codebase rather than building my
own understanding of it. That's how issues slip through unnoticed. This is a
plan to fix that — not by working alone, but by changing *how* Claude and I
work through problems together.

## The plan

1. **Explain-back, not explain-to.** For each fix we take on, Claude points
   me at the relevant function/file first. I read it and say what I think it
   does and where I'd expect it to break, *before* Claude confirms or
   corrects. The reasoning has to happen in my head first.

2. **Use the client feedback list as a training set.** We have 8 concrete
   claims from the client. Rather than Claude telling me which are real bugs,
   I trace through the code myself for a few of them and form my own verdict
   — real bug / stale run / intentional design — then we compare notes.

3. **Keep a running "why" log.** Every time we fix something, I write one
   sentence in my own words on *why* it was broken (not what changed). That's
   the habit that builds the ability to catch the next one myself.

## First application

Starting with the BBX2/BBX3 capacity inconsistency from the client feedback
(issue 1) as the first "explain-back" exercise, since it's concrete and
already flagged as a likely real bug.
