// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `UT-RUN-01`..`UT-RUN-08` (`WP-13`, `SI-06` `runner`): the one
///   cycle loop, a measured stage as a pure source, an off stage's absent
///   ports, the injection boundary logged before tick 0, first-divergence
///   latching, the per-message informational-only flag, the per-cycle
///   checkpoint and the time slice.
///
///   **Fixtures.** `F-CHAIN4`/`F-SPEC`/`F-LONG` do not exist as reusable
///   test infrastructure yet, so this file builds a small self-contained
///   synthetic equivalent inline -- a four-stage spec and an in-test codec
///   (a `Reader`/`Writer` pair over a message vector, no file on disk) --
///   exactly what `WP-11`'s own row did for its synthetic message type.
///   `F-STUB` is real and is used as such: anything needing a loadable
///   `Component` uses the `echo_stub` fixture over the real generic ABI,
///   the same way `WP-10`'s tests did.
/// @author Pavan Karimajji

#include "simcore/runner.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include <gtest/gtest.h>

namespace simcore::runner {
namespace {

using simcore::io::Batch;
using simcore::io::RawMessage;
using simcore::io::ReadBounds;
using simcore::io::TopicInfo;

constexpr std::int64_t kDtNs = 10'000'000;  // 10 ms
constexpr std::uint8_t kStubPayload = 0xAB;  // echo_stub's own single output byte

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

// The in-test codec's read half. `ReadRange` delegates to the shared
// `detail::AccumulateBatch` (`IMP-0025`'s "the only read entry point")
// rather than re-implementing the three-axis bound logic, and counts what
// it actually pulled -- which is what `UT-RUN-08` asserts against in place
// of `IMP-0135`'s not-yet-existing byte counter.
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
      ++pulled_;
      pulled_bytes_ += messages_[index_].payload.size();
      return messages_[index_++];
    });
  }

  void Close() override {}
  std::optional<std::vector<std::uint8_t>> GetMeta(const std::string&) const override { return std::nullopt; }

  std::size_t pulled() const { return pulled_; }
  std::size_t pulled_bytes() const { return pulled_bytes_; }

 private:
  std::vector<RawMessage> messages_;
  std::map<std::string, TopicInfo> topics_;
  std::optional<RawMessage> lookahead_;
  std::size_t index_ = 0;
  std::size_t pulled_ = 0;
  std::size_t pulled_bytes_ = 0;
};

class CapturingWriter final : public simcore::io::Writer {
 public:
  Result<bool> Open(const std::filesystem::path&, const std::map<std::string, TopicInfo>&) override {
    return Result<bool>::Ok(true);
  }
  void Write(const RawMessage& message) override { written.push_back(message); }
  void WriteMeta(const std::string&, const std::vector<std::uint8_t>&) override {}
  void Close() override {}

  std::vector<RawMessage> written;
};

// The synthetic `F-CHAIN4` equivalent: a source-fed measured stage, a
// simulate stage consuming it, and an off stage. Every port carries a
// concrete `record` policy, as an emitted spec always does (`IMP-0009`).
SpecPort MakePort(const std::string& name, const std::string& dir, const std::string& record = "full") {
  SpecPort port;
  port.name = name;
  port.dir = dir;
  port.kind = "data";
  port.proto_type = "test.Bytes";
  port.record = record;
  return port;
}

RunSpec MakeSpec(const std::string& sut_output_port, const std::string& sut_record = "full") {
  RunSpec spec;
  spec.run_id = "20260821T000000Z-run13000";

  SpecStage measured;
  measured.name = "meas";
  measured.mode = "measured";
  measured.ports.push_back(MakePort("objects", "pro"));
  measured.ports.push_back(MakePort("stimulus", "req"));
  SpecInput measured_input;
  measured_input.port = "stimulus";
  measured_input.producer = "source";
  measured_input.producer_port = "stimulus";
  measured.inputs.push_back(measured_input);

  SpecStage sut;
  sut.name = "sut";
  sut.mode = "simulate";
  sut.clock_period_ns = kDtNs;  // the stage starts on its own clock: one run per recorded instant
  sut.ports.push_back(MakePort("objects", "req"));
  sut.ports.push_back(MakePort(sut_output_port, "pro", sut_record));
  SpecInput from_measured;
  from_measured.port = "objects";
  from_measured.producer = "meas";
  from_measured.producer_port = "objects";
  sut.inputs.push_back(from_measured);

  SpecStage dark;
  dark.name = "dark";
  dark.mode = "off";
  dark.ports.push_back(MakePort("unused", "pro"));

  spec.stages = {measured, sut, dark};
  return spec;
}

