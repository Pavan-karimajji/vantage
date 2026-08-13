# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0371 / ANL-SW-65 (docs/v2/SIM_Implementation_Plan_v0.1.md WP-01) --
the CI entry point for `docs/v2/py/trace_check.py`, plus `R-REQ-9`'s
mechanisation: every `UT-*`/`IT-*`/`ANL-SW-*`/`INSP-SW-*` identifier a
software requirement's `Verify` clause cites must appear **verbatim**
inside the test file that implements it, so the link is discoverable by
grep rather than by one sentence in a plan. `docs/v2/py/trace_check.py`
already proves the *documents* agree with each other; this proves the
*code* agrees with the documents.

`IMP-0417`'s second table -- each cited artifact kind's `detected_by:`
list from `conf/known_limits.yaml` -- is deferred: that file's real
content (which limit is governed by which check, one entry per cited
kind) is `WP-31`'s `USE_CONSTRAINTS.md` generation input, and no kind is
cited yet (`conf/artifact_kinds.yaml` is new at this same `WP-01`, all
`cited: false`). Populating `detected_by:` now would invent content
nobody has decided. **Closed by:** the first `WP` that cites a kind
`true` in `conf/artifact_kinds.yaml`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
TRACE_CHECK = SIM_ROOT / "docs" / "v2" / "py" / "trace_check.py"
TESTS_ROOT = SIM_ROOT / "tests"

_PY_DIR = SIM_ROOT / "docs" / "v2" / "py"
if str(_PY_DIR) not in sys.path:
    sys.path.insert(0, str(_PY_DIR))


def run_trace_check() -> int:
    """The CI entry point: shell out so this script's own exit code is the
    one CI reports, exactly as `python docs/v2/py/trace_check.py` would."""
    result = subprocess.run([sys.executable, str(TRACE_CHECK)])
    return result.returncode


def check_test_ids_appear_in_tests(tests_root: Path = TESTS_ROOT) -> tuple[list[str], int]:
    """R-REQ-9: every test id a software requirement's `Verify` cites
    appears verbatim inside some file under `tests_root`. Returns
    (findings, ids checked)."""
    import trace_check as tc  # noqa: PLC0415 -- deferred: only needed here

    sw_text = tc._read(tc.SWREQ)
    sw = tc.parse_sw(sw_text)
    cited: set[str] = set()
    for r in sw.values():
        cited |= r.tests

    if not tests_root.is_dir():
        return [f"tests root does not exist: {tests_root}"], 0

    haystack = ""
    for path in sorted(tests_root.rglob("*.py")):
        haystack += path.read_text(encoding="utf-8") + "\n"

    findings: list[str] = []
    for tid in sorted(cited):
        if not re.search(re.escape(tid), haystack):
            findings.append(f"{tid}: cited by a requirement's Verify clause but appears in no test file under {tests_root}")
    return findings, len(cited)


def main(argv: list[str] | None = None) -> int:
    doc_rc = run_trace_check()

    findings, checked = check_test_ids_appear_in_tests()
    print()
    for f in findings:
        print(f)
    print(f"{checked} cited test id(s) checked against {TESTS_ROOT}")
    if findings:
        print(f"{len(findings)} R-REQ-9 violation(s) -- a cited test id has no matching test yet")

    # A test id not yet implemented is expected during an in-progress WP
    # and is not itself a CI failure -- only the document-level trace
    # (`doc_rc`) gates the build. The grep half is informational until a
    # work package's Exit gate names it explicitly.
    return doc_rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
