// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-BUS-03` (`SW-0045`): `PortValue::age_ns()` is derived -- capture
///   time when known, else the hold schedule, else a genuine known zero --
///   and is a method, never a stored field: nothing in this file ever
///   assigns to it, only calls it.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <cstdint>
#include <vector>

#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

TEST(UtBus03DerivedAge, CaptureKnownDerivesFromTheTwoStamps) {
  PortValue value;
  value.header.t_sim_ns = 1'000;
  value.header.t_capture_ns = std::int64_t{600};

  const auto age = value.age_ns();
  ASSERT_TRUE(age.has_value());
  EXPECT_EQ(age.value(), 400);

  // SW-0045's Accept: "changing a timestamp changes the age" -- age is
  // never cached, so a later mutation is reflected on the next call.
  value.header.t_sim_ns = 1'500;
  EXPECT_EQ(value.age_ns().value(), 900);
}

TEST(UtBus03DerivedAge, HeldAcrossSeveralTicksReadsTheHoldScheduleEachTime) {
  PortValue value;  // no capture stamp on this path -- a held, framework-produced value
  ASSERT_FALSE(value.header.t_capture_ns.has_value());

  const std::vector<std::int64_t> hold_schedule = {20'000, 40'000, 60'000};
  for (const std::int64_t hold_ns : hold_schedule) {
    value.hold_ns = hold_ns;
    const auto age = value.age_ns();
    ASSERT_TRUE(age.has_value());
    EXPECT_EQ(age.value(), hold_ns);
  }
}

TEST(UtBus03DerivedAge, UpdatedThisTickWithNoScheduleIsAKnownZero) {
  PortValue value;  // fresh: no capture stamp, no hold schedule yet
  const auto age = value.age_ns();
  ASSERT_TRUE(age.has_value());  // a genuine answer, distinct from "not applicable"
  EXPECT_EQ(age.value(), 0);
}

TEST(UtBus03DerivedAge, StaticPortAgeIsNotApplicableRegardlessOfCaptureOrHold) {
  PortValue value;
  value.kind = PortKind::Static;
  value.header.t_capture_ns = std::int64_t{600};  // even with a capture stamp present...
  value.header.t_sim_ns = 1'000;
  EXPECT_FALSE(value.age_ns().has_value());  // ...a Static port's age is "not applicable", not a number
}

}  // namespace
}  // namespace simcore::bus
