// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `PlanText` (`WP-03`, `IMP-0015`): one line per `simulate` stage with its
///   rank, start and previous-cycle inputs, from the `RunSpec` and the graph
///   alone; the text is deterministic and a different wiring gives a different
///   text. Unit tests of the function; the system test `SYT-ORC-10` is built
///   in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <set>
#include <string>

#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {
namespace {

SpecInput In(const std::string& port, const std::string& producer, bool previous_cycle = false) {
  SpecInput input;
  input.port = port;
  input.producer = producer;
  input.producer_port = "out";
  input.previous_cycle = previous_cycle;
  return input;
}

SpecStage Stage(const std::string& name, std::vector<SpecInput> inputs = {}) {
  SpecStage stage;
  stage.name = name;
  stage.mode = "simulate";
  stage.clock_period_ns = 20'000'000;
  stage.inputs = std::move(inputs);
  return stage;
}

// The lab's `feedback` shape with a recorded control on B.
RunSpec Feedback() {
  RunSpec spec;
  spec.run_id = "plan_run";
  SpecStage a = Stage("A", {In("x", "source"), In("b", "B", /*previous_cycle=*/true)});
  SpecStage b = Stage("B", {In("in", "A")});
  b.trigger = "control";
  b.clock_period_ns = 0;
  spec.stages = {a, b};
  return spec;
}

const std::set<std::string> kTopics = {"/B/control"};

TEST(OrcPlan, OneLinePerSimulateStageWithRankStartAndPreviousCycleInputs) {
  const RunSpec spec = Feedback();
  const Result<Graph> graph = BuildGraph(spec, kTopics);
  ASSERT_TRUE(graph.ok()) << graph.error().Format();
  EXPECT_EQ(PlanText(spec, graph.value()),
            "run_id: plan_run\n"
            "stage: A rank=1 start=clock:20000000ns previous_cycle=[b<-B.out]\n"
            "stage: B rank=2 start=control previous_cycle=[]\n");
}

TEST(OrcPlan, AnInputTriggerIsPrintedWithItsPort) {
  RunSpec spec;
  spec.run_id = "r";
  SpecStage a = Stage("A", {In("trig", "source")});
  a.trigger = "trig";
  a.clock_period_ns = 0;
  spec.stages = {a};
  const Result<Graph> graph = BuildGraph(spec, {});
  ASSERT_TRUE(graph.ok());
  EXPECT_NE(PlanText(spec, graph.value()).find("start=input:trig"), std::string::npos);
}

TEST(OrcPlan, AMeasuredStageHasNoLine) {
  RunSpec spec = Feedback();
  spec.stages[0].mode = "measured";
  spec.stages[0].inputs.erase(spec.stages[0].inputs.begin() + 1);  // A no longer reads B
  const Result<Graph> graph = BuildGraph(spec, kTopics);
  ASSERT_TRUE(graph.ok()) << graph.error().Format();
  const std::string text = PlanText(spec, graph.value());
  EXPECT_EQ(text.find("stage: A"), std::string::npos) << text;
  EXPECT_NE(text.find("stage: B rank=1"), std::string::npos) << text;
}

TEST(OrcPlan, TheSameSetupGivesTheSameTextAndADifferentWiringAnotherOne) {
  const RunSpec spec = Feedback();
  const std::string first = PlanText(spec, BuildGraph(spec, kTopics).value());
  EXPECT_EQ(first, PlanText(spec, BuildGraph(spec, kTopics).value()));

  RunSpec changed = spec;
  changed.stages[0].inputs.erase(changed.stages[0].inputs.begin() + 1);  // drop the feedback input
  EXPECT_NE(first, PlanText(changed, BuildGraph(changed, kTopics).value()));
}

}  // namespace
}  // namespace simcore::orchestrator
