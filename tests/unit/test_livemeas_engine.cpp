// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The engine writes the live measurement (`WP-15`), through the C ABI alone and a real echo stub:
///   `IMP-0078` (the description lists the setup's stages and ports), `IMP-0080` (a stage run twice in one
///   step leaves two values on its per-run ports, in run order, `D30`), `IMP-0081` (every cycle equals the
///   step report the step tap gets), `IMP-0082` (a held name prints one warning and the run completes; no
///   `outputs.livemeas`, nothing is created), `IMP-0083` (outcome `pass` after `simEngineRun`, and the close
///   in `simEngineDestroy` of a host-driven run) and `IMP-0084` (a seek keeps the run id and the steps
///   continue).
///
///   A reader attaches right after `simEngineCreate`, when the live measurement is open, and keeps its
///   mapping: the name is removed at close (`ARCH §14` Q8), the mapping is not.
/// @author Pavan Karimajji

#include <gtest/gtest.h>
#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include "abi/engine_access.hpp"
#include "common/cycle_control.pb.h"
#include "common/ref_sync.pb.h"
#include "livemeas/engine_sink.hpp"
#include "livemeas/livemeas_layout.hpp"
#include "livemeas/meas_cycle.pb.h"
#include "livemeas/meas_description.pb.h"
#include "livemeas/shared_region.hpp"
#include "run_fixtures.hpp"
#include "simcore/abi/simcore.h"
#include "simcore/io.hpp"
#include "simcore/runner.hpp"

