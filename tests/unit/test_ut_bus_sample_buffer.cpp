// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SampleBuffer` (`WP-02`, `IMP-0006`): at most `buffer_depth` samples, a
///   search by counter and by time, an eviction miss for a counter that was
///   held and dropped, and counters compared only through `counterDistance`
///   (planted wrap-around cases a plain `<` would get wrong). Unit tests of
///   the buffer; the system tests `SYT-RUN-06` and `SYT-SEL-01`, `-03`, `-06`
///   are built in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <cstdint>

#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

Sample MakeSample(std::uint32_t counter, std::int64_t arrival_ns) {
  Sample sample;
  sample.sig.measurement_counter = counter;
  sample.sig.present = true;
  sample.arrival_ns = arrival_ns;
  sample.value.payload = {static_cast<std::uint8_t>(counter & 0xFF)};
  return sample;
}

TEST(UtBusSampleBuffer, NeverHoldsMoreThanItsDepthAndDropsTheOldest) {
  SampleBuffer buffer(3);
  for (std::uint32_t i = 1; i <= 5; ++i) buffer.Push(MakeSample(i, i * 100));
  EXPECT_EQ(buffer.Size(), 3u);
  EXPECT_EQ(buffer.Evicted(), 2u);
  EXPECT_EQ(buffer.Samples().front().sig.measurement_counter.value(), 3u);
  EXPECT_EQ(buffer.Newest()->sig.measurement_counter.value(), 5u);
}

TEST(UtBusSampleBuffer, ADepthBelowOneHoldsOneSample) {
  SampleBuffer buffer(0);
  buffer.Push(MakeSample(1, 10));
  buffer.Push(MakeSample(2, 20));
  EXPECT_EQ(buffer.Depth(), 1u);
  EXPECT_EQ(buffer.Size(), 1u);
  EXPECT_EQ(buffer.Newest()->sig.measurement_counter.value(), 2u);
}

TEST(UtBusSampleBuffer, AnEmptyBufferAnswersNothing) {
  SampleBuffer buffer(4);
  EXPECT_EQ(buffer.Newest(), nullptr);
  EXPECT_EQ(buffer.NewestNotAfter(1000), nullptr);
  EXPECT_EQ(buffer.NewestCounterNotAfter(7), nullptr);
  const CounterLookup lookup = buffer.FindByCounter(7);
  EXPECT_EQ(lookup.sample, nullptr);
  EXPECT_FALSE(lookup.eviction_miss);
}

TEST(UtBusSampleBuffer, FindsASampleByItsCounter) {
  SampleBuffer buffer(4);
  for (std::uint32_t i = 10; i < 14; ++i) buffer.Push(MakeSample(i, i));
  const CounterLookup lookup = buffer.FindByCounter(12);
  ASSERT_NE(lookup.sample, nullptr);
  EXPECT_EQ(lookup.sample->sig.measurement_counter.value(), 12u);
  EXPECT_FALSE(lookup.eviction_miss);
}

TEST(UtBusSampleBuffer, ACounterNeverMadeIsNotAnEvictionMiss) {
  SampleBuffer buffer(4);
  buffer.Push(MakeSample(10, 1));
  buffer.Push(MakeSample(12, 2));  // 11 was never made
  buffer.Push(MakeSample(13, 3));
  const CounterLookup lookup = buffer.FindByCounter(11);
  EXPECT_EQ(lookup.sample, nullptr);
  EXPECT_FALSE(lookup.eviction_miss);
  EXPECT_EQ(buffer.EvictionMisses(), 0u);
}

TEST(UtBusSampleBuffer, AnEvictedCounterReportsAnEvictionMissAndIsCounted) {
  SampleBuffer buffer(2);
  for (std::uint32_t i = 1; i <= 4; ++i) buffer.Push(MakeSample(i, i));  // holds 3 and 4
  const CounterLookup lookup = buffer.FindByCounter(1);
  EXPECT_EQ(lookup.sample, nullptr);
  EXPECT_TRUE(lookup.eviction_miss);
  EXPECT_EQ(buffer.EvictionMisses(), 1u);
  EXPECT_TRUE(buffer.FindByCounter(2).eviction_miss);
  EXPECT_EQ(buffer.EvictionMisses(), 2u);
  // A counter newer than everything held is not an eviction.
  EXPECT_FALSE(buffer.FindByCounter(9).eviction_miss);
}

