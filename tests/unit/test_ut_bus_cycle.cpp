// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-BUS-07`..`UT-BUS-13`, `UT-BUS-19` (`WP-08`, `SI-02` `bus`):
///   `CycleReconstructor`'s recovery ladder, forced-floor validation,
///   gap/repeat detection and measured-rate tracking. `F-FOREIGN`/
///   `F-LADDER` (Software Test Spec §4) are synthetic here -- crafted
///   `PortMessage` sequences, since no `.mcap` fixture carries decoded
///   header fields yet (this WP's own scope note, `bus.hpp::PortMessage`).
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

PortMessage MakeMsg(std::string port, std::int64_t t_recv_ns) {
  PortMessage msg;
  msg.port = std::move(port);
  msg.t_recv_ns = t_recv_ns;
  return msg;
}

// UT-BUS-07: F-FOREIGN -- no two messages share a reception timestamp,
// each port carries its own counter. Reconstruct cycles; count ports per
// cycle against the graph's expected input set (SW-0049's own defect fix
// -- grouping by counter, never by reception-time equality).
TEST(UtBusCycle07, ForeignRecordingGroupsByCounterNotReceptionTime) {
  CycleReconstructor rc({"a", "b"});

  PortMessage a1 = MakeMsg("a", 1000);
  a1.counter = 5u;
  PortMessage b1 = MakeMsg("b", 1731);  // deliberately different reception time
  b1.counter = 5u;

  ASSERT_TRUE(rc.Ingest(a1).ok());
  EXPECT_FALSE(rc.TakeCompleteCycle().has_value());  // "b" not seen yet for this cycle
  ASSERT_TRUE(rc.Ingest(b1).ok());

  auto cycle = rc.TakeCompleteCycle();
  ASSERT_TRUE(cycle.has_value());
  EXPECT_EQ(cycle->ports.size(), 2u);  // multi-port input set, not "one port each"
  EXPECT_EQ(cycle->ports.at("a").counter.value(), 5u);
  EXPECT_EQ(cycle->ports.at("b").counter.value(), 5u);
  EXPECT_FALSE(rc.TakeCompleteCycle().has_value());  // nothing else pending
}

// UT-BUS-08: F-LADDER -- one variant per rung. RungUsed reads back
// exactly which rung a message actually landed on.
TEST(UtBusCycle08, EachLadderVariantSelectsItsOwnRung) {
  CycleReconstructor rc({"p"});

  PortMessage bySourceCycleId = MakeMsg("p", 100);
  bySourceCycleId.source_cycle_id = 1u;
  bySourceCycleId.counter = 1u;  // present too -- rung 1 must still win
  ASSERT_TRUE(rc.Ingest(bySourceCycleId).ok());
  EXPECT_EQ(rc.RungUsed("p"), Rung::SourceCycleId);
  EXPECT_EQ(rc.QualityUsed("p"), Quality::Exact);

  PortMessage byCounter = MakeMsg("p", 200);
  byCounter.counter = 2u;
  ASSERT_TRUE(rc.Ingest(byCounter).ok());
  EXPECT_EQ(rc.RungUsed("p"), Rung::HeaderCounter);
  EXPECT_EQ(rc.QualityUsed("p"), Quality::Exact);

  PortMessage bySourceTime = MakeMsg("p", 300);
  bySourceTime.t_source_ns = 250;
  ASSERT_TRUE(rc.Ingest(bySourceTime).ok());
  EXPECT_EQ(rc.RungUsed("p"), Rung::SourceTime);
  EXPECT_EQ(rc.QualityUsed("p"), Quality::Derived);

  PortMessage byReception = MakeMsg("p", 400);  // no counter, no source time
  ASSERT_TRUE(rc.Ingest(byReception).ok());
  EXPECT_EQ(rc.RungUsed("p"), Rung::ReceptionTime);
  EXPECT_EQ(rc.QualityUsed("p"), Quality::Approximated);
}

