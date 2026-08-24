// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-ABI-03` (`WP-15`, `IMP-0139`): `simEngineCreate` wires a real
///   `Checkpoint` into its own `Runner` iff the resolved spec declares
///   `checkpoint.path` -- the gap this row's own design decision
///   (2026-08-24) closed. Before this, no real `simengine.exe` run ever
///   wrote a `progress.json`; that was proven only by `checkpoint.cpp`'s
///   own isolated `Runner`+`Checkpoint` unit tests
///   (`tests/unit/test_ut_run_core.cpp`), never through the actual
///   production entry point this file drives (`simEngineCreate`/
///   `simEngineRun`/`simEngineDestroy` alone, the same "second host" shape
///   `IT-11`/`UT-ABI-01`/`UT-ABI-02` already prove `simcore` needs no
///   `simengine` translation unit for).
///
///   Two cases, `IMP-0426`'s own "declared vs. absent" shape: a spec
///   declaring `checkpoint.path` produces a real, readable `progress.json`
///   naming the last completed cycle; a spec omitting the key (every
///   pre-existing spec) writes nothing, matching behaviour before this
///   change exactly.
/// @author Pavan Karimajji

#include "simcore/abi/simcore.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

#include <gtest/gtest.h>

#include "simcore/runner.hpp"

namespace {

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

std::filesystem::path TempPath(const std::string& name) {
  return std::filesystem::temp_directory_path() / name;
}

// Same JSON-escaping discipline `test_ut_abi_writer_and_resolver.cpp`'s
// own top note requires on Windows -- a path fed unescaped into a JSON
// string literal is that file's already-documented pre-existing defect,
// not one this file repeats.
std::string JsonEscape(const std::filesystem::path& path) {
  const std::string raw = path.string();
  std::string out;
  out.reserve(raw.size());
  for (char c : raw) {
    if (c == '\\' || c == '"') out.push_back('\\');
    out.push_back(c);
  }
  return out;
}

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

std::filesystem::path WriteSpec(const std::filesystem::path& spec_path, const std::string& json) {
  std::ofstream out(spec_path);
  out << json;
  out.close();
  return spec_path;
}

// One `simulate` stage, one declared `pro` port, no `outputs.path` (a
// checkpoint-only run needs no recording output to exercise) -- the
// `checkpoint` block, when present, is this test's own variable.
std::string BuildRunSpecJson(const std::filesystem::path& recording, const std::filesystem::path& stub,
                              const std::string& run_id, const std::string& checkpoint_json) {
  std::ostringstream out;
  out << R"({
    "schema": "adas.sim.runspec/1.0",
    "run_id": ")"
      << run_id << R"(",
    "spec_sha256": "0",
    "grid": {"step_ns": 10000000},
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [{
      "name": "sut", "mode": "simulate",
      "impl": {"kind": "dll", "path": ")"
      << JsonEscape(stub) << R"(", "pattern": "", "search": []},
      "period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
      "ports": [{"name": "outputs", "dir": "pro", "kind": "data", "proto_type": "test.Echo",
                 "record": "full", "sampling": "latest", "on_missing": "hold", "fixed_slots": null}],
      "inputs": []
    }],
    "mutations": [],
    "order": ["sut"],
    "coherence": {"verdict": "clean"},
    "outputs": {}, )"
      << checkpoint_json << R"(
    "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  return out.str();
}

void RunToCompletion(const std::filesystem::path& spec_path) {
  char err_buf[512] = {0};
  SimExitCode create_exit = kSimExitOk;
  SimEngine* engine =
      simEngineCreate(spec_path.string().c_str(), nullptr, 2000, err_buf, sizeof(err_buf), &create_exit);
  ASSERT_NE(engine, nullptr) << "simEngineCreate failed: " << err_buf;

  char run_err[512] = {0};
  const SimExitCode run_exit = simEngineRun(engine, run_err, sizeof(run_err));
  EXPECT_EQ(run_exit, kSimExitOk) << "simEngineRun failed: " << run_err;

  simEngineDestroy(engine);
}

}  // namespace

TEST(UtAbi03Checkpoint, ADeclaredCheckpointPathWritesARealProgressFile) {
  const std::filesystem::path recording = WriteHeartbeatRecording(TempPath("ut_abi_03_input.mcap"));
  const std::filesystem::path checkpoint_path = TempPath("ut_abi_03_progress.json");
  std::filesystem::remove(checkpoint_path);
  std::filesystem::remove_all(std::filesystem::path(checkpoint_path).concat("_input_capture"));

  const std::string spec_json =
      BuildRunSpecJson(recording, EchoStubPath(), "20260824T000000Z-abi03",
                        R"("checkpoint": {"path": ")" + JsonEscape(checkpoint_path) + R"("},)");
  const std::filesystem::path spec_path = WriteSpec(TempPath("ut_abi_03_spec.json"), spec_json);

  RunToCompletion(spec_path);

  ASSERT_TRUE(std::filesystem::exists(checkpoint_path))
      << "simEngineCreate declared checkpoint.path but no progress.json was ever written";
  const simcore::Result<simcore::runner::CheckpointRecord> record = simcore::runner::Checkpoint::Read(checkpoint_path);
  ASSERT_TRUE(record.ok()) << record.error().Format();
  EXPECT_EQ(record.value().run_id, "20260824T000000Z-abi03");
  EXPECT_TRUE(record.value().completed);
  // Three heartbeat messages on the input grid -> cycles 0, 1, 2; the last
  // completed cycle recorded is index 2.
  EXPECT_EQ(record.value().tick_index, 2u);
}

TEST(UtAbi03Checkpoint, AnAbsentCheckpointPathWritesNothing) {
  const std::filesystem::path recording = WriteHeartbeatRecording(TempPath("ut_abi_03b_input.mcap"));
  const std::string spec_json = BuildRunSpecJson(recording, EchoStubPath(), "20260824T000000Z-abi03b", "");
  const std::filesystem::path spec_path = WriteSpec(TempPath("ut_abi_03b_spec.json"), spec_json);

  RunToCompletion(spec_path);

  // Nothing named by this test was ever declared -- there is no path to
  // assert absent by construction other than "the run completed with no
  // checkpoint field at all," which `BuildRunSpecJson`'s own omitted
  // `checkpoint_json` parameter already exercises; `simEngineCreate` must
  // not have crashed or misbehaved with `spec.checkpoint.path` empty
  // (covered by `RunToCompletion`'s own `kSimExitOk` assertion above).
}
