// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   Engine integration plan E-4 (`G-4`): Vantage's engine runs on its own thread and the window only
///   watches. `EngineThread` owns one worker that creates the engine, steps it one cycle at a time and
///   pushes each finished `Tick` into a bounded, thread-safe hand-over (`TickHandoff`); the window thread
///   pops from it without ever waiting. The engine never waits on the window -- except in the optional
///   step-locked debugging mode, where it waits for the window to report that it has drawn the previous
///   cycle.
///
///   **Threads.** Every engine call (create, `StepTick`, destroy) happens on the worker thread and nowhere
///   else: the engine is constructed by the factory *inside* the worker, never handed in, and the
///   `CycleSource` is destroyed by the worker before it exits. The window side only touches this class's
///   control and pop methods, which lock. `viz::session::PushSource` (a bare deque, no locking) is NOT on
///   this path: the worker produces `Tick`s directly (`EmbeddedEngine::StepTick`) into `TickHandoff`.
///
///   **Pace.** "max" runs as fast as the engine goes. "N cycles/s" paces the worker's own loop; it is NOT
///   the component's period (`R-SIM-18`: the period lives in the config bundle and the bridge does not have
///   it), so the default is only a viewing speed. Pacing waits on a condition variable with a deadline, so
///   pause, step, stop and a pace change wake it at once -- there is no sleep loop anywhere.
///
///   **Determinism (`R-SIM-5`).** Pace, pause and the window never reach the engine's inputs: the worker
///   calls `StepTick` in a fixed sequence and the ticks it publishes are the same at any pace.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>

#include "viz/session/tick.hpp"

namespace sim::vantage {

/// Capacity of the hand-over between the worker and the window: ticks waiting to be drawn. A cycle is a
/// few kB, so this bounds memory at about a megabyte; at 1 kHz it is a quarter second of backlog.
inline constexpr std::size_t kHandoffCapacity = 256;

/// The pace a run starts at: cycles per second. NOT the component's period (R-SIM-18 -- the period is in
/// the config bundle, which the bridge does not read); it is a comfortable viewing speed, nothing more.
inline constexpr double kDefaultPaceHz = 50.0;

/// Bounded, thread-safe FIFO of finished ticks. `Push` never blocks: when full it drops the OLDEST tick
/// and counts it. `TryPop` never blocks either. Each tick carries a sequence number (1, 2, 3, ...) in push
/// order, which the step-locked acknowledgement counts in.
class TickHandoff {
 public:
  explicit TickHandoff(std::size_t capacity) : capacity_(capacity) {}

  /// Returns the tick's sequence number.
  std::uint64_t Push(viz::session::Tick tick);

  struct Popped {
    viz::session::Tick tick;
    std::uint64_t seq = 0;
  };
  std::optional<Popped> TryPop();

  std::uint64_t Dropped() const;
  std::size_t Size() const;

 private:
  const std::size_t capacity_;
  mutable std::mutex mutex_;
  std::deque<Popped> queue_;
  std::uint64_t next_seq_ = 1;
  std::uint64_t dropped_ = 0;
};

/// What the worker steps: one cycle per `Next()`. `nullopt` means the run is over -- finished (`ok()`
/// true) or failed (`ok()` false, `error()` says why).
class CycleSource {
 public:
  virtual ~CycleSource() = default;
  virtual std::optional<viz::session::Tick> Next() = 0;
  virtual bool ok() const { return true; }
  virtual const std::string& error() const {
    static const std::string kNone;
    return kNone;
  }
};

/// Built ON the worker thread (so the engine is created there); returns null and fills `error` on failure.
using CycleSourceFactory = std::function<std::unique_ptr<CycleSource>(std::string* error)>;

struct PaceSetting {
  bool max = false;       // true: as fast as the engine goes
  double hz = kDefaultPaceHz;  // cycles per second when not max
  bool operator==(const PaceSetting& other) const { return max == other.max && hz == other.hz; }
};

class EngineThread {
 public:
  explicit EngineThread(CycleSourceFactory factory, std::size_t handoff_capacity = kHandoffCapacity);
  ~EngineThread();  // Stop()
  EngineThread(const EngineThread&) = delete;
  EngineThread& operator=(const EngineThread&) = delete;

  /// Starts the worker and waits until it has created its source (or failed to). False + `error` on a
  /// failed creation. The run starts running (not paused) at `kDefaultPaceHz`, not step-locked.
  bool Start(std::string* error);

  /// Stops and joins the worker: from running, paused, paced or step-locked. Safe to call twice.
  void Stop();

  // ---- the window thread's controls (all non-blocking) ----
  void SetRunning(bool running);
  bool Running() const;
  /// One cycle while paused; ignored while running. Several requests queue.
  void RequestStep();
  void SetPace(const PaceSetting& pace);
  PaceSetting Pace() const;
  void SetStepLocked(bool step_locked);
  bool StepLocked() const;

  // ---- the window thread's data side ----
  /// Pops one finished tick, or `nullopt` when none is waiting. NEVER blocks and never steps anything.
  /// Step-locked acknowledgement: the call that follows a call which found nothing means the window has
  /// finished drawing everything it popped before, so it acknowledges up to the last tick popped (a frame
  /// pops until empty, draws, and starts the next frame with this call).
  std::optional<viz::session::Tick> NextTick();

  std::uint64_t Dropped() const { return handoff_.Dropped(); }
  std::uint64_t CyclesProduced() const;
  /// Total time the worker spent inside `Next()` (the engine's own cost per cycle, waits excluded).
  double BusySeconds() const;
  bool Finished() const;   // the source ran out (not an error)
  bool Failed() const;
  std::string Error() const;

 private:
  void Worker();

  CycleSourceFactory factory_;
  TickHandoff handoff_;
  std::thread thread_;

  mutable std::mutex mutex_;          // guards everything below
  std::condition_variable cv_;        // the worker waits here; every control and the ack notify it
  bool started_ = false;
  bool create_done_ = false;
  std::string create_error_;
  bool stop_ = false;
  bool running_ = true;
  std::uint64_t step_requests_ = 0;
  PaceSetting pace_;
  std::uint64_t pace_generation_ = 0;  // bumped by any change the pacing wait must notice
  bool step_locked_ = false;
  std::uint64_t pushed_seq_ = 0;       // sequence number of the last tick the worker pushed
  std::uint64_t acked_seq_ = 0;        // the last one the window reported drawn
  std::uint64_t cycles_produced_ = 0;
  double busy_s_ = 0.0;
  bool finished_ = false;
  bool failed_ = false;
  std::string error_;

  // Window-thread-only (NextTick is called from one thread): the ack protocol's own state.
  std::uint64_t last_popped_seq_ = 0;
  bool last_pop_found_nothing_ = false;
};

/// The embedded sim engine as a cycle source: `EmbeddedEngine::Create` runs inside the factory, so on the
/// worker thread, and every `Next()` is `EmbeddedEngine::StepTick`.
CycleSourceFactory MakeEmbeddedFactory(std::string run_spec_path, std::string config_path,
                                       std::int64_t exec_timeout_ms);

}  // namespace sim::vantage
