// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `Runner::Preflight`, `Construct`, `StepOnce` and `Seek` (`IMP-0028`..
///   `IMP-0030`, `WP-05`) over a real component and real contract messages:
///   a control-started stage whose input is picked by the recorded refSync
///   (not the newest sample), the control written to the recording, an output
///   that does not copy the control's counter in the event log and its file,
///   the divergence latched by step, the step tap's values and badges, a
///   clock-started stage with no refSync (KIND_FALLBACK), two files as one
///   recording, a slice, a jump, and the load-time refusals. The system tests
///   `SYT-RUN-*`, `SYT-ORC-*`, `SYT-SEL-*` and `SYT-STP-*` run over a lab case
///   in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>

#include <google/protobuf/descriptor.h>

#include "common/cycle_control.pb.h"
#include "run_fixtures.hpp"
#include "simcore/runner.hpp"

namespace simcore::runner {
namespace {

using testing::CapturingWriter;
using testing::Data;
using testing::Message;
using testing::RefSyncOf;
using testing::Topic;
using testing::VectorReader;

constexpr std::int64_t kMs = 1'000'000;

class EnvGuard {
 public:
  EnvGuard(const char* name, const std::string& value) : name_(name) {
#if defined(_WIN32)
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
  }
  ~EnvGuard() {
#if defined(_WIN32)
    _putenv_s(name_, "");
#else
    unsetenv(name_);
#endif
  }

