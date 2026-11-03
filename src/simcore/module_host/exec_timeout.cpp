// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `RunWithTimeout` implementation -- ported unchanged from
///   `sil_host/src/exec_timeout.cpp` (`IMP-0092`). `ExecTimeout`
///   (`IMP-0093`, `IMP-0060`) runs a caller's calls on that caller's own
///   long-lived thread.
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#include <condition_variable>
#include <future>
#include <memory>
#include <mutex>
#include <thread>

namespace simcore::module_host {

ExecResult RunWithTimeout(const std::function<void()>& fn, std::chrono::milliseconds timeout) {
  auto packaged = std::make_shared<std::packaged_task<void()>>(fn);
  std::future<void> future = packaged->get_future();
  std::thread worker([packaged]() { (*packaged)(); });
  worker.detach();

  if (future.wait_for(timeout) == std::future_status::timeout) {
    return ExecResult{ExecOutcome::kTimeout, "exec() did not return within the configured timeout"};
  }
  try {
    future.get();
  } catch (const std::exception& e) {
    return ExecResult{ExecOutcome::kException, e.what()};
  } catch (...) {
    return ExecResult{ExecOutcome::kException, "unknown exception"};
  }
  return ExecResult{ExecOutcome::kOk, std::string()};
}

// `IMP-0060`: the thread and the state it shares with the caller. The thread owns a share of
// `Shared`, so abandoning it (detaching) leaves it a valid place to finish in.
struct ExecTimeout::CallThread {
  struct Shared {
    std::mutex mutex;
    std::condition_variable wake;
    std::condition_variable finished;
    std::function<void()> task;
    bool has_task = false;
    bool done = false;
    bool stop = false;
    bool threw = false;
    std::string error;
  };

  CallThread() : shared(std::make_shared<Shared>()) {}

  ~CallThread() {
    if (!thread.joinable()) return;
    if (abandoned) {
      thread.detach();
      return;
    }
    {
      std::lock_guard<std::mutex> lock(shared->mutex);
      shared->stop = true;
    }
    shared->wake.notify_all();
    thread.join();
  }

  static void Loop(std::shared_ptr<Shared> shared) {
    std::unique_lock<std::mutex> lock(shared->mutex);
    for (;;) {
      shared->wake.wait(lock, [&] { return shared->has_task || shared->stop; });
      if (shared->stop) return;
      std::function<void()> task = std::move(shared->task);
      shared->has_task = false;
      lock.unlock();
      bool threw = false;
      std::string error;
      try {
        task();
      } catch (const std::exception& e) {
        threw = true;
        error = e.what();
      } catch (...) {
        threw = true;
        error = "unknown exception";
      }
      lock.lock();
      shared->threw = threw;
      shared->error = std::move(error);
      shared->done = true;
      shared->finished.notify_all();
    }
  }

  std::shared_ptr<Shared> shared;
  std::thread thread;
  bool abandoned = false;
};

ExecTimeout::ExecTimeout(std::chrono::milliseconds timeout)
    : timeout_(timeout), call_thread_(std::make_shared<CallThread>()) {}

ExecResult ExecTimeout::Run(const std::function<void()>& fn) const {
  CallThread& call = *call_thread_;
  if (call.abandoned) return ExecResult{ExecOutcome::kTimeout, "the call thread of this caller was abandoned by an earlier timeout"};
  const std::shared_ptr<CallThread::Shared>& shared = call.shared;
  {
    std::lock_guard<std::mutex> lock(shared->mutex);
    shared->task = fn;
    shared->has_task = true;
    shared->done = false;
    shared->threw = false;
    shared->error.clear();
  }
  if (!call.thread.joinable()) call.thread = std::thread(&CallThread::Loop, shared);
  shared->wake.notify_all();

  std::unique_lock<std::mutex> lock(shared->mutex);
  if (!shared->finished.wait_for(lock, timeout_, [&] { return shared->done; })) {
    call.abandoned = true;
    return ExecResult{ExecOutcome::kTimeout, "exec() did not return within the configured timeout"};
  }
  if (shared->threw) return ExecResult{ExecOutcome::kException, shared->error};
  return ExecResult{ExecOutcome::kOk, std::string()};
}

}  // namespace simcore::module_host
