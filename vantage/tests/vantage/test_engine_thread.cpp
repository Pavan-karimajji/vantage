// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   UT-VTG-04.. (engine integration plan E-4): the hand-over (bounded, oldest dropped and counted, never
///   blocks), the worker's pause / step / pace / step-locked behaviour and clean stop from every state, over
///   a fake cycle source -- and R-SIM-5's claim that the published ticks are the same at "max" and at a
///   paced rate, over the real embedded engine (echo stub always; any run spec named by
///   VANTAGE_DETERMINISM_SPEC too, e.g. a df run). No window.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "vantage/engine_thread.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <memory>
#include <future>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <gtest/gtest.h>

#include "simcore/io.hpp"

namespace {

using namespace std::chrono_literals;
using sim::vantage::EngineThread;
using sim::vantage::PaceSetting;
using sim::vantage::TickHandoff;

viz::session::Tick TickNumber(std::size_t index) {
  viz::session::Tick tick;
  tick.index = index;
  tick.t_ns = static_cast<std::int64_t>(index);
  return tick;
}

// UT-VTG-04.c1 -- the hand-over is bounded: past its capacity the OLDEST ticks are dropped and counted, the
// newest are kept in order. .c2 -- Push never waits (it returns with the queue full and nobody popping);
// TryPop on an empty hand-over returns at once.
TEST(TickHandoffTest, UT_VTG_04_IsBoundedDropsTheOldestAndCountsAndNeverBlocks) {
  TickHandoff handoff(4);
  EXPECT_FALSE(handoff.TryPop().has_value());  // .c2: empty, returns at once
  for (std::size_t i = 0; i < 10; ++i) {
    handoff.Push(TickNumber(i));  // .c2: nobody pops, and Push never waits
  }
  EXPECT_EQ(handoff.Size(), 4u);
  EXPECT_EQ(handoff.Dropped(), 6u);  // .c1
  for (std::size_t expected = 6; expected < 10; ++expected) {
    auto popped = handoff.TryPop();
    ASSERT_TRUE(popped.has_value());
    EXPECT_EQ(popped->tick.index, expected) << "the newest four, oldest first";
    EXPECT_EQ(popped->seq, expected + 1) << "sequence numbers count every push, drops included";
  }
  EXPECT_FALSE(handoff.TryPop().has_value());
}

// A fake cycle source: `Next()` returns cycle numbers 0.. up to `total`, and tells the test each time it is
// called, so a test can wait for "the engine stepped" without sleeping in a loop.
struct FakeState {
  std::mutex mutex;
  std::condition_variable cv;
  std::size_t calls = 0;
  std::size_t total = 1000000;
  bool fail_at_end = false;

  bool WaitForCalls(std::size_t n, std::chrono::milliseconds timeout) {
    std::unique_lock<std::mutex> lock(mutex);
    return cv.wait_for(lock, timeout, [&] { return calls >= n; });
  }
  std::size_t Calls() {
    std::lock_guard<std::mutex> lock(mutex);
    return calls;
  }
};

class FakeSource final : public sim::vantage::CycleSource {
 public:
  explicit FakeSource(std::shared_ptr<FakeState> state) : state_(std::move(state)) {}
  ~FakeSource() override { destroyed_on_ = std::this_thread::get_id(); }
  std::optional<viz::session::Tick> Next() override {
    std::lock_guard<std::mutex> lock(state_->mutex);
    if (state_->calls >= state_->total) {
      ok_ = !state_->fail_at_end;
      if (!ok_) error_ = "boom";
      return std::nullopt;
    }
    viz::session::Tick tick = TickNumber(state_->calls);
    ++state_->calls;
    state_->cv.notify_all();
    return tick;
  }
  bool ok() const override { return ok_; }
  const std::string& error() const override { return error_; }

