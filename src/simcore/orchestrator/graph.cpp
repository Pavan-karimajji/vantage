// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `BuildGraph` and `Rank` (`IMP-0012`..`IMP-0014`, `WP-03`): the
///   dependency graph of the `simulate` stages, their ranks (rules 1, 2), the
///   exactly-one-start check (rule 3) and the `KIND_COMPUTED_NOT_CONSUMED`
///   mark. Pure functions of the `RunSpec` and the recording's topic index.
/// @author Pavan Karimajji

#include <algorithm>
#include <map>

#include "simcore/io.hpp"
#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {

namespace {

constexpr const char* kSourceProducer = "source";

Error Refusal(std::string expected, std::string found, std::string where) {
  return Error{Kind::Authoring, std::move(expected), std::move(found), std::move(where), ""};
}

// A cycle among the stages Kahn's pass could not rank. Walks producer links
// from the earliest-declared stage left, until a stage repeats; returns the
// cycle starting at its earliest-declared member.
std::vector<std::string> FindLoop(const Graph& graph, const std::set<std::string>& left) {
  std::map<std::string, std::vector<std::string>> producers_of;
  for (const GraphEdge& edge : graph.edges) {
    if (left.count(edge.consumer) != 0 && left.count(edge.producer) != 0) {
      producers_of[edge.consumer].push_back(edge.producer);
    }
  }
  std::string current;
  for (const GraphStage& stage : graph.stages) {
    if (left.count(stage.name) != 0) {
      current = stage.name;
      break;
    }
  }
  std::vector<std::string> path;
  while (std::find(path.begin(), path.end(), current) == path.end()) {
    path.push_back(current);
    current = producers_of[current].front();  // every stage left has a producer left
  }
  // `path` follows consumer -> producer; the loop is the tail from `current`.
  std::vector<std::string> loop(std::find(path.begin(), path.end(), current), path.end());
  std::reverse(loop.begin(), loop.end());  // producer -> consumer order
  const auto declared_first = std::min_element(loop.begin(), loop.end(), [&graph](const auto& a, const auto& b) {
    const auto position = [&graph](const std::string& name) {
      return std::find_if(graph.stages.begin(), graph.stages.end(),
                          [&name](const GraphStage& s) { return s.name == name; }) -
             graph.stages.begin();
    };
    return position(a) < position(b);
  });
  std::rotate(loop.begin(), declared_first, loop.end());
  return loop;
}

std::string JoinLoop(const std::vector<std::string>& loop) {
  std::string text;
  for (const std::string& name : loop) text += name + " -> ";
  return text + loop.front();
}

}  // namespace

const GraphStage* Graph::Find(const std::string& name) const {
  for (const GraphStage& stage : stages) {
    if (stage.name == name) return &stage;
  }
  return nullptr;
}

// IMP-0012: rank = 1 + the highest rank among the simulated stages read, 1 if
// none. Kahn's pass over `edges`; whatever it cannot place is on or behind a loop.
Result<bool> Rank(Graph& graph) {
  std::map<std::string, int> unranked_producers;
  std::map<std::string, int> rank;  // highest producer rank + 1 so far
  std::set<std::string> placed;     // stages whose every producer is placed
  for (const GraphStage& stage : graph.stages) unranked_producers[stage.name] = 0;
  for (const GraphEdge& edge : graph.edges) ++unranked_producers[edge.consumer];

  std::vector<std::string> ready;
  for (const GraphStage& stage : graph.stages) {
    if (unranked_producers[stage.name] == 0) {
      rank[stage.name] = 1;
      placed.insert(stage.name);
      ready.push_back(stage.name);
    }
  }
  while (!ready.empty()) {
    const std::string producer = ready.back();
    ready.pop_back();
    for (const GraphEdge& edge : graph.edges) {
      if (edge.producer != producer) continue;
      rank[edge.consumer] = std::max(rank[edge.consumer], rank[producer] + 1);
      if (--unranked_producers[edge.consumer] == 0) {
        placed.insert(edge.consumer);
        ready.push_back(edge.consumer);
      }
    }
  }

  std::set<std::string> left;
  for (const GraphStage& stage : graph.stages) {
    if (placed.count(stage.name) == 0) left.insert(stage.name);
  }
  if (!left.empty()) {
    const std::vector<std::string> loop = FindLoop(graph, left);
    return Result<bool>::Fail(Refusal(
        "every loop in the wiring broken by one input marked previous_cycle",
        "a loop through " + JoinLoop(loop) + " with no previous_cycle input",
        "stages " + JoinLoop(loop)));
  }
  for (GraphStage& stage : graph.stages) stage.rank = rank[stage.name];
  return Result<bool>::Ok(true);
}

