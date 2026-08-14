# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0122 / ANL-SW-28 (docs/v2/SIM_Implementation_Plan_v0.1.md WP-03) --
SW-0121/SW-0122: the one permitted cross-language duplication (the error
taxonomy and the event vocabulary, each hand-transcribed on both the C++
and Python side from docs/v2/errors.yaml / events.yaml) is kept honest by
comparing the two transcriptions directly, never by trusting they agree.

Lightweight regex parsing, same style as check_no_duplication.py /
check_invariants.py -- no C++ parser dependency, and none of the four
files this reads is large or free-form enough to need one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
ERRORS_HPP = SIM_ROOT / "include" / "simcore" / "errors.hpp"
EVENTS_HPP = SIM_ROOT / "include" / "simcore" / "events.hpp"
EVENTS_CPP = SIM_ROOT / "src" / "simcore" / "errors" / "events.cpp"
ERRORS_PY = SIM_ROOT / "src" / "adas_sim" / "diagnostics" / "errors.py"
EVENTS_PY = SIM_ROOT / "src" / "adas_sim" / "diagnostics" / "events.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _hpp_kind_names(text: str) -> list[str]:
    match = re.search(r"enum class Kind \{([^}]*)\}", text)
    if not match:
        return []
    return [name.strip() for name in match.group(1).split(",") if name.strip()]


def _hpp_error_fields(text: str) -> list[str]:
    """`struct Error`'s own `std::string <name>;` field declarations, one
    per line, stopping at the first member function (`Format()` sits in
    the same struct, after the fields, and its own `std::string msg = ...`
    local must not be counted as a field)."""
    match = re.search(r"struct Error \{(.*?)\};", text, re.DOTALL)
    if not match:
        return []
    body = match.group(1)
    fields_only = body.split("Format()", 1)[0]
    return re.findall(r"std::string (\w+);", fields_only)


def _hpp_exit_codes(text: str) -> dict[str, int]:
    match = re.search(r"enum class ExitCode \{([^}]*)\}", text)
    if not match:
        return {}
    return {
        name.strip(): int(value)
        for name, value in re.findall(r"(\w+)\s*=\s*(\d+)", match.group(1))
    }


def _py_kind_exit_codes(text: str) -> dict[str, int]:
    """`kind = "..."` and `exit_code = N` inside every `SimError` subclass,
    matched by proximity within one `class ...(SimError):` block."""
    result: dict[str, int] = {}
    for block in re.finditer(r"class \w+\(SimError\):(.*?)(?=\nclass |\Z)", text, re.DOTALL):
        body = block.group(1)
        kind_match = re.search(r'kind\s*=\s*"(\w+)"', body)
        exit_match = re.search(r"exit_code\s*=\s*(\d+)", body)
        if kind_match and exit_match:
            result[kind_match.group(1)] = int(exit_match.group(1))
    return result


def _py_exit_codes_mapping(text: str) -> dict[str, int]:
    match = re.search(r"EXIT_CODES:\s*Mapping\[str,\s*int\]\s*=\s*\{([^}]*)\}", text, re.DOTALL)
    if not match:
        return {}
    return {
        name: int(value)
        for name, value in re.findall(r'"(\w+)":\s*(\d+)', match.group(1))
    }


def _cpp_event_strings(text: str) -> set[str]:
    """`events.cpp`'s `ToString` switch: `case Event::kFoo: return "foo";`."""
    return set(re.findall(r'return\s+"(\w+)";', text))


def _hpp_event_names(text: str) -> set[str]:
    match = re.search(r"enum class Event \{([^}]*)\}", text, re.DOTALL)
    if not match:
        return set()
    return {name.strip() for name in match.group(1).split(",") if name.strip()}


def _py_event_strings(text: str) -> set[str]:
    match = re.search(r"class Event\(StrEnum\):(.*?)(?=\nclass |\Z)", text, re.DOTALL)
    if not match:
        return set()
    return set(re.findall(r'=\s*"(\w+)"', match.group(1)))