std::map<std::string, TopicInfo> MakeTopics(const std::string& sut_output_topic) {
  std::map<std::string, TopicInfo> topics;
  TopicInfo measured_info;
  measured_info.schema_name = "test.Bytes";
  measured_info.provenance = simcore::io::Provenance::kMeasured;
  topics["/source/stimulus"] = measured_info;
  topics["/meas/objects"] = measured_info;
  TopicInfo simulated_info;
  simulated_info.schema_name = "test.Bytes";
  simulated_info.provenance = simcore::io::Provenance::kSimulated;
  topics[sut_output_topic] = simulated_info;
  return topics;
}

// `cycles` cycles, three topics each, one `log_time_ns` per cycle.
// `sut_output` is what the recording claims the SUT produced -- the bytes
// `IMP-0116` compares this run's freshly-computed output against.
std::vector<RawMessage> MakeRecording(std::size_t cycles, const std::string& sut_output_topic,
                                      const std::vector<std::uint8_t>& sut_output) {
  std::vector<RawMessage> messages;
  for (std::size_t i = 0; i < cycles; ++i) {
    const std::int64_t t_ns = static_cast<std::int64_t>(i) * kDtNs;
    RawMessage stimulus;
    stimulus.topic = "/source/stimulus";
    stimulus.log_time_ns = t_ns;
    stimulus.payload = {static_cast<std::uint8_t>(i & 0xFF)};
    RawMessage objects;
    objects.topic = "/meas/objects";
    objects.log_time_ns = t_ns;
    objects.payload = {static_cast<std::uint8_t>(i & 0xFF), 0x01};
    RawMessage outputs;
    outputs.topic = sut_output_topic;
    outputs.log_time_ns = t_ns;
    outputs.payload = sut_output;
    messages.push_back(stimulus);
    messages.push_back(objects);
    messages.push_back(outputs);
  }
  return messages;
}

// One loaded, initialised `echo_stub` -- the real generic ABI, not a mock.
class StubComponent {
 public:
  explicit StubComponent(const std::string& output_port)
      : name_guard_("ADAS_SIL_TEST_STUB_NAME", "run_stub"),
        port_guard_("ADAS_SIL_TEST_STUB_OUTPUT_PORT", output_port) {
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
  explicit Harness(std::size_t cycles, const std::vector<std::uint8_t>& recorded_sut_output = {kStubPayload},
                   const std::string& sut_record = "full")
      : spec(MakeSpec("outputs", sut_record)),
        reader(MakeRecording(cycles, "/sut/outputs", recorded_sut_output), MakeTopics("/sut/outputs")),
        writer_base(sink) {}

  RunSpec spec;
  VectorReader reader;
  simcore::bus::PortBus bus;
  CapturingWriter sink;
  simcore::io::WriterBase writer_base;
};

}  // namespace

// ---------------------------------------------------------------------------
// UT-RUN-01 -- SW-0109: one loop. Run() reaches the same body as StepOnce().
// ---------------------------------------------------------------------------
TEST(UtRun01OneLoop, RunAndManualSteppingProduceByteIdenticalRuns) {
  StubComponent stub_a("outputs");
  ASSERT_TRUE(stub_a.ok());
  Harness a(5);
  auto runner_a = Runner::Construct(a.spec, a.bus, {&a.reader}, {{"sut", stub_a.get()}}, nullptr, &a.writer_base);
  ASSERT_TRUE(runner_a.ok()) << runner_a.error().Format();
  auto outcome_a = std::move(runner_a).value().Run();
  ASSERT_TRUE(outcome_a.ok()) << outcome_a.error().Format();

  StubComponent stub_b("outputs");
  ASSERT_TRUE(stub_b.ok());
  Harness b(5);
  auto runner_b = Runner::Construct(b.spec, b.bus, {&b.reader}, {{"sut", stub_b.get()}}, nullptr, &b.writer_base);
  ASSERT_TRUE(runner_b.ok()) << runner_b.error().Format();
  Runner stepped = std::move(runner_b).value();
  std::uint64_t steps = 0;
  for (;;) {
    auto step = stepped.StepOnce();
    ASSERT_TRUE(step.ok()) << step.error().Format();
    if (!step.value()) break;
    ++steps;
  }
  b.writer_base.Flush();

  EXPECT_EQ(outcome_a.value().cycles_executed, 5u);
  EXPECT_EQ(steps, outcome_a.value().cycles_executed);
  EXPECT_EQ(stepped.outcome().last_log_time_ns, outcome_a.value().last_log_time_ns);
  ASSERT_EQ(a.sink.written.size(), b.sink.written.size());
  for (std::size_t i = 0; i < a.sink.written.size(); ++i) {
    EXPECT_EQ(a.sink.written[i].topic, b.sink.written[i].topic);
    EXPECT_EQ(a.sink.written[i].log_time_ns, b.sink.written[i].log_time_ns);
    EXPECT_EQ(a.sink.written[i].payload, b.sink.written[i].payload);
  }
}

