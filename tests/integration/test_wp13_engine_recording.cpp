// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `VNT-WP-09a-R1`, through the real C ABI (`simEngineCreate`/`simEngineRun`):
///     `IMP-0052` -- an engine run's `manifest` (`RCT_Architecture.md` section 6a): `run_kind: resim`, the input's
///       `source_kind`, the simulated stages with their `build_id`, each port's `record` policy, no logging time;
///       an input that states no `source_kind`, or holds a topic with no origin, is refused naming it.
///     `IMP-0059` -- the `config_bundle` block: exactly the simulated stages' bundle files, texts as on disk; none
///       for a `measured` stage, none when no stage has a bundle folder.
///     `IMP-0060` -- with an exec timeout set and one thread the component sees ONE thread id over many calls; a
///       call that blocks past the timeout ends the run with `kSimExitTimeout`; the process then refuses a
///       second engine, saying to restart it.
/// @author Pavan Karimajji

#include "simcore/abi/simcore.h"

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include <gtest/gtest.h>

#include "abi/engine_access.hpp"
#include "simcore/io.hpp"

namespace {

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

// A test that provokes the timeout refusal goes on in the same process: clear it however the test ends.
struct TimeoutRefusalGuard {
  ~TimeoutRefusalGuard() { SimEngineClearTimeoutRefusalForTest(); }
};

#if defined(_WIN32)
constexpr const char* kStubName = "echo_stub.dll";
constexpr const char* kProbeName = "exec_probe.dll";
#else
constexpr const char* kStubName = "libecho_stub.so";
constexpr const char* kProbeName = "libexec_probe.so";
#endif

std::filesystem::path FixturePath(const char* name) { return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / name; }

std::filesystem::path FreshDir(const std::string& name) {
  const std::filesystem::path dir = std::filesystem::temp_directory_path() / name;
  std::filesystem::remove_all(dir);
  std::filesystem::create_directories(dir);
  return dir;
}

std::string JsonEscape(const std::filesystem::path& path) {
  std::string out;
  for (const char c : path.generic_string()) {
    if (c == '\\' || c == '"') out.push_back('\\');
    out.push_back(c);
  }
  return out;
}

void WriteText(const std::filesystem::path& path, const std::string& text) {
  std::filesystem::create_directories(path.parent_path());
  std::ofstream out(path, std::ios::binary);
  out << text;
}

std::string ReadText(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  std::ostringstream text;
  text << in.rdbuf();
  return text.str();
}

std::vector<std::uint8_t> EncodeAbiPortDouble(double value) {
  std::vector<std::uint8_t> bytes(9);
  bytes[0] = 0x09;
  std::memcpy(bytes.data() + 1, &value, sizeof(double));
  return bytes;
}

// A recording of `abi_test.AbiPort` on `/meas/objects`, `cycles` messages 10 ms apart. `manifest_yaml` empty
// writes no `manifest` block; `origin` unknown writes the topic with no stated origin.
std::filesystem::path WriteInput(const std::filesystem::path& path, const std::string& manifest_yaml,
                                 simcore::io::Provenance origin, int cycles = 3) {
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(path);
  EXPECT_TRUE(writer.ok());
  simcore::io::TopicInfo info;
  info.schema_name = "abi_test.AbiPort";
  info.provenance = origin;
  EXPECT_TRUE(writer.value()->Open(path, {{"/meas/objects", info}}).ok());
  if (!manifest_yaml.empty()) writer.value()->WriteMetaBlock("manifest", {{"yaml", manifest_yaml}});
  for (int i = 0; i < cycles; ++i) {
    simcore::io::RawMessage msg;
    msg.topic = "/meas/objects";
    msg.log_time_ns = static_cast<std::int64_t>(i) * 10'000'000;
    msg.payload = EncodeAbiPortDouble(7.0);
    writer.value()->Write(msg);
  }
  writer.value()->Close();
  return path;
}

// `meas` (measured) feeds `sut` (simulate, `library`); `exec_timeout_ms` as the run setup's limit.
std::string RunSpecJson(const std::filesystem::path& recording, const std::filesystem::path& library,
                        const std::string& outputs_json, int exec_timeout_ms) {
  std::ostringstream out;
  out << R"({
    "schema": "adas.sim.runspec/2.0",
    "run_id": "20261102T000000Z-wp13",
    "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [
      {
        "name": "meas", "mode": "measured",
        "impl": {"kind": "dll", "path": ""},
        "trigger": "", "clock_period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
        "ports": [{"name": "objects", "dir": "pro", "kind": "data", "proto_type": "abi_test.AbiPort",
                   "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 16}],
        "inputs": []
      },
      {
        "name": "sut", "mode": "simulate",
        "impl": {"kind": "dll", "path": ")"
      << JsonEscape(library) << R"("},
        "trigger": "", "clock_period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
        "ports": [{"name": "objects", "dir": "req", "kind": "data", "proto_type": "abi_test.AbiPort",
                   "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 16}],
        "inputs": [{"port": "objects", "producer": "meas", "producer_port": "objects", "previous_cycle": false}]
      }
    ],
    "mutations": [],
    "coherence_verdict": "clean", "readiness_limit_steps": 4, "fallback_max_gap": 4,
    "outputs": )"
      << outputs_json << R"(,
    "limits": {"exec_timeout_ms": )"
      << exec_timeout_ms << R"(, "severity_exit": "crash"}
  })";
  return out.str();
}

std::string OutputsJson(const std::filesystem::path& output) {
  return R"({"path": ")" + JsonEscape(output) + R"(", "codec": "mcap"})";
}

struct Created {
  SimEngine* engine = nullptr;
  SimExitCode exit_code = kSimExitOk;
  std::string error;
};

Created Create(const std::filesystem::path& spec_path) {
  Created created;
  char err[1024] = {0};
  created.engine = simEngineCreate(spec_path.string().c_str(), nullptr, 0, err, sizeof(err), &created.exit_code);
  created.error = err;
  return created;
}

SimExitCode RunAll(SimEngine* engine, std::string* error = nullptr) {
  char err[1024] = {0};
  const SimExitCode code = simEngineRun(engine, err, sizeof(err));
  if (error != nullptr) *error = err;
  return code;
}

// Runs the spec to completion; the engine is destroyed (and the recording closed) before this returns.
void RunToCompletion(const std::filesystem::path& spec_path) {
  Created created = Create(spec_path);
  ASSERT_NE(created.engine, nullptr) << created.error;
  std::string error;
  EXPECT_EQ(RunAll(created.engine, &error), kSimExitOk) << error;
  simEngineDestroy(created.engine);
}

struct Meta {
  std::optional<std::map<std::string, std::string>> manifest;
  std::optional<std::map<std::string, std::string>> config_bundle;
};

Meta ReadMeta(const std::filesystem::path& recording) {
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto reader = registry.OpenRead(recording);
  EXPECT_TRUE(reader.ok());
  EXPECT_TRUE(reader.value()->Open(recording).ok());
  Meta meta{reader.value()->GetMetaBlock("manifest"), reader.value()->GetMetaBlock("config_bundle")};
  reader.value()->Close();
  return meta;
}

const char kSourceKind[] = "source_kind: synthetic\n";

}  // namespace

