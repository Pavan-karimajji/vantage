// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IT-11` (`WP-14`, `SW-0144`): proves `simcore` is usable without
///   `simengine` -- this file is a SECOND host, built into the ordinary
///   `simcore_tests` gtest binary rather than the `simengine` executable,
///   and it reaches the engine through nothing but `abi/simcore.h`
///   (`simEngineCreate`/`simEngineRun`/`simEngineDestroy`). If this test
///   compiled and ran only because it happened to also link `simengine`'s
///   own translation unit, it would not be evidence for `SW-0144`; it does
///   not link `simengine` at all (see `tests/CMakeLists.txt`).
/// @author Pavan Karimajji

#include "simcore/abi/simcore.h"

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include <gtest/gtest.h>

#include "simcore/io.hpp"
#include "simcore/transport.hpp"

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

// Same escaping discipline `test_ut_abi_writer_and_resolver.cpp`'s own top
// note requires -- an unescaped Windows path fed into a JSON string literal
// was this file's own pre-existing, already-documented `WP-14a`/`WP-15a`
// defect (`ConstructsRunsAndDestroysThroughTheCAbiAlone`'s own listed
// failure throughout this doc set). Fixed live, 2026-08-24.
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

// A tiny real `.mcap` recording -- three heartbeat messages 10ms apart --
// written through the SAME `io::CodecRegistry`/`mcap` codec a real
// recording would go through (never a hand-rolled byte layout).
std::filesystem::path WriteTinyRecording(const std::filesystem::path& path) {
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

// `abi/simcore.h`'s own only input: a Resolved Run Spec on disk (`D-1`).
// One `simulate` stage running the real `echo_stub` fixture, no `req`
// ports (`echo_stub` declares none) -- the recording above exists only to
// drive the cycle grid, not to feed this stage.
std::filesystem::path WriteRunSpec(const std::filesystem::path& spec_path, const std::filesystem::path& recording,
                                   const std::filesystem::path& stub) {
  std::ofstream out(spec_path);
  out << R"({
    "schema": "adas.sim.runspec/1.0",
    "run_id": "20260822T000000Z-it11",
    "spec_sha256": "0000000000000000000000000000000000000000000000000000000000000",
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
    "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  out.close();
  return spec_path;
}

class It11EmbedHost : public ::testing::Test {
 protected:
  void SetUp() override {
#if defined(_WIN32)
    _putenv_s("ADAS_SIL_TEST_STUB_NAME", "run_stub");
    _putenv_s("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs");
#else
    setenv("ADAS_SIL_TEST_STUB_NAME", "run_stub", 1);
    setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs", 1);
#endif
    recording_ = WriteTinyRecording(TempPath("it11_recording.mcap"));
    spec_ = WriteRunSpec(TempPath("it11_run_spec.json"), recording_, EchoStubPath());
  }

  std::filesystem::path recording_;
  std::filesystem::path spec_;
};

TEST_F(It11EmbedHost, ConstructsRunsAndDestroysThroughTheCAbiAlone) {
  ASSERT_GE(simEngineAbiVersion(), 1);

  char err_buf[512] = {0};
  SimExitCode create_exit = kSimExitOk;
  SimEngine* engine =
      simEngineCreate(spec_.string().c_str(), nullptr, 2000, err_buf, sizeof(err_buf), &create_exit);
  ASSERT_NE(engine, nullptr) << "simEngineCreate failed: " << err_buf;

  char run_err[512] = {0};
  const SimExitCode run_exit = simEngineRun(engine, run_err, sizeof(run_err));
  EXPECT_EQ(run_exit, kSimExitOk) << "simEngineRun failed: " << run_err;

  simEngineDestroy(engine);
}

// `UT-ABI-04` (`SW-0425`, `ABI_VERSION 2`, `SM-11`/`vantage`): the real
// mechanism an in-process host needs -- attach a transport, then step tick
// by tick, draining real frames BETWEEN steps (which `simEngineRun`'s one
// blocking call cannot offer). `InProcessTransport` is the SAME class the
// host would really use (zero marshalling, `D-5`); this test IS that
// host, minus a GL window.
TEST_F(It11EmbedHost, AttachTransportThenStepOnceDeliversRealFramesBetweenTicks) {
  char err_buf[512] = {0};
  SimExitCode create_exit = kSimExitOk;
  SimEngine* engine =
      simEngineCreate(spec_.string().c_str(), nullptr, 2000, err_buf, sizeof(err_buf), &create_exit);
  ASSERT_NE(engine, nullptr) << "simEngineCreate failed: " << err_buf;

  simcore::transport::InProcessTransport transport(/*depth=*/8);
  // `InProcessTransport` multiply-inherits `ITransport` AND
  // `TransportPublisher` -- converting to the correct base type HERE
  // (while the compiler still has both types) lets it apply the base-
  // class pointer adjustment before the address is erased to `void*`;
  // erasing straight from `InProcessTransport*` would hand
  // `simEngineAttachTransport` an address for the WRONG subobject the
  // instant `TransportPublisher` is not the first base (found live: this
  // is exactly what happened on the first attempt, silently reaching no
  // real frames rather than crashing).
  simcore::transport::TransportPublisher* publisher = &transport;
  simEngineAttachTransport(engine, publisher);

  uint32_t engine_version = 0;
  ASSERT_EQ(transport.attach(simcore::transport::InProcessTransport::kProtocolVersion, &engine_version),
            adas::transport::AttachResult::kOk);

  int cycles_stepped = 0;
  std::vector<std::vector<uint8_t>> outputs;
  for (;;) {
    char step_err[512] = {0};
    int32_t keep_going = 0;
    const SimExitCode step_exit = simEngineStepOnce(engine, step_err, sizeof(step_err), &keep_going);
    ASSERT_EQ(step_exit, kSimExitOk) << "simEngineStepOnce failed: " << step_err;
    if (keep_going == 0) break;  // exhausted -- no cycle was actually stepped this call
    ++cycles_stepped;

    // Drain whatever this cycle published BEFORE the next step -- the
    // real, per-tick pump shape a live renderer would use, proving the
    // frame is available between steps, not just accumulated and read
    // back at the end.
    adas::transport::PortFrame frame{};
    while (transport.tryReceive(&frame)) {
      if (std::strcmp(frame.portName, "sut.outputs") == 0) {
        outputs.emplace_back(frame.data, frame.data + frame.size);
      }
    }
  }

  EXPECT_EQ(cycles_stepped, 3);
  ASSERT_EQ(outputs.size(), 3u);
  EXPECT_TRUE(transport.engineAlive());

  simEngineDestroy(engine);
}

TEST_F(It11EmbedHost, StepOnceWithNoConstructedEngineIsAConfigExitNotACrash) {
  char err_buf[512] = {0};
  int32_t keep_going = 1;
  const SimExitCode exit_code = simEngineStepOnce(nullptr, err_buf, sizeof(err_buf), &keep_going);
  EXPECT_EQ(exit_code, kSimExitConfig);
  EXPECT_EQ(keep_going, 0);
  EXPECT_NE(err_buf[0], '\0');
}

TEST_F(It11EmbedHost, MissingRunSpecFileIsAConfigExitNotACrash) {
  char err_buf[512] = {0};
  SimExitCode exit_code = kSimExitOk;
  SimEngine* engine = simEngineCreate((TempPath("it11_does_not_exist.json")).string().c_str(), nullptr, 0, err_buf,
                                       sizeof(err_buf), &exit_code);
  EXPECT_EQ(engine, nullptr);
  EXPECT_NE(exit_code, kSimExitOk);
  EXPECT_NE(err_buf[0], '\0');
}

}  // namespace