// ---------------------------------------------------------------------------
// UT-RUN-02 -- SW-0110: a measured stage is a pure source.
// ---------------------------------------------------------------------------
TEST(UtRun02MeasuredStage, PublishesItsDeclaredOutputsFromTheRecordingAndIsNeverLoaded) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(3);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  auto step = runner.StepOnce();
  ASSERT_TRUE(step.ok()) << step.error().Format();

  // Its declared `pro` port carries the recording's bytes, tagged with the
  // recording's own provenance -- never re-derived, never executed.
  const simcore::bus::SampleBuffer* buffer = h.bus.Buffer("meas.objects");
  ASSERT_NE(buffer, nullptr);
  ASSERT_NE(buffer->Newest(), nullptr);
  const simcore::bus::PortValue value = buffer->Newest()->value;
  EXPECT_EQ(value.origin, simcore::bus::Origin::Measured);
  EXPECT_EQ(value.header.producer, "meas");
  ASSERT_EQ(value.payload.size(), 2u);
  EXPECT_EQ(value.payload[1], 0x01);
}

TEST(UtRun02MeasuredStage, HandingAMeasuredStageALoadedComponentIsRefusedAtConstruction) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(2);
  auto constructed =
      Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}, {"meas", stub.get()}});
  ASSERT_FALSE(constructed.ok());
  EXPECT_EQ(constructed.error().kind, simcore::Kind::Authoring);
  EXPECT_NE(constructed.error().found.find("meas"), std::string::npos);
}

// ---------------------------------------------------------------------------
// UT-RUN-03 -- SW-0112: an off stage's ports are simply absent.
// ---------------------------------------------------------------------------
TEST(UtRun03OffStage, ContributesNoPortsAndIsIndistinguishableFromAnUnmappedInput) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(3);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  auto outcome = runner.Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();

  // The consumer's view of an off stage's port and of a name nothing ever
  // wired are the same value, produced by the same call -- there is no
  // second convention to tell them apart, which is the point (CN-0320).
  const simcore::bus::PortValue off_port = h.bus.Get("dark.unused", 0);
  const simcore::bus::PortValue never_wired = h.bus.Get("nothing.ever.wired.this", 0);
  EXPECT_EQ(off_port.origin, never_wired.origin);
  EXPECT_EQ(off_port.updated, never_wired.updated);
  EXPECT_EQ(off_port.payload.size(), never_wired.payload.size());
  EXPECT_EQ(off_port.origin, simcore::bus::Origin::Unknown);

  // ...and it contributes no topic to the recorder either.
  for (const RecordedTopic& topic : runner.RecordedTopics()) {
    EXPECT_NE(topic.stage, "dark");
  }
  for (const RawMessage& message : h.sink.written) {
    EXPECT_EQ(message.topic.find("/dark/"), std::string::npos);
  }
}

// ---------------------------------------------------------------------------
// UT-RUN-04 -- SW-0113: the injection boundary, logged before tick 0.
// ---------------------------------------------------------------------------
TEST(UtRun04InjectionBoundary, ComputedFromTheSpecAndLoggedOnceBeforeTheFirstCycle) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(4);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  ASSERT_TRUE(runner.Prepare().ok());

  // Before the first step: nothing has executed yet. The boundary is the
  // `event=run_start` line the engine prints with the plan; it is not an entry
  // of the event log (`WP-05`, decision of 2026-11-01).
  EXPECT_EQ(runner.outcome().cycles_executed, 0u);
  EXPECT_NE(runner.BoundaryLine().find("event=run_start"), std::string::npos);
  EXPECT_NE(runner.BoundaryLine().find("inject=meas.objects->sut.objects"), std::string::npos);
  EXPECT_NE(runner.BoundaryLine().find("source=stimulus"), std::string::npos);
  EXPECT_TRUE(runner.EventLogLines().empty());

  ASSERT_EQ(runner.Boundary().ports.size(), 1u);
  EXPECT_EQ(runner.Boundary().ports[0].producer, "meas");
  EXPECT_EQ(runner.Boundary().ports[0].consumer, "sut");
  ASSERT_EQ(runner.Boundary().source_ports.size(), 1u);
  EXPECT_EQ(runner.Boundary().source_ports[0], "stimulus");

  // Running the whole run adds no boundary entry to the event log.
  ASSERT_TRUE(runner.Run().ok());
  for (const std::string& line : runner.EventLogLines()) EXPECT_EQ(line.find("event=run_start"), std::string::npos);
}

