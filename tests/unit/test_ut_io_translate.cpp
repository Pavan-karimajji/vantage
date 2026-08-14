// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-IO-12`..`UT-IO-14` (`SW-0032`..`SW-0034`): `Translator` applies an
///   already-resolved ingest table, a topic absent from the table passes
///   through untranslated and tagged unknown, a factor/offset is applied
///   once, and a declared `proto_type` mismatch is refused rather than
///   coerced.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "simcore/io.hpp"

namespace simcore::io {
namespace {

IngestRow MakeRow(std::string raw_topic, std::string port, double factor = 1.0, double offset = 0.0) {
  IngestRow row;
  row.raw_topic = std::move(raw_topic);
  row.port = std::move(port);
  row.factor = factor;
  row.offset = offset;
  return row;
}

TEST(UtIo12Translator, TopicAbsentFromTableIsDeliveredUntranslatedAndTaggedUnknown) {
  Translator translator({MakeRow("known/topic", "known.port")});

  RawMessage msg;
  msg.topic = "unmapped/topic";
  msg.log_time_ns = 100;

  const auto result = translator.Apply(msg, /*declared_schema_name=*/"");
  ASSERT_TRUE(result.ok());
  EXPECT_EQ(result.value().topic, "unmapped/topic");  // unchanged
  EXPECT_FALSE(result.value().translated);
  EXPECT_EQ(translator.OriginFor("unmapped/topic"), Provenance::kUnknown);
}

TEST(UtIo13UnitCorrection, FactorAndOffsetAppliedOnceAndDoubleApplyRefused) {
  Translator translator({MakeRow("raw/vx", "vdy.vx", /*factor=*/1000.0, /*offset=*/5.0)});

  RawMessage msg;
  msg.topic = "raw/vx";
  msg.log_time_ns = 2;  // -> 2*1000 + 5 = 2005

  const auto first = translator.Apply(msg, "");
  ASSERT_TRUE(first.ok());
  EXPECT_EQ(first.value().topic, "vdy.vx");
  EXPECT_EQ(first.value().log_time_ns, 2005);
  EXPECT_TRUE(first.value().translated);

  // SW-0033's Accept: applying the same map twice is refused.
  const auto second = translator.Apply(first.value(), "");
  EXPECT_FALSE(second.ok());
}

TEST(UtIo14TypeMismatch, ADeclaredProtoTypeMismatchIsRefusedNeverCoerced) {
  IngestRow row = MakeRow("raw/obj", "df.objects");
  row.proto_type = "adas.df.DfObjList";
  Translator translator({row});

  RawMessage msg;
  msg.topic = "raw/obj";

  const auto mismatched = translator.Apply(msg, /*declared_schema_name=*/"adas.legacy.ObjectList");
  ASSERT_FALSE(mismatched.ok());
  EXPECT_EQ(mismatched.error().kind, Kind::Authoring);

  const auto matched = translator.Apply(msg, /*declared_schema_name=*/"adas.df.DfObjList");
  EXPECT_TRUE(matched.ok());
}

}  // namespace
}  // namespace simcore::io
