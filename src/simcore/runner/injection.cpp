// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IMP-0113` / `SW-0113` -- the injection boundary: the set of ports
///   crossing `measured` (or `source`) into `simulate`, computed once from
///   the Resolved Run Spec and logged as ONE structured event before tick 0.
///
///   `source_ports` is `resim_runner.cpp::WiredSourcePorts` /
///   `core/resim.py::_wired_source_ports` ported directly -- same rule
///   (every port a non-`off` stage references through the reserved
///   `source` producer), expressed against `SpecInput`'s already-split
///   `producer`/`producer_port` pair rather than against a dotted string,
///   because `SW-0007` removed the reference grammar before the spec
///   reaches `simcore`.
///
///   `ports` is the half neither source computes (`SW-0113`'s own `NEW`):
///   the `measured -> simulate` edges themselves. This is the set
///   `R-SIM-10` calls the injection boundary -- where recorded data stops
///   and executed code starts. Stating it before tick 0 is what turns
///   *"which half of this run is evidence?"* from an inference into a
///   line in the log.
/// @author Pavan Karimajji

#include <algorithm>
#include <map>
#include <string>

#include "simcore/events.hpp"
#include "simcore/runner.hpp"

namespace simcore::runner {

namespace {

// The reserved pipeline-grammar keyword (`contracts/pipeline.py`'s own
// `producer_name == "source"`, checked literally) -- never a stage a
// pipeline could rename, which is why `R-SIM-21` exempts it from the
// literal-address ban.
constexpr const char* kSourceProducer = "source";

}  // namespace

InjectionBoundary ComputeInjectionBoundary(const RunSpec& spec) {
  std::map<std::string, std::string> mode_of;
  for (const auto& stage : spec.stages) {
    mode_of[stage.name] = stage.mode;
  }

  InjectionBoundary boundary;
  for (const auto& stage : spec.stages) {
    if (stage.mode == "off") continue;
    for (const auto& input : stage.inputs) {
      if (input.producer == kSourceProducer) {
        // Ported rule: a set, so a port two stages both consume is named
        // once (both ported twins use a set for exactly this reason).
        if (std::find(boundary.source_ports.begin(), boundary.source_ports.end(), input.producer_port) ==
            boundary.source_ports.end()) {
          boundary.source_ports.push_back(input.producer_port);
        }
      }
      if (stage.mode != "simulate") continue;
      const auto producer_mode = mode_of.find(input.producer);
      const bool from_measured = producer_mode != mode_of.end() && producer_mode->second == "measured";
      const bool from_source = input.producer == kSourceProducer;
      if (!from_measured && !from_source) continue;
      boundary.ports.push_back(BoundaryPort{input.producer, input.producer_port, stage.name, input.port});
    }
  }
  return boundary;
}

std::string InjectionBoundary::FormatEvent(const std::string& run_id) const {
  // One line, `event=<closed vocabulary value>` (`N-10`) -- the boundary is
  // a field of the run's own start event rather than a thirteenth event
  // name, which would have to be added to `docs/v2/events.yaml` and its
  // Python twin (`scripts/check_error_parity.py`) for information that is
  // already scoped to exactly one moment: run start.
  std::string line = "event=";
  line += ToString(Event::kRunStart);
  line += " run_id=" + run_id;
  line += " injection_boundary_ports=" + std::to_string(ports.size());
  line += " source_ports=" + std::to_string(source_ports.size());
  for (const auto& port : ports) {
    line += " inject=" + port.producer + "." + port.producer_port + "->" + port.consumer + "." + port.consumer_port;
  }
  for (const auto& port : source_ports) {
    line += " source=" + port;
  }
  return line;
}

}  // namespace simcore::runner
