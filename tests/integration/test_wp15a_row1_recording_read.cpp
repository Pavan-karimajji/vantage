// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   WP-15a row 1 ("recording read and cycle grouping") -- the assembly
///   `scripts/prove_equal.py`'s own row-1 note named as the closing
///   condition: `simcore/io`'s read path (`WP-06`) and
///   `simcore::bus::CycleReconstructor` (`WP-08`) wired together into one
///   recording-read-and-group capability, run end to end against a real
///   `.mcap` file and compared to `sil_host/src/recording_reader.cpp`'s own
///   algorithm (read directly, not linked -- `sil_host` and `sim` are
///   separate submodules, R-ARCH-1). This is the "dedicated integration
///   slice" Design's own row-1 note names as the alternative to pulling
///   `WP-17`'s index/seek/selection forward: `recording_reader.cpp` itself
///   does no seeking -- it opens the file, calls `readMessages()` once with
///   `ReadOrder::LogTimeOrder`, and buckets the full stream -- so the
///   equivalent slice here is a full linear `ReadRange` loop into
///   `CycleReconstructor::Ingest`, with none of `WP-17`'s index-then-seek
///   machinery required or built.
///
///   **Scope of the equivalence claim, stated so it is never overclaimed.**
///
///   1. Cycle KEY. `recording_reader.cpp` groups by exact `log_time_ns`
///      equality (`std::map<int64_t, std::map<string, bytes>> byLogTime`).
///      `CycleReconstructor` groups by a per-message CYCLE KEY chosen by its
///      own recovery ladder (`bus.hpp`'s own comment: "never by equality of
///      file/reception timestamps -- `recording_reader.cpp`'s own defect,
///      ported nowhere") -- a deliberate improvement, not a port. The two
///      algorithms are NOT equal in general. They ARE equal today, for
///      every real recording this framework or `sil_host` produces: with no
///      `source_cycle_id`/header `counter`/`t_source_ns` decoded (`WP-08`'s
///      own scope note -- wire-decode of `SignalHeader` fields is a named
///      follow-on, and no producer populates them yet per R-IFACE-4,
///      "planned, not yet implemented"), `CycleReconstructor`'s ladder
///      always lands on `Rung::ReceptionTime`, whose cycle key is
///      `msg.t_recv_ns` -- set here from `RawMessage::log_time_ns`, the
///      exact quantity `recording_reader.cpp` groups by. Proven below on
///      real encoded bytes read through the real `.mcap` codec.
///
///   2. Completeness. `recording_reader.cpp` emits ONE `RecordingTick` per
///      distinct `log_time_ns` REGARDLESS of which ports are present in it
///      -- a tick with only one of two expected topics is still emitted,
///      with the missing port simply absent from `RecordingTick::ports`.
///      `CycleReconstructor::TakeCompleteCycle` is deliberately stricter
///      (`SW-0049`'s own "multi-port input sets"): it withholds a cycle key
///      until every port named in `expected_ports` has landed, so an
///      under-populated tick never drains and a genuinely incomplete
///      recording's tail is left pending rather than handed to a consumer
///      one port short. This is a REAL, un-ported behavioural difference,
///      not a gap in this test's coverage of the shared case -- and it is
///      why this equivalence claim is scoped to well-formed recordings
///      (every declared port present every tick), which is what R-SIM-6
///      already requires of any recording usable for a `measured` stage.
///      A malformed/legacy recording missing a port on some ticks is
///      exactly the case `recording_reader.cpp`'s own tolerance and
///      `CycleReconstructor`'s own strictness diverge on; nothing here
///      claims otherwise.
///
///   The day a producer populates a header counter, claim (1) needs
///   re-establishing at that rung, not assumed to still hold; claim (2) is
///   permanent, by design (`SW-0049`), and is not the equivalence this test
///   is proving -- it is the improvement over `recording_reader.cpp` that
///   motivated moving away from it.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "simcore/bus.hpp"
#include "simcore/io.hpp"
#include "simcore/runner.hpp"

