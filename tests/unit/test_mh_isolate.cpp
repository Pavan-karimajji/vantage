// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-HOST-13` (`IMP-0096`, `WP-14`): `RunIsolatedStage` classifies a
///   clean exit, a nonzero (self-reported) exit, an abnormal (signalled)
///   termination and a timeout as four DISTINCT outcomes, never merged
///   (`R-SIM-19`). Exercised against `/bin/sh` rather than a real
///   `simengine` spec -- the classification logic under test cares only
///   about how the child process ended, not what it computed, and a shell
///   one-liner is the smallest thing that can end each of those four ways
///   on demand.
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#include <chrono>

#include <gtest/gtest.h>

namespace simcore::module_host {
namespace {

#if !defined(_WIN32)

TEST(MhIsolate, CleanZeroExitIsOk) {
  const IsolatedRunResult result = RunIsolatedStage("sut", "/bin/sh", {"-c", "exit 0"}, std::chrono::seconds(5));
  EXPECT_EQ(result.outcome, IsolatedOutcome::kOk);
  EXPECT_EQ(result.exit_code, 0);
  EXPECT_EQ(result.stage, "sut");
  EXPECT_EQ(ToString(result.outcome), "ok");
}

TEST(MhIsolate, CleanNonzeroExitIsFailNotCrash) {
  const IsolatedRunResult result = RunIsolatedStage("sut", "/bin/sh", {"-c", "exit 7"}, std::chrono::seconds(5));
  EXPECT_EQ(result.outcome, IsolatedOutcome::kFail);
  EXPECT_EQ(result.exit_code, 7);
  EXPECT_EQ(ToString(result.outcome), "fail");
}

TEST(MhIsolate, AbnormalTerminationIsCrashNotFail) {
  // `kill -SEGV $$` terminates the shell itself by signal -- WIFSIGNALED,
  // never a self-reported nonzero exit (SIGSEGV = 11).
  const IsolatedRunResult result =
      RunIsolatedStage("sut", "/bin/sh", {"-c", "kill -SEGV $$"}, std::chrono::seconds(5));
  EXPECT_EQ(result.outcome, IsolatedOutcome::kCrashed);
  EXPECT_EQ(result.exit_code, 11);
  EXPECT_EQ(ToString(result.outcome), "crash");
}

TEST(MhIsolate, StillRunningAtDeadlineIsTimedOutAndTheChildIsKilled) {
  const IsolatedRunResult result =
      RunIsolatedStage("sut", "/bin/sh", {"-c", "sleep 30"}, std::chrono::milliseconds(200));
  EXPECT_EQ(result.outcome, IsolatedOutcome::kTimedOut);
  EXPECT_EQ(ToString(result.outcome), "timeout");
}

TEST(MhIsolate, AnExecutableThatDoesNotExistFailsToStart) {
  const IsolatedRunResult result =
      RunIsolatedStage("sut", "/no/such/executable-it11-fixture", {}, std::chrono::seconds(1));
  EXPECT_EQ(result.outcome, IsolatedOutcome::kFailedToStart);
  EXPECT_FALSE(result.detail.empty());
}

#endif  // !_WIN32

}  // namespace
}  // namespace simcore::module_host
