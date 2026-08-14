// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `Origin`/`PortKind` naming (`IMP-0048`). `Header`/`Unknown<T>`
///   themselves are template/aggregate types defined entirely in
///   `bus.hpp` -- there is no non-template code for them to hold.
/// @author Pavan Karimajji

#include "simcore/bus.hpp"

namespace simcore::bus {

std::string ToString(Origin origin) {
  switch (origin) {
    case Origin::Measured:
      return "measured";
    case Origin::Truth:
      return "truth";
    case Origin::Mocked:
      return "mocked";
    case Origin::Simulated:
      return "simulated";
    case Origin::Overridden:
      return "overridden";
    case Origin::Unknown:
      return "unknown";
  }
  return "unknown";  // unreachable for a valid Origin; never guess a real tag
}

std::string ToString(PortKind kind) {
  switch (kind) {
    case PortKind::Data:
      return "data";
    case PortKind::Control:
      return "control";
    case PortKind::Static:
      return "static";
  }
  return "data";  // unreachable for a valid PortKind
}

}  // namespace simcore::bus
