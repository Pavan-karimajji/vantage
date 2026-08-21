// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   IMP-0097/0098: the closed six-verb vocabulary and the four
///   arithmetic verbs' bare-number math. Ported from
///   `contracts/override.py::OverrideVerb`/`Override.apply`/
///   `parse_override_verb`, plus `contracts/fault.py::FaultVerb`/
///   `parse_fault_verb`.
/// @author Pavan Karimajji

#include "simcore/mutate.hpp"

namespace simcore::mutate {

namespace {

Error MakeError(Kind kind, std::string expected, std::string found, std::string where, std::string hint = "") {
  return Error{kind, std::move(expected), std::move(found), std::move(where), std::move(hint)};
}

}  // namespace

std::string ToString(Verb verb) {
  switch (verb) {
    case Verb::Const:
      return "const";
    case Verb::Hold:
      return "hold";
    case Verb::Offset:
      return "offset";
    case Verb::Scale:
      return "scale";
    case Verb::Select:
      return "select";
    case Verb::Drop:
      return "drop";
  }
  return "unknown";  // unreachable for a valid Verb; never guess a real name
}

Result<Verb> ParseVerb(std::string_view raw, const std::string& where) {
  if (raw == "const") return Result<Verb>::Ok(Verb::Const);
  if (raw == "hold") return Result<Verb>::Ok(Verb::Hold);
  if (raw == "offset") return Result<Verb>::Ok(Verb::Offset);
  if (raw == "scale") return Result<Verb>::Ok(Verb::Scale);
  if (raw == "select") return Result<Verb>::Ok(Verb::Select);
  if (raw == "drop") return Result<Verb>::Ok(Verb::Drop);
  return Result<Verb>::Fail(MakeError(
      Kind::Authoring, "one of: const, hold, offset, scale, select, drop", "'" + std::string(raw) + "'", where,
      "there is no seventh verb -- no expression language, no callable (R-SIM-15)"));
}

std::string ToString(Fault fault) {
  switch (fault) {
    case Fault::Drop:
      return "drop";
    case Fault::Stale:
      return "stale";
    case Fault::Delay:
      return "delay";
    case Fault::Invalidate:
      return "invalidate";
    case Fault::Corrupt:
      return "corrupt";
  }
  return "unknown";  // unreachable for a valid Fault; never guess a real name
}

Result<Fault> ParseFault(std::string_view raw, const std::string& where) {
  if (raw == "drop") return Result<Fault>::Ok(Fault::Drop);
  if (raw == "stale") return Result<Fault>::Ok(Fault::Stale);
  if (raw == "delay") return Result<Fault>::Ok(Fault::Delay);
  if (raw == "invalidate") return Result<Fault>::Ok(Fault::Invalidate);
  if (raw == "corrupt") return Result<Fault>::Ok(Fault::Corrupt);
  return Result<Fault>::Fail(MakeError(
      Kind::Authoring, "one of: drop, stale, delay, invalidate, corrupt", "'" + std::string(raw) + "'", where,
      "the fault vocabulary is closed at five, derived from PortValue's own header fields (SS9.2)"));
}

Result<double> ApplyArithmetic(Verb verb, double current, double first, double operand) {
  switch (verb) {
    case Verb::Const:
      return Result<double>::Ok(operand);
    case Verb::Hold:
      return Result<double>::Ok(first);
    case Verb::Offset:
      return Result<double>::Ok(current + operand);
    case Verb::Scale:
      return Result<double>::Ok(current * operand);
    case Verb::Select:
    case Verb::Drop:
      return Result<double>::Fail(MakeError(
          Kind::Internal, "an arithmetic verb (const/hold/offset/scale)", ToString(verb), "mutate::ApplyArithmetic",
          "select/drop are structural -- mutate::ApplyAtAddress, not this function"));
  }
  return Result<double>::Fail(MakeError(Kind::Internal, "a recognised Verb", "unknown", "mutate::ApplyArithmetic"));
}

}  // namespace simcore::mutate
