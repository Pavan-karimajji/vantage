// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `PredictSchedule`/`ScheduleDumpText` (`SW-0076`, `IMP-0076`,
///   `WP-15`) -- "the schedule is emitted before it is executed". Builds a
///   throwaway `Scheduler` from the same `RunSpec` a real run would use and
///   walks it `horizon_ticks` times, reading only `IsDue()`/`Order()`/
///   `now_ns()` -- the exact three calls `runner::Runner::StepOnce` reads
///   before it calls a single `Component::Exec` (`cycle_loop.cpp`). No
///   component is loaded, no port is read, nothing here can execute
///   anything; the plan this produces is therefore comparable against a
///   real run's actual dispatch order without either side influencing the
///   other.
/// @author Pavan Karimajji

#include "simcore/scheduler.hpp"

#include <sstream>

namespace simcore::scheduler {

std::vector<ScheduleTick> PredictSchedule(const RunSpec& spec, std::uint64_t horizon_ticks) {
  Scheduler scheduler(spec);
  std::vector<ScheduleTick> plan;
  plan.reserve(horizon_ticks + 1);

  for (std::uint64_t i = 0; i <= horizon_ticks; ++i) {
    ScheduleTick tick;
    tick.tick_index = scheduler.tick_index();
    tick.now_ns = scheduler.now_ns();
    for (const std::string& stage : scheduler.Order()) {
      if (scheduler.IsDue(stage)) tick.due_stages.push_back(stage);
    }
    plan.push_back(std::move(tick));
    if (i < horizon_ticks) scheduler.Advance();
  }
  return plan;
}

std::string ScheduleDumpText(const RunSpec& spec, std::uint64_t horizon_ticks) {
  std::ostringstream out;
  out << "run_id: " << spec.run_id << "\n";
  out << "grid_step_ns: " << spec.grid_step_ns << "\n";
  for (const ScheduleTick& tick : PredictSchedule(spec, horizon_ticks)) {
    out << "tick: " << tick.tick_index << " now_ns=" << tick.now_ns << " due=[";
    for (std::size_t i = 0; i < tick.due_stages.size(); ++i) {
      if (i != 0) out << ",";
      out << tick.due_stages[i];
    }
    out << "]\n";
  }
  return out.str();
}

}  // namespace simcore::scheduler
