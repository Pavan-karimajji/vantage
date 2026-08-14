// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `PortValue::age_ns()` (`IMP-0045`, `SW-0045`): a method, never a
///   stored field. Ports `session/tick.py::PortValue.age_s`'s own
///   derivation -- capture time when known, else the hold schedule, else a
///   genuine known zero -- widened to integer nanoseconds (`SW-0046`) and
///   routed through `AgeForKind` (`static_data.cpp`) so a `Static` port's
///   answer is "not applicable" rather than a number.
/// @author Pavan Karimajji

#include "simcore/bus.hpp"

namespace simcore::bus {

Unknown<std::int64_t> PortValue::age_ns() const {
  Unknown<std::int64_t> derived;
  if (header.t_capture_ns.has_value()) {
    derived = header.t_sim_ns - header.t_capture_ns.value();
  } else if (hold_ns.has_value()) {
    derived = hold_ns.value();
  } else {
    derived = std::int64_t{0};  // updated this tick -- no schedule to hold against
  }
  return AgeForKind(kind, derived);
}

}  // namespace simcore::bus
