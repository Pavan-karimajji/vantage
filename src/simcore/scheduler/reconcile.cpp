// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `Scheduler::ReconcileModuleFlag` (`SW-0066`, `WP-09`) -- ported
///   from `contracts/pipeline.py`'s `ProvenanceWarning` (naming stage,
///   port, declared period, predicted due-ness and reported flag), scoped
///   here to the stage-level disagreement this class can see without a
///   port set (`SW-0414`'s own per-port measured-rate reconciliation is a
///   named follow-on, not this file).
/// @author Pavan Karimajji

#include "simcore/scheduler.hpp"

namespace simcore::scheduler {

std::optional<ScheduleFinding> Scheduler::ReconcileModuleFlag(
    const std::string& stage_name, bool reported_updated) const {
  const bool predicted = IsDue(stage_name);
  if (predicted == reported_updated) {
    return std::nullopt;  // agreement -- never a finding for the common case
  }
  return ScheduleFinding{stage_name, predicted, reported_updated};
}

}  // namespace simcore::scheduler
