// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `PlanText` (`IMP-0015`, `WP-03`): the plan printed before anything
///   runs -- from the `RunSpec` and the graph alone, one line per `simulate`
///   stage. It loads no library and reads no recording. Replaces the schedule
///   dump (`PredictSchedule`, `ScheduleDumpText`): with no base grid the
///   schedule cannot be predicted from the setup, but ranks, starts and
///   previous-cycle inputs can.
/// @author Pavan Karimajji

#include <sstream>

#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {

std::string PlanText(const RunSpec& spec, const Graph& graph) {
  std::ostringstream out;
  out << "run_id: " << spec.run_id << "\n";
  for (const GraphStage& stage : graph.stages) {
    out << "stage: " << stage.name << " rank=" << stage.rank << " start=";
    switch (stage.start) {
      case StartKind::kControl:
        out << "control";
        break;
      case StartKind::kInput:
        out << "input:" << stage.trigger_input;
        break;
      case StartKind::kClock:
        out << "clock:" << stage.clock_period_ns << "ns";
        break;
    }
    out << " previous_cycle=[";
    bool first = true;
    for (const GraphEdge& edge : graph.previous_cycle_inputs) {
      if (edge.consumer != stage.name) continue;
      if (!first) out << ",";
      first = false;
      out << edge.consumer_port << "<-" << edge.producer << "." << edge.producer_port;
    }
    out << "]\n";
  }
  return out.str();
}

}  // namespace simcore::orchestrator
