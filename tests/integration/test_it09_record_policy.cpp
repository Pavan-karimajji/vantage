// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IT-09` (`WP-13`, `SW-0114`/`IMP-0114`): the record-policy write pass
///   proved at the unit level by `UtRun14RecordPolicy`
///   (`tests/unit/test_ut_run_core.cpp`) -- against a hand-built `Runner`
///   fed by an in-test codec, not the real DLL boundary -- is proved here
///   again through the actual production entry point: a real Run Spec
///   handed to `simEngineCreate`/`simEngineRun`/`simEngineDestroy` alone
///   (the same "second host" shape `IT-11`/`UT-ABI-01`/`UT-ABI-03` already
///   use), a real `echo_stub` fixture DLL, and a real `.mcap` written and
///   read back through `simcore::io::CodecRegistry`. This is `IMP-0114`'s
///   own named closing condition -- the plan row's mechanism has been
///   landed and unit-covered since `WP-13`; only its integration proof was
///   missing.
///
///   Two declared stages give three ports carrying three DIFFERENT record
///   policies -- `meas.objects` (`full`), `sut.objects` (`excluded`,
///   the `req` half of the same edge `meas.objects` feeds) and
///   `sut.outputs` (`decimate:3`), the same "declared vs. how it is kept"
///   split `UtRun14RecordPolicy`'s own `AnExcludedPortIsNeverWrittenAnd...`
///   case exercises, but reached here through a real `PortResolver`/
///   `Component::Exec` round trip instead of a synthetic in-test bus.
///   `echo_stub`'s own `ADAS_SIL_TEST_STUB_INPUT_PORT`/`_OUTPUT_PORT` pair
///   (its own top note) makes `sut.outputs` a genuine echo of
///   `sut.objects`'s delivered bytes -- so the two `decimate:3` messages
///   this test reads back are checked against the exact `meas.objects`
///   payload at those cycles, never a placeholder constant.
///
///   Six cycles, matching `UtRun14RecordPolicy`'s own "`decimate:3` writes
///   cycles 0 and 3 of 0..5" pattern exactly, so the expected write count
///   (2) is the same number a reader of that unit test already knows.
///
///   The Accept this proves, read from the artifact alone with no access
///   to the Run Spec that produced it: `/meas/objects` carries all 6
///   messages: `/sut/objects` carries none; `/sut/outputs` carries exactly
///   the 2 the `decimate:3` grammar predicts, at the predicted log times,
///   with the predicted bytes.
/// @author Pavan Karimajji

#include "simcore/abi/simcore.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include <gtest/gtest.h>

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

// Same JSON-escaping discipline every other C-ABI-driven integration test
// in this directory carries at its own top -- a path fed unescaped into a
// JSON string literal is `test_ut_abi_writer_and_resolver.cpp`'s own
// already-documented pre-existing Windows defect, not one this file repeats.
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

