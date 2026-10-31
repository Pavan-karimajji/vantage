// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `ReadSignalHeader` (`WP-02`, `IMP-0008`) and the port bus that reads it
///   at the door (`IMP-0007`): the four fields come out of a real contract
///   message by reflection on `sig_header`; no field, no header or bytes that
///   do not parse give an explicit unknown for every field; a port declared
///   with a depth keeps that many samples and a declared port's samples feed
///   the identity tracker. Unit tests; the system tests `SYT-SEL-10` and
///   `SYT-RUN-06` are built in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <cstdint>
#include <memory>
#include <vector>

#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>
#include <google/protobuf/dynamic_message.h>

#include "Bsd__Outputs/bsd_outputs.pb.h"
#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

std::vector<std::uint8_t> Encode(const google::protobuf::Message& message) {
  std::vector<std::uint8_t> bytes(message.ByteSizeLong());
  message.SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
  return bytes;
}

const google::protobuf::Descriptor* BsdDescriptor() { return adas::df::BsdOutputs::descriptor(); }

std::vector<std::uint8_t> BsdBytes(std::uint32_t measurement, std::uint32_t cycle, std::uint64_t time_us,
                                   std::uint32_t status) {
  adas::df::BsdOutputs message;
  adas::common::SignalHeader* header = message.mutable_sig_header();
  header->set_measurement_counter(measurement);
  header->set_cycle_counter(cycle);
  header->set_source_timestamp_us(time_us);
  header->set_sig_status(status);
  return Encode(message);
}

TEST(UtBusSignalHeader, ReadsTheFourFieldsOfARealContractMessage) {
  const SignalHeader header = ReadSignalHeader(BsdBytes(41, 7, 1'234'567, 1), BsdDescriptor());
  EXPECT_TRUE(header.present);
  EXPECT_EQ(header.measurement_counter.value(), 41u);
  EXPECT_EQ(header.cycle_counter.value(), 7u);
  EXPECT_EQ(header.source_timestamp_us.value(), 1'234'567u);
  EXPECT_EQ(header.sig_status.value(), 1u);
}

// The contract: a 0 measurement_counter or source_timestamp_us is unknown; a 0
// cycle_counter or sig_status is a real value (a sender's first count, INIT).
TEST(UtBusSignalHeader, AZeroMeasurementCounterAndSourceTimeReadAsUnknownButZeroCycleAndStatusStay) {
  const SignalHeader header = ReadSignalHeader(BsdBytes(0, 0, 0, 0), BsdDescriptor());
  EXPECT_TRUE(header.present);
  EXPECT_FALSE(header.measurement_counter.has_value());
  EXPECT_FALSE(header.source_timestamp_us.has_value());
  ASSERT_TRUE(header.cycle_counter.has_value());
  EXPECT_EQ(header.cycle_counter.value(), 0u);
  ASSERT_TRUE(header.sig_status.has_value());
  EXPECT_EQ(header.sig_status.value(), 0u);
}

TEST(UtBusSignalHeader, EachZeroIsJudgedOnItsOwn) {
  const SignalHeader only_counter_zero = ReadSignalHeader(BsdBytes(0, 4, 9, 1), BsdDescriptor());
  EXPECT_FALSE(only_counter_zero.measurement_counter.has_value());
  EXPECT_EQ(only_counter_zero.source_timestamp_us.value(), 9u);
  const SignalHeader only_time_zero = ReadSignalHeader(BsdBytes(3, 4, 0, 1), BsdDescriptor());
  EXPECT_EQ(only_time_zero.measurement_counter.value(), 3u);
  EXPECT_FALSE(only_time_zero.source_timestamp_us.has_value());
}

TEST(UtBusSignalHeader, AMessageWithoutTheHeaderSetGivesUnknownForEveryField) {
  adas::df::BsdOutputs message;  // sig_header never set
  const SignalHeader header = ReadSignalHeader(Encode(message), BsdDescriptor());
  EXPECT_FALSE(header.present);
  EXPECT_FALSE(header.measurement_counter.has_value());
  EXPECT_FALSE(header.cycle_counter.has_value());
  EXPECT_FALSE(header.source_timestamp_us.has_value());
  EXPECT_FALSE(header.sig_status.has_value());
}

TEST(UtBusSignalHeader, ADescriptorWithoutASigHeaderFieldGivesUnknownForEveryField) {
  // The header message itself has no field called sig_header.
  const SignalHeader header = ReadSignalHeader(BsdBytes(1, 1, 1, 1), adas::common::SignalHeader::descriptor());
  EXPECT_FALSE(header.present);
  EXPECT_FALSE(header.measurement_counter.has_value());
}

TEST(UtBusSignalHeader, ANullDescriptorOrBytesThatDoNotParseGiveUnknown) {
  EXPECT_FALSE(ReadSignalHeader(BsdBytes(1, 1, 1, 1), nullptr).present);
  const std::vector<std::uint8_t> garbage = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  const SignalHeader header = ReadSignalHeader(garbage, BsdDescriptor());
  EXPECT_FALSE(header.present);
  EXPECT_FALSE(header.measurement_counter.has_value());
}

