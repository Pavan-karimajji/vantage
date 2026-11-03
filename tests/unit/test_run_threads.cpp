// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `IMP-0034`..`IMP-0036` (`WP-07`, `ARCH §8`): the default of one thread, the
///   tickets of one rank that run side by side, the two things that never do
///   (two stages of one library path, a wired pair), and the commit order. The
///   rank's dispatcher is driven with plain tasks; the commit order and the
///   equal runs go through a `Runner` over two real components (`echo_stub`,
///   one a second copy of the file, one sleeping longer than the other). The
///   system tests `SYT-THR-01`..`03` run over a lab case in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <stdexcept>
#include <thread>

#include <google/protobuf/descriptor.h>

#include "run_fixtures.hpp"
#include "runner/rank_dispatch.hpp"
#include "simcore/runner.hpp"

namespace simcore::runner {
namespace {

using testing::CapturingWriter;
using testing::Data;
using testing::Message;
using testing::RefSyncOf;
using testing::Topic;
using testing::VectorReader;

constexpr std::int64_t kMs = 1'000'000;
using Clock = std::chrono::steady_clock;

// ---------------------------------------------------------------------------
// The dispatcher with plain tasks
// ---------------------------------------------------------------------------

SpecStage SimulateStage(const std::string& name, const std::string& library) {
  SpecStage stage;
  stage.name = name;
  stage.mode = "simulate";
  stage.impl.kind = "dll";
  stage.impl.path = library;
  return stage;
}

struct Span {
  Clock::time_point begin;
  Clock::time_point end;
  std::thread::id thread;
};

bool Overlap(const Span& a, const Span& b) { return a.begin < b.end && b.begin < a.end; }

// Runs `count` tasks of `work_ms` each through `DispatchRank`; the spans are in ticket order.
std::vector<Span> RunTasks(std::size_t count, int threads, const ConflictTable& table,
                           const std::vector<std::string>& stages, int work_ms = 80) {
  std::vector<Span> spans(count);
  DispatchRank(
      count, threads,
      [&](std::size_t earlier, std::size_t later) { return table.Conflicts(stages[earlier], stages[later]); },
      [&](std::size_t i) {
        spans[i].thread = std::this_thread::get_id();
        spans[i].begin = Clock::now();
        std::this_thread::sleep_for(std::chrono::milliseconds(work_ms));
        spans[i].end = Clock::now();
        return true;
      });
  return spans;
}

TEST(RunThreads, TheDefaultIsOneThreadAndEveryCallIsMadeOnTheCallingThread) {
  EXPECT_EQ(RunnerOptions{}.threads, 1);
  RunSpec spec;
  spec.stages = {SimulateStage("B", "/lib/b.dll"), SimulateStage("C", "/lib/c.dll"), SimulateStage("D", "/lib/d.dll")};
  const std::vector<Span> spans = RunTasks(3, RunnerOptions{}.threads, ConflictTable::FromSpec(spec), {"B", "C", "D"}, 10);
  for (const Span& span : spans) EXPECT_EQ(span.thread, std::this_thread::get_id());
  EXPECT_FALSE(Overlap(spans[0], spans[1]));
  EXPECT_FALSE(Overlap(spans[1], spans[2]));
}

TEST(RunThreads, WithMoreThreadsTwoStagesWithNothingBetweenThemOverlapOnWorkers) {
  RunSpec spec;
  spec.stages = {SimulateStage("B", "/lib/b.dll"), SimulateStage("C", "/lib/c.dll")};
  const ConflictTable table = ConflictTable::FromSpec(spec);
  ASSERT_TRUE(table.empty());
  const std::vector<Span> spans = RunTasks(2, 2, table, {"B", "C"});
  EXPECT_TRUE(Overlap(spans[0], spans[1]));
  EXPECT_NE(spans[0].thread, std::this_thread::get_id());
  EXPECT_NE(spans[1].thread, std::this_thread::get_id());
  EXPECT_NE(spans[0].thread, spans[1].thread);
}

TEST(RunThreads, TwoStagesOfOneLibraryPathNeverOverlapAndRunInDeclarationOrder) {
  RunSpec spec;
  spec.stages = {SimulateStage("B", "/lib/same.dll"), SimulateStage("C", "/lib/same.dll"),
                 SimulateStage("D", "/lib/other.dll")};
  const ConflictTable table = ConflictTable::FromSpec(spec);
  ASSERT_TRUE(table.Conflicts("B", "C"));
  const std::vector<Span> spans = RunTasks(3, 3, table, {"B", "C", "D"});
  EXPECT_FALSE(Overlap(spans[0], spans[1]));
  EXPECT_LE(spans[0].end, spans[1].begin);  // the later waits for the earlier's call to return
  EXPECT_TRUE(Overlap(spans[0], spans[2]));  // the guard holds back one pair, not the rank
}

TEST(RunThreads, TheSameFileUnderTwoSpellingsIsOneLibrary) {
  const std::filesystem::path dir = std::filesystem::temp_directory_path() / "vantage_run_threads_paths";
  std::filesystem::create_directories(dir / "sub");
  std::ofstream(dir / "lib.dll") << "x";
  RunSpec spec;
  spec.stages = {SimulateStage("B", (dir / "lib.dll").string()),
                 SimulateStage("C", (dir / "sub" / ".." / "lib.dll").string())};
  EXPECT_TRUE(ConflictTable::FromSpec(spec).Conflicts("B", "C"));
}

TEST(RunThreads, AWiredPairIsNeverRunSideBySideEvenThroughAPreviousCycleInput) {
  RunSpec spec;
  spec.stages = {SimulateStage("B", "/lib/b.dll"), SimulateStage("C", "/lib/c.dll"), SimulateStage("D", "/lib/d.dll")};
  SpecInput reads_b;
  reads_b.port = "in";
  reads_b.producer = "B";
  reads_b.producer_port = "out";
  reads_b.previous_cycle = true;
  spec.stages[1].inputs = {reads_b};
  const ConflictTable table = ConflictTable::FromSpec(spec);
  ASSERT_TRUE(table.Conflicts("B", "C"));
  ASSERT_FALSE(table.Conflicts("B", "D"));
  const std::vector<Span> spans = RunTasks(3, 3, table, {"B", "C", "D"});
  EXPECT_FALSE(Overlap(spans[0], spans[1]));
  EXPECT_LE(spans[0].end, spans[1].begin);
  EXPECT_TRUE(Overlap(spans[0], spans[2]));
}

TEST(RunThreads, AMeasuredStageAndTheRecordingAreNeverAConflict) {
  RunSpec spec;
  SpecStage measured = SimulateStage("A", "/lib/same.dll");
  measured.mode = "measured";
  spec.stages = {measured, SimulateStage("B", "/lib/same.dll"), SimulateStage("C", "/lib/c.dll")};
  SpecInput from_a;
  from_a.port = "in";
  from_a.producer = "A";
  from_a.producer_port = "out";
  SpecInput from_source = from_a;
  from_source.producer = "source";
  spec.stages[1].inputs = {from_a};
  spec.stages[2].inputs = {from_source};
  EXPECT_TRUE(ConflictTable::FromSpec(spec).empty());
}

TEST(RunThreads, AnExceptionOnAWorkerIsRethrownOnTheCallingThreadAfterTheBarrier) {
  std::atomic<int> finished{0};
  const auto dispatch = [&]() {
    DispatchRank(
        3, 3, [](std::size_t, std::size_t) { return false; },
        [&](std::size_t i) -> bool {
          std::this_thread::sleep_for(std::chrono::milliseconds(20));
          ++finished;
          if (i == 1) throw std::runtime_error("boom");
          return true;
        });
  };
  EXPECT_THROW(dispatch(), std::runtime_error);
  EXPECT_EQ(finished.load(), 3);
}

// ---------------------------------------------------------------------------
// A Runner over two real components
// ---------------------------------------------------------------------------

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

// One loaded `echo_stub`, copying `in` to `out`, sleeping `sleep_ms` in every exec. `copy_as` names a
// copy of the file made for it, so two stages come from two library paths.
class Stub {
 public:
  Stub(const std::string& copy_as, int sleep_ms) {
    const std::filesystem::path dir = std::filesystem::temp_directory_path() / "vantage_run_threads_libs";
    std::filesystem::create_directories(dir);
    path_ = dir / (copy_as + EchoStubPath().extension().string());
    std::error_code ec;
    std::filesystem::copy_file(EchoStubPath(), path_, std::filesystem::copy_options::overwrite_existing, ec);
    if (ec) return;
    const std::filesystem::path config = dir / (copy_as + ".sleep");
    std::ofstream(config) << sleep_ms << "\n";
    auto loaded = module_host::Component::Load(path_);
    if (!loaded.ok()) return;
    component_.emplace(std::move(loaded).value());
    if (!component_->Init(config).ok()) component_.reset();
  }
  bool ok() const { return component_.has_value(); }
  module_host::Component* get() { return &*component_; }
  std::string path() const { return path_.string(); }

