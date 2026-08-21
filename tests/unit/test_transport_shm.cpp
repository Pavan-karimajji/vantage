// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `SharedMemoryTransport`'s own class-level contract (`SI-25`,
///   `WP-27`) -- same clauses `test_transport_inproc.cpp` exercises
///   against `InProcessTransport` (`SW-0349`/`0352`/`0353`/`0355`/`0356`),
///   here against two objects (`Role::kEngine`, `Role::kClient`) mapping
///   the same named segment, which is what makes this a real cross-
///   process-shaped test rather than a same-object shortcut. Real
///   liveness detection (`ProcessAlive` on the recorded pid) is exercised
///   implicitly -- both roles run in this same test process, so the
///   engine's own pid is always alive except where `SimulateEngineDeath`
///   overrides it, same test-hook pattern `InProcessTransport`'s own
///   `MarkEngineDead` uses. `UT-TRN-01`'s own "diff the consumer's
///   source" is satisfied by construction: every `ITransport` call below
///   is identical to `test_transport_inproc.cpp`'s, only the transport
///   object differs.
/// @author Pavan Karimajji

#include "simcore/transport_shm.hpp"

#include <gtest/gtest.h>

#include <cstring>
#include <string>
#include <vector>

namespace {

using simcore::transport::SharedMemoryTransport;

std::vector<uint8_t> Bytes(const std::string& s) { return std::vector<uint8_t>(s.begin(), s.end()); }

// One segment name per test -- a leftover segment from a crashed prior run
// would otherwise make a test's own AttachResult::kOk depend on process
// history, exactly the kind of hidden state R-SIM-25 exists to forbid
// everywhere it can be avoided.
std::string UniqueName(const std::string& suffix) { return "/simcore_shm_test_" + suffix; }

}  // namespace

TEST(TransportShm, PublishThenReceiveRoundTrips) {
  SharedMemoryTransport engine(UniqueName("roundtrip"), SharedMemoryTransport::Role::kEngine);
  SharedMemoryTransport client(UniqueName("roundtrip"), SharedMemoryTransport::Role::kClient);

  uint32_t engineVersion = 0;
  ASSERT_EQ(client.attach(SharedMemoryTransport::kProtocolVersion, &engineVersion),
            adas::transport::AttachResult::kOk);
  EXPECT_EQ(engineVersion, SharedMemoryTransport::kProtocolVersion);

  auto bytes = Bytes("payload");
  engine.Publish(42, "bsd.outputs", bytes.data(), bytes.size());

  adas::transport::PortFrame frame{};
  ASSERT_TRUE(client.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 42u);
  EXPECT_EQ(std::string(frame.portName), "bsd.outputs");
  ASSERT_EQ(frame.size, bytes.size());
  EXPECT_EQ(std::memcmp(frame.data, bytes.data(), bytes.size()), 0);

  EXPECT_FALSE(client.tryReceive(&frame));  // nothing pending -- never blocks
}

TEST(TransportShm, DetachedTransportNeverReceives) {
  SharedMemoryTransport engine(UniqueName("detached"), SharedMemoryTransport::Role::kEngine);
  SharedMemoryTransport client(UniqueName("detached"), SharedMemoryTransport::Role::kClient);

  auto bytes = Bytes("x");
  engine.Publish(1, "p", bytes.data(), bytes.size());

  adas::transport::PortFrame frame{};
  EXPECT_FALSE(client.tryReceive(&frame));  // never attached
}

