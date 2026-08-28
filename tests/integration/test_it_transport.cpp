// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-TRN-01` (`WP-27`, `SW-0349`, `SI-25` `transport`): "drive one
///   consumer over the in-process transport, then over shared memory;
///   diff the consumer's source" (`SIM_Software_Test_Spec_v0.1.md` SS5.25)
///   -- the IT-level fixture `WP-27`'s own row named as remaining scope
///   (`Runner::SetTransportPublisher`, landed this pass in `cycle_loop.cpp`
///   alongside this test). A real `Runner` (`SI-06`), a real `echo_stub`
///   component (`F-STUB`) over the generic ABI, wired through the actual
///   scheduler -- not a hand-built bus feeding a transport object
///   directly, which would prove the transport but not the wiring.
///
///   The two runs are independently constructed (fresh `Harness`, fresh
///   `StubComponent`, fresh spec) and driven through `Runner::Run()`
///   exactly as `UtRun01OneLoop` proves byte-identical between `Run()` and
///   manual `StepOnce()` -- the same determinism that test relies on is
///   what makes "diff the consumer's source" a meaningful assertion here
///   rather than a coincidence.
///
///   **`UT-TRN-03` (`F-LONG`, closed 2026-08-24, a later pass in this same
///   file):** "attach a deliberately slow reader; sample engine tick rate;
///   read the reported drop count." The reader here is the worst case a
///   slow one can be -- it never calls `tryReceive` at all until the run
///   is over -- against a real `Runner`/`echo_stub` run long enough
///   (300 cycles) to be a meaningful sample. Engine wall time is compared
///   against an identical run with no publisher attached at all, with a
///   deliberately generous bound (this is a regression catch for a real
///   block, not a micro-benchmark -- a tight bound on synthetic in-memory
///   timing would be the flaky test this codebase's own `WP-06` scoping
///   note (`ANL-SW-12`) already argues against). The **deterministic**
///   half of this test is `DroppedFrames()`: with the ring never drained,
///   the drop count is exactly `published - depth`, checked as an exact
///   equality on both transports, not just "greater than zero."
///
///   **`UT-TRN-02` (`F-BULK`, closed 2026-08-24, a later pass in this same
///   file):** a 200 KB payload (well under `kShmMaxFrameBytes`, clearly
///   "bulk") crosses through a real `Runner`/`echo_stub` run and is
///   compared byte-for-byte against its known source content per cycle --
///   the integrity claim `TransportShm`'s own unit-level zero-copy proof
///   (`DataCrossesThroughTheMappedSegmentNotACopyOnTheStack`, small
///   payloads only) does not by itself cover: does a real *large* value
///   survive the Runner's own value-resolution/write-pass path intact.
///   This implementation has no second control channel to observe
///   separately (`SW-0351`'s own "may" clause, `transport_shm.hpp`'s top
///   note) -- one `tryReceive()` surface carries both bulk and small
///   frames, structurally, so there is nothing else to check on that half.
///
///   **`UT-TRN-05` (`F-STUB-CRASH`, closed 2026-08-24, `test_it_trn05_crash.cpp`):**
///   a genuinely separate, killable process running a real `Runner` --
///   see that file's own top note.
///
///   **`IT-19` (`SW-0298`, `SW-0352`, closed 2026-08-24, a later pass in
///   this same file):** the one test in this file that needs a genuinely
///   live consumer racing the engine thread rather than an attach fully
///   before or fully after `Run()`. A real `Runner`/`echo_stub` steps
///   cycle by cycle on a background thread with a real per-tick sleep
///   (`std::this_thread::sleep_for`, same device `trn_engine_host.cpp`
///   uses for `UT-TRN-05`) while the TEST thread attaches a client
///   partway through, drains a few live frames to prove it is a real
///   player and not an idle handle, detaches, and lets the run continue
///   to exhaustion -- so the attach and the detach both land while
///   `StepOnce()` is actually mid-loop, never before the first call or
///   after the last. `SW-0298`/`SW-0352`'s own `Accept` clause is about
///   VALUES, not timing ("produces port values identical to a control run
///   with no player attached"), so the test's real assertion is a
///   byte-for-byte `RawMessage` diff between this run's `CapturingWriter`
///   output and an independent control run's, over the identical spec and
///   recording, with no publisher ever attached to the control run. The
///   engine's own tick progress (an atomic counter, incremented once per
///   completed `StepOnce()`, sampled at each phase boundary) is checked
///   too, matching this row's literal Test Spec wording ("measure engine
///   tick rate ... attaching mid-run, and after detach") -- a generous
///   bound per phase (same "catch a real block, not a micro-benchmark"
///   reasoning `UT-TRN-03` already uses), not a precision timing claim.
///
///   `UT-TRN-04` (version negotiation) needed no IT-level repeat: `attach()`
///   never touches the scheduler or the bus, so `TransportInproc`/
///   `TransportShm.VersionMismatchRefusedBeforeAnyDataCrosses` already
///   exercise the real code path end to end.
/// @author Pavan Karimajji

