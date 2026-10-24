// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief See engine_thread.hpp.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "vantage/engine_thread.hpp"

#include <algorithm>
#include <chrono>
#include <utility>

#include "vantage/host_loop.hpp"

namespace sim::vantage {

// ---- TickHandoff ---------------------------------------------------------------------------------------

std::uint64_t TickHandoff::Push(viz::session::Tick tick) {
  std::deque<Popped> evicted;  // destroyed after the lock is released
  std::uint64_t seq = 0;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    seq = next_seq_++;
    queue_.push_back(Popped{std::move(tick), seq});
    while (queue_.size() > capacity_) {
      evicted.push_back(std::move(queue_.front()));
      queue_.pop_front();
      ++dropped_;
    }
  }
  return seq;
}

std::optional<TickHandoff::Popped> TickHandoff::TryPop() {
  std::lock_guard<std::mutex> lock(mutex_);
  if (queue_.empty()) {
    return std::nullopt;
  }
  Popped popped = std::move(queue_.front());
  queue_.pop_front();
  return popped;
}

std::uint64_t TickHandoff::Dropped() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return dropped_;
}

std::size_t TickHandoff::Size() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return queue_.size();
}

// ---- EngineThread --------------------------------------------------------------------------------------

EngineThread::EngineThread(CycleSourceFactory factory, std::size_t handoff_capacity)
    : factory_(std::move(factory)), handoff_(handoff_capacity) {}

EngineThread::~EngineThread() {
  Stop();
}

bool EngineThread::Start(std::string* error) {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (started_) {
      return true;
    }
    started_ = true;
  }
  thread_ = std::thread([this] { Worker(); });
  std::unique_lock<std::mutex> lock(mutex_);
  cv_.wait(lock, [this] { return create_done_; });
  if (!create_error_.empty()) {
    if (error != nullptr) {
      *error = create_error_;
    }
    lock.unlock();
    Stop();
    return false;
  }
  return true;
}

void EngineThread::Stop() {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    stop_ = true;
  }
  cv_.notify_all();
  if (thread_.joinable()) {
    thread_.join();
  }
}

void EngineThread::SetRunning(bool running) {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    running_ = running;
    ++pace_generation_;
  }
  cv_.notify_all();
}

bool EngineThread::Running() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return running_;
}

void EngineThread::RequestStep() {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (running_) {
      return;  // a step is for a paused engine
    }
    ++step_requests_;
  }
  cv_.notify_all();
}

void EngineThread::SetPace(const PaceSetting& pace) {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    pace_ = pace;
    if (pace_.hz <= 0.0) {
      pace_.hz = kDefaultPaceHz;
    }
    ++pace_generation_;
  }
  cv_.notify_all();
}

PaceSetting EngineThread::Pace() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return pace_;
}

void EngineThread::SetStepLocked(bool step_locked) {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    step_locked_ = step_locked;
    ++pace_generation_;
  }
  cv_.notify_all();
}

bool EngineThread::StepLocked() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return step_locked_;
}

std::optional<viz::session::Tick> EngineThread::NextTick() {
  // The window has finished drawing everything it popped before when it starts a frame after a frame
  // that popped until empty: that is the step-locked acknowledgement. No effect unless step-locked.
  if (last_pop_found_nothing_) {
    bool changed = false;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (last_popped_seq_ > acked_seq_) {
        acked_seq_ = last_popped_seq_;
        changed = true;
      }
    }
    if (changed) {
      cv_.notify_all();
    }
  }
  std::optional<TickHandoff::Popped> popped = handoff_.TryPop();
  if (!popped.has_value()) {
    last_pop_found_nothing_ = true;
    return std::nullopt;
  }
  last_pop_found_nothing_ = false;
  last_popped_seq_ = popped->seq;
  return std::move(popped->tick);
}

double EngineThread::BusySeconds() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return busy_s_;
}

std::uint64_t EngineThread::CyclesProduced() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return cycles_produced_;
}

bool EngineThread::Finished() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return finished_;
}

bool EngineThread::Failed() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return failed_;
}

std::string EngineThread::Error() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return error_;
}

