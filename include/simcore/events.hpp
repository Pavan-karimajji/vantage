// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   The closed event= vocabulary (N-10, SI-07). Ported from
///   docs/v2/events.yaml -- the Python half is
///   adas_sim.diagnostics.events.Event, kept in parity by
///   scripts/check_error_parity.py.
/// @author Pavan Karimajji

#pragma once

namespace simcore {

// Thirteen values, no free text (N-10: "event= value added to the closed
// vocabulary"). Adding a value is a review, never a runtime extension
// point.
enum class Event {
  kRunStart,
  kRunEnd,
  kStageInit,
  kStageShutdown,
  kExecOk,
  kExecFail,
  kPortMissing,
  kPortOverridden,
  kDegrade,
  kExpectPass,
  kExpectFail,
  kBundleMismatch,
  kDedupStarted,
};

const char* ToString(Event event);

}  // namespace simcore