TEST(UtBusSampleBuffer, NewestCounterNotAfterTakesTheNewestAtOrBeforeTheWantedCounter) {
  SampleBuffer buffer(8);
  for (std::uint32_t c : {10u, 11u, 13u, 14u}) buffer.Push(MakeSample(c, c));
  EXPECT_EQ(buffer.NewestCounterNotAfter(13)->sig.measurement_counter.value(), 13u);
  EXPECT_EQ(buffer.NewestCounterNotAfter(12)->sig.measurement_counter.value(), 11u);  // 12 is not held
  EXPECT_EQ(buffer.NewestCounterNotAfter(99)->sig.measurement_counter.value(), 14u);
  EXPECT_EQ(buffer.NewestCounterNotAfter(9), nullptr);  // everything held is after it
}

TEST(UtBusSampleBuffer, NewestNotAfterTakesTheNewestArrivedAtOrBeforeTheTime) {
  SampleBuffer buffer(8);
  for (std::uint32_t i = 1; i <= 4; ++i) buffer.Push(MakeSample(i, i * 1000));
  EXPECT_EQ(buffer.NewestNotAfter(3000)->sig.measurement_counter.value(), 3u);
  EXPECT_EQ(buffer.NewestNotAfter(3999)->sig.measurement_counter.value(), 3u);
  EXPECT_EQ(buffer.NewestNotAfter(1'000'000)->sig.measurement_counter.value(), 4u);
  EXPECT_EQ(buffer.NewestNotAfter(999), nullptr);
}

TEST(UtBusSampleBuffer, ASampleWithoutACounterIsNeverMatchedByNumber) {
  SampleBuffer buffer(4);
  Sample unknown;
  unknown.arrival_ns = 5;
  buffer.Push(unknown);
  buffer.Push(MakeSample(8, 6));
  EXPECT_EQ(buffer.NewestCounterNotAfter(100)->sig.measurement_counter.value(), 8u);
  EXPECT_EQ(buffer.FindByCounter(0).sample, nullptr);
  EXPECT_NE(buffer.NewestNotAfter(5), nullptr);  // the time search still sees it
}

// Wrap-around: the sender counts ... 0xFFFFFFFE, 0xFFFFFFFF, 1, 2 ... (a
// counter of 0 is unknown in the contract, so a real stream does not use it).
// A plain comparison would call 0xFFFFFFFF the newest and 1 the oldest.
TEST(UtBusSampleBuffer, CountersCompareByDistanceAcrossTheWrap) {
  SampleBuffer buffer(4);
  for (std::uint32_t c : {0xFFFFFFFEu, 0xFFFFFFFFu, 1u, 2u}) buffer.Push(MakeSample(c, c + 10));
  // A naive `counter <= wanted` would answer 2 for a wanted 0xFFFFFFFF.
  EXPECT_EQ(buffer.NewestCounterNotAfter(0xFFFFFFFFu)->sig.measurement_counter.value(), 0xFFFFFFFFu);
  EXPECT_EQ(buffer.NewestCounterNotAfter(1)->sig.measurement_counter.value(), 1u);
  EXPECT_EQ(buffer.NewestCounterNotAfter(2)->sig.measurement_counter.value(), 2u);
  ASSERT_NE(buffer.FindByCounter(1).sample, nullptr);
  EXPECT_EQ(buffer.FindByCounter(0xFFFFFFFEu).sample->sig.measurement_counter.value(), 0xFFFFFFFEu);
}

