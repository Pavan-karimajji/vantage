// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `UT-EDG-03`/`04`/`05` (`IMP-0134`/`0135`/`0136`, `WP-15`):
///   `CostReport`/`ByteCounter`/`ScopedTimer`. `ByteCounter::Observe` is
///   exercised at the exact call shape `io::Reader::ReadRange` produces
///   (one call per `RawMessage` actually pulled, its real
///   `payload.size()`) -- a topic nothing pulls gets no `Observe` call at
///   all, which is what makes "a run decoding no image topic reports zero
///   image bytes" true by construction rather than by a zero-fill pass.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <thread>

#include <gtest/gtest.h>

namespace simcore::diagnostics {
namespace {

TEST(UtEdg04ByteCounter, PerTopicTotalEqualsRunTotal) {
  ByteCounter counter;
  counter.Observe("/a/objects", 100);
  counter.Observe("/a/objects", 50);
  counter.Observe("/b/veh_dyn", 24);

  std::uint64_t topic_sum = 0;
  for (const auto& [topic, bytes] : counter.PerTopic()) topic_sum += bytes;

  EXPECT_EQ(counter.Total(), topic_sum);
  EXPECT_EQ(counter.Total(), 174u);
  EXPECT_EQ(counter.ForTopic("/a/objects"), 150u);
}

TEST(UtEdg04ByteCounter, ATopicNothingPullsReportsExactlyZeroNeverEstimated) {
  ByteCounter counter;
  counter.Observe("/a/objects", 100);
  // "/a/image" is never Observe()'d -- exactly the "decoded no image"
  // shape (SW-0135's own Accept clause).
  EXPECT_EQ(counter.ForTopic("/a/image"), 0u);
  EXPECT_EQ(counter.PerTopic().count("/a/image"), 0u);  // no entry at all, not a zero entry
}

TEST(UtEdg04ByteCounter, IsARealCountNotDerivedFromMessageCountOrTiming) {
  // Two messages of very different sizes on the same topic -- if this were
  // secretly estimating from a message count, both totals below would be
  // equal (2 messages each); they are not, because it is a real byte sum.
  ByteCounter a;
  a.Observe("/t", 4);
  a.Observe("/t", 4);

  ByteCounter b;
  b.Observe("/t", 1);
  b.Observe("/t", 4096);

  EXPECT_EQ(a.Total(), 8u);
  EXPECT_EQ(b.Total(), 4097u);
  EXPECT_NE(a.Total(), b.Total());
}

TEST(UtEdg03CostReport, AllFiveFieldsPresentAndReconcile) {
  CostReport report;
  report.wall_time = std::chrono::milliseconds(100);
  report.cycles_executed = 10;
  report.time_per_module["a"] = std::chrono::milliseconds(30);
  report.time_per_module["b"] = std::chrono::milliseconds(20);
  report.time_reading = std::chrono::milliseconds(5);
  report.bytes_read_per_topic["/a/out"] = 40;
  report.bytes_read_per_topic["/b/out"] = 60;
  report.bytes_read_total = 100;

  EXPECT_TRUE(report.Reconcile().empty());
}

TEST(UtEdg03CostReport, PerTopicByteMismatchAgainstTheRunTotalIsAFinding) {
  CostReport report;
  report.wall_time = std::chrono::milliseconds(100);
  report.bytes_read_per_topic["/a/out"] = 40;
  report.bytes_read_total = 999;  // deliberately wrong

  const std::vector<std::string> findings = report.Reconcile();
  ASSERT_FALSE(findings.empty());
  EXPECT_NE(findings[0].find("bytes_read"), std::string::npos);
}

TEST(UtEdg03CostReport, PerModuleTimeExceedingWallTimeIsAFinding) {
  CostReport report;
  report.wall_time = std::chrono::milliseconds(10);
  report.time_per_module["a"] = std::chrono::milliseconds(50);  // impossible

  const std::vector<std::string> findings = report.Reconcile();
  ASSERT_FALSE(findings.empty());
  EXPECT_NE(findings[0].find("wall_time"), std::string::npos);
}

TEST(UtEdg03CostReport, ReconcilesAgainstACycleTraceWhenGiven) {
  CycleTrace trace;
  trace.Record(CycleTraceEntry{0, "a", CycleOutcome::kRan, {}, std::chrono::milliseconds(10)});
  trace.Record(CycleTraceEntry{1, "a", CycleOutcome::kRan, {}, std::chrono::milliseconds(15)});

  CostReport report;
  report.wall_time = std::chrono::milliseconds(100);
  report.time_per_module["a"] = std::chrono::milliseconds(25);
  EXPECT_TRUE(report.Reconcile(&trace).empty());

  report.time_per_module["a"] = std::chrono::milliseconds(50);  // disagrees with the trace, still under wall_time
  const std::vector<std::string> findings = report.Reconcile(&trace);
  ASSERT_FALSE(findings.empty());
  EXPECT_NE(findings[0].find("CycleTrace"), std::string::npos);
}

// UT-EDG-05: a measured duration never enters a value this class reports
// back into scheduling/output -- ScopedTimer only ever accumulates into a
// caller-owned nanoseconds reference, and has no accessor of its own a
// scheduling path could read (a compile-time property; this test only
// exercises the timing accumulation itself is well-formed and monotonic).
TEST(UtEdg05ScopedTimer, AccumulatesRealElapsedTimeAndNothingElse) {
  std::chrono::nanoseconds total{0};
  {
    ScopedTimer timer(total);
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  EXPECT_GT(total.count(), 0);

  const std::chrono::nanoseconds after_first = total;
  {
    ScopedTimer timer(total);
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  EXPECT_GT(total, after_first);  // accumulates, never resets
}

}  // namespace
}  // namespace simcore::diagnostics
