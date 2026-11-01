// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `RunStage` (`IMP-0027`, `WP-05`; serves `SYS-0012`, `SYS-0013`,
///   `SYS-0021`, `SYS-0027`): the port set built from the control and the
///   selection (an input with no sample handed over empty and invalid, an
///   unwired input not offered), the exact bytes recorded as delivered, an
///   output whose `measurement_counter` differs from the control's logged,
///   and no retry after a failed call. The exec call is a function the test
///   supplies, so real protobuf bytes run with no library. The system tests
///   `SYT-ORC-04`, `SYT-ORC-05` and `SYT-SEL-02` run over a lab case in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "common/cycle_control.pb.h"
#include "run_fixtures.hpp"
#include "simcore/runner.hpp"

namespace simcore::runner {
namespace {

using testing::Data;

const google::protobuf::Descriptor* DataType() { return adas::common::CycleControl::descriptor(); }

struct Rig {
  Rig() {
    stage.name = "B";
    stage.mode = "simulate";
    bus.DeclarePort("B.outputs", 4, DataType());
    bus.DeclarePort("B.noheader", 4, nullptr);
    ticket.id = 7;
    ticket.stage = "B";
    ticket.start = orchestrator::StartKind::kClock;
  }

  InputSelection Input(const std::string& port, std::optional<std::vector<std::uint8_t>> payload,
                       bool offered = true) {
    InputSelection input;
    input.port = port;
    input.offered = offered;
    input.producer_port = "A." + port;
    if (payload.has_value()) {
      bus::Sample sample;
      sample.arrival_ns = 400'000;
      sample.value.origin = bus::Origin::Measured;
      sample.value.payload = *payload;
      input.sample = sample;
    }
    return input;
  }

  Result<RunStageResult> Run(const ExecFn& exec, std::optional<std::uint32_t> control_counter = 5,
                             std::vector<std::uint8_t> control = {9, 9}) {
    RunStageArgs args;
    args.stage = &stage;
    args.ticket = &ticket;
    args.selection = &selection;
    args.control = std::move(control);
    args.bus = &bus;
    args.now_ns = 500'000;
    args.dt_ns = 10'000'000;
    args.control_counter = control_counter;
    return RunStage(args, exec);
  }

