// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   The closed error taxonomy (SI-07, DG-5): Kind, Error, Result<T>,
///   ExitCode. Ported from docs/v2/errors.yaml -- the Python half is
///   adas_sim/diagnostics/errors.py, kept in parity by
///   scripts/check_error_parity.py (the one permitted cross-language
///   duplication, SW-0121/SW-0122).
/// @author Pavan Karimajji

#pragma once

#include <string>
#include <utility>
#include <variant>

namespace simcore {

// Four kinds, no fifth (docs/v2/errors.yaml). A new kind is a design
// review, never a runtime extension point -- same discipline R-SIM-15's
// closed verb lists apply.
enum class Kind { Authoring, Environment, Contract, Internal };

// expected/found are separate fields, never one formatted string, so both
// ends of a wiring error stay machine-readable (IMP-0123, N-8).
struct Error {
  Kind kind;
  std::string expected;
  std::string found;
  std::string where;
  std::string hint;

  std::string Format() const {
    std::string msg = "expected " + expected + "; found " + found + "; where " + where;
    if (!hint.empty()) {
      msg += " -> " + hint;
    }
    return msg;
  }
};

// Error or T, never both -- a caller checks ok() before reading either
// side. A minimal hand-rolled wrapper (no third-party dependency needed
// this early -- DD-02's single-header JSON reader is WP-05's own
// addition, not a reason to pull one in now).
template <class T>
class Result {
 public:
  static Result Ok(T value) { return Result(std::move(value)); }
  static Result Fail(Error error) { return Result(std::move(error)); }

  bool ok() const { return std::holds_alternative<T>(value_); }

  const T& value() const { return std::get<T>(value_); }
  const Error& error() const { return std::get<Error>(value_); }

 private:
  explicit Result(T value) : value_(std::move(value)) {}
  explicit Result(Error error) : value_(std::move(error)) {}

  std::variant<T, Error> value_;
};

// Eight values (docs/v2/errors.yaml) -- more than the four Kinds, because
// this is a finer-grained, CLI-level concept. Coherence/Input/Timeout are
// situational codes a specific call site passes directly (WP-19/WP-20/a
// future timeout path), never derived from a raised Error's kind; the
// other four are each one Kind's published default. Published in the CLI
// reference; identical on both platforms (UT-ERR-04 diffs the emitted
// table).
enum class ExitCode {
  Ok = 0,
  Config = 2,
  Coherence = 3,
  Module = 4,
  Input = 5,
  Infra = 6,
  Timeout = 7,
  Crash = 8,
};

// Kind's published default ExitCode (docs/v2/errors.yaml's
// default_exit_code column) -- the code a caller uses when it has a Kind
// and nothing more specific to say.
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
  return ExitCode::Crash;  // unreachable for a valid Kind; never guess Ok
}

}  // namespace simcore