// UT-BUS-08's own demotion case: source time present but not monotonic.
TEST(UtBusCycle08, NonMonotonicSourceTimeDemotesToReceptionTime) {
  CycleReconstructor rc({"p"});

  PortMessage first = MakeMsg("p", 100);
  first.t_source_ns = 500;
  ASSERT_TRUE(rc.Ingest(first).ok());
  EXPECT_EQ(rc.RungUsed("p"), Rung::SourceTime);

  PortMessage regressed = MakeMsg("p", 200);
  regressed.t_source_ns = 400;  // decreased -- not monotonic for this port
  ASSERT_TRUE(rc.Ingest(regressed).ok());
  EXPECT_EQ(rc.RungUsed("p"), Rung::ReceptionTime);  // demoted, never SourceTime

  ASSERT_EQ(rc.Demotions().size(), 1u);
  EXPECT_EQ(rc.Demotions()[0].port, "p");
  EXPECT_EQ(rc.Demotions()[0].from, Rung::SourceTime);
  EXPECT_EQ(rc.Demotions()[0].to, Rung::ReceptionTime);
  EXPECT_EQ(rc.Demotions()[0].previous_t_source_ns, 500);
  EXPECT_EQ(rc.Demotions()[0].offending_t_source_ns, 400);
}

// Equal (non-decreasing, not strictly increasing) source time must NOT
// demote -- SW-0050's own "non-decreasing, not strictly increasing"
// clause: two messages legitimately sharing a stamp is not a defect.
TEST(UtBusCycle08, EqualSourceTimeIsMonotonicNotADemotion) {
  CycleReconstructor rc({"p"});
  PortMessage first = MakeMsg("p", 100);
  first.t_source_ns = 500;
  ASSERT_TRUE(rc.Ingest(first).ok());

  PortMessage same = MakeMsg("p", 200);
  same.t_source_ns = 500;
  ASSERT_TRUE(rc.Ingest(same).ok());
  EXPECT_EQ(rc.RungUsed("p"), Rung::SourceTime);
  EXPECT_TRUE(rc.Demotions().empty());
}

// UT-BUS-09: F-LADDER -- force a port's rung down and read it back; then
// attempt to force it up (an Authoring error, naming the port).
TEST(UtBusCycle09, ForceDownSucceedsForceUpIsAuthoringError) {
  CycleReconstructor rc({"p"}, {LadderFloor{"p", Rung::ReceptionTime}});

  PortMessage msg = MakeMsg("p", 100);
  msg.counter = 7u;  // the data supports HeaderCounter...
  auto result = rc.Ingest(msg);
  ASSERT_TRUE(result.ok());
  EXPECT_EQ(rc.RungUsed("p"), Rung::ReceptionTime);  // ...but the floor forces it down

  CycleReconstructor rcUp({"q"}, {LadderFloor{"q", Rung::SourceCycleId}});
  PortMessage weak = MakeMsg("q", 100);
  weak.counter = 3u;  // no source_cycle_id -- the floor asks for more than the data has
  auto failed = rcUp.Ingest(weak);
  ASSERT_FALSE(failed.ok());
  EXPECT_EQ(failed.error().kind, Kind::Authoring);
  EXPECT_EQ(failed.error().where, "q");
}

// UT-BUS-11: F-DAMAGED -- reconstruct across a counter gap; enumerate
// reported gaps, missing cycles are never synthesised.
TEST(UtBusCycle11, CounterDiscontinuityIsReportedNotSynthesised) {
  CycleReconstructor rc({"p"});
  PortMessage m1 = MakeMsg("p", 100);
  m1.counter = 10u;
  PortMessage m2 = MakeMsg("p", 200);
  m2.counter = 14u;  // 11, 12, 13 missing
  ASSERT_TRUE(rc.Ingest(m1).ok());
  ASSERT_TRUE(rc.Ingest(m2).ok());

  ASSERT_EQ(rc.Gaps().size(), 1u);
  EXPECT_EQ(rc.Gaps()[0].port, "p");
  EXPECT_EQ(rc.Gaps()[0].from, 10u);
  EXPECT_EQ(rc.Gaps()[0].to, 14u);
  EXPECT_EQ(rc.Gaps()[0].missed, 3u);
}

