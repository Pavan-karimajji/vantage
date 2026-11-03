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

// Three instants, 100/200/300 ms (the first control carries RESTART, `IMP-0062`). The car's controls count 10, 11, 12; its refSync names the `A.out`
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
    messages.push_back(Message("/B/control", t, Data(controls[i], (i + 1) * 100'000, i + 1,
                                                            i == 0 ? adas::common::CycleControl::RESTART
                                                                   : adas::common::CycleControl::RUN)));
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

// `IMP-0061`, `SYS-0053`: the step writes each run committed in it, in commit order -- its control, then the outputs it
// committed -- so a stage that runs twice in one step (two controls at one instant) leaves both runs.
TEST(RunStep, AStageThatRunsTwiceInOneStepLeavesBothRunsEachControlBeforeItsOwnOutputs) {
  std::vector<io::RawMessage> messages;
  messages.push_back(Message("/A/out", 100 * kMs, Data(10, 100'000)));
  messages.push_back(Message("/A/out", 100 * kMs, Data(11, 100'000)));
  messages.push_back(Message("/B/control", 100 * kMs, Data(10, 100'000, 1)));
  messages.push_back(Message("/B/control", 100 * kMs, Data(11, 100'000, 2)));
  messages.push_back(Message("/B/refSync", 100 * kMs, RefSyncOf(10, {{"in", 10}})));
  messages.push_back(Message("/B/refSync", 100 * kMs, RefSyncOf(11, {{"in", 11}})));
  Harness h(ControlSpec(), messages, ControlTopics());
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  const auto outcome = std::move(built).value().Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();
  EXPECT_EQ(outcome.value().cycles_executed, 1u);  // both runs are in the one step

  std::vector<std::pair<std::string, std::uint32_t>> seen;
  for (const io::RawMessage& message : h.sink.written) {
    if (message.topic == "/B/control" || message.topic == "/B/out") seen.emplace_back(message.topic, CounterOf(message));
  }
  const std::vector<std::pair<std::string, std::uint32_t>> expected = {
      {"/B/control", 10u}, {"/B/out", 10u}, {"/B/control", 11u}, {"/B/out", 11u}};
  EXPECT_EQ(seen, expected);
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

  // Its output (counter 11) is paired with the recorded output of counter 11, which it equals (`IMP-0033`): the
  // counter break is the only entry.
  ASSERT_EQ(runner.EventLogLines().size(), 1u);
  EXPECT_EQ(runner.EventLogLines()[0],
            "event=degrade step=2 entry=output_counter_break stage=B port=out wanted=12 found=11");
  std::ifstream file(dir / "engine_run.events.log");
  ASSERT_TRUE(file.good());
  std::stringstream content;
  content << file.rdbuf();
  EXPECT_EQ(content.str(), runner.EventLogLines()[0] + "\n");
}

std::vector<io::RawMessage> EchoRecording(const std::uint32_t (&out_source_us)[3], const std::uint32_t (&out_cycle)[3]);

TEST(RunStep, TheFirstDivergenceIsTheFirstStepWhoseOutputDiffersFromTheRecordedOne) {
  Harness h(ControlSpec(), EchoRecording({100'000, 200'000, 1}, {1, 1, 1}));  // only the third recorded output differs
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

// `IMP-0032`, `IMP-0033` (`WP-06`). The car's controls count 10, 11, 12 and its refSync names each instant's own
// `A.out` sample, so `B` echoes 10, 11, 12 with source times 100000, 200000, 300000 us. The recorded `B.out` carries the
// same counters (`IMP-0033` pairs an output with the recorded output of its own counter), the given source times -- a
// time other than the echo's is a difference -- and the given cycle counters.
std::vector<io::RawMessage> EchoRecording(const std::uint32_t (&out_source_us)[3], const std::uint32_t (&out_cycle)[3]) {
  std::vector<io::RawMessage> messages;
  for (int i = 0; i < 3; ++i) {
    const std::int64_t t = (i + 1) * 100 * kMs;
    messages.push_back(Message("/A/out", t, Data(10 + i, (i + 1) * 100'000)));
    messages.push_back(Message("/B/control", t, Data(10 + i, (i + 1) * 100'000, i + 1,
                                                            i == 0 ? adas::common::CycleControl::RESTART
                                                                   : adas::common::CycleControl::RUN)));
    messages.push_back(Message("/B/refSync", t, RefSyncOf(10 + i, {{"in", static_cast<std::uint32_t>(10 + i)}})));
    messages.push_back(Message("/B/out", t, Data(10 + i, out_source_us[i], out_cycle[i])));
  }
  return messages;
}

std::size_t CountDivergenceLines(const Runner& runner) {
  std::size_t count = 0;
  for (const std::string& line : runner.EventLogLines()) {
    if (line.find("entry=first_divergence") != std::string::npos) ++count;
  }
  return count;
}

TEST(RunStep, ARestartRunIsNeverOfferedToTheDivergenceLatch) {
  // Step 0 is the stage's first run, a RESTART run; its output differs from the recorded one, the others do not.
  Harness h(ControlSpec(), EchoRecording({1, 200'000, 300'000}, {1, 1, 1}));
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  ASSERT_TRUE(runner.Run().ok());
  EXPECT_FALSE(runner.FirstDivergence().has_value());
  EXPECT_EQ(CountDivergenceLines(runner), 0u);
}

TEST(RunStep, TheFirstDivergenceIsLoggedOnceAndTheRunStillSucceedsThroughEveryStep) {
  Harness h(ControlSpec(), EchoRecording({100'000, 1, 1}, {1, 1, 1}));  // steps 1 and 2 both differ
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  const auto outcome = runner.Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();
  EXPECT_EQ(outcome.value().cycles_executed, 3u);
  ASSERT_TRUE(runner.FirstDivergence().has_value());
  EXPECT_EQ(runner.FirstDivergence()->tick_index, 1u);
  ASSERT_EQ(CountDivergenceLines(runner), 1u);
  EXPECT_EQ(runner.EventLogLines().back(), "event=degrade step=1 entry=first_divergence stage=B port=out");
}

TEST(RunStep, OutputsDifferingOnlyInCycleCounterAreNotADivergence) {
  Harness h(ControlSpec(), EchoRecording({100'000, 200'000, 300'000}, {5, 6, 7}));
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  ASSERT_TRUE(runner.Run().ok());
  EXPECT_FALSE(runner.FirstDivergence().has_value());
  EXPECT_EQ(CountDivergenceLines(runner), 0u);
}

TEST(RunStep, AStagesWarmingUpEndsAtItsFirstEqualOutputNotItsFirstByteEqualOne) {
  // The recorded 300 ms output differs from the stage's only in cycle_counter: equal outputs, not equal bytes.
  Harness h(ControlSpec(), EchoRecording({100'000, 200'000, 300'000}, {1, 1, 9}));
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  Collect tap;
  runner.SetLiveMeasurement(&tap);
  ASSERT_TRUE(runner.StepOnce().value());     // 100 ms, step 0: the recording's start, not warming up
  ASSERT_TRUE(runner.Seek(200 * kMs).ok());
  ASSERT_TRUE(runner.StepOnce().value());     // 200 ms: the RESTART run after the jump raises the badge
  ASSERT_TRUE(runner.StepOnce().value());     // 300 ms: the first RUN run, equal outputs, ends it
  ASSERT_EQ(tap.badges.size(), 3u);
  EXPECT_TRUE(tap.badges[0].empty());
  const auto warming = [](const std::vector<StepBadge>& badges) -> std::uint64_t {
    for (const StepBadge& badge : badges) {
      if (badge.kind == BadgeKind::kWarmingUp && badge.subject == "B") return badge.count;
    }
    return 0;
  };
  EXPECT_EQ(warming(tap.badges[1]), 1u);
  EXPECT_EQ(warming(tap.badges[2]), 1u);  // not raised again: a byte comparison would raise it a second time
}

// `IMP-0033` (`ARCH §7`): an output meets the recorded output of the same port and `measurement_counter`, never the
// recorded output of the same instant. A stage that runs twice in one step (two controls at 100 ms, counters 10 and
// 11), after a first run at 50 ms so neither is a RESTART run; `B` echoes what it reads, so its outputs carry the
// counters 10 and 11. `recorded_source_us` is what each recorded `B.out` says: 100'000 equals the echo.
std::vector<io::RawMessage> TwoRunsInOneStep(std::uint64_t recorded_10_us, std::uint64_t recorded_11_us) {
  std::vector<io::RawMessage> messages;
  messages.push_back(Message("/A/out", 50 * kMs, Data(9, 50'000)));
  messages.push_back(Message("/B/control", 50 * kMs, Data(9, 50'000, 1)));
  messages.push_back(Message("/B/refSync", 50 * kMs, RefSyncOf(9, {{"in", 9}})));
  messages.push_back(Message("/B/out", 50 * kMs, Data(9, 50'000)));
  messages.push_back(Message("/A/out", 100 * kMs, Data(10, 100'000)));
  messages.push_back(Message("/A/out", 100 * kMs, Data(11, 100'000)));
  messages.push_back(Message("/B/control", 100 * kMs, Data(10, 100'000, 2)));
  messages.push_back(Message("/B/control", 100 * kMs, Data(11, 100'000, 3)));
  messages.push_back(Message("/B/refSync", 100 * kMs, RefSyncOf(10, {{"in", 10}})));
  messages.push_back(Message("/B/refSync", 100 * kMs, RefSyncOf(11, {{"in", 11}})));
  messages.push_back(Message("/B/out", 100 * kMs, Data(10, recorded_10_us)));
  messages.push_back(Message("/B/out", 100 * kMs, Data(11, recorded_11_us)));
  return messages;
}

Runner RunToTheEnd(Harness& h) {
  EXPECT_TRUE(h.echo.ok());
  auto built = h.Build();
  EXPECT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  const auto outcome = runner.Run();
  EXPECT_TRUE(outcome.ok()) << outcome.error().Format();
  return runner;
}

TEST(RunStep, IMP0033TwoRunsOfOneStageInOneStepBothEqualToTheirRecordedRunsAreNoDivergence) {
  Harness h(ControlSpec(), TwoRunsInOneStep(100'000, 100'000));
  Runner runner = RunToTheEnd(h);
  EXPECT_FALSE(runner.FirstDivergence().has_value());  // by instant, run 10 met the recorded output of 11
  EXPECT_EQ(CountDivergenceLines(runner), 0u);
}

TEST(RunStep, IMP0033TheFirstOfTwoRunsInOneStepDifferingIsReportedOnThatStageAndPort) {
  Harness h(ControlSpec(), TwoRunsInOneStep(77'000, 100'000));
  Runner runner = RunToTheEnd(h);
  ASSERT_TRUE(runner.FirstDivergence().has_value());
  ASSERT_EQ(CountDivergenceLines(runner), 1u);
  EXPECT_EQ(runner.EventLogLines().back().substr(runner.EventLogLines().back().find("entry=")),
            "entry=first_divergence stage=B port=out");
}

TEST(RunStep, IMP0033OnlyTheSecondOfTwoRunsInOneStepDifferingIsReportedTheSameWay) {
  Harness h(ControlSpec(), TwoRunsInOneStep(100'000, 77'000));
  Runner runner = RunToTheEnd(h);
  ASSERT_TRUE(runner.FirstDivergence().has_value());
  ASSERT_EQ(CountDivergenceLines(runner), 1u);
  EXPECT_EQ(runner.EventLogLines().back().substr(runner.EventLogLines().back().find("entry=")),
            "entry=first_divergence stage=B port=out");
}

// `C` reads `B`'s output; the car ran `C` at 100 ms on `B`'s sample 10, which `B` made at 200 ms. So `C`'s run waits
// (`B.out` 10 is not committed), and runs in the 200 ms step, a step after its recorded run.
struct WaitingRun {
  explicit WaitingRun(std::uint64_t recorded_c_out_us) {
    spec = ControlSpec();
    SpecStage c;
    c.name = "C";
    c.mode = "simulate";
    c.trigger = "control";
    c.ports = {Port("control", "req"), Port("in", "req"), Port("out", "pro"), Port("refSync", "pro", "adas.common.RefSync")};
    SpecInput in;
    in.port = "in";
    in.producer = "B";
    in.producer_port = "out";
    c.inputs = {in};
    spec.stages.push_back(c);
    topics = ControlTopics();
    topics["/C/control"] = Topic("adas.common.CycleControl", io::Provenance::kSimulated);
    topics["/C/refSync"] = Topic("adas.common.RefSync", io::Provenance::kSimulated);
    topics["/C/out"] = Topic("adas.common.CycleControl", io::Provenance::kSimulated);
    // 50 ms: both stages run once (RESTART). 100 ms: `C`'s run names `B.out` 10. 200 ms: `B` makes it.
    messages.push_back(Message("/A/out", 50 * kMs, Data(9, 50'000)));
    messages.push_back(Message("/B/control", 50 * kMs, Data(9, 50'000, 1)));
    messages.push_back(Message("/B/refSync", 50 * kMs, RefSyncOf(9, {{"in", 9}})));
    messages.push_back(Message("/B/out", 50 * kMs, Data(9, 50'000)));
    messages.push_back(Message("/C/control", 50 * kMs, Data(1, 50'000, 1)));
    messages.push_back(Message("/C/refSync", 50 * kMs, RefSyncOf(1, {{"in", 9}})));
    messages.push_back(Message("/C/out", 50 * kMs, Data(9, 50'000)));
    messages.push_back(Message("/A/out", 100 * kMs, Data(10, 100'000)));
    messages.push_back(Message("/C/control", 100 * kMs, Data(2, 100'000, 2)));
    messages.push_back(Message("/C/refSync", 100 * kMs, RefSyncOf(2, {{"in", 10}})));
    messages.push_back(Message("/C/out", 100 * kMs, Data(10, recorded_c_out_us)));
    messages.push_back(Message("/B/control", 200 * kMs, Data(10, 100'000, 2)));
    messages.push_back(Message("/B/refSync", 200 * kMs, RefSyncOf(10, {{"in", 10}})));
    messages.push_back(Message("/B/out", 200 * kMs, Data(10, 100'000)));
  }
  RunSpec spec;
  std::map<std::string, io::TopicInfo> topics;
  std::vector<io::RawMessage> messages;
};

Result<Runner> BuildWaiting(WaitingRun& w, Echo& b_echo, Echo& c_echo, bus::PortBus& bus, testing::VectorReader& reader,
                            io::WriterBase& writer) {
  return Runner::Construct(w.spec, bus, {&reader}, {{"B", b_echo.get()}, {"C", c_echo.get()}},
                           google::protobuf::DescriptorPool::generated_pool(), &writer, nullptr, Runner::Options{});
}

TEST(RunStep, IMP0033ARunThatWaitedAndRanStepsAfterItsRecordedRunIsComparedWithItsOwnRecordedOutput) {
  for (const bool differs : {false, true}) {
    WaitingRun w(differs ? 77'000 : 100'000);
    Echo b_echo;
    Echo c_echo;
    ASSERT_TRUE(b_echo.ok() && c_echo.ok());
    bus::PortBus bus;
    testing::VectorReader reader(w.messages, w.topics);
    testing::CapturingWriter sink;
    io::WriterBase writer(sink);
    auto built = BuildWaiting(w, b_echo, c_echo, bus, reader, writer);
    ASSERT_TRUE(built.ok()) << built.error().Format();
    Runner runner = std::move(built).value();
    ASSERT_TRUE(runner.Run().ok());
    // C ran in the 200 ms step: its output was written there, after its recorded run at 100 ms.
    std::int64_t c_ran_at = -1;
    for (const io::RawMessage& message : sink.written) {
      if (message.topic == "/C/out" && CounterOf(message) == 10u) c_ran_at = message.log_time_ns;
    }
    EXPECT_EQ(c_ran_at, 200 * kMs);
    if (differs) {
      ASSERT_TRUE(runner.FirstDivergence().has_value());
      ASSERT_EQ(CountDivergenceLines(runner), 1u);
      EXPECT_EQ(runner.EventLogLines().back().substr(runner.EventLogLines().back().find("entry=")),
                "entry=first_divergence stage=C port=out");
    } else {
      EXPECT_FALSE(runner.FirstDivergence().has_value());
      EXPECT_EQ(CountDivergenceLines(runner), 0u);
    }
  }
}

// The first-divergence tests that used a header-less stub output (`UT-RUN-05`, `UT-RUN-06`, `UT-RUN-07`, `SW-0116`,
// `SW-0117`, `SW-0224`) now run on the echo stage and real `sig_header` messages: since `IMP-0033` pairs an output with
// the recorded output of its own `measurement_counter`, an output with no counter is never compared. `n` instants,
// the recorded `B.out` of every instant from `diverges_from` on carrying another source time than the echo's.
std::vector<io::RawMessage> LongEchoRecording(int n, int diverges_from) {
  std::vector<io::RawMessage> messages;
  for (int i = 0; i < n; ++i) {
    const std::int64_t t = (i + 1) * 100 * kMs;
    messages.push_back(Message("/A/out", t, Data(10 + i, (i + 1) * 100'000)));
    messages.push_back(Message("/B/control", t, Data(10 + i, (i + 1) * 100'000, i + 1,
                                                            i == 0 ? adas::common::CycleControl::RESTART
                                                                   : adas::common::CycleControl::RUN)));
    messages.push_back(Message("/B/refSync", t, RefSyncOf(10 + i, {{"in", static_cast<std::uint32_t>(10 + i)}})));
    messages.push_back(Message("/B/out", t, Data(10 + i, i >= diverges_from ? 1 : (i + 1) * 100'000)));
  }
  return messages;
}

TEST(RunStep, UtRun05TheFirstDivergenceIsLatchedAndIsIdenticalAcrossReRuns) {
  // Step 0 is the stage's RESTART run, never compared; step 1 is the first RUN run and the first divergence.
  const auto run_once = [] {
    Harness h(ControlSpec(), LongEchoRecording(6, 1));
    return RunToTheEnd(h).FirstDivergence();
  };
  const std::optional<Divergence> first = run_once();
  ASSERT_TRUE(first.has_value());
  EXPECT_EQ(first->tick_index, 1u);
  EXPECT_EQ(first->log_time_ns, 200 * kMs);
  EXPECT_EQ(first->stage, "B");
  EXPECT_EQ(first->port, "out");
  EXPECT_GT(first->differing_bytes, 0u);
  const std::optional<Divergence> again = run_once();
  ASSERT_TRUE(again.has_value());
  EXPECT_EQ(again->tick_index, first->tick_index);
  EXPECT_EQ(again->log_time_ns, first->log_time_ns);
  EXPECT_EQ(again->differing_bytes, first->differing_bytes);
}

TEST(RunStep, UtRun06EveryMessageWrittenPastTheGraceWindowCarriesTheFlagAndEarlierOnesDoNot) {
  Harness h(ControlSpec(), LongEchoRecording(8, 1));
  Runner::Options options;
  options.grace_ticks = 3;
  ASSERT_TRUE(h.echo.ok());
  auto built = h.Build(options);
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  ASSERT_TRUE(runner.Run().ok());
  ASSERT_TRUE(runner.FirstDivergence().has_value());
  // Any message at or after the divergence step (1) plus the grace window (3) is flagged; every earlier one is not.
  const std::int64_t flagged_from_ns = (1 + 3 + 1) * 100 * kMs;
  bool saw_flagged = false;
  bool saw_unflagged = false;
  for (const io::RawMessage& message : h.sink.written) {
    if (message.log_time_ns >= flagged_from_ns) {
      EXPECT_TRUE(message.informational_only) << message.topic << " @" << message.log_time_ns;
      saw_flagged = true;
    } else {
      EXPECT_FALSE(message.informational_only) << message.topic << " @" << message.log_time_ns;
      saw_unflagged = true;
    }
  }
  EXPECT_TRUE(saw_flagged);
  EXPECT_TRUE(saw_unflagged);
}

TEST(RunStep, UtRun07ProgressJsonCarriesTheFirstDivergenceOnceLatched) {
  Harness h(ControlSpec(), LongEchoRecording(4, 1));
  ASSERT_TRUE(h.echo.ok());
  const std::filesystem::path progress =
      std::filesystem::temp_directory_path() / "simcore_run_step_divergence_progress.json";
  std::filesystem::remove(progress);
  Checkpoint checkpoint(progress, h.spec.run_id);
  auto built = h.Build();
  ASSERT_TRUE(built.ok()) << built.error().Format();
  Runner runner = std::move(built).value();
  runner.SetCheckpoint(&checkpoint);
  ASSERT_TRUE(runner.Run().ok());
  ASSERT_TRUE(runner.FirstDivergence().has_value());

  auto record = Checkpoint::Read(progress);
  ASSERT_TRUE(record.ok()) << record.error().Format();
  EXPECT_TRUE(record.value().has_divergence);
  EXPECT_EQ(record.value().divergence_tick_index, 1u);
  EXPECT_EQ(record.value().divergence_log_time_ns, 200 * kMs);
  EXPECT_EQ(record.value().divergence_stage, "B");
  EXPECT_EQ(record.value().divergence_port, "out");
  EXPECT_EQ(record.value().divergence_differing_bytes, runner.FirstDivergence()->differing_bytes);
  std::filesystem::remove(progress);
}

}  // namespace
}  // namespace simcore::runner
