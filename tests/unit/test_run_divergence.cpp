// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `EqualOutputs` and `DivergenceLatch::Observe` (`IMP-0032`, `IMP-0033`,
///   `WP-06`; serve `SYS-0036`, `SYS-0043`..`SYS-0045`): two outputs differing
///   only in `cycle_counter` are equal, a `refSync` is compared only on each
///   entry's `measurement_counter` and `source_timestamp_us`, every other byte
///   is compared exactly, and the latch keeps the first step that differs. The
///   Runner side (a RESTART run never observed, the entry logged once, warming
///   up ending at the first equal output) is in `test_run_step.cpp`. The system
///   tests `SYT-EQO-02`..`SYT-EQO-04` and `SYT-STP-05` run over a lab case in
///   `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <cstdint>
#include <vector>

#include "common/cycle_control.pb.h"
#include "common/ref_sync.pb.h"
#include "run_fixtures.hpp"
#include "simcore/runner.hpp"

namespace simcore::runner {
namespace {

using adas::common::CycleControl;
using adas::common::RefSync;
using testing::Data;

template <class M>
std::vector<std::uint8_t> Bytes(const M& message) {
  std::vector<std::uint8_t> bytes(static_cast<std::size_t>(message.ByteSizeLong()));
  if (!bytes.empty()) message.SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
  return bytes;
}

const google::protobuf::Descriptor* DataType() { return CycleControl::descriptor(); }
const google::protobuf::Descriptor* RefSyncType() { return RefSync::descriptor(); }

// A refSync with two entries; the tests change one field of a copy.
RefSync BaseRefSync() {
  RefSync message;
  message.mutable_sig_header()->set_measurement_counter(10);
  message.mutable_sig_header()->set_source_timestamp_us(1000);
  message.mutable_sig_header()->set_cycle_counter(4);
  message.mutable_sig_header()->set_sig_status(1);
  for (std::uint32_t i = 0; i < 2; ++i) {
    adas::common::RefSyncEntry* entry = message.add_inputs();
    entry->set_port(i == 0 ? "in" : "other");
    entry->set_measurement_counter(20 + i);
    entry->set_source_timestamp_us(2000 + i);
    entry->set_cycle_counter(30 + i);
    entry->set_sig_status(1);
  }
  return message;
}

// ---- IMP-0032: EqualOutputs --------------------------------------------------------------------------------------
TEST(RunDivergence, TwoOutputsDifferingOnlyInCycleCounterAreEqual) {
  EXPECT_TRUE(EqualOutputs(Data(7, 700, /*cycle=*/1), Data(7, 700, /*cycle=*/9), DataType()));
  EXPECT_TRUE(EqualOutputs(Data(7, 700, 0), Data(7, 700, 0xFFFFFFFFu), DataType()));
}

TEST(RunDivergence, EveryOtherByteOfAnOutputIsComparedExactly) {
  EXPECT_FALSE(EqualOutputs(Data(7, 700, 1), Data(8, 700, 1), DataType()));  // measurement_counter
  EXPECT_FALSE(EqualOutputs(Data(7, 700, 1), Data(7, 701, 1), DataType()));  // source_timestamp_us
  CycleControl other_status;
  other_status.ParseFromArray(Data(7, 700, 1).data(), static_cast<int>(Data(7, 700, 1).size()));
  other_status.mutable_sig_header()->set_sig_status(2);
  EXPECT_FALSE(EqualOutputs(Data(7, 700, 1), Bytes(other_status), DataType()));  // sig_status
  EXPECT_FALSE(EqualOutputs(Data(7, 700, 1, CycleControl::RUN), Data(7, 700, 1, CycleControl::RESTART), DataType()));
}

TEST(RunDivergence, WithoutADescriptorOrWithBytesThatDoNotParseTheBytesDecide) {
  EXPECT_TRUE(EqualOutputs(Data(7, 700, 1), Data(7, 700, 1), nullptr));
  EXPECT_FALSE(EqualOutputs(Data(7, 700, 1), Data(7, 700, 9), nullptr));
  const std::vector<std::uint8_t> garbage = {0xFF, 0xFF, 0xFF};
  EXPECT_TRUE(EqualOutputs(garbage, garbage, DataType()));
  EXPECT_FALSE(EqualOutputs(garbage, Data(7, 700, 1), DataType()));
}

TEST(RunDivergence, ARefSyncDifferingOnlyInAHeaderFieldOtherThanCounterAndTimeIsEqual) {
  const RefSync base = BaseRefSync();
  RefSync other = base;
  other.mutable_sig_header()->set_cycle_counter(99);
  other.mutable_sig_header()->set_sig_status(2);
  other.mutable_sig_header()->set_measurement_counter(11);
  other.mutable_inputs(0)->set_cycle_counter(77);
  other.mutable_inputs(0)->set_sig_status(0);
  other.mutable_inputs(1)->set_port("renamed");
  EXPECT_TRUE(EqualOutputs(Bytes(base), Bytes(other), RefSyncType()));
}

TEST(RunDivergence, ARefSyncDifferingInOneEntrysTimeOrCounterOrInTheEntryCountIsNot) {
  const RefSync base = BaseRefSync();
  RefSync time = base;
  time.mutable_inputs(1)->set_source_timestamp_us(5000);
  EXPECT_FALSE(EqualOutputs(Bytes(base), Bytes(time), RefSyncType()));
  RefSync counter = base;
  counter.mutable_inputs(0)->set_measurement_counter(21);
  EXPECT_FALSE(EqualOutputs(Bytes(base), Bytes(counter), RefSyncType()));
  RefSync fewer = base;
  fewer.mutable_inputs()->RemoveLast();
  EXPECT_FALSE(EqualOutputs(Bytes(base), Bytes(fewer), RefSyncType()));
}

// ---- IMP-0033: DivergenceLatch::Observe --------------------------------------------------------------------------
TEST(RunDivergence, TheLatchKeepsTheFirstStepThatDiffersAndIgnoresAnOutputEqualByEqualOutputs) {
  DivergenceLatch latch;
  // Only the cycle_counter differs: equal outputs, nothing latches.
  latch.Observe(1, 10, "B", "out", Data(7, 700, 1), Data(7, 700, 9), DataType());
  EXPECT_FALSE(latch.latched());
  latch.Observe(2, 20, "B", "out", Data(8, 800, 1), Data(9, 800, 1), DataType());
  ASSERT_TRUE(latch.latched());
  EXPECT_EQ(latch.first()->tick_index, 2u);  // the step
  EXPECT_EQ(latch.first()->stage, "B");
  EXPECT_EQ(latch.first()->port, "out");
  latch.Observe(3, 30, "C", "other", Data(1, 1, 1), Data(2, 1, 1), DataType());  // a later, different divergence
  EXPECT_EQ(latch.first()->tick_index, 2u);
  EXPECT_EQ(latch.first()->stage, "B");
}

}  // namespace
}  // namespace simcore::runner
