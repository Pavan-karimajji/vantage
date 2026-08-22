// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `CycleTrace` (`IMP-0132`/`IMP-0133`, `WP-15`) -- an optional,
///   purely additive per-cycle trace. `Record` reads nothing and decides
///   nothing; it only appends what a caller already computed, which is
///   what makes `SW-0133`'s "does not alter results" true by construction
///   rather than by discipline: there is no code path here a caller's
///   result could flow through.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

namespace simcore::diagnostics {

void CycleTrace::Record(CycleTraceEntry entry) { entries_.push_back(std::move(entry)); }

std::chrono::nanoseconds CycleTrace::TotalDuration(const std::string& stage) const {
  std::chrono::nanoseconds total{0};
  for (const CycleTraceEntry& entry : entries_) {
    if (entry.stage == stage) total += entry.duration;
  }
  return total;
}

std::size_t CycleTrace::RanCount(const std::string& stage) const {
  std::size_t count = 0;
  for (const CycleTraceEntry& entry : entries_) {
    if (entry.stage == stage && entry.outcome == CycleOutcome::kRan) ++count;
  }
  return count;
}

std::size_t CycleTrace::HeldCount(const std::string& stage) const {
  std::size_t count = 0;
  for (const CycleTraceEntry& entry : entries_) {
    if (entry.stage == stage && entry.outcome == CycleOutcome::kHeld) ++count;
  }
  return count;
}

std::vector<std::pair<std::uint64_t, std::string>> CycleTrace::CoveredCells() const {
  std::vector<std::pair<std::uint64_t, std::string>> cells;
  cells.reserve(entries_.size());
  for (const CycleTraceEntry& entry : entries_) {
    cells.emplace_back(entry.tick_index, entry.stage);
  }
  return cells;
}

}  // namespace simcore::diagnostics
