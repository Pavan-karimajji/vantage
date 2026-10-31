// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The orchestrator's parts (`VANTAGE_Architecture.md` §3.2, §5, §11;
///   `IMP-0011`..`IMP-0015`). This slice (`WP-03`) builds the graph, the
///   ranks, the start check and the plan text -- all of it pure functions of
///   the `RunSpec` (and, for the start check, the recording's topic index):
///   no library is loaded, no file opened, nothing executed.
///
///   **Not wired yet.** `BuildGraph` is not called by `simEngineCreate`
///   (`abi/simcore.cpp`): the call, with `PlanText` printed before any library
///   loads and each refusal returned as a load error, goes into
///   `Runner::Construct` in `WP-05` (`IMP-0028`). `scheduler.hpp` stays beside
///   this header until `WP-04` deletes it (`IMP-0024`).
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <set>
#include <string>
#include <vector>

#include "simcore/errors.hpp"
#include "simcore/runspec.hpp"

namespace simcore::orchestrator {

// `WP-04` builds these four (`IMP-0016`..`IMP-0023`); they are named here so
// the header already says what the orchestrator is made of, and carry no
// members until then.
class EventQueue;
class Orchestrator;
class Readiness;
struct EventLog;

// How a `simulate` stage is started (rule 3): exactly one of the three.
enum class StartKind {
  kControl,  // `trigger: control` -- the stage's recorded control message
  kInput,    // `trigger: <input port>` -- a new `measurement_counter` on that input
  kClock,    // `clock_period_ns` above 0
};

// One wiring edge: `producer.producer_port` feeds `consumer.consumer_port`.
struct GraphEdge {
  std::string producer;
  std::string producer_port;
  std::string consumer;
  std::string consumer_port;
};

// One `simulate` stage, in the setup's declaration order.
struct GraphStage {
  std::string name;
  int rank = 0;  // 1 + the highest rank among the simulated stages it reads; 1 if none (§2.2)
  StartKind start = StartKind::kClock;
  std::string trigger_input;          // the port, for `StartKind::kInput`
  std::int64_t clock_period_ns = 0;   // for `StartKind::kClock`
  // `IMP-0014`: declared consumers exist and none of them is `simulate`; the
  // orchestrator raises `KIND_COMPUTED_NOT_CONSUMED` on it, once.
  bool computed_not_consumed = false;
};

struct Graph {
  std::vector<GraphStage> stages;  // `simulate` stages only, declaration order
  // Edges from a `simulate` producer to a `simulate` consumer, never a
  // `previous_cycle` input. These are the only edges that give rank.
  std::vector<GraphEdge> edges;
  // Every `previous_cycle` input of a `simulate` stage, whatever its producer.
  std::vector<GraphEdge> previous_cycle_inputs;

  // nullptr when `name` is not a `simulate` stage of this graph.
  const GraphStage* Find(const std::string& name) const;
};

// `IMP-0012`, `IMP-0013`, `IMP-0014`. Builds the graph from the wiring, ranks
// it, and checks every `simulate` stage has exactly one start. A load error
// (Kind::Authoring) names the loop's stages (rules 1, 2), or the stage and
// what was expected (rule 3). `recorded_topics` is the recording's topic index
// (`Reader::Describe()` keys); `<stage>.control` is looked up in it.
Result<Graph> BuildGraph(const RunSpec& spec, const std::set<std::string>& recorded_topics);

// `IMP-0012`: fills `GraphStage::rank` from `edges`, or fails naming the stages
// of a loop. Called by `BuildGraph`; public so a caller holding a graph it
// changed (and the tests) can rank it again.
Result<bool> Rank(Graph& graph);

// `IMP-0015`: the plan, from the `RunSpec` and the graph alone -- one line per
// `simulate` stage: rank, its start, its previous-cycle inputs. Deterministic
// text; loads no library and reads no recording.
std::string PlanText(const RunSpec& spec, const Graph& graph);

}  // namespace simcore::orchestrator
