// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `Scheduler`'s core -- see `simcore/scheduler.hpp` for the design
///   note. Due-ness and the tick clock are ported from
///   `sil_host/src/pipeline.cpp::Pipeline::Step`'s own
///   `elapsedNs_ % periodNs == 0` (confirmed by reading that file
///   directly, `WP-09`'s own `DEDUPE` source for `IMP-0061`/`IMP-0064`).
/// @author Pavan Karimajji

#include "simcore/scheduler.hpp"

#include <utility>

namespace simcore::scheduler {

namespace {
const SpecStage* FindStage(const RunSpec& spec, const std::string& name) {
  for (const auto& stage : spec.stages) {
    if (stage.name == name) return &stage;
  }
  return nullptr;
}
}  // namespace

Scheduler::Scheduler(const RunSpec& spec, std::int64_t grid_step_ns, std::vector<std::string> order)
    : spec_(spec), grid_step_ns_(grid_step_ns), order_(std::move(order)) {}

void Scheduler::Advance() {
  ++tick_index_;
  now_ns_ = static_cast<std::int64_t>(tick_index_) * grid_step_ns_;
}

bool Scheduler::IsDue(const std::string& stage_name) const {
  const SpecStage* stage = FindStage(spec_, stage_name);
  if (stage == nullptr) return false;
  if (stage->clock_period_ns == 0) return true;  // static/aperiodic producer -- always due, ported from pipeline.cpp
  return now_ns_ % stage->clock_period_ns == 0;
}

}  // namespace simcore::scheduler