namespace {

namespace layout = adas::livemeas;
using vantage::livemeas::SharedRegion;

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

std::filesystem::path TempPath(const std::string& name) { return std::filesystem::temp_directory_path() / name; }

std::string JsonEscape(const std::filesystem::path& path) {
  std::string out;
  for (char c : path.string()) {
    if (c == '\\' || c == '"') out.push_back('\\');
    out.push_back(c);
  }
  return out;
}

void SetEnv(const char* name, const char* value) {
#if defined(_WIN32)
  _putenv_s(name, value);
#else
  setenv(name, value, 1);
#endif
}

std::string UniqueName(const char* tag) {
  static int counter = 0;
  return std::string("vnt_lme_") + tag + "_" + std::to_string(SharedRegion::currentProcessId()) + "_" +
         std::to_string(++counter);
}

std::string LiveMeasJson(const std::string& name, int cycle_slots = 16) {
  return R"("livemeas": {"name": ")" + name + R"(", "cycle_slot_count": )" + std::to_string(cycle_slots) +
         R"(, "cycle_slot_size": 4096, "bulk_slot_count": 2, "bulk_slot_size": 4096})";
}

// Three heartbeat messages 10 ms apart; one clock-started stage `sut` with one output `outputs`.
std::filesystem::path WriteHeartbeatRecording(const std::filesystem::path& path) {
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(path);
  EXPECT_TRUE(writer.ok());
  simcore::io::TopicInfo heartbeat;
  heartbeat.schema_name = "test.Heartbeat";
  EXPECT_TRUE(writer.value()->Open(path, {{"/dummy/heartbeat", heartbeat}}).ok());
  for (std::int64_t t_ns : {0, 10'000'000, 20'000'000}) {
    simcore::io::RawMessage msg;
    msg.topic = "/dummy/heartbeat";
    msg.log_time_ns = t_ns;
    msg.payload = {0x01};
    writer.value()->Write(msg);
  }
  writer.value()->Close();
  return path;
}

std::filesystem::path WriteClockSpec(const std::string& tag, const std::string& outputs_json) {
  const std::filesystem::path recording = WriteHeartbeatRecording(TempPath("lme_" + tag + ".mcap"));
  const std::filesystem::path spec = TempPath("lme_" + tag + "_spec.json");
  std::ofstream out(spec);
  out << R"({
    "schema": "adas.sim.runspec/2.0",
    "run_id": "20261104T000000Z-lme",
    "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [{
      "name": "sut", "mode": "simulate",
      "impl": {"kind": "dll", "path": ")"
      << JsonEscape(EchoStubPath()) << R"("},
      "trigger": "", "clock_period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
      "ports": [{"name": "outputs", "dir": "pro", "kind": "data", "proto_type": "test.Echo",
                 "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 16}],
      "inputs": []
    }],
    "mutations": [],
    "coherence_verdict": "clean", "readiness_limit_steps": 4, "fallback_max_gap": 4,
    "outputs": {)"
      << outputs_json << R"(},
    "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  return spec;
}

struct Engine {
  SimEngine* engine = nullptr;
  std::string error;
};

Engine Create(const std::filesystem::path& spec) {
  Engine e;
  char err[512] = {0};
  SimExitCode code = kSimExitOk;
  e.engine = simEngineCreate(spec.string().c_str(), nullptr, 2000, err, sizeof(err), &code);
  e.error = err;
  return e;
}

const layout::MeasStatus& StatusOf(const SharedRegion& region) {
  return *static_cast<const layout::MeasStatus*>(region.data());
}

std::unique_ptr<SharedRegion> Attach(const std::string& name) {
  return SharedRegion::open(name, SharedRegion::Access::kReadOnly);
}

bool ReadStep(const SharedRegion& region, std::uint64_t step, adas::livemeas::MeasCycle& cycle,
              layout::CycleSlotHeader* header_out = nullptr) {
  const layout::MeasStatus& s = StatusOf(region);
  for (std::size_t i = 0; i < s.cycleSlotCount; ++i) {
    std::vector<std::uint8_t> copy(s.cycleSlotSize);
    const auto* slot = static_cast<const std::uint8_t*>(region.data()) + layout::cycleSlotOffset(s, i);
    if (!layout::tryCopySlot<layout::CycleSlotHeader>(slot, s.cycleSlotSize, copy.data(), copy.size())) continue;
    layout::CycleSlotHeader header{};
    std::memcpy(&header, copy.data(), sizeof(header));
    if (header.step != step) continue;
    if (header_out != nullptr) std::memcpy(header_out, &header, sizeof(header));
    return cycle.ParseFromArray(copy.data() + sizeof(layout::CycleSlotHeader), static_cast<int>(header.length));
  }
  return false;
}

adas::livemeas::MeasDescription ReadDescription(const SharedRegion& region) {
  const layout::MeasStatus& s = StatusOf(region);
  adas::livemeas::MeasDescription description;
  EXPECT_TRUE(description.ParseFromArray(
      static_cast<const std::uint8_t*>(region.data()) + layout::descriptionOffset(),
      static_cast<int>(s.descriptionLength)));
  return description;
}

// A tap that keeps what it was handed, copies of every payload.
struct Tap final : simcore::runner::LiveMeasSink {
  struct Value {
    std::string port;
    std::vector<std::uint8_t> payload;
    simcore::bus::Origin origin;
    std::optional<std::int64_t> age_ns;
    std::size_t run;
  };
  struct Step {
    std::uint64_t step;
    std::int64_t time;
    std::vector<Value> values;
    std::vector<simcore::runner::StepBadge> badges;
  };
  void OnStep(const simcore::runner::StepReport& report) override {
    Step step{report.step, report.sim_time_ns, {}, report.badges};
    for (const auto& value : report.values) {
      step.values.push_back({value.port, *value.payload, value.origin, value.age_ns, value.run});
    }
    steps.push_back(std::move(step));
  }
  std::vector<Step> steps;
};

class LiveMeasEngine : public ::testing::Test {
 protected:
  void SetUp() override {
    SetEnv("ADAS_SIL_TEST_STUB_NAME", "run_stub");
    SetEnv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs");
    SetEnv("ADAS_SIL_TEST_STUB_INPUT_PORT", "");
  }
};

}  // namespace

// `IMP-0078`: the description lists the setup's stages and ports.
TEST_F(LiveMeasEngine, IMP_0078_TheDescriptionListsTheSetupsStagesAndPorts) {
  const std::string name = UniqueName("desc");
  Engine e = Create(WriteClockSpec("desc", LiveMeasJson(name)));
  ASSERT_NE(e.engine, nullptr) << e.error;
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const layout::MeasDescription description = ReadDescription(*data);
  ASSERT_EQ(description.stages_size(), 1);
  EXPECT_EQ(description.stages(0).name(), "sut");
  EXPECT_EQ(description.stages(0).mode(), layout::MeasStage::MODE_SIMULATE);
  EXPECT_EQ(description.stages(0).clock_period_ns(), 10'000'000u);
  EXPECT_EQ(description.stages(0).build_id(), "test");  // the loaded manifest's
  ASSERT_EQ(description.ports_size(), 1);
  EXPECT_EQ(description.ports(0).name(), "sut.outputs");
  EXPECT_EQ(description.ports(0).proto_type(), "test.Echo");
  EXPECT_FALSE(description.ports(0).bulk());
  EXPECT_EQ(description.readiness_limit_steps(), 4u);
  EXPECT_EQ(description.recording(), "lme_desc.mcap");
  EXPECT_EQ(StatusOf(*data).cycleSlotCount, 16u);
  EXPECT_EQ(StatusOf(*data).cycleSlotSize, 4096u);
  simEngineDestroy(e.engine);
}

