// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `IdentityTracker::Observe` (`WP-02`, `IMP-0009`): a counter reset, a
///   counter gap and identity broken told apart by the `counterDistance` of
///   both counters (`D17 (3)`), including across the `uint32` wrap, with
///   planted comparisons a `<` or a "restarted from 1" rule would fail. Unit
///   tests of the tracker; the system tests `SYT-SEL-10` and `SYT-SEL-11` are
///   built in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <cstdint>

#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

SignalHeader Header(std::uint32_t measurement, std::uint32_t cycle) {
  SignalHeader header;
  header.measurement_counter = measurement;
  header.cycle_counter = cycle;
  header.present = true;
  return header;
}

TEST(UtBusIdentity, ACountingSenderIsOkAndTheFirstSampleIsFirst) {
  IdentityTracker tracker;
  EXPECT_EQ(tracker.Observe("p", Header(1, 1)).verdict, IdentityVerdict::kFirst);
  EXPECT_EQ(tracker.Observe("p", Header(2, 2)).verdict, IdentityVerdict::kOk);
  EXPECT_EQ(tracker.Observe("p", Header(3, 3)).verdict, IdentityVerdict::kOk);
  const IdentityCounts counts = tracker.Counts("p");
  EXPECT_EQ(counts.samples, 3u);
  EXPECT_EQ(counts.gaps + counts.resets + counts.identity_broken, 0u);
}

TEST(UtBusIdentity, AMeasurementJumpIsAGapWithTheMissedCount) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(10, 1));
  const IdentityResult result = tracker.Observe("p", Header(14, 2));
  EXPECT_EQ(result.verdict, IdentityVerdict::kCounterGap);
  EXPECT_EQ(result.measurement_distance, 4);
  EXPECT_EQ(result.missed, 3u);
  EXPECT_EQ(tracker.Counts("p").gaps, 1u);
  EXPECT_EQ(tracker.Observe("p", Header(15, 3)).verdict, IdentityVerdict::kOk);  // the gap is counted once
}

TEST(UtBusIdentity, BothCountersGoingBackIsAResetNotBroken) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(100, 100));
  const IdentityResult result = tracker.Observe("p", Header(5, 5));  // the sender restarted
  EXPECT_EQ(result.verdict, IdentityVerdict::kCounterReset);
  EXPECT_LT(result.measurement_distance, 0);
  EXPECT_LT(result.cycle_distance, 0);
  EXPECT_EQ(tracker.Counts("p").resets, 1u);
  EXPECT_EQ(tracker.Counts("p").identity_broken, 0u);
  // The restart is judged against the new numbers afterwards.
  EXPECT_EQ(tracker.Observe("p", Header(6, 6)).verdict, IdentityVerdict::kOk);
}

TEST(UtBusIdentity, AResetNeedNotRestartFromOne) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(5000, 5000));
  EXPECT_EQ(tracker.Observe("p", Header(37, 40)).verdict, IdentityVerdict::kCounterReset);
}

TEST(UtBusIdentity, MeasurementGoingBackWhileCycleCountsUpIsIdentityBroken) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(100, 10));
  const IdentityResult result = tracker.Observe("p", Header(90, 11));
  EXPECT_EQ(result.verdict, IdentityVerdict::kIdentityBroken);
  EXPECT_EQ(tracker.Counts("p").identity_broken, 1u);
  EXPECT_EQ(tracker.Counts("p").resets, 0u);
}

TEST(UtBusIdentity, MeasurementRepeatingWhileCycleCountsUpIsIdentityBroken) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(100, 10));
  EXPECT_EQ(tracker.Observe("p", Header(100, 11)).verdict, IdentityVerdict::kIdentityBroken);
}

TEST(UtBusIdentity, ABothCountersRepeatedDeliveryIsNotBroken) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(100, 10));
  EXPECT_EQ(tracker.Observe("p", Header(100, 10)).verdict, IdentityVerdict::kOk);
}

// A wrap is not a reset: the cycle counter 0xFFFFFFFF -> 0 is distance +1
// (a cycle_counter of 0 is a real count). The measurement counter has no 0
// (0 is unknown), so it wraps 0xFFFFFFFF -> 1, a step of 2.
TEST(UtBusIdentity, CountersWrappingAtUint32AreNotAReset) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(0xFFFFFFFFu, 0xFFFFFFFFu));
  const IdentityResult result = tracker.Observe("p", Header(1u, 0u));
  EXPECT_EQ(result.verdict, IdentityVerdict::kCounterGap);  // measurement 0 was skipped
  EXPECT_EQ(result.measurement_distance, 2);
  EXPECT_EQ(result.cycle_distance, 1);
  EXPECT_EQ(tracker.Counts("p").resets, 0u);
}

TEST(UtBusIdentity, AGapAcrossTheWrapIsCountedByDistance) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(0xFFFFFFFEu, 1));
  const IdentityResult result = tracker.Observe("p", Header(3u, 2));  // 0xFFFFFFFF, 0, 1, 2 missed
  EXPECT_EQ(result.verdict, IdentityVerdict::kCounterGap);
  EXPECT_EQ(result.measurement_distance, 5);
  EXPECT_EQ(result.missed, 4u);
}

