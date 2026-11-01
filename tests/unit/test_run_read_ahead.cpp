// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `ReadAhead` and `RecordedReference` (`IMP-0026`, `WP-05`): every
///   `sources[]` file read through `ReadRange` and merged by reception time
///   then `sources[]` order, as far as asked past the first instant; `Find`
///   by `measurement_counter`; a seek; the byte counter. The system tests
///   `SYT-RUN-05` and `SYT-ORC-07` run over a lab case in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "common/cycle_control.pb.h"
#include "run_fixtures.hpp"
#include "simcore/runner.hpp"

namespace simcore::runner {
namespace {

using testing::Data;
using testing::Message;
using testing::Topic;
using testing::VectorReader;

const google::protobuf::Descriptor* DataType() { return adas::common::CycleControl::descriptor(); }

TEST(RunReadAhead, TwoFilesAreMergedByReceptionTimeThenSourceOrder) {
  // Both files hold a message at 200; the first source's comes first. A naive
  // concatenation or a sort by topic fails one of the two orders.
  VectorReader first({Message("/a/x", 100, {1}), Message("/a/x", 200, {2}), Message("/a/x", 400, {5})}, {});
  VectorReader second({Message("/b/y", 150, {3}), Message("/b/y", 200, {4})}, {});
  ReadAhead ahead({&first, &second});
  ahead.Fill(10);
  ASSERT_TRUE(ahead.Drained());
  std::vector<std::string> order;
  std::vector<std::size_t> sources;
  while (!ahead.Empty()) {
    for (const AheadMessage& message : ahead.TakeFront().messages) {
      order.push_back(message.port);
      sources.push_back(message.source_index);
    }
  }
  EXPECT_EQ(order, (std::vector<std::string>{"a.x", "b.y", "a.x", "b.y", "a.x"}));
  EXPECT_EQ(sources, (std::vector<std::size_t>{0, 1, 0, 1, 0}));
}

TEST(RunReadAhead, ItReadsOnlyAsFarAsAskedPastTheFirstInstantAndNoFurther) {
  std::vector<io::RawMessage> messages;
  for (int i = 0; i < 200; ++i) messages.push_back(Message("/a/x", i * 10, {static_cast<std::uint8_t>(i)}));
  VectorReader reader(messages, {});
  io::ReadBounds bounds;
  bounds.max_messages = 4;
  ReadAhead ahead({&reader}, bounds);
  ahead.Fill(2);  // the first instant, two more, and the one after (possibly incomplete)
  EXPECT_FALSE(ahead.Drained());
  EXPECT_EQ(ahead.Instants(), 3u);
  EXPECT_TRUE(ahead.FrontComplete());
  EXPECT_LT(reader.pulled(), 20u);  // a whole-file read would have pulled 200
}

TEST(RunReadAhead, TheFrontOfAnUnfinishedStreamIsCompleteOnlyOnceALaterInstantWasSeen) {
  VectorReader reader({Message("/a/x", 100, {1}), Message("/a/y", 100, {2})}, {});
  ReadAhead ahead({&reader});
  EXPECT_FALSE(ahead.FrontComplete());  // nothing read
  ahead.Fill(0);
  EXPECT_FALSE(ahead.FrontComplete());  // the first instant has begun; a second message may still join it
  ahead.Fill(1);
  EXPECT_TRUE(ahead.Drained());  // a single instant, then the end: nothing can still join it
  EXPECT_TRUE(ahead.FrontComplete());
  EXPECT_EQ(ahead.Front()->messages.size(), 2u);
}

TEST(RunReadAhead, FindMatchesTheCounterAmongTheMessagesAheadOnThatPortOnly) {
  VectorReader reader({Message("/p/out", 100, Data(5)), Message("/q/out", 100, Data(9)), Message("/p/out", 200, Data(9)),
                       Message("/p/out", 300, Data(10))},
                      {});
  ReadAhead ahead({&reader});
  ahead.Fill(10);
  const AheadMessage* found = ahead.Find("p.out", 9, DataType());
  ASSERT_NE(found, nullptr);
  EXPECT_EQ(found->message.log_time_ns, 200);  // not the /q/out message that also carries 9
  EXPECT_EQ(ahead.Find("p.out", 11, DataType()), nullptr);
  EXPECT_EQ(ahead.Find("p.out", 9, nullptr), nullptr);  // no type, no header, no match
  EXPECT_EQ(ahead.OnPort("p.out").size(), 3u);
}

TEST(RunReadAhead, ACounterIsFoundAcrossAWrapByItsDistanceNotItsMagnitude) {
  VectorReader reader({Message("/p/out", 100, Data(0xFFFFFFFFu)), Message("/p/out", 200, Data(1))}, {});
  ReadAhead ahead({&reader});
  ahead.Fill(10);
  EXPECT_NE(ahead.Find("p.out", 0xFFFFFFFFu, DataType()), nullptr);
  EXPECT_EQ(ahead.Find("p.out", 1, DataType())->message.log_time_ns, 200);
}

TEST(RunReadAhead, ASeekDropsWhatWasHeldAndSkipsWhatACodecWithoutSeekStillDeliversBeforeIt) {
  VectorReader reader({Message("/a/x", 100, {1}), Message("/a/x", 200, {2}), Message("/a/x", 300, {3})}, {});
  ReadAhead ahead({&reader});
  ahead.Fill(10);
  ahead.Seek(250);
  EXPECT_TRUE(ahead.Empty());
  ahead.Fill(10);
  ASSERT_EQ(ahead.Instants(), 1u);
  EXPECT_EQ(ahead.Front()->time_ns, 300);
}

TEST(RunReadAhead, TheFirstAndLastReceptionTimesAreTheRecordingsEvenAfterASeek) {
  VectorReader reader({Message("/a/x", 100, {1}), Message("/a/x", 900, {2})}, {});
  ReadAhead ahead({&reader});
  ahead.Fill(10);
  ahead.Seek(500);
  ahead.Fill(10);
  EXPECT_EQ(ahead.FirstTimeNs().value(), 100);
  EXPECT_EQ(ahead.LastTimeNs().value(), 900);
}

TEST(RunReadAhead, BytesReadBeforeTheCounterWasAttachedAreReportedToItAtOnce) {
  VectorReader reader({Message("/a/x", 100, {1, 2, 3}), Message("/a/y", 200, {4, 5})}, {});
  ReadAhead ahead({&reader});
  ahead.Fill(10);
  diagnostics::ByteCounter counter;
  ahead.SetByteCounter(&counter);
  EXPECT_EQ(counter.ForTopic("/a/x"), 3u);
  EXPECT_EQ(counter.Total(), 5u);
}

TEST(RunReadAhead, StopDropsEverythingAndReadsNoMore) {
  VectorReader reader({Message("/a/x", 100, {1}), Message("/a/x", 200, {2})}, {});
  ReadAhead ahead({&reader});
  ahead.Fill(0);
  ahead.Stop();
  ahead.Fill(10);
  EXPECT_TRUE(ahead.Empty());
  EXPECT_TRUE(ahead.Drained());
}

TEST(RunRecordedReference, KeepsTheLastDepthMessagesAndFindsByCounterOrByTime) {
  RecordedReference reference;
  reference.Declare("s.refSync", 2, DataType());
  reference.Add("s.refSync", 100, Data(1));
  reference.Add("s.refSync", 200, Data(2));
  reference.Add("s.refSync", 300, Data(3));
  EXPECT_EQ(reference.Find("s.refSync", 1), nullptr);  // evicted by depth 2
  EXPECT_NE(reference.Find("s.refSync", 2), nullptr);
  ASSERT_NE(reference.AtTime("s.refSync", 300), nullptr);
  EXPECT_EQ(*reference.AtTime("s.refSync", 300), Data(3));
  EXPECT_EQ(reference.AtTime("s.refSync", 250), nullptr);
  reference.Clear();
  EXPECT_EQ(reference.Find("s.refSync", 3), nullptr);
  reference.Add("undeclared.port", 1, Data(1));
  EXPECT_FALSE(reference.Declared("undeclared.port"));
}

}  // namespace
}  // namespace simcore::runner
