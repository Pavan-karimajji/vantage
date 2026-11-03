// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SelectInputs` (`RCT:IMP-0033`, `WP-05`; serves `RCT:SYS-0016`,
///   `VANTAGE_Architecture.md` §6): by the recorded refSync, entry 0, the
///   counter fallback up to `fallback_max_gap`, the time rule beyond it and
///   for a stage with no recorded refSync, waiting on a `simulate` producer,
///   the read-ahead, a previous-cycle input, an unwired input. Each case is
///   built so the naive "newest sample" version fails it. The system tests
///   `SYT-SEL-*` run over a lab case in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "common/cycle_control.pb.h"
#include "common/ref_sync.pb.h"
#include "run_fixtures.hpp"
#include "simcore/runner.hpp"

namespace simcore::runner {
namespace {

using testing::Data;
using testing::Message;
using testing::RefSyncOf;
using testing::VectorReader;

const google::protobuf::Descriptor* DataType() { return adas::common::CycleControl::descriptor(); }

SpecPort Port(const std::string& name, const std::string& dir) {
  SpecPort port;
  port.name = name;
  port.dir = dir;
  port.kind = "data";
  port.proto_type = "adas.common.CycleControl";
  port.record = "full";
  port.buffer_depth = 8;
  return port;
}

// `A` produces `out`; `B` reads it as `objects` (and `lone`, which nobody wires).
struct Rig {
  explicit Rig(const std::string& producer_mode = "measured", bool previous_cycle = false, std::int64_t depth = 8) {
    SpecStage producer;
    producer.name = "A";
    producer.mode = producer_mode;
    producer.ports.push_back(Port("out", "pro"));
    SpecStage stage;
    stage.name = "B";
    stage.mode = "simulate";
    stage.ports = {Port("control", "req"), Port("objects", "req"), Port("lone", "req"), Port("outputs", "pro")};
    SpecInput input;
    input.port = "objects";
    input.producer = "A";
    input.producer_port = "out";
    input.previous_cycle = previous_cycle;
    stage.inputs.push_back(input);
    spec.stages = {producer, stage};
    bus.DeclarePort("A.out", depth, DataType());
    reference.Declare("B.refSync", 8, adas::common::RefSync::descriptor());
  }

  void Sample(std::uint32_t counter, std::uint64_t source_us, std::int64_t arrival_ns,
              std::optional<std::uint64_t> committed_step = std::nullopt) {
    bus::PortValue value;
    value.origin = bus::Origin::Measured;
    value.payload = Data(counter, source_us);
    bus::PublishInfo info;
    info.committed_step = committed_step;
    ASSERT_TRUE(bus.Publish("A.out", std::move(value), arrival_ns, info).ok());
  }

  void RecordRefSync(std::uint32_t control_counter, std::uint32_t objects_counter) {
    reference.Add("B.refSync", 1, RefSyncOf(control_counter, {{"objects", objects_counter}, {"lone", 0}}));
  }

  Selection Run(std::uint32_t control_counter, std::uint64_t control_us = 0, std::int64_t now_ns = 1'000'000,
                bool expired = false, std::uint64_t step = 5, ReadAhead* ahead = nullptr,
                bool control_recorded = false) {
    SelectContext context;
    context.spec = &spec;
    context.stage = &spec.stages[1];
    context.bus = &bus;
    context.reference = &reference;
    context.ahead = ahead;
    context.control_recorded = control_recorded;
    context.controls = &controls;
    context.fallback_max_gap = 4;
    context.now_ns = now_ns;
    context.step = step;
    orchestrator::Ticket ticket;
    ticket.stage = "B";
    ticket.readiness_expired = expired;
    orchestrator::ControlHeader header;
    header.measurement_counter = control_counter;
    header.source_timestamp_us = control_us;
    return SelectInputs(context, ticket, header);
  }

