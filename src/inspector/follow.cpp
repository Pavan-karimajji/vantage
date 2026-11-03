// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief `FollowCursor` (`WP-16`, `IMP-0094`): the reader's own position in the cycle ring. When the writer has
///   overwritten cycles the reader had not read, they are counted, never guessed at.
/// @author Pavan Karimajji

#include "inspector.hpp"

namespace vantage::inspector {

FollowCursor::Range FollowCursor::next(std::uint64_t writeSequence, std::uint32_t slotCount) {
  Range range;
  if (writeSequence < position_) position_ = 0;  // a new run in the same name
  range.first = position_;
  range.last = writeSequence;
  if (slotCount > 0 && writeSequence - range.first > slotCount) {
    const std::uint64_t lost = writeSequence - range.first - slotCount;
    addSkipped(lost);
    range.first += lost;
  }
  position_ = range.last;
  return range;
}

}  // namespace vantage::inspector