// ---------------------------------------------------------------------------
// UT-RUN-05 -- SW-0116: divergence is detected at its FIRST occurrence.
// ---------------------------------------------------------------------------
TEST(UtRun05Divergence, FirstDivergenceIsLatchedAndIsIdenticalAcrossReRuns) {
  // The recording claims an output the stub never produces, from cycle 0 --
  // "command an actuation the recording does not contain".
  auto run_once = [](std::size_t cycles) {
    StubComponent stub("outputs");
    EXPECT_TRUE(stub.ok());
    Harness h(cycles, {0x01, 0x02});
    auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
    EXPECT_TRUE(constructed.ok());
    Runner runner = std::move(constructed).value();
    EXPECT_TRUE(runner.Run().ok());
    return runner.FirstDivergence();
  };

  const std::optional<Divergence> first = run_once(6);
  ASSERT_TRUE(first.has_value());
  EXPECT_EQ(first->tick_index, 0u);
  EXPECT_EQ(first->log_time_ns, 0);
  EXPECT_EQ(first->stage, "sut");
  EXPECT_EQ(first->port, "outputs");
  EXPECT_EQ(first->simulated_bytes, 1u);
  EXPECT_EQ(first->recorded_bytes, 2u);
  EXPECT_EQ(first->differing_bytes, 2u);  // one differing byte + one length byte

  const std::optional<Divergence> again = run_once(6);
  ASSERT_TRUE(again.has_value());
  EXPECT_EQ(again->tick_index, first->tick_index);
  EXPECT_EQ(again->log_time_ns, first->log_time_ns);
  EXPECT_EQ(again->differing_bytes, first->differing_bytes);
}

TEST(UtRun05Divergence, ALaterAgreementNeverClearsTheLatchAndALaterDifferenceNeverReplacesIt) {
  DivergenceLatch latch;
  const std::vector<std::uint8_t> a{0x01};
  const std::vector<std::uint8_t> b{0x02};
  latch.Observe(3, 30, "sut", "outputs", a, b);
  ASSERT_TRUE(latch.latched());
  EXPECT_EQ(latch.first()->tick_index, 3u);
  latch.Observe(4, 40, "sut", "outputs", a, a);  // back in agreement
  EXPECT_EQ(latch.first()->tick_index, 3u);
  latch.Observe(5, 50, "sut", "other", b, a);  // a second, different divergence
  EXPECT_EQ(latch.first()->tick_index, 3u);
  EXPECT_EQ(latch.first()->port, "outputs");
}

// ---------------------------------------------------------------------------
// UT-RUN-06 -- SW-0117: the flag is per message, past the grace window.
// ---------------------------------------------------------------------------
TEST(UtRun06InformationalOnly, EveryMessageWrittenPastTheGraceWindowCarriesTheFlagAndEarlierOnesDoNot) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(8, {0x01, 0x02});  // diverges at cycle 0
  Runner::Options options;
  options.grace_ticks = 3;
  auto constructed =
      Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base, nullptr, options);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  ASSERT_TRUE(runner.Run().ok());
  ASSERT_TRUE(runner.FirstDivergence().has_value());
  ASSERT_FALSE(h.sink.written.empty());

  // An ARBITRARY slice of the export: any message at or after
  // (divergence tick + grace) * dt is flagged; every earlier one is not.
  const std::int64_t flagged_from_ns = 3 * kDtNs;
  bool saw_flagged = false;
  bool saw_unflagged = false;
  for (const RawMessage& message : h.sink.written) {
    if (message.log_time_ns >= flagged_from_ns) {
      EXPECT_TRUE(message.informational_only) << message.topic << " @" << message.log_time_ns;
      saw_flagged = true;
    } else {
      EXPECT_FALSE(message.informational_only) << message.topic << " @" << message.log_time_ns;
      saw_unflagged = true;
    }
  }
  EXPECT_TRUE(saw_flagged);
  EXPECT_TRUE(saw_unflagged);
}

