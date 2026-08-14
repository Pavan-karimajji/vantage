// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-BUS-18` (`SW-0060`): a `Static`-kind port has no cycle structure,
///   no hold semantics and no age -- distinct from `Data`/`Control`, which
///   this file also exercises for contrast.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

TEST(UtBus18StaticPortClass, AgeIsNotApplicableNotANumber) {
  PortValue value;
  value.kind = PortKind::Static;
  // No cycle structure and no hold schedule -- exactly the state a static
  // parameter port is in for the whole recording.
  EXPECT_FALSE(value.age_ns().has_value());
  EXPECT_EQ(Format(value.age_ns()), "unknown");
}

TEST(UtBus18StaticPortClass, DataPortOfOtherwiseIdenticalStateHasARealAge) {
  PortValue value;
  value.kind = PortKind::Data;  // the only difference from the test above
  EXPECT_TRUE(value.age_ns().has_value());
  EXPECT_EQ(value.age_ns().value(), 0);
}

TEST(UtBus18StaticPortClass, ThreeDistinctKinds) {
  EXPECT_NE(PortKind::Data, PortKind::Static);
  EXPECT_NE(PortKind::Control, PortKind::Static);
  EXPECT_NE(PortKind::Data, PortKind::Control);
  EXPECT_EQ(ToString(PortKind::Static), "static");
}

}  // namespace
}  // namespace simcore::bus
