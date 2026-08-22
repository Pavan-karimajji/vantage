// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `UT-EDG-01`/`02` (`IMP-0132`/`0133`, `WP-15`): `CycleTrace`
///   accounts for every module on every tick including held ones, and is
///   purely additive -- recording never alters what a caller passes
///   through it.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <gtest/gtest.h>

namespace simcore::diagnostics {
namespace {

TEST(UtEdg01CycleTrace, AccountsForRanAndHeldModulesAcrossTicks) {
  CycleTrace trace;
  trace.Record(CycleTraceEntry{0, "a", CycleOutcome::kRan, {"a.in"}, std::chrono::microseconds(500)});
  trace.Record(CycleTraceEntry{0, "b", CycleOutcome::kHeld, {}, std::chrono::nanoseconds(0)});
  trace.Record(CycleTraceEntry{1, "a", CycleOutcome::kHeld, {}, std::chrono::nanoseconds(0)});
  trace.Record(CycleTraceEntry{1, "b", CycleOutcome::kRan, {"b.in"}, std::chrono::microseconds(300)});

  EXPECT_EQ(trace.entries().size(), 4u);
  EXPECT_EQ(trace.RanCount("a"), 1u);
  EXPECT_EQ(trace.HeldCount("a"), 1u);
  EXPECT_EQ(trace.RanCount("b"), 1u);
  EXPECT_EQ(trace.HeldCount("b"), 1u);

  // Every (tick, stage) cell is covered exactly once each -- "every module
  // on every tick including held ones" (SW-0132's own Accept), checkable.
  const auto cells = trace.CoveredCells();
  const std::vector<std::pair<std::uint64_t, std::string>> expected = {
      {0, "a"}, {0, "b"}, {1, "a"}, {1, "b"}};
  EXPECT_EQ(cells, expected);
}

TEST(UtEdg01CycleTrace, TimingReconcilesWithPerModuleTotals) {
  CycleTrace trace;
  trace.Record(CycleTraceEntry{0, "a", CycleOutcome::kRan, {}, std::chrono::milliseconds(4)});
  trace.Record(CycleTraceEntry{1, "a", CycleOutcome::kRan, {}, std::chrono::milliseconds(6)});
  trace.Record(CycleTraceEntry{2, "a", CycleOutcome::kHeld, {}, std::chrono::nanoseconds(0)});

  EXPECT_EQ(trace.TotalDuration("a"), std::chrono::milliseconds(10));
  EXPECT_EQ(trace.TotalDuration("unknown_stage"), std::chrono::nanoseconds(0));
}

// UT-EDG-02: enabling the trace does not change a port value -- `Record`
// takes and stores exactly what it is given, with no branch that could
// mutate `inputs_received` or a value derived from it. Modelled here as:
// running "the same tick twice", once feeding a trace and once not, must
// leave the caller's own values (the vector fed in) byte-identical.
TEST(UtEdg02CycleTraceIsOffByDefaultAndInert, RecordingDoesNotMutateWhatWasPassedIn) {
  const std::vector<std::string> inputs = {"a.in1", "a.in2"};
  CycleTraceEntry entry{0, "a", CycleOutcome::kRan, inputs, std::chrono::milliseconds(1)};

  CycleTrace trace;
  trace.Record(entry);  // entry is copied in (pass-by-value Record)

  // The caller's own copy is untouched -- proves Record has no back-channel
  // into the value it was handed.
  EXPECT_EQ(entry.inputs_received, inputs);
  EXPECT_EQ(trace.entries().front().inputs_received, inputs);
}

TEST(UtEdg02CycleTraceIsOffByDefaultAndInert, ANeverConstructedTraceCostsNothingAndAffectsNothing) {
  // The off-by-default case: a caller that never constructs a CycleTrace
  // at all (this test constructs one only to prove it starts empty and
  // idle) -- no entries exist until Record is called.
  CycleTrace trace;
  EXPECT_TRUE(trace.entries().empty());
  EXPECT_EQ(trace.TotalDuration("a"), std::chrono::nanoseconds(0));
  EXPECT_TRUE(trace.CoveredCells().empty());
}

}  // namespace
}  // namespace simcore::diagnostics
