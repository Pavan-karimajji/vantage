// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `Lifecycle` implementation -- new this slice (`IMP-0084`..`0086`),
///   no ported source: `sil_host::SilComponent` tracked only a
///   `handle_ == nullptr` sentinel.
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

namespace simcore::module_host {

std::string ToString(Phase phase) {
  switch (phase) {
    case Phase::Loaded:
      return "Loaded";
    case Phase::Initialized:
      return "Initialized";
    case Phase::ShutdownDone:
      return "ShutdownDone";
  }
  return "Loaded";  // unreachable for a valid Phase; never guess a live one
}

Result<bool> Lifecycle::Transition(Phase to) {
  const bool legal =
      (phase_ == Phase::Loaded && to == Phase::Initialized) ||
      (phase_ == Phase::Initialized && to == Phase::ShutdownDone) ||
      (phase_ == Phase::ShutdownDone && to == Phase::Loaded) ||       // Reset, IMP-0085
      (phase_ == Phase::ShutdownDone && to == Phase::ShutdownDone);   // a second Shutdown() is a no-op
  if (!legal) {
    return Result<bool>::Fail(Error{Kind::Internal, "a legal lifecycle edge from " + ToString(phase_),
                                     "attempted " + ToString(phase_) + " -> " + ToString(to), "Lifecycle::Transition",
                                     "Loaded->Initialized (Init), Initialized->ShutdownDone (Shutdown), "
                                     "ShutdownDone->Loaded (Reset)"});
  }
  phase_ = to;
  return Result<bool>::Ok(true);
}

}  // namespace simcore::module_host