// `IMP-0083`: `pass` after `simEngineRun`, with the name removed and the attached reader still reading.
// `IMP-0081`: every cycle equals the step report the tap gets, through the same chain `step_tap` uses.
TEST_F(LiveMeasEngine, IMP_0081_EveryCycleEqualsTheStepReportTheTapGetsAndIMP_0083TheOutcomeIsPass) {
  const std::string name = UniqueName("tap");
  Engine e = Create(WriteClockSpec("tap", LiveMeasJson(name)));
  ASSERT_NE(e.engine, nullptr) << e.error;
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  simcore::runner::Runner* runner = SimEngineRunner(e.engine);
  ASSERT_NE(runner, nullptr);
  auto* writer_sink = dynamic_cast<simcore::livemeas::LiveMeasWriterSink*>(runner->LiveMeasurement());
  ASSERT_NE(writer_sink, nullptr);  // the engine installed its own sink
  Tap tap;
  writer_sink->SetNext(&tap);

  char err[512] = {0};
  EXPECT_EQ(simEngineRun(e.engine, err, sizeof(err)), kSimExitOk) << err;
  ASSERT_EQ(tap.steps.size(), 3u);
  const layout::MeasDescription description = ReadDescription(*data);
  for (const Tap::Step& step : tap.steps) {
    layout::CycleSlotHeader header{};
    layout::MeasCycle cycle;
    ASSERT_TRUE(ReadStep(*data, step.step, cycle, &header)) << "step " << step.step;
    EXPECT_EQ(static_cast<std::int64_t>(header.simTimeNs), step.time);
    ASSERT_EQ(static_cast<std::size_t>(cycle.values_size()), step.values.size());
    for (std::size_t i = 0; i < step.values.size(); ++i) {
      const auto& value = cycle.values(static_cast<int>(i));
      EXPECT_EQ(description.ports(static_cast<int>(value.port())).name(), step.values[i].port);
      EXPECT_EQ(value.payload(), std::string(step.values[i].payload.begin(), step.values[i].payload.end()));
      EXPECT_EQ(value.age_ns(), static_cast<std::uint64_t>(step.values[i].age_ns.value_or(0)));
    }
    EXPECT_EQ(static_cast<std::size_t>(cycle.badges_size()), step.badges.size());
  }
  EXPECT_EQ(StatusOf(*data).status.load(), 3u);   // finished
  EXPECT_EQ(StatusOf(*data).outcome.load(), 1u);  // pass
  EXPECT_EQ(StatusOf(*data).writeSequence.load(), 3u);
  simEngineDestroy(e.engine);
}

// `IMP-0082`: a name held by a live writer prints exactly one warning naming it, and the run completes.
TEST_F(LiveMeasEngine, IMP_0082_AHeldNamePrintsOneWarningAndTheRunCompletes) {
  const std::string name = UniqueName("held");
  Engine first = Create(WriteClockSpec("held1", LiveMeasJson(name)));
  ASSERT_NE(first.engine, nullptr) << first.error;
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const std::uint64_t run_id = StatusOf(*data).runId;

  testing::internal::CaptureStderr();
  Engine second = Create(WriteClockSpec("held2", LiveMeasJson(name)));
  const std::string warnings = testing::internal::GetCapturedStderr();
  ASSERT_NE(second.engine, nullptr) << second.error;
  std::size_t lines = 0;
  std::istringstream stream(warnings);
  for (std::string line; std::getline(stream, line);) {
    if (line.find("live measurement") != std::string::npos) {
      ++lines;
      EXPECT_NE(line.find(name), std::string::npos) << line;
      EXPECT_NE(line.find("kLiveMeasNameHeld"), std::string::npos) << line;
    }
  }
  EXPECT_EQ(lines, 1u) << warnings;
  char err[512] = {0};
  EXPECT_EQ(simEngineRun(second.engine, err, sizeof(err)), kSimExitOk) << err;
  EXPECT_EQ(StatusOf(*data).runId, run_id);  // the first engine's live measurement is untouched
  EXPECT_EQ(StatusOf(*data).status.load(), 1u);
  simEngineDestroy(second.engine);
  simEngineDestroy(first.engine);
}

