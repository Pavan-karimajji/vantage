// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-EXE-04` (`SW-0147`, `WP-14`): a restart-capable `simengine` run
///   restarts ONLY on a real, OS-observed abnormal termination, bounded by
///   `--restart-on-crash`, and every attempt is recorded into
///   `<run_spec>.manifest.json` so a restarted run is identifiable from
///   its artifacts alone. The default (no `--restart-on-crash`) run does
///   not restart at all.
///
///   The crash under test is REAL: `ADAS_SIM_TEST_FORCE_ABORT` makes
///   `simengine` itself call `std::abort()` (`main.cpp`'s own test hook),
///   a genuine `SIGABRT` this file's own `RunIsolatedStage` call observes
///   exactly the way a real segfault would -- nothing here is a same-
///   process catch standing in for a crash.
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

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

// Same escaping discipline `test_ut_abi_writer_and_resolver.cpp`'s own top
// note requires -- an unescaped Windows path fed into a JSON string literal
// was this file's own pre-existing, already-documented `WP-14a`/`WP-15a`
// defect (`EnabledRunThatSucceedsRecordsExactlyOneOkAttempt`'s own listed
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

// A run spec `simengine` can genuinely load -- doesn't need to be exercised
// to completion for the crash cases (`ADAS_SIM_TEST_FORCE_ABORT` aborts
// before the spec is even opened), but the "default run succeeds, one
// manifest attempt" case does run it to completion, so it has to be real.
std::filesystem::path WriteMinimalRunSpec(const std::filesystem::path& spec_path,
                                          const std::filesystem::path& recording) {
  std::ofstream out(spec_path);
  out << R"({
    "schema": "adas.sim.runspec/2.0", "run_id": "20260822T000000Z-exe04",
    "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [], "mutations": [],
    "coherence_verdict": "clean", "readiness_limit_steps": 4, "fallback_max_gap": 4, "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  return spec_path;
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

std::size_t CountManifestLines(const std::filesystem::path& manifest_path) {
  std::ifstream in(manifest_path);
  std::size_t n = 0;
  std::string line;
  while (std::getline(in, line)) {
    if (!line.empty()) ++n;
  }
  return n;
}

std::filesystem::path SimenginePath() { return std::filesystem::path(SIMENGINE_EXECUTABLE); }

class UtExe04Restart : public ::testing::Test {
 protected:
  void SetUp() override {
    recording_ = WriteTinyRecording(TempPath("ut_exe_04_recording.mcap"));
    spec_ = WriteMinimalRunSpec(TempPath("ut_exe_04_spec.json"), recording_);
    manifest_ = spec_.string() + ".manifest.json";
    std::filesystem::remove(manifest_);
  }
  void TearDown() override { std::filesystem::remove(manifest_); }

  std::filesystem::path recording_;
  std::filesystem::path spec_;
  std::filesystem::path manifest_;
};

TEST_F(UtExe04Restart, DefaultRunDoesNotRestartOnARealCrashAndWritesNoManifest) {
  EnvGuard force_abort("ADAS_SIM_TEST_FORCE_ABORT", "1");
  const auto result = simcore::module_host::RunIsolatedStage("sut", SimenginePath(), {spec_.string()},
                                                              std::chrono::seconds(5));
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kCrashed);
  EXPECT_FALSE(std::filesystem::exists(manifest_)) << "no supervisor -> no manifest ever written";
}

TEST_F(UtExe04Restart, EnabledRunRestartsUpToTheBoundThenReportsCrashAndRecordsEveryAttempt) {
  EnvGuard force_abort("ADAS_SIM_TEST_FORCE_ABORT", "1");
  const auto result = simcore::module_host::RunIsolatedStage(
      "sut", SimenginePath(), {spec_.string(), "--restart-on-crash", "2"}, std::chrono::seconds(10));
  // The SUPERVISOR itself returns cleanly (exit(kSimExitCrash)) once its
  // own restart bound is exhausted -- it is never itself signalled, only
  // its children are, so THIS call's own outcome is a clean nonzero exit.
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kFail);
  EXPECT_EQ(result.exit_code, static_cast<int>(kSimExitCrash));

  ASSERT_TRUE(std::filesystem::exists(manifest_));
  EXPECT_EQ(CountManifestLines(manifest_), 3u) << "initial attempt + 2 restarts, never a 4th";
  std::ifstream in(manifest_);
  std::string line;
  while (std::getline(in, line)) {
    EXPECT_NE(line.find("\"outcome\":\"crash\""), std::string::npos);
  }
}

TEST_F(UtExe04Restart, EnabledRunThatSucceedsRecordsExactlyOneOkAttempt) {
  const auto result = simcore::module_host::RunIsolatedStage(
      "sut", SimenginePath(), {spec_.string(), "--restart-on-crash", "3"}, std::chrono::seconds(10));
  EXPECT_EQ(result.outcome, simcore::module_host::IsolatedOutcome::kOk);

  ASSERT_TRUE(std::filesystem::exists(manifest_));
  EXPECT_EQ(CountManifestLines(manifest_), 1u);
  std::ifstream in(manifest_);
  std::string line;
  std::getline(in, line);
  EXPECT_NE(line.find("\"outcome\":\"ok\""), std::string::npos);
  EXPECT_NE(line.find("\"final\":true"), std::string::npos);
}

}  // namespace