TEST(UtRun06InformationalOnly, ARunThatNeverDivergesNeverFlagsAMessage) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(5);  // the recording carries exactly what the stub produces
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  ASSERT_TRUE(runner.Run().ok());
  EXPECT_FALSE(runner.FirstDivergence().has_value());
  ASSERT_FALSE(h.sink.written.empty());
  for (const RawMessage& message : h.sink.written) {
    EXPECT_FALSE(message.informational_only);
  }
}

// ---------------------------------------------------------------------------
// UT-RUN-07 -- SW-0119: the checkpoint names the last COMPLETED cycle.
// ---------------------------------------------------------------------------
TEST(UtRun07Checkpoint, AnAbortedRunLeavesACheckpointAgreeingWithTheLastCycleInTheOutput) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(20);
  const std::filesystem::path progress =
      std::filesystem::temp_directory_path() / "simcore_ut_run_07_progress.json";
  std::filesystem::remove(progress);

  Checkpoint checkpoint(progress, h.spec.run_id);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  runner.SetCheckpoint(&checkpoint);

  // Three cycles complete, then the process "dies": the loop is abandoned
  // with no Flush, no Close and no return value -- exactly the state a
  // segfaulting component leaves behind, which is why the FILE and not the
  // return value is what `SW-0119` makes the record. (A real SIGSEGV in a
  // child process is `UT-ORC-08`'s own `F-STUB-CRASH` territory, one layer
  // up; what is asserted HERE is the invariant this file owns.)
  for (int i = 0; i < 3; ++i) {
    auto step = runner.StepOnce();
    ASSERT_TRUE(step.ok()) << step.error().Format();
    ASSERT_TRUE(step.value());
  }

  auto record = Checkpoint::Read(progress);
  ASSERT_TRUE(record.ok()) << record.error().Format();
  EXPECT_EQ(record.value().run_id, h.spec.run_id);
  EXPECT_TRUE(record.value().completed);
  EXPECT_EQ(record.value().tick_index, 2u);  // cycles 0,1,2 completed

  // ...and it agrees with the last cycle actually present in the output.
  h.writer_base.Flush();
  ASSERT_FALSE(h.sink.written.empty());
  EXPECT_EQ(h.sink.written.back().log_time_ns, record.value().log_time_ns);
  EXPECT_EQ(record.value().log_time_ns, 2 * kDtNs);
  std::filesystem::remove(progress);
}

// `IMP-0224` (`SW-0224`): the checkpoint carries the run's first
// divergence, the same way it already carries the last completed cycle --
// a supervisor process reads BOTH from the one file, without needing the
// crashed child's own return value (which a real crash never produces).
TEST(UtRun07Checkpoint, ProgressJsonCarriesTheFirstDivergenceOnceLatched) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  // Same fixture UT-RUN-05 uses: the recording claims an output the stub
  // never produces, from cycle 0.
  Harness h(4, {0x01, 0x02});
  const std::filesystem::path progress =
      std::filesystem::temp_directory_path() / "simcore_ut_run_07_divergence_progress.json";
  std::filesystem::remove(progress);

  Checkpoint checkpoint(progress, h.spec.run_id);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  runner.SetCheckpoint(&checkpoint);
  ASSERT_TRUE(runner.Run().ok());

  auto record = Checkpoint::Read(progress);
  ASSERT_TRUE(record.ok()) << record.error().Format();
  EXPECT_TRUE(record.value().has_divergence);
  EXPECT_EQ(record.value().divergence_tick_index, 0u);
  EXPECT_EQ(record.value().divergence_log_time_ns, 0);
  EXPECT_EQ(record.value().divergence_stage, "sut");
  EXPECT_EQ(record.value().divergence_port, "outputs");
  EXPECT_EQ(record.value().divergence_differing_bytes, 2u);
  std::filesystem::remove(progress);
}