// IMP-0059
TEST(Wp13ConfigBundle, TheRunEmbedsTheSimulatedStagesBundleFilesAndNoMeasuredStages) {
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "wp13_bundle");
  EnvGuard schema_guard("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", "1");
  const std::filesystem::path dir = FreshDir("wp13_bundle");
  std::filesystem::create_directories(dir / "lib");
  std::filesystem::copy_file(FixturePath(kStubName), dir / "lib" / kStubName, std::filesystem::copy_options::overwrite_existing);
  WriteText(dir / "lib" / "config" / "default.yaml", "SUT_GAIN: 1.5\n");
  WriteText(dir / "lib" / "config" / "vehicle" / "ego_params.yaml", "EGO_WHEELBASE_M: 2.7\r\nEGO_TRACK_M: 1.6\r\n");
  const std::filesystem::path recording = WriteInput(dir / "in.mcap", kSourceKind, simcore::io::Provenance::kMeasured);
  const std::filesystem::path output = dir / "out.mcap";
  WriteText(dir / "spec.json", RunSpecJson(recording, dir / "lib" / kStubName, OutputsJson(output), 2000));

  RunToCompletion(dir / "spec.json");

  const Meta meta = ReadMeta(output);
  ASSERT_TRUE(meta.config_bundle.has_value()) << "no config_bundle block";
  const std::map<std::string, std::string> expected = {
      {"sut/default.yaml", "SUT_GAIN: 1.5\n"},
      {"sut/vehicle/ego_params.yaml", "EGO_WHEELBASE_M: 2.7\r\nEGO_TRACK_M: 1.6\r\n"}};
  EXPECT_EQ(*meta.config_bundle, expected) << "exactly the simulated stage's two files, texts as on disk; none for `meas`";
}

