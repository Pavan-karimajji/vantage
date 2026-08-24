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
///   **Not attempted this pass, named rather than silently dropped:**
///   `UT-TRN-02` (`F-BULK`, channel-usage observation -- already proven at
///   unit level, `TransportShm.DataCrossesThroughTheMappedSegmentNotACopyOnTheStack`,
///   and this implementation has no second control channel to observe,
///   `SW-0351`'s own "may" clause, `transport_shm.hpp`'s top note);
///   `UT-TRN-03` (`F-LONG`, measured engine tick rate with/without a slow
///   reader -- needs a real timing harness, `IT-19`'s own sibling
///   concern); `UT-TRN-05` (`F-STUB-CRASH`, a real killed engine process
///   with a player attached -- `TransportShm`'s own unit tests already
///   prove the OS-level liveness mechanism itself via `fork()`/
///   `TerminateProcess`, but not through a real `Runner` in the loop);
///   `IT-19` (measured tick rate with a player attaching mid-run). `UT-TRN-04`
///   (version negotiation) needed no IT-level repeat: `attach()` never
///   touches the scheduler or the bus, so `TransportInproc`/
///   `TransportShm.VersionMismatchRefusedBeforeAnyDataCrosses` already
///   exercise the real code path end to end.
/// @author Pavan Karimajji

#include "simcore/runner.hpp"
#include "simcore/transport.hpp"
#include "simcore/transport_shm.hpp"

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

}  // namespace simcore::runner
