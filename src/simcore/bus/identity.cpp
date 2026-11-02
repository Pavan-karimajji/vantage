// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `IdentityTracker::Observe` (`WP-02`, `IMP-0009`): per port, what
///   `measurement_counter` and `cycle_counter` say against the previous
///   sample, by `MeasurementCounterDistance` and `counterDistance` (`D17 (3)`,
///   `D24`). Replaces the counter,
///   gap and repeat logic of the retired cycle reconstructor.
/// @author Pavan Karimajji

#include "adas/counter.hpp"
#include "simcore/bus.hpp"

namespace simcore::bus {

std::int32_t MeasurementCounterDistance(std::uint32_t from, std::uint32_t to) {
  const std::int32_t distance = adas::common::counterDistance(from, to);
  // Where the step crosses the missing 0 (`D24`), the distance counted it.
  const std::int32_t to_zero = adas::common::counterDistance(from, 0);
  if (to_zero > 0 && to_zero <= distance) return distance - 1;
  if (to_zero < 0 && distance <= to_zero) return distance + 1;
  return distance;
}

bool IsUnknownMeasurementCounter(std::uint32_t counter) { return counter == 0; }

IdentityResult IdentityTracker::Observe(const PortId& port, const SignalHeader& header, bool content_differs) {
  PortState& state = state_[port];
  IdentityResult result;

  // A sample whose measurement_counter is unknown (0 on the wire, or no
  // header) is not judged: no gap, reset or broken comes from it, and the
  // earlier sample stays the one the next is compared with.
  if (!header.measurement_counter.has_value() || !header.cycle_counter.has_value()) {
    result.verdict = IdentityVerdict::kNotComparable;
    ++state.counts.unknown;
    state.last = result;
    return result;
  }
  const std::uint32_t measurement = header.measurement_counter.value();
  const std::uint32_t cycle = header.cycle_counter.value();
  ++state.counts.samples;

  if (!state.has_previous) {
    result.verdict = IdentityVerdict::kFirst;
  } else {
    result.measurement_distance = MeasurementCounterDistance(state.measurement, measurement);
    result.cycle_distance = adas::common::counterDistance(state.cycle, cycle);
    if (result.measurement_distance == 0 && content_differs) {
      // The same counter with other bytes: identity is broken whatever the
      // cycle counter does (`IMP-0050`).
      result.verdict = IdentityVerdict::kIdentityBroken;
      ++state.counts.identity_broken;
    } else if (result.measurement_distance < 0 && result.cycle_distance < 0) {
      result.verdict = IdentityVerdict::kCounterReset;
      ++state.counts.resets;
    } else if (result.measurement_distance <= 0 && result.cycle_distance > 0) {
      result.verdict = IdentityVerdict::kIdentityBroken;
      ++state.counts.identity_broken;
    } else if (result.measurement_distance > 1) {
      result.verdict = IdentityVerdict::kCounterGap;
      result.missed = static_cast<std::uint32_t>(result.measurement_distance - 1);
      ++state.counts.gaps;
    } else {
      result.verdict = IdentityVerdict::kOk;
    }
  }
  state.has_previous = true;
  state.measurement = measurement;
  state.cycle = cycle;
  state.last = result;
  return result;
}

IdentityCounts IdentityTracker::Counts(const PortId& port) const {
  const auto it = state_.find(port);
  return it == state_.end() ? IdentityCounts{} : it->second.counts;
}

IdentityResult IdentityTracker::Last(const PortId& port) const {
  const auto it = state_.find(port);
  return it == state_.end() ? IdentityResult{} : it->second.last;
}

}  // namespace simcore::bus