TEST(UtRun07Checkpoint, ProgressJsonHasNoDivergenceFieldWhenNothingEverDiverged) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(3);  // the default recorded payload matches the stub's own output -- no divergence
  const std::filesystem::path progress =
      std::filesystem::temp_directory_path() / "simcore_ut_run_07_no_divergence_progress.json";
  std::filesystem::remove(progress);

  Checkpoint checkpoint(progress, h.spec.run_id);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  runner.SetCheckpoint(&checkpoint);
  ASSERT_TRUE(runner.Run().ok());

  auto record = Checkpoint::Read(progress);
  ASSERT_TRUE(record.ok()) << record.error().Format();
  EXPECT_FALSE(record.value().has_divergence);  // R-SIM-25: absent, never a guessed zero-tick divergence
  std::filesystem::remove(progress);
}

// `IMP-0139`: the per-port input capture `WriteReproducer`'s own
// `ReproducerInput::input_capture` needs, persisted by the SAME
// `Checkpoint` that already survives a crash for `progress.json` -- a
// black-box supervisor reads it back through `Checkpoint::ReadInputCapture`
// after the child that wrote it has already died.
TEST(UtRun07Checkpoint, InputCaptureNamesTheSameCycleAsProgressJsonAndSurvivesAnAbandonedRun) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(20);
  const std::filesystem::path progress =
      std::filesystem::temp_directory_path() / "simcore_ut_run_07b_progress.json";
  std::filesystem::remove(progress);
  std::filesystem::remove_all(std::filesystem::path(progress).concat("_input_capture"));

  Checkpoint checkpoint(progress, h.spec.run_id);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  runner.SetCheckpoint(&checkpoint);

  // Same "process dies mid-run" shape as the sibling test above -- no
  // Flush, no Close, just an abandoned loop after cycle 2.
  for (int i = 0; i < 3; ++i) {
    auto step = runner.StepOnce();
    ASSERT_TRUE(step.ok()) << step.error().Format();
    ASSERT_TRUE(step.value());
  }

  auto record = Checkpoint::Read(progress);
  ASSERT_TRUE(record.ok()) << record.error().Format();

  // The supervisor's own read half -- a free function over the path, never
  // a method on a Checkpoint instance the supervisor never constructed.
  const auto capture = Checkpoint::ReadInputCapture(progress);
  ASSERT_TRUE(capture.count("sut.objects"));
  // Cycle 2's own recorded stimulus (MakeRecording's own encoding: byte i,
  // then 0x01) -- the exact bytes StepOnce delivered to "sut"'s "objects"
  // req port that cycle, not a re-derived or estimated value.
  const std::vector<std::uint8_t> expected = {static_cast<std::uint8_t>(record.value().tick_index), 0x01};
  EXPECT_EQ(capture.at("sut.objects"), expected);

  std::filesystem::remove(progress);
  std::filesystem::remove_all(std::filesystem::path(progress).concat("_input_capture"));
}

TEST(UtRun07Checkpoint, ReadInputCaptureIsAnEmptyMapNotAnErrorWhenNoneWasEverWritten) {
  const std::filesystem::path progress =
      std::filesystem::temp_directory_path() / "simcore_ut_run_07c_never_written.json";
  std::filesystem::remove(progress);
  EXPECT_TRUE(Checkpoint::ReadInputCapture(progress).empty());
}

TEST(UtRun07Checkpoint, NoCycleCompletedWritesNoFileRatherThanClaimingCycleZero) {
  const std::filesystem::path progress =
      std::filesystem::temp_directory_path() / "simcore_ut_run_07_empty.json";
  std::filesystem::remove(progress);
  Checkpoint checkpoint(progress, "run-none");
  checkpoint.Flush();
  EXPECT_FALSE(std::filesystem::exists(progress));
  auto record = Checkpoint::Read(progress);
  EXPECT_FALSE(record.ok());
  EXPECT_EQ(record.error().kind, simcore::Kind::Environment);
}