 private:
  std::shared_ptr<FakeState> state_;
  bool ok_ = true;
  std::string error_;
  std::thread::id destroyed_on_;
};

sim::vantage::CycleSourceFactory FakeFactory(std::shared_ptr<FakeState> state, std::thread::id* created_on = nullptr) {
  return [state, created_on](std::string*) -> std::unique_ptr<sim::vantage::CycleSource> {
    if (created_on != nullptr) *created_on = std::this_thread::get_id();
    return std::make_unique<FakeSource>(state);
  };
}

// Stops an EngineThread and fails the test rather than hanging it if the worker does not come back.
void ExpectStopsPromptly(EngineThread& engine) {
  auto done = std::async(std::launch::async, [&engine] { engine.Stop(); });
  EXPECT_EQ(done.wait_for(5s), std::future_status::ready) << "Stop() did not return: the worker is stuck";
  if (done.wait_for(0s) != std::future_status::ready) {
    std::abort();  // a stuck worker cannot be joined; do not hang the whole test run behind it
  }
}

// UT-VTG-05.c1 -- a source that cannot be created fails Start with its error and leaves nothing running.
// .c2 -- the engine is created on the worker thread, never the caller's (every engine call happens there).
TEST(EngineThreadTest, UT_VTG_05_CreationFailureIsReportedAndTheEngineIsCreatedOnTheWorker) {
  EngineThread broken([](std::string* error) -> std::unique_ptr<sim::vantage::CycleSource> {
    *error = "no such run spec";
    return nullptr;
  });
  std::string error;
  EXPECT_FALSE(broken.Start(&error));
  EXPECT_EQ(error, "no such run spec");

  auto state = std::make_shared<FakeState>();
  std::thread::id created_on;
  EngineThread engine(FakeFactory(state, &created_on));
  ASSERT_TRUE(engine.Start(&error));
  EXPECT_NE(created_on, std::this_thread::get_id());  // .c2
  ExpectStopsPromptly(engine);
}

// UT-VTG-06.c1 -- at pace "max" every cycle is produced in order and the run's end is reported as finished
// (not failed). .c2 -- a source that fails at the end is reported as failed with its error.
TEST(EngineThreadTest, UT_VTG_06_MaxPaceProducesEveryCycleInOrderAndReportsTheEnd) {
  auto state = std::make_shared<FakeState>();
  state->total = 100;
  EngineThread engine(FakeFactory(state), /*handoff_capacity=*/256);
  ASSERT_TRUE(engine.Start(nullptr));
  engine.SetPace(PaceSetting{/*max=*/true, 50.0});
  ASSERT_TRUE(state->WaitForCalls(100, 5s));
  std::size_t seen = 0;
  while (seen < 100) {
    auto tick = engine.NextTick();
    if (!tick.has_value()) {
      std::this_thread::yield();
      continue;
    }
    EXPECT_EQ(tick->index, seen);
    ++seen;
  }
  ExpectStopsPromptly(engine);
  EXPECT_TRUE(engine.Finished());
  EXPECT_FALSE(engine.Failed());
  EXPECT_EQ(engine.CyclesProduced(), 100u);

  auto bad = std::make_shared<FakeState>();
  bad->total = 3;
  bad->fail_at_end = true;
  EngineThread failing(FakeFactory(bad));
  ASSERT_TRUE(failing.Start(nullptr));
  failing.SetPace(PaceSetting{true, 50.0});
  ASSERT_TRUE(bad->WaitForCalls(3, 5s));
  ExpectStopsPromptly(failing);  // .c2: Stop joins, so the worker's verdict is in
  EXPECT_TRUE(failing.Failed());
  EXPECT_EQ(failing.Error(), "boom");
}

// UT-VTG-07.c1 -- paused, nothing is produced; Step makes exactly one cycle per request; a Step while
// running is ignored; Run resumes. .c2 -- stopping from paused returns.
TEST(EngineThreadTest, UT_VTG_07_PauseHoldsStepMakesOneCycleAndStopWorksFromPaused) {
  auto state = std::make_shared<FakeState>();
  EngineThread engine(FakeFactory(state));
  ASSERT_TRUE(engine.Start(nullptr));
  engine.SetPace(PaceSetting{true, 50.0});
  ASSERT_TRUE(state->WaitForCalls(1, 5s));
  engine.SetRunning(false);
  // Let any cycle already under way finish: a step request is a barrier -- once 2 more have been made the
  // count must stop there.
  engine.RequestStep();
  engine.RequestStep();
  const std::size_t before = state->Calls();
  ASSERT_TRUE(state->WaitForCalls(before + 0, 5s));
  EXPECT_FALSE(state->WaitForCalls(before + 100, 150ms)) << "paused: only the requested steps run";
  const std::size_t after_steps = state->Calls();
  EXPECT_LE(after_steps, before + 2);
  EXPECT_FALSE(engine.Running());
  EXPECT_FALSE(state->WaitForCalls(after_steps + 1, 100ms)) << "still paused: nothing more is produced";

  engine.RequestStep();
  ASSERT_TRUE(state->WaitForCalls(after_steps + 1, 5s)) << ".c1: one more cycle for one request";
  EXPECT_FALSE(state->WaitForCalls(after_steps + 2, 100ms));

  engine.SetRunning(true);
  engine.RequestStep();  // ignored while running
  ASSERT_TRUE(state->WaitForCalls(after_steps + 50, 5s)) << "running again";
  engine.SetRunning(false);
  ExpectStopsPromptly(engine);  // .c2 (stopping from paused is the next test's state; here from a pause just set)
}

TEST(EngineThreadTest, UT_VTG_07_c2_StopFromPausedFromTheStartReturns) {
  auto state = std::make_shared<FakeState>();
  EngineThread engine(FakeFactory(state));
  ASSERT_TRUE(engine.Start(nullptr));
  engine.SetRunning(false);
  ExpectStopsPromptly(engine);
}

// UT-VTG-08.c1 -- at "N cycles/s" the worker paces itself: 6 cycles at 50/s take about 5 periods
// (~100 ms nominal, over 60 ms), not microseconds. .c2 -- stopping while waiting for the next moment (1 cycle/s) returns at
// once, not after the period.
TEST(EngineThreadTest, UT_VTG_08_PaceSpacesTheCyclesAndStopWakesTheWait) {
  auto state = std::make_shared<FakeState>();
  EngineThread engine(FakeFactory(state));
  const auto t0 = std::chrono::steady_clock::now();
  ASSERT_TRUE(engine.Start(nullptr));
  engine.SetPace(PaceSetting{false, 50.0});
  ASSERT_TRUE(state->WaitForCalls(6, 5s));
  EXPECT_GE(std::chrono::steady_clock::now() - t0, 60ms);  // .c1 (5 periods = 100 ms nominal; the timer is coarse)

  engine.SetPace(PaceSetting{false, 1.0});
  std::this_thread::sleep_for(50ms);  // let it enter the long wait
  const auto t1 = std::chrono::steady_clock::now();
  ExpectStopsPromptly(engine);
  EXPECT_LT(std::chrono::steady_clock::now() - t1, 900ms) << ".c2";
}

// UT-VTG-09.c1 -- step-locked: after one cycle the worker waits; it makes the next only after the window has
// popped the first, found nothing (its frame is drawn), and started the next frame (the acknowledgement).
// .c2 -- stopping while step-locked and waiting returns.
TEST(EngineThreadTest, UT_VTG_09_StepLockedWaitsForTheWindowsAcknowledgement) {
  auto state = std::make_shared<FakeState>();
  EngineThread engine(FakeFactory(state));
  ASSERT_TRUE(engine.Start(nullptr));
  engine.SetStepLocked(true);
  engine.SetPace(PaceSetting{true, 50.0});
  ASSERT_TRUE(state->WaitForCalls(1, 5s));
  EXPECT_FALSE(state->WaitForCalls(3, 200ms)) << "the engine waits: at most one cycle past the unacknowledged one";
  const std::size_t waiting_at = state->Calls();
  EXPECT_LE(waiting_at, 2u);

  // The window's frame: pop until empty ...
  std::size_t popped = 0;
  while (engine.NextTick().has_value()) ++popped;
  EXPECT_GE(popped, 1u);
  EXPECT_FALSE(state->WaitForCalls(waiting_at + 1, 100ms)) << "popping alone does not release the engine";
  // ... draw ... and the next frame's first call is the acknowledgement.
  engine.NextTick();
  ASSERT_TRUE(state->WaitForCalls(waiting_at + 1, 5s)) << "acknowledged: the next cycle is made";

  engine.SetStepLocked(false);  // turning the lock off releases it without any acknowledgement
  ASSERT_TRUE(state->WaitForCalls(waiting_at + 20, 5s));
  engine.SetStepLocked(true);
  std::this_thread::sleep_for(50ms);
  ExpectStopsPromptly(engine);  // .c2: stopped while (likely) waiting for an acknowledgement
}

TEST(EngineThreadTest, UT_VTG_09_c2_StopFromStepLockedWithNoAcknowledgementEverReturns) {
  auto state = std::make_shared<FakeState>();
  EngineThread engine(FakeFactory(state));
  ASSERT_TRUE(engine.Start(nullptr));
  engine.SetStepLocked(true);
  ASSERT_TRUE(state->WaitForCalls(1, 5s));
  EXPECT_FALSE(state->WaitForCalls(3, 100ms));
  ExpectStopsPromptly(engine);
}

// UT-VTG-10 -- the engine never waits on a window that never pops: with a tiny hand-over and nobody
// popping, the run still completes and the dropped count says how many cycles were not kept.
TEST(EngineThreadTest, UT_VTG_10_ASlowWindowNeverStallsTheEngineAndTheDropsAreCounted) {
  auto state = std::make_shared<FakeState>();
  state->total = 500;
  EngineThread engine(FakeFactory(state), /*handoff_capacity=*/16);
  ASSERT_TRUE(engine.Start(nullptr));
  engine.SetPace(PaceSetting{true, 50.0});
  ASSERT_TRUE(state->WaitForCalls(500, 5s));
  ExpectStopsPromptly(engine);
  EXPECT_EQ(engine.CyclesProduced(), 500u);
  EXPECT_EQ(engine.Dropped(), 500u - 16u);
  auto newest = engine.NextTick();
  ASSERT_TRUE(newest.has_value());
  EXPECT_EQ(newest->index, 500u - 16u) << "the oldest were dropped, the newest 16 remain";
}

// ---- R-SIM-5: the same published ticks at any pace --------------------------------------------------------

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

std::string JsonEscape(const std::filesystem::path& path) {
  std::string out;
  for (char c : path.string()) {
    if (c == '\\' || c == '"') out.push_back('\\');
    out.push_back(c);
  }
  return out;
}

std::filesystem::path WriteRecording(const std::filesystem::path& path, int ticks) {
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(path);
  EXPECT_TRUE(writer.ok());
  simcore::io::TopicInfo heartbeat;
  heartbeat.schema_name = "test.Heartbeat";
  EXPECT_TRUE(writer.value()->Open(path, {{"/dummy/heartbeat", heartbeat}}).ok());
  for (int i = 0; i < ticks; ++i) {
    simcore::io::RawMessage msg;
    msg.topic = "/dummy/heartbeat";
    msg.log_time_ns = static_cast<std::int64_t>(i) * 10'000'000;
    msg.payload = {static_cast<std::uint8_t>(i & 0xFF)};
    writer.value()->Write(msg);
  }
  writer.value()->Close();
  return path;
}

std::filesystem::path WriteRunSpec(const std::filesystem::path& spec_path, const std::filesystem::path& recording) {
  std::ofstream out(spec_path);
  out << R"({
    "schema": "adas.sim.runspec/1.0",
    "run_id": "20260825T000000Z-vtg",
    "spec_sha256": "0000000000000000000000000000000000000000000000000000000000000",
    "grid": {"step_ns": 10000000},
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [{
      "name": "sut", "mode": "simulate",
      "impl": {"kind": "dll", "path": ")"
      << JsonEscape(EchoStubPath()) << R"(", "pattern": "", "search": []},
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
  return spec_path;
}

struct Published {
  std::size_t index = 0;
  std::int64_t t_ns = 0;
  std::vector<std::pair<std::string, std::vector<std::uint8_t>>> ports;  // sorted by name
  bool operator==(const Published& o) const { return index == o.index && t_ns == o.t_ns && ports == o.ports; }
};

// Runs the spec on an EngineThread at `pace` and collects the first `want` published ticks.
std::vector<Published> Collect(const std::string& spec, const PaceSetting& pace, std::size_t want) {
  EngineThread engine(sim::vantage::MakeEmbeddedFactory(spec, "", 2000), /*handoff_capacity=*/4096);
  std::string error;
  EXPECT_TRUE(engine.Start(&error)) << error;
  engine.SetPace(pace);
  std::vector<Published> out;
  const auto deadline = std::chrono::steady_clock::now() + 60s;
  while (out.size() < want && std::chrono::steady_clock::now() < deadline) {
    std::optional<viz::session::Tick> tick = engine.NextTick();
    if (!tick.has_value()) {
      if (engine.Finished() || engine.Failed()) {
        // drain what is left, then stop looking
        tick = engine.NextTick();
        if (!tick.has_value()) break;
      } else {
        std::this_thread::sleep_for(1ms);
        continue;
      }
    }
    Published p;
    p.index = tick->index;
    p.t_ns = tick->t_ns;
    for (const viz::session::PortValue& port : tick->ports) p.ports.emplace_back(port.name, port.payload);
    std::sort(p.ports.begin(), p.ports.end());
    out.push_back(std::move(p));
  }
  engine.Stop();
  EXPECT_EQ(engine.Dropped(), 0u) << "the comparison needs every cycle kept";
  return out;
}

void ExpectSamePublishedTicksAtMaxAndPaced(const std::string& spec, std::size_t want) {
  const std::vector<Published> at_max = Collect(spec, PaceSetting{true, 50.0}, want);
  const std::vector<Published> at_50 = Collect(spec, PaceSetting{false, 50.0}, want);
  ASSERT_FALSE(at_max.empty());
  ASSERT_EQ(at_max.size(), at_50.size());
  for (std::size_t i = 0; i < at_max.size(); ++i) {
    ASSERT_EQ(at_max[i].index, i) << "cycle numbers are the engine's own, in order";
    ASSERT_TRUE(at_max[i] == at_50[i]) << "tick " << i << " differs between pace max and 50 cycles/s";
  }
}

// UT-VTG-11 -- R-SIM-5: the published ticks (cycle numbers and every port's bytes) are identical at "max"
// and at 50 cycles/s on the same run, first 200 ticks, over the real embedded engine.
TEST(EngineDeterminism, UT_VTG_11_PublishedTicksAreIdenticalAtMaxAndAt50CyclesPerSecond) {
#if defined(_WIN32)
  _putenv_s("ADAS_SIL_TEST_STUB_NAME", "run_stub");
  _putenv_s("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs");
#else
  setenv("ADAS_SIL_TEST_STUB_NAME", "run_stub", 1);
  setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs", 1);
#endif
  const auto recording = WriteRecording(std::filesystem::temp_directory_path() / "vtg09_recording.mcap", 220);
  const auto spec = WriteRunSpec(std::filesystem::temp_directory_path() / "vtg09_run_spec.json", recording);
  ExpectSamePublishedTicksAtMaxAndPaced(spec.string(), 200);
}

// The same comparison over any run spec: VANTAGE_DETERMINISM_SPEC=<run spec json> (e.g. a df run).
TEST(EngineDeterminism, UT_VTG_11_c2_AnyNamedRunSpecIsIdenticalAtMaxAndAt50CyclesPerSecond) {
  const char* spec = std::getenv("VANTAGE_DETERMINISM_SPEC");
  if (spec == nullptr || spec[0] == '\0') {
    GTEST_SKIP() << "set VANTAGE_DETERMINISM_SPEC to a run spec json to compare a real run";
  }
  ExpectSamePublishedTicksAtMaxAndPaced(spec, 200);
}

// UT-VTG-12 -- timing report, not gated: the engine's own cost per cycle at pace "max" with nobody drawing
// (the window-less figure the live check compares against). VANTAGE_DETERMINISM_SPEC names the run spec.
TEST(EngineDeterminism, UT_VTG_12_TimingReportEngineCostPerCycleAtMaxWithNoWindow) {
  const char* spec = std::getenv("VANTAGE_DETERMINISM_SPEC");
  if (spec == nullptr || spec[0] == 0) {
    GTEST_SKIP() << "set VANTAGE_DETERMINISM_SPEC to a run spec json to time a real run";
  }
  EngineThread engine(sim::vantage::MakeEmbeddedFactory(spec, "", 2000), /*handoff_capacity=*/4096);
  std::string error;
  ASSERT_TRUE(engine.Start(&error)) << error;
  const auto t0 = std::chrono::steady_clock::now();
  engine.SetPace(PaceSetting{true, 50.0});
  while (!engine.Finished() && !engine.Failed() && std::chrono::steady_clock::now() - t0 < 120s) {
    std::this_thread::sleep_for(5ms);
  }
  const double wall_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  engine.Stop();
  ASSERT_GT(engine.CyclesProduced(), 0u);
  std::printf("[ TIMING ] %llu cycles at pace max, no window: %.1f us per cycle inside the engine, %.3f s wall\n",
              static_cast<unsigned long long>(engine.CyclesProduced()),
              engine.BusySeconds() * 1e6 / static_cast<double>(engine.CyclesProduced()), wall_s);
}

}  // namespace
