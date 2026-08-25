// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `WP-33` (`SM-11`/`vantage`): the bridge nothing built before this pass
///   -- turns one cycle's real `adas::transport::PortFrame`s (raw bytes off
///   a live `simcore::transport` attach) into one `viz::session::Tick`, the
///   shape `viz::session::PushSource::DeliverTick` already expects.
///   `PushSource` existed as the intended live-push entry point
///   (`VZ-15`/`WP-12`); nothing called it until this file.
///
///   **Named, honest limitation:** every `PortValue::schema_bytes`/
///   `schema_name` this bridge produces is empty. Resolving them needs a
///   manifest source reachable in-process, which this pass does not wire in
///   -- per `R-SIM-25` an unfilled field reads `unknown`, never a guessed
///   value. `Tick::t_ns`/`PortValue::t_ns` carry the engine's own cycle
///   count, not true elapsed nanoseconds -- the ABI exposes no wall-clock/
///   period value at this remove (`R-SIM-18`'s period lives in the config
///   bundle, not fetched here). Both are named `vantage` follow-on scope
///   (`WP-34`), not silently faked.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include <cstdint>
#include <vector>

#include "transport/ITransport.hpp"
#include "viz/session/tick.hpp"

namespace sim::vantage {

// Accumulates every `PortFrame` published during ONE engine cycle (a real
// `tryReceive()` drain loop, mirroring `test_it11_embed_host.cpp`'s own
// `UT-ABI-04` shape) into one `viz::session::Tick`. `AddFrame` copies
// `frame.data`/`size` immediately -- `PortFrame::data` is only valid until
// the next `tryReceive`/`detach` call (`ITransport.hpp`'s own contract), so
// nothing may retain the pointer past this call.
class FrameBridge {
 public:
  void AddFrame(const adas::transport::PortFrame& frame);

  // Packages every frame added since construction/the last `TakeTick` into
  // one `Tick` and clears for the next cycle. `cycle_index` becomes both
  // `Tick::index` and every contained `PortValue::t_ns` -- see this file's
  // own top note on why that is a cycle count, not true nanoseconds.
  viz::session::Tick TakeTick(std::uint64_t cycle_index);

 private:
  std::vector<viz::session::PortValue> pending_;
};

}  // namespace sim::vantage
