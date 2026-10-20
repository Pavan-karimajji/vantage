// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IT-23`/`UT-VTG-01` (`WP-33`, `SW-0426`, `SM-11`/`vantage`): the same
///   embed-host shape `test_it11_embed_host.cpp`'s own `UT-ABI-04` proves,
///   extended past the transport into the player side -- this test IS the
///   headless half of `vantage` (`sim::vantage::RunEmbedded`), minus a GL
///   window. Built ONLY under the `gtest_viz` target (`tests/vantage/
///   CMakeLists.txt`) -- `simcore_tests`/the plain `gtest` target stay
///   viz-free (`O-7`).
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "vantage/host_loop.hpp"
#include "vantage/frame_bridge.hpp"

#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

#include <gtest/gtest.h>

#include "simcore/io.hpp"
#include "viz/session/source.hpp"

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

// Same escaping discipline `test_it11_embed_host.cpp`'s own `JsonEscape`
// requires (an unescaped Windows path fed into a JSON string literal) --
// duplicated rather than shared, matching this test's own self-contained
// fixture pattern (it builds into a SEPARATE gtest binary, `vantage_tests`,
// never linked with `simcore_tests`).
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

std::filesystem::path WriteRunSpec(const std::filesystem::path& spec_path, const std::filesystem::path& recording,
                                   const std::filesystem::path& stub) {
  std::ofstream out(spec_path);
  out << R"({
    "schema": "adas.sim.runspec/1.0",
    "run_id": "20260825T000000Z-it23",
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

class It23VantageBridge : public ::testing::Test {
 protected:
  void SetUp() override {
#if defined(_WIN32)
    _putenv_s("ADAS_SIL_TEST_STUB_NAME", "run_stub");
    _putenv_s("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs");
#else
    setenv("ADAS_SIL_TEST_STUB_NAME", "run_stub", 1);
    setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs", 1);
#endif
    recording_ = WriteTinyRecording(TempPath("it23_recording.mcap"));
    spec_ = WriteRunSpec(TempPath("it23_run_spec.json"), recording_, EchoStubPath());
  }

  std::filesystem::path recording_;
  std::filesystem::path spec_;
};

TEST_F(It23VantageBridge, EmbeddedRunDeliversTicksMatchingTheTransportsRealFrames) {
  viz::session::PushSource sink(/*depth=*/8);
  ASSERT_TRUE(sink.Open().ok());

  const sim::vantage::HostLoopResult result = sim::vantage::RunEmbedded(spec_.string(), "", 2000, sink);
  ASSERT_TRUE(result.ok) << result.error;
  EXPECT_EQ(result.cycles_stepped, 3);

  int ticks_seen = 0;
  for (;;) {
    const std::optional<viz::session::Tick> tick = sink.NextTick();
    if (!tick.has_value()) break;
    ++ticks_seen;

    // A frame's "sut.outputs" reaches the player in the canonical spelling a Session uses for a recorded
    // port, which is what the plug-in port resolver matches (a dotted name would bind no layer).
    const viz::session::PortValue* port = tick->Port("/sut/outputs");
    ASSERT_NE(port, nullptr) << "tick " << tick->index << " carried no /sut/outputs port";
    EXPECT_EQ(port->origin, viz::session::Origin::kSimulated);
    ASSERT_EQ(port->payload.size(), 1u);
    EXPECT_EQ(port->payload[0], 0xAB);  // echo_stub's default output byte
    // Named, honest limitation (SW-0426's own Accept) -- no manifest source
    // is wired into this pass, so schema resolution is out of scope here.
    EXPECT_TRUE(port->schema_bytes.empty());
    EXPECT_TRUE(port->schema_name.empty());
  }
  EXPECT_EQ(ticks_seen, 3);
}

// A frame's dotted port name reaches the player in the canonical spelling a Session gives a recorded port
// ("df.fast.outputs" -> "/df/fast.outputs"), which is what the plug-in port resolver matches.
TEST(FrameBridgeNames, AFramesDottedPortNameIsCanonical) {
  sim::vantage::FrameBridge bridge;
  const std::uint8_t byte = 7;
  adas::transport::PortFrame frame{};
  frame.portName = "df.fast.outputs";
  frame.data = &byte;
  frame.size = 1;
  bridge.AddFrame(frame);
  const viz::session::Tick tick = bridge.TakeTick(0);
  ASSERT_EQ(tick.ports.size(), 1u);
  EXPECT_NE(tick.Port("/df/fast.outputs"), nullptr);
  EXPECT_EQ(tick.Port("df.fast.outputs"), nullptr);
}

}  // namespace
