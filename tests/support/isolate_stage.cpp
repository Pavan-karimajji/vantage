// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `isolate_stage` (`WP-18`, `IMP-0117`; fixture `F-ISOLATE`): hosts one stage of a lab case through
///   `RunIsolatedStage` -- the run setup given has that one stage simulated and the others measured, and its child is
///   a `simengine` -- and prints what came back, then ends. That it prints at all is the proof the asker outlived
///   the stage's crash.
///
///     isolate_stage <run_setup.json> <stage> <simengine> [--timeout-s N]
///   Prints `outcome=<ok|fail|crash|timeout|failed_to_start> exit=<SimExitCode> stage=<name> asker_alive=1`, where
///   `exit` is the code the supervisor would give that outcome: 0, the child's own code on a fail, 8, 7, 6.
/// @author Pavan Karimajji

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>

#include "simcore/abi/simcore.h"
#include "simcore/module_host.hpp"

int main(int argc, char** argv) {
  if (argc < 4) {
    std::cerr << "usage: isolate_stage <run_setup.json> <stage> <simengine> [--timeout-s N]\n";
    return 2;
  }
  const std::string setup = argv[1];
  const std::string stage = argv[2];
  const std::filesystem::path simengine = argv[3];
  int timeout_s = 120;
  for (int i = 4; i + 1 < argc; ++i) {
    if (std::string(argv[i]) == "--timeout-s") timeout_s = std::atoi(argv[i + 1]);
  }
  using simcore::module_host::IsolatedOutcome;
  const std::filesystem::path capture = std::filesystem::path(setup + ".isolated.stderr.txt");
  const simcore::module_host::IsolatedRunResult result =
      simcore::module_host::RunIsolatedStage(stage, simengine, {setup}, std::chrono::seconds(timeout_s), capture);
  int exit_code = 0;
  switch (result.outcome) {
    case IsolatedOutcome::kOk: exit_code = kSimExitOk; break;
    case IsolatedOutcome::kFail: exit_code = result.exit_code; break;
    case IsolatedOutcome::kCrashed: exit_code = kSimExitCrash; break;
    case IsolatedOutcome::kTimedOut: exit_code = kSimExitTimeout; break;
    case IsolatedOutcome::kFailedToStart: exit_code = kSimExitInfra; break;
  }
  std::cout << "outcome=" << simcore::module_host::ToString(result.outcome) << " exit=" << exit_code
            << " stage=" << result.stage << " asker_alive=1\n";
  return 0;
}