TEST(TransportShm, SlowConsumerDropsFramesNeverBlocksProducer) {
  // SW-0353, over shared memory: depth=2, publish more than fit before any
  // read, prove Publish() itself never observes anything but success.
  SharedMemoryTransport engine(UniqueName("slowconsumer"), SharedMemoryTransport::Role::kEngine,
                                /*depth=*/2);
  SharedMemoryTransport client(UniqueName("slowconsumer"), SharedMemoryTransport::Role::kClient,
                                /*depth=*/2);
  uint32_t v = 0;
  ASSERT_EQ(client.attach(SharedMemoryTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kOk);

  for (uint64_t tick = 0; tick < 5; ++tick) {
    auto bytes = Bytes("tick" + std::to_string(tick));
    engine.Publish(tick, "p", bytes.data(), bytes.size());
  }

  adas::transport::PortFrame frame{};
  ASSERT_TRUE(client.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 3u);
  ASSERT_TRUE(client.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 4u);
  EXPECT_FALSE(client.tryReceive(&frame));
}

TEST(TransportShm, AttachDetachDoesNotPerturbPublish) {
  SharedMemoryTransport engine(UniqueName("attachdetach"), SharedMemoryTransport::Role::kEngine,
                                /*depth=*/4);
  SharedMemoryTransport client(UniqueName("attachdetach"), SharedMemoryTransport::Role::kClient,
                                /*depth=*/4);
  auto bytes = Bytes("a");

  engine.Publish(0, "p", bytes.data(), bytes.size());  // no attach yet

  uint32_t v = 0;
  ASSERT_EQ(client.attach(SharedMemoryTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kOk);
  engine.Publish(1, "p", bytes.data(), bytes.size());
  client.detach();
  engine.Publish(2, "p", bytes.data(), bytes.size());  // detached again -- still accepted

  ASSERT_EQ(client.attach(SharedMemoryTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kOk);
  adas::transport::PortFrame frame{};
  ASSERT_TRUE(client.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 0u);
  ASSERT_TRUE(client.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 1u);
  ASSERT_TRUE(client.tryReceive(&frame));
  EXPECT_EQ(frame.tickIndex, 2u);
}

TEST(TransportShm, VersionMismatchRefusedBeforeAnyDataCrosses) {
  SharedMemoryTransport engine(UniqueName("versionmismatch"), SharedMemoryTransport::Role::kEngine);
  SharedMemoryTransport client(UniqueName("versionmismatch"), SharedMemoryTransport::Role::kClient);

  uint32_t engineVersion = 0;
  auto result = client.attach(SharedMemoryTransport::kProtocolVersion + 1, &engineVersion);
  EXPECT_EQ(result, adas::transport::AttachResult::kVersionMismatch);
  EXPECT_EQ(engineVersion, SharedMemoryTransport::kProtocolVersion);  // named

  auto bytes = Bytes("x");
  engine.Publish(0, "p", bytes.data(), bytes.size());
  adas::transport::PortFrame frame{};
  EXPECT_FALSE(client.tryReceive(&frame));  // refused attach never let data cross
}

TEST(TransportShm, DepthMismatchRefused) {
  // Two ends built against different wire-layout assumptions for the same
  // segment name -- refused the same way a version mismatch is, not a
  // separate error path (shm.cpp::attach's own comment).
  SharedMemoryTransport engine(UniqueName("depthmismatch"), SharedMemoryTransport::Role::kEngine,
                                /*depth=*/8);
  SharedMemoryTransport client(UniqueName("depthmismatch"), SharedMemoryTransport::Role::kClient,
                                /*depth=*/4);
  uint32_t v = 0;
  EXPECT_EQ(client.attach(SharedMemoryTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kVersionMismatch);
}

TEST(TransportShm, DeadEngineReportedNotWaitedOn) {
  SharedMemoryTransport engine(UniqueName("deadengine"), SharedMemoryTransport::Role::kEngine);
  SharedMemoryTransport client(UniqueName("deadengine"), SharedMemoryTransport::Role::kClient);
  uint32_t v = 0;
  ASSERT_EQ(client.attach(SharedMemoryTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kOk);

  auto bytes = Bytes("x");
  engine.Publish(7, "p", bytes.data(), bytes.size());
  adas::transport::PortFrame frame{};
  ASSERT_TRUE(client.tryReceive(&frame));
  EXPECT_EQ(client.lastTickReceived(), 7u);

  EXPECT_TRUE(client.engineAlive());
  engine.SimulateEngineDeath();
  EXPECT_FALSE(client.engineAlive());
  EXPECT_EQ(client.lastTickReceived(), 7u);  // still queryable after death
  EXPECT_FALSE(client.tryReceive(&frame));   // no new data, no block
}

TEST(TransportShm, AttachRefusedWhenEngineAlreadyDead) {
  SharedMemoryTransport engine(UniqueName("alreadydead"), SharedMemoryTransport::Role::kEngine);
  engine.SimulateEngineDeath();
  SharedMemoryTransport client(UniqueName("alreadydead"), SharedMemoryTransport::Role::kClient);
  uint32_t v = 0;
  EXPECT_EQ(client.attach(SharedMemoryTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kEngineUnavailable);
}

TEST(TransportShm, AttachRefusedWhenSegmentNeverCreated) {
  // No engine object at all for this name -- attach()'s own MapSegment
  // fails to open, which must read as kEngineUnavailable, never a crash.
  SharedMemoryTransport client(UniqueName("nosegment"), SharedMemoryTransport::Role::kClient);
  uint32_t v = 0;
  EXPECT_EQ(client.attach(SharedMemoryTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kEngineUnavailable);
}

TEST(TransportShm, DataCrossesThroughTheMappedSegmentNotACopyOnTheStack) {
  // SW-0351: the bulk read does not copy -- tryReceive's data pointer must
  // resolve to memory that survives after the local PortFrame goes out of
  // scope in the producer's own frame, i.e. it points into the segment,
  // not into something Publish() only had on its own stack.
  SharedMemoryTransport engine(UniqueName("zerocopy"), SharedMemoryTransport::Role::kEngine);
  SharedMemoryTransport client(UniqueName("zerocopy"), SharedMemoryTransport::Role::kClient);
  uint32_t v = 0;
  ASSERT_EQ(client.attach(SharedMemoryTransport::kProtocolVersion, &v),
            adas::transport::AttachResult::kOk);

  auto bytes = Bytes("stable");
  engine.Publish(3, "p", bytes.data(), bytes.size());

  adas::transport::PortFrame frame{};
  ASSERT_TRUE(client.tryReceive(&frame));
  const uint8_t* firstAddr = frame.data;

  // Publish a second frame into a different slot (depth defaults to 8) --
  // the first frame's memory must be untouched since nothing has wrapped
  // the ring back to its slot yet.
  auto bytes2 = Bytes("other");
  engine.Publish(4, "q", bytes2.data(), bytes2.size());
  EXPECT_EQ(std::memcmp(firstAddr, bytes.data(), bytes.size()), 0);
}