// Without `outputs.livemeas` nothing is created and the run is unchanged.
TEST_F(LiveMeasEngine, IMP_0082_WithoutOutputsLiveMeasNothingIsCreated) {
  const std::string name = UniqueName("none");
  Engine e = Create(WriteClockSpec("none", ""));
  ASSERT_NE(e.engine, nullptr) << e.error;
  EXPECT_EQ(Attach(name), nullptr);
  char err[512] = {0};
  EXPECT_EQ(simEngineRun(e.engine, err, sizeof(err)), kSimExitOk) << err;
  simEngineDestroy(e.engine);
}

// `IMP-0084`: a seek neither opens nor closes; one run id, the step numbers continue.
// `IMP-0083`: a host that drove `simEngineStepOnce` to the end gets `pass` from `simEngineDestroy`.
TEST_F(LiveMeasEngine, IMP_0084_ASeekKeepsTheRunIdAndTheStepsContinueAndIMP_0083DestroyClosesAHostDrivenRun) {
  const std::string name = UniqueName("seek");
  Engine e = Create(WriteClockSpec("seek", LiveMeasJson(name)));
  ASSERT_NE(e.engine, nullptr) << e.error;
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const std::uint64_t run_id = StatusOf(*data).runId;
  char err[512] = {0};
  std::int32_t more = 1;
  ASSERT_EQ(simEngineStepOnce(e.engine, err, sizeof(err), &more), kSimExitOk) << err;  // step 0, at 0 ms
  ASSERT_EQ(simEngineSeek(e.engine, 20'000'000, err, sizeof(err)), kSimExitOk) << err;
  EXPECT_EQ(StatusOf(*data).runId, run_id);
  EXPECT_EQ(StatusOf(*data).status.load(), 1u);
  ASSERT_EQ(simEngineStepOnce(e.engine, err, sizeof(err), &more), kSimExitOk) << err;  // step 1, at 20 ms
  ASSERT_EQ(simEngineStepOnce(e.engine, err, sizeof(err), &more), kSimExitOk) << err;
  EXPECT_EQ(more, 0);
  EXPECT_EQ(StatusOf(*data).runId, run_id);
  layout::MeasCycle cycle;
  layout::CycleSlotHeader header{};
  ASSERT_TRUE(ReadStep(*data, 0, cycle, &header));
  EXPECT_EQ(header.simTimeNs, 0u);
  ASSERT_TRUE(ReadStep(*data, 1, cycle, &header));  // numbering continues across the jump
  EXPECT_EQ(header.simTimeNs, 20'000'000u);
  EXPECT_EQ(StatusOf(*data).status.load(), 1u);  // still running: only the destroy closes a host-driven run
  simEngineDestroy(e.engine);
  EXPECT_EQ(StatusOf(*data).status.load(), 3u);
  EXPECT_EQ(StatusOf(*data).outcome.load(), 1u);
}

// A host that stops stepping early gets `fail` from the destroy: the recording did not end.
TEST_F(LiveMeasEngine, IMP_0083_DestroyOfARunThatDidNotReachTheEndWritesFail) {
  const std::string name = UniqueName("early");
  Engine e = Create(WriteClockSpec("early", LiveMeasJson(name)));
  ASSERT_NE(e.engine, nullptr) << e.error;
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  char err[512] = {0};
  std::int32_t more = 1;
  ASSERT_EQ(simEngineStepOnce(e.engine, err, sizeof(err), &more), kSimExitOk) << err;
  simEngineDestroy(e.engine);
  EXPECT_EQ(StatusOf(*data).status.load(), 3u);
  EXPECT_EQ(StatusOf(*data).outcome.load(), 2u);
}