def check_error_parity(
    errors_hpp: Path = ERRORS_HPP, errors_py: Path = ERRORS_PY,
    events_hpp: Path = EVENTS_HPP, events_cpp: Path = EVENTS_CPP, events_py: Path = EVENTS_PY,
) -> list[str]:
    findings: list[str] = []
    if not errors_hpp.is_file() or not errors_py.is_file():
        return findings

    hpp_text = _read(errors_hpp)
    py_text = _read(errors_py)

    # Kind: the four taxonomy names, PascalCase (C++) vs lowercase (Python).
    hpp_kinds = {name.lower() for name in _hpp_kind_names(hpp_text)}
    py_kind_codes = _py_kind_exit_codes(py_text)
    py_kinds = set(py_kind_codes)
    if hpp_kinds != py_kinds:
        findings.append(
            f"Kind mismatch: errors.hpp has {sorted(hpp_kinds)}, errors.py has {sorted(py_kinds)}"
        )

    # Error's four fields.
    hpp_fields = _hpp_error_fields(hpp_text)
    expected_fields = ["expected", "found", "where", "hint"]
    if hpp_fields != expected_fields:
        findings.append(f"Error struct fields: errors.hpp has {hpp_fields}, expected {expected_fields}")

    # ExitCode: name->value, case-insensitive on the name.
    hpp_exit_codes = {name.lower(): value for name, value in _hpp_exit_codes(hpp_text).items()}
    py_exit_codes = _py_exit_codes_mapping(py_text)
    if hpp_exit_codes != py_exit_codes:
        findings.append(
            f"ExitCode mismatch: errors.hpp has {sorted(hpp_exit_codes.items())}, "
            f"errors.py's EXIT_CODES has {sorted(py_exit_codes.items())}"
        )

    # Each Kind's default ExitCode must agree between the two default maps
    # (errors.hpp::DefaultExitCode's switch vs each Python subclass's own
    # exit_code) -- read from py_kind_codes directly against hpp's parsed
    # DefaultExitCode body.
    default_match = re.search(r"DefaultExitCode\(Kind kind\)[^{]*\{(.*?)\n\}", hpp_text, re.DOTALL)
    if default_match:
        hpp_defaults = {
            kind.lower(): code.lower()
            for kind, code in re.findall(
                r"case Kind::(\w+):\s*\n\s*return ExitCode::(\w+);", default_match.group(1)
            )
        }
        for kind, exit_value in py_kind_codes.items():
            hpp_default_name = hpp_defaults.get(kind)
            if hpp_default_name is None:
                findings.append(f"DefaultExitCode: errors.hpp has no case for Kind::{kind}")
                continue
            hpp_default_value = hpp_exit_codes.get(hpp_default_name)
            if hpp_default_value != exit_value:
                findings.append(
                    f"DefaultExitCode mismatch for '{kind}': errors.hpp default is "
                    f"{hpp_default_name}={hpp_default_value}, errors.py exit_code is {exit_value}"
                )

    # Events: compare the closed vocabulary by its wire-level string value
    # (the enumerator SPELLING differs by language convention on purpose --
    # kRunStart vs RUN_START -- only the "run_start" string is the contract).
    if events_hpp.is_file() and events_cpp.is_file() and events_py.is_file():
        hpp_names = _hpp_event_names(_read(events_hpp))
        cpp_strings = _cpp_event_strings(_read(events_cpp))
        py_strings = _py_event_strings(_read(events_py))
        if len(hpp_names) != len(cpp_strings):
            findings.append(
                f"Event count mismatch: events.hpp declares {len(hpp_names)} values, "
                f"events.cpp's ToString covers {len(cpp_strings)}"
            )
        if cpp_strings != py_strings:
            findings.append(
                f"Event vocabulary mismatch: events.cpp has {sorted(cpp_strings)}, "
                f"events.py has {sorted(py_strings)}"
            )

    return findings


def main(argv: list[str] | None = None) -> int:
    findings = check_error_parity()
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} parity violation(s)")
        return 1
    print("check_error_parity: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