// The field is found by its name only: a message whose field 1 is some other
// name carries no header, whatever its number or type.
TEST(UtBusSignalHeader, AFieldNotNamedSigHeaderIsNotAHeader) {
  google::protobuf::DescriptorPool pool;
  google::protobuf::FileDescriptorProto file;
  file.set_name("other_header.proto");
  file.set_package("other_header");
  file.set_syntax("proto3");
  google::protobuf::DescriptorProto* message = file.add_message_type();
  message->set_name("Other");
  google::protobuf::FieldDescriptorProto* field = message->add_field();
  field->set_name("header");
  field->set_number(1);
  field->set_type(google::protobuf::FieldDescriptorProto::TYPE_UINT32);
  field->set_label(google::protobuf::FieldDescriptorProto::LABEL_OPTIONAL);
  const google::protobuf::FileDescriptor* built = pool.BuildFile(file);
  ASSERT_NE(built, nullptr);
  const google::protobuf::Descriptor* descriptor = built->FindMessageTypeByName("Other");
  EXPECT_FALSE(ReadSignalHeader({0x08, 0x05}, descriptor).present);
}

TEST(UtBusSignalHeader, ADeclaredPortKeepsItsDepthAndAnswersWithTheNewest) {
  PortBus bus;
  bus.DeclarePort("bsd.outputs", 3, BsdDescriptor());
  for (std::uint32_t i = 1; i <= 5; ++i) {
    PortValue value;
    value.payload = BsdBytes(i, i, i * 1000, 1);
    ASSERT_TRUE(bus.Publish("bsd.outputs", std::move(value), i * 100).ok());
  }
  const SampleBuffer* buffer = bus.Buffer("bsd.outputs");
  ASSERT_NE(buffer, nullptr);
  EXPECT_EQ(buffer->Size(), 3u);
  EXPECT_EQ(buffer->Evicted(), 2u);
  EXPECT_EQ(buffer->Samples().front().sig.measurement_counter.value(), 3u);
  const PortValue newest = bus.Get("bsd.outputs", 500);
  EXPECT_TRUE(newest.updated);
  EXPECT_EQ(newest.payload, BsdBytes(5, 5, 5000, 1));
  EXPECT_EQ(buffer->FindByCounter(4).sample->arrival_ns, 400);
  EXPECT_EQ(buffer->NewestNotAfter(450)->arrival_ns, 400);
  EXPECT_EQ(buffer->NewestNotAfter(250), nullptr);  // that sample was evicted
}

TEST(UtBusSignalHeader, EveryDeclaredPortSampleIsObservedForIdentity) {
  PortBus bus;
  bus.DeclarePort("p", 4, BsdDescriptor());
  const std::uint32_t measurement[] = {1, 2, 5, 1};  // a gap of two, then both back
  const std::uint32_t cycle[] = {1, 2, 3, 1};
  for (int i = 0; i < 4; ++i) {
    PortValue value;
    value.payload = BsdBytes(measurement[i], cycle[i], 0, 1);
    ASSERT_TRUE(bus.Publish("p", std::move(value), i).ok());
  }
  EXPECT_EQ(bus.Identity().Counts("p").samples, 4u);
  EXPECT_EQ(bus.Identity().Counts("p").gaps, 1u);
  EXPECT_EQ(bus.Identity().Counts("p").resets, 1u);
  EXPECT_EQ(bus.Identity().Last("p").verdict, IdentityVerdict::kCounterReset);
}

// Planted: a zero header that a naive read would match by number or by time.
TEST(UtBusSignalHeader, AZeroHeaderSampleInADeclaredPortIsNotFoundByCounterOrTime) {
  PortBus bus;
  bus.DeclarePort("p", 4, BsdDescriptor());
  PortValue zero;
  zero.payload = BsdBytes(0, 1, 0, 1);
  ASSERT_TRUE(bus.Publish("p", std::move(zero), 10).ok());
  PortValue real;
  real.payload = BsdBytes(6, 2, 5000, 1);
  ASSERT_TRUE(bus.Publish("p", std::move(real), 20).ok());
  const SampleBuffer* buffer = bus.Buffer("p");
  EXPECT_EQ(buffer->FindByCounter(0).sample, nullptr);
  EXPECT_EQ(buffer->NewestCounterNotAfter(0), nullptr);
  EXPECT_EQ(buffer->NewestCounterNotAfter(100)->sig.measurement_counter.value(), 6u);
  EXPECT_EQ(buffer->NewestSourceTimeNotAfter(4999), nullptr);  // the zero-time sample is not "before" it
  EXPECT_EQ(buffer->NewestSourceTimeNotAfter(5000)->sig.measurement_counter.value(), 6u);
  EXPECT_EQ(bus.Identity().Counts("p").unknown, 1u);
  EXPECT_EQ(bus.Identity().Counts("p").samples, 1u);
  EXPECT_EQ(bus.Identity().Counts("p").identity_broken + bus.Identity().Counts("p").resets, 0u);
}

TEST(UtBusSignalHeader, APortNeverDeclaredKeepsOneSampleAndReadsNoHeader) {
  PortBus bus;
  PortValue value;
  value.payload = BsdBytes(9, 9, 9, 1);
  ASSERT_TRUE(bus.Publish("undeclared", value, 10).ok());
  ASSERT_TRUE(bus.Publish("undeclared", value, 20).ok());
  const SampleBuffer* buffer = bus.Buffer("undeclared");
  ASSERT_NE(buffer, nullptr);
  EXPECT_EQ(buffer->Size(), 1u);
  EXPECT_FALSE(buffer->Newest()->sig.present);
  EXPECT_EQ(bus.Identity().Counts("undeclared").samples, 0u);
  EXPECT_EQ(bus.Buffer("nowhere"), nullptr);
}

TEST(UtBusSignalHeader, ADeclaredPortWithNothingPublishedAnswersUnknownNotAbsent) {
  PortBus bus;
  bus.DeclarePort("p", 2, BsdDescriptor());
  const PortValue value = bus.Get("p", 5);
  EXPECT_FALSE(value.updated);
  EXPECT_EQ(value.origin, Origin::Unknown);
}

}  // namespace
}  // namespace simcore::bus
