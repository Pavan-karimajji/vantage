// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-ABI-01`/`UT-ABI-02` (`WP-14a`, `SW-0422`/`SW-0423`): the
///   embeddable ABI's real writer and real resolver, proved through
///   `simEngineCreate`/`simEngineRun`/`simEngineDestroy` alone -- the same
///   "second host" shape `IT-11` (`test_it11_embed_host.cpp`) already
///   proves `simcore` needs no `simengine` translation unit to run.
///
///   `UT-ABI-01`: a spec declaring `outputs.path` produces a real `.mcap`
///   recording containing every declared, non-excluded port with real
///   per-tick bytes -- read back through the SAME `io::CodecRegistry`
///   codec a real recording would be read through, never a hand-rolled
///   byte layout.
///
///   `UT-ABI-02`: a spec carrying one declared `const` override on a
///   producer-qualified port (`meas.objects`) should apply for real
///   against `echo_stub`'s own `ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA`
///   mode (a real `descriptor_set` plus genuinely reflection-encoded
///   input bytes, `echo_stub.cpp`'s own top note) -- exercising the
///   actual `DescriptorPool`/`PortResolver` `simcore/abi/simcore.cpp` now
///   builds, not a stand-in.
///
///   **Found running this test for real, first left unfixed by `WP-14a`
///   (out of that package's own scope, which left `Runner`/`Mutator`
///   unmodified), closed here by `WP-11a`/`IMP-0428` (2026-08-22):**
///   `mutate::Mutator::ApplyTo` (`src/simcore/mutate/address.cpp`) used to
///   re-derive its own gate from `value.port` directly, but
///   `bus::PortBus::Publish` (`src/simcore/bus/port_bus.cpp:24`,
///   `value.port = port;`) always stores the FULLY QUALIFIED
///   `"<stage>.<port>"` string there, never the bare port name a
///   `SpecMutation::address.port` names. `cycle_loop.cpp`'s own caller
///   already computed the correct bare split before calling
///   `Mutator::Touches` as a pre-check, so `ApplyTo` was reached and did
///   NOT error -- it silently no-op'd on its own second, inconsistent
///   `Touches` re-check. No single `address.port` string could satisfy both
///   call sites at once (one wanted bare, the other wanted qualified), so
///   this was not an authoring mistake in this test's own JSON -- it was a
///   pre-existing seam between `bus`/`mutate`/`runner` (`WP-11`/`WP-13`)
///   that nothing exercised end-to-end before `WP-14a` found it: `WP-13`'s
///   own `test_ut_run_core.cpp` never passes a non-null `mutator` into
///   `Runner::Construct`, and `WP-11`'s own `test_mut_core.cpp` only ever
///   called `Mutator::ApplyTo` on a hand-built `PortValue` whose `.port` is
///   deliberately bare (`MakeValue`'s own helper) -- never through
///   `bus::PortBus::Publish`. `simcore/abi/simcore.cpp`'s own writer and
///   resolver wiring (`IMP-0426`/`IMP-0427`) were confirmed correct up to
///   this point throughout: `resolve_port` genuinely resolves a real
///   `Descriptor` (a resolver miss would fail the whole engine, which does
///   not happen) and the run completes with `kSimExitOk`. `WP-11a` fixed
///   `ApplyTo` to take the bare port name as an explicit parameter from its
///   caller (`cycle_loop.cpp` already had it in scope) rather than
///   re-deriving it from `value.port` -- the override-applies half below is
///   un-skipped and asserted for real. The zero-`mutations` half
///   (`SW-0423`'s "unchanged" Accept) was unaffected by this and already
///   passed for real.
/// @author Pavan Karimajji

#include "simcore/abi/simcore.h"

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <optional>
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

// Escapes a path for embedding inside a JSON string literal -- Windows'
// own separator is JSON's escape character, and `IT-11`'s own
// `WriteRunSpec` (`test_it11_embed_host.cpp`) does not do this, which is
// the pre-existing, already-documented Windows JSON-escaping defect this
// file's own new specs must not repeat.
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