// A recording the reader finds cut off ends the run with exit code `Input` (`VNT-CLEAN-1`), and the live measurement closes
// `fail`, not `pass`.
TEST_F(LiveMeasEngine, IMP_0083_ARecordingCutOffEndsTheRunWithInputAndWritesFail) {
  const std::string name = UniqueName("cutoff");
  const std::filesystem::path spec = WriteClockSpec("cutoff", LiveMeasJson(name));
  const std::filesystem::path recording = TempPath("lme_cutoff.mcap");
  std::string bytes;
  {
    std::ifstream in(recording, std::ios::binary);
    bytes.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
  }
  {
    std::ofstream out(recording, std::ios::binary | std::ios::trunc);
    out.write(bytes.data(), static_cast<std::streamsize>(bytes.size() * 6 / 10));
  }
  Engine e = Create(spec);
  ASSERT_NE(e.engine, nullptr) << e.error;
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  char err[512] = {0};
  EXPECT_EQ(simEngineRun(e.engine, err, sizeof(err)), kSimExitInput);
  EXPECT_NE(std::string(err).find("lme_cutoff.mcap"), std::string::npos) << err;
  EXPECT_EQ(StatusOf(*data).status.load(), 3u);
  EXPECT_EQ(StatusOf(*data).outcome.load(), 2u);
  simEngineDestroy(e.engine);
}

