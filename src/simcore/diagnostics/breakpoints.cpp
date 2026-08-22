// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `BreakCondition` evaluators (`IMP-0138`, `WP-15`) -- four halt
///   kinds, a closed comparator set (`R-SIM-15`'s spirit: `eq`/`ne`/`lt`/
///   `gt`/`le`/`ge` against a literal, never an expression string). Each
///   `Check*` is a stateless pure predicate; a caller (a future Bench-side
///   step loop, or a test standing in for one) supplies the fact at the
///   point in its own loop where that fact becomes known.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

namespace simcore::diagnostics {

bool CompareLiteral(Comparator comparator, double lhs, double rhs) noexcept {
  switch (comparator) {
    case Comparator::kEq:
      return lhs == rhs;
    case Comparator::kNe:
      return lhs != rhs;
    case Comparator::kLt:
      return lhs < rhs;
    case Comparator::kGt:
      return lhs > rhs;
    case Comparator::kLe:
      return lhs <= rhs;
    case Comparator::kGe:
      return lhs >= rhs;
  }
  return false;  // unreachable for a valid Comparator; never guess true
}

bool CheckCycle(const BreakCondition& condition, std::uint64_t tick_index) noexcept {
  return condition.at_cycle.has_value() && *condition.at_cycle == tick_index;
}

bool CheckTime(const BreakCondition& condition, std::int64_t log_time_ns) noexcept {
  return condition.at_time_ns.has_value() && *condition.at_time_ns == log_time_ns;
}

bool CheckModuleEntry(const BreakCondition& condition, const std::string& stage_about_to_run) noexcept {
  return condition.on_module_entry.has_value() && *condition.on_module_entry == stage_about_to_run;
}

bool CheckPortLength(const BreakCondition& condition, const std::string& qualified_port,
                     std::size_t byte_length) noexcept {
  if (!condition.on_port.has_value()) return false;
  const BreakCondition::PortCheck& check = *condition.on_port;
  if (check.qualified_port != qualified_port) return false;
  return CompareLiteral(check.comparator, static_cast<double>(byte_length), check.literal);
}

}  // namespace simcore::diagnostics