std::vector<uint8_t> EncodeAbiPortDouble(double value) {
  std::vector<uint8_t> bytes(9);
  bytes[0] = 0x09;  // field 1 (value), wire type 1 (fixed64) -- proto3 double
  std::memcpy(bytes.data() + 1, &value, sizeof(double));
  return bytes;
}

std::optional<double> DecodeAbiPortDouble(const std::vector<uint8_t>& bytes) {
  if (bytes.size() != 9 || bytes[0] != 0x09) return std::nullopt;
  double value = 0.0;
  std::memcpy(&value, bytes.data() + 1, sizeof(double));
  return value;
}

// A tiny real `.mcap` recording -- three heartbeat messages, no
// particular schema -- driving `UT-ABI-01`'s single `simulate` stage
// (the recording only sets the cycle grid; `echo_stub` has no `req`
// ports to feed from it).
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

// A real `.mcap` recording of a genuinely encoded `abi_test.AbiPort`,
// three cycles, on `/meas/objects` -- `UT-ABI-02`'s own input, decoded
// and (in the override case) mutated by `simcore/abi/simcore.cpp`'s real
// `PortResolver` when delivered to `sut`'s own `objects` req port.
std::filesystem::path WriteAbiPortRecording(const std::filesystem::path& path, double recorded_value) {
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(path);
  EXPECT_TRUE(writer.ok());
  simcore::io::TopicInfo info;
  info.schema_name = "abi_test.AbiPort";
  // Declared, not defaulted. `TopicInfo::provenance` defaults to `kUnknown`,
  // and a value whose grade is unknown is currently indistinguishable from a
  // port nothing ever published (`Origin::Unknown` carries both meanings), so
  // a provenance-less fixture makes the producing stage's own topic drop out
  // of the recording. Every real recording declares a grade; this one now
  // does too. The conflation itself is a separate finding -- see `F-6` in
  // `docs/v2/SIM_Test_Execution_2026-08-28.md`.
  info.provenance = simcore::io::Provenance::kMeasured;
  EXPECT_TRUE(writer.value()->Open(path, {{"/meas/objects", info}}).ok());
  for (std::int64_t t_ns : {0, 10'000'000, 20'000'000}) {
    simcore::io::RawMessage msg;
    msg.topic = "/meas/objects";
    msg.log_time_ns = t_ns;
    msg.payload = EncodeAbiPortDouble(recorded_value);
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

// `UT-ABI-01`'s own spec: one `simulate` stage, one declared `pro` port,
// `outputs.path` set -- `SW-0422`'s own "declares recording output".
std::string BuildAbi01RunSpecJson(const std::filesystem::path& recording, const std::filesystem::path& stub,
                                  const std::filesystem::path& output_path) {
  std::ostringstream out;
  out << R"({
    "schema": "adas.sim.runspec/2.0",
    "run_id": "20260822T000000Z-abi01",
    "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [{
      "name": "sut", "mode": "simulate",
      "impl": {"kind": "dll", "path": ")"
      << JsonEscape(stub) << R"(", "pattern": "", "search": []},
      "trigger": "", "clock_period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
      "ports": [{"name": "outputs", "dir": "pro", "kind": "data", "proto_type": "test.Echo",
                 "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 16}],
      "inputs": []
    }],
    "mutations": [],
    "coherence_verdict": "clean", "readiness_limit_steps": 4, "fallback_max_gap": 4,
    "outputs": {"path": ")"
      << JsonEscape(output_path) << R"(", "codec": "mcap"},
    "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  return out.str();
}

// `UT-ABI-02`'s own spec: a `measured` producer (`meas.objects`) feeding
// a `simulate` consumer's `req` port (`sut.objects`) -- `mutate::Mutator`
// only ever touches a delivered `req` port (`cycle_loop.cpp`'s own
// injection-boundary write pass), never a stage's own computed `pro`
// output, so this two-stage shape is the one that actually exercises an
// override, matching `R-SIM-15`'s "tweak the inputs".
std::string BuildAbi02RunSpecJson(const std::filesystem::path& recording, const std::filesystem::path& stub,
                                  const std::filesystem::path& output_path, const std::string& mutations_json) {
  std::ostringstream out;
  out << R"({
    "schema": "adas.sim.runspec/2.0",
    "run_id": "20260822T000000Z-abi02",
    "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [
      {
        "name": "meas", "mode": "measured",
        "impl": {"kind": "dll", "path": "", "pattern": "", "search": []},
        "trigger": "", "clock_period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
        "ports": [{"name": "objects", "dir": "pro", "kind": "data", "proto_type": "abi_test.AbiPort",
                   "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 16}],
        "inputs": []
      },
      {
        "name": "sut", "mode": "simulate",
        "impl": {"kind": "dll", "path": ")"
      << JsonEscape(stub) << R"(", "pattern": "", "search": []},
        "trigger": "", "clock_period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
        "ports": [{"name": "objects", "dir": "req", "kind": "data", "proto_type": "abi_test.AbiPort",
                   "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 16}],
        "inputs": [{"port": "objects", "producer": "meas", "producer_port": "objects", "previous_cycle": false}]
      }
    ],
    "mutations": )"
      << mutations_json << R"(,
    "coherence_verdict": "clean", "readiness_limit_steps": 4, "fallback_max_gap": 4,
    "outputs": {"path": ")"
      << JsonEscape(output_path) << R"(", "codec": "mcap"},
    "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  return out.str();
}

const char kOverrideMutation[] = R"([{
  "verb": "const",
  "address": {"stage": "meas", "port": "objects", "path": ["value"], "index": null},
  "operands": [99.5],
  "window_ns": [0, null]
}])";

// Runs `spec_path` through the C ABI alone (`simEngineCreate`/
// `simEngineRun`/`simEngineDestroy`) to completion; fails the test on any
// non-`kSimExitOk` outcome.
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

// The value actually delivered to `sut`'s own `objects` req port this
// run, decoded back out of the written recording's `/sut/objects` topic
// (`IMP-0114`'s "every declared input is recorded too", `R-SIM-6`).
// `topic` is explicit since F-3: with no override declared, `sut`'s `objects`
// input is carried by its producer's topic (`/meas/objects`); a declared
// override adds `/sut/objects` alongside it, carrying the post-mutation
// bytes. Which topic a caller reads is therefore the assertion.
std::optional<double> ReadDeliveredValue(const std::filesystem::path& output_path, const std::string& topic) {
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto reader = registry.OpenRead(output_path);
  if (!reader.ok()) return std::nullopt;
  if (!reader.value()->Open(output_path).ok()) return std::nullopt;
  const simcore::io::Batch batch = reader.value()->ReadRange(simcore::io::ReadBounds{});
  reader.value()->Close();
  for (const auto& message : batch.messages) {
    if (message.topic != topic) continue;
    return DecodeAbiPortDouble(message.payload);
  }
  return std::nullopt;
}

}  // namespace

