# SIM Test Execution — 2026-08-31 — Board `#20` closed green

**Campaign:** close out board item `#20` entirely (author's decision,
2026-08-31: the chase camera is sufficient; driver view is not wanted). Not a
build — a scope decision recorded against an already-shipped capability.

## What changed

1. **`misc/CONSOLIDATED_REQUIREMENTS.md`, row `#20`** — re-marked 🟡→🟢. The
   row's own sentence narrowed to what it actually still covers: video feed
   publishing, beside the BEV. Driver view joins the other three items
   (lane/pedestrian markings, free space, semantic segmentation) as
   **out of scope entirely**, author's call — the other three were decided
   2026-08-30; driver view is decided today, 2026-08-31, for a different
   reason than "no recording on hand" (this session's own prior note): the
   chase camera already shipped (`WP-22`, 2026-08-30, a real frame from
   `bsd_curve_r172_passby.mcap`'s `carla/chase_camera` decodes and draws live
   in `viz_player.exe`'s "Camera" panel) and is declared **sufficient** — a
   driver-view feed is simply not wanted, not merely unverified for lack of
   a recording.
2. **"What is NOT in scope"** — new bullet: *"No driver view"*, stating the
   decision and reason explicitly, same discipline as the section's other
   three rows (no live co-simulation, no KPI framework, no expression
   language) — so a later session reading `#20`'s green row does not read
   the absence of a driver-view feed as an open gap and try to reopen it.
3. **`misc/START_HERE.md`** — new Decision `G` (chase camera sufficient,
   driver view not wanted, `#20` closes with nothing left open).
4. **§2 "Where is it?"** rewritten: **25 of 25 green or amber, none red, none
   unverified** — the old wording ("driver view... unverified") is no longer
   true and is replaced. `#25`'s same-day closure (CI descope pass, this
   session, earlier record) is named alongside `#20`'s for the same reason
   both happened today: neither was a build, both were a scope decision
   closing a row that a prior build (`WP-22` for `#20`, `ci_gate.py` for
   `#25`) had already satisfied in substance.

## Verification

No code changed; this is a board/decision-record pass. Re-confirmed by
re-reading, not re-running:
- `WP-22`'s own exit gate (`docs/v2/SIM_Test_Execution_2026-08-30_wp22_camera_feed.md`)
  already proved the chase-camera feed live and screenshotted — nothing new
  needed to support closing `#20` green.
- `grep -n "🔴" misc/CONSOLIDATED_REQUIREMENTS.md` — no matches, confirming
  "none red" as stated.
- `grep -n "unverified" misc/CONSOLIDATED_REQUIREMENTS.md` — no remaining
  matches in the board table itself (the phrase survives only in this
  record's own prose, describing the *prior* state).

## Not done, and not claimed

- No new capability was built this pass. `vantage_app.exe` still has no
  bare-replay mode (Open risk, unrelated to `#20`) and driver view's
  mechanism (the same camera-layer path `WP-22` built) still exists and would
  work if a driver-view-camera recording ever showed up — it is simply not
  being pursued, by decision, not because it is impossible.
- Board items other than `#20` (closed here) and `#25` (closed in the prior
  pass this session, `docs/v2/SIM_Test_Execution_2026-08-31_ci_descope.md`)
  untouched.