TEST(Wp13ConfigBundle, NoStageWithABundleFolderGivesNoBlock) {
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "wp13_nobundle");
  EnvGuard schema_guard("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", "1");
  const std::filesystem::path dir = FreshDir("wp13_nobundle");
  std::filesystem::create_directories(dir / "lib");
  std::filesystem::copy_file(FixturePath(kStubName), dir / "lib" / kStubName, std::filesystem::copy_options::overwrite_existing);
  const std::filesystem::path recording = WriteInput(dir / "in.mcap", kSourceKind, simcore::io::Provenance::kMeasured);
  const std::filesystem::path output = dir / "out.mcap";
  WriteText(dir / "spec.json", RunSpecJson(recording, dir / "lib" / kStubName, OutputsJson(output), 2000));

  RunToCompletion(dir / "spec.json");

  const Meta meta = ReadMeta(output);
  EXPECT_TRUE(meta.manifest.has_value());
  EXPECT_FALSE(meta.config_bundle.has_value()) << "a run whose stages have no bundle folder writes no block";
}

TEST(Wp13ConfigBundle, WithoutAnOutputPathNothingIsReadOrRefused) {
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "wp13_nooutput");
  EnvGuard schema_guard("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", "1");
  const std::filesystem::path dir = FreshDir("wp13_nooutput");
  // The input states no source_kind and no origin: only a run that writes a recording needs them.
  const std::filesystem::path recording = WriteInput(dir / "in.mcap", "", simcore::io::Provenance::kUnknown);
  WriteText(dir / "spec.json", RunSpecJson(recording, FixturePath(kStubName), R"({"path": "", "codec": "mcap"})", 2000));

  RunToCompletion(dir / "spec.json");
}

// IMP-0052
TEST(Wp13Manifest, AnEngineRunStatesItsKindsItsComponentsAndItsPolicies) {
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "wp13_manifest");
  EnvGuard schema_guard("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", "1");
  const std::filesystem::path dir = FreshDir("wp13_manifest");
  const std::filesystem::path recording = WriteInput(dir / "in.mcap", kSourceKind, simcore::io::Provenance::kMocked);
  const std::filesystem::path output = dir / "out.mcap";
  WriteText(dir / "spec.json", RunSpecJson(recording, FixturePath(kStubName), OutputsJson(output), 2000));

  RunToCompletion(dir / "spec.json");

  const Meta meta = ReadMeta(output);
  ASSERT_TRUE(meta.manifest.has_value() && meta.manifest->count("yaml") == 1) << "no manifest block with a yaml entry";
  const std::string& yaml = meta.manifest->at("yaml");
  EXPECT_NE(yaml.find("manifest_version: 1\n"), std::string::npos) << yaml;
  EXPECT_NE(yaml.find("run_kind: resim\n"), std::string::npos) << yaml;
  EXPECT_NE(yaml.find("source_kind: 'synthetic'\n"), std::string::npos) << yaml;
  // `IMP-0063`: the component entry now also carries its library's hash (keys sorted: build_id, library_sha256, name).
  EXPECT_NE(yaml.find("- build_id: 'test'\n  library_sha256: '"), std::string::npos) << yaml;
  EXPECT_NE(yaml.find("'\n  name: 'sut'\n"), std::string::npos) << yaml;
  for (const char* key : {"run_id: '", "host: '", "process_nonce: '", "run_spec_sha256: '", "divergence: '"}) {
    EXPECT_NE(yaml.find(std::string("\n") + key), std::string::npos) << key << "\n" << yaml;
  }
  EXPECT_EQ(yaml.find("config_bundle_sha256"), std::string::npos) << "a bundle hash stays in config_bundle (D29 (1))";
  EXPECT_NE(yaml.find("  meas.objects: 'full'\n"), std::string::npos) << yaml;
  EXPECT_EQ(yaml.find("created_utc"), std::string::npos) << "the engine has no logging time to state:\n" << yaml;
}

