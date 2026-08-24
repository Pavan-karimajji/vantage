// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-TRN-05` (`WP-27`, `SW-0356`, `SI-25` `transport`): "kill the
///   engine with a player attached; observe what the player reports and
///   how long it waits" (`SIM_Software_Test_Spec_v0.1.md` SS5.25).
///
///   `TransportShm.DeadEngineReportedNotWaitedOn` (`tests/unit/
///   test_transport_shm.cpp`) already proves `SharedMemoryTransport`'s
///   liveness contract via `SimulateEngineDeath()` -- a same-process test
///   hook, not a real kill. This file is the real thing: a genuinely
///   separate process (`sim_test_fixture_trn_engine_host`, this module's
///   own new fixture -- see its own top note) running a real `Runner` +
///   real `echo_stub`, force-killed while it is still mid-run (never an
///   orderly shutdown, which would store `engineAlivePid = 0` in its own
///   destructor and prove nothing about the OS-level liveness path this
///   test exists to exercise), with a genuine second `SharedMemoryTransport`
///   object (`Role::kClient`) in THIS process observing the death.
///
///   Same technique the design note for `SharedMemoryTransport` already
///   named as proven-but-uncommitted ("a scratch `.cpp`, not committed")
///   -- committed here for the first time, with a real `Runner` in the
///   loop rather than the transport object alone.
/// @author Pavan Karimajji

#include "simcore/transport_shm.hpp"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <thread>
#include <vector>

#include <gtest/gtest.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>
extern char** environ;
#endif

namespace {

// Minimal spawn-then-kill-on-demand primitive -- deliberately NOT
// module_host::RunIsolatedStage, which blocks until the child exits or a
// deadline passes and has no "kill it now, whenever the test decides" mode.
// Same two platform halves that function already uses (CreateProcessA/
// TerminateProcess; posix_spawn/kill+waitpid), reshaped for this test's own
// non-blocking need.
class KillableChild {
 public:
  bool Spawn(const std::filesystem::path& executable, const std::vector<std::string>& args) {
#if defined(_WIN32)
    std::string cmd = "\"" + executable.string() + "\"";
    for (const std::string& a : args) cmd += " \"" + a + "\"";
    std::vector<char> cmd_buf(cmd.begin(), cmd.end());
    cmd_buf.push_back('\0');
    STARTUPINFOA startup_info{};
    startup_info.cb = sizeof(startup_info);
    const BOOL spawned = CreateProcessA(nullptr, cmd_buf.data(), nullptr, nullptr, FALSE, 0, nullptr, nullptr,
                                         &startup_info, &process_info_);
    if (!spawned) return false;
    CloseHandle(process_info_.hThread);
    spawned_ = true;
    return true;
#else
    std::vector<std::string> argv_storage;
    argv_storage.push_back(executable.string());
    argv_storage.insert(argv_storage.end(), args.begin(), args.end());
    std::vector<char*> argv;
    argv.reserve(argv_storage.size() + 1);
    for (std::string& s : argv_storage) argv.push_back(s.data());
    argv.push_back(nullptr);
    const int status = posix_spawn(&pid_, executable.c_str(), nullptr, nullptr, argv.data(), environ);
    spawned_ = status == 0;
    return spawned_;
#endif
  }

  // A real crash shape -- forcibly terminated, never given a chance to run
  // its own destructor/cleanup (that is exactly the "orderly shutdown looks
  // identical to a crash to a still-attached client" case `shm.cpp`'s
  // header comment says SW-0356 does not distinguish, but here it matters:
  // an orderly exit WOULD still store engineAlivePid=0 itself, proving
  // nothing about the independent OS-level pid check this test targets).
  // Blocks until the OS has actually reaped the process, same as
  // `RunIsolatedStage`'s own timeout path does.
  void KillAndReap() {
    if (!spawned_) return;
#if defined(_WIN32)
    TerminateProcess(process_info_.hProcess, 1);
    WaitForSingleObject(process_info_.hProcess, INFINITE);
    CloseHandle(process_info_.hProcess);
#else
    kill(pid_, SIGKILL);
    int status = 0;
    waitpid(pid_, &status, 0);
#endif
    spawned_ = false;
  }