TEST(UtAbi01Writer, ProducesARealRecordingWithEveryDeclaredPortAndRealPerTickValues) {
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "run_stub_abi01");
  EnvGuard port_guard("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs");

  const std::filesystem::path recording = WriteHeartbeatRecording(TempPath("ut_abi_01_input.mcap"));
  const std::filesystem::path output_path = TempPath("ut_abi_01_output.mcap");
  std::filesystem::remove(output_path);
  const std::filesystem::path spec_path =
      WriteSpec(TempPath("ut_abi_01_spec.json"), BuildAbi01RunSpecJson(recording, EchoStubPath(), output_path));

  RunToCompletion(spec_path);

  ASSERT_TRUE(std::filesystem::exists(output_path)) << "no recording was written at all";
  EXPECT_GT(std::filesystem::file_size(output_path), 0u) << "the recording is empty";

  simcore::io::CodecRegistry registry;
  ASSERT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto reader = registry.OpenRead(output_path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(output_path).ok());

  const simcore::io::Batch batch = reader.value()->ReadRange(simcore::io::ReadBounds{});
  reader.value()->Close();

  EXPECT_TRUE(batch.exhausted);
  // SW-0422's Accept: every declared, non-excluded port present with real
  // per-tick values -- one cycle per input heartbeat, on the one declared
  // `pro` port, none of them empty.
  ASSERT_EQ(batch.messages.size(), 3u);
  for (const auto& message : batch.messages) {
    EXPECT_EQ(message.topic, "/sut/outputs");
    EXPECT_FALSE(message.payload.empty());
  }
}

