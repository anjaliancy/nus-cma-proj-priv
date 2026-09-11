---
name: collab-short-explanations
description: User repeatedly asks for shorter bug/fix explanations even after simplifying once
metadata:
  type: feedback
---

Default to short, plain explanations for bug/fix summaries — a few lines, not tables or
multi-section writeups. When asked "give a short/small explanation," compress further
than the first simplification pass, not just trim slightly.

**Why:** during the 2026-08-11 client-feedback session, the user asked twice in a row
for shorter versions of the same explanation (capacity/weekly_capacity_teu bug, then
BBX2/BBX3 capacity mechanism) — the first "simplified" pass was still too dense both
times.

**How to apply:** for any "what did you fix / why" explanation, lead with a 2-4 line
version (bug → fix → one-line why-it-matters) by default. Only expand to
tables/sections if the user asks for more detail. See [[collab_pacing]] and
[[collab_explain_back]] for the related explain-back working style — this is the
inverse case (delivering findings/fixes, not teaching concepts).