#include "simcore/runner.hpp"
#include "simcore/transport.hpp"
#include "simcore/transport_shm.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <thread>
#include <tuple>
#include <vector>

#include <gtest/gtest.h>

namespace simcore::runner {
namespace {

using simcore::io::Batch;
using simcore::io::RawMessage;
using simcore::io::ReadBounds;
using simcore::io::TopicInfo;

constexpr std::int64_t kDtNs = 10'000'000;  // 10 ms
constexpr std::uint8_t kStubPayload = 0xCD;  // distinct from test_ut_run_core.cpp's 0xAB

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

// Same shape as test_ut_run_core.cpp's own VectorReader -- an in-test codec,
// no file on disk, so this test is about the transport wiring, not `io`.
class VectorReader final : public simcore::io::Reader {
 public:
  VectorReader(std::vector<RawMessage> messages, std::map<std::string, TopicInfo> topics)
      : messages_(std::move(messages)), topics_(std::move(topics)) {}

  Result<bool> Open(const std::filesystem::path&) override { return Result<bool>::Ok(true); }
  std::map<std::string, TopicInfo> Describe() const override { return topics_; }
  void Seek(std::int64_t log_time_ns) override {
    lookahead_.reset();
    index_ = 0;
    while (index_ < messages_.size() && messages_[index_].log_time_ns < log_time_ns) ++index_;
  }
  Batch ReadRange(const ReadBounds& bounds) override {
    return simcore::io::detail::AccumulateBatch(bounds, lookahead_, [this]() -> std::optional<RawMessage> {
      if (index_ >= messages_.size()) return std::nullopt;
      return messages_[index_++];
    });
  }
  void Close() override {}
  std::optional<std::vector<std::uint8_t>> GetMeta(const std::string&) const override { return std::nullopt; }

 private:
  std::vector<RawMessage> messages_;
  std::map<std::string, TopicInfo> topics_;
  std::optional<RawMessage> lookahead_;
  std::size_t index_ = 0;
};

class NullWriter final : public simcore::io::Writer {
 public:
  Result<bool> Open(const std::filesystem::path&, const std::map<std::string, TopicInfo>&) override {
    return Result<bool>::Ok(true);
  }
  void Write(const RawMessage&) override {}
  void WriteMeta(const std::string&, const std::vector<std::uint8_t>&) override {}
  void Close() override {}
};

// IT-19 -- keeps every written message so two runs' output can be diffed
// byte-for-byte (`SW-0298`/`SW-0352`'s own "identical to a control run"
// Accept clause).
class CapturingWriter final : public simcore::io::Writer {
 public:
  Result<bool> Open(const std::filesystem::path&, const std::map<std::string, TopicInfo>&) override {
    return Result<bool>::Ok(true);
  }
  void Write(const RawMessage& msg) override { messages_.push_back(msg); }
  void WriteMeta(const std::string&, const std::vector<std::uint8_t>&) override {}
  void Close() override {}

  const std::vector<RawMessage>& messages() const { return messages_; }

