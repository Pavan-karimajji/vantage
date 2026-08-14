// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-IO-05`..`UT-IO-07` (`SW-0025`..`SW-0027`): streaming batches never
///   materialise a whole recording, the three-axis bound fires correctly
///   (including the single-oversized-message case), and decode is deferred
///   and memoised.
///
///   **Scoping note (honest, not silent):** `SW-0025`'s Verify line also
///   names `ANL-SW-12`, a peak-resident-bytes measurement across 1x/5x/20x
///   duration -- a genuine RSS sample (`GetProcessMemoryInfo` on Windows) is
///   a separate, platform-specific analysis check the design doc tracks as
///   its own row, not a sub-case `UT-IO-05` must also implement. What is
///   tested here is the STRUCTURAL property that actually prevents
///   unbounded growth: `ReadRange` never returns more than one bounded
///   `Batch` regardless of how long the underlying stream is, at 1x/5x/20x
///   duration -- the mechanism `ANL-SW-12`'s measurement would confirm has
///   the claimed effect.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "simcore/io.hpp"

namespace simcore::io {
namespace {

// A synthetic pull source: N messages, one byte payload each, log_time_ns
// = index -- exactly what `F-LONG`'s "same content at 1x/5x/20x duration"
// means for a streaming test that does not need a real recording file.
class SyntheticStream {
 public:
  explicit SyntheticStream(int count) : remaining_(count) {}

  std::optional<RawMessage> operator()() {
    if (remaining_ <= 0) return std::nullopt;
    RawMessage msg;
    msg.topic = "synthetic";
    msg.log_time_ns = index_;
    msg.payload = {static_cast<std::uint8_t>(index_ % 256)};
    ++index_;
    --remaining_;
    return msg;
  }

 private:
  int remaining_;
  std::int64_t index_ = 0;
};

// UT-IO-05: reading to completion at 1x/5x/20x never yields a batch larger
// than the declared bound, regardless of total stream length -- the
// mechanism that keeps peak resident memory flat rather than growing with
// file length (SW-0025's Accept).
TEST(UtIo05Streaming, ReadToCompletionNeverMaterialisesMoreThanOneBoundedBatch) {
  constexpr std::size_t kBatchLimit = 10;
  for (const int duration : {100, 500, 2000}) {  // 1x, 5x, 20x
    SyntheticStream stream(duration);
    std::optional<RawMessage> lookahead;
    ReadBounds bounds;
    bounds.max_messages = kBatchLimit;

    int total_read = 0;
    while (true) {
      const Batch batch = detail::AccumulateBatch(bounds, lookahead, std::ref(stream));
      ASSERT_LE(batch.messages.size(), kBatchLimit) << "duration=" << duration;
      total_read += static_cast<int>(batch.messages.size());
      if (batch.exhausted) break;
    }
    EXPECT_EQ(total_read, duration);
  }
}

TEST(UtIo06ReadBounds, EachAxisFiresAloneAndAnOversizedMessageIsEmittedAlone) {
  // Count bound.
  {
    SyntheticStream stream(10);
    std::optional<RawMessage> lookahead;
    ReadBounds bounds;
    bounds.max_messages = 3;
    const Batch batch = detail::AccumulateBatch(bounds, lookahead, std::ref(stream));
    EXPECT_EQ(batch.messages.size(), 3u);
    EXPECT_EQ(batch.end_reason, BatchEndReason::kCount);
  }
  // Bytes bound: each message is 1 byte, so a 3-byte bound stops at 3.
  {
    SyntheticStream stream(10);
    std::optional<RawMessage> lookahead;
    ReadBounds bounds;
    bounds.max_bytes = 3;
    const Batch batch = detail::AccumulateBatch(bounds, lookahead, std::ref(stream));
    EXPECT_EQ(batch.messages.size(), 3u);
    EXPECT_EQ(batch.end_reason, BatchEndReason::kBytes);
  }
  // Span bound: log_time_ns is the message index, so a span of 3ns admits
  // indices [0..3].
  {
    SyntheticStream stream(10);
    std::optional<RawMessage> lookahead;
    ReadBounds bounds;
    bounds.max_span_ns = 3;
    const Batch batch = detail::AccumulateBatch(bounds, lookahead, std::ref(stream));
    EXPECT_EQ(batch.messages.size(), 4u);  // indices 0,1,2,3 -- span 0..3
    EXPECT_EQ(batch.end_reason, BatchEndReason::kSpan);
  }
  // IMP-0026: a single message larger than max_bytes is delivered alone,
  // never deadlocked.
  {
    auto pull = [called = false]() mutable -> std::optional<RawMessage> {
      if (called) return std::nullopt;
      called = true;
      RawMessage msg;
      msg.topic = "big";
      msg.payload.assign(100, std::uint8_t{7});
      return msg;
    };
    std::optional<RawMessage> lookahead;
    ReadBounds bounds;
    bounds.max_bytes = 10;
    const Batch batch = detail::AccumulateBatch(bounds, lookahead, pull);
    ASSERT_EQ(batch.messages.size(), 1u);
    EXPECT_EQ(batch.messages[0].payload.size(), 100u);
  }
}

TEST(UtIo07LazyDecode, DecodeIsDeferredAndMemoised) {
  ResetDecodeCount();
  LazyPayload<int> payload(std::vector<std::uint8_t>{5});

  EXPECT_EQ(DecodeCount(), 0u);
  EXPECT_FALSE(payload.decoded());

  const auto parse = [](const std::vector<std::uint8_t>& bytes) { return static_cast<int>(bytes[0]); };
  EXPECT_EQ(payload.Get(parse), 5);
  EXPECT_EQ(DecodeCount(), 1u);

  // Second access is memoised -- no second decode.
  EXPECT_EQ(payload.Get(parse), 5);
  EXPECT_EQ(DecodeCount(), 1u);
}

}  // namespace
}  // namespace simcore::io
