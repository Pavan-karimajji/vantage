// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-TRN-05` (`WP-27`, `SW-0356`, `SI-25` `transport`)'s own real
///   "engine" -- a standalone process (not a linked-in test body) so the
///   test that spawns it can genuinely kill it, the same real-crash shape
///   `module_host::RunIsolatedStage`'s own POSIX/Windows halves already
///   spawn/reap, and `TransportShm`'s unit-level `fork()`/`TerminateProcess`
///   tests already use for the transport object alone -- this file is what
///   puts a real `Runner`/`echo_stub` in that loop instead.
///
///   argv: [shm_name, cycles, tick_sleep_ms]. Runs a real `Runner` step by
///   step (not `Run()`, so a per-tick sleep is meaningful) over
///   `SharedMemoryTransport(Role::kEngine)`, sleeping `tick_sleep_ms`
///   between cycles so the spawning test has ample real time to attach,
///   observe live frames, and kill this process mid-run. `echo_stub`'s
///   directory is read from `ADAS_SIM_TEST_FIXTURE_DIR` (same compile
///   definition `simcore_tests` itself uses, `tests/CMakeLists.txt`).
///
///   Exits 0 if it runs to completion WITHOUT being killed -- never
///   expected in `UT-TRN-05` itself, but real hygiene: a caller running
///   this fixture standalone (not killing it) gets a clean, honest exit
///   rather than a hang.
/// @author Pavan Karimajji

#include "simcore/runner.hpp"
#include "simcore/transport_shm.hpp"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <thread>
#include <vector>

namespace {

using simcore::Result;
using simcore::io::Batch;
using simcore::io::RawMessage;
using simcore::io::ReadBounds;
using simcore::io::TopicInfo;

constexpr std::int64_t kDtNs = 10'000'000;  // 10 ms

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

void SetEnv(const char* name, const std::string& value) {
#if defined(_WIN32)
  _putenv_s(name, value.c_str());
#else
  setenv(name, value.c_str(), 1);
#endif
}

// Same in-test codec shape test_it_transport.cpp's own VectorReader/
// NullWriter use -- duplicated rather than shared across a gtest binary
// and this plain executable, which link differently (this file has no
// GTest dependency at all, deliberately: a spawned "engine" process is
// not a test).
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

simcore::RunSpec MakeSpec() {
  simcore::RunSpec spec;
  spec.run_id = "20260824T000000Z-it-trn-05";

  auto make_port = [](const std::string& name, const std::string& dir) {
    simcore::SpecPort port;
    port.name = name;
    port.dir = dir;
    port.kind = "data";
    port.proto_type = "test.Bytes";
    port.record = "full";
    return port;
  };

  simcore::SpecStage measured;
  measured.name = "meas";
  measured.mode = "measured";
  measured.ports.push_back(make_port("objects", "pro"));

  simcore::SpecStage sut;
  sut.name = "sut";
  sut.mode = "simulate";
  sut.clock_period_ns = kDtNs;  // one run per recorded instant
  sut.ports.push_back(make_port("objects", "req"));
  sut.ports.push_back(make_port("outputs", "pro"));
  simcore::SpecInput from_measured;
  from_measured.port = "objects";
  from_measured.producer = "meas";
  from_measured.producer_port = "objects";
  sut.inputs.push_back(from_measured);

  spec.stages = {measured, sut};
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
    objects.payload = {static_cast<std::uint8_t>(i & 0xFF), 0x03};
    messages.push_back(objects);
  }
  return messages;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 4) {
    std::cerr << "usage: trn_engine_host <shm_name> <cycles> <tick_sleep_ms>\n";
    return 2;
  }
  const std::string shm_name = argv[1];
  const std::size_t cycles = static_cast<std::size_t>(std::stoul(argv[2]));
  const auto tick_sleep = std::chrono::milliseconds(std::stoul(argv[3]));

  SetEnv("ADAS_SIL_TEST_STUB_NAME", "trn_engine_host");
  SetEnv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs");
  auto loaded = simcore::module_host::Component::Load(EchoStubPath());
  if (!loaded.ok()) {
    std::cerr << "Component::Load failed: " << loaded.error().Format() << "\n";
    return 1;
  }
  simcore::module_host::Component component = std::move(loaded).value();
  if (!component.Init().ok()) {
    std::cerr << "Component::Init failed\n";
    return 1;
  }

  simcore::RunSpec spec = MakeSpec();
  VectorReader reader(MakeRecording(cycles), MakeTopics());
  simcore::bus::PortBus bus;
  NullWriter sink;
  simcore::io::WriterBase writer_base(sink);

  simcore::transport::SharedMemoryTransport engine_side(
      shm_name, simcore::transport::SharedMemoryTransport::Role::kEngine, /*depth=*/64);

  auto constructed =
      simcore::runner::Runner::Construct(spec, bus, {&reader}, {{"sut", &component}}, nullptr, &writer_base);
  if (!constructed.ok()) {
    std::cerr << "Runner::Construct failed: " << constructed.error().Format() << "\n";
    return 1;
  }
  simcore::runner::Runner runner = std::move(constructed).value();
  runner.SetTransportPublisher(&engine_side);

  for (;;) {
    auto step = runner.StepOnce();
    if (!step.ok()) {
      std::cerr << "StepOnce failed: " << step.error().Format() << "\n";
      return 1;
    }
    if (!step.value()) break;  // exhausted
    std::this_thread::sleep_for(tick_sleep);
  }
  return 0;  // never expected to be observed by UT-TRN-05 -- it kills this first
}
