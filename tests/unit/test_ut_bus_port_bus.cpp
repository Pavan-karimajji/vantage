// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `UT-BUS-14`/`UT-BUS-15`/`UT-BUS-16` (`WP-09`, `SI-02` `bus`):
///   `PortBus`'s held-value hold semantics, always-full port set and
///   buffer-reuse/budget accounting.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

PortValue MakeValue(std::vector<std::uint8_t> payload) {
  PortValue value;
  value.payload = std::move(payload);
  return value;
}

// UT-BUS-14: read a not-due producer's port at several ticks; inspect
// value, updated and age.
TEST(UtBusPortBus14, HeldValueReportsExactElapsedNanoseconds) {
  PortBus bus;
  bus.DeclarePort("p", 1, nullptr);
  ASSERT_TRUE(bus.Publish("p", MakeValue({1, 2, 3}), /*now_ns=*/1000).ok());

  PortValue fresh = bus.Get("p", 1000);
  EXPECT_TRUE(fresh.updated);
  EXPECT_EQ(fresh.hold_ns.value(), 0);

  PortValue held = bus.Get("p", 4000);
  EXPECT_FALSE(held.updated);
  EXPECT_EQ(held.hold_ns.value(), 3000);
  EXPECT_EQ(held.payload, (std::vector<std::uint8_t>{1, 2, 3}));  // the last real value, not a gap

  PortValue heldLater = bus.Get("p", 9000);
  EXPECT_FALSE(heldLater.updated);
  EXPECT_EQ(heldLater.hold_ns.value(), 8000);
}

TEST(UtBusPortBus14, NeverPublishedPortIsUnknownNeverAbsent) {
  PortBus bus;
  PortValue v = bus.Get("never", 500);
  EXPECT_FALSE(v.updated);
  EXPECT_EQ(v.origin, Origin::Unknown);
  EXPECT_EQ(v.port, "never");
}

// UT-BUS-15: build a stage's port set with its producer simulate, then
// measured, then off; compare the sets -- SetFor's own invariant is that
// the RETURNED SET is identical regardless (byte-identical port names and
// count), only the values behind them differ by what was Published.
TEST(UtBusPortBus15, SetForReturnsTheFullDeclaredSetRegardlessOfMode) {
  PortBus bus;
  std::vector<PortId> declared = {"a", "b", "c"};
  for (const PortId& port : declared) bus.DeclarePort(port, 1, nullptr);

  // "simulate": all three published this tick.
  bus.Publish("a", MakeValue({1}), 100);
  bus.Publish("b", MakeValue({2}), 100);
  bus.Publish("c", MakeValue({3}), 100);
  auto simulateSet = bus.SetFor(declared, 100);
  ASSERT_EQ(simulateSet.size(), 3u);

  // "measured": nothing published this tick (an external injector would
  // publish under a real integration; here the set must still be the
  // same three ports, now held).
  auto measuredSet = bus.SetFor(declared, 200);
  ASSERT_EQ(measuredSet.size(), 3u);
  for (std::size_t i = 0; i < declared.size(); ++i) {
    EXPECT_EQ(simulateSet[i].port, measuredSet[i].port);  // same port set, same order
  }

  // "off": still the same declared set -- SW-0057's own "regardless of
  // any producer's due-ness or mode".
  auto offSet = bus.SetFor(declared, 300);
  ASSERT_EQ(offSet.size(), 3u);
  for (std::size_t i = 0; i < declared.size(); ++i) {
    EXPECT_EQ(simulateSet[i].port, offSet[i].port);
  }
}

// UT-BUS-16: run past the buffer count; read reuse count and high-water
// bytes; read a view taken before reuse.
TEST(UtBusPortBus16, ReuseCountAndHighWaterBytesAreTracked) {
  PortBus bus;
  bus.DeclarePort("p", 1, nullptr);
  ASSERT_TRUE(bus.Publish("p", MakeValue({1, 2, 3, 4}), 0).ok());
  PortValue firstView = bus.Get("p", 0);  // taken before the next Publish reuses the buffer
  EXPECT_EQ(firstView.payload, (std::vector<std::uint8_t>{1, 2, 3, 4}));

  // Same size -- fits inside the existing capacity, counted as a reuse.
  ASSERT_TRUE(bus.Publish("p", MakeValue({5, 6, 7, 8}), 1000).ok());
  EXPECT_EQ(bus.Stats().reuse_count, 1u);
  // The earlier view is unaffected -- PortValue owns its own copy.
  EXPECT_EQ(firstView.payload, (std::vector<std::uint8_t>{1, 2, 3, 4}));

  EXPECT_GE(bus.Stats().high_water_bytes, 4u);
}

TEST(UtBusPortBus16, ExceedingTheDeclaredBudgetIsRefusedNamingThePort) {
  PortBus bus(/*byte_budget=*/4);
  bus.DeclarePort("small", 1, nullptr);
  bus.DeclarePort("big", 1, nullptr);
  ASSERT_TRUE(bus.Publish("small", MakeValue({1, 2}), 0).ok());
  auto result = bus.Publish("big", MakeValue({1, 2, 3, 4, 5}), 0);
  ASSERT_FALSE(result.ok());
  EXPECT_EQ(result.error().kind, Kind::Contract);
  EXPECT_EQ(result.error().where, "big");
}

// `WP-05`: declaration is mandatory -- a sample for a port nobody declared is
// refused, naming the port, and no buffer appears for it.
TEST(UtBusPortBus17, PublishingAnUndeclaredPortIsRefusedNamingIt) {
  PortBus bus;
  auto result = bus.Publish("ghost", MakeValue({1}), 0);
  ASSERT_FALSE(result.ok());
  EXPECT_EQ(result.error().kind, Kind::Contract);
  EXPECT_NE(result.error().found.find("ghost"), std::string::npos);
  EXPECT_EQ(bus.Buffer("ghost"), nullptr);
}

}  // namespace
}  // namespace simcore::bus