 private:
  std::vector<RawMessage> messages_;
};

// One measured stage (source-fed) -> one simulate stage (echo_stub). No
// `off` stage here -- UT-RUN-03 already proves that shape elsewhere; this
// file's own concern is the transport, not the scheduler's port set.
RunSpec MakeSpec() {
  RunSpec spec;
  spec.run_id = "20260824T000000Z-it-trn-01";
  spec.grid_step_ns = kDtNs;

  auto make_port = [](const std::string& name, const std::string& dir) {
    SpecPort port;
    port.name = name;
    port.dir = dir;
    port.kind = "data";
    port.proto_type = "test.Bytes";
    port.record = "full";
    port.sampling = "latest";
    port.on_missing = "hold";
    return port;
  };

  SpecStage measured;
  measured.name = "meas";
  measured.mode = "measured";
  measured.ports.push_back(make_port("objects", "pro"));

  SpecStage sut;
  sut.name = "sut";
  sut.mode = "simulate";
  sut.ports.push_back(make_port("objects", "req"));
  sut.ports.push_back(make_port("outputs", "pro"));
  SpecInput from_measured;
  from_measured.port = "objects";
  from_measured.producer = "meas";
  from_measured.producer_port = "objects";
  sut.inputs.push_back(from_measured);

  spec.stages = {measured, sut};
  spec.order = {"meas", "sut"};
  return spec;
}

std::map<std::string, TopicInfo> MakeTopics() {
  std::map<std::string, TopicInfo> topics;
  TopicInfo measured_info;
  measured_info.schema_name = "test.Bytes";
  measured_info.provenance = simcore::io::Provenance::kMeasured;
  topics["/meas/objects"] = measured_info;
  return topics;
}

std::vector<RawMessage> MakeRecording(std::size_t cycles) {
  std::vector<RawMessage> messages;
  for (std::size_t i = 0; i < cycles; ++i) {
    RawMessage objects;
    objects.topic = "/meas/objects";
    objects.log_time_ns = static_cast<std::int64_t>(i) * kDtNs;
    objects.payload = {static_cast<std::uint8_t>(i & 0xFF), 0x02};
    messages.push_back(objects);
  }
  return messages;
}

class StubComponent {
 public:
  explicit StubComponent(const std::string& stub_name)
      : name_guard_("ADAS_SIL_TEST_STUB_NAME", stub_name),
        port_guard_("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs") {
    auto loaded = simcore::module_host::Component::Load(EchoStubPath());
    if (loaded.ok()) {
      component_.emplace(std::move(loaded).value());
      (void)component_->Init();
    }
  }

  bool ok() const { return component_.has_value(); }
  simcore::module_host::Component* get() { return component_.has_value() ? &*component_ : nullptr; }

 private:
  EnvGuard name_guard_;
  EnvGuard port_guard_;
  std::optional<simcore::module_host::Component> component_;
};

struct Harness {
  explicit Harness(std::size_t cycles)
      : spec(MakeSpec()), reader(MakeRecording(cycles), MakeTopics()), scheduler(spec), writer_base(sink) {}

