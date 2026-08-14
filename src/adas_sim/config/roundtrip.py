# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`round_trip` (`SW-0155`) -- read a YAML file and write it back byte-
identical: key order, comments and quoting all survive, so a launcher that
reads a file and re-saves it with no real edit produces no spurious diff for
the user's own VCS. `pyyaml`'s `SafeLoader`/`safe_dump` (used everywhere
else in this package for VALUES) discards all three; this module exists
because `config/__init__.py::load` never needs to write a file back, but a
GUI editor does, and it must not need a second, hand-rolled YAML writer to
do it.
"""

from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML

#: One instance, configured once: round-trip mode, quote style preserved,
#: and a wrap width wide enough that no line already on disk gets re-wrapped
#: -- a line-wrapped rewrite is not byte-identical (`UT-CFG-08`).
_yaml = YAML(typ="rt")
_yaml.preserve_quotes = True
_yaml.width = 1 << 20
#: Matches this repo's own YAML style (every hand-authored pipeline/scenario/
#: project file indents a block sequence two spaces under its key, dash
#: included) -- ruamel's round-trip mode preserves comments/order/quoting
#: unconditionally, but block-sequence indentation is a DUMP option, not
#: something read back from the source; left at ruamel's own default (no
#: indent under the key) it would re-indent every list on write-back.
_yaml.indent(mapping=2, sequence=4, offset=2)


def round_trip(path: Path) -> bytes:
    """Loads `path` with the round-trip loader and dumps it straight back
    out, returning the resulting bytes -- a caller compares this against
    `path.read_bytes()` to prove nothing moved."""
    data = _yaml.load(path.read_bytes())
    buf = io.BytesIO()
    _yaml.dump(data, buf)
    return buf.getvalue()
