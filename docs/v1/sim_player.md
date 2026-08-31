# Vantage — the player application (v1, superseded)

**Retired 2026-08-31 (Step 7 document-set shrink).** Full text:
`git show 1e2bb5b:docs/v1/sim_player.md` (430 lines).

**§1 (Names — the naming rationale a live C++ header,
`modules/viz/cpp/viz/player/workspace_mode.hpp`, quotes directly) and §10
(What shipped — reconciled 2026-08-06) are extracted, unabridged, to
[`FROZEN_DESIGN_ORIGINS.md`](FROZEN_DESIGN_ORIGINS.md)** — read them there.
Note that §10 documents the Python `app/` implementation of Vantage as it
stood on 2026-08-06; that implementation was itself deleted 2026-08-29
(`7d4c626`, "delete the Python scene/render/player implementation",
Decision B) — the player is now `viz`'s C++ implementation, and §10 is kept
purely as historical record, not as a description of anything that exists
today.

Everything else this document held (the lean-principle rule, the window
layout in detail, the Bench and Campaign workspaces in detail, the first-run
walkthrough, the full feature/traceability lists) had no live external
reader and is evidence only, full text at the commit above.

No `R-REQ-2` trace exposure (checked, `misc/STEP_7_SHRINK_PLAN.md` §3).