namespace simcore::io {
namespace {

std::filesystem::path TempPath(const std::string& name) {
  return std::filesystem::temp_directory_path() / name;
}

// Writes a real `.mcap` recording through simcore's OWN registered codec
// (already proven round-trip-correct, `UT-IO-22`) -- two topics, three
// ticks, every tick's two messages sharing one `log_time_ns`, exactly the
// shape `recording_reader.cpp`'s own grouping map keys on. Every declared
// port present every tick, per this file's own completeness note above.
std::filesystem::path WriteTwoTopicRecording(const std::string& name, int tick_count) {
  const std::filesystem::path path = TempPath(name);
  CodecRegistry registry;
  EXPECT_TRUE(codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(path);
  EXPECT_TRUE(writer.ok());
  TopicInfo info_a;
  info_a.schema_name = "test.A";
  TopicInfo info_b;
  info_b.schema_name = "test.B";
  EXPECT_TRUE(writer.value()->Open(path, {{"a/out", info_a}, {"b/out", info_b}}).ok());

  for (int i = 1; i <= tick_count; ++i) {
    const std::int64_t t_ns = static_cast<std::int64_t>(i) * 50'000'000;
    RawMessage a;
    a.topic = "a/out";
    a.log_time_ns = t_ns;
    a.payload = {static_cast<std::uint8_t>(i)};
    writer.value()->Write(a);

    RawMessage b;
    b.topic = "b/out";
    b.log_time_ns = t_ns;
    b.payload = {static_cast<std::uint8_t>(i * 10)};
    writer.value()->Write(b);
  }
  writer.value()->Close();
  return path;
}

// The assembled capability itself: open, stream every `RawMessage` via the
// io read path (`AccumulateBatch`'s three-axis loop, unbounded here), feed
// each into `CycleReconstructor` with no header fields decoded (WP-08's own
// first-slice scope), and drain every complete cycle in ascending key order
// -- `sorted(groups)`, same as `recording_reader.cpp`'s own final iteration
// over its `std::map`. No `Seek` call anywhere: this IS the "dedicated
// integration slice" -- a full linear read, matching what
// `recording_reader.cpp` itself does, never `WP-17`'s index/seek machinery.
std::vector<bus::Cycle> ReadAndGroup(const std::filesystem::path& path, const std::vector<bus::PortId>& expected_ports) {
  CodecRegistry registry;
  EXPECT_TRUE(codecs::RegisterMcap(registry).ok());
  auto reader = registry.OpenRead(path);
  EXPECT_TRUE(reader.ok());
  EXPECT_TRUE(reader.value()->Open(path).ok());

  bus::CycleReconstructor reconstructor(expected_ports);
  ReadBounds bounds;
  bounds.max_messages = 1;  // exercises the streaming path one message at a time
  for (;;) {
    const Batch batch = reader.value()->ReadRange(bounds);
    for (const RawMessage& raw : batch.messages) {
      bus::PortMessage msg;
      msg.port = simcore::runner::TopicToPortName(raw.topic);
      msg.t_recv_ns = raw.log_time_ns;
      // `RawMessage::capture_time_ns` is `std::optional<int64_t>`
      // (`simcore/io.hpp`); `PortMessage::t_capture_ns` is `bus::Unknown<int64_t>`
      // (`simcore/bus.hpp`) -- same "absent means unknown" shape (R-SIM-14),
      // different vocabulary per module, so the join point converts
      // explicitly rather than relying on an implicit conversion neither
      // header declares.
      msg.t_capture_ns = raw.capture_time_ns.has_value()
                              ? bus::Unknown<std::int64_t>(*raw.capture_time_ns)
                              : bus::Unknown<std::int64_t>::None();
      msg.payload = raw.payload;
      EXPECT_TRUE(reconstructor.Ingest(msg).ok());
    }
    if (batch.exhausted) break;
  }
  reader.value()->Close();

  std::vector<bus::Cycle> cycles;
  for (std::optional<bus::Cycle> cycle = reconstructor.TakeCompleteCycle(); cycle.has_value();
       cycle = reconstructor.TakeCompleteCycle()) {
    cycles.push_back(std::move(*cycle));
  }
  return cycles;
}

TEST(Wp15aRow1RecordingRead, AssembledIoPlusCycleReconstructorGroupsARealMcapFileByLogTime) {
  constexpr int kTickCount = 3;
  const std::filesystem::path path = WriteTwoTopicRecording("wp15a_row1.mcap", kTickCount);

  const std::vector<bus::PortId> expected_ports = {"a.out", "b.out"};
  const std::vector<bus::Cycle> cycles = ReadAndGroup(path, expected_ports);

  // `recording_reader.cpp`'s own algorithm, read directly: one tick per
  // distinct log_time_ns, both topics present (a "complete" tick), ascending
  // order -- reproduced here as the expected shape, since sil_host cannot be
  // linked into this binary (separate submodule).
  ASSERT_EQ(cycles.size(), static_cast<std::size_t>(kTickCount));
  for (int i = 0; i < kTickCount; ++i) {
    const bus::Cycle& cycle = cycles[static_cast<std::size_t>(i)];
    ASSERT_EQ(cycle.ports.size(), 2u) << "tick " << i;
    ASSERT_NE(cycle.ports.find("a.out"), cycle.ports.end()) << "tick " << i;
    ASSERT_NE(cycle.ports.find("b.out"), cycle.ports.end()) << "tick " << i;
    const std::uint8_t tick = static_cast<std::uint8_t>(i + 1);
    EXPECT_EQ(cycle.ports.at("a.out").payload, (std::vector<std::uint8_t>{tick}));
    EXPECT_EQ(cycle.ports.at("b.out").payload, (std::vector<std::uint8_t>{static_cast<std::uint8_t>(tick * 10)}));
    // Every message landed on ReceptionTime/Approximated -- no header field
    // was ever decoded onto it, so the ladder had exactly one rung
    // available. This IS the boundary condition the file header states.
    EXPECT_EQ(cycle.ports.at("a.out").rung, bus::Rung::ReceptionTime);
    EXPECT_EQ(cycle.ports.at("a.out").quality, bus::Quality::Approximated);
  }
}

// Same shape as `sil_host/tests/unit/test_resim_measured.cpp`'s own
// `WriteMeasuredRecording` corpus (one topic "a/out", 3 ticks, payload byte
// == tick index) -- a genuine same-input case: identical bytes, both sides'
// own test proving the same per-tick payload comes back out.
TEST(Wp15aRow1RecordingRead, SameInputAsSilHostsResimMeasuredFixtureGroupsIdentically) {
  const std::filesystem::path path = TempPath("wp15a_row1_same_input.mcap");
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  TopicInfo info;
  info.schema_name = "test.Echo";
  ASSERT_TRUE(writer.value()->Open(path, {{"a/out", info}}).ok());
  constexpr int kTickCount = 3;
  for (int i = 1; i <= kTickCount; ++i) {
    RawMessage msg;
    msg.topic = "a/out";
    msg.log_time_ns = static_cast<std::int64_t>(i) * 50'000'000;
    msg.payload = {static_cast<std::uint8_t>(i)};
    writer.value()->Write(msg);
  }
  writer.value()->Close();

  const std::vector<bus::Cycle> cycles = ReadAndGroup(path, {"a.out"});
  ASSERT_EQ(cycles.size(), static_cast<std::size_t>(kTickCount));
  for (int i = 0; i < kTickCount; ++i) {
    const std::vector<std::uint8_t> expected = {static_cast<std::uint8_t>(i + 1)};
    EXPECT_EQ(cycles[static_cast<std::size_t>(i)].ports.at("a.out").payload, expected) << "tick " << i;
  }
}

// Row-1 completeness note, made concrete rather than left as prose: a tick
// missing an expected port never drains from `CycleReconstructor`, unlike
// `recording_reader.cpp`'s own tolerant grouping (see this file's header,
// claim 2). This is not a bug this test is chasing -- it is the documented,
// permanent divergence, planted here so a future change that silently makes
// the two "more equal" than they should be (e.g. draining incomplete
// cycles at end-of-stream) is caught rather than assumed harmless.
TEST(Wp15aRow1RecordingRead, IncompleteTickNeverDrainsUnlikeSilHostsTolerantGrouping) {
  const std::filesystem::path path = TempPath("wp15a_row1_incomplete.mcap");
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  TopicInfo info_a;
  info_a.schema_name = "test.A";
  ASSERT_TRUE(writer.value()->Open(path, {{"a/out", info_a}}).ok());
  // Only "a/out" is ever written -- "b/out" is declared expected below but
  // never appears. recording_reader.cpp would still emit one tick (with
  // "b/out" simply absent); CycleReconstructor must never drain it.
  RawMessage a;
  a.topic = "a/out";
  a.log_time_ns = 50'000'000;
  a.payload = {1};
  writer.value()->Write(a);
  writer.value()->Close();

  const std::vector<bus::Cycle> cycles = ReadAndGroup(path, {"a.out", "b.out"});
  EXPECT_TRUE(cycles.empty()) << "an under-populated tick must stay pending, never drain";
}

}  // namespace
}  // namespace simcore::io
