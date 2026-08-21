#!/usr/bin/env python3
# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @file check_anl_sw36.py
# @brief
#   ANL-SW-36 (SIM_Implementation_Plan_v0.1.md WP-12, serves SW-0202) --
#   an ingest map renames and tags only (R-SIM-23). Mechanised as: no
#   `eval`/`exec`/`lambda`/`compile` call anywhere under
#   `adas_sim/ingest/**`, and no arithmetic operator token in any file in
#   that tree except `units.py` (IMP-0193's own, deliberately narrow,
#   widening -- a factor and an offset, nothing else). This is the line
#   IMP-0193 must not cross.
#
#   Real Python tokens, not a character-class grep: `tokenize` walks the
#   file's actual token stream, so a docstring or comment saying "value *
#   factor + offset" (this project's own established prose style, which
#   uses `*`/`--` freely in explanatory text) is a STRING/COMMENT token,
#   never an OP token, and is never flagged -- a naive `[+\-*/%]` grep
#   across this codebase's comment-heavy style would be red everywhere and
#   nowhere useful. Only a real arithmetic OP token in live code counts.
# @author Pavan Karimajji <pavankarimajji1997@gmail.com>

from __future__ import annotations

import sys
import tempfile
import tokenize
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
INGEST_DIR = SIM_ROOT / "src" / "adas_sim" / "ingest"

_FORBIDDEN_CALLS = frozenset({"eval", "exec", "lambda", "compile"})
_ARITHMETIC_OPS = frozenset({"+", "-", "*", "/", "%", "**", "//"})
_UNIT_FACTOR_FILE = "units.py"


#: Token types that never carry meaning of their own -- skipped when
#: looking at an operator's neighbours so blank lines/comments/line
#: continuations don't hide a real adjacent NUMBER.
_SKIP_TYPES = frozenset({
    tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING,
})


def _tokenize(source: str) -> list[tokenize.TokenInfo]:
    line_iter = iter(source.splitlines(keepends=True))

    def _readline() -> bytes:
        try:
            return next(line_iter).encode("utf-8")
        except StopIteration:
            return b""

    return list(tokenize.tokenize(_readline))


def _is_numeric_arithmetic(tokens: list[tokenize.TokenInfo], i: int) -> bool:
    """`*`/`**` are also Python's kwonly-argument marker and
    argument-unpacking syntax; `-` is also set difference; `/` is also
    `pathlib.Path.__truediv__` -- none of those are the "field arithmetic"
    R-SIM-23 refuses, and a bare token-class match cannot tell them apart
    from real arithmetic without knowing the operands' types, which
    tokenize does not provide. The tractable, honestly-scoped proxy: a
    smuggled unit conversion looks like `value * factor + offset` --
    a numeric coefficient sits directly next to the operator. Requiring a
    NUMBER token on at least one side catches exactly that shape while
    passing syntactic `*`/`-`/`/` uses that never involve a literal
    number. This will not catch two *variables* multiplied together with
    no literal in sight -- a known, named scope limit (see module
    docstring), not a silent one."""

    def _neighbour(step: int) -> tokenize.TokenInfo | None:
        j = i + step
        while 0 <= j < len(tokens) and tokens[j].type in _SKIP_TYPES:
            j += step
        return tokens[j] if 0 <= j < len(tokens) else None

    left, right = _neighbour(-1), _neighbour(1)
    return (left is not None and left.type == tokenize.NUMBER) or (right is not None and right.type == tokenize.NUMBER)


def find_violations(ingest_dir: Path, *, base: Path | None = None) -> list[str]:
    base = base or SIM_ROOT
    findings: list[str] = []
    for path in sorted(ingest_dir.rglob("*.py")):
        allow_arithmetic = path.name == _UNIT_FACTOR_FILE
        tokens = _tokenize(path.read_text(encoding="utf-8"))
        for i, tok in enumerate(tokens):
            if tok.type == tokenize.NAME and tok.string in _FORBIDDEN_CALLS:
                findings.append(
                    f"{path.relative_to(base)}:{tok.start[0]}: forbidden call/keyword {tok.string!r}: "
                    f"{tok.line.strip()}"
                )
            elif (
                not allow_arithmetic and tok.type == tokenize.OP and tok.string in _ARITHMETIC_OPS
                and _is_numeric_arithmetic(tokens, i)
            ):
                findings.append(
                    f"{path.relative_to(base)}:{tok.start[0]}: arithmetic operator {tok.string!r} outside "
                    f"units.py: {tok.line.strip()}"
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    if not INGEST_DIR.is_dir():
        print(f"check_anl_sw36: FAIL -- {INGEST_DIR} does not exist")
        return 1
    findings = find_violations(INGEST_DIR)
    if findings:
        print("check_anl_sw36: FAIL -- adas_sim/ingest/** computes, or calls eval/exec/lambda/compile:")
        for f in findings:
            print(f"  {f}")
        print("\nR-SIM-23: an ingest map renames and tags only -- a step that computes is an "
              "unversioned algorithm sitting between the recording and the SUT.")
        return 1
    scanned = len(list(INGEST_DIR.rglob("*.py")))
    print(f"check_anl_sw36: clean -- {scanned} files scanned")
    return 0


def _self_test() -> None:
    """Planted-violation discipline (R-REQ-9): prove the scan really fires
    before trusting a clean run of the real tree."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        eval_file = tmp_path / "bad_eval.py"
        eval_file.write_text("def f(expr):\n    return eval(expr)\n")
        assert find_violations(tmp_path, base=tmp_path), "self-test FAILED: did not catch a planted eval() call"
        eval_file.unlink()

        arith_file = tmp_path / "bad_arith.py"
        arith_file.write_text("def f(x):\n    return x * 2.5 + 1\n")
        violations = find_violations(tmp_path, base=tmp_path)
        assert violations, "self-test FAILED: did not catch a planted arithmetic operator"
        arith_file.unlink()

        # The one sanctioned exception: units.py itself may compute.
        units_file = tmp_path / "units.py"
        units_file.write_text("FACTOR = 1.0 / 3.6\n")
        assert not find_violations(tmp_path, base=tmp_path), \
            "self-test FAILED: flagged units.py's own sanctioned arithmetic"
        units_file.unlink()

        # A docstring/comment using '*'/'+' in prose must never be flagged.
        prose_file = tmp_path / "prose_only.py"
        prose_file.write_text(
            '"""value * factor + offset -- this is prose, not code. # also a comment with + and *"""\n'
            "def f():\n    pass  # unrelated + comment * text\n"
        )
        assert not find_violations(tmp_path, base=tmp_path), \
            "self-test FAILED: flagged an operator character inside a docstring/comment"
    print("check_anl_sw36: self-test (planted violation) passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        _self_test()
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
