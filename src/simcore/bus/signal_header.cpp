// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `ReadSignalHeader` (`WP-02`, `IMP-0008`): the four fields of a
///   message's `sig_header`, read by protobuf reflection on the field named
///   `sig_header` -- the only payload read behind a decision. No generated
///   class of the message type is needed (`R-SIM-11`). A 0 in
///   `measurement_counter` or `source_timestamp_us` reads as unknown (the
///   contract's rule); a 0 `cycle_counter` or `sig_status` is a real value.
/// @author Pavan Karimajji

#include <memory>

#include <google/protobuf/descriptor.h>
#include <google/protobuf/dynamic_message.h>
#include <google/protobuf/message.h>

#include "simcore/bus.hpp"

namespace simcore::bus {

namespace pb = google::protobuf;

namespace {

// The value of `name` in `header` when the field exists with the wanted
// integer type; unknown otherwise (a field of another type is not read).
// `zero_is_unknown` is the contract's rule for `measurement_counter` and
// `source_timestamp_us` (`signal_header.proto`: 0 means unknown); for
// `cycle_counter` and `sig_status` a 0 is a real value.
template <class T>
Unknown<T> ReadUnsigned(const pb::Message& header, const char* name, pb::FieldDescriptor::CppType type,
                        bool zero_is_unknown) {
  const pb::FieldDescriptor* field = header.GetDescriptor()->FindFieldByName(name);
  if (field == nullptr || field->is_repeated() || field->cpp_type() != type) return Unknown<T>::None();
  const pb::Reflection* reflection = header.GetReflection();
  const T value = type == pb::FieldDescriptor::CPPTYPE_UINT32
                      ? static_cast<T>(reflection->GetUInt32(header, field))
                      : static_cast<T>(reflection->GetUInt64(header, field));
  if (zero_is_unknown && value == 0) return Unknown<T>::None();
  return value;
}

}  // namespace

SignalHeader ReadSignalHeader(const std::vector<std::uint8_t>& payload, const pb::Descriptor* descriptor) {
  SignalHeader result;
  if (descriptor == nullptr) return result;
  const pb::FieldDescriptor* field = descriptor->FindFieldByName("sig_header");
  if (field == nullptr || field->is_repeated() || field->cpp_type() != pb::FieldDescriptor::CPPTYPE_MESSAGE) {
    return result;
  }
  pb::DynamicMessageFactory factory;
  const pb::Message* prototype = factory.GetPrototype(descriptor);
  if (prototype == nullptr) return result;
  std::unique_ptr<pb::Message> message(prototype->New());
  if (!message->ParseFromArray(payload.data(), static_cast<int>(payload.size()))) return result;
  const pb::Reflection* reflection = message->GetReflection();
  if (!reflection->HasField(*message, field)) return result;
  const pb::Message& header = reflection->GetMessage(*message, field);
  result.source_timestamp_us =
      ReadUnsigned<std::uint64_t>(header, "source_timestamp_us", pb::FieldDescriptor::CPPTYPE_UINT64, true);
  result.measurement_counter =
      ReadUnsigned<std::uint32_t>(header, "measurement_counter", pb::FieldDescriptor::CPPTYPE_UINT32, true);
  result.cycle_counter = ReadUnsigned<std::uint32_t>(header, "cycle_counter", pb::FieldDescriptor::CPPTYPE_UINT32, false);
  result.sig_status = ReadUnsigned<std::uint32_t>(header, "sig_status", pb::FieldDescriptor::CPPTYPE_UINT32, false);
  result.present = true;
  return result;
}

}  // namespace simcore::bus