// IMP-0013: exactly one of control (with `<stage>.control` in the index), a
// declared input as trigger, a clock above 0.
static Result<bool> ResolveStart(const SpecStage& spec_stage, const std::set<std::string>& topics, GraphStage& out) {
  const bool by_control = spec_stage.trigger == "control";
  const bool by_input = !spec_stage.trigger.empty() && !by_control;
  const bool by_clock = spec_stage.clock_period_ns > 0;
  const std::string where = "stage '" + spec_stage.name + "'";
  const std::string expected =
      "exactly one start: trigger 'control' with '" + spec_stage.name +
      ".control' in the recording, a declared input as trigger, or clock_period_ns above 0";

  const int starts = static_cast<int>(by_control) + static_cast<int>(by_input) + static_cast<int>(by_clock);
  if (starts == 0) return Result<bool>::Fail(Refusal(expected, "no start", where));
  if (starts > 1) {
    std::string found = "more than one start:";
    if (by_control) found += " trigger 'control'";
    if (by_input) found += " trigger input '" + spec_stage.trigger + "'";
    if (by_clock) found += " clock_period_ns " + std::to_string(spec_stage.clock_period_ns);
    return Result<bool>::Fail(Refusal(expected, found, where));
  }
  if (by_control) {
    const std::string topic = io::CanonicalTopic(spec_stage.name + ".control");
    if (topics.count(topic) == 0) {
      return Result<bool>::Fail(
          Refusal("'" + topic + "' in the recording's topic index (trigger 'control')", "no such topic", where));
    }
    out.start = StartKind::kControl;
  } else if (by_input) {
    const bool declared = std::any_of(spec_stage.inputs.begin(), spec_stage.inputs.end(),
                                      [&](const SpecInput& input) { return input.port == spec_stage.trigger; });
    if (!declared) {
      return Result<bool>::Fail(Refusal("trigger '" + spec_stage.trigger + "' to name a declared input of the stage",
                                        "no such input", where));
    }
    out.start = StartKind::kInput;
    out.trigger_input = spec_stage.trigger;
  } else {
    out.start = StartKind::kClock;
    out.clock_period_ns = spec_stage.clock_period_ns;
  }
  return Result<bool>::Ok(true);
}

Result<Graph> BuildGraph(const RunSpec& spec, const std::set<std::string>& recorded_topics) {
  std::set<std::string> topics;
  for (const std::string& topic : recorded_topics) topics.insert(io::CanonicalTopic(topic));

  std::set<std::string> simulated;
  for (const SpecStage& stage : spec.stages) {
    if (stage.mode == "simulate") simulated.insert(stage.name);
  }

  Graph graph;
  for (const SpecStage& spec_stage : spec.stages) {
    if (spec_stage.mode != "simulate") continue;
    GraphStage stage;
    stage.name = spec_stage.name;
    const Result<bool> start = ResolveStart(spec_stage, topics, stage);
    if (!start.ok()) return Result<Graph>::Fail(start.error());
    graph.stages.push_back(std::move(stage));

    for (const SpecInput& input : spec_stage.inputs) {
      const GraphEdge edge{input.producer, input.producer_port, spec_stage.name, input.port};
      if (input.previous_cycle) {
        graph.previous_cycle_inputs.push_back(edge);
      } else if (simulated.count(input.producer) != 0) {
        graph.edges.push_back(edge);
      }
    }
  }

  // IMP-0014: a simulate stage with declared consumers, none of them simulate.
  // A stage nobody consumes at all is the end of a chain and is not marked.
  for (GraphStage& stage : graph.stages) {
    bool consumed = false;
    bool consumed_by_simulate = false;
    for (const SpecStage& other : spec.stages) {
      for (const SpecInput& input : other.inputs) {
        if (input.producer != stage.name) continue;
        consumed = true;
        if (simulated.count(other.name) != 0) consumed_by_simulate = true;
      }
    }
    stage.computed_not_consumed = consumed && !consumed_by_simulate;
  }

  const Result<bool> ranked = Rank(graph);
  if (!ranked.ok()) return Result<Graph>::Fail(ranked.error());
  return Result<Graph>::Ok(std::move(graph));
}

}  // namespace simcore::orchestrator