// `IMP-0080` (`D30`): `B` runs twice in the 100 ms step (two recorded controls at the same instant); each of its
// per-run ports leaves two values in that step's cycle, in run order, the same recording edit `IMP-0066`'s test uses.
namespace {

// The recorded schema of a message type -- its file and every file it imports -- as a serialized
// `FileDescriptorSet`, which is what a real recording carries and the engine's own pool is built from.
void AddFileWithDependencies(const google::protobuf::FileDescriptor* file, google::protobuf::FileDescriptorSet& set,
                             std::set<std::string>& seen) {
  if (!seen.insert(file->name()).second) return;
  for (int i = 0; i < file->dependency_count(); ++i) AddFileWithDependencies(file->dependency(i), set, seen);
  file->CopyTo(set.add_file());
}

std::vector<std::uint8_t> SchemaBytesOf(const google::protobuf::Descriptor* descriptor) {
  google::protobuf::FileDescriptorSet set;
  std::set<std::string> seen;
  AddFileWithDependencies(descriptor->file(), set, seen);
  const std::string text = set.SerializeAsString();
  return std::vector<std::uint8_t>(text.begin(), text.end());
}

simcore::io::TopicInfo TopicWithSchema(const google::protobuf::Descriptor* descriptor,
                                       simcore::io::Provenance provenance) {
  simcore::io::TopicInfo info = simcore::testing::Topic(descriptor->full_name(), provenance);
  info.schema_bytes = SchemaBytesOf(descriptor);
  return info;
}

std::filesystem::path WriteTwoRunsRecording(const std::filesystem::path& path) {
  using simcore::testing::Data;
  using simcore::testing::RefSyncOf;
  constexpr std::int64_t kMs = 1'000'000;
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(path);
  EXPECT_TRUE(writer.ok());
  const std::map<std::string, simcore::io::TopicInfo> topics = {
      {"/A/out", TopicWithSchema(adas::common::CycleControl::descriptor(), simcore::io::Provenance::kMeasured)},
      {"/B/control", TopicWithSchema(adas::common::CycleControl::descriptor(), simcore::io::Provenance::kSimulated)},
      {"/B/refSync", TopicWithSchema(adas::common::RefSync::descriptor(), simcore::io::Provenance::kSimulated)},
      {"/B/out", TopicWithSchema(adas::common::CycleControl::descriptor(), simcore::io::Provenance::kSimulated)}};
  EXPECT_TRUE(writer.value()->Open(path, topics).ok());
  const std::vector<simcore::io::RawMessage> messages = {
      simcore::testing::Message("/A/out", 50 * kMs, Data(9, 50'000)),
      simcore::testing::Message("/B/control", 50 * kMs, Data(9, 50'000, 1)),
      simcore::testing::Message("/B/refSync", 50 * kMs, RefSyncOf(9, {{"in", 9}})),
      simcore::testing::Message("/B/out", 50 * kMs, Data(9, 50'000)),
      simcore::testing::Message("/A/out", 100 * kMs, Data(10, 100'000)),
      simcore::testing::Message("/A/out", 100 * kMs, Data(11, 100'000)),
      simcore::testing::Message("/B/control", 100 * kMs, Data(10, 100'000, 2)),
      simcore::testing::Message("/B/control", 100 * kMs, Data(11, 100'000, 3)),
      simcore::testing::Message("/B/refSync", 100 * kMs, RefSyncOf(10, {{"in", 10}})),
      simcore::testing::Message("/B/refSync", 100 * kMs, RefSyncOf(11, {{"in", 11}})),
      simcore::testing::Message("/B/out", 100 * kMs, Data(10, 100'000)),
      simcore::testing::Message("/B/out", 100 * kMs, Data(11, 100'000))};
  for (const auto& message : messages) writer.value()->Write(message);
  writer.value()->Close();
  return path;
}

std::filesystem::path WriteTwoRunsSpec(const std::string& livemeas_json) {
  const std::filesystem::path recording = WriteTwoRunsRecording(TempPath("lme_twice.mcap"));
  const std::filesystem::path spec = TempPath("lme_twice_spec.json");
  const auto port = [](const std::string& name, const std::string& dir, const std::string& type) {
    return R"({"name": ")" + name + R"(", "dir": ")" + dir + R"(", "kind": "data", "proto_type": ")" + type +
           R"(", "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 8})";
  };
  std::ofstream out(spec);
  out << R"({
    "schema": "adas.sim.runspec/2.0", "run_id": "20261104T000000Z-twice", "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [
      {"name": "A", "mode": "measured", "impl": {"kind": "dll", "path": ""}, "trigger": "", "clock_period_ns": 0,
       "abi_version": 1, "config_bundle_sha256": "",
       "ports": [)"
      << port("out", "pro", "adas.common.CycleControl") << R"(], "inputs": []},
      {"name": "B", "mode": "simulate", "impl": {"kind": "dll", "path": ")"
      << JsonEscape(EchoStubPath()) << R"("}, "trigger": "control", "clock_period_ns": 0,
       "abi_version": 1, "config_bundle_sha256": "",
       "ports": [)"
      << port("control", "req", "adas.common.CycleControl") << "," << port("in", "req", "adas.common.CycleControl")
      << "," << port("out", "pro", "adas.common.CycleControl") << "," << port("refSync", "pro", "adas.common.RefSync")
      << R"(],
       "inputs": [{"port": "in", "producer": "A", "producer_port": "out", "previous_cycle": false}]}
    ],
    "mutations": [], "coherence_verdict": "clean", "readiness_limit_steps": 2, "fallback_max_gap": 4,
    "outputs": {)"
      << livemeas_json << R"(},
    "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  return spec;
}

std::uint32_t CounterOf(const std::string& payload) {
  adas::common::CycleControl message;
  message.ParseFromString(payload);
  return message.sig_header().measurement_counter();
}

}  // namespace

TEST_F(LiveMeasEngine, IMP_0080_AStageRunTwiceInOneStepLeavesTwoValuesOnItsPerRunPortsInRunOrder) {
  SetEnv("ADAS_SIL_TEST_STUB_NAME", "step_stub");
  SetEnv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "out");
  SetEnv("ADAS_SIL_TEST_STUB_INPUT_PORT", "in");
  const std::string name = UniqueName("twice");
  Engine e = Create(WriteTwoRunsSpec(LiveMeasJson(name)));
  ASSERT_NE(e.engine, nullptr) << e.error;
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  char err[512] = {0};
  ASSERT_EQ(simEngineRun(e.engine, err, sizeof(err)), kSimExitOk) << err;
  const layout::MeasDescription description = ReadDescription(*data);
  // The steps are 50 ms (step 0) and 100 ms (step 1, where `B` runs twice).
  layout::MeasCycle cycle;
  ASSERT_TRUE(ReadStep(*data, 1, cycle));
  std::map<std::string, std::vector<std::uint32_t>> counters;
  for (const auto& value : cycle.values()) {
    counters[description.ports(static_cast<int>(value.port())).name()].push_back(CounterOf(value.payload()));
  }
  const std::vector<std::uint32_t> two_runs{10u, 11u};
  EXPECT_EQ(counters["B.control"], two_runs);  // each run's own control, run order
  EXPECT_EQ(counters["B.out"], two_runs);      // each run's own output
  ASSERT_EQ(counters["A.out"].size(), 1u);     // a stage that ran once keeps one value per port
  // The step before had one run: one value on each per-run port.
  ASSERT_TRUE(ReadStep(*data, 0, cycle));
  std::map<std::string, std::size_t> count0;
  for (const auto& value : cycle.values()) ++count0[description.ports(static_cast<int>(value.port())).name()];
  EXPECT_EQ(count0["B.control"], 1u);
  EXPECT_EQ(count0["B.out"], 1u);
  simEngineDestroy(e.engine);
}