  ~KillableChild() { KillAndReap(); }  // never leak a running/zombie child if a case fails early

 private:
  bool spawned_ = false;
#if defined(_WIN32)
  PROCESS_INFORMATION process_info_{};
#else
  pid_t pid_ = 0;
#endif
};

std::filesystem::path TrnEngineHostPath() { return std::filesystem::path(TRN_ENGINE_HOST_EXECUTABLE); }

}  // namespace

TEST(ItTrn05Crash, EngineAliveFlipsFalseOnlyAfterARealKillNotBefore) {
  const std::string shm_name = "it_trn05_shm";

  KillableChild child;
  // 1000 cycles at 20ms/tick is ~20s if never killed -- ample real time for
  // this test to attach, observe live data and kill it long before it
  // would ever finish on its own.
  ASSERT_TRUE(child.Spawn(TrnEngineHostPath(), {shm_name, "1000", "20"}))
      << "failed to spawn " << TrnEngineHostPath();

  // The child creates the segment itself, at its own process start -- poll-
  // attach rather than assume it already exists (the two processes' start
  // order relative to each other is not otherwise synchronised).
  simcore::transport::SharedMemoryTransport client(
      shm_name, simcore::transport::SharedMemoryTransport::Role::kClient, /*depth=*/64);
  adas::transport::AttachResult attach_result = adas::transport::AttachResult::kEngineUnavailable;
  const auto attach_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
  uint32_t engine_version = 0;
  while (std::chrono::steady_clock::now() < attach_deadline) {
    attach_result = client.attach(simcore::transport::SharedMemoryTransport::kProtocolVersion, &engine_version);
    if (attach_result == adas::transport::AttachResult::kOk) break;
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  ASSERT_EQ(attach_result, adas::transport::AttachResult::kOk) << "never attached to the child's segment";
  ASSERT_TRUE(client.engineAlive()) << "engine reported dead before it was ever killed";

  // Drain until at least one real frame has been observed -- confirms this
  // is watching a real, running Runner publish real data, not just an
  // empty segment.
  adas::transport::PortFrame frame{};
  const auto data_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
  bool saw_data = false;
  while (std::chrono::steady_clock::now() < data_deadline) {
    if (client.tryReceive(&frame)) {
      saw_data = true;
      break;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  ASSERT_TRUE(saw_data) << "never observed a single published frame from the real child engine";
  const std::uint64_t last_tick_before_kill = client.lastTickReceived();

  // -- The kill itself: forcibly terminated mid-run, never an orderly exit.
  const auto kill_started = std::chrono::steady_clock::now();
  child.KillAndReap();

  // `tryReceive` is non-blocking by contract (SW-0353) regardless of
  // engine state -- confirmed here, not just assumed: this call must
  // return immediately whether or not new data exists.
  const auto call_started = std::chrono::steady_clock::now();
  client.tryReceive(&frame);
  const auto call_elapsed = std::chrono::steady_clock::now() - call_started;
  EXPECT_LT(std::chrono::duration_cast<std::chrono::milliseconds>(call_elapsed), std::chrono::milliseconds(100))
      << "tryReceive() appears to have blocked after the engine died";

  // -- engineAlive() must flip false, and it must do so promptly (SW-0356:
  // "reported ... rather than blocking") -- polled with a generous but
  // bounded timeout, never an unbounded wait on this test's own part
  // either.
  bool observed_dead = false;
  const auto liveness_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
  while (std::chrono::steady_clock::now() < liveness_deadline) {
    if (!client.engineAlive()) {
      observed_dead = true;
      break;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  const auto detected_after = std::chrono::steady_clock::now() - kill_started;
  EXPECT_TRUE(observed_dead) << "engineAlive() never reported the killed engine as dead";
  EXPECT_LT(std::chrono::duration_cast<std::chrono::milliseconds>(detected_after), std::chrono::milliseconds(5000))
      << "took implausibly long to detect the kill";

  // The session up to the last real tick received stays intact (SW-0356's
  // own "with the session up to the last received tick intact") -- the
  // count observed before the kill is never retroactively lost.
  EXPECT_GE(client.lastTickReceived(), last_tick_before_kill);
}
