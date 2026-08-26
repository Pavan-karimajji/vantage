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
///   `WP-34`: `EmbeddedEngine` is the step-once shape a real windowed
///   `main()` needs -- `RunEmbedded` below loops a whole run to exhaustion
///   in one blocking call, which does not fit a per-frame render loop (the
///   window would freeze until the run finished, and `PushSource`'s bounded
///   ring would have evicted everything but its last few ticks by the time
///   a frame is drawn). `EmbeddedEngine::StepOnce` is the same per-cycle
///   body (`simEngineStepOnce` -> drain -> bridge -> `DeliverTick`), called
///   once per frame on the caller's own thread instead -- no background
///   thread, since `PushSource` (a bare `std::deque`) has no locking and
///   nothing else in `viz`/`sim` drives a `Source` from a second thread.
///   `RunEmbedded` is now a thin loop over `Create`/`StepOnce`, kept for
///   `test_it23_vantage_bridge.cpp`'s own headless, no-window use.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include <cstdint>
#include <memory>
#include <string>

#include "simcore/errors.hpp"
#include "simcore/transport.hpp"
#include "vantage/frame_bridge.hpp"
#include "viz/session/source.hpp"

struct SimEngine;

namespace sim::vantage {

struct HostLoopResult {
  bool ok = true;
  std::string error;   // empty iff ok
  int cycles_stepped = 0;
};

// `WP-34`: owns one embedded engine's lifetime across many `StepOnce` calls
// -- the RAII shape `RunEmbedded`'s own loop body is refactored onto below.
// Move-only (owns `SimEngine*` and the attached `InProcessTransport`, which
// `StepOnce` hands the engine a non-owning pointer into -- moving would
// invalidate that pointer if the transport itself moved, so it is
// heap-allocated here specifically to stay address-stable across a move).
class EmbeddedEngine {
 public:
  // `simEngineCreate`'s own two-path/timeout contract (`simcore.h`). On
  // failure, the returned `Result` carries `simEngineCreate`'s own error
  // text -- never a partially-constructed `EmbeddedEngine`.
  static simcore::Result<EmbeddedEngine> Create(const std::string& run_spec_path,
                                                 const std::string& config_path,
                                                 std::int64_t exec_timeout_ms);

  ~EmbeddedEngine();
  EmbeddedEngine(EmbeddedEngine&&) noexcept;
  EmbeddedEngine& operator=(EmbeddedEngine&&) noexcept;
  EmbeddedEngine(const EmbeddedEngine&) = delete;
  EmbeddedEngine& operator=(const EmbeddedEngine&) = delete;

  // One `simEngineStepOnce` + drain `tryReceive()` + `FrameBridge::TakeTick`
  // + `sink.DeliverTick` -- the identical per-cycle body `RunEmbedded`'s own
  // loop used, now callable once per caller frame. Returns `false` once the
  // run is exhausted (mirrors `simEngineStepOnce`'s own `keep_going == 0`)
  // or once a step has already failed -- both cases leave `sink` untouched
  // and are a no-op on every subsequent call, never re-entering a destroyed
  // engine. A step failure sets `ok()`/`error()`; exhaustion alone does not
  // (`ok()` stays `true` -- exhaustion is expected, not an error).
  bool StepOnce(viz::session::PushSource& sink);

  bool ok() const { return ok_; }
  const std::string& error() const { return error_; }
  int cycles_stepped() const { return cycles_stepped_; }

 private:
  EmbeddedEngine() = default;

  SimEngine* engine_ = nullptr;
  std::unique_ptr<simcore::transport::InProcessTransport> transport_;
  FrameBridge bridge_;
  bool ok_ = true;
  bool exhausted_ = false;
  std::string error_;
  int cycles_stepped_ = 0;
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
