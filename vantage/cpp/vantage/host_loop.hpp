// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `WP-33` (`SM-11`/`vantage`): the headless half of the in-process host
///   -- `test_it11_embed_host.cpp`'s own `UT-ABI-04` shape (attach a real
///   `InProcessTransport`, converted to `TransportPublisher*` BEFORE
///   erasure per `simcore.h`'s own documented gotcha; step; drain
///   `tryReceive()` between steps), now delivering each cycle's frames into
///   a real `viz::session::PushSource` via `FrameBridge` instead of
///   collecting raw bytes for a test to inspect directly.
///
///   No GLFW, no window, no `main()` argv -- that is `WP-34`'s own scope
///   (this file's own header note in the WP-33 plan row). This is the
///   mechanism a future `vantage.cpp` `main()` calls once per run, proven
///   here by a real integration test with no display.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include <cstdint>
#include <string>

#include "viz/session/source.hpp"

namespace sim::vantage {

struct HostLoopResult {
  bool ok = true;
  std::string error;   // empty iff ok
  int cycles_stepped = 0;
};

// Creates the engine from `run_spec_path`/`config_path` (`simEngineCreate`'s
// own two-path contract), attaches a real `InProcessTransport`, then loops
// `simEngineStepOnce` to exhaustion, bridging every cycle's real frames into
// `sink` via `FrameBridge`/`PushSource::DeliverTick`. Returns once the run
// is exhausted; `sink` must already be `Open()`ed by the caller (this
// function owns the engine's lifetime, never the sink's).
HostLoopResult RunEmbedded(const std::string& run_spec_path, const std::string& config_path,
                           std::int64_t exec_timeout_ms, viz::session::PushSource& sink);

}  // namespace sim::vantage