 private:
  const char* name_;
};

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

// The real generic ABI: input `in` is copied to output `out`.
class Echo {
 public:
  Echo()
      : name_("ADAS_SIL_TEST_STUB_NAME", "step_stub"),
        out_("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "out"),
        in_("ADAS_SIL_TEST_STUB_INPUT_PORT", "in") {
    auto loaded = module_host::Component::Load(EchoStubPath());
    if (loaded.ok()) {
      component_.emplace(std::move(loaded).value());
      (void)component_->Init();
    }
  }
  bool ok() const { return component_.has_value(); }
  module_host::Component* get() { return &*component_; }

 private:
  EnvGuard name_;
  EnvGuard out_;
  EnvGuard in_;
  std::optional<module_host::Component> component_;
};

SpecPort Port(const std::string& name, const std::string& dir, const std::string& type = "adas.common.CycleControl") {
  SpecPort port;
  port.name = name;
  port.dir = dir;
  port.kind = "data";
  port.proto_type = type;
  port.record = "full";
  port.buffer_depth = 8;
  return port;
}

// `A` (measured) makes `out`; `B` (simulate, control-started) reads it as `in` and makes `out`.
RunSpec ControlSpec() {
  RunSpec spec;
  spec.run_id = "step-test";
  spec.readiness_limit_steps = 2;
  spec.fallback_max_gap = 4;
  SpecStage a;
  a.name = "A";
  a.mode = "measured";
  a.ports = {Port("out", "pro")};
  SpecStage b;
  b.name = "B";
  b.mode = "simulate";
  b.trigger = "control";
  b.ports = {Port("control", "req"), Port("in", "req"), Port("out", "pro"), Port("refSync", "pro", "adas.common.RefSync")};
  SpecInput in;
  in.port = "in";
  in.producer = "A";
  in.producer_port = "out";
  b.inputs = {in};
  spec.stages = {a, b};
  return spec;
}

std::map<std::string, io::TopicInfo> ControlTopics() {
  return {{"/A/out", Topic("adas.common.CycleControl")},
          {"/B/control", Topic("adas.common.CycleControl", io::Provenance::kSimulated)},
          {"/B/refSync", Topic("adas.common.RefSync", io::Provenance::kSimulated)},
          {"/B/out", Topic("adas.common.CycleControl", io::Provenance::kSimulated)}};
}

// Three instants, 100/200/300 ms. The car's controls count 10, 11, 12; its refSync names the `A.out`
// sample 10, 11 and -- the third time -- 11 although 12 has arrived. Its outputs echo what it read,
// except the third, which is 12.
std::vector<io::RawMessage> ControlRecording() {
  std::vector<io::RawMessage> messages;
  const std::uint32_t controls[3] = {10, 11, 12};
  const std::uint32_t named[3] = {10, 11, 11};
  const std::uint32_t recorded_out[3] = {10, 11, 12};
  for (int i = 0; i < 3; ++i) {
    const std::int64_t t = (i + 1) * 100 * kMs;
    messages.push_back(Message("/A/out", t, Data(10 + i, (i + 1) * 100'000)));
    messages.push_back(Message("/B/control", t, Data(controls[i], (i + 1) * 100'000, i + 1)));
    messages.push_back(Message("/B/refSync", t, RefSyncOf(controls[i], {{"in", named[i]}})));
    messages.push_back(Message("/B/out", t, Data(recorded_out[i], (i + 1) * 100'000)));
  }
  return messages;
}

struct Collect final : LiveMeasSink {
  void OnStep(const StepReport& report) override {
    steps.push_back(report.step);
    times.push_back(report.sim_time_ns);
    badges.push_back(report.badges);
    for (const StepValue& value : report.values) {
      if (value.port == "A.out") a_out_origin = value.origin;
    }
  }
  std::vector<std::uint64_t> steps;
  std::vector<std::int64_t> times;
  std::vector<std::vector<StepBadge>> badges;
  bus::Origin a_out_origin = bus::Origin::Unknown;
};

struct Harness {
  explicit Harness(RunSpec s = ControlSpec(), std::vector<io::RawMessage> messages = ControlRecording(),
                   std::map<std::string, io::TopicInfo> topics = ControlTopics())
      : spec(std::move(s)), reader(std::move(messages), std::move(topics)), writer_base(sink) {}

  Result<Runner> Build(const Runner::Options& options = Runner::Options{}, std::vector<io::Reader*> readers = {}) {
    if (readers.empty()) readers = {&reader};
    return Runner::Construct(spec, bus, readers, {{"B", echo.get()}},
                             google::protobuf::DescriptorPool::generated_pool(), &writer_base, nullptr, options);
  }

  std::vector<io::RawMessage> Written(const std::string& topic) const {
    std::vector<io::RawMessage> found;
    for (const io::RawMessage& message : sink.written) {
      if (message.topic == topic) found.push_back(message);
    }
    return found;
  }

  Echo echo;
  RunSpec spec;
  VectorReader reader;
  bus::PortBus bus;
  CapturingWriter sink;
  io::WriterBase writer_base;
};

adas::common::CycleControl Parse(const io::RawMessage& message) {
  adas::common::CycleControl parsed;
  EXPECT_TRUE(parsed.ParseFromArray(message.payload.data(), static_cast<int>(message.payload.size())));
  return parsed;
}

std::uint32_t CounterOf(const io::RawMessage& message) { return Parse(message).sig_header().measurement_counter(); }

TEST(RunStep, EachInstantIsOneStepAndTheInputIsTheSampleTheRefSyncNamesNotTheNewest) {
  Harness h;
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  const auto outcome = runner.Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();
  EXPECT_EQ(outcome.value().cycles_executed, 3u);

  const std::vector<io::RawMessage> out = h.Written("/B/out");
  ASSERT_EQ(out.size(), 3u);
  EXPECT_EQ(CounterOf(out[0]), 10u);
  EXPECT_EQ(CounterOf(out[1]), 11u);
  EXPECT_EQ(CounterOf(out[2]), 11u);  // the refSync names 11 although 12 had arrived; a "newest sample" version gives 12
  EXPECT_EQ(out[2].log_time_ns, 300 * kMs);
}

TEST(RunStep, TheControlWrittenForEachRunIsRecordedWithTheTriggersCounterAndTheStagesOwnCount) {
  Harness h;
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  ASSERT_TRUE(std::move(built).value().Run().ok());
  const std::vector<io::RawMessage> controls = h.Written("/B/control");
  ASSERT_EQ(controls.size(), 3u);
  for (int i = 0; i < 3; ++i) {
    const adas::common::CycleControl control = Parse(controls[i]);
    EXPECT_EQ(control.sig_header().measurement_counter(), 10u + i);
    EXPECT_EQ(control.sig_header().cycle_counter(), static_cast<std::uint32_t>(i + 1));
    EXPECT_EQ(control.sig_header().sig_status(), 1u);
    EXPECT_EQ(control.op_mode(), i == 0 ? adas::common::CycleControl::RESTART : adas::common::CycleControl::RUN);
  }
}

TEST(RunStep, AnOutputThatDoesNotCopyTheControlsCounterIsInTheEventLogAndItsFile) {
  Harness h;
  ASSERT_TRUE(h.echo.ok());
  const std::filesystem::path dir = std::filesystem::temp_directory_path() / "vantage_run_step_events";
  std::filesystem::create_directories(dir);
  h.spec.outputs.path = (dir / "engine_run.mcap").string();
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  ASSERT_TRUE(runner.Run().ok());

  ASSERT_EQ(runner.EventLogLines().size(), 1u);
  EXPECT_EQ(runner.EventLogLines()[0],
            "event=degrade step=2 entry=output_counter_break stage=B port=out wanted=12 found=11");
  std::ifstream file(dir / "engine_run.events.log");
  ASSERT_TRUE(file.good());
  std::stringstream content;
  content << file.rdbuf();
  EXPECT_EQ(content.str(), runner.EventLogLines()[0] + "\n");
}

TEST(RunStep, TheFirstDivergenceIsTheFirstStepWhoseOutputDiffersFromTheRecordedOne) {
  Harness h;
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  ASSERT_TRUE(runner.Run().ok());
  ASSERT_TRUE(runner.FirstDivergence().has_value());
  EXPECT_EQ(runner.FirstDivergence()->tick_index, 2u);  // the step number
  EXPECT_EQ(runner.FirstDivergence()->stage, "B");
  EXPECT_EQ(runner.FirstDivergence()->port, "out");
}

TEST(RunStep, TheStepTapGetsEachStepsNumberTimeValuesAndNoBadgeForAMatchedRun) {
  Harness h;
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  Collect tap;
  runner.SetLiveMeasurement(&tap);
  ASSERT_TRUE(runner.Run().ok());
  EXPECT_EQ(tap.steps, (std::vector<std::uint64_t>{0, 1, 2}));
  EXPECT_EQ(tap.times, (std::vector<std::int64_t>{100 * kMs, 200 * kMs, 300 * kMs}));
  for (const auto& badges : tap.badges) EXPECT_TRUE(badges.empty());
  EXPECT_EQ(tap.a_out_origin, bus::Origin::Measured);
}

TEST(RunStep, AStageWithNoRecordedRefSyncRaisesKindFallbackOnEveryInputEveryRun) {
  RunSpec spec = ControlSpec();
  spec.stages[1].trigger.clear();
  spec.stages[1].clock_period_ns = 100 * kMs;
  std::vector<io::RawMessage> messages;
  for (int i = 0; i < 3; ++i) messages.push_back(Message("/A/out", i * 100 * kMs, Data(10 + i, i * 100'000 + 1)));
  Harness h(spec, messages, {{"/A/out", Topic("adas.common.CycleControl")}});
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  Collect tap;
  runner.SetLiveMeasurement(&tap);
  ASSERT_TRUE(runner.Run().ok());
  ASSERT_EQ(tap.steps.size(), 3u);
  for (std::size_t i = 0; i < 3; ++i) {
    ASSERT_EQ(tap.badges[i].size(), 1u);
    EXPECT_EQ(tap.badges[i][0].kind, BadgeKind::kFallback);
    EXPECT_EQ(tap.badges[i][0].subject, "B.in");
    EXPECT_EQ(tap.badges[i][0].count, i + 1);  // counted since the engine run started
  }
  // The clock numbers the runs from 1 on the recording's first instant.
  const std::vector<io::RawMessage> controls = h.Written("/B/control");
  ASSERT_EQ(controls.size(), 3u);
  EXPECT_EQ(Parse(controls[2]).sig_header().measurement_counter(), 3u);
}

TEST(RunStep, TwoFilesInSourcesOrderAreOneRecording) {
  Harness one;
  ASSERT_TRUE(one.echo.ok());
  auto built_one = one.Build();
  ASSERT_TRUE(built_one.ok()) << built_one.error().Format();
  ASSERT_TRUE(std::move(built_one).value().Run().ok());

  Harness two;
  std::vector<io::RawMessage> source_side;
  std::vector<io::RawMessage> rest;
  for (const io::RawMessage& message : ControlRecording()) (message.topic == "/A/out" ? source_side : rest).push_back(message);
  VectorReader first(source_side, {{"/A/out", Topic("adas.common.CycleControl")}});
  VectorReader second(rest, {{"/B/control", Topic("adas.common.CycleControl", io::Provenance::kSimulated)},
                             {"/B/refSync", Topic("adas.common.RefSync", io::Provenance::kSimulated)},
                             {"/B/out", Topic("adas.common.CycleControl", io::Provenance::kSimulated)}});
  auto built_two = two.Build(Runner::Options{}, {&first, &second});
  ASSERT_TRUE(built_two.ok()) << built_two.error().Format();
  ASSERT_TRUE(std::move(built_two).value().Run().ok());

  ASSERT_EQ(one.sink.written.size(), two.sink.written.size());
  for (std::size_t i = 0; i < one.sink.written.size(); ++i) {
    EXPECT_EQ(one.sink.written[i].topic, two.sink.written[i].topic);
    EXPECT_EQ(one.sink.written[i].payload, two.sink.written[i].payload);
  }
}

TEST(RunStep, ASliceStartsWithARestartAndStopsBeforeItsEnd) {
  Harness h;
  ASSERT_TRUE(h.echo.ok());
  Runner::Options options;
  options.slice.start_log_time_ns = 200 * kMs;
  options.slice.end_log_time_ns = 300 * kMs;  // exclusive
  auto built = h.Build(options);
  ASSERT_TRUE(built.ok()) << built.error().Format();
  const auto outcome = std::move(built).value().Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();
  EXPECT_EQ(outcome.value().cycles_executed, 1u);
  const std::vector<io::RawMessage> controls = h.Written("/B/control");
  ASSERT_EQ(controls.size(), 1u);
  EXPECT_EQ(Parse(controls[0]).op_mode(), adas::common::CycleControl::RESTART);  // the first run after the start is a restart
  EXPECT_EQ(Parse(controls[0]).sig_header().measurement_counter(), 11u);
}

TEST(RunStep, AJumpMovesTheEngineKeepsTheStepNumbersAndRestartsTheNextRun) {
  Harness h;
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  Collect tap;
  runner.SetLiveMeasurement(&tap);
  ASSERT_TRUE(runner.StepOnce().value());  // 100 ms, step 0
  ASSERT_TRUE(runner.Seek(300 * kMs).ok());
  ASSERT_TRUE(runner.StepOnce().value());  // 300 ms: the 200 ms instant is skipped
  EXPECT_FALSE(runner.StepOnce().value());
  EXPECT_EQ(tap.steps, (std::vector<std::uint64_t>{0, 1}));  // the step number continues
  EXPECT_EQ(tap.times, (std::vector<std::int64_t>{100 * kMs, 300 * kMs}));
  const std::vector<io::RawMessage> controls = h.Written("/B/control");
  ASSERT_EQ(controls.size(), 2u);
  EXPECT_EQ(Parse(controls[1]).op_mode(), adas::common::CycleControl::RESTART);
  EXPECT_EQ(Parse(controls[1]).sig_header().measurement_counter(), 12u);
  // The recorded sample the refSync of the 300 ms run names (11, logged at 200 ms) is gone with the jump.
  ASSERT_EQ(tap.badges.size(), 2u);
  EXPECT_TRUE(tap.badges[1].empty() == false);
  EXPECT_EQ(tap.badges[1][0].kind, BadgeKind::kFallback);
}

TEST(RunStep, PreflightRefusesAMeasuredStageWhoseOutputsTheRecordingLacksNamingStageAndPorts) {
  RunSpec spec = ControlSpec();
  spec.stages[0].ports.push_back(Port("extra", "pro"));
  const auto result = Runner::Preflight(spec, {"/A/out", "/B/control"});
  ASSERT_FALSE(result.ok());
  EXPECT_EQ(result.error().kind, Kind::Authoring);
  EXPECT_NE(result.error().found.find("'A'"), std::string::npos);
  EXPECT_NE(result.error().found.find("extra"), std::string::npos);
  EXPECT_EQ(result.error().found.find("out,"), std::string::npos);  // `out` is there: not named
}

TEST(RunStep, PreflightGivesThePlanFromTheSetupAndTheTopicIndexAlone) {
  const auto result = Runner::Preflight(ControlSpec(), {"/A/out", "/B/control"});
  ASSERT_TRUE(result.ok()) << result.error().Format();
  EXPECT_NE(result.value().plan_text.find("B"), std::string::npos);
  ASSERT_EQ(result.value().graph.stages.size(), 1u);
  EXPECT_EQ(result.value().graph.stages[0].start, orchestrator::StartKind::kControl);
  // A control start with no recorded control is refused at load.
  EXPECT_FALSE(Runner::Preflight(ControlSpec(), {"/A/out"}).ok());
}

TEST(RunStep, ConstructPrintsThePlanBeforeTheFirstStepWhenAskedTo) {
  Harness h;
  ASSERT_TRUE(h.echo.ok());
  std::ostringstream plan;
  Runner::Options options;
  options.plan_out = &plan;
  auto built = h.Build(options);
  ASSERT_TRUE(built.ok()) << built.error().Format();
  EXPECT_FALSE(plan.str().empty());
  EXPECT_EQ(plan.str(), Runner::Preflight(h.spec, {"/A/out", "/B/control", "/B/refSync", "/B/out"}).value().plan_text);
}

TEST(RunStep, ASimulatedStageNobodySimulatedConsumesIsBadgedOnceFromTheFirstStep) {
  RunSpec spec = ControlSpec();
  SpecStage c;
  c.name = "C";
  c.mode = "measured";
  c.ports = {Port("req_in", "req"), Port("out", "pro")};
  SpecInput from_b;
  from_b.port = "req_in";
  from_b.producer = "B";
  from_b.producer_port = "out";
  c.inputs = {from_b};
  spec.stages.push_back(c);
  auto topics = ControlTopics();
  topics["/C/out"] = Topic("adas.common.CycleControl");
  Harness h(spec, ControlRecording(), topics);
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  Collect tap;
  runner.SetLiveMeasurement(&tap);
  ASSERT_TRUE(runner.Run().ok());
  ASSERT_FALSE(tap.badges.empty());
  bool seen_each_step = true;
  for (const auto& badges : tap.badges) {
    bool found = false;
    for (const StepBadge& badge : badges) {
      if (badge.kind == BadgeKind::kComputedNotConsumed && badge.subject == "B" && badge.count == 1) found = true;
    }
    seen_each_step = seen_each_step && found;
  }
  EXPECT_TRUE(seen_each_step);
}

}  // namespace
}  // namespace simcore::runner
