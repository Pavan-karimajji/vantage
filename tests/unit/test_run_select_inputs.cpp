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
                bool expired = false, std::uint64_t step = 5, const ReadAhead* ahead = nullptr) {
    SelectContext context;
    context.spec = &spec;
    context.stage = &spec.stages[1];
    context.bus = &bus;
    context.reference = &reference;
    context.ahead = ahead;
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
  rig.RecordRefSync(100, 2);  // 0, 1 never made: distance from 0xFFFFFFFF to 2 is 3
  const Selection selection = rig.Run(100);
  const InputSelection& objects = selection.inputs[0];
  ASSERT_TRUE(objects.sample.has_value());
  EXPECT_EQ(CounterOf(objects), 0xFFFFFFFFu);
  EXPECT_EQ(objects.gap.value(), 3);
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

}  // namespace
}  // namespace simcore::runner
