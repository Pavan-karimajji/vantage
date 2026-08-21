// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `UT-SCH-01`/`02`/`04`/`09`/`13` (`WP-09`, `SI-03` `scheduler`):
///   `Scheduler`'s core -- one execution path, integer due-ness, the
///   module-flag reconciliation, the consumed (never recomputed)
///   execution order, and simulation time as the grid-step arithmetic
///   sequence.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "simcore/scheduler.hpp"

namespace simcore::scheduler {
namespace {

RunSpec MakeSpec(std::int64_t grid_step_ns, std::vector<std::pair<std::string, std::int64_t>> stages) {
  RunSpec spec;
  spec.grid_step_ns = grid_step_ns;
  for (const auto& [name, period_ns] : stages) {
    SpecStage stage;
    stage.name = name;
    stage.period_ns = period_ns;
    spec.stages.push_back(stage);
    spec.order.push_back(name);
  }
  return spec;
}

// UT-SCH-01: `IsDue`/`Advance` are the only functions deciding a module
// executes -- enumerated here as the two calls every due-ness question in
// this suite goes through; no second per-cycle execution route exists in
// this class (a grep over scheduler/*.cpp finding no other Advance/IsDue
// pair is `ANL-SW-17`'s own mechanised half, not attempted in this test).
TEST(UtSch01OneExecutionPath, DueDecisionGoesThroughIsDueAlone) {
  RunSpec spec = MakeSpec(10'000'000, {{"a", 30'000'000}});
  Scheduler sched(spec);
  sched.Advance();  // now_ns = 10ms
  EXPECT_FALSE(sched.IsDue("a"));
  sched.Advance();  // 20ms
  EXPECT_FALSE(sched.IsDue("a"));
  sched.Advance();  // 30ms
  EXPECT_TRUE(sched.IsDue("a"));
}

// UT-SCH-02: 60s on a 10ms grid with a 30ms module -- fired ticks match
// the expected set exactly, integer arithmetic only (no float/epsilon
// anywhere in IsDue/Advance).
TEST(UtSch02IntegerDueNess, ThirtyMsModuleFiresOnExactlyTheExpectedTicksOverSixtySeconds) {
  RunSpec spec = MakeSpec(10'000'000, {{"a", 30'000'000}});
  Scheduler sched(spec);
  std::vector<std::int64_t> firedAtNs;
  const std::int64_t totalTicks = 60'000'000'000LL / 10'000'000LL;  // 6000 ticks over 60s
  for (std::int64_t i = 0; i < totalTicks; ++i) {
    sched.Advance();
    if (sched.IsDue("a")) {
      firedAtNs.push_back(sched.now_ns());
    }
  }
  ASSERT_FALSE(firedAtNs.empty());
  for (std::int64_t t : firedAtNs) {
    EXPECT_EQ(t % 30'000'000, 0);  // every fire is an exact multiple of 30ms, zero drift
  }
  EXPECT_EQ(firedAtNs.size(), static_cast<std::size_t>(60'000'000'000LL / 30'000'000LL));
}

TEST(UtSch02IntegerDueNess, ZeroPeriodStageIsAlwaysDue) {
  RunSpec spec = MakeSpec(10'000'000, {{"aperiodic", 0}});
  Scheduler sched(spec);
  for (int i = 0; i < 5; ++i) {
    sched.Advance();
    EXPECT_TRUE(sched.IsDue("aperiodic"));
  }
}

// UT-SCH-04: a stub whose internal gating has drifted from its declared
// period -- read the finding, never a silent value; agreement produces no
// finding at all.
TEST(UtSch04ModuleFlagAuthoritative, DisagreementProducesANamedFinding) {
  RunSpec spec = MakeSpec(10'000'000, {{"a", 30'000'000}});
  Scheduler sched(spec);
  sched.Advance();  // 10ms -- not due
  auto finding = sched.ReconcileModuleFlag("a", /*reported_updated=*/true);  // module ran anyway
  ASSERT_TRUE(finding.has_value());
  EXPECT_EQ(finding->stage, "a");
  EXPECT_FALSE(finding->predicted_due);
  EXPECT_TRUE(finding->reported_updated);
}

TEST(UtSch04ModuleFlagAuthoritative, AgreementProducesNoFinding) {
  RunSpec spec = MakeSpec(10'000'000, {{"a", 30'000'000}});
  Scheduler sched(spec);
  sched.Advance();
  sched.Advance();
  sched.Advance();  // 30ms -- due
  EXPECT_FALSE(sched.ReconcileModuleFlag("a", /*reported_updated=*/true).has_value());
}

// UT-SCH-09: run one spec twice; compare the order -- identical, because
// it is read once from RunSpec::order, never recomputed from container
// iteration.
TEST(UtSch09StableOrder, OrderIsIdenticalAcrossTwoInstancesOfTheSameSpec) {
  RunSpec spec = MakeSpec(10'000'000, {{"c", 10'000'000}, {"a", 10'000'000}, {"b", 10'000'000}});
  Scheduler first(spec);
  Scheduler second(spec);
  EXPECT_EQ(first.Order(), second.Order());
  ASSERT_EQ(first.Order().size(), 3u);
  EXPECT_EQ(first.Order()[0], "c");  // spec's own declared order, not sorted/reordered
  EXPECT_EQ(first.Order()[1], "a");
  EXPECT_EQ(first.Order()[2], "b");
}

// UT-SCH-13: simulation time is the arithmetic sequence the grid step
// defines, regardless of any recording's own message density -- this
// class never reads one, so the sequence is trivially uniform, which is
// exactly SW-0413's own point (contrasted with SW-0049's identical defect
// seen from the recording side).
TEST(UtSch13SimTimeIsArithmeticSequence, TickSequenceIsUniformRegardlessOfAnythingElse) {
  RunSpec spec = MakeSpec(20'000'000, {});
  Scheduler sched(spec);
  for (std::uint64_t i = 1; i <= 10; ++i) {
    sched.Advance();
    EXPECT_EQ(sched.now_ns(), static_cast<std::int64_t>(i) * 20'000'000);
    EXPECT_EQ(sched.tick_index(), i);
  }
}

}  // namespace
}  // namespace simcore::scheduler
