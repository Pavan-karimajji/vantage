// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The supervisor of the real `simengine` (`WP-17`): `IMP-0103` (arguments), `IMP-0105` (the outcome and its exit
///   code), `IMP-0106` (restarts after a crash only), `IMP-0107` and `IMP-0075` (the seal, the hold), `IMP-0108`
///   (`<run_setup>.attempts.jsonl`), `IMP-0110` and `IMP-0111` (the crash reproducer) and `IMP-0124` (the stages in
///   a call, from the supervision cell). Echo-stub setups as `UT-EXE-04`/`05` use; the seal runs a `held_probe`
///   stage with `outputs.livemeas`, held in its first call until a gate file exists.
/// @author Pavan Karimajji

#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>
#include <gtest/gtest.h>

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "common/comp_state.pb.h"
#include "common/cycle_control.pb.h"
#include "common/ref_sync.pb.h"
#include "lab/lab_sample.pb.h"
#include "livemeas/livemeas_layout.hpp"
#include "livemeas/shared_region.hpp"
#include "run_fixtures.hpp"
#include "simcore/abi/simcore.h"
#include "simcore/io.hpp"
#include "simcore/module_host.hpp"

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
#include <csignal>
#include <sys/types.h>
#endif

namespace {

namespace layout = adas::livemeas;
using simcore::module_host::IsolatedOutcome;
using vantage::livemeas::SharedRegion;

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

std::filesystem::path TempPath(const std::string& name) { return std::filesystem::temp_directory_path() / name; }
std::filesystem::path SimenginePath() { return std::filesystem::path(SIMENGINE_EXECUTABLE); }

std::string JsonEscape(const std::filesystem::path& path) {
  std::string out;
  for (char c : path.string()) {
    if (c == '\\' || c == '"') out.push_back('\\');
    out.push_back(c);
  }
  return out;
}

std::string UniqueName(const char* tag) {
  static int counter = 0;
  return std::string("vnt_sup_") + tag + "_" + std::to_string(SharedRegion::currentProcessId()) + "_" +
         std::to_string(++counter);
}

std::filesystem::path FixtureLibrary(const char* stem) {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / (std::string(stem) + ".dll");
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / ("lib" + std::string(stem) + ".so");
#endif
}

std::string ReadAll(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  std::ostringstream text;
  text << in.rdbuf();
  return text.str();
}

std::vector<std::string> Lines(const std::filesystem::path& path) {
  std::ifstream in(path);
  std::vector<std::string> lines;
  std::string line;
  while (std::getline(in, line)) {
    if (!line.empty()) lines.push_back(line);
  }
  return lines;
}

bool Has(const std::string& text, const std::string& part) { return text.find(part) != std::string::npos; }

// ---- setups ---------------------------------------------------------------------------------------------------

// Three heartbeat messages; one clock-started stage `sut` running the echo stub; `outputs_json` is the content of
// `outputs`.
std::filesystem::path WriteEchoSpec(const std::string& tag, const std::string& outputs_json = "") {
  const std::filesystem::path recording = TempPath("sup_" + tag + ".mcap");
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(recording);
  EXPECT_TRUE(writer.ok());
  simcore::io::TopicInfo heartbeat;
  heartbeat.schema_name = "test.Heartbeat";
  EXPECT_TRUE(writer.value()->Open(recording, {{"/dummy/heartbeat", heartbeat}}).ok());
  for (std::int64_t t_ns : {0, 10'000'000, 20'000'000}) {
    simcore::io::RawMessage msg;
    msg.topic = "/dummy/heartbeat";
    msg.log_time_ns = t_ns;
    msg.payload = {0x01};
    writer.value()->Write(msg);
  }
  writer.value()->Close();
  const std::filesystem::path spec = TempPath("sup_" + tag + "_spec.json");
  std::filesystem::remove(spec.string() + ".attempts.jsonl");
  std::filesystem::remove_all(TempPath("reproducers"));
  std::ofstream out(spec);
  out << R"({
    "schema": "adas.sim.runspec/2.0", "run_id": "20261105T000000Z-sup", "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [{
      "name": "sut", "mode": "simulate", "impl": {"kind": "dll", "path": ")"
      << JsonEscape(FixtureLibrary("echo_stub")) << R"("},
      "trigger": "", "clock_period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
      "ports": [{"name": "outputs", "dir": "pro", "kind": "data", "proto_type": "test.Echo",
                 "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 16}],
      "inputs": []
    }],
    "mutations": [], "coherence_verdict": "clean", "readiness_limit_steps": 4, "fallback_max_gap": 4,
    "outputs": {)"
      << outputs_json << R"(},
    "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  return spec;
}

void AddFileWithDependencies(const google::protobuf::FileDescriptor* file, google::protobuf::FileDescriptorSet& set,
                             std::set<std::string>& seen) {
  if (!seen.insert(file->name()).second) return;
  for (int i = 0; i < file->dependency_count(); ++i) AddFileWithDependencies(file->dependency(i), set, seen);
  file->CopyTo(set.add_file());
}

simcore::io::TopicInfo TopicWithSchema(const google::protobuf::Descriptor* descriptor, simcore::io::Provenance provenance) {
  simcore::io::TopicInfo info = simcore::testing::Topic(descriptor->full_name(), provenance);
  google::protobuf::FileDescriptorSet set;
  std::set<std::string> seen;
  AddFileWithDependencies(descriptor->file(), set, seen);
  const std::string text = set.SerializeAsString();
  info.schema_bytes.assign(text.begin(), text.end());
  return info;
}

template <class Message>
std::vector<std::uint8_t> Bytes(const Message& message) {
  std::vector<std::uint8_t> bytes(static_cast<std::size_t>(message.ByteSizeLong()));
  if (!bytes.empty()) message.SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
  return bytes;
}

// Stage `A` is measured (a `LabSample` per control); stage `P` runs the `held_probe` fixture: one run, at 50 ms. The
// probe's bundle folder, given to `simengine` as `--config`, names the gate file that releases its first call.
struct ProbeSetup {
  std::filesystem::path spec;
  std::filesystem::path config_dir;
  std::filesystem::path gate;
  std::string live_name;
};

ProbeSetup WriteProbeSetup(const std::string& tag) {
  using simcore::testing::Message;
  ProbeSetup setup;
  setup.live_name = UniqueName("live");
  setup.gate = TempPath("sup_" + tag + ".gate");
  std::filesystem::remove(setup.gate);
  // The probe's bundle is beside its own copy of the library, where the engine looks for it: the setup names the copy
  // (`--config` is no longer an option of `simengine`, `D31 (1)`).
  const std::filesystem::path library_dir = TempPath("sup_" + tag + "_lib");
  setup.config_dir = library_dir / "config";
  std::filesystem::create_directories(setup.config_dir);
  std::ofstream(setup.config_dir / "default.yaml") << "PROBE_GATE_FILE: " << setup.gate.string() << "\n";
  const std::filesystem::path probe_source = FixtureLibrary("held_probe");
  const std::filesystem::path probe_copy = library_dir / probe_source.filename();
  std::filesystem::copy_file(probe_source, probe_copy, std::filesystem::copy_options::overwrite_existing);

  const std::filesystem::path recording = TempPath("sup_" + tag + ".mcap");
  {
    simcore::io::CodecRegistry registry;
    EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
    auto writer = registry.OpenWrite(recording);
    EXPECT_TRUE(writer.ok());
    const std::map<std::string, simcore::io::TopicInfo> topics = {
        {"/A/out", TopicWithSchema(adas::lab::LabSample::descriptor(), simcore::io::Provenance::kMeasured)},
        {"/P/control", TopicWithSchema(adas::common::CycleControl::descriptor(), simcore::io::Provenance::kSimulated)},
        {"/P/refSync", TopicWithSchema(adas::common::RefSync::descriptor(), simcore::io::Provenance::kSimulated)},
        {"/P/compState", TopicWithSchema(adas::df::CompState::descriptor(), simcore::io::Provenance::kSimulated)}};
    EXPECT_TRUE(writer.value()->Open(recording, topics).ok());
    adas::lab::LabSample sample;
    sample.mutable_sig_header()->set_measurement_counter(9);
    sample.mutable_sig_header()->set_source_timestamp_us(50'000);
    sample.mutable_sig_header()->set_cycle_counter(1);
    sample.mutable_sig_header()->set_sig_status(1);
    sample.set_value(77);
    constexpr std::int64_t kMs = 1'000'000;
    const std::vector<simcore::io::RawMessage> messages = {
        Message("/A/out", 50 * kMs, Bytes(sample)),
        Message("/P/control", 50 * kMs, simcore::testing::Data(9, 50'000, 1)),
        Message("/P/refSync", 50 * kMs, simcore::testing::RefSyncOf(9, {{"in", 9}})),
        Message("/P/compState", 50 * kMs, Bytes(adas::df::CompState()))};
    for (const auto& message : messages) writer.value()->Write(message);
    writer.value()->Close();
  }
  const auto port = [](const std::string& name, const std::string& dir, const std::string& type) {
    return R"({"name": ")" + name + R"(", "dir": ")" + dir + R"(", "kind": "data", "proto_type": ")" + type +
           R"(", "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 8})";
  };
  setup.spec = TempPath("sup_" + tag + "_spec.json");
  std::filesystem::remove(setup.spec.string() + ".attempts.jsonl");
  std::ofstream out(setup.spec);
  out << R"({
    "schema": "adas.sim.runspec/2.0", "run_id": "20261105T000000Z-probe", "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [
      {"name": "A", "mode": "measured", "impl": {"kind": "dll", "path": ""}, "trigger": "", "clock_period_ns": 0,
       "abi_version": 1, "config_bundle_sha256": "", "ports": [)"
      << port("out", "pro", "adas.lab.LabSample") << R"(], "inputs": []},
      {"name": "P", "mode": "simulate", "impl": {"kind": "dll", "path": ")"
      << JsonEscape(probe_copy) << R"("}, "trigger": "control", "clock_period_ns": 0,
       "abi_version": 1, "config_bundle_sha256": "",
       "ports": [)"
      << port("control", "req", "adas.common.CycleControl") << "," << port("in", "req", "adas.lab.LabSample") << ","
      << port("refSync", "pro", "adas.common.RefSync") << "," << port("compState", "pro", "adas.df.CompState")
      << R"(],
       "inputs": [{"port": "in", "producer": "A", "producer_port": "out", "previous_cycle": false}]}
    ],
    "mutations": [], "coherence_verdict": "clean", "readiness_limit_steps": 2, "fallback_max_gap": 4,
    "outputs": {"livemeas": {"name": ")"
      << setup.live_name << R"(", "cycle_slot_count": 8, "cycle_slot_size": 4096, "bulk_slot_count": 2, "bulk_slot_size": 4096}},
    "limits": {"exec_timeout_ms": 0, "severity_exit": "crash"}
  })";
  return setup;
}

// ---- running ---------------------------------------------------------------------------------------------------

struct Ran {
  IsolatedOutcome outcome = IsolatedOutcome::kFailedToStart;
  int exit_code = -1;
  std::string error_text;
  int code() const { return outcome == IsolatedOutcome::kOk ? 0 : exit_code; }
};

Ran RunSimengine(const std::vector<std::string>& args, std::chrono::seconds timeout = std::chrono::seconds(30)) {
  const std::filesystem::path capture = TempPath(UniqueName("stderr") + ".txt");
  const auto result = simcore::module_host::RunIsolatedStage("sup", SimenginePath(), args, timeout, capture);
  return Ran{result.outcome, result.exit_code, ReadAll(capture)};
}

void KillProcess(std::uint32_t pid) {
#if defined(_WIN32)
  HANDLE process = OpenProcess(PROCESS_TERMINATE, FALSE, pid);
  ASSERT_NE(process, nullptr);
  TerminateProcess(process, 0xC0000005u);  // an unhandled-exception status: a crash, not a failure
  CloseHandle(process);
#else
  kill(static_cast<pid_t>(pid), SIGKILL);
#endif
}

// The live measurement once the engine has made it and it runs; null after the wait.
std::unique_ptr<SharedRegion> WaitForLiveMeasurement(const std::string& name, std::chrono::seconds wait) {
  const auto until = std::chrono::steady_clock::now() + wait;
  while (std::chrono::steady_clock::now() < until) {
    std::unique_ptr<SharedRegion> region = SharedRegion::open(name, SharedRegion::Access::kReadOnly);
    if (region != nullptr && region->size() >= sizeof(layout::MeasStatus)) {
      const auto& status = *static_cast<const layout::MeasStatus*>(region->data());
      if (status.magic == layout::kMagic && status.status.load() == 1) return region;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return nullptr;
}

const layout::MeasStatus& StatusOf(const SharedRegion& region) {
  return *static_cast<const layout::MeasStatus*>(region.data());
}

std::vector<std::uint8_t> Copy(const void* base, std::size_t length) {
  const auto* bytes = static_cast<const std::uint8_t*>(base);
  return std::vector<std::uint8_t>(bytes, bytes + length);
}

}  // namespace

// ---- IMP-0103: arguments ---------------------------------------------------------------------------------------

TEST(Supervisor, IMP_0103_SuperviseWithoutADeadlineExitsTwoNamingItAndStartsNoWorker) {
  const std::filesystem::path spec = WriteEchoSpec("nodeadline");
  const Ran ran = RunSimengine({spec.string(), "--supervise"});
  EXPECT_EQ(ran.code(), static_cast<int>(kSimExitConfig));
  EXPECT_TRUE(Has(ran.error_text, "--attempt-timeout-ms")) << ran.error_text;
  EXPECT_FALSE(std::filesystem::exists(spec.string() + ".attempts.jsonl")) << "no worker, so no attempt";
}

TEST(Supervisor, IMP_0103_RestartOnCrashOrAnAttemptDeadlineWithoutSuperviseExitsTwoNamingTheOption) {
  const std::filesystem::path spec = WriteEchoSpec("nosupervise");
  const Ran restart = RunSimengine({spec.string(), "--restart-on-crash", "1"});
  EXPECT_EQ(restart.code(), static_cast<int>(kSimExitConfig));
  EXPECT_TRUE(Has(restart.error_text, "--supervise")) << restart.error_text;
  const Ran deadline = RunSimengine({spec.string(), "--attempt-timeout-ms", "500"});
  EXPECT_EQ(deadline.code(), static_cast<int>(kSimExitConfig));
  EXPECT_TRUE(Has(deadline.error_text, "--supervise")) << deadline.error_text;
  EXPECT_FALSE(std::filesystem::exists(spec.string() + ".attempts.jsonl"));
}

// ---- IMP-0105, IMP-0108: outcomes and the attempts file ---------------------------------------------------------

TEST(Supervisor, IMP_0108_APassExitsZeroAndLeavesOneAttemptsLine) {
  const std::filesystem::path spec = WriteEchoSpec("pass");
  const Ran ran = RunSimengine({spec.string(), "--supervise", "--attempt-timeout-ms", "10000"});
  EXPECT_EQ(ran.code(), 0) << ran.error_text;
  const std::vector<std::string> lines = Lines(spec.string() + ".attempts.jsonl");
  ASSERT_EQ(lines.size(), 1u);
  EXPECT_TRUE(Has(lines[0], "\"attempt\":1")) << lines[0];
  EXPECT_TRUE(Has(lines[0], "\"outcome\":\"ok\""));
  EXPECT_TRUE(Has(lines[0], "\"exit_code\":0"));
  EXPECT_TRUE(Has(lines[0], "\"last\":true"));
  EXPECT_TRUE(Has(lines[0], "\"stages\":\"unknown\""));
  EXPECT_FALSE(std::filesystem::exists(TempPath("reproducers"))) << "a pass writes no reproducer";
}

TEST(Supervisor, IMP_0105_ACrashIsRestartedOnceThenExitsEightWithTwoLinesAndAReproducerWithNoStep) {
  const std::filesystem::path spec = WriteEchoSpec("crash");
  EnvGuard force_abort("ADAS_SIM_TEST_FORCE_ABORT", "1");
  const Ran ran = RunSimengine({spec.string(), "--supervise", "--attempt-timeout-ms", "10000", "--restart-on-crash", "1"});
  EXPECT_EQ(ran.code(), static_cast<int>(kSimExitCrash)) << ran.error_text;
  const std::vector<std::string> lines = Lines(spec.string() + ".attempts.jsonl");
  ASSERT_EQ(lines.size(), 2u);
  for (const std::string& line : lines) {
    EXPECT_TRUE(Has(line, "\"outcome\":\"crash\"")) << line;
    EXPECT_TRUE(Has(line, "\"stages\":\"unknown\"")) << line;
  }
  EXPECT_TRUE(Has(lines[0], "\"last\":false"));
  EXPECT_TRUE(Has(lines[1], "\"last\":true"));
  // IMP-0110, IMP-0111: the reproducer holds the run id and names no step (none completed).
  const std::filesystem::path package = TempPath("reproducers") / "no_step_20261105T000000Z-sup";
  ASSERT_TRUE(std::filesystem::exists(package / "crash.json")) << "no reproducer at " << package.string();
  const std::string crash = ReadAll(package / "crash.json");
  EXPECT_TRUE(Has(crash, "\"run_id\":\"20261105T000000Z-sup\"")) << crash;
  EXPECT_TRUE(Has(crash, "\"failing_cycle\":null")) << crash;
  EXPECT_TRUE(std::filesystem::exists(package / "run_spec.json"));
  EXPECT_TRUE(std::filesystem::exists(package / "stderr.txt"));
}

TEST(Supervisor, IMP_0124_AHungStageIsNamedFromTheCellAndATimeoutExitsSevenWithNoReproducer) {
  const std::filesystem::path spec = WriteEchoSpec("hang");
  EnvGuard name("ADAS_SIL_TEST_STUB_NAME", "supstub");
  EnvGuard hang("ADAS_SIL_TEST_STUB_HANG", "1");
  const Ran ran = RunSimengine({spec.string(), "--supervise", "--attempt-timeout-ms", "300"});
  EXPECT_EQ(ran.code(), static_cast<int>(kSimExitTimeout)) << ran.error_text;
  const std::vector<std::string> lines = Lines(spec.string() + ".attempts.jsonl");
  ASSERT_EQ(lines.size(), 1u);
  EXPECT_TRUE(Has(lines[0], "\"outcome\":\"timeout\"")) << lines[0];
  EXPECT_TRUE(Has(lines[0], "\"stages\":[\"sut\"]")) << lines[0];
  EXPECT_TRUE(Has(lines[0], "\"last\":true"));
  EXPECT_FALSE(std::filesystem::exists(TempPath("reproducers"))) << "a timeout writes no reproducer";
}

TEST(Supervisor, IMP_0106_ACleanFailureIsNotRestartedAndKeepsItsOwnExitCode) {
  const std::filesystem::path spec = WriteEchoSpec("fail");
  EnvGuard name("ADAS_SIL_TEST_STUB_NAME", "supstub");
  EnvGuard bad_abi("ADAS_SIL_TEST_STUB_ABI_VERSION", "999");  // the component refuses to load: a clean failure
  const Ran ran = RunSimengine({spec.string(), "--supervise", "--attempt-timeout-ms", "10000", "--restart-on-crash", "2"});
  EXPECT_EQ(ran.code(), static_cast<int>(kSimExitModule)) << ran.error_text;
  const std::vector<std::string> lines = Lines(spec.string() + ".attempts.jsonl");
  ASSERT_EQ(lines.size(), 1u) << "a fail is never retried";
  EXPECT_TRUE(Has(lines[0], "\"outcome\":\"fail\"")) << lines[0];
  EXPECT_TRUE(Has(lines[0], "\"exit_code\":4"));
  EXPECT_FALSE(std::filesystem::exists(TempPath("reproducers"))) << "a failure writes no reproducer";
}

// ---- IMP-0075, IMP-0107: the hold and the seal -------------------------------------------------------------------

TEST(Supervisor, IMP_0107_AKilledWorkersLiveMeasurementIsSealedCrashAndOnlyThatChanges) {
  const ProbeSetup setup = WriteProbeSetup("seal");
  Ran ran;
  std::thread supervisor([&] {
    ran = RunSimengine({setup.spec.string(), "--supervise", "--attempt-timeout-ms", "60000"}, std::chrono::seconds(90));
  });
  std::unique_ptr<SharedRegion> data = WaitForLiveMeasurement(setup.live_name, std::chrono::seconds(30));
  ASSERT_NE(data, nullptr) << "the held run never showed its live measurement";
  const layout::MeasStatus& status = StatusOf(*data);
  std::unique_ptr<SharedRegion> bulk =
      SharedRegion::open(setup.live_name + layout::kBulkSegmentSuffix, SharedRegion::Access::kReadOnly);
  ASSERT_NE(bulk, nullptr);
  const std::size_t data_size = layout::dataSegmentSize(status);
  const std::size_t bulk_size = layout::bulkSegmentSize(status);
  std::this_thread::sleep_for(std::chrono::milliseconds(300));  // the supervisor's wait holds it meanwhile (IMP-0075)
  const std::vector<std::uint8_t> data_before = Copy(data->data(), data_size);
  const std::vector<std::uint8_t> bulk_before = Copy(bulk->data(), bulk_size);
  ASSERT_EQ(status.status.load(), 1u);
  ASSERT_EQ(status.outcome.load(), 0u);

  KillProcess(status.writerPid);
  supervisor.join();

  EXPECT_EQ(ran.code(), static_cast<int>(kSimExitCrash)) << ran.error_text;
  EXPECT_EQ(status.status.load(), 3u) << "status finished";
  EXPECT_EQ(status.outcome.load(), 3u) << "outcome crash";
  const std::vector<std::uint8_t> data_after = Copy(data->data(), data_size);
  const auto* base = static_cast<const std::uint8_t*>(data->data());
  const std::size_t outcome_at = static_cast<std::size_t>(reinterpret_cast<const std::uint8_t*>(&status.outcome) - base);
  const std::size_t status_at = static_cast<std::size_t>(reinterpret_cast<const std::uint8_t*>(&status.status) - base);
  std::size_t other_differences = 0;
  for (std::size_t i = 0; i < data_size; ++i) {
    const bool in_outcome = i >= outcome_at && i < outcome_at + sizeof(std::uint32_t);
    const bool in_status = i >= status_at && i < status_at + sizeof(std::uint32_t);
    if (!in_outcome && !in_status && data_before[i] != data_after[i]) ++other_differences;
  }
  EXPECT_EQ(other_differences, 0u) << "the seal writes outcome and status and nothing else";
  EXPECT_EQ(Copy(bulk->data(), bulk_size), bulk_before) << "the bulk segment is not touched";
  const std::vector<std::string> lines = Lines(setup.spec.string() + ".attempts.jsonl");
  ASSERT_EQ(lines.size(), 1u);
  EXPECT_TRUE(Has(lines[0], "\"outcome\":\"crash\"")) << lines[0];
  EXPECT_TRUE(Has(lines[0], "\"stages\":[\"P\"]")) << "the cell names the stage that was in its call: " << lines[0];
}

TEST(Supervisor, IMP_0107_APassingSupervisedRunIsLeftPassAndTheSupervisorSealsNothing) {
  const ProbeSetup setup = WriteProbeSetup("pass");
  Ran ran;
  std::thread supervisor([&] {
    ran = RunSimengine({setup.spec.string(), "--supervise", "--attempt-timeout-ms", "60000"}, std::chrono::seconds(90));
  });
  std::unique_ptr<SharedRegion> data = WaitForLiveMeasurement(setup.live_name, std::chrono::seconds(30));
  ASSERT_NE(data, nullptr);
  std::this_thread::sleep_for(std::chrono::milliseconds(300));
  std::ofstream(setup.gate) << "go\n";  // releases the probe's first call: the run goes on to its end
  supervisor.join();
  EXPECT_EQ(ran.code(), 0) << ran.error_text;
  const layout::MeasStatus& status = StatusOf(*data);
  EXPECT_EQ(status.status.load(), 3u);
  EXPECT_EQ(status.outcome.load(), 1u) << "pass, as the engine closed it";
}
