// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `PortKind::Static` (`IMP-0060`, `DD-05`): a static port has no cycle
///   structure and no hold semantics, so its age is a category error, not
///   a number. `AgeForKind` is the one place that distinction is applied --
///   `value.cpp` computes the ordinary capture/hold derivation and this
///   function decides whether that derivation even applies.
/// @author Pavan Karimajji

#include "simcore/bus.hpp"

namespace simcore::bus {

// SW-0060's Accept: "asking for its age returns not applicable, not a
// number." `Unknown<int64_t>::has_value() == false` IS "not applicable"
// here -- the same type `Header`'s own unknown fields use, so a `Static`
// port's age formats identically to any other unknown field rather than
// needing a second "N/A" convention.
Unknown<std::int64_t> AgeForKind(PortKind kind, Unknown<std::int64_t> derived) {
  if (kind == PortKind::Static) return Unknown<std::int64_t>();
  return derived;
}

}  // namespace simcore::bus