void EngineThread::Worker() {
  // The engine is created here, steps here and is destroyed here: no other thread ever calls into it.
  std::string create_error;
  std::unique_ptr<CycleSource> source = factory_ ? factory_(&create_error) : nullptr;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (source == nullptr) {
      create_error_ = create_error.empty() ? std::string("the engine could not be created") : create_error;
    }
    create_done_ = true;
  }
  cv_.notify_all();
  if (source == nullptr) {
    return;
  }

  using Clock = std::chrono::steady_clock;
  Clock::time_point next_due{};
  bool have_due = false;

  std::unique_lock<std::mutex> lock(mutex_);
  for (;;) {
    // Paused: nothing happens until the engine is set running, a step is requested or the thread stops.
    cv_.wait(lock, [this] { return stop_ || running_ || step_requests_ > 0; });
    if (stop_) {
      break;
    }
    const bool stepping = !running_;
    if (stepping) {
      --step_requests_;
      have_due = false;
    }

    // Step-locked: the next cycle waits for the window to report the previous one drawn.
    cv_.wait(lock, [this] { return stop_ || !step_locked_ || acked_seq_ >= pushed_seq_; });
    if (stop_) {
      break;
    }

    // Pace (running only): wait for this cycle's moment; a pause, a pace or lock change or a stop wakes it.
    if (!stepping) {
      if (pace_.max) {
        have_due = false;
      } else {
        const auto period = std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(1.0 / pace_.hz));
        const Clock::time_point now = Clock::now();
        if (!have_due || now > next_due + period) {
          next_due = now;  // never burst to catch up after a stall
          have_due = true;
        }
        const std::uint64_t generation = pace_generation_;
        cv_.wait_until(lock, next_due, [&] { return stop_ || !running_ || pace_generation_ != generation; });
        if (stop_) {
          break;
        }
        if (!running_ || pace_generation_ != generation) {
          have_due = false;
          continue;  // re-evaluate with the new state
        }
        next_due += period;
      }
    }

    lock.unlock();
    const Clock::time_point step_start = Clock::now();
    std::optional<viz::session::Tick> tick = source->Next();
    const double step_s = std::chrono::duration<double>(Clock::now() - step_start).count();
    if (!tick.has_value()) {
      const bool ok = source->ok();
      const std::string error = source->error();
      lock.lock();
      finished_ = ok;
      failed_ = !ok;
      error_ = error;
      break;
    }
    const std::uint64_t seq = handoff_.Push(std::move(*tick));
    lock.lock();
    pushed_seq_ = seq;
    ++cycles_produced_;
    busy_s_ += step_s;
  }
  if (lock.owns_lock()) {
    lock.unlock();
  }
  source.reset();  // the engine is destroyed on this thread
}

// ---- the embedded engine as a CycleSource --------------------------------------------------------------

namespace {

class EmbeddedCycleSource final : public CycleSource {
 public:
  explicit EmbeddedCycleSource(EmbeddedEngine engine) : engine_(std::move(engine)) {}
  std::optional<viz::session::Tick> Next() override { return engine_.StepTick(); }
  bool ok() const override { return engine_.ok(); }
  const std::string& error() const override { return engine_.error(); }

 private:
  EmbeddedEngine engine_;
};

}  // namespace

CycleSourceFactory MakeEmbeddedFactory(std::string run_spec_path, std::string config_path,
                                       std::int64_t exec_timeout_ms) {
  return [=](std::string* error) -> std::unique_ptr<CycleSource> {
    simcore::Result<EmbeddedEngine> created = EmbeddedEngine::Create(run_spec_path, config_path, exec_timeout_ms);
    if (!created.ok()) {
      if (error != nullptr) {
        *error = created.error().Format();
      }
      return nullptr;
    }
    // Same const_cast idiom as host_loop.cpp / vantage_app.cpp: the &&-qualified value() is not in every
    // cached adas-sim package.
    return std::make_unique<EmbeddedCycleSource>(std::move(const_cast<EmbeddedEngine&>(created.value())));
  };
}

}  // namespace sim::vantage
