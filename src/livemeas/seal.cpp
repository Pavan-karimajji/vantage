// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `sealAbandoned` (`IMP-0076`, `D18 (3)`, `D31 (5)`): after the worker is confirmed dead, writes
///   `outcome` and then `status` finished, and no other byte, then removes the name as
///   `liveMeasClose` does. Nothing is written when the writer lives or the status is finished.
/// @author Pavan Karimajji

#include "vantage/livemeas_seal.hpp"

#include <atomic>

#include "livemeas/livemeas_layout.hpp"
#include "livemeas/shared_region.hpp"

namespace vantage {

SealResult sealAbandoned(const std::string& name, std::uint32_t outcome) noexcept {
  namespace layout = adas::livemeas;
  try {
    if (outcome < 1 || outcome > 4) return SealResult::kBadArgument;
    std::unique_ptr<livemeas::SharedRegion> region =
        livemeas::SharedRegion::open(name, livemeas::SharedRegion::Access::kReadWrite);
    if (region == nullptr) {
      // Told apart: nothing of that name, or something there that could not be mapped read-write.
      return livemeas::SharedRegion::open(name, livemeas::SharedRegion::Access::kReadOnly) == nullptr
                 ? SealResult::kNoSuchLiveMeasurement
                 : SealResult::kFailed;
    }
    if (region->size() < sizeof(layout::MeasStatus)) return SealResult::kNotLiveMeasurement;
    auto& status = *static_cast<layout::MeasStatus*>(region->data());
    if (status.magic != layout::kMagic) return SealResult::kNotLiveMeasurement;
    if (status.status.load(std::memory_order_acquire) != 1) return SealResult::kAlreadyFinished;
    if (livemeas::SharedRegion::isProcessAlive(status.writerPid)) return SealResult::kWriterAlive;
    status.outcome.store(outcome, std::memory_order_release);
    status.status.store(3, std::memory_order_release);
    livemeas::SharedRegion::remove(name);
    livemeas::SharedRegion::remove(name + layout::kBulkSegmentSuffix);
    return SealResult::kSealed;
  } catch (...) {
    return SealResult::kFailed;
  }
}

}  // namespace vantage
