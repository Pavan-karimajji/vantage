// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `encodeCycle` (`IMP-0073`): the serialized `adas.livemeas.MeasCycle` of one step, built from the
///   plain structs of `livemeas_writer.h`. Values keep the order given, so two runs of one stage keep
///   their run order (`D30`); `age_ns` and origin are copied as handed. A payload that would not leave
///   the cycle within `capacity` is marked omitted; a cycle that does not fit even with every payload
///   omitted is not encoded.
/// @author Pavan Karimajji

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "vantage/livemeas_writer.h"

namespace vantage::livemeas {

/// Where the writer put one bulk value, or that it could not.
struct BulkPlacement {
  bool placed = false;  ///< the payload is in a `MeasBulk` slot
  std::uint32_t slot = 0;
  std::uint64_t sequence = 0;
};

struct EncodedCycle {
  bool fits = false;               ///< false: nothing fits, the step is dropped
  std::string bytes;               ///< the serialized `MeasCycle`
  std::uint32_t omitted = 0;       ///< payloads marked omitted
};

/// `placements` has one entry per value (unused for a value whose `bulk` is 0).
EncodedCycle encodeCycle(const LiveMeasValue* values, std::uint32_t value_count,
                         const std::vector<BulkPlacement>& placements, const LiveMeasBadge* badges,
                         std::uint32_t badge_count, std::size_t capacity);

}  // namespace vantage::livemeas
