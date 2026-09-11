Subject: Follow-up on Full-Scope MCTS Output Review — Findings & Fix Plan

Hi [Client contact name],

Thank you for the detailed review of the first full-scope MCTS output — we've gone
through each point and traced it back to the underlying cause in the model. Summary
below, with our proposed plan for each.

| # | Your observation | Root cause | Current status / action taken | Plan of action | Priority |
|---|---|---|---|---|---|
| 1 | BBX2/BBX3 vessel capacity looks inconsistent — BBX2's 735 TEU reserved-for-slotters figure isn't reflected, and BBX3's effective capacity doesn't reconcile the same way | The model currently calculates capacity using one flat number per vessel type (rank), and doesn't yet factor in each line's individually reserved/slotted capacity from the proforma data — so BBX2 and BBX3 are both computed the same simplified way, which is why comparing them against your real per-line numbers looked inconsistent | Root cause identified and confirmed against the source data. Fix not yet implemented. | Wire each line's actual reserved-capacity figure into the capacity calculation so it reflects real, per-line numbers instead of one generic figure per vessel type | High |
| 2 | BMX rotation duration (25.77 days) isn't a multiple of 7 | This traces to the same root cause as #3 below — the underlying duration constraint is always an exact multiple of 7; the number you're seeing came from manually summing per-port timing figures that were affected by the issue in #3 | Investigated and confirmed this is not an independent issue — tracked together with #3. | Resolved once #3 is fixed (see below) | High (bundled with #3) |
| 3 | BMX wait/manoeuvring times show as 0 after JPYOK was added, though proforma shows 197 hours | When a port is added to a line, the per-port operational detail (wait/manoeuvring time) isn't currently being carried over/recalculated for the new line shape, so it defaults to zero instead of the correct figure | Root cause identified and confirmed reproducible for this exact scenario. Fix not yet implemented. | Fix the underlying data linkage so operational timing is correctly recalculated whenever a line's port sequence changes | High |
| 4 | VSA (partner) service schedules appear to be changing even though those lines should be frozen | Confirmed: topology, weekly schedule, and vessel type are correctly locked for VSA lines. Sailing speed is intentionally left flexible (locking it caused solver infeasibility against the partner's own schedule data). However, we've identified that port stay times are not yet locked the same way weekly schedule/vessel type are — that gap is the likely source of the schedule drift you're seeing | Confirmed topology/schedule/vessel-type locking is working as intended. Identified the stay-time gap as the likely cause. Fix not yet implemented. | Lock port stay times for VSA lines, consistent with how topology/schedule/vessel type are already locked | High |
| 5 | BBX is sailing at a constant 19kts, appearing to exceed the 16.5kt soft-cap speed rule | The 16.5kt soft-cap penalty does exist in the model, but we found a calibration error in how it's applied — it currently starts discouraging speed too early (13.5kt) rather than at the intended 16.5kt threshold. Separately, we haven't yet confirmed why BBX specifically still reaches the 19.0kt ceiling despite the fuel penalty; investigation ongoing | Calibration bug identified and fix designed, not yet implemented. Investigation ongoing into why BBX reaches the top of the allowed range. | (a) Fix the miscalibrated penalty so it applies at the correct 16.5kt threshold; (b) continue investigating why BBX rides the top of the allowed range | Medium |
| 6 | Ports with no cargo movement (CNCWN, MYLBU) are being added to services with no apparent benefit | The model currently doesn't check whether a candidate port addition will actually move any cargo before accepting it into a route — it only checks that the route shape itself is valid | Root cause identified. Fix requires a change inside the core route-search logic, so it's being scoped as its own piece of work. Not yet implemented. | Add a check so the model rejects a port addition if it results in zero cargo movement | Medium |
| 7 | Cargo flow routing isn't visible in the output, making it hard to fully review output quality | The underlying routing is already calculated internally — it's just not currently included in the exported output file | Confirmed the data already exists internally. Export addition not yet implemented. | Add cargo flow routing (by OD pair/path) to the exported output | Medium |
| 8 | Clarification requested on "vrank_mix" and the difference between "capacity" and "weekly_capacity_teu" | `vrank_mix` shows the mix of vessel types on a line when more than one type is used (e.g. "5:2;6:1" = 2 ships of type 5, 1 of type 6). Separately, `capacity` and `weekly_capacity_teu` were incorrectly showing identical values due to an export bug | **Complete.** `vrank_mix` clarified (no change needed). `capacity`/`weekly_capacity_teu` duplicate-column bug fixed and verified. | `vrank_mix`: no change needed, documented above for clarity. `capacity`/`weekly_capacity_teu`: **fixed** — `capacity` now correctly shows total fleet capacity for the line, distinct from the per-week figure | Done |

**Summary:** points 2 and 3 share one root cause and are being fixed together. Points 1,
4, 6, and 7 are real gaps where the underlying data/computation already substantially
exists but isn't fully wired through to the constraint or the output — these are
additive fixes, not a redesign. Point 5 has one confirmed calibration bug (fix
identified) and one open question we're still tracing. Point 8 is resolved.

We'll prioritize 1, 3/2, and 4 first given their direct impact on output correctness,
followed by 5 and 6, with 7 alongside as it's a reporting-only addition. Happy to walk
through any of these in more detail on a call if useful.

Best,
[Your name]
