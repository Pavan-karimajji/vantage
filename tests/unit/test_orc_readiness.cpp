// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `Readiness::Park`, `Retry`, `Expired` (`WP-04`, `IMP-0022`): steps are
///   counted from the step a ticket was first parked, the limit is reached at
///   exactly that many steps (not one early, not one late), a limit of 0 means
///   a run never waits, and a sample found at any time wins over the limit.
///   The system tests `SYT-ORC-07` and `SYT-SEL-09` are built in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {
namespace {

TEST(OrcReadiness, ALimitOfThreeExpiresAtExactlyThreeStepsWaited) {
  Readiness readiness(3);
  readiness.Park(1, 10);
  EXPECT_FALSE(readiness.Expired(1, 10));
  EXPECT_FALSE(readiness.Expired(1, 12));  // two steps waited
  EXPECT_TRUE(readiness.Expired(1, 13));   // the third
  EXPECT_TRUE(readiness.Expired(1, 14));
  EXPECT_EQ(readiness.Waited(1, 13), 3u);
}

TEST(OrcReadiness, ALimitOfZeroExpiresTheMomentATicketIsParked) {
  Readiness readiness(0);
  readiness.Park(1, 5);
  EXPECT_TRUE(readiness.Expired(1, 5));
  EXPECT_EQ(readiness.Retry(1, 5, /*sample_found=*/false), Readiness::Verdict::kExpired);
}

TEST(OrcReadiness, ALimitOfOneWaitsOneStepNotZero) {
  Readiness readiness(1);
  readiness.Park(1, 5);
  EXPECT_EQ(readiness.Retry(1, 5, false), Readiness::Verdict::kWaiting);  // same step: still waiting
  EXPECT_EQ(readiness.Retry(1, 6, false), Readiness::Verdict::kExpired);
}

TEST(OrcReadiness, ParkingAgainKeepsTheFirstStep) {
  Readiness readiness(2);
  readiness.Park(1, 4);
  readiness.Park(1, 9);  // a naive overwrite would restart the wait
  EXPECT_EQ(readiness.Waited(1, 9), 5u);
  EXPECT_TRUE(readiness.Expired(1, 6));
}

TEST(OrcReadiness, AFoundSampleWinsAndUnparks) {
  Readiness readiness(2);
  readiness.Park(1, 4);
  EXPECT_EQ(readiness.Retry(1, 5, false), Readiness::Verdict::kWaiting);
  EXPECT_EQ(readiness.Retry(1, 5, true), Readiness::Verdict::kReady);
  EXPECT_FALSE(readiness.IsParked(1));
  EXPECT_EQ(readiness.ParkedCount(), 0u);
}

TEST(OrcReadiness, AFoundSampleBeatsAnExpiredLimit) {
  Readiness readiness(1);
  readiness.Park(1, 4);
  EXPECT_EQ(readiness.Retry(1, 20, true), Readiness::Verdict::kReady);  // not kExpired
}

TEST(OrcReadiness, ExpiredUnparksAndATicketNeverParkedIsNotExpired) {
  Readiness readiness(1);
  readiness.Park(1, 4);
  EXPECT_EQ(readiness.Retry(1, 5, false), Readiness::Verdict::kExpired);
  EXPECT_FALSE(readiness.IsParked(1));
  EXPECT_FALSE(readiness.Expired(99, 100));
}

TEST(OrcReadiness, ClearForgetsEveryParkedTicket) {
  Readiness readiness(1);
  readiness.Park(1, 1);
  readiness.Park(2, 1);
  EXPECT_EQ(readiness.ParkedIds().size(), 2u);
  readiness.Clear();
  EXPECT_EQ(readiness.ParkedCount(), 0u);
}

}  // namespace
}  // namespace simcore::orchestrator
