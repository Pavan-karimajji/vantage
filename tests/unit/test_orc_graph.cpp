// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `BuildGraph` and `Rank` (`WP-03`, `IMP-0012`..`IMP-0014`): ranks of the
///   lab's `fan_out`, `diamond` and `feedback` shapes built here, a planted
///   loop (and a loop of one), each way a `simulate` stage has no start or
///   two, and the `KIND_COMPUTED_NOT_CONSUMED` mark. Unit tests of the
///   functions; the system tests `SYT-ORC-01`..`03` and `SYT-ORC-09` are built
///   in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <set>
#include <string>
#include <vector>

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

// A `simulate` stage started by a clock unless the test changes it.
SpecStage Stage(const std::string& name, std::vector<SpecInput> inputs = {}) {
  SpecStage stage;
  stage.name = name;
  stage.mode = "simulate";
  stage.clock_period_ns = 20'000'000;
  stage.inputs = std::move(inputs);
  return stage;
}

RunSpec Spec(std::vector<SpecStage> stages) {
  RunSpec spec;
  spec.run_id = "orc";
  spec.stages = std::move(stages);
  return spec;
}

int RankOf(const Graph& graph, const std::string& name) {
  const GraphStage* stage = graph.Find(name);
  return stage == nullptr ? -1 : stage->rank;
}

const std::set<std::string> kNoTopics;

// The lab's catalogue shapes (`X` is a source here: no edge, no rank).
RunSpec FanOut() {
  return Spec({Stage("A", {In("in", "source")}), Stage("B", {In("in", "A")}), Stage("C", {In("in", "A")})});
}
RunSpec Diamond() {
  return Spec({Stage("A", {In("in", "source")}), Stage("B", {In("in", "A")}), Stage("C", {In("in", "A")}),
               Stage("D", {In("b", "B"), In("c", "C")})});
}
RunSpec Feedback() {
  return Spec({Stage("A", {In("x", "source"), In("b", "B", /*previous_cycle=*/true)}), Stage("B", {In("in", "A")})});
}

TEST(OrcGraph, FanOutRanksTheProducerBeforeBothConsumers) {
  const Result<Graph> graph = BuildGraph(FanOut(), kNoTopics);
  ASSERT_TRUE(graph.ok()) << graph.error().Format();
  EXPECT_EQ(RankOf(graph.value(), "A"), 1);
  EXPECT_EQ(RankOf(graph.value(), "B"), 2);
  EXPECT_EQ(RankOf(graph.value(), "C"), 2);
}

TEST(OrcGraph, DiamondRanksTheJoinAfterBothBranches) {
  const Result<Graph> graph = BuildGraph(Diamond(), kNoTopics);
  ASSERT_TRUE(graph.ok()) << graph.error().Format();
  EXPECT_EQ(RankOf(graph.value(), "A"), 1);
  EXPECT_EQ(RankOf(graph.value(), "B"), 2);
  EXPECT_EQ(RankOf(graph.value(), "C"), 2);
  EXPECT_EQ(RankOf(graph.value(), "D"), 3);
}

TEST(OrcGraph, RankIsOnePlusTheHighestProducerNotTheNearestOne) {
  // D reads A (rank 1) and C (rank 3): rank 4, whatever the input order.
  const RunSpec spec = Spec({Stage("A"), Stage("B", {In("in", "A")}), Stage("C", {In("in", "B")}),
                             Stage("D", {In("a", "A"), In("c", "C")})});
  const Result<Graph> graph = BuildGraph(spec, kNoTopics);
  ASSERT_TRUE(graph.ok());
  EXPECT_EQ(RankOf(graph.value(), "D"), 4);
}

TEST(OrcGraph, RankDoesNotFollowDeclarationOrder) {
  // The consumer is declared before its producer.
  const RunSpec spec = Spec({Stage("B", {In("in", "A")}), Stage("A")});
  const Result<Graph> graph = BuildGraph(spec, kNoTopics);
  ASSERT_TRUE(graph.ok());
  EXPECT_EQ(RankOf(graph.value(), "A"), 1);
  EXPECT_EQ(RankOf(graph.value(), "B"), 2);
}

TEST(OrcGraph, FeedbackWithOnePreviousCycleInputIsRankedAndKeepsTheInput) {
  const Result<Graph> graph = BuildGraph(Feedback(), kNoTopics);
  ASSERT_TRUE(graph.ok()) << graph.error().Format();
  EXPECT_EQ(RankOf(graph.value(), "A"), 1);
  EXPECT_EQ(RankOf(graph.value(), "B"), 2);
  ASSERT_EQ(graph.value().edges.size(), 1u);  // A -> B only; the previous-cycle input adds none
  EXPECT_EQ(graph.value().edges[0].producer, "A");
  ASSERT_EQ(graph.value().previous_cycle_inputs.size(), 1u);
  EXPECT_EQ(graph.value().previous_cycle_inputs[0].consumer, "A");
  EXPECT_EQ(graph.value().previous_cycle_inputs[0].producer, "B");
}

