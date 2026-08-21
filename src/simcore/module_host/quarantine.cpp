// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `Quarantine` implementation -- new this slice (`IMP-0091`), no
///   ported source. Operationalises `R-SIM-19`'s per-stage `mode:
///   isolated` bisection primitive for `Bench`'s in-process case.
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

namespace simcore::module_host {

void Quarantine::Trip(QuarantineReason reason, std::string detail) {
  reason_ = reason;
  detail_ = std::move(detail);
}

void Quarantine::Clear() {
  reason_ = QuarantineReason::kNone;
  detail_.clear();
}

}  // namespace simcore::module_host
