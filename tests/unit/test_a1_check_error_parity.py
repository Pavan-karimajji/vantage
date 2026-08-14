# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-03: IMP-0122 / ANL-SW-28 -- check_error_parity.py is tested, not
trusted (IMP-0370)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_error_parity import check_error_parity  # noqa: E402

_ERRORS_HPP = """
enum class Kind { Authoring, Environment, Contract, Internal };
struct Error {
  Kind kind;
  std::string expected;
  std::string found;
  std::string where;
  std::string hint;

  std::string Format() const {
    std::string msg = "unrelated local, must not count as a field";
    return msg;
  }
};
enum class ExitCode { Ok = 0, Config = 2, Coherence = 3, Module = 4, Input = 5, Infra = 6, Timeout = 7, Crash = 8 };
inline ExitCode DefaultExitCode(Kind kind) {
  switch (kind) {
    case Kind::Authoring:
      return ExitCode::Config;
    case Kind::Environment:
      return ExitCode::Infra;
    case Kind::Contract:
      return ExitCode::Module;
    case Kind::Internal:
      return ExitCode::Crash;
  }
}
"""

_ERRORS_PY = """
class SimError(Exception):
    kind: ClassVar[str]
    exit_code: ClassVar[int]

class AuthoringError(SimError):
    kind = "authoring"
    exit_code = 2

class EnvironmentError_(SimError):
    kind = "environment"
    exit_code = 6

class ContractError(SimError):
    kind = "contract"
    exit_code = 4

class InternalError(SimError):
    kind = "internal"
    exit_code = 8

EXIT_CODES: Mapping[str, int] = {
    "ok": 0,
    "config": 2,
    "coherence": 3,
    "module": 4,
    "input": 5,
    "infra": 6,
    "timeout": 7,
    "crash": 8,
}
"""

_EVENTS_HPP = """
enum class Event {
  kRunStart,
  kRunEnd,
};
"""

_EVENTS_CPP = """
const char* ToString(Event event) {
  switch (event) {
    case Event::kRunStart:
      return "run_start";
    case Event::kRunEnd:
      return "run_end";
  }
}
"""

_EVENTS_PY = """
class Event(StrEnum):
    RUN_START = "run_start"
    RUN_END = "run_end"
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_all(tmp_path: Path, **overrides: str) -> dict[str, Path]:
    contents = {
        "errors_hpp": _ERRORS_HPP, "errors_py": _ERRORS_PY,
        "events_hpp": _EVENTS_HPP, "events_cpp": _EVENTS_CPP, "events_py": _EVENTS_PY,
    }
    contents.update(overrides)
    paths = {name: tmp_path / f"{name}.txt" for name in contents}
    for name, text in contents.items():
        _write(paths[name], text)
    return paths


def test_check_error_parity_passes_on_the_real_files():
    assert check_error_parity() == []


def test_check_error_parity_passes_on_a_clean_fixture(tmp_path):
    paths = _write_all(tmp_path)
    assert check_error_parity(**paths) == []


def test_check_error_parity_fails_on_a_planted_exit_code_mismatch(tmp_path):
    """The check is tested, not trusted (SW-0370): a deliberately
    mismatched ExitCode value between the two sides must be caught."""
    bad_py = _ERRORS_PY.replace('"crash": 8', '"crash": 9')
    paths = _write_all(tmp_path, errors_py=bad_py)
    findings = check_error_parity(**paths)
    assert findings
    assert any("ExitCode mismatch" in f for f in findings)


def test_check_error_parity_fails_on_a_planted_kind_mismatch(tmp_path):
    bad_hpp = _ERRORS_HPP.replace(
        "enum class Kind { Authoring, Environment, Contract, Internal };",
        "enum class Kind { Authoring, Environment, Contract };",
    )
    paths = _write_all(tmp_path, errors_hpp=bad_hpp)
    findings = check_error_parity(**paths)
    assert findings
    assert any("Kind mismatch" in f for f in findings)


def test_check_error_parity_fails_on_a_planted_default_exit_code_mismatch(tmp_path):
    bad_py = _ERRORS_PY.replace('kind = "internal"\n    exit_code = 8', 'kind = "internal"\n    exit_code = 7')
    paths = _write_all(tmp_path, errors_py=bad_py)
    findings = check_error_parity(**paths)
    assert findings
    assert any("DefaultExitCode mismatch" in f for f in findings)


def test_check_error_parity_fails_on_a_planted_event_vocabulary_mismatch(tmp_path):
    bad_py = _EVENTS_PY.replace('RUN_END = "run_end"', 'RUN_END = "typo_run_end"')
    paths = _write_all(tmp_path, events_py=bad_py)
    findings = check_error_parity(**paths)
    assert findings
    assert any("Event vocabulary mismatch" in f for f in findings)
