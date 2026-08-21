// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   IMP-0108: `[from_ns, to_ns)` per mutation/fault, `null` meaning open
///   on that side -- shared by `Mutator` (`SpecMutation::window_ns_start`/
///   `window_ns_end`) and `FaultSpec`, one window rule rather than two.
/// @author Pavan Karimajji

#include "simcore/mutate.hpp"

namespace simcore::mutate {

bool InWindow(std::optional<std::int64_t> start_ns, std::optional<std::int64_t> end_ns, std::int64_t t_sim_ns) {
  if (start_ns.has_value() && t_sim_ns < *start_ns) return false;
  if (end_ns.has_value() && t_sim_ns >= *end_ns) return false;
  return true;
}

}  // namespace simcore::mutate