// `SW-0423`'s second Accept clause: "a Run Spec with zero overrides
// behaves identically to today". Real and green: the delivered value is
// exactly the recording's own bytes, untouched.
TEST(UtAbi02Resolver, ZeroMutationsBehavesAsBefore) {
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "run_stub_abi02");
  EnvGuard schema_guard("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", "1");

  constexpr double kRecordedValue = 7.0;
  const std::filesystem::path recording = WriteAbiPortRecording(TempPath("ut_abi_02_input.mcap"), kRecordedValue);

  const std::filesystem::path output_path = TempPath("ut_abi_02_output_plain.mcap");
  std::filesystem::remove(output_path);
  const std::filesystem::path spec_path = WriteSpec(
      TempPath("ut_abi_02_spec_plain.json"), BuildAbi02RunSpecJson(recording, EchoStubPath(), output_path, "[]"));

  RunToCompletion(spec_path);

  // No override declared, so `sut`'s input is the producer's own value on
  // the producer's own topic, and no second post-mutation topic exists.
  const std::optional<double> delivered = ReadDeliveredValue(output_path, "/meas/objects");
  ASSERT_TRUE(delivered.has_value()) << "no /meas/objects message in the written recording";
  EXPECT_DOUBLE_EQ(*delivered, kRecordedValue);
  EXPECT_FALSE(ReadDeliveredValue(output_path, "/sut/objects").has_value())
      << "an un-overridden input must not be duplicated under the consuming address";
}

// `SW-0423`'s first Accept clause: "applied for real". This file's own top
// note named the exact pre-existing `bus`/`mutate` seam defect this run
// first uncovered (never a fault in `simcore/abi/simcore.cpp`'s own writer
// and resolver wiring, which was already confirmed reached and error-free)
// -- closed by `WP-11a`/`IMP-0428`: `Mutator::ApplyTo` now takes the bare
// port name as an explicit parameter from its caller instead of re-deriving
// it from `value.port` (always fully-qualified). Un-skipped 2026-08-22.
TEST(UtAbi02Resolver, ADeclaredOverrideIsApplied) {
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "run_stub_abi02");
  EnvGuard schema_guard("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", "1");

  constexpr double kRecordedValue = 7.0;
  constexpr double kOverrideValue = 99.5;
  const std::filesystem::path recording = WriteAbiPortRecording(TempPath("ut_abi_02_input.mcap"), kRecordedValue);

  const std::filesystem::path output_path = TempPath("ut_abi_02_output_override.mcap");
  std::filesystem::remove(output_path);
  const std::filesystem::path spec_path =
      WriteSpec(TempPath("ut_abi_02_spec_override.json"),
                BuildAbi02RunSpecJson(recording, EchoStubPath(), output_path, kOverrideMutation));

  RunToCompletion(spec_path);

  // An override IS declared, so both halves are kept and neither is lost:
  // the post-mutation bytes the component actually received, under the
  // consuming address...
  const std::optional<double> delivered = ReadDeliveredValue(output_path, "/sut/objects");
  ASSERT_TRUE(delivered.has_value()) << "no /sut/objects message in the written recording";
  EXPECT_DOUBLE_EQ(*delivered, kOverrideValue);
  // ...and the producer's own true value, untouched, on its own topic.
  const std::optional<double> upstream = ReadDeliveredValue(output_path, "/meas/objects");
  ASSERT_TRUE(upstream.has_value()) << "the overridden run lost the producer's own bytes";
  EXPECT_DOUBLE_EQ(*upstream, kRecordedValue);
}
