// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   The closed event= vocabulary (N-10), C++ half. Ported verbatim from
///   docs/v2/events.yaml -- same values as the Python
///   adas_sim.diagnostics.events.Event enum, kept in parity by
///   scripts/check_error_parity.py.
/// @author Pavan Karimajji

#include "simcore/events.hpp"

namespace simcore {

const char* ToString(Event event) {
  switch (event) {
    case Event::kRunStart:
      return "run_start";
    case Event::kRunEnd:
      return "run_end";
    case Event::kStageInit:
      return "stage_init";
    case Event::kStageShutdown:
      return "stage_shutdown";
    case Event::kExecOk:
      return "exec_ok";
    case Event::kExecFail:
      return "exec_fail";
    case Event::kPortMissing:
      return "port_missing";
    case Event::kPortOverridden:
      return "port_overridden";
    case Event::kDegrade:
      return "degrade";
    case Event::kExpectPass:
      return "expect_pass";
    case Event::kExpectFail:
      return "expect_fail";
    case Event::kBundleMismatch:
      return "bundle_mismatch";
  }
  return "";  // unreachable for a valid Event; never guess a value
}

}  // namespace simcore
