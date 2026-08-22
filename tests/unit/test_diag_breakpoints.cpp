// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `UT-EDG-07` (`IMP-0138`, `WP-15`): each of the four break-
///   condition kinds -- cycle index, time, module entry, port predicate --
///   halts at exactly the correct point, exercised as a real driven loop
///   (not a single call), so "halts at the correct point" means "and not
///   one tick early or late".
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <gtest/gtest.h>

namespace simcore::diagnostics {
namespace {

TEST(UtEdg07Breakpoints, HaltsAtCycleAndNoOtherTick) {
  BreakCondition condition;
  condition.at_cycle = 3;

  std::optional<std::uint64_t> hit;
  for (std::uint64_t tick = 0; tick <= 10; ++tick) {
    if (CheckCycle(condition, tick)) {
      hit = tick;
      break;
    }
  }
  ASSERT_TRUE(hit.has_value());
  EXPECT_EQ(*hit, 3u);
}

TEST(UtEdg07Breakpoints, HaltsAtTimeAndNoOtherTime) {
  BreakCondition condition;
  condition.at_time_ns = 50'000'000;

  std::optional<std::int64_t> hit;
  for (std::int64_t now_ns = 0; now_ns <= 100'000'000; now_ns += 10'000'000) {
    if (CheckTime(condition, now_ns)) {
      hit = now_ns;
      break;
    }
  }
  ASSERT_TRUE(hit.has_value());
  EXPECT_EQ(*hit, 50'000'000);
}

TEST(UtEdg07Breakpoints, HaltsOnEntryToTheNamedModuleOnly) {
  BreakCondition condition;
  condition.on_module_entry = "b";

  const std::vector<std::string> order = {"a", "b", "c"};
  std::optional<std::string> hit;
  for (const std::string& stage : order) {
    if (CheckModuleEntry(condition, stage)) {
      hit = stage;
      break;
    }
  }
  ASSERT_TRUE(hit.has_value());
  EXPECT_EQ(*hit, "b");
}

TEST(UtEdg07Breakpoints, HaltsWhenAPortSatisfiesADeclaredComparison) {
  BreakCondition condition;
  condition.on_port = BreakCondition::PortCheck{"a.out", Comparator::kGe, 100.0};

  EXPECT_FALSE(CheckPortLength(condition, "a.out", 50));
  EXPECT_FALSE(CheckPortLength(condition, "a.out", 99));
  EXPECT_TRUE(CheckPortLength(condition, "a.out", 100));
  EXPECT_TRUE(CheckPortLength(condition, "a.out", 200));
  // A different port never matches, regardless of its length.
  EXPECT_FALSE(CheckPortLength(condition, "b.out", 500));
}

TEST(UtEdg07Breakpoints, ComparatorSetIsClosedAndEachValueBehavesCorrectly) {
  EXPECT_TRUE(CompareLiteral(Comparator::kEq, 5.0, 5.0));
  EXPECT_FALSE(CompareLiteral(Comparator::kEq, 5.0, 6.0));
  EXPECT_TRUE(CompareLiteral(Comparator::kNe, 5.0, 6.0));
  EXPECT_TRUE(CompareLiteral(Comparator::kLt, 4.0, 5.0));
  EXPECT_TRUE(CompareLiteral(Comparator::kGt, 6.0, 5.0));
  EXPECT_TRUE(CompareLiteral(Comparator::kLe, 5.0, 5.0));
  EXPECT_TRUE(CompareLiteral(Comparator::kGe, 5.0, 5.0));
}

}  // namespace
}  // namespace simcore::diagnostics
