// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `IdentityTracker::Observe` (`WP-02`, `IMP-0009`): per port, what
///   `measurement_counter` and `cycle_counter` say against the previous
///   sample, by `counterDistance` of both (`D17 (3)`). Replaces the counter,
///   gap and repeat logic of the retired cycle reconstructor.
/// @author Pavan Karimajji

#include "adas/counter.hpp"
#include "simcore/bus.hpp"

namespace simcore::bus {

IdentityResult IdentityTracker::Observe(const PortId& port, const SignalHeader& header) {
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
    result.measurement_distance = adas::common::counterDistance(state.measurement, measurement);
    result.cycle_distance = adas::common::counterDistance(state.cycle, cycle);
    if (result.measurement_distance < 0 && result.cycle_distance < 0) {
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