  RunSpec spec;
  VectorReader reader;
  simcore::scheduler::Scheduler scheduler;
  simcore::bus::PortBus bus;
  NullWriter sink;
  simcore::io::WriterBase writer_base;
};

using Frame = std::tuple<std::uint64_t, std::string, std::vector<std::uint8_t>>;

// Drains every frame currently available -- ring depth is generous (below)
// so nothing drops during this test; `TransportInproc`/
// `TransportShm.SlowConsumerDropsFramesNeverBlocksProducer` already prove
// the drop path on its own.
template <typename Consumer>
std::vector<Frame> DrainAll(Consumer& consumer) {
  std::vector<Frame> frames;
  adas::transport::PortFrame frame{};
  while (consumer.tryReceive(&frame)) {
    frames.emplace_back(frame.tickIndex, std::string(frame.portName),
                        std::vector<std::uint8_t>(frame.data, frame.data + frame.size));
  }
  return frames;
}

}  // namespace

TEST(ItTrn01Transport, InProcessAndSharedMemoryConsumersObserveTheIdenticalStream) {
  constexpr std::size_t kCycles = 5;
  constexpr std::size_t kDepth = 64;  // generous: this test is about parity, not the drop path

  // -- Run 1: InProcessTransport as both publisher and consumer object.
  StubComponent stub_a("it_trn01_a");
  ASSERT_TRUE(stub_a.ok());
  Harness a(kCycles);
  simcore::transport::InProcessTransport transport_a(kDepth);
  uint32_t engine_version = 0;
  ASSERT_EQ(transport_a.attach(simcore::transport::InProcessTransport::kProtocolVersion, &engine_version),
            adas::transport::AttachResult::kOk);
  auto runner_a = Runner::Construct(a.spec, a.scheduler, a.bus, a.reader, {{"sut", stub_a.get()}}, &a.writer_base);
  ASSERT_TRUE(runner_a.ok()) << runner_a.error().Format();
  Runner r_a = std::move(runner_a).value();
  r_a.SetTransportPublisher(&transport_a);
  auto outcome_a = r_a.Run();
  ASSERT_TRUE(outcome_a.ok()) << outcome_a.error().Format();
  const std::vector<Frame> frames_inproc = DrainAll(transport_a);

  // -- Run 2: SharedMemoryTransport, engine role publishes, a separate
  // client-role object (same segment, real second object -- not one
  // dual-role instance, same discipline TransportShm's own unit tests use)
  // consumes.
  StubComponent stub_b("it_trn01_b");
  ASSERT_TRUE(stub_b.ok());
  Harness b(kCycles);
  simcore::transport::SharedMemoryTransport engine_side(
      "it_trn01_shm", simcore::transport::SharedMemoryTransport::Role::kEngine, kDepth);
  simcore::transport::SharedMemoryTransport client_side(
      "it_trn01_shm", simcore::transport::SharedMemoryTransport::Role::kClient, kDepth);
  ASSERT_EQ(client_side.attach(simcore::transport::SharedMemoryTransport::kProtocolVersion, &engine_version),
            adas::transport::AttachResult::kOk);
  auto runner_b = Runner::Construct(b.spec, b.scheduler, b.bus, b.reader, {{"sut", stub_b.get()}}, &b.writer_base);
  ASSERT_TRUE(runner_b.ok()) << runner_b.error().Format();
  Runner r_b = std::move(runner_b).value();
  r_b.SetTransportPublisher(&engine_side);
  auto outcome_b = r_b.Run();
  ASSERT_TRUE(outcome_b.ok()) << outcome_b.error().Format();
  const std::vector<Frame> frames_shm = DrainAll(client_side);

  // Both runs are the identical spec over the identical recording and the
  // identical echo_stub behaviour -- UtRun01OneLoop's own determinism claim
  // one level up. Neither stream may be empty (a passing diff over two
  // empty vectors would prove nothing).
  ASSERT_FALSE(frames_inproc.empty());
  ASSERT_EQ(frames_inproc.size(), frames_shm.size());
  for (std::size_t i = 0; i < frames_inproc.size(); ++i) {
    EXPECT_EQ(std::get<0>(frames_inproc[i]), std::get<0>(frames_shm[i])) << "frame " << i << " tick";
    EXPECT_EQ(std::get<1>(frames_inproc[i]), std::get<1>(frames_shm[i])) << "frame " << i << " port";
    EXPECT_EQ(std::get<2>(frames_inproc[i]), std::get<2>(frames_shm[i])) << "frame " << i << " payload";
  }

  // Every declared, full-policy port crossed every cycle. TWO names, not
  // three (F-3): `sut.objects` is wired to `meas.objects`, and a `req` port
  // now takes its producing identity, so both the recorded topic and the
  // published frame carry that one name -- publishing the identical bytes a
  // second time under the consuming name would put two identities on one
  // signal, which is what F-3 removed.
  std::set<std::string> ports_seen;
  for (const Frame& f : frames_inproc) ports_seen.insert(std::get<1>(f));
  EXPECT_EQ(ports_seen, (std::set<std::string>{"meas.objects", "sut.outputs"}));
  EXPECT_EQ(frames_inproc.size(), kCycles * 2);
}

TEST(ItTrn01Transport, AbsentPublisherLeavesTheRunUnaffected) {
  // SW-0352's own non-perturbing guarantee, structural: a Runner with no
  // SetTransportPublisher call behaves exactly as every other WP-13 test
  // already proves -- this case exists only to name that the transport
  // wiring itself introduces no new failure mode when unused.
  StubComponent stub("it_trn01_none");
  ASSERT_TRUE(stub.ok());
  Harness h(3);
  auto constructed = Runner::Construct(h.spec, h.scheduler, h.bus, h.reader, {{"sut", stub.get()}}, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  auto outcome = std::move(constructed).value().Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();
  EXPECT_EQ(outcome.value().cycles_executed, 3u);
}

// ---------------------------------------------------------------------------
// UT-TRN-03 -- SW-0353: a slow player never slows the engine, and dropped
// frames are counted and reported.
// ---------------------------------------------------------------------------

TEST(ItTrn03SlowReader, EngineWallTimeIsUnaffectedAndDropCountIsExact) {
  constexpr std::size_t kCycles = 300;  // F-LONG's own "long enough to sample" spirit
  constexpr std::size_t kDepth = 4;     // small and deliberate -- most frames must drop
  // meas.objects (also carries sut's `objects` input, F-3) and sut.outputs.
  constexpr std::size_t kPortsPerCycle = 2;

  // -- Baseline: no publisher attached at all.
  StubComponent stub_baseline("it_trn03_baseline");
  ASSERT_TRUE(stub_baseline.ok());
  Harness baseline(kCycles);
  auto runner_baseline =
      Runner::Construct(baseline.spec, baseline.scheduler, baseline.bus, baseline.reader,
                        {{"sut", stub_baseline.get()}}, &baseline.writer_base);
  ASSERT_TRUE(runner_baseline.ok()) << runner_baseline.error().Format();
  const auto t0 = std::chrono::steady_clock::now();
  auto outcome_baseline = std::move(runner_baseline).value().Run();
  const auto baseline_wall = std::chrono::steady_clock::now() - t0;
  ASSERT_TRUE(outcome_baseline.ok()) << outcome_baseline.error().Format();

  // -- Slow reader: a publisher is attached but NEVER drained during the
  // run -- the worst case a slow consumer can be, on both transports.
  StubComponent stub_inproc("it_trn03_inproc");
  ASSERT_TRUE(stub_inproc.ok());
  Harness h_inproc(kCycles);
  simcore::transport::InProcessTransport transport_inproc(kDepth);
  auto runner_inproc = Runner::Construct(h_inproc.spec, h_inproc.scheduler, h_inproc.bus, h_inproc.reader,
                                         {{"sut", stub_inproc.get()}}, &h_inproc.writer_base);
  ASSERT_TRUE(runner_inproc.ok()) << runner_inproc.error().Format();
  Runner r_inproc = std::move(runner_inproc).value();
  r_inproc.SetTransportPublisher(&transport_inproc);
  const auto t1 = std::chrono::steady_clock::now();
  auto outcome_inproc = r_inproc.Run();
  const auto inproc_wall = std::chrono::steady_clock::now() - t1;
  ASSERT_TRUE(outcome_inproc.ok()) << outcome_inproc.error().Format();

  StubComponent stub_shm("it_trn03_shm");
  ASSERT_TRUE(stub_shm.ok());
  Harness h_shm(kCycles);
  simcore::transport::SharedMemoryTransport engine_side(
      "it_trn03_shm", simcore::transport::SharedMemoryTransport::Role::kEngine, kDepth);
  auto runner_shm = Runner::Construct(h_shm.spec, h_shm.scheduler, h_shm.bus, h_shm.reader,
                                      {{"sut", stub_shm.get()}}, &h_shm.writer_base);
  ASSERT_TRUE(runner_shm.ok()) << runner_shm.error().Format();
  Runner r_shm = std::move(runner_shm).value();
  r_shm.SetTransportPublisher(&engine_side);
  const auto t2 = std::chrono::steady_clock::now();
  auto outcome_shm = r_shm.Run();
  const auto shm_wall = std::chrono::steady_clock::now() - t2;
  ASSERT_TRUE(outcome_shm.ok()) << outcome_shm.error().Format();

  // Loose, deliberately generous bound -- catches a real block (Publish()
  // waiting on a reader that never comes), not a micro-benchmark. An
  // absolute floor is included because a baseline run near 0ms would make
  // any ratio meaningless.
  const auto floor = std::chrono::milliseconds(50);
  const auto baseline_ms = std::chrono::duration_cast<std::chrono::milliseconds>(baseline_wall);
  const auto bound = std::max(baseline_ms * 10, floor);
  EXPECT_LE(std::chrono::duration_cast<std::chrono::milliseconds>(inproc_wall), bound)
      << "InProcessTransport appears to have blocked the engine";
  EXPECT_LE(std::chrono::duration_cast<std::chrono::milliseconds>(shm_wall), bound)
      << "SharedMemoryTransport appears to have blocked the engine";

  // Exact, deterministic: with the ring never drained, every publish past
  // the first `kDepth` frames overwrites an unread slot -- the same
  // arithmetic TransportInproc/Shm.SlowConsumerDropsFramesNeverBlocksProducer
  // prove for a handful of frames, now over a real run's full port set.
  const std::uint64_t published = kCycles * kPortsPerCycle;
  ASSERT_GT(published, kDepth);
  const std::uint64_t expected_dropped = published - kDepth;
  EXPECT_EQ(transport_inproc.DroppedFrames(), expected_dropped);
  EXPECT_EQ(engine_side.DroppedFrames(), expected_dropped);
}

// ---------------------------------------------------------------------------
// UT-TRN-02 -- SW-0351: bulk data crosses intact through the mapped
// segment, over a real Runner-wired run.
// ---------------------------------------------------------------------------

std::vector<RawMessage> MakeBulkRecording(std::size_t cycles, std::size_t payload_bytes) {
  std::vector<RawMessage> messages;
  for (std::size_t i = 0; i < cycles; ++i) {
    RawMessage objects;
    objects.topic = "/meas/objects";
    objects.log_time_ns = static_cast<std::int64_t>(i) * kDtNs;
    objects.payload.resize(payload_bytes);
    // Deterministic, per-cycle-distinct content -- a copy bug (truncation,
    // a stale slot, an off-by-one on the wrap) would show up as a mismatch
    // against THIS exact pattern, not just "some bytes."
    for (std::size_t b = 0; b < payload_bytes; ++b) {
      objects.payload[b] = static_cast<std::uint8_t>((i * 7 + b) & 0xFF);
    }
    messages.push_back(objects);
  }
  return messages;
}

TEST(ItTrn02Bulk, BulkPayloadCrossesIntactThroughTheMappedSegment) {
  // Comfortably under kShmMaxFrameBytes (256 KiB, transport_shm.hpp) --
  // clearly "bulk" (SI-25's own F-BULK spirit: a payload large enough that
  // a copy or a truncation would be obvious, not a coincidence of small
  // numbers).
  constexpr std::size_t kPayloadBytes = 200'000;
  constexpr std::size_t kCycles = 3;
  // Generous: 3 declared ports x kCycles publishes total -- this test is
  // about payload integrity, not the drop path (that is UT-TRN-03's own
  // concern), so the ring must never fill during this run.
  constexpr std::size_t kDepth = 32;

  StubComponent stub("it_trn02_bulk");
  ASSERT_TRUE(stub.ok());

  RunSpec spec = MakeSpec();
  VectorReader reader(MakeBulkRecording(kCycles, kPayloadBytes), MakeTopics());
  simcore::scheduler::Scheduler scheduler(spec);
  simcore::bus::PortBus bus;
  NullWriter sink;
  simcore::io::WriterBase writer_base(sink);

  simcore::transport::SharedMemoryTransport engine_side(
      "it_trn02_shm", simcore::transport::SharedMemoryTransport::Role::kEngine, kDepth);
  simcore::transport::SharedMemoryTransport client_side(
      "it_trn02_shm", simcore::transport::SharedMemoryTransport::Role::kClient, kDepth);
  uint32_t engine_version = 0;
  ASSERT_EQ(client_side.attach(simcore::transport::SharedMemoryTransport::kProtocolVersion, &engine_version),
            adas::transport::AttachResult::kOk);

  auto constructed = Runner::Construct(spec, scheduler, bus, reader, {{"sut", stub.get()}}, &writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  runner.SetTransportPublisher(&engine_side);
  auto outcome = runner.Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();

  const std::vector<RawMessage> expected = MakeBulkRecording(kCycles, kPayloadBytes);
  std::size_t bulk_frames_checked = 0;
  adas::transport::PortFrame frame{};
  while (client_side.tryReceive(&frame)) {
    if (std::string(frame.portName) != "meas.objects") continue;  // sut.objects/outputs also cross, smaller
    // The received size must match exactly -- no silent truncation at
    // kShmMaxFrameBytes or anywhere else on the write path.
    ASSERT_EQ(frame.size, kPayloadBytes) << "tick " << frame.tickIndex;
    const auto& want = expected[frame.tickIndex].payload;
    ASSERT_EQ(want.size(), kPayloadBytes);
    EXPECT_EQ(std::memcmp(frame.data, want.data(), kPayloadBytes), 0)
        << "bulk payload corrupted in transit at tick " << frame.tickIndex;
    ++bulk_frames_checked;
  }
  EXPECT_EQ(bulk_frames_checked, kCycles);
}

// ---------------------------------------------------------------------------
// IT-19 -- SW-0298/SW-0352: attach and detach do not disturb a run already
// in progress.
// ---------------------------------------------------------------------------

// Byte-for-byte, no tolerance -- `SW-0298`/`SW-0352`'s own Accept clause.
bool MessagesEqual(const std::vector<RawMessage>& a, const std::vector<RawMessage>& b) {
  if (a.size() != b.size()) return false;
  for (std::size_t i = 0; i < a.size(); ++i) {
    if (a[i].topic != b[i].topic) return false;
    if (a[i].log_time_ns != b[i].log_time_ns) return false;
    if (a[i].payload != b[i].payload) return false;
  }
  return true;
}

TEST(ItTrn19MidRunAttach, AttachAndDetachDuringARunProduceIdenticalValuesAndDoNotStallTheEngine) {
  constexpr std::size_t kCycles = 200;
  constexpr std::size_t kDepth = 64;  // generous: this test is not about the drop path
  const auto kTickSleep = std::chrono::milliseconds(2);
  const auto kWindow = std::chrono::milliseconds(100);  // one phase's real-time budget

  // -- Control: no publisher attached at any point.
  StubComponent stub_ctrl("it_trn19_ctrl");
  ASSERT_TRUE(stub_ctrl.ok());
  RunSpec spec_ctrl = MakeSpec();
  VectorReader reader_ctrl(MakeRecording(kCycles), MakeTopics());
  simcore::scheduler::Scheduler scheduler_ctrl(spec_ctrl);
  simcore::bus::PortBus bus_ctrl;
  CapturingWriter sink_ctrl;
  simcore::io::WriterBase writer_base_ctrl(sink_ctrl);
  auto constructed_ctrl =
      Runner::Construct(spec_ctrl, scheduler_ctrl, bus_ctrl, reader_ctrl, {{"sut", stub_ctrl.get()}}, &writer_base_ctrl);
  ASSERT_TRUE(constructed_ctrl.ok()) << constructed_ctrl.error().Format();
  auto outcome_ctrl = std::move(constructed_ctrl).value().Run();
  ASSERT_TRUE(outcome_ctrl.ok()) << outcome_ctrl.error().Format();

  // -- Live run: a real background thread steps the engine cycle by cycle
  // with a real per-tick sleep, so the test thread has genuine wall-clock
  // room to attach and detach WHILE `StepOnce()` is mid-loop.
  StubComponent stub_live("it_trn19_live");
  ASSERT_TRUE(stub_live.ok());
  RunSpec spec_live = MakeSpec();
  VectorReader reader_live(MakeRecording(kCycles), MakeTopics());
  simcore::scheduler::Scheduler scheduler_live(spec_live);
  simcore::bus::PortBus bus_live;
  CapturingWriter sink_live;
  simcore::io::WriterBase writer_base_live(sink_live);
  simcore::transport::SharedMemoryTransport engine_side(
      "it_trn19_shm", simcore::transport::SharedMemoryTransport::Role::kEngine, kDepth);

  auto constructed_live =
      Runner::Construct(spec_live, scheduler_live, bus_live, reader_live, {{"sut", stub_live.get()}}, &writer_base_live);
  ASSERT_TRUE(constructed_live.ok()) << constructed_live.error().Format();
  Runner runner_live = std::move(constructed_live).value();
  runner_live.SetTransportPublisher(&engine_side);

  std::atomic<std::size_t> ticks_done{0};
  std::atomic<bool> engine_finished{false};
  const auto t_start = std::chrono::steady_clock::now();
  std::thread engine_thread([&]() {
    for (;;) {
      auto step = runner_live.StepOnce();
      ASSERT_TRUE(step.ok()) << step.error().Format();
      if (!step.value()) break;  // exhausted
      ticks_done.fetch_add(1, std::memory_order_release);
      std::this_thread::sleep_for(kTickSleep);
    }
    engine_finished.store(true, std::memory_order_release);
  });

  // Phase 1: no player. The minimum possible engine run time is
  // kCycles * kTickSleep, comfortably above 3 * kWindow, so the engine is
  // still mid-run at every checkpoint below.
  std::this_thread::sleep_for(kWindow);
  const auto t1 = std::chrono::steady_clock::now();
  const std::size_t ticks_phase1 = ticks_done.load(std::memory_order_acquire);
  ASSERT_FALSE(engine_finished.load(std::memory_order_acquire)) << "engine finished before the player attached";

  // Phase 2: attach WHILE the engine is mid-run, and drain a few live
  // frames to prove this is a real player, not an idle handle.
  simcore::transport::SharedMemoryTransport client_side(
      "it_trn19_shm", simcore::transport::SharedMemoryTransport::Role::kClient, kDepth);
  uint32_t engine_version = 0;
  ASSERT_EQ(client_side.attach(simcore::transport::SharedMemoryTransport::kProtocolVersion, &engine_version),
            adas::transport::AttachResult::kOk);
  std::size_t frames_drained = 0;
  const auto drain_until = std::chrono::steady_clock::now() + kWindow;
  while (std::chrono::steady_clock::now() < drain_until) {
    adas::transport::PortFrame frame{};
    if (client_side.tryReceive(&frame)) {
      ++frames_drained;
    } else {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  }
  EXPECT_GT(frames_drained, 0u) << "attached mid-run but never observed a live frame";
  const auto t2 = std::chrono::steady_clock::now();
  const std::size_t ticks_phase2 = ticks_done.load(std::memory_order_acquire);
  ASSERT_FALSE(engine_finished.load(std::memory_order_acquire)) << "engine finished before the player detached";

  // Phase 3: detach WHILE the engine is still mid-run, then let it run on
  // unattended to exhaustion.
  client_side.detach();
  std::this_thread::sleep_for(kWindow);
  const auto t3 = std::chrono::steady_clock::now();
  const std::size_t ticks_phase3 = ticks_done.load(std::memory_order_acquire);

  engine_thread.join();
  ASSERT_TRUE(engine_finished.load(std::memory_order_acquire));
  EXPECT_EQ(ticks_done.load(std::memory_order_acquire), kCycles);

  // The engine progressed through every phase -- no stall on attach, none
  // on detach.
  EXPECT_GT(ticks_phase1, 0u) << "no progress before the player ever attached";
  EXPECT_GT(ticks_phase2, ticks_phase1) << "no progress while the player was attached";
  EXPECT_GT(ticks_phase3, ticks_phase2) << "no progress after the player detached";

  // Generous per-phase rate bound, measured (not assumed) -- the `UT-TRN-03`
  // "regression catch for a real block, not a micro-benchmark" reasoning.
  // Baseline is phase 1's own measured ms/tick (no player at all); phases 2
  // (attached) and 3 (detached) must stay within a wide multiple of it. A
  // real stall (attach/detach blocking the engine) would blow this bound by
  // orders of magnitude, not by scheduler noise.
  auto ms_per_tick = [](std::chrono::steady_clock::time_point from, std::chrono::steady_clock::time_point to,
                        std::size_t ticks) {
    return std::chrono::duration<double, std::milli>(to - from).count() / static_cast<double>(ticks);
  };
  const double baseline_ms_per_tick = ms_per_tick(t_start, t1, ticks_phase1);
  const double phase2_ms_per_tick = ms_per_tick(t1, t2, ticks_phase2 - ticks_phase1);
  const double phase3_ms_per_tick = ms_per_tick(t2, t3, ticks_phase3 - ticks_phase2);
  const double floor_ms = 5.0;
  const double bound_ms_per_tick = std::max(baseline_ms_per_tick * 10.0, floor_ms);
  EXPECT_LE(phase2_ms_per_tick, bound_ms_per_tick)
      << "engine tick rate collapsed on attach (baseline " << baseline_ms_per_tick << " ms/tick, attached "
      << phase2_ms_per_tick << " ms/tick)";
  EXPECT_LE(phase3_ms_per_tick, bound_ms_per_tick)
      << "engine tick rate collapsed on detach (baseline " << baseline_ms_per_tick << " ms/tick, detached "
      << phase3_ms_per_tick << " ms/tick)";

  // SW-0298/SW-0352's own Accept clause: values identical to the control
  // run, regardless of the concurrent attach/detach.
  EXPECT_TRUE(MessagesEqual(sink_ctrl.messages(), sink_live.messages()))
      << "mid-run attach/detach altered the run's own output "
      << "(" << sink_ctrl.messages().size() << " vs " << sink_live.messages().size() << " messages)";
}

}  // namespace simcore::runner