TEST(Wp13Manifest, AnInputThatStatesNoSourceKindIsRefusedNamingIt) {
  const std::filesystem::path dir = FreshDir("wp13_nokind");
  const std::filesystem::path recording = WriteInput(dir / "in.mcap", "", simcore::io::Provenance::kMeasured);
  WriteText(dir / "spec.json", RunSpecJson(recording, FixturePath(kStubName), OutputsJson(dir / "out.mcap"), 2000));

  const Created created = Create(dir / "spec.json");
  EXPECT_EQ(created.engine, nullptr);
  EXPECT_NE(created.error.find("source_kind"), std::string::npos) << created.error;
  EXPECT_NE(created.error.find("in.mcap"), std::string::npos) << created.error;
}

TEST(Wp13Manifest, AnInputTopicWithNoOriginIsRefusedNamingIt) {
  const std::filesystem::path dir = FreshDir("wp13_noorigin");
  const std::filesystem::path recording = WriteInput(dir / "in.mcap", kSourceKind, simcore::io::Provenance::kUnknown);
  WriteText(dir / "spec.json", RunSpecJson(recording, FixturePath(kStubName), OutputsJson(dir / "out.mcap"), 2000));

  const Created created = Create(dir / "spec.json");
  EXPECT_EQ(created.engine, nullptr);
  EXPECT_NE(created.error.find("/meas/objects"), std::string::npos) << created.error;
  EXPECT_NE(created.error.find("in.mcap"), std::string::npos) << created.error;
}

// IMP-0060
TEST(Wp13CallThread, UnderAnExecTimeoutOneThreadMakesEveryCall) {
  const std::filesystem::path dir = FreshDir("wp13_callthread");
  std::filesystem::create_directories(dir / "lib");
  std::filesystem::copy_file(FixturePath(kProbeName), dir / "lib" / kProbeName, std::filesystem::copy_options::overwrite_existing);
  const std::filesystem::path log = dir / "calls.log";
  WriteText(dir / "lib" / "config" / "default.yaml",
            "PROBE_STAGE_NAME: sut\nPROBE_LOG_FILE: " + log.generic_string() + "\nPROBE_SPIN_MS: 0\n");
  const std::filesystem::path recording =
      WriteInput(dir / "in.mcap", kSourceKind, simcore::io::Provenance::kMeasured, /*cycles=*/30);
  WriteText(dir / "spec.json", RunSpecJson(recording, dir / "lib" / kProbeName, OutputsJson(dir / "out.mcap"), 2000));

  RunToCompletion(dir / "spec.json");

  std::set<std::string> threads;
  std::size_t calls = 0;
  std::istringstream lines(ReadText(log));
  for (std::string line; std::getline(lines, line);) {
    if (line.find("event=enter") == std::string::npos) continue;
    ++calls;
    const std::size_t at = line.find("thread=");
    ASSERT_NE(at, std::string::npos) << line;
    threads.insert(line.substr(at, line.find(' ', at) - at));
  }
  EXPECT_GE(calls, 20u) << "the component was called on most cycles";
  EXPECT_EQ(threads.size(), 1u) << "one call thread for every call under limits.exec_timeout_ms";
}

TEST(Wp13CallThread, ACallPastTheTimeoutEndsTheRunWithTimeoutAndTheProcessRefusesASecondEngine) {
  TimeoutRefusalGuard clear_when_done;
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "wp13_hang");
  EnvGuard schema_guard("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", "1");
  EnvGuard hang_guard("ADAS_SIL_TEST_STUB_HANG", "1");
  const std::filesystem::path dir = FreshDir("wp13_hang");
  const std::filesystem::path recording = WriteInput(dir / "in.mcap", kSourceKind, simcore::io::Provenance::kMeasured);
  WriteText(dir / "spec.json", RunSpecJson(recording, FixturePath(kStubName), OutputsJson(dir / "out.mcap"), 100));

  Created first = Create(dir / "spec.json");
  ASSERT_NE(first.engine, nullptr) << first.error;
  std::string error;
  EXPECT_EQ(RunAll(first.engine, &error), kSimExitTimeout) << error;

  const Created second = Create(dir / "spec.json");
  EXPECT_EQ(second.engine, nullptr) << "a second engine in the process after a timeout";
  EXPECT_NE(second.error.find("restart"), std::string::npos) << second.error;
  // The first engine is left as it is: its component call may still be running, and is never joined.
}