TEST(OrcGraph, PlantedLoopWithoutAPreviousCycleInputIsRefusedNamingItsStages) {
  // The feedback shape with the marker taken away.
  RunSpec spec = Feedback();
  spec.stages[0].inputs[1].previous_cycle = false;
  const Result<Graph> graph = BuildGraph(spec, kNoTopics);
  ASSERT_FALSE(graph.ok());
  EXPECT_NE(graph.error().Format().find("A -> B -> A"), std::string::npos) << graph.error().Format();
  EXPECT_EQ(graph.error().kind, Kind::Authoring);
}

TEST(OrcGraph, ALoopNamesOnlyTheLoopNotTheStagesBehindIt) {
  // P -> A -> B -> A, and C reads B: C is behind the loop, not in it.
  const RunSpec spec = Spec({Stage("P"), Stage("A", {In("p", "P"), In("b", "B")}), Stage("B", {In("in", "A")}),
                             Stage("C", {In("in", "B")})});
  const Result<Graph> graph = BuildGraph(spec, kNoTopics);
  ASSERT_FALSE(graph.ok());
  const std::string text = graph.error().Format();
  EXPECT_NE(text.find("A -> B -> A"), std::string::npos) << text;
  EXPECT_EQ(text.find("C"), std::string::npos) << text;
  EXPECT_EQ(text.find("P"), std::string::npos) << text;
}

TEST(OrcGraph, AStageReadingItsOwnOutputIsALoopOfOne) {
  const Result<Graph> refused = BuildGraph(Spec({Stage("A", {In("self", "A")})}), kNoTopics);
  ASSERT_FALSE(refused.ok());
  EXPECT_NE(refused.error().Format().find("A -> A"), std::string::npos) << refused.error().Format();

  const Result<Graph> allowed = BuildGraph(Spec({Stage("A", {In("self", "A", /*previous_cycle=*/true)})}), kNoTopics);
  ASSERT_TRUE(allowed.ok()) << allowed.error().Format();
  EXPECT_EQ(RankOf(allowed.value(), "A"), 1);
}

TEST(OrcGraph, OnlyASimulateToSimulateEdgeGivesRank) {
  // B reads a measured stage and a source: neither adds an edge, so B is rank 1.
  SpecStage measured = Stage("M");
  measured.mode = "measured";
  const RunSpec spec = Spec({measured, Stage("B", {In("m", "M"), In("s", "source")})});
  const Result<Graph> graph = BuildGraph(spec, kNoTopics);
  ASSERT_TRUE(graph.ok());
  EXPECT_TRUE(graph.value().edges.empty());
  EXPECT_EQ(RankOf(graph.value(), "B"), 1);
  EXPECT_EQ(graph.value().Find("M"), nullptr);  // not a simulate stage: not in the graph
}

TEST(OrcGraph, ALoopThroughAMeasuredStageIsNotALoop) {
  SpecStage measured = Stage("M", {In("in", "A")});
  measured.mode = "measured";
  const RunSpec spec = Spec({Stage("A", {In("m", "M")}), measured});
  EXPECT_TRUE(BuildGraph(spec, kNoTopics).ok());
}

// --- IMP-0013: exactly one start -------------------------------------------------

std::string Refusal(const RunSpec& spec, const std::set<std::string>& topics = {}) {
  const Result<Graph> graph = BuildGraph(spec, topics);
  return graph.ok() ? std::string() : graph.error().Format();
}

TEST(OrcStart, ControlWithTheControlTopicInTheIndexIsAStart) {
  SpecStage stage = Stage("A");
  stage.trigger = "control";
  stage.clock_period_ns = 0;
  const Result<Graph> graph = BuildGraph(Spec({stage}), {"/A/control"});
  ASSERT_TRUE(graph.ok()) << graph.error().Format();
  EXPECT_EQ(graph.value().stages[0].start, StartKind::kControl);
}

TEST(OrcStart, TheIndexIsComparedByCanonicalTopicSpelling) {
  SpecStage stage = Stage("A");
  stage.trigger = "control";
  stage.clock_period_ns = 0;
  EXPECT_TRUE(BuildGraph(Spec({stage}), {"A/control"}).ok());  // a legacy spelling, no leading slash
}

TEST(OrcStart, ControlWithoutItsTopicInTheIndexIsRefusedNamingStageAndTopic) {
  SpecStage stage = Stage("A");
  stage.trigger = "control";
  stage.clock_period_ns = 0;
  const std::string text = Refusal(Spec({stage}), {"/B/control"});  // another stage's control only
  EXPECT_NE(text.find("stage 'A'"), std::string::npos) << text;
  EXPECT_NE(text.find("/A/control"), std::string::npos) << text;
}

