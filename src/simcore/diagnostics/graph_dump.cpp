// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `BuildGraphView`/`DumpGraphText`/`CompareGraphDumps`
///   (`IMP-0131`, `WP-15`) -- MOVE+adapt of `sil_host/src/graph_dump.cpp`'s
///   `DumpGraphText` onto `simcore::RunSpec` (that file's own `Pipeline`
///   type has no C++ twin here; `RunSpec` is the equivalent already-loaded
///   structure). The line format is deliberately the same shape
///   (`pipeline:`/`stage:`/`  input:` there, `run_id:`/`stage:`/
///   `  input:` here) so a reader who knows one dump can read the other.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <algorithm>
#include <set>
#include <sstream>

namespace simcore::diagnostics {

GraphView BuildGraphView(const RunSpec& spec, const std::vector<std::string>& loaded_stages) {
  const std::set<std::string> loaded(loaded_stages.begin(), loaded_stages.end());

  GraphView view;
  view.run_id = spec.run_id;
  view.grid_step_ns = spec.grid_step_ns;

  for (const SpecStage& stage : spec.stages) {
    GraphStageView out;
    out.name = stage.name;
    out.mode = stage.mode;
    // SW-0131: the engine's OWN view -- a `simulate` stage the engine
    // never got a live `Component` for (load failure, or simply not in
    // `loaded_stages`) is reported as "unloaded", never as the spec's own
    // (possibly stale) `impl.path` re-printed as if it were live.
    if (stage.mode == "simulate" && loaded.count(stage.name) != 0) {
      out.impl = stage.impl.path.empty() ? stage.impl.pattern : stage.impl.path;
    } else if (stage.mode == "simulate") {
      out.impl = "unloaded";
    } else {
      out.impl = stage.mode;  // "measured"/"off" stages carry no live impl
    }

    for (const SpecInput& input : stage.inputs) {
      std::ostringstream line;
      line << input.port << " = " << input.producer << "." << input.producer_port;
      out.inputs.push_back(line.str());
    }
    std::sort(out.inputs.begin(), out.inputs.end());  // never hash order (UT-A4-12/P-8)

    view.stages.push_back(std::move(out));
  }
  return view;
}

std::string DumpGraphText(const GraphView& view) noexcept {
  std::ostringstream out;
  out << "run_id: " << view.run_id << "\n";
  out << "grid_step_ns: " << view.grid_step_ns << "\n";
  for (const GraphStageView& stage : view.stages) {
    out << "stage: " << stage.name << " mode=" << stage.mode << " impl=" << stage.impl << "\n";
    for (const std::string& input : stage.inputs) {
      out << "  input: " << input << "\n";
    }
  }
  return out.str();
}

namespace {
std::vector<std::string> SplitLines(const std::string& text) {
  std::vector<std::string> lines;
  std::istringstream in(text);
  std::string line;
  while (std::getline(in, line)) lines.push_back(line);
  return lines;
}
}  // namespace

GraphDumpDiff CompareGraphDumps(const std::string& engine_dump, const std::string& predicted_dump) noexcept {
  const std::vector<std::string> engine_lines = SplitLines(engine_dump);
  const std::vector<std::string> predicted_lines = SplitLines(predicted_dump);
  const std::size_t n = std::max(engine_lines.size(), predicted_lines.size());

  for (std::size_t i = 0; i < n; ++i) {
    const std::string engine_line = i < engine_lines.size() ? engine_lines[i] : std::string("<missing line>");
    const std::string predicted_line =
        i < predicted_lines.size() ? predicted_lines[i] : std::string("<missing line>");
    if (engine_line != predicted_line) {
      return GraphDumpDiff{/*matches=*/false, i, engine_line, predicted_line};
    }
  }
  return GraphDumpDiff{/*matches=*/true, 0, "", ""};
}

}  // namespace simcore::diagnostics
