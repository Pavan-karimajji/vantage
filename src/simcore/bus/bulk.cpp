// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `BulkRef` budget check (`IMP-0059`, `SW-0059`). Ports
///   `scene/types.py`'s `BulkRef` and the budget check in
///   `Layer.__post_init__` (R-SIM-2) into the bus, so a bulk array cannot
///   be inlined into a tick structure even before the player exists to
///   enforce it a second time.
/// @author Pavan Karimajji

#include "simcore/bus.hpp"

namespace simcore::bus {

Result<bool> CheckBulkBudget(const PortId& port, std::size_t actual_bytes) {
  if (actual_bytes > kBulkRefBudgetBytes) {
    return Result<bool>::Fail(Error{
        Kind::Authoring,
        "a bulk reference of at most " + std::to_string(kBulkRefBudgetBytes) + " bytes",
        std::to_string(actual_bytes) + " bytes",
        "port " + port,
        "bulk arrays are referenced (topic + log_time_ns), never inlined -- SW-0059",
    });
  }
  return Result<bool>::Ok(true);
}

}  // namespace simcore::bus
