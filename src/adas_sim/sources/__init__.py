# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The synthetic scripted source and the recorder that drives it
(`R-SIM-14`, `sim_api_reference.md` §8). The live CARLA world-model client
is removed (`DD-12`); `SyntheticSource` stays production code pending
`WP-09`/`WP-13`'s runner rewrite, which is where "no live source at all"
(recordings only) actually lands."""

from __future__ import annotations