TEST(UtBusCycle11, ConsecutiveCounterProducesNoGap) {
  CycleReconstructor rc({"p"});
  PortMessage m1 = MakeMsg("p", 100);
  m1.counter = 10u;
  PortMessage m2 = MakeMsg("p", 200);
  m2.counter = 11u;
  ASSERT_TRUE(rc.Ingest(m1).ok());
  ASSERT_TRUE(rc.Ingest(m2).ok());
  EXPECT_TRUE(rc.Gaps().empty());
}

// UT-BUS-12: F-FOREIGN -- deliver an unchanged freshness key twice; read
// is_repeat.
TEST(UtBusCycle12, UnchangedFreshnessKeyIsRepeat) {
  CycleReconstructor rc({"p"});
  PortMessage m1 = MakeMsg("p", 100);
  m1.counter = 9u;
  PortMessage m2 = MakeMsg("p", 200);
  m2.counter = 9u;  // unchanged
  ASSERT_TRUE(rc.Ingest(m1).ok());
  EXPECT_FALSE(rc.IsRepeat("p"));  // first sighting is never a repeat
  ASSERT_TRUE(rc.Ingest(m2).ok());
  EXPECT_TRUE(rc.IsRepeat("p"));

  PortMessage m3 = MakeMsg("p", 300);
  m3.counter = 10u;  // changed again
  ASSERT_TRUE(rc.Ingest(m3).ok());
  EXPECT_FALSE(rc.IsRepeat("p"));
}

// UT-BUS-13: F-FOREIGN -- run a port at a rate differing from its
// declared period; read the reported comparison.
TEST(UtBusCycle13, MeasuredRateComparesAgainstDeclaredPeriod) {
  CycleReconstructor rc({"p"});
  // Three messages 25ms apart, declared period 20ms -- a real mismatch.
  for (std::int64_t t = 0; t < 3; ++t) {
    PortMessage msg = MakeMsg("p", t * 25'000'000);
    msg.t_source_ns = t * 25'000'000;
    ASSERT_TRUE(rc.Ingest(msg).ok());
  }
  RateReport report = rc.MeasuredRate("p", /*declared_period_ns=*/20'000'000);
  ASSERT_TRUE(report.has_data);
  EXPECT_DOUBLE_EQ(report.mean_period_ns, 25'000'000.0);
  EXPECT_TRUE(report.mismatch);

  RateReport noData = rc.MeasuredRate("nope", 20'000'000);
  EXPECT_FALSE(noData.has_data);
}

TEST(UtBusCycle13, MeasuredRateWithinBandIsNotAMismatch) {
  CycleReconstructor rc({"p"});
  for (std::int64_t t = 0; t < 3; ++t) {
    PortMessage msg = MakeMsg("p", t * 20'000'000);
    msg.t_source_ns = t * 20'000'000;
    ASSERT_TRUE(rc.Ingest(msg).ok());
  }
  RateReport report = rc.MeasuredRate("p", 20'000'000);
  ASSERT_TRUE(report.has_data);
  EXPECT_FALSE(report.mismatch);
}

// UT-BUS-19: F-LADDER -- a port carrying both stamps; source time is
// preferred over capture time wherever both exist (t_source_ns is what
// the ladder and rate tracking read; t_capture_ns is carried through
// unused by this class, which is itself the point -- it never overrides
// which clock cycle reconstruction believes).
TEST(UtBusCycle19, SourceTimePreferredOverCaptureWhenBothPresent) {
  CycleReconstructor rc({"p"});
  PortMessage msg = MakeMsg("p", 999);
  msg.t_source_ns = 111;
  msg.t_capture_ns = 222;  // present too, but must not be what selects the rung
  ASSERT_TRUE(rc.Ingest(msg).ok());
  EXPECT_EQ(rc.RungUsed("p"), Rung::SourceTime);

  auto cycle = rc.TakeCompleteCycle();
  ASSERT_TRUE(cycle.has_value());
  EXPECT_EQ(cycle->ports.at("p").t_source_ns.value(), 111);
  EXPECT_EQ(cycle->ports.at("p").t_capture_ns.value(), 222);
}

}  // namespace
}  // namespace simcore::bus
