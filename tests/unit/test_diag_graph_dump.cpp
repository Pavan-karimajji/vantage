// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `BuildGraphView`/`DumpGraphText`/`CompareGraphDumps`
///   (`IMP-0131`, `WP-15`) -- structural unit coverage. `IT-10`'s own
///   engine-vs-Python comparison lives separately
///   (`tests/integration/test_it10_graph_diff.cpp`), since that test needs
///   a real `python3` on PATH and degrades honestly when one is absent.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <gtest/gtest.h>

namespace simcore::diagnostics {
namespace {

RunSpec MakeSpec() {
  RunSpec spec;
  spec.run_id = "ut_graph_dump";
  spec.grid_step_ns = 5'000'000;

  SpecStage a;
  a.name = "a";
  a.mode = "simulate";
  a.impl.path = "/opt/libs/a_sil.so";
  spec.stages.push_back(a);

  SpecStage b;
  b.name = "b";
  b.mode = "simulate";
  b.impl.path = "/opt/libs/b_sil.so";
  SpecInput in1;
  in1.port = "z_port";
  in1.producer = "a";
  in1.producer_port = "out";
  SpecInput in2;
  in2.port = "a_port";
  in2.producer = "a";
  in2.producer_port = "out2";
  b.inputs = {in1, in2};  // deliberately out of alphabetical order
  spec.stages.push_back(b);

  SpecStage measured;
  measured.name = "m";
  measured.mode = "measured";
  spec.stages.push_back(measured);

  return spec;
}

TEST(DiagGraphDump, LoadedSimulateStageReportsItsRealPath) {
  const GraphView snapshot = BuildGraphView(MakeSpec(), {"a", "b"});
  ASSERT_EQ(snapshot.stages.size(), 3u);
  EXPECT_EQ(snapshot.stages[0].impl, "/opt/libs/a_sil.so");
  EXPECT_EQ(snapshot.stages[1].impl, "/opt/libs/b_sil.so");
}

TEST(DiagGraphDump, ASimulateStageNotActuallyLoadedIsReportedAsUnloadedNeverGuessed) {
  // "b" is not in loaded_stages, e.g. its Component::Load failed.
  const GraphView snapshot = BuildGraphView(MakeSpec(), {"a"});
  EXPECT_EQ(snapshot.stages[1].impl, "unloaded");
}

TEST(DiagGraphDump, AMeasuredStageCarriesNoLiveImplByDefinition) {
  const GraphView snapshot = BuildGraphView(MakeSpec(), {"a", "b"});
  EXPECT_EQ(snapshot.stages[2].mode, "measured");
  EXPECT_EQ(snapshot.stages[2].impl, "measured");
}

TEST(DiagGraphDump, InputsAreSortedNeverHashOrder) {
  const GraphView snapshot = BuildGraphView(MakeSpec(), {"a", "b"});
  const std::vector<std::string> expected = {"a_port = a.out2", "z_port = a.out"};
  EXPECT_EQ(snapshot.stages[1].inputs, expected);
}

TEST(DiagGraphDump, DumpTextIsDeterministicAcrossRepeatedCalls) {
  const GraphView snapshot = BuildGraphView(MakeSpec(), {"a", "b"});
  EXPECT_EQ(DumpGraphText(snapshot), DumpGraphText(snapshot));
}

TEST(DiagGraphDump, CompareGraphDumpsAgreesOnIdenticalText) {
  const std::string text = DumpGraphText(BuildGraphView(MakeSpec(), {"a", "b"}));
  const GraphDumpDiff diff = CompareGraphDumps(text, text);
  EXPECT_TRUE(diff.matches);
}

// A deliberately introduced disagreement (`IT-10`'s own point, exercised at
// the comparator level here): a stage silently missing from the
// "prediction" side is caught, named by line, never passed as a match.
TEST(DiagGraphDump, CompareGraphDumpsCatchesADeliberatelyIntroducedDisagreement) {
  const std::string engine_text = DumpGraphText(BuildGraphView(MakeSpec(), {"a", "b"}));
  const std::string predicted_text = DumpGraphText(BuildGraphView(MakeSpec(), {"a"}));  // "b" reported unloaded

  const GraphDumpDiff diff = CompareGraphDumps(engine_text, predicted_text);
  ASSERT_FALSE(diff.matches);
  EXPECT_NE(diff.engine_line, diff.predicted_line);
  EXPECT_NE(diff.engine_line.find("b_sil.so"), std::string::npos);
  EXPECT_NE(diff.predicted_line.find("unloaded"), std::string::npos);
}

}  // namespace
}  // namespace simcore::diagnostics
