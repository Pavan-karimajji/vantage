// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-EXE-05` (`SW-0148`, `WP-14`): every terminating path returns a
///   member of the published `ExitCode` set, exercised through the real
///   `simengine` binary rather than asserted against the mapping table
///   alone.
///
///   **Coverage, honestly, of all eight codes:**
///     - `Ok` (0), `Config` (2), `Infra` (6), `Crash` (8), `Timeout` (7):
///       each has a REAL path in this codebase today and each is
///       exercised here.
///     - `Module` (4, `Kind::Contract`'s default): the only real call
///       sites (`Component::Load`'s ABI-version check / manifest decode
///       failure, `src/simcore/module_host/component.cpp`) need a fixture
///       library that reports a WRONG ABI version or an unparsable
///       manifest -- every fixture this repo ships (`echo_stub`,
///       `c5_bundle_fixture`) reports the real, current ABI version and a
///       well-formed manifest. Building a new fixture is outside `WP-14`'s
///       own stated file scope (`main.cpp`/`isolate.cpp`/`simcore.h` and
///       their tests) -- **honestly not exercised here**, not faked.
///     - `Coherence` (3) and `Input` (5): `docs/v2/errors.yaml`'s own
///       words -- "a coherence-graph verdict blocked the run (`WP-20`)"
///       and "a damaged/refused recording (`WP-19`)" -- name the work
///       packages that would create the call sites that return these
///       codes. Neither `WP-20` nor `WP-19` has landed (confirmed live:
///       `grep -rn coherence_verdict src/simcore include/simcore` outside
///       `runspec/` returns nothing at the time of this row). There is no
///       path in `simcore` today capable of returning either code --
///       **structurally unreachable, not merely untested.**
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

#include <gtest/gtest.h>

#include "simcore/abi/simcore.h"
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

std::filesystem::path TempPath(const std::string& name) { return std::filesystem::temp_directory_path() / name; }
std::filesystem::path SimenginePath() { return std::filesystem::path(SIMENGINE_EXECUTABLE); }

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

std::filesystem::path WriteTinyRecording(const std::filesystem::path& path) {
  simcore::io::CodecRegistry registry;
  simcore::io::codecs::RegisterMcap(registry);
  auto writer = registry.OpenWrite(path);
  simcore::io::TopicInfo heartbeat;
  heartbeat.schema_name = "test.Heartbeat";
  writer.value()->Open(path, {{"/dummy/heartbeat", heartbeat}});
  simcore::io::RawMessage msg;
  msg.topic = "/dummy/heartbeat";
  msg.log_time_ns = 0;
  msg.payload = {0x01};
  writer.value()->Write(msg);
  writer.value()->Close();
  return path;
}

// A single `simulate` stage running `echo_stub`, optionally hanging inside
// `adasExec()` forever (`ADAS_SIL_TEST_STUB_HANG=1`) -- the real fixture
// this repo already ships for exactly this purpose (`WP-10`'s own tests).
std::filesystem::path WriteStubRunSpec(const std::filesystem::path& spec_path, const std::filesystem::path& recording) {
  std::ofstream out(spec_path);
  out << R"({
    "schema": "adas.sim.runspec/1.0", "run_id": "20260822T000000Z-exe05",
    "spec_sha256": "0", "grid": {"step_ns": 10000000},
    "sources": [{"path": ")"
      << recording.string() << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [{
      "name": "sut", "mode": "simulate",
      "impl": {"kind": "dll", "path": ")"
      << EchoStubPath().string() << R"(", "pattern": "", "search": []},
      "period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
      "ports": [], "inputs": []
    }],
    "mutations": [], "order": ["sut"],
    "coherence": {"verdict": "clean"}, "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  return spec_path;
}

}  // namespace

TEST(UtExe05ExitCodes, OkOnARealSuccessfulRun) {
  const auto recording = WriteTinyRecording(TempPath("ut_exe_05_ok.mcap"));
  const auto spec = WriteStubRunSpec(TempPath("ut_exe_05_ok.json"), recording);
  EnvGuard name("ADAS_SIL_TEST_STUB_NAME", "exe05");
  const auto result =
      simcore::module_host::RunIsolatedStage("sut", SimenginePath(), {spec.string()}, std::chrono::seconds(5));
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kOk);
  EXPECT_EQ(result.exit_code, static_cast<int>(kSimExitOk));
}

TEST(UtExe05ExitCodes, ConfigOnBadArguments) {
  const auto result = simcore::module_host::RunIsolatedStage("sut", SimenginePath(), {}, std::chrono::seconds(5));
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kFail);
  EXPECT_EQ(result.exit_code, static_cast<int>(kSimExitConfig));
}

TEST(UtExe05ExitCodes, InfraOnAnUnreadableRunSpecFile) {
  const auto result = simcore::module_host::RunIsolatedStage(
      "sut", SimenginePath(), {TempPath("ut_exe_05_missing.json").string()}, std::chrono::seconds(5));
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kFail);
  EXPECT_EQ(result.exit_code, static_cast<int>(kSimExitInfra));
}

TEST(UtExe05ExitCodes, CrashOnARealAbnormalTerminationWithNoRestartConfigured) {
  EnvGuard force_abort("ADAS_SIM_TEST_FORCE_ABORT", "1");
  const auto result = simcore::module_host::RunIsolatedStage(
      "sut", SimenginePath(), {TempPath("ut_exe_05_unused.json").string()}, std::chrono::seconds(5));
  // No `--restart-on-crash`: this IS the unsupervised, single-process path
  // -- the process that aborts is this one, so THIS call observes the
  // signal directly, never a mapped ExitCode (there is no clean exit to
  // map -- SW-0148's Accept is about codes a process RETURNS, and a
  // genuinely crashed process returns nothing; `Crash` (8) is what the
  // published set assigns to this outcome one layer up, at whichever
  // supervisor/orchestrator is watching -- exercised distinctly below).
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kCrashed);
}

TEST(UtExe05ExitCodes, CrashIsTheSupervisorsOwnExitCodeOnceRestartsAreExhausted) {
  EnvGuard force_abort("ADAS_SIM_TEST_FORCE_ABORT", "1");
  const auto result = simcore::module_host::RunIsolatedStage(
      "sut", SimenginePath(), {TempPath("ut_exe_05_unused.json").string(), "--restart-on-crash", "1"},
      std::chrono::seconds(10));
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kFail);
  EXPECT_EQ(result.exit_code, static_cast<int>(kSimExitCrash));
}

TEST(UtExe05ExitCodes, TimeoutWhenASupervisedAttemptNeverReturns) {
  const auto recording = WriteTinyRecording(TempPath("ut_exe_05_timeout.mcap"));
  const auto spec = WriteStubRunSpec(TempPath("ut_exe_05_timeout.json"), recording);
  EnvGuard name("ADAS_SIL_TEST_STUB_NAME", "exe05timeout");
  EnvGuard hang("ADAS_SIL_TEST_STUB_HANG", "1");
  // No engine-level `--timeout-ms`: `adasExec()` spins forever with no
  // per-call watchdog wrapping it, so the ONLY thing that can end this
  // attempt is the supervisor's own process-level deadline
  // (`--attempt-timeout-ms`) -- a real, OS-observed timeout, not a
  // fabricated one.
  const auto result = simcore::module_host::RunIsolatedStage(
      "sut", SimenginePath(),
      {spec.string(), "--restart-on-crash", "1", "--attempt-timeout-ms", "300"}, std::chrono::seconds(10));
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kFail);
  EXPECT_EQ(result.exit_code, static_cast<int>(kSimExitTimeout));
}