// ---------------------------------------------------------------------------
// UT-RUN-08 -- SW-0120: a time-sliced run costs the slice.
// ---------------------------------------------------------------------------
TEST(UtRun08Slice, ExecutesOnlyTheRequestedRangeAndReadsFarLessThanTheWholeRecording) {
  // The full run, for the baseline both halves are compared against.
  std::size_t full_pulled = 0;
  {
    StubComponent stub("outputs");
    ASSERT_TRUE(stub.ok());
    Harness h(100);
    Runner::Options options;
    options.read_bounds.max_messages = 8;
    auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base,
                                         nullptr, options);
    ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
    auto outcome = std::move(constructed).value().Run();
    ASSERT_TRUE(outcome.ok()) << outcome.error().Format();
    EXPECT_EQ(outcome.value().cycles_executed, 100u);
    full_pulled = h.reader.pulled();
  }

  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(100);
  Runner::Options options;
  options.read_bounds.max_messages = 8;
  options.slice.start_log_time_ns = 50 * kDtNs;
  options.slice.end_log_time_ns = 60 * kDtNs;
  auto constructed =
      Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base, nullptr, options);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  auto outcome = std::move(constructed).value().Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();

  EXPECT_EQ(outcome.value().cycles_executed, 10u);
  EXPECT_EQ(outcome.value().last_log_time_ns, 59 * kDtNs);
  // The cost scales with the slice, not the file. Asserted here on the
  // reader's own pulled-message count; `UtRun15ByteCounter` below is the
  // byte-level form of this same claim, now that `IMP-0135`'s counter is
  // wired into the live cycle loop.
  EXPECT_GT(full_pulled, 0u);
  EXPECT_LT(h.reader.pulled(), full_pulled / 4);
}

// ---------------------------------------------------------------------------
// UT-RUN-15 -- IMP-0135: `ByteCounter` wired into the live cycle loop.
// ---------------------------------------------------------------------------
TEST(UtRun15ByteCounter, PerTopicAndTotalMatchWhatWasActuallyReadNeverEstimated) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(5);
  diagnostics::ByteCounter counter;
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  runner.SetByteCounter(&counter);

  auto outcome = runner.Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();
  ASSERT_EQ(outcome.value().cycles_executed, 5u);

  // `pulled_bytes()` is the reader's own ground truth for what was actually
  // read off the wire (same role it plays for `UtRun08Slice` above) --
  // `ByteCounter::Total()` must equal it exactly, never estimated from
  // timing or message count.
  EXPECT_EQ(counter.Total(), h.reader.pulled_bytes());
  EXPECT_GT(counter.Total(), 0u);

  // Per-topic: `/source/stimulus` carries one byte per cycle, 5 cycles.
  EXPECT_EQ(counter.ForTopic("/source/stimulus"), 5u);
  // An unpulled topic reports exactly zero, never derived from timing.
  EXPECT_EQ(counter.ForTopic("/topic/never/pulled"), 0u);
}

TEST(UtRun15ByteCounter, NoCounterAttachedCostsNothingExtraAndChangesNoBehaviour) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(5);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  // Deliberately no SetByteCounter call -- the nullable-pointer default.
  auto outcome = std::move(constructed).value().Run();
  ASSERT_TRUE(outcome.ok()) << outcome.error().Format();
  EXPECT_EQ(outcome.value().cycles_executed, 5u);
}

// ---------------------------------------------------------------------------
// IMP-0114 -- the recorder's topic list is DERIVED from the spec's ports.
// ---------------------------------------------------------------------------
TEST(UtRun14RecordPolicy, EveryDeclaredPortOfANonOffStageBecomesATopicAndCarriesItsOwnPolicy) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(4);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  Runner runner = std::move(constructed).value();
  // meas: objects (pro) + stimulus (req); sut: objects (req) + outputs (pro).
  //
  // Four declared ports, THREE topics (F-3): a `req` port is recorded under
  // its PRODUCING address, so `sut.objects` -- wired to `meas.objects` --
  // resolves onto the topic `meas` already owns as its own `pro` output.
  // One signal, one topic, one value; which port received it stays
  // answerable from the spec's own wiring.
  std::map<std::string, std::string> topic_by_port;
  for (const RecordedTopic& topic : runner.RecordedTopics()) {
    EXPECT_EQ(topic.policy.verb, RecordVerb::kFull);
    topic_by_port[topic.qualified_port] = topic.topic;
  }
  ASSERT_EQ(runner.RecordedTopics().size(), 3u);
  EXPECT_EQ(topic_by_port["meas.objects"], "/meas/objects");   // pro: its own address
  EXPECT_EQ(topic_by_port["meas.stimulus"], "/source/stimulus");  // req: its producer's
  EXPECT_EQ(topic_by_port["sut.outputs"], "/sut/outputs");
  EXPECT_EQ(topic_by_port.count("sut.objects"), 0u);  // deduped onto /meas/objects
}

