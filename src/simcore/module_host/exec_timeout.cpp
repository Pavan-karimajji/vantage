// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `RunWithTimeout` implementation -- ported unchanged from
///   `sil_host/src/exec_timeout.cpp` (`IMP-0092`). `ExecTimeout` itself
///   (`IMP-0093`) is header-only (`module_host.hpp`).
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#include <future>
#include <memory>
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

}  // namespace simcore::module_host
