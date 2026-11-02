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
