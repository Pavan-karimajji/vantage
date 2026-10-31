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
///     - `Module` (4, `Kind::Contract`'s default): `Component::Load`'s
///       ABI-version check (`src/simcore/module_host/component.cpp`)
///       compares `adasAbiVersion()`'s return value against `kAbiVersion`
///       and nothing else -- confirmed live by reading that function
///       before adding a fixture for it, 2026-08-24. `echo_stub` gained an
///       env-gated `ADAS_SIL_TEST_STUB_ABI_VERSION` (default: the real
///       version) so this repo's existing fixture can report a wrong one
///       with no new DLL. **Exercised for real below**
///       (`ModuleOnAnAbiVersionMismatch`).
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

// Same escaping discipline `test_ut_abi_writer_and_resolver.cpp`'s own top
// note requires -- a Windows path fed unescaped into a JSON string literal
// was this file's own pre-existing, already-documented defect (`WP-14a`/
// `WP-15a`), found live re-checking this row 2026-08-24: it failed
// `OkOnARealSuccessfulRun` and `TimeoutWhenASupervisedAttemptNeverReturns`
// on `vs2026` for the same reason every other pre-existing-failure note in
// this doc set already names, not a platform limitation.
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
    "schema": "adas.sim.runspec/2.0", "run_id": "20260822T000000Z-exe05",
    "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [{
      "name": "sut", "mode": "simulate",
      "impl": {"kind": "dll", "path": ")"
      << JsonEscape(EchoStubPath()) << R"(", "pattern": "", "search": []},
      "trigger": "", "clock_period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
      "ports": [], "inputs": []
    }],
    "mutations": [],
    "coherence_verdict": "clean", "readiness_limit_steps": 4, "fallback_max_gap": 4, "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
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

// IMP-0005: `--threads N` (N >= 1, default 1) is a simengine option; a value
// below 1 or not a whole number is a usage error, never clamped.
TEST(UtExe05ExitCodes, ThreadsOptionTakesAWholeNumberOfAtLeastOne) {
  const auto recording = WriteTinyRecording(TempPath("ut_exe_05_threads.mcap"));
  const auto spec = WriteStubRunSpec(TempPath("ut_exe_05_threads.json"), recording);
  EnvGuard name("ADAS_SIL_TEST_STUB_NAME", "exe05threads");
  const auto accepted = simcore::module_host::RunIsolatedStage(
      "sut", SimenginePath(), {spec.string(), "--threads", "2"}, std::chrono::seconds(5));
  EXPECT_EQ(accepted.outcome, simcore::module_host::IsolatedOutcome::kOk);
  for (const char* bad : {"0", "-1", "two", "1.5"}) {
    const auto refused = simcore::module_host::RunIsolatedStage(
        "sut", SimenginePath(), {spec.string(), "--threads", bad}, std::chrono::seconds(5));
    EXPECT_EQ(refused.outcome, simcore::module_host::IsolatedOutcome::kFail) << bad;
    EXPECT_EQ(refused.exit_code, static_cast<int>(kSimExitConfig)) << bad;
  }
}

TEST(UtExe05ExitCodes, ModuleOnAnAbiVersionMismatch) {
  const auto recording = WriteTinyRecording(TempPath("ut_exe_05_module.mcap"));
  const auto spec = WriteStubRunSpec(TempPath("ut_exe_05_module.json"), recording);
  EnvGuard name("ADAS_SIL_TEST_STUB_NAME", "exe05module");
  // Any value other than the real ADAS_SIL_ABI_VERSION -- Component::Load's
  // gate compares this against kAbiVersion and nothing else (component.cpp,
  // confirmed by reading it before this test was written), so the mismatch
  // fails at Load(), before Init() or a single Exec() call.
  EnvGuard bad_abi("ADAS_SIL_TEST_STUB_ABI_VERSION", "999");
  const auto result =
      simcore::module_host::RunIsolatedStage("sut", SimenginePath(), {spec.string()}, std::chrono::seconds(5));
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kFail);
  EXPECT_EQ(result.exit_code, static_cast<int>(kSimExitModule));
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
