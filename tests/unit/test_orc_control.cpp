// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `ControlWriter::Write` (`RCT:IMP-0032`, `WP-05`; serves `RCT:SYS-0009`..
///   `SYS-0012`): the header a control takes from what started the run, the
///   stage's own run count, the sticker, and `op_mode` -- RESTART on a first
///   run and after a jump, otherwise the recorded `op_mode` of a recorded
///   control, otherwise RUN. The system tests `SYT-CTL-04`..`SYT-CTL-07` run
///   over a lab case in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "adas/sig_status.hpp"
#include "common/cycle_control.pb.h"
#include "run_fixtures.hpp"
#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {
namespace {

using adas::common::CycleControl;
using testing::Data;

const google::protobuf::Descriptor* DataType() { return CycleControl::descriptor(); }

GraphStage ClockStage(std::int64_t period_ns) {
  GraphStage stage;
  stage.name = "A";
  stage.start = StartKind::kClock;
  stage.clock_period_ns = period_ns;
  return stage;
}

Ticket TicketOf(StartKind start, std::int64_t time_ns, std::vector<std::uint8_t> trigger = {},
                std::uint64_t run_number = 0, bool restart = false) {
  Ticket ticket;
  ticket.stage = "A";
  ticket.start = start;
  ticket.trigger_time_ns = time_ns;
  ticket.trigger_payload = std::move(trigger);
  ticket.run_number = run_number;
  ticket.restart = restart;
  return ticket;
}

CycleControl Parse(const std::vector<std::uint8_t>& bytes) {
  CycleControl control;
  EXPECT_TRUE(control.ParseFromArray(bytes.data(), static_cast<int>(bytes.size())));
  return control;
}

TEST(OrcControl, ARecordedControlGivesItsCounterAndTimeAndNothingElse) {
  const ControlWriter writer(0);
  // The recorded cycle_counter (77) is the car's; ours is the stage's own run count.
  const Ticket ticket = TicketOf(StartKind::kControl, 5'000'000,
                                 Data(/*measurement=*/41, /*source_us=*/4'000, /*cycle=*/77, CycleControl::RUN),
                                 /*run_number=*/6);
  const CycleControl control = Parse(writer.Write(ticket, ClockStage(0), nullptr));
  EXPECT_EQ(control.sig_header().measurement_counter(), 41u);
  EXPECT_EQ(control.sig_header().source_timestamp_us(), 4'000u);
  EXPECT_EQ(control.sig_header().cycle_counter(), 7u);
  EXPECT_EQ(control.sig_header().sig_status(), adas::common::kSigStatusOk);
}

TEST(OrcControl, OpModeIsRestartOnAFirstRunOrAfterAJumpElseTheRecordedOne) {
  const ControlWriter writer(0);
  const GraphStage stage = ClockStage(0);
  // A restart wins over what the recording says.
  const Ticket first = TicketOf(StartKind::kControl, 0, Data(1, 1, 1, CycleControl::RUN), 0, /*restart=*/true);
  EXPECT_EQ(Parse(writer.Write(first, stage, nullptr)).op_mode(), CycleControl::RESTART);
  // A recorded RESTART in mid-run is repeated (RCT:SYS-0011).
  const Ticket recorded_restart = TicketOf(StartKind::kControl, 0, Data(2, 1, 2, CycleControl::RESTART), 1);
  EXPECT_EQ(Parse(writer.Write(recorded_restart, stage, nullptr)).op_mode(), CycleControl::RESTART);
  const Ticket recorded_run = TicketOf(StartKind::kControl, 0, Data(3, 1, 3, CycleControl::RUN), 2);
  EXPECT_EQ(Parse(writer.Write(recorded_run, stage, nullptr)).op_mode(), CycleControl::RUN);
}

TEST(OrcControl, ATriggerSampleGivesItsHeaderAndAStartedRunIsRunUnlessItRestarts) {
  const ControlWriter writer(0);
  GraphStage stage = ClockStage(0);
  stage.start = StartKind::kInput;
  // The trigger sample's own op_mode field means nothing for a data trigger.
  Ticket ticket = TicketOf(StartKind::kInput, 9'000'000, Data(52, 8'500, 3, CycleControl::RESTART), 2);
  const CycleControl control = Parse(writer.Write(ticket, stage, DataType()));
  EXPECT_EQ(control.sig_header().measurement_counter(), 52u);
  EXPECT_EQ(control.sig_header().source_timestamp_us(), 8'500u);
  EXPECT_EQ(control.sig_header().cycle_counter(), 3u);
  EXPECT_EQ(control.op_mode(), CycleControl::RUN);
  ticket.restart = true;
  EXPECT_EQ(Parse(writer.Write(ticket, stage, DataType())).op_mode(), CycleControl::RESTART);
}

TEST(OrcControl, AClockTickIsNumberedFromOneOnTheRecordingsFirstInstantAndCarriesTheTickTime) {
  const ControlWriter writer(/*first_reception_ns=*/2'000'000);
  const GraphStage stage = ClockStage(7'000'000);
  // k = 0 at the first instant, 1 one period later, 3 three periods later.
  EXPECT_EQ(writer.HeaderOf(TicketOf(StartKind::kClock, 2'000'000), stage, nullptr).measurement_counter, 1u);
  const ControlHeader third = writer.HeaderOf(TicketOf(StartKind::kClock, 2'000'000 + 3 * 7'000'000), stage, nullptr);
  EXPECT_EQ(third.measurement_counter, 4u);
  EXPECT_EQ(third.source_timestamp_us, 23'000u);
}

TEST(OrcControl, AnUnknownTriggerHeaderStaysUnknownAndIsNeverFilledFromTheClock) {
  const ControlWriter writer(0);
  GraphStage stage = ClockStage(0);
  stage.start = StartKind::kInput;
  // No descriptor for the trigger's type: its header is unknown, so the control's is 0 (unknown).
  const Ticket ticket = TicketOf(StartKind::kInput, 9'000'000, Data(52, 8'500), 0);
  const ControlHeader header = writer.HeaderOf(ticket, stage, nullptr);
  EXPECT_EQ(header.measurement_counter, 0u);
  EXPECT_EQ(header.source_timestamp_us, 0u);
}

TEST(OrcControl, TheStagesOwnCountRunsFromOneAndOnlyTheRunNumberMovesIt) {
  const ControlWriter writer(0);
  const GraphStage stage = ClockStage(1'000'000);
  for (std::uint64_t run = 0; run < 3; ++run) {
    const Ticket ticket = TicketOf(StartKind::kClock, 4'000'000 * static_cast<std::int64_t>(run + 1), {}, run);
    EXPECT_EQ(Parse(writer.Write(ticket, stage, nullptr)).sig_header().cycle_counter(), run + 1);
  }
}

}  // namespace
}  // namespace simcore::orchestrator
