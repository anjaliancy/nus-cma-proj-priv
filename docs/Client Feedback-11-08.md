# Client Feedback — 11/08

Raw feedback from CMA CGM after reviewing the first full-scope MCTS output,
kept as a standalone reference in the client's own wording.

## 1. Vessel rank/capacity

- BBX2 was downgraded to VRank 2 (742 TEUs nominal). Proforma info shared with
  them clearly states that 735 TEUs of capacity is reserved for external
  slotters.
- BBX3 was downgraded to VRank 2 (742 TEUs nominal). But somehow they
  calculated that the effective capacity owned by CNC is 2316 TEUs, which is
  not just higher than nominal capacity, it's not consistent with the
  capacity calculations used for BBX2.

## 2. Rotation duration looks incorrect

After adding JPYOK to BMX, adding up all "seatime", "opstime", "waittime" and
"mantime" shows that BMX has a total duration of 618.38 hours, or 25.77 days.
This is clearly not an integer multiple of 7; claiming "3 vessels, 21 days"
looks incorrect.

## 3. Wait Times and Manoeuvring Times are treated as a variable instead of a constant parameter

All waiting times and manoeuvring times for BMX were set to 0. Proforma
clearly states that these times add up to 197 hours.

## 4. VSA services are frozen, yet their service schedules (speeds, stay times, sailing times) are being modified

## 5. Speed limits are not respected

BBX has a constant sailing speed of 19kts.

## 6. Ports with no demand are added to services

- CNCWN added to CP2. Filling factor before and after CNCWN is the same, and
  ops time at CNCWN = 0, meaning no movements are made. What is the point of
  it?
- Same observation and conclusion for the port MYLBU added to YCX.

## 7. Cargo flow routing is not reported

Need this in order to properly review the quality of the output — especially
how many of the cargo flows.

## 8. Need clarity on columns

- What is "vrank_mix"?
- What is the difference between "capacity" and "weekly_capacity_teu"?