 private:
  std::filesystem::path path_;
  std::optional<module_host::Component> component_;
};

SpecPort Port(const std::string& name, const std::string& dir, const std::string& type = "adas.common.CycleControl") {
  SpecPort port;
  port.name = name;
  port.dir = dir;
  port.kind = "data";
  port.proto_type = type;
  port.record = "full";
  port.buffer_depth = 8;
  return port;
}

SpecStage ControlStage(const std::string& name, const std::string& library) {
  SpecStage stage;
  stage.name = name;
  stage.mode = "simulate";
  stage.impl.kind = "dll";
  stage.impl.path = library;
  stage.trigger = "control";
  stage.ports = {Port("control", "req"), Port("in", "req"), Port("out", "pro"), Port("refSync", "pro", "adas.common.RefSync")};
  SpecInput in;
  in.port = "in";
  in.producer = "A";
  in.producer_port = "out";
  stage.inputs = {in};
  return stage;
}

// `A` (measured) makes `out`; `B` and `C` (simulate, control-started) read it and echo it.
RunSpec TwoStageSpec(const std::string& b_library, const std::string& c_library) {
  RunSpec spec;
  spec.run_id = "threads-test";
  spec.readiness_limit_steps = 2;
  spec.fallback_max_gap = 4;
  SpecStage a;
  a.name = "A";
  a.mode = "measured";
  a.ports = {Port("out", "pro")};
  spec.stages = {a, ControlStage("B", b_library), ControlStage("C", c_library)};
  return spec;
}

std::map<std::string, io::TopicInfo> TwoStageTopics() {
  std::map<std::string, io::TopicInfo> topics{{"/A/out", Topic("adas.common.CycleControl")}};
  for (const char* stage : {"B", "C"}) {
    const std::string base = std::string("/") + stage;
    topics[base + "/control"] = Topic("adas.common.CycleControl", io::Provenance::kSimulated);
    topics[base + "/refSync"] = Topic("adas.common.RefSync", io::Provenance::kSimulated);
    topics[base + "/out"] = Topic("adas.common.CycleControl", io::Provenance::kSimulated);
  }
  return topics;
}

// Three instants. Each stage's third refSync names the `A.out` sample 11 although 12 has arrived, so
// each stage's third output breaks the counter. It is paired with the recorded output of its own counter (11), which
// it equals (`IMP-0033`), so no first divergence is logged.
std::vector<io::RawMessage> TwoStageRecording() {
  std::vector<io::RawMessage> messages;
  const std::uint32_t named[3] = {10, 11, 11};
  for (int i = 0; i < 3; ++i) {
    const std::int64_t t = (i + 1) * 100 * kMs;
    messages.push_back(Message("/A/out", t, Data(10 + i, (i + 1) * 100'000)));
    for (const char* stage : {"B", "C"}) {
      const std::string base = std::string("/") + stage;
      messages.push_back(Message(base + "/control", t, Data(10 + i, (i + 1) * 100'000, i + 1)));
      messages.push_back(Message(base + "/refSync", t, RefSyncOf(10 + i, {{"in", named[i]}})));
      messages.push_back(Message(base + "/out", t, Data(10 + i, (i + 1) * 100'000)));
    }
  }
  return messages;
}

struct Outcome {
  bool ok = false;
  std::string error;
  std::vector<std::string> event_log;
  std::vector<std::pair<std::string, std::vector<std::uint8_t>>> written;
};

// Runs the two-stage case with `threads`; B sleeps `b_sleep_ms` in every exec, C sleeps nothing.
Outcome RunTwoStages(int threads, int b_sleep_ms, bool same_library = false) {
  Outcome outcome;
  EnvGuard name("ADAS_SIL_TEST_STUB_NAME", "threads_stub");
  EnvGuard out("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "out");
  EnvGuard in("ADAS_SIL_TEST_STUB_INPUT_PORT", "in");
  Stub b("stub_b", b_sleep_ms);
  Stub c("stub_c", 0);
  if (!b.ok() || !c.ok()) {
    outcome.error = "the echo_stub copies did not load";
    return outcome;
  }
  const RunSpec spec = TwoStageSpec(b.path(), same_library ? b.path() : c.path());
  VectorReader reader(TwoStageRecording(), TwoStageTopics());
  bus::PortBus bus;
  CapturingWriter sink;
  io::WriterBase writer(sink);
  Runner::Options options;
  options.threads = threads;
  auto built = Runner::Construct(spec, bus, {&reader}, {{"B", b.get()}, {"C", c.get()}},
                                 google::protobuf::DescriptorPool::generated_pool(), &writer, nullptr, options);
  if (!built.ok()) {
    outcome.error = built.error().Format();
    return outcome;
  }
  Runner runner = std::move(built).value();
  const auto ran = runner.Run();
  if (!ran.ok()) {
    outcome.error = ran.error().Format();
    return outcome;
  }
  outcome.ok = true;
  outcome.event_log = runner.EventLogLines();
  for (const io::RawMessage& message : sink.written) outcome.written.emplace_back(message.topic, message.payload);
  return outcome;
}

TEST(RunThreads, ResultsAreCommittedInStageDeclarationOrderWhateverOrderTheWorkersFinishIn) {
  // B is declared first and ends last (it sleeps 300 ms, C nothing).
  const Outcome run = RunTwoStages(2, 300);
  ASSERT_TRUE(run.ok) << run.error;
  ASSERT_EQ(run.event_log.size(), 2u);
  EXPECT_EQ(run.event_log[0], "event=degrade step=2 entry=output_counter_break stage=B port=out wanted=12 found=11");
  EXPECT_EQ(run.event_log[1], "event=degrade step=2 entry=output_counter_break stage=C port=out wanted=12 found=11");
}

TEST(RunThreads, AnEngineRunWithThreeThreadsEqualsTheRunWithOneByteForByte) {
  const Outcome one = RunTwoStages(1, 120);
  const Outcome three = RunTwoStages(3, 120);
  ASSERT_TRUE(one.ok) << one.error;
  ASSERT_TRUE(three.ok) << three.error;
  EXPECT_FALSE(one.written.empty());
  EXPECT_EQ(one.written, three.written);
  EXPECT_EQ(one.event_log, three.event_log);
}

TEST(RunThreads, TwoStagesOfOneLibraryPathGiveTheSameRunWithThreadsAsWithout) {
  const Outcome one = RunTwoStages(1, 0, true);
  const Outcome three = RunTwoStages(3, 0, true);
  ASSERT_TRUE(one.ok) << one.error;
  ASSERT_TRUE(three.ok) << three.error;
  EXPECT_EQ(one.written, three.written);
  EXPECT_EQ(one.event_log, three.event_log);
}

}  // namespace
}  // namespace simcore::runner