TEST(UtBusSampleBuffer, AnEvictionMissIsFoundAcrossTheWrap) {
  SampleBuffer buffer(2);
  for (std::uint32_t c : {0xFFFFFFFEu, 0xFFFFFFFFu, 1u, 2u}) buffer.Push(MakeSample(c, c + 10));  // holds 1 and 2
  // 0xFFFFFFFF is numerically larger than everything held, so a plain `<`
  // would miss that it is older than the oldest.
  const CounterLookup lookup = buffer.FindByCounter(0xFFFFFFFFu);
  EXPECT_EQ(lookup.sample, nullptr);
  EXPECT_TRUE(lookup.eviction_miss);
}

// The contract reads a 0 measurement_counter as unknown. A naive read keeps
// the 0 and matches it; the buffer holds an unknown, which matches nothing.
TEST(UtBusSampleBuffer, ASampleWithAnUnknownCounterIsNeverFoundAndAWantedZeroFindsNothing) {
  SampleBuffer buffer(4);
  Sample unknown = MakeSample(0, 10);
  unknown.sig.measurement_counter = Unknown<std::uint32_t>::None();  // a zero header, as the door reads it
  buffer.Push(unknown);
  buffer.Push(MakeSample(5, 20));
  EXPECT_EQ(buffer.FindByCounter(0).sample, nullptr);
  EXPECT_FALSE(buffer.FindByCounter(0).eviction_miss);
  EXPECT_EQ(buffer.NewestCounterNotAfter(0), nullptr);
  EXPECT_EQ(buffer.NewestCounterNotAfter(100)->sig.measurement_counter.value(), 5u);
  EXPECT_EQ(buffer.EvictionMisses(), 0u);
}

TEST(UtBusSampleBuffer, AWantedZeroIsNotAnEvictionMissEvenAfterEvictions) {
  SampleBuffer buffer(1);
  buffer.Push(MakeSample(7, 1));
  buffer.Push(MakeSample(8, 2));  // 7 evicted
  EXPECT_FALSE(buffer.FindByCounter(0).eviction_miss);
  EXPECT_EQ(buffer.EvictionMisses(), 0u);
}

Sample MakeSampleWithSourceTime(std::uint32_t counter, std::uint64_t source_us) {
  Sample sample = MakeSample(counter, counter);
  if (source_us != 0) sample.sig.source_timestamp_us = source_us;
  return sample;
}

TEST(UtBusSampleBuffer, NewestSourceTimeNotAfterTakesTheNewestAtOrBeforeTheTime) {
  SampleBuffer buffer(8);
  buffer.Push(MakeSampleWithSourceTime(1, 1000));
  buffer.Push(MakeSampleWithSourceTime(2, 2000));
  buffer.Push(MakeSampleWithSourceTime(3, 0));  // unknown source time
  buffer.Push(MakeSampleWithSourceTime(4, 4000));
  EXPECT_EQ(buffer.NewestSourceTimeNotAfter(3000)->sig.measurement_counter.value(), 2u);  // skips the unknown
  EXPECT_EQ(buffer.NewestSourceTimeNotAfter(4000)->sig.measurement_counter.value(), 4u);
  EXPECT_EQ(buffer.NewestSourceTimeNotAfter(5000)->sig.measurement_counter.value(), 4u);
  EXPECT_EQ(buffer.NewestSourceTimeNotAfter(999), nullptr);
}

// A naive read keeps the 0 as a time, which is "not after" every wanted time.
TEST(UtBusSampleBuffer, ASampleWithAnUnknownSourceTimeIsNeverTakenByTimeAndAWantedZeroFindsNothing) {
  SampleBuffer buffer(4);
  buffer.Push(MakeSampleWithSourceTime(1, 0));
  EXPECT_EQ(buffer.NewestSourceTimeNotAfter(1'000'000), nullptr);
  buffer.Push(MakeSampleWithSourceTime(2, 500));
  EXPECT_EQ(buffer.NewestSourceTimeNotAfter(0), nullptr);
  EXPECT_NE(buffer.NewestNotAfter(1), nullptr);  // the arrival-time half still sees the unknown-time sample
}

}  // namespace
}  // namespace simcore::bus