// Planted: a plain `current < previous` rule calls this a reset; by distance
// it is a step forward of 2^31 - 1 (a gap).
TEST(UtBusIdentity, AHalfRangeStepForwardIsAGapNotAReset) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(10, 10));
  EXPECT_EQ(tracker.Observe("p", Header(10u + 0x7FFFFFFFu, 11)).verdict, IdentityVerdict::kCounterGap);
}

TEST(UtBusIdentity, PortsAreTrackedSeparately) {
  IdentityTracker tracker;
  tracker.Observe("a", Header(100, 100));
  tracker.Observe("b", Header(1, 1));
  EXPECT_EQ(tracker.Observe("b", Header(2, 2)).verdict, IdentityVerdict::kOk);
  EXPECT_EQ(tracker.Observe("a", Header(1, 1)).verdict, IdentityVerdict::kCounterReset);
  EXPECT_EQ(tracker.Counts("a").resets, 1u);
  EXPECT_EQ(tracker.Counts("b").resets, 0u);
  EXPECT_EQ(tracker.Counts("never").samples, 0u);
}

TEST(UtBusIdentity, AnUnknownCounterIsNotJudgedAndChangesNothing) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(10, 10));
  SignalHeader unknown;  // no sig_header
  EXPECT_EQ(tracker.Observe("p", unknown).verdict, IdentityVerdict::kNotComparable);
  EXPECT_EQ(tracker.Observe("p", Header(11, 11)).verdict, IdentityVerdict::kOk);
  EXPECT_EQ(tracker.Counts("p").samples, 2u);
  EXPECT_EQ(tracker.Counts("p").unknown, 1u);
}

// A zero header as the door reads it: measurement_counter unknown, cycle
// counter a real count. A naive read keeps the 0 and calls it a reset (it
// went back) or broken (it went back while the cycle counted up).
TEST(UtBusIdentity, AZeroMeasurementCounterIsNeitherAResetNorBrokenNorAGap) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(100, 10));
  SignalHeader zero_measurement;
  zero_measurement.cycle_counter = 11u;  // counting up
  zero_measurement.present = true;       // measurement_counter left unknown
  const IdentityResult result = tracker.Observe("p", zero_measurement);
  EXPECT_EQ(result.verdict, IdentityVerdict::kNotComparable);
  EXPECT_EQ(tracker.Counts("p").identity_broken, 0u);
  EXPECT_EQ(tracker.Counts("p").resets, 0u);
  EXPECT_EQ(tracker.Counts("p").gaps, 0u);
  EXPECT_EQ(tracker.Counts("p").unknown, 1u);
  // The earlier sample is still the one the next is compared with.
  EXPECT_EQ(tracker.Observe("p", Header(101, 12)).verdict, IdentityVerdict::kOk);
}

// `IMP-0050`: the caller knows the bytes differ from a sample of the same counter.
TEST(UtBusIdentity, TheSameCountersWithOtherContentIsIdentityBrokenOnlyWhenTheCallerSaysSo) {
  IdentityTracker without_content;
  without_content.Observe("p", Header(8, 8));
  // Same counters, nothing said about content: not judged broken (a plain repeat).
  EXPECT_EQ(without_content.Observe("p", Header(8, 8)).verdict, IdentityVerdict::kOk);

  IdentityTracker with_content;
  with_content.Observe("p", Header(8, 8));
  const IdentityResult result = with_content.Observe("p", Header(8, 8), /*content_differs=*/true);
  EXPECT_EQ(result.verdict, IdentityVerdict::kIdentityBroken);  // whatever the cycle counter does
  EXPECT_EQ(result.measurement_distance, 0);
  EXPECT_EQ(result.cycle_distance, 0);
  EXPECT_EQ(with_content.Counts("p").identity_broken, 1u);
}

TEST(UtBusIdentity, ContentDiffersChangesNothingAtAnotherMeasurementDistance) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(8, 8));
  EXPECT_EQ(tracker.Observe("p", Header(9, 9), /*content_differs=*/true).verdict, IdentityVerdict::kOk);
  EXPECT_EQ(tracker.Observe("p", Header(20, 10), true).verdict, IdentityVerdict::kCounterGap);
  EXPECT_EQ(tracker.Observe("p", Header(3, 2), true).verdict, IdentityVerdict::kCounterReset);
  EXPECT_EQ(tracker.Counts("p").identity_broken, 0u);
}

TEST(UtBusIdentity, ContentDiffersOnASampleWithAnUnknownCounterIsNotJudged) {
  IdentityTracker tracker;
  tracker.Observe("p", Header(8, 8));
  SignalHeader unknown;
  unknown.cycle_counter = 9u;
  unknown.present = true;
  EXPECT_EQ(tracker.Observe("p", unknown, true).verdict, IdentityVerdict::kNotComparable);
}

}  // namespace
}  // namespace simcore::bus
