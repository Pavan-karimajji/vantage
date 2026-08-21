// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IMP-0120` / `SW-0120` -- a time-sliced run: seek to the start, stop
///   at the end, cost the slice rather than the file.
///
///   The seek goes through the EXISTING `io::Reader::Seek` primitive, never
///   a re-implemented scan. That matters twice: today the `.mcap` codec's
///   `Seek` resets its message view to a start time (`mcap.cpp::ResetView`,
///   which is a real seek, not a filtered read); and `IMP-0030` (`WP-17`,
///   `index.cpp::OffsetAtOrAfter`) upgrades that same primitive to an
///   offset jump, which this file inherits with no change because it calls
///   the interface.
///
///   **Named gap, `WP-13`'s own** (`ANL-SW-26`, `UT-RUN-08`'s second half):
///   the COST claim -- "wall time and bytes read scale with the slice" --
///   asserts against the byte counter `IMP-0135` defines (`WP-15`,
///   `cost.cpp`), which does not exist yet. What is testable today is the
///   behavioural half: a sliced run executes exactly the cycles inside the
///   slice and stops at its end. The byte assertion is added to that same
///   test when the counter lands; nothing here changes.
/// @author Pavan Karimajji

#include "simcore/runner.hpp"

namespace simcore::runner {

bool Slice::PastEnd(std::int64_t log_time_ns) const {
  return end_log_time_ns.has_value() && log_time_ns >= *end_log_time_ns;
}

bool Slice::Contains(std::int64_t log_time_ns) const {
  if (start_log_time_ns.has_value() && log_time_ns < *start_log_time_ns) return false;
  return !PastEnd(log_time_ns);
}

void SeekToSliceStart(io::Reader& reader, const Slice& slice) {
  if (!slice.start_log_time_ns.has_value()) return;
  reader.Seek(*slice.start_log_time_ns);
}

}  // namespace simcore::runner