// Six one-byte messages on `/meas/objects` -- `meas`'s own declared `pro`
// port pulls straight from this topic (a `measured` stage's recorded
// output is sourced from `/<stage>/<port>`, `UT-ABI-02`'s own
// `WriteAbiPortRecording` precedent), and their distinct byte values let
// the two surviving `decimate:3` messages on `/sut/outputs` be checked
// against the exact input bytes for their own cycle, never a constant.
std::filesystem::path WriteObjectsRecording(const std::filesystem::path& path, std::size_t cycles,
                                            std::int64_t step_ns) {
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(path);
  EXPECT_TRUE(writer.ok());
  simcore::io::TopicInfo info;
  info.schema_name = "test.Echo";
  // `origin_for` (`cycle_loop.cpp`) resolves a `measured` stage's own
  // published origin from THIS recording's own topic provenance -- an
  // unset (`kUnknown`) provenance reads as "nobody can establish this was
  // measured" (`R-SIM-12`) and the value is never published, which is
  // exactly the gap this test exists to close: a real recording always
  // carries a provenance tag, so this must too.
  info.provenance = simcore::io::Provenance::kMeasured;
  EXPECT_TRUE(writer.value()->Open(path, {{"/meas/objects", info}}).ok());
  for (std::size_t i = 0; i < cycles; ++i) {
    simcore::io::RawMessage msg;
    msg.topic = "/meas/objects";
    msg.log_time_ns = static_cast<std::int64_t>(i) * step_ns;
    msg.payload = {static_cast<std::uint8_t>(0x10 + i)};
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

// One `measured` stage (`meas`, `objects` pro, policy `full`) feeding one
// `simulate` stage (`sut`, `echo_stub`) whose `objects` req port carries
// policy `excluded` and whose `outputs` pro port -- `echo_stub`'s own
// verbatim echo of `objects` -- carries policy `decimate:3`. Three
// declared ports, three different policies, mirroring
// `UtRun14RecordPolicy`'s own two-stage shape (`meas`+`sut`) but through
// the real C ABI rather than a hand-built `Runner`.
std::string BuildRunSpecJson(const std::filesystem::path& recording, const std::filesystem::path& stub,
                              const std::filesystem::path& output_path, std::int64_t step_ns) {
  std::ostringstream out;
  out << R"({
    "schema": "adas.sim.runspec/1.0",
    "run_id": "20260824T000000Z-it09",
    "spec_sha256": "0",
    "grid": {"step_ns": )"
      << step_ns << R"(},
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [
      {
        "name": "meas", "mode": "measured",
        "impl": {"kind": "dll", "path": "", "pattern": "", "search": []},
        "period_ns": )"
      << step_ns << R"(, "abi_version": 1, "config_bundle_sha256": "",
        "ports": [{"name": "objects", "dir": "pro", "kind": "data", "proto_type": "test.Echo",
                   "record": "full", "sampling": "latest", "on_missing": "hold", "fixed_slots": null}],
        "inputs": []
      },
      {
        "name": "sut", "mode": "simulate",
        "impl": {"kind": "dll", "path": ")"
      << JsonEscape(stub) << R"(", "pattern": "", "search": []},
        "period_ns": )"
      << step_ns << R"(, "abi_version": 1, "config_bundle_sha256": "",
        "ports": [{"name": "objects", "dir": "req", "kind": "data", "proto_type": "test.Echo",
                   "record": "excluded", "sampling": "latest", "on_missing": "hold", "fixed_slots": null},
                  {"name": "outputs", "dir": "pro", "kind": "data", "proto_type": "test.Echo",
                   "record": "decimate:3", "sampling": "latest", "on_missing": "hold", "fixed_slots": null}],
        "inputs": [{"port": "objects", "producer": "meas", "producer_port": "objects", "delay_steps": 0}]
      }
    ],
    "mutations": [],
    "order": ["meas", "sut"],
    "coherence": {"verdict": "clean"},
    "outputs": {"path": ")"
      << JsonEscape(output_path) << R"(", "codec": "mcap"},
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

TEST(It09RecordPolicy, MixedPoliciesAreAnsweredFromTheWrittenRecordingAlone) {
  constexpr std::int64_t kStepNs = 10'000'000;  // 10 ms
  constexpr std::size_t kCycles = 6;  // UtRun14RecordPolicy's own "0..5" range

  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "run_stub_it09");
  EnvGuard input_guard("ADAS_SIL_TEST_STUB_INPUT_PORT", "objects");
  EnvGuard output_guard("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs");

  const std::filesystem::path recording =
      WriteObjectsRecording(TempPath("it09_input.mcap"), kCycles, kStepNs);
  const std::filesystem::path output_path = TempPath("it09_output.mcap");
  std::filesystem::remove(output_path);
  const std::filesystem::path spec_path = WriteSpec(
      TempPath("it09_spec.json"), BuildRunSpecJson(recording, EchoStubPath(), output_path, kStepNs));

  RunToCompletion(spec_path);

  ASSERT_TRUE(std::filesystem::exists(output_path)) << "no recording was written at all";

  simcore::io::CodecRegistry registry;
  ASSERT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto reader = registry.OpenRead(output_path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(output_path).ok());
  const simcore::io::Batch batch = reader.value()->ReadRange(simcore::io::ReadBounds{});
  reader.value()->Close();
  EXPECT_TRUE(batch.exhausted);

  std::vector<simcore::io::RawMessage> objects_full;
  std::vector<simcore::io::RawMessage> objects_excluded;
  std::vector<simcore::io::RawMessage> outputs_decimated;
  for (const simcore::io::RawMessage& message : batch.messages) {
    if (message.topic == "/meas/objects") {
      objects_full.push_back(message);
    } else if (message.topic == "/sut/objects") {
      objects_excluded.push_back(message);
    } else if (message.topic == "/sut/outputs") {
      outputs_decimated.push_back(message);
    }
  }

  // `full`: every one of the 6 declared cycles is present, answerable from
  // the artifact alone with no reference to how many were fed in.
  EXPECT_EQ(objects_full.size(), kCycles);

  // `excluded`: the topic itself is never written, not merely empty --
  // `UtRun14RecordPolicy`'s own "never written" Accept, reached here
  // through the real injection boundary rather than a synthetic bus.
  EXPECT_TRUE(objects_excluded.empty());

  // `decimate:3`: cycles 0 and 3 of 0..5 survive -- the same count and the
  // same cycle indices `UtRun14RecordPolicy`'s own
  // `AnExcludedPortIsNeverWrittenAndADecimatedOneIsWrittenEveryNthCycle`
  // case asserts, now through `echo_stub`'s real `Component::Exec` and a
  // real `.mcap` round trip.
  ASSERT_EQ(outputs_decimated.size(), 2u);
  EXPECT_EQ(outputs_decimated[0].log_time_ns, 0);
  EXPECT_EQ(outputs_decimated[1].log_time_ns, 3 * kStepNs);

  // `echo_stub`'s own verbatim echo (`ADAS_SIL_TEST_STUB_INPUT_PORT`) means
  // each surviving `outputs` message carries exactly the `objects` bytes
  // delivered that same cycle -- a real value, not a placeholder constant,
  // which is what "answerable from the artifact alone" requires: the two
  // decimated messages must be traceable to real per-tick computation, not
  // to a policy that merely happened to let something through.
  ASSERT_EQ(objects_full[0].payload, outputs_decimated[0].payload);
  ASSERT_EQ(objects_full[3].payload, outputs_decimated[1].payload);
}