TEST(OrcStart, ADeclaredInputAsTriggerIsAStart) {
  SpecStage stage = Stage("A", {In("trig", "source")});
  stage.trigger = "trig";
  stage.clock_period_ns = 0;
  const Result<Graph> graph = BuildGraph(Spec({stage}), kNoTopics);
  ASSERT_TRUE(graph.ok()) << graph.error().Format();
  EXPECT_EQ(graph.value().stages[0].start, StartKind::kInput);
  EXPECT_EQ(graph.value().stages[0].trigger_input, "trig");
}

TEST(OrcStart, ATriggerNamingNoDeclaredInputIsRefused) {
  SpecStage stage = Stage("A", {In("other", "source")});
  stage.trigger = "trig";
  stage.clock_period_ns = 0;
  const std::string text = Refusal(Spec({stage}));
  EXPECT_NE(text.find("stage 'A'"), std::string::npos) << text;
  EXPECT_NE(text.find("'trig'"), std::string::npos) << text;
}

TEST(OrcStart, AClockAboveZeroIsAStart) {
  const Result<Graph> graph = BuildGraph(Spec({Stage("A")}), kNoTopics);
  ASSERT_TRUE(graph.ok());
  EXPECT_EQ(graph.value().stages[0].start, StartKind::kClock);
  EXPECT_EQ(graph.value().stages[0].clock_period_ns, 20'000'000);
}

TEST(OrcStart, NoStartIsRefusedNamingTheStageAndWhatWasExpected) {
  SpecStage stage = Stage("A");
  stage.clock_period_ns = 0;
  const std::string text = Refusal(Spec({stage}));
  EXPECT_NE(text.find("stage 'A'"), std::string::npos) << text;
  EXPECT_NE(text.find("no start"), std::string::npos) << text;
  EXPECT_NE(text.find("A.control"), std::string::npos) << text;
  EXPECT_NE(text.find("clock_period_ns"), std::string::npos) << text;
}

TEST(OrcStart, ControlAndAClockAreTwoStarts) {
  SpecStage stage = Stage("A");
  stage.trigger = "control";
  const std::string text = Refusal(Spec({stage}), {"/A/control"});
  EXPECT_NE(text.find("more than one start"), std::string::npos) << text;
  EXPECT_NE(text.find("stage 'A'"), std::string::npos) << text;
}

TEST(OrcStart, AnInputTriggerAndAClockAreTwoStarts) {
  SpecStage stage = Stage("A", {In("trig", "source")});
  stage.trigger = "trig";
  const std::string text = Refusal(Spec({stage}));
  EXPECT_NE(text.find("more than one start"), std::string::npos) << text;
}

TEST(OrcStart, OnlyASimulateStageNeedsAStart) {
  SpecStage measured = Stage("M");
  measured.mode = "measured";
  measured.clock_period_ns = 0;
  SpecStage off = Stage("O");
  off.mode = "off";
  off.clock_period_ns = 0;
  EXPECT_TRUE(BuildGraph(Spec({measured, off, Stage("A")}), kNoTopics).ok());
}

TEST(OrcStart, TheFirstStageWithoutAStartIsTheOneNamed) {
  SpecStage bad = Stage("B");
  bad.clock_period_ns = 0;
  const std::string text = Refusal(Spec({Stage("A"), bad, Stage("C")}));
  EXPECT_NE(text.find("stage 'B'"), std::string::npos) << text;
}

// --- IMP-0014: computed, not consumed ----------------------------------------------

bool NotConsumed(const Graph& graph, const std::string& name) {
  return graph.Find(name)->computed_not_consumed;
}

TEST(OrcConsumed, ASimulateStageWhoseOnlyConsumersAreMeasuredIsMarked) {
  SpecStage measured = Stage("M", {In("in", "A")});
  measured.mode = "measured";
  const Result<Graph> graph = BuildGraph(Spec({Stage("A"), measured}), kNoTopics);
  ASSERT_TRUE(graph.ok());
  EXPECT_TRUE(NotConsumed(graph.value(), "A"));
}

TEST(OrcConsumed, ASimulateConsumerAmongOthersClearsTheMark) {
  SpecStage measured = Stage("M", {In("in", "A")});
  measured.mode = "measured";
  const Result<Graph> graph = BuildGraph(Spec({Stage("A"), measured, Stage("B", {In("in", "A")})}), kNoTopics);
  ASSERT_TRUE(graph.ok());
  EXPECT_FALSE(NotConsumed(graph.value(), "A"));
}

TEST(OrcConsumed, AStageNobodyConsumesIsTheEndOfAChainAndIsNotMarked) {
  const Result<Graph> graph = BuildGraph(Spec({Stage("A")}), kNoTopics);
  ASSERT_TRUE(graph.ok());
  EXPECT_FALSE(NotConsumed(graph.value(), "A"));
}

TEST(OrcConsumed, APreviousCycleConsumerThatIsSimulatedCountsAsConsuming) {
  const Result<Graph> graph = BuildGraph(Feedback(), kNoTopics);
  ASSERT_TRUE(graph.ok());
  EXPECT_FALSE(NotConsumed(graph.value(), "B"));  // A reads B, previous cycle
}

}  // namespace
}  // namespace simcore::orchestrator
