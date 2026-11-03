// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SimEngineRunner` (`WP-09a`, `IMP-0041`): the `Runner` a `SimEngine` handle holds,
///   for a test executable that attaches a sink to `Runner::SetLiveMeasurement`
///   (`tests/support/step_tap.cpp`). Internal: not part of the C ABI, not installed,
///   and not for a host. The handle stays the owner.
/// @author Pavan Karimajji

#pragma once

#include "simcore/abi/simcore.h"

namespace simcore::runner {
class Runner;
}

// C++ linkage on purpose; null when `engine` is null or holds no constructed runner.
simcore::runner::Runner* SimEngineRunner(SimEngine* engine);

// `IMP-0060`: after a run ended with `kSimExitTimeout` the component's call may still be inside its
// library, so every later `simEngineCreate`, run or step in this process is refused. For a test that
// provokes the timeout and has to go on in the same process.
void SimEngineClearTimeoutRefusalForTest();