  SpecStage stage;
  orchestrator::Ticket ticket;
  Selection selection;
  bus::PortBus bus;
};

TEST(RunStage, ThePortSetHoldsTheControlAndEveryOfferedInputAndNothingElse) {
  Rig rig;
  rig.selection.inputs = {rig.Input("objects", Data(3)), rig.Input("empty", std::nullopt),
                          rig.Input("lone", std::nullopt, /*offered=*/false)};
  module_host::PortMap seen;
  module_host::InputMetaMap seen_meta;
  std::int64_t seen_dt = 0;
  const ExecFn exec = [&](std::int64_t dt_ns, const module_host::PortMap& inputs,
                          const module_host::InputMetaMap& meta) -> Result<module_host::PortMap> {
    seen = inputs;
    seen_meta = meta;
    seen_dt = dt_ns;
    return Result<module_host::PortMap>::Ok(module_host::PortMap{});
  };
  const Result<RunStageResult> ran = rig.Run(exec);
  ASSERT_TRUE(ran.ok()) << ran.error().Format();
  EXPECT_EQ(seen_dt, 10'000'000);
  ASSERT_EQ(seen.size(), 3u);  // control, objects, empty -- not `lone`
  EXPECT_EQ(seen.at("objects"), Data(3));
  EXPECT_EQ(seen.at("control"), (std::vector<std::uint8_t>{9, 9}));
  EXPECT_TRUE(seen.at("empty").empty());
  EXPECT_TRUE(seen_meta.at("objects").valid);
  EXPECT_NEAR(seen_meta.at("objects").age_s, 0.0001, 1e-9);  // 100 us since it arrived
  EXPECT_FALSE(seen_meta.at("empty").valid);  // an empty input is invalid, never a default value
  EXPECT_EQ(seen.count("lone"), 0u);
}

TEST(RunStage, TheDeliveredMapHoldsExactlyTheBytesHandedOverUnderTheConsumingNames) {
  Rig rig;
  rig.selection.inputs = {rig.Input("objects", Data(3)), rig.Input("empty", std::nullopt)};
  const ExecFn exec = [](std::int64_t, const module_host::PortMap&, const module_host::InputMetaMap&) {
    return Result<module_host::PortMap>::Ok(module_host::PortMap{});
  };
  const Result<RunStageResult> ran = rig.Run(exec);
  ASSERT_TRUE(ran.ok());
  const auto& delivered = ran.value().delivered;
  ASSERT_EQ(delivered.size(), 3u);
  EXPECT_EQ(delivered.at("B.objects").payload, Data(3));
  EXPECT_EQ(delivered.at("B.control").payload, (std::vector<std::uint8_t>{9, 9}));
  EXPECT_TRUE(delivered.at("B.empty").payload.empty());
}

TEST(RunStage, AStageThatDeclaresNoControlIsHandedNone) {
  Rig rig;
  rig.selection.inputs = {rig.Input("objects", Data(3))};
  module_host::PortMap seen;
  const ExecFn exec = [&](std::int64_t, const module_host::PortMap& inputs, const module_host::InputMetaMap&) {
    seen = inputs;
    return Result<module_host::PortMap>::Ok(module_host::PortMap{});
  };
  ASSERT_TRUE(rig.Run(exec, 5, /*control=*/{}).ok());
  EXPECT_EQ(seen.count("control"), 0u);
}

TEST(RunStage, AnOutputThatDoesNotCopyTheControlsCounterIsLoggedAndOneThatDoesIsNot) {
  Rig rig;
  const ExecFn exec = [](std::int64_t, const module_host::PortMap&, const module_host::InputMetaMap&) {
    module_host::PortMap out;
    out["outputs"] = Data(6);  // the control's is 5: renumbered
    out["noheader"] = {1, 2, 3};  // no type, no header: not judged
    return Result<module_host::PortMap>::Ok(out);
  };
  const Result<RunStageResult> ran = rig.Run(exec);
  ASSERT_TRUE(ran.ok());
  ASSERT_EQ(ran.value().report.outputs.size(), 2u);
  ASSERT_EQ(ran.value().entries.size(), 1u);
  const orchestrator::LogEntry& entry = ran.value().entries[0];
  EXPECT_EQ(entry.kind, orchestrator::EntryKind::kOutputCounterBreak);
  EXPECT_EQ(entry.stage, "B");
  EXPECT_EQ(entry.port, "outputs");
  EXPECT_EQ(entry.wanted.value(), 5);
  EXPECT_EQ(entry.found.value(), 6);

  const ExecFn faithful = [](std::int64_t, const module_host::PortMap&, const module_host::InputMetaMap&) {
    module_host::PortMap out;
    out["outputs"] = Data(5);
    return Result<module_host::PortMap>::Ok(out);
  };
  EXPECT_TRUE(rig.Run(faithful).value().entries.empty());
  EXPECT_TRUE(rig.Run(exec, /*control_counter=*/std::nullopt).value().entries.empty());  // control unknown
}

TEST(RunStage, TheReportNamesTheTicketAndQualifiesEveryOutputPort) {
  Rig rig;
  const ExecFn exec = [](std::int64_t, const module_host::PortMap&, const module_host::InputMetaMap&) {
    module_host::PortMap out;
    out["outputs"] = Data(5);
    return Result<module_host::PortMap>::Ok(out);
  };
  const Result<RunStageResult> ran = rig.Run(exec);
  ASSERT_TRUE(ran.ok());
  EXPECT_EQ(ran.value().report.ticket_id, 7u);
  ASSERT_EQ(ran.value().report.outputs.size(), 1u);
  EXPECT_EQ(ran.value().report.outputs[0].port, "B.outputs");
  EXPECT_EQ(ran.value().report.outputs[0].origin, bus::Origin::Simulated);
}

TEST(RunStage, AFailedCallIsReturnedAsItCameAndIsNeverRetried) {
  Rig rig;
  int calls = 0;
  const ExecFn exec = [&](std::int64_t, const module_host::PortMap&, const module_host::InputMetaMap&) {
    ++calls;
    return Result<module_host::PortMap>::Fail(Error{Kind::Environment, "a return", "a timeout", "adasExec", ""});
  };
  const Result<RunStageResult> ran = rig.Run(exec);
  ASSERT_FALSE(ran.ok());
  EXPECT_EQ(ran.error().kind, Kind::Environment);
  EXPECT_EQ(ran.error().found, "a timeout");
  EXPECT_EQ(calls, 1);
}

}  // namespace
}  // namespace simcore::runner