  RunSpec spec;
  bus::PortBus bus;
  RecordedReference reference;
  std::deque<ControlArrival> controls;  // B's recorded controls as they arrived (`IMP-0065`), beside the bus buffer
};

std::uint32_t CounterOf(const InputSelection& input) {
  return bus::ReadSignalHeader(input.sample->value.payload, DataType()).measurement_counter.value();
}

TEST(RunSelectInputs, TheSampleTheRefSyncNamesIsHandedOverNotTheNewest) {
  Rig rig;
  rig.Sample(10, 1000, 10);
  rig.Sample(11, 2000, 20);
  rig.Sample(12, 3000, 30);
  rig.RecordRefSync(/*control=*/100, /*objects=*/11);
  const Selection selection = rig.Run(100);
  ASSERT_FALSE(selection.not_ready);
  const InputSelection& objects = selection.inputs[0];
  ASSERT_TRUE(objects.sample.has_value());
  EXPECT_EQ(CounterOf(objects), 11u);
  EXPECT_FALSE(objects.fallback);
  EXPECT_FALSE(objects.beyond_gap);
}

TEST(RunSelectInputs, OnlyDeclaredWiredDataInputsAreOfferedAndTheControlIsNotOneOfThem) {
  Rig rig;
  rig.Sample(10, 1000, 10);
  rig.RecordRefSync(100, 10);
  const Selection selection = rig.Run(100);
  ASSERT_EQ(selection.inputs.size(), 2u);  // objects, lone -- never control, never an output
  EXPECT_EQ(selection.inputs[0].port, "objects");
  EXPECT_EQ(selection.inputs[1].port, "lone");
  EXPECT_FALSE(selection.inputs[1].offered);  // unwired: not offered at all
  EXPECT_FALSE(selection.inputs[1].fallback);  // and no badge for it
}

TEST(RunSelectInputs, AnEntryOfZeroGivesAnEmptyInputWithNoBadge) {
  Rig rig;
  rig.Sample(10, 1000, 10);
  rig.RecordRefSync(100, 0);
  const Selection selection = rig.Run(100);
  EXPECT_TRUE(selection.inputs[0].offered);
  EXPECT_FALSE(selection.inputs[0].sample.has_value());
  EXPECT_FALSE(selection.inputs[0].fallback);
}

TEST(RunSelectInputs, WithNoRecordedRefSyncTheTimeRuleTakesTheNewestSampleNotAfterTheTriggersTime) {
  Rig rig;
  rig.Sample(10, 1000, 10);
  rig.Sample(11, 2000, 20);
  rig.Sample(12, 3000, 30);  // arrived before `now`, but made after the trigger
  const Selection selection = rig.Run(/*control=*/100, /*control_us=*/2500);
  ASSERT_TRUE(selection.inputs[0].sample.has_value());
  EXPECT_EQ(CounterOf(selection.inputs[0]), 11u);
  EXPECT_TRUE(selection.inputs[0].fallback);  // KIND_FALLBACK on every input of such a stage
}

TEST(RunSelectInputs, AnUnknownTriggerTimeFallsBackToTheNewestSampleThatArrivedByNow) {
  Rig rig;
  rig.Sample(10, 1000, 10);
  rig.Sample(11, 2000, 20);
  rig.Sample(12, 3000, 5'000'000);  // arrives after `now`
  const Selection selection = rig.Run(100, /*control_us=*/0, /*now_ns=*/1'000'000);
  EXPECT_EQ(CounterOf(selection.inputs[0]), 11u);
}

TEST(RunSelectInputs, ASampleWithNoSourceTimeIsComparedByItsArrivalNotSkipped) {
  Rig rig;
  rig.Sample(10, 1000, 10);
  rig.Sample(11, /*source_us=*/0, 500'000);  // newer, but its time is unknown
  const Selection selection = rig.Run(100, /*control_us=*/2500, 1'000'000);
  EXPECT_EQ(CounterOf(selection.inputs[0]), 11u);
}

TEST(RunSelectInputs, AMissingSampleTakesTheNewestWithACounterNotAfterTheWantedOne) {
  Rig rig;
  rig.Sample(10, 1000, 10);
  rig.Sample(12, 3000, 30);  // 11 was never made
  rig.RecordRefSync(100, 11);
  const Selection selection = rig.Run(100);
  const InputSelection& objects = selection.inputs[0];
  ASSERT_TRUE(objects.sample.has_value());
  EXPECT_EQ(CounterOf(objects), 10u);  // not 12: it was made after the one wanted
  EXPECT_TRUE(objects.fallback);
  EXPECT_FALSE(objects.beyond_gap);
  EXPECT_EQ(objects.gap.value(), 1);
}

TEST(RunSelectInputs, BeyondTheMaximumGapTheTimeRulePicksAndTheNumbersAreKept) {
  Rig rig;
  rig.Sample(10, 1000, 10);
  rig.Sample(11, 2000, 20);
  rig.RecordRefSync(100, 30);  // gap 19 from the newest not after it
  const Selection selection = rig.Run(100, /*control_us=*/1500);
  const InputSelection& objects = selection.inputs[0];
  EXPECT_TRUE(objects.beyond_gap);
  EXPECT_TRUE(objects.fallback);
  EXPECT_EQ(objects.wanted.value(), 30);
  EXPECT_EQ(objects.found.value(), 11);
  EXPECT_EQ(objects.gap.value(), 19);
  EXPECT_EQ(CounterOf(objects), 10u);  // the time rule: made at 1000 us, not 2000
}

TEST(RunSelectInputs, NoSampleWithACounterNotAfterTheWantedOneGivesAnEmptyInputAndABadge) {
  Rig rig;
  rig.Sample(50, 1000, 10);
  rig.RecordRefSync(100, 20);
  const Selection selection = rig.Run(100);
  EXPECT_FALSE(selection.inputs[0].sample.has_value());
  EXPECT_TRUE(selection.inputs[0].fallback);
}

TEST(RunSelectInputs, TheCounterFallbackWorksAcrossAWrapOfTheCounter) {
  Rig rig;
  rig.Sample(0xFFFFFFFEu, 1000, 10);
  rig.Sample(0xFFFFFFFFu, 2000, 20);
  rig.RecordRefSync(100, 2);  // 1 never made: the distance from 0xFFFFFFFF to 2 is 2 (`D24`)
  const Selection selection = rig.Run(100);
  const InputSelection& objects = selection.inputs[0];
  ASSERT_TRUE(objects.sample.has_value());
  EXPECT_EQ(CounterOf(objects), 0xFFFFFFFFu);
  EXPECT_EQ(objects.gap.value(), 2);
}

// `IMP-0056` (`D24`): 0xFFFFFFFF -> 1 is one step in the fallback's gap too, so
// from 0xFFFFFFFE the wanted 2 is a gap of 3, within a maximum of 3, beyond 2.
TEST(RunSelectInputs, TheFallbackGapCountsTheWrapAsOneStepAgainstTheMaximum) {
  for (const std::int64_t maximum : {3, 2}) {
    Rig rig;
    rig.Sample(0xFFFFFFFEu, 1000, 10);
    rig.Sample(3, 2000, 20);  // made after the wanted one
    rig.RecordRefSync(100, 2);
    SelectContext context;
    context.spec = &rig.spec;
    context.stage = &rig.spec.stages[1];
    context.bus = &rig.bus;
    context.reference = &rig.reference;
    context.fallback_max_gap = maximum;
    context.now_ns = 1'000'000;
    context.step = 5;
    orchestrator::Ticket ticket;
    ticket.stage = "B";
    orchestrator::ControlHeader header;
    header.measurement_counter = 100;
    const InputSelection& objects = SelectInputs(context, ticket, header).inputs[0];
    EXPECT_TRUE(objects.fallback);
    EXPECT_EQ(objects.found.value(), static_cast<std::int64_t>(0xFFFFFFFEu)) << maximum;
    EXPECT_EQ(objects.gap.value(), 3) << maximum;
    EXPECT_EQ(objects.beyond_gap, maximum == 2) << maximum;
  }
}

TEST(RunSelectInputs, ASimulatedProducersMissingSampleMakesTheTicketWaitUntilTheLimitPasses) {
  Rig rig("simulate");
  rig.Sample(10, 1000, 10, /*committed_step=*/3);
  rig.RecordRefSync(100, 11);
  const Selection waiting = rig.Run(100);
  EXPECT_TRUE(waiting.not_ready);
  EXPECT_EQ(waiting.waiting_on, "A.out");

  const Selection expired = rig.Run(100, 0, 1'000'000, /*expired=*/true);
  EXPECT_FALSE(expired.not_ready);
  EXPECT_TRUE(expired.inputs[0].readiness_timeout);  // KIND_READINESS_TIMEOUT, then ...
  EXPECT_TRUE(expired.inputs[0].fallback);           // ... KIND_FALLBACK too
  EXPECT_EQ(CounterOf(expired.inputs[0]), 10u);
}

TEST(RunSelectInputs, ARecordedProducerNeverMakesATicketWaitItIsReadAheadInstead) {
  Rig rig;  // measured
  rig.Sample(10, 1000, 10);
  rig.RecordRefSync(100, 11);
  VectorReader reader({Message("/A/out", 2'000'000, Data(11, 1500))}, {});
  ReadAhead ahead({&reader});
  ahead.Fill(4);
  const Selection selection = rig.Run(100, 0, 1'000'000, false, 5, &ahead);
  EXPECT_FALSE(selection.not_ready);
  ASSERT_TRUE(selection.inputs[0].sample.has_value());
  EXPECT_EQ(CounterOf(selection.inputs[0]), 11u);  // logged by the car after the control that names it
  EXPECT_FALSE(selection.inputs[0].fallback);
}

TEST(RunSelectInputs, ThePreviousCycleInputSeesOnlySamplesCommittedInAnEarlierStep) {
  Rig rig("simulate", /*previous_cycle=*/true);
  rig.Sample(4, 1000, 10, /*committed_step=*/4);
  rig.Sample(5, 2000, 20, /*committed_step=*/5);  // made by the producer in THIS step (5)
  rig.RecordRefSync(100, 5);
  EXPECT_TRUE(rig.Run(100, 0, 1'000'000, false, /*step=*/5).not_ready);
  const Selection later = rig.Run(100, 0, 1'000'000, false, /*step=*/6);
  EXPECT_FALSE(later.not_ready);
  EXPECT_EQ(CounterOf(later.inputs[0]), 5u);
}

TEST(RunSelectInputs, ASampleEvictedFromAShallowBufferIsReportedAsAnEvictionMiss) {
  Rig rig("measured", false, /*depth=*/2);
  for (std::uint32_t c = 10; c < 14; ++c) rig.Sample(c, c * 100, c);
  rig.RecordRefSync(100, 10);  // older than anything the buffer still holds
  const Selection selection = rig.Run(100);
  EXPECT_TRUE(selection.inputs[0].eviction_miss);
  EXPECT_FALSE(selection.inputs[0].sample.has_value());  // nothing at or before 10 is held
  EXPECT_TRUE(selection.inputs[0].fallback);
}

TEST(RunSelectInputs, AnOffProducerGivesAnEmptyInputIndistinguishableFromAnUnmappedOne) {
  Rig rig("off");
  // An off stage declares no port on the bus.
  bus::PortBus empty;
  rig.bus = std::move(empty);
  const Selection selection = rig.Run(100);
  EXPECT_TRUE(selection.inputs[0].offered);
  EXPECT_FALSE(selection.inputs[0].sample.has_value());
  EXPECT_FALSE(selection.inputs[0].fallback);
}

// `ARCH §6`'s table: "not in the recording, evicted, or never made" gives KIND_FALLBACK. A named sample of a
// simulate producer that the buffer reports evicted was committed and is gone, so waiting cannot help.
TEST(RunSelectInputs, ASimulatedProducersEvictedSampleIsAFallbackAtOnceAndOnlyANotYetCommittedOneParks) {
  Rig rig("simulate", false, /*depth=*/2);
  for (std::uint32_t c = 10; c < 14; ++c) rig.Sample(c, c * 100, c, /*committed_step=*/c);
  rig.RecordRefSync(100, 10);  // committed, then evicted by 12 and 13
  const Selection evicted = rig.Run(100);
  EXPECT_FALSE(evicted.not_ready);                       // no park
  EXPECT_TRUE(evicted.inputs[0].eviction_miss);
  EXPECT_TRUE(evicted.inputs[0].fallback);               // KIND_FALLBACK in that run
  EXPECT_FALSE(evicted.inputs[0].readiness_timeout);     // it did not wait, so it did not time out

  Rig fresh("simulate", false, /*depth=*/2);
  fresh.Sample(10, 1000, 10, /*committed_step=*/3);
  fresh.RecordRefSync(100, 11);  // newer than anything committed: not made yet
  const Selection not_yet = fresh.Run(100);
  EXPECT_TRUE(not_yet.not_ready);                        // still parks
  EXPECT_FALSE(not_yet.inputs[0].eviction_miss);
}

// `D27`. The refSync is matched by `measurement_counter` and searched to the stage's next recorded control, however
// small the readiness limit is.
TEST(RunSelectInputs, D27ALimitOfZeroStillFindsARefSyncLoggedThreeInstantsAfterItsControl) {
  Rig rig;
  rig.Sample(10, 1000, 10);
  rig.Sample(11, 2000, 20);
  VectorReader reader({Message("/A/out", 110'000'000, Data(12, 3000)), Message("/A/out", 120'000'000, Data(13, 4000)),
                       Message("/B/refSync", 130'000'000, RefSyncOf(100, {{"objects", 11}, {"lone", 0}}))},
                      {});
  ReadAhead ahead({&reader});
  ahead.Fill(1);  // readiness_limit_steps 0: two instants held, the refSync is the third
  const Selection selection = rig.Run(100, 0, 1'000'000, false, 5, &ahead, /*control_recorded=*/true);
  EXPECT_FALSE(selection.not_ready);
  ASSERT_TRUE(selection.inputs[0].sample.has_value());
  EXPECT_EQ(CounterOf(selection.inputs[0]), 11u);  // the refSync's entry was used
  EXPECT_FALSE(selection.inputs[0].fallback);
}

TEST(RunSelectInputs, D27ARefSyncLoggedAfterTheNextControlIsNeverHandedToTheEarlierRun) {
  // Run 100 overran: its refSync is logged after control 101, the next run's.
  const auto messages = [] {
    return std::vector<io::RawMessage>{
        Message("/B/control", 110'000'000, Data(101, 2000)),
        Message("/B/refSync", 120'000'000, RefSyncOf(100, {{"objects", 10}, {"lone", 0}})),
        Message("/B/refSync", 125'000'000, RefSyncOf(101, {{"objects", 11}, {"lone", 0}}))};
  };
  Rig first;
  first.Sample(10, 1000, 10);
  first.Sample(11, 2000, 2'000'000);  // arrives after the time the run is decided at
  VectorReader reader_a(messages(), {});
  ReadAhead ahead_a({&reader_a});
  ahead_a.Fill(1);
  const Selection run_k = first.Run(100, 0, 1'000'000, false, 5, &ahead_a, /*control_recorded=*/true);
  ASSERT_TRUE(run_k.inputs[0].sample.has_value());
  EXPECT_TRUE(run_k.inputs[0].fallback);  // the time rule, KIND_FALLBACK: run k has no refSync
  EXPECT_EQ(CounterOf(run_k.inputs[0]), 10u);  // the newest arrived, not record 101's 11

  Rig second;
  second.Sample(10, 1000, 10);
  second.Sample(11, 2000, 20);
  VectorReader reader_b(messages(), {});
  ReadAhead ahead_b({&reader_b});
  ahead_b.Fill(1);
  const Selection run_k1 = second.Run(101, 0, 1'000'000, false, 5, &ahead_b, /*control_recorded=*/true);
  ASSERT_TRUE(run_k1.inputs[0].sample.has_value());
  EXPECT_FALSE(run_k1.inputs[0].fallback);  // run k+1 takes its own refSync
  EXPECT_EQ(CounterOf(run_k1.inputs[0]), 11u);
}

TEST(RunSelectInputs, D27AStageTheRecordingHoldsNoControlOfIsSearchedOnlyToTheReadinessLimit) {
  const auto messages = [] {
    return std::vector<io::RawMessage>{
        Message("/A/out", 110'000'000, Data(12, 3000)), Message("/A/out", 120'000'000, Data(13, 4000)),
        Message("/A/out", 130'000'000, Data(14, 5000)), Message("/A/out", 140'000'000, Data(15, 6000)),
        Message("/B/refSync", 150'000'000, RefSyncOf(100, {{"objects", 11}, {"lone", 0}}))};
  };
  Rig no_control;
  no_control.Sample(10, 1000, 10);
  no_control.Sample(11, 2000, 20);
  VectorReader reader_a(messages(), {});
  ReadAhead ahead_a({&reader_a});
  ahead_a.Fill(2);  // readiness_limit_steps 1: three instants held, the refSync is the fifth
  const Selection stopped = no_control.Run(100, 0, 1'000'000, false, 5, &ahead_a, /*control_recorded=*/false);
  EXPECT_TRUE(stopped.inputs[0].fallback);  // not found by the limit: the time rule

  Rig with_control;
  with_control.Sample(10, 1000, 10);
  with_control.Sample(11, 2000, 20);
  VectorReader reader_b(messages(), {});
  ReadAhead ahead_b({&reader_b});
  ahead_b.Fill(2);
  const Selection found = with_control.Run(100, 0, 1'000'000, false, 5, &ahead_b, /*control_recorded=*/true);
  EXPECT_FALSE(found.inputs[0].fallback);  // the same ahead, a stage with a recorded control: searched on
}

// `IMP-0065` (`D29 (3)`): run 100 of `B` was held behind an earlier parked run of the stage and dispatches only after its
// refSync (logged at `refsync_ns`) and the next control (101, logged at 200) both arrived. `A.out` holds 10 and 11, the
// refSync names 10; a refSync taken wrongly hands over 10, the time rule (control time 0: newest arrived) hands over 11.
Selection RunHeldBehindAParkedRun(std::int64_t refsync_ns, std::int64_t control_depth = 8) {
  Rig rig;
  rig.bus.DeclarePort("B.control", control_depth, DataType());
  const auto control = [&](std::uint32_t counter, std::int64_t arrival_ns) {
    rig.controls.push_back({counter, arrival_ns});
    bus::PortValue value;
    value.origin = bus::Origin::Measured;
    value.payload = Data(counter, 0);
    bus::PublishInfo info;
    EXPECT_TRUE(rig.bus.Publish("B.control", std::move(value), arrival_ns, info).ok());
  };
  rig.Sample(10, 1000, 10);
  rig.Sample(11, 2000, 20);
  control(100, 100);
  control(101, 200);
  rig.reference.Add("B.refSync", refsync_ns, RefSyncOf(100, {{"objects", 10}, {"lone", 0}}));
  return rig.Run(100, /*control_us=*/0, /*now_ns=*/1'000'000, /*expired=*/false, /*step=*/5, /*ahead=*/nullptr,
                 /*control_recorded=*/true);
}

TEST(RunSelectInputs, IMP_0065_ARefSyncReceivedAfterTheStagesNextControlIsNeverMatchedTheTimeRulePicks) {
  const Selection selection = RunHeldBehindAParkedRun(/*refsync_ns=*/300);  // after control 101 (200)
  const InputSelection& objects = selection.inputs[0];
  ASSERT_TRUE(objects.sample.has_value());
  EXPECT_TRUE(objects.fallback);
  EXPECT_EQ(CounterOf(objects), 11u);  // the time rule, not the sample the late refSync names
}

TEST(RunSelectInputs, IMP_0065_ARefSyncReceivedBeforeTheStagesNextControlIsMatched) {
  const Selection selection = RunHeldBehindAParkedRun(/*refsync_ns=*/150);  // before control 101 (200)
  const InputSelection& objects = selection.inputs[0];
  ASSERT_TRUE(objects.sample.has_value());
  EXPECT_FALSE(objects.fallback);
  EXPECT_EQ(CounterOf(objects), 10u);
}

// The same two cases at `buffer_depth` 1: control 100 is evicted from `B.control` by control 101 (`SYT-RUN-06`), and the
// bound must hold all the same.
TEST(RunSelectInputs, IMP_0065_AtControlDepthOneARefSyncReceivedAfterTheNextControlIsNeverMatched) {
  const Selection selection = RunHeldBehindAParkedRun(/*refsync_ns=*/300, /*control_depth=*/1);
  const InputSelection& objects = selection.inputs[0];
  ASSERT_TRUE(objects.sample.has_value());
  EXPECT_TRUE(objects.fallback);
  EXPECT_EQ(CounterOf(objects), 11u);
}

TEST(RunSelectInputs, IMP_0065_AtControlDepthOneARefSyncReceivedAtTheNextControlsInstantIsMatched) {
  const Selection selection = RunHeldBehindAParkedRun(/*refsync_ns=*/200, /*control_depth=*/1);  // control 101 is at 200
  const InputSelection& objects = selection.inputs[0];
  ASSERT_TRUE(objects.sample.has_value());
  EXPECT_FALSE(objects.fallback);
  EXPECT_EQ(CounterOf(objects), 10u);
}

}  // namespace
}  // namespace simcore::runner
