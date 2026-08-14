// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-BUS-17` (`SW-0059`): a bulk array is carried as a reference
///   {topic, log_time_ns, bytes} that stays under a declared budget, never
///   copied into a tick structure.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

TEST(UtBus17BulkArraysAreReferenced, PortValueCarriesAReferenceNotThePayload) {
  PortValue value;
  value.bulk.topic = "lidar/points";
  value.bulk.log_time_ns = 123'456;
  value.bulk.bytes = 4 * 1024 * 1024;  // a real point cloud's actual size
  value.bulk.present = true;

  // The reference itself -- not the 4 MiB it describes -- is what must
  // stay small. Asserting on BulkRef's own size, not PortValue's, is the
  // point: PortValue also carries a raw-bytes `payload` for the small,
  // structured side of a port, which this budget does not govern.
  EXPECT_LE(sizeof(BulkRef), kBulkRefBudgetBytes);
  EXPECT_EQ(value.bulk.bytes, 4 * 1024 * 1024);  // the recording knows the real size; the reference just names it
}

TEST(UtBus17BulkArraysAreReferenced, ReferenceUnderBudgetPasses) {
  const auto result = CheckBulkBudget("lidar.points", kBulkRefBudgetBytes);
  EXPECT_TRUE(result.ok());
}

TEST(UtBus17BulkArraysAreReferenced, ExceedingTheBudgetNamesThePort) {
  const auto result = CheckBulkBudget("lidar.points", kBulkRefBudgetBytes + 1);
  ASSERT_FALSE(result.ok());
  EXPECT_EQ(result.error().kind, Kind::Authoring);
  EXPECT_NE(result.error().Format().find("lidar.points"), std::string::npos);
}

}  // namespace
}  // namespace simcore::bus
