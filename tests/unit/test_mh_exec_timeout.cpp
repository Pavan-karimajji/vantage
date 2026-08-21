// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `RunWithTimeout` -- ported unchanged from `sil_host/tests/unit/
///   test_exec_timeout.cpp` (`WP-10`'s own exit criterion: "sil_host's own
///   component and timeout tests pass against the moved code unchanged").
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#include <chrono>
#include <stdexcept>
#include <thread>

#include <gtest/gtest.h>

using simcore::module_host::ExecOutcome;
using simcore::module_host::RunWithTimeout;

TEST(MhExecTimeout, FastCallableReturnsOkWithNoError) {
  const auto result = RunWithTimeout([]() {}, std::chrono::milliseconds(200));
  EXPECT_EQ(result.outcome, ExecOutcome::kOk);
  EXPECT_TRUE(result.error.empty());
}

TEST(MhExecTimeout, HangingCallableReportsTimeoutRatherThanBlockingForever) {
  const auto start = std::chrono::steady_clock::now();
  const auto result = RunWithTimeout(
      []() { std::this_thread::sleep_for(std::chrono::seconds(30)); }, std::chrono::milliseconds(100));
  const auto elapsed = std::chrono::steady_clock::now() - start;

  EXPECT_EQ(result.outcome, ExecOutcome::kTimeout);
  EXPECT_FALSE(result.error.empty());
  EXPECT_LT(elapsed, std::chrono::seconds(5));
}

TEST(MhExecTimeout, StdExceptionIsReportedAsExceptionNotTimeout) {
  const auto result = RunWithTimeout(
      []() { throw std::runtime_error("stage blew up"); }, std::chrono::milliseconds(200));
  EXPECT_EQ(result.outcome, ExecOutcome::kException);
  EXPECT_NE(result.error.find("stage blew up"), std::string::npos) << result.error;
}

TEST(MhExecTimeout, NonStdExceptionIsReportedAsUnknownException) {
  const auto result = RunWithTimeout([]() { throw 42; }, std::chrono::milliseconds(200));
  EXPECT_EQ(result.outcome, ExecOutcome::kException);
  EXPECT_NE(result.error.find("unknown"), std::string::npos) << result.error;
}

TEST(MhExecTimeout, TimeoutIsNeverMergedWithExceptionOnAFastThrow) {
  const auto result = RunWithTimeout([]() { throw std::runtime_error("fast fail"); },
                                      std::chrono::milliseconds(500));
  EXPECT_EQ(result.outcome, ExecOutcome::kException);
}

TEST(MhExecTimeout, ExecTimeoutObjectWrapsTheFreeFunctionWithAConfiguredBudget) {
  const simcore::module_host::ExecTimeout budget(std::chrono::milliseconds(200));
  const auto result = budget.Run([]() {});
  EXPECT_EQ(result.outcome, ExecOutcome::kOk);
  EXPECT_EQ(budget.timeout(), std::chrono::milliseconds(200));
}
