// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The supervisor's seal (`IMP-0076`, `D18 (3)`, `D31 (4)`): the one write anybody but the
///   writer makes to a live measurement, after the worker is confirmed dead. This header
///   declares `sealAbandoned` and nothing else (`ARCH §10.1`).
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <string>

namespace vantage {

/// What `sealAbandoned` did. Closed list.
enum class SealResult {
  kSealed,                ///< outcome then status finished written, the name removed
  kNoSuchLiveMeasurement, ///< no segment of that name
  kNotLiveMeasurement,    ///< the segment is not a live measurement of this layout
  kWriterAlive,           ///< `writerPid` is alive: nothing written
  kAlreadyFinished,       ///< `status` is not running: nothing written
  kBadArgument,           ///< an outcome outside 1..4: nothing written
  kFailed                 ///< the segment could not be mapped read-write
};

/// Opens the live measurement `name`; only when `status` is running and `writerPid` is not
/// alive, writes `outcome` (1 pass, 2 fail, 3 crash, 4 timeout) and then `status` finished and
/// no other byte, once, then removes the name as `liveMeasClose` does. Never throws.
SealResult sealAbandoned(const std::string& name, std::uint32_t outcome) noexcept;

}  // namespace vantage
