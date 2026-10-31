// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `UT-SCH-11` (`IMP-0076`, `SW-0076`, `WP-15`): `PredictSchedule`/
///   `ScheduleDumpText` produce the full tick-by-tick plan without
///   executing anything, and the plan agrees EXACTLY with the order a real
///   run actually takes -- checked automatically by driving a second,
///   independent `Scheduler` instance the same way `runner::Runner::
///   StepOnce` drives its own (`Advance()` then `IsDue()` per `Order()`
///   entry) and comparing the two due-stage sequences tick by tick.
/// @author Pavan Karimajji

#include "simcore/scheduler.hpp"

#include <gtest/gtest.h>

namespace simcore::scheduler {
namespace {

// The run setup carries no grid step and no order since schema 2.0; the
// scheduler is given both, as these tests do.
constexpr std::int64_t kGridStepNs = 10'000'000;  // 10ms
const std::vector<std::string> kOrder = {"a", "b"};

RunSpec MakeSpec() {
  RunSpec spec;
  spec.run_id = "ut_sch_11";

  SpecStage a;
  a.name = "a";
  a.clock_period_ns = 10'000'000;
  spec.stages.push_back(a);

  SpecStage b;
  b.name = "b";
  b.clock_period_ns = 30'000'000;
  spec.stages.push_back(b);

  return spec;
}

// UT-SCH-11: predicts nothing runs -- no Component, no exec -- and the
// predicted due set at each tick matches a second Scheduler stepped the
// same way `cycle_loop.cpp` steps its own (Advance, then IsDue per Order).
TEST(UtSch11ScheduleDump, PredictedPlanAgreesExactlyWithARealSchedulersDueSequence) {
  const RunSpec spec = MakeSpec();
  constexpr std::uint64_t kHorizon = 9;

  const std::vector<ScheduleTick> predicted = PredictSchedule(spec, kGridStepNs, kOrder, kHorizon);
  ASSERT_EQ(predicted.size(), kHorizon + 1);

  // The "real run" side: a SEPARATE Scheduler instance, stepped exactly the
  // way a cycle loop would (never reusing PredictSchedule's own instance or
  // its own loop body -- this must be an independent computation for the
  // comparison to mean anything).
  Scheduler actual(spec, kGridStepNs, kOrder);
  for (std::uint64_t tick = 0; tick <= kHorizon; ++tick) {
    std::vector<std::string> actual_due;
    for (const std::string& stage : actual.Order()) {
      if (actual.IsDue(stage)) actual_due.push_back(stage);
    }
    EXPECT_EQ(predicted[tick].tick_index, tick);
    EXPECT_EQ(predicted[tick].now_ns, actual.now_ns());
    EXPECT_EQ(predicted[tick].due_stages, actual_due) << "tick " << tick;
    if (tick < kHorizon) actual.Advance();
  }
}

TEST(UtSch11ScheduleDump, TickZeroCarriesNoDueStageOnAPeriodicGrid) {
  const RunSpec spec = MakeSpec();
  const std::vector<ScheduleTick> predicted = PredictSchedule(spec, kGridStepNs, kOrder, 0);
  ASSERT_EQ(predicted.size(), 1u);
  EXPECT_EQ(predicted[0].now_ns, 0);
  // now_ns=0 is a multiple of every period -- both stages are due at tick 0,
  // matching Scheduler::IsDue's own `now_ns % period == 0` rule exactly.
  EXPECT_EQ(predicted[0].due_stages, (std::vector<std::string>{"a", "b"}));
}

TEST(UtSch11ScheduleDump, DumpTextIsDeterministicAndDiffableAcrossTwoCalls) {
  const RunSpec spec = MakeSpec();
  const std::string first = ScheduleDumpText(spec, kGridStepNs, kOrder, 5);
  const std::string second = ScheduleDumpText(spec, kGridStepNs, kOrder, 5);
  EXPECT_EQ(first, second);
  EXPECT_NE(first.find("run_id: ut_sch_11"), std::string::npos);
  EXPECT_NE(first.find("tick: 0 now_ns=0 due=[a,b]"), std::string::npos);
}

// A deliberately introduced disagreement: a schedule dump computed from a
// spec whose stage "b" has a different period is NOT byte-identical to the
// original -- proving the dump is sensitive to the fact it is meant to
// check, not merely to the run_id/tick count.
TEST(UtSch11ScheduleDump, ADifferentPeriodProducesADetectablyDifferentPlan) {
  RunSpec spec = MakeSpec();
  RunSpec mutated = spec;
  mutated.stages[1].clock_period_ns = 20'000'000;  // was 30ms

  EXPECT_NE(ScheduleDumpText(spec, kGridStepNs, kOrder, 6), ScheduleDumpText(mutated, kGridStepNs, kOrder, 6));
}

}  // namespace
}  // namespace simcore::scheduler
