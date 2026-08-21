// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IMP-0116`/`IMP-0117` / `SW-0116`/`SW-0117` -- first-divergence
///   detection and the per-message informational-only flag.
///
///   `NEW`: neither `resim_runner.cpp` nor `core/resim.py` compares a
///   simulated port against its recorded twin at all; both simply overwrite
///   the channel. There is nothing to port here, only the two rules to
///   implement:
///
///   1. **The FIRST difference latches.** A later tick agreeing again does
///      not clear it and a later, different difference does not replace it
///      -- which is what makes `SW-0116`'s "identical across re-runs" a
///      property of the mechanism rather than of the data.
///   2. **The flag is per message.** `SW-0117`'s Accept is a consumer
///      reading an *arbitrary slice* of the export, so a run-level header
///      cannot satisfy it: a slice that does not contain the header would
///      read clean.
/// @author Pavan Karimajji

#include <algorithm>
#include <cstddef>

#include "simcore/runner.hpp"

namespace simcore::runner {

void DivergenceLatch::Observe(std::uint64_t tick_index, std::int64_t log_time_ns, const std::string& stage,
                              const std::string& port, const std::vector<std::uint8_t>& simulated,
                              const std::vector<std::uint8_t>& recorded) {
  if (first_.has_value()) return;  // latched: never re-triggers (rule 1 above)
  if (simulated == recorded) return;

  // The magnitude, in the one unit available without a declared per-field
  // tolerance band (`R-SIM-24`'s `tolerance.yaml`, which nothing emits
  // yet): differing bytes over the common prefix, plus the length
  // difference. A length difference alone is still a real magnitude -- a
  // simulated message one byte longer than the recorded one differs by one.
  const std::size_t common = std::min(simulated.size(), recorded.size());
  std::size_t differing = 0;
  for (std::size_t i = 0; i < common; ++i) {
    if (simulated[i] != recorded[i]) ++differing;
  }
  differing += std::max(simulated.size(), recorded.size()) - common;

  Divergence divergence;
  divergence.tick_index = tick_index;
  divergence.log_time_ns = log_time_ns;
  divergence.stage = stage;
  divergence.port = port;
  divergence.differing_bytes = differing;
  divergence.simulated_bytes = simulated.size();
  divergence.recorded_bytes = recorded.size();
  first_ = divergence;
}

bool DivergenceLatch::InformationalOnly(std::uint64_t tick_index) const {
  if (!first_.has_value()) return false;
  // Unsigned addition on two `uint64_t`s a run could never make overflow
  // (a tick index and a configured grace window), compared with `>=` so a
  // zero grace window flags the divergence tick itself.
  return tick_index >= first_->tick_index + grace_ticks_;
}

}  // namespace simcore::runner
