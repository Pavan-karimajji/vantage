// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `InProcessTransport`'s own class-level contract (`SI-25`,
///   `WP-27`). Exercises `SW-0349`/`0352`/`0353`/`0355`/`0356` directly
///   against the object -- the IT-level `UT-TRN-01`..`05` fixtures
///   (`F-STUB`/`F-BULK`/`F-LONG`/`F-STUB-CRASH`, a real component wired
///   through the scheduler) are follow-on work, not attempted here; this
///   file proves the transport itself is correct before anything is wired
///   to it.
/// @author Pavan Karimajji

#include "simcore/transport.hpp"

#include <gtest/gtest.h>

#include <cstring>
#include <string>
#include <vector>

namespace {

std::vector<uint8_t> Bytes(const std::string& s) {
  return std::vector<uint8_t>(s.begin(), s.end());
}

}  // namespace

TEST(TransportInproc, PublishThenReceiveRoundTrips) {
  simcore::transport::InProcessTransport t;
  uint32_t engineVersion = 0;
  ASSERT_EQ(t.attach(simcore::transport::InProcessTransport::kProtocolVersion, &engineVersion),
            adas::transport::AttachResult::kOk);
  EXPECT_EQ(engineVersion, simcore::transport::InProcessTransport::kProtocolVersion);

  auto bytes = Bytes("payload");
  t.Publish(42, "bsd.outputs", bytes.data(), bytes.size());

  adas::transport::PortFrame frame{};
  ASSERT_TRUE(t.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 42u);
  EXPECT_EQ(std::string(frame.portName), "bsd.outputs");
  ASSERT_EQ(frame.size, bytes.size());
  EXPECT_EQ(std::memcmp(frame.data, bytes.data(), bytes.size()), 0);

  // Nothing pending -- a second call finds no frame ready (SW-0353's own
  // non-blocking contract, not just the drop case).
  EXPECT_FALSE(t.tryReceive(&frame));
}

TEST(TransportInproc, DetachedTransportNeverReceives) {
  simcore::transport::InProcessTransport t;
  auto bytes = Bytes("x");
  t.Publish(1, "p", bytes.data(), bytes.size());

  adas::transport::PortFrame frame{};
  EXPECT_FALSE(t.tryReceive(&frame));  // never attached
}

TEST(TransportInproc, SlowConsumerDropsFramesNeverBlocksProducer) {
  // SW-0353: a slow player drops frames and never applies back-pressure.
  // depth=2 -- publish more than fit before any read and prove the
  // producer side (Publish) never observes anything but success.
  simcore::transport::InProcessTransport t(/*depth=*/2);
  uint32_t v = 0;
  ASSERT_EQ(t.attach(simcore::transport::InProcessTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kOk);

  for (uint64_t tick = 0; tick < 5; ++tick) {
    auto bytes = Bytes("tick" + std::to_string(tick));
    t.Publish(tick, "p", bytes.data(), bytes.size());  // never blocks, no return to check
  }

  // Only the last `depth` frames survive -- ticks 3 and 4.
  adas::transport::PortFrame frame{};
  ASSERT_TRUE(t.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 3u);
  ASSERT_TRUE(t.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 4u);
  EXPECT_FALSE(t.tryReceive(&frame));
}

TEST(TransportInproc, AttachDetachDoesNotPerturbPublish) {
  // SW-0352: attaching/detaching shall not alter the engine's execution --
  // Publish() must behave identically (accept every call, same ring state
  // transitions) whether or not a player is attached.
  simcore::transport::InProcessTransport t(/*depth=*/4);
  auto bytes = Bytes("a");

  t.Publish(0, "p", bytes.data(), bytes.size());  // no attach yet

  uint32_t v = 0;
  ASSERT_EQ(t.attach(simcore::transport::InProcessTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kOk);
  t.Publish(1, "p", bytes.data(), bytes.size());
  t.detach();
  t.Publish(2, "p", bytes.data(), bytes.size());  // detached again -- still accepted

  ASSERT_EQ(t.attach(simcore::transport::InProcessTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kOk);
  adas::transport::PortFrame frame{};
  ASSERT_TRUE(t.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 0u);  // all three publishes landed, none lost or perturbed
  ASSERT_TRUE(t.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 1u);
  ASSERT_TRUE(t.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 2u);
}

TEST(TransportInproc, VersionMismatchRefusedBeforeAnyDataCrosses) {
  // SW-0355: an incompatible pair refuses to attach, naming both versions.
  simcore::transport::InProcessTransport t;
  uint32_t engineVersion = 0;
  auto result = t.attach(simcore::transport::InProcessTransport::kProtocolVersion + 1, &engineVersion);
  EXPECT_EQ(result, adas::transport::AttachResult::kVersionMismatch);
  EXPECT_EQ(engineVersion, simcore::transport::InProcessTransport::kProtocolVersion);  // named

  auto bytes = Bytes("x");
  t.Publish(0, "p", bytes.data(), bytes.size());
  adas::transport::PortFrame frame{};
  EXPECT_FALSE(t.tryReceive(&frame));  // refused attach never let data cross
}

TEST(TransportInproc, DeadEngineReportedNotWaitedOn) {
  // SW-0356: the player detects a terminated engine and reports it with
  // the last tick received, rather than blocking.
  simcore::transport::InProcessTransport t;
  uint32_t v = 0;
  ASSERT_EQ(t.attach(simcore::transport::InProcessTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kOk);

  auto bytes = Bytes("x");
  t.Publish(7, "p", bytes.data(), bytes.size());
  adas::transport::PortFrame frame{};
  ASSERT_TRUE(t.tryReceive(&frame));
  EXPECT_EQ(t.lastTickReceived(), 7u);

  EXPECT_TRUE(t.engineAlive());
  t.MarkEngineDead();
  EXPECT_FALSE(t.engineAlive());
  EXPECT_EQ(t.lastTickReceived(), 7u);  // still queryable after death
  EXPECT_FALSE(t.tryReceive(&frame));   // no new data, no block
}

TEST(TransportInproc, AttachRefusedWhenEngineAlreadyDead) {
  simcore::transport::InProcessTransport t;
  t.MarkEngineDead();
  uint32_t v = 0;
  EXPECT_EQ(t.attach(simcore::transport::InProcessTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kEngineUnavailable);
}