TEST(UtRun14RecordPolicy, AnExcludedPortIsNeverWrittenAndADecimatedOneIsWrittenEveryNthCycle) {
  {
    StubComponent stub("outputs");
    ASSERT_TRUE(stub.ok());
    Harness h(6, {kStubPayload}, "excluded");
    auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
    ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
    ASSERT_TRUE(std::move(constructed).value().Run().ok());
    for (const RawMessage& message : h.sink.written) {
      EXPECT_NE(message.topic, "/sut/outputs");
    }
    EXPECT_FALSE(h.sink.written.empty());  // the other three ports still recorded
  }
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(6, {kStubPayload}, "decimate:3");
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  ASSERT_TRUE(std::move(constructed).value().Run().ok());
  std::size_t decimated = 0;
  for (const RawMessage& message : h.sink.written) {
    if (message.topic == "/sut/outputs") ++decimated;
  }
  EXPECT_EQ(decimated, 2u);  // cycles 0 and 3 of 0..5
}

TEST(UtRun14RecordPolicy, AnUnparsablePolicyIsAnAuthoringErrorNamingThePortRatherThanASilentFull) {
  auto parsed = ParseRecordPolicy("sometimes", "port 'sut.outputs'");
  ASSERT_FALSE(parsed.ok());
  EXPECT_EQ(parsed.error().kind, simcore::Kind::Authoring);
  EXPECT_NE(parsed.error().where.find("sut.outputs"), std::string::npos);
  auto bare = ParseRecordPolicy("decimate", "port 'sut.outputs'");
  EXPECT_FALSE(bare.ok());
  auto zero = ParseRecordPolicy("decimate:0", "port 'sut.outputs'");
  EXPECT_FALSE(zero.ok());
}

// Regression coverage for a real defect found in code review (2026-08-21):
// a `req` (input) port's `RecordedTopic` was being looked up on the bus
// under its OWN stage-local name ("sut.objects"), but the bus only ever
// holds a value under its PRODUCER's qualified name ("meas.objects") --
// every declared `req` topic was therefore silently never written, despite
// carrying a `full` record policy. This asserts both `req` topics a stage
// graph can declare actually land in the output: a `simulate` stage's own
// input (delivered via `delivered_req_`, the per-cycle post-mutation echo)
// and a `measured` stage's own input (resolved straight off the bus, since
// nothing consumes it in this process).
TEST(UtRun14RecordPolicy, EveryDeclaredInputPortIsAlsoWritten) {
  StubComponent stub("outputs");
  ASSERT_TRUE(stub.ok());
  Harness h(2);
  auto constructed = Runner::Construct(h.spec, h.bus, {&h.reader}, {{"sut", stub.get()}}, nullptr, &h.writer_base);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  ASSERT_TRUE(std::move(constructed).value().Run().ok());

  auto find = [&](const std::string& topic, std::int64_t t_ns) -> const RawMessage* {
    for (const RawMessage& message : h.sink.written) {
      if (message.topic == topic && message.log_time_ns == t_ns) return &message;
    }
    return nullptr;
  };

  // "meas" is a `measured` stage; its own declared `req` port ("stimulus")
  // resolves to producer "source" and is read straight off the bus -- and
  // since F-3 it is recorded under that PRODUCING address, which is the
  // name a later run would have to wire to in order to re-simulate this
  // recording rather than only replay it.
  const RawMessage* meas_stimulus = find("/source/stimulus", 0);
  ASSERT_NE(meas_stimulus, nullptr);
  EXPECT_EQ(meas_stimulus->payload, (std::vector<std::uint8_t>{0}));
  EXPECT_EQ(find("/meas/stimulus", 0), nullptr);  // the consuming address is not used

  // "sut" is a `simulate` stage; its own declared `req` port ("objects") is
  // wired to `meas.objects` and is carried by that topic. With no override
  // declared, the delivered bytes and the producer's bytes are the same
  // value, so a second topic would be a byte-identical duplicate.
  const RawMessage* sut_input = find("/meas/objects", kDtNs);
  ASSERT_NE(sut_input, nullptr);
  EXPECT_EQ(find("/sut/objects", kDtNs), nullptr);
}

TEST(UtRun14RecordPolicy, TopicAndPortNameRoundTrip) {
  EXPECT_EQ(TopicToPortName("/source/veh_dyn"), "source.veh_dyn");
  EXPECT_EQ(TopicToPortName("/df/fn.outputs"), "df.fn.outputs");
  EXPECT_EQ(PortNameToTopic("source.veh_dyn"), "/source/veh_dyn");
  EXPECT_EQ(PortNameToTopic("df.fn.outputs"), "/df/fn.outputs");
}

}  // namespace simcore::runner
