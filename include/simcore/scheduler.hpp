// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `Scheduler` (`SI-03`, `WP-09`) -- the multi-rate stepping engine,
///   `SW-0061`'s own "one execution path" made real: `IsDue`/`Advance`
///   decide when a module runs, `Order` (the order the constructor was
///   given -- consumed, never computed) decides in what sequence, and neither reads a message payload (`SW-0075`) or a
///   wall clock (`SW-0077`).
///
///   **Scope note, this slice (2026-08-21):** the core (`IsDue`,
///   `Advance`, `Order`) is built and tested
///   against real behaviour, ported from `sil_host/src/pipeline.cpp`'s
///   own `Step()` (the `DEDUPE`/`MOVE` source `WP-09`'s own plan row
///   names). Explicitly **not** attempted here, named rather than
///   discovered missing: the data-driven trigger (`SW-0065`, freshness-
///   key evaluation needs the sample buffers wired in), the five
///   sampling policies (`SW-0068`), missing-data behaviour beyond hold
///   (`SW-0070`), per-edge transport delay (`SW-0073`), play-rate pacing
///   (`SW-0078`), the pathological-grid warning (`SW-0067`) and
///   measured-rate reconciliation against a real recording (`SW-0414`).
///
///   **Retiring (VANTAGE `c1`).** This header stays only because the runner and
///   `simEngineCreate` still drive a `Scheduler`; `WP-05` deletes it with that
///   loop (`IMP-0024`) in favour of `orchestrator.hpp`. `ReconcileModuleFlag`
///   and `ScheduleFinding` are gone (`IMP-0025`, `WP-04`). The schedule dump
///   (`PredictSchedule`, `ScheduleDumpText`) is gone (`WP-03`, `IMP-0015`): its
///   successor is `orchestrator::PlanText`.
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "simcore/runspec.hpp"

namespace simcore::scheduler {

// SW-0061/0062/0064/0072/0075/0077/0413: consumes the grid step and
// execution order it is given (the run setup carries neither since schema
// 2.0; `WP-04` replaces this class) and the spec's per-stage clock periods
// -- never derives a GCD, never snaps a period, never reads wall-clock time
// or a message payload. `Advance()`
// is the ONLY writer of simulation time (`SW-0413`); no arrival,
// reconstructed cycle boundary or module output may move it.
class Scheduler {
 public:
  Scheduler(const RunSpec& spec, std::int64_t grid_step_ns, std::vector<std::string> order);

  // SW-0413: moves to the next tick -- simulation time becomes exactly
  // `tick_index() * grid_step_ns`, the arithmetic sequence the grid step
  // defines, from the declared run start (tick 0, time 0, nothing due
  // there but every stage's own period boundary at its first multiple).
  void Advance();

  std::int64_t now_ns() const { return now_ns_; }
  std::uint64_t tick_index() const { return tick_index_; }
  std::int64_t grid_step_ns() const { return grid_step_ns_; }

  // SW-0064: integer due-ness -- `now_ns % period == 0` (a `clock_period_ns==0`
  // stage is treated as due every tick, matching a static/aperiodic
  // producer's own real shape, ported from `pipeline.cpp::Step`'s
  // identical special case). Refuses (returns false, never throws) an
  // unknown stage name -- callers iterate `Order()`, which only ever
  // names real stages.
  bool IsDue(const std::string& stage_name) const;

  // SW-0072: the run's own execution order -- the one given at
  // construction, never recomputed. This class trusts it, the same way
  // `PortCatalogue::Resolve` trusts the spec's own declared port set.
  const std::vector<std::string>& Order() const { return order_; }

 private:
  RunSpec spec_;
  std::int64_t grid_step_ns_ = 0;
  std::int64_t now_ns_ = 0;
  std::uint64_t tick_index_ = 0;

  std::vector<std::string> order_;
};

}  // namespace simcore::scheduler
