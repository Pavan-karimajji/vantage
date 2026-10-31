// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SampleBuffer` (`WP-02`, `IMP-0006`): the last `buffer_depth` samples of
///   one port. Counters are compared only through `counterDistance`
///   (`RCT:SYS-0005`), never with `<` or `>`.
/// @author Pavan Karimajji

#include <algorithm>

#include "adas/counter.hpp"
#include "simcore/bus.hpp"

namespace simcore::bus {

SampleBuffer::SampleBuffer(std::size_t depth) : depth_(std::max<std::size_t>(depth, 1)) {}

void SampleBuffer::Push(Sample sample) {
  samples_.push_back(std::move(sample));
  while (samples_.size() > depth_) {
    samples_.pop_front();
    ++evicted_;
  }
}

CounterLookup SampleBuffer::FindByCounter(std::uint32_t counter) const {
  CounterLookup result;
  if (counter == 0) return result;  // 0 is "unknown" in the contract: nothing is wanted
  const Sample* oldest_with_counter = nullptr;
  for (auto it = samples_.rbegin(); it != samples_.rend(); ++it) {
    if (!it->sig.measurement_counter.has_value()) continue;
    oldest_with_counter = &*it;  // ends on the oldest one, scanning newest first
    if (adas::common::counterDistance(it->sig.measurement_counter.value(), counter) == 0) {
      result.sample = &*it;
      return result;
    }
  }
  // Not held. It is an eviction miss when the wanted number is older than
  // everything held and samples have been dropped from this buffer.
  if (evicted_ > 0 && oldest_with_counter != nullptr &&
      adas::common::counterDistance(counter, oldest_with_counter->sig.measurement_counter.value()) > 0) {
    result.eviction_miss = true;
    ++eviction_misses_;
  }
  return result;
}

const Sample* SampleBuffer::NewestCounterNotAfter(std::uint32_t counter) const {
  if (counter == 0) return nullptr;  // 0 is "unknown" in the contract: nothing is wanted
  for (auto it = samples_.rbegin(); it != samples_.rend(); ++it) {
    if (!it->sig.measurement_counter.has_value()) continue;
    if (adas::common::counterDistance(it->sig.measurement_counter.value(), counter) >= 0) return &*it;
  }
  return nullptr;
}

const Sample* SampleBuffer::NewestNotAfter(std::int64_t time_ns) const {
  for (auto it = samples_.rbegin(); it != samples_.rend(); ++it) {
    if (it->arrival_ns <= time_ns) return &*it;
  }
  return nullptr;
}

const Sample* SampleBuffer::NewestSourceTimeNotAfter(std::uint64_t source_timestamp_us) const {
  if (source_timestamp_us == 0) return nullptr;  // 0 is "unknown" in the contract: nothing is wanted
  for (auto it = samples_.rbegin(); it != samples_.rend(); ++it) {
    if (!it->sig.source_timestamp_us.has_value()) continue;
    if (it->sig.source_timestamp_us.value() <= source_timestamp_us) return &*it;
  }
  return nullptr;
}

const Sample* SampleBuffer::Newest() const { return samples_.empty() ? nullptr : &samples_.back(); }

}  // namespace simcore::bus
