// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-BUS-01`/`UT-BUS-02`/`UT-BUS-05`/`UT-BUS-06` (`SW-0043`, `SW-0044`,
///   `SW-0047`, `SW-0048`): the eight-field header, the two-clock rule,
///   the `Unknown<T>` "missing is not zero" discipline, and the closed
///   `Origin` set.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <algorithm>
#include <string>
#include <utility>
#include <vector>

#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

// UT-BUS-01: every one of the eight header fields is present -- as a
// value or an explicit unknown -- and readable back.
TEST(UtBus01EightHeaderFields, AllEightFieldsSetAndReadable) {
  Header header;
  header.t_source_ns = std::int64_t{1'000};
  header.counter = std::uint64_t{7};
  header.status = std::uint32_t{0};
  header.t_capture_ns = std::int64_t{950};
  header.t_sim_ns = 1'020;
  header.producer = "bsd";
  header.mode = Mode::Simulate;
  header.is_repeat = false;

  EXPECT_TRUE(header.t_source_ns.has_value());
  EXPECT_EQ(header.t_source_ns.value(), 1'000);
  EXPECT_TRUE(header.counter.has_value());
  EXPECT_EQ(header.counter.value(), 7u);
  EXPECT_TRUE(header.status.has_value());
  EXPECT_EQ(header.status.value(), 0u);
  EXPECT_TRUE(header.t_capture_ns.has_value());
  EXPECT_EQ(header.t_capture_ns.value(), 950);
  EXPECT_EQ(header.t_sim_ns, 1'020);
  EXPECT_EQ(header.producer, "bsd");
  EXPECT_EQ(header.mode, Mode::Simulate);
  EXPECT_FALSE(header.is_repeat);
}

// UT-BUS-01: a default-constructed header leaves every genuinely-unknown
// field unknown rather than absent-as-zero -- t_sim_ns/producer/mode/
// is_repeat are the four always-known fields (design §5.1) and start at
// their stated defaults.
TEST(UtBus01EightHeaderFields, DefaultHeaderLeavesSourceFieldsUnknown) {
  const Header header;
  EXPECT_FALSE(header.t_source_ns.has_value());
  EXPECT_FALSE(header.counter.has_value());
  EXPECT_FALSE(header.status.has_value());
  EXPECT_FALSE(header.t_capture_ns.has_value());
  EXPECT_EQ(header.t_sim_ns, 0);
  EXPECT_EQ(header.mode, Mode::Off);
  EXPECT_FALSE(header.is_repeat);
}

// UT-BUS-02: a message carrying a capture stamp is representable...
TEST(UtBus02TwoClocks, CaptureStampWhenThePayloadCarriesOne) {
  Header header;
  header.t_capture_ns = std::int64_t{4'200};
  EXPECT_TRUE(header.t_capture_ns.has_value());
  EXPECT_EQ(header.t_capture_ns.value(), 4'200);
}

// UT-BUS-02: ...and one without stays explicitly unknown -- constructing a
// header from a message's reception time alone (t_sim_ns, this port
// value's own delivery cycle) never populates t_capture_ns. `Header` is an
// aggregate with no constructor that could perform that collapse: naming
// t_sim_ns and leaving t_capture_ns unnamed is the only way to write this,
// which is what makes the defaulting SW-0044 forbids unwritable rather
// than merely discouraged.
TEST(UtBus02TwoClocks, NoConstructorDefaultsCaptureFromReception) {
  constexpr std::int64_t kReceptionNs = 8'675'309;
  Header header;
  header.t_sim_ns = kReceptionNs;  // reception/delivery time -- NOT capture
  EXPECT_FALSE(header.t_capture_ns.has_value());
  EXPECT_NE(header.t_sim_ns, 0);  // sanity: the field we did set really is set
}

// UT-BUS-05: an absent field formats as "unknown", never a zero.
TEST(UtBus05MissingIsNotZero, AbsentStatusFormatsAsUnknown) {
  const Unknown<std::uint32_t> status;
  EXPECT_FALSE(status.has_value());
  EXPECT_EQ(Format(status), "unknown");
}

// UT-BUS-05: a known zero is distinguishable from unknown -- both by
// has_value() and by its formatted text.
TEST(UtBus05MissingIsNotZero, KnownZeroIsNotUnknown) {
  const Unknown<std::uint32_t> status(0);
  EXPECT_TRUE(status.has_value());
  EXPECT_EQ(status.value(), 0u);
  EXPECT_EQ(Format(status), "0");
}

// UT-BUS-05: "attempt arithmetic on it" -- the one door left open is
// `.value()`, and it refuses on an absent field rather than handing back a
// plausible-looking zero for a caller to do arithmetic with.
TEST(UtBus05MissingIsNotZero, ValueThrowsOnAnAbsentField) {
  const Unknown<std::int64_t> t_source_ns;
  EXPECT_THROW(t_source_ns.value(), std::logic_error);
}

// UT-BUS-06: one value per origin tag, enumerated -- the closed set is
// exactly six (ANL-SW-15 keeps this in parity with the published schema).
TEST(UtBus06OriginClosedSet, EverySixOriginsFormatDistinctly) {
  const std::vector<std::pair<Origin, std::string>> expected = {
      {Origin::Measured, "measured"},     {Origin::Truth, "truth"},
      {Origin::Mocked, "mocked"},         {Origin::Simulated, "simulated"},
      {Origin::Overridden, "overridden"}, {Origin::Unknown, "unknown"},
  };
  ASSERT_EQ(expected.size(), 6u);
  std::vector<std::string> seen;
  for (const auto& [origin, text] : expected) {
    EXPECT_EQ(ToString(origin), text);
    seen.push_back(ToString(origin));
  }
  std::sort(seen.begin(), seen.end());
  EXPECT_EQ(std::adjacent_find(seen.begin(), seen.end()), seen.end()) << "an origin tag collided with another";
}

}  // namespace
}  // namespace simcore::bus
