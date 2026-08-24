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
///   **Not attempted this pass, named rather than silently dropped:**
///   `UT-TRN-02` (`F-BULK`, channel-usage observation -- already proven at
///   unit level, `TransportShm.DataCrossesThroughTheMappedSegmentNotACopyOnTheStack`,
///   and this implementation has no second control channel to observe,
///   `SW-0351`'s own "may" clause, `transport_shm.hpp`'s top note);
///   `UT-TRN-05` (`F-STUB-CRASH`, a real killed engine process with a
///   player attached -- `TransportShm`'s own unit tests already prove the
///   OS-level liveness mechanism itself via `fork()`/`TerminateProcess`,
///   but not through a real `Runner` in the loop); `IT-19` (measured tick
///   rate with a player attaching mid-run, then detaching). `UT-TRN-04`
///   (version negotiation) needed no IT-level repeat: `attach()` never
///   touches the scheduler or the bus, so `TransportInproc`/
///   `TransportShm.VersionMismatchRefusedBeforeAnyDataCrosses` already
///   exercise the real code path end to end.
/// @author Pavan Karimajji

#include "simcore/runner.hpp"
#include "simcore/transport.hpp"
#include "simcore/transport_shm.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <set>
#include <string>
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

  // All three declared, full-policy ports (meas.objects, sut.objects req,
  // sut.outputs) crossed every cycle.
  std::set<std::string> ports_seen;
  for (const Frame& f : frames_inproc) ports_seen.insert(std::get<1>(f));
  EXPECT_EQ(ports_seen, (std::set<std::string>{"meas.objects", "sut.objects", "sut.outputs"}));
  EXPECT_EQ(frames_inproc.size(), kCycles * 3);
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
  constexpr std::size_t kPortsPerCycle = 3;  // meas.objects, sut.objects, sut.outputs

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

}  // namespace simcore::runner
