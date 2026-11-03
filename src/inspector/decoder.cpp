// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief `DynamicDecoder` (`WP-16`, `RCT:IMP-0039`, `SYS-0078`): a port payload decoded through the description's
///   `descriptor_set` and nothing else -- a pool built from the set's files, a dynamic message of the named type,
///   its text format on one line. No generated class of a port payload is looked up.
/// @author Pavan Karimajji

#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>
#include <google/protobuf/dynamic_message.h>
#include <google/protobuf/text_format.h>

#include "inspector.hpp"

namespace vantage::inspector {

namespace pb = google::protobuf;

struct DynamicDecoder::Impl {
  pb::DescriptorPool pool;
  pb::DynamicMessageFactory factory{&pool};
};

DynamicDecoder::DynamicDecoder(const std::string& descriptorSet) : impl_(new Impl()) {
  pb::FileDescriptorSet set;
  if (!set.ParseFromString(descriptorSet)) return;
  std::vector<pb::FileDescriptorProto> pending(set.file().begin(), set.file().end());
  // A file whose dependencies are not built yet waits for the next pass.
  while (!pending.empty()) {
    std::vector<pb::FileDescriptorProto> next;
    for (const pb::FileDescriptorProto& file : pending) {
      if (impl_->pool.FindFileByName(file.name()) != nullptr) continue;
      if (impl_->pool.BuildFile(file) == nullptr) next.push_back(file);
    }
    if (next.size() == pending.size()) break;
    pending = std::move(next);
  }
}

DynamicDecoder::~DynamicDecoder() = default;

std::string DynamicDecoder::decode(const std::string& protoType, const std::uint8_t* bytes, std::size_t length) const {
  const pb::Descriptor* descriptor = impl_->pool.FindMessageTypeByName(protoType);
  if (descriptor == nullptr) return "<unknown type " + protoType + ">";
  std::unique_ptr<pb::Message> message(impl_->factory.GetPrototype(descriptor)->New());
  if (!message->ParseFromArray(bytes, static_cast<int>(length))) return "<bytes do not parse as " + protoType + ">";
  pb::TextFormat::Printer printer;
  printer.SetSingleLineMode(true);
  std::string text;
  printer.PrintToString(*message, &text);
  while (!text.empty() && text.back() == ' ') text.pop_back();  // single-line mode ends with a space
  return text.empty() ? "<empty>" : text;
}

std::optional<std::uint64_t> DynamicDecoder::measurementCounter(const std::string& protoType, const std::uint8_t* bytes,
                                                                std::size_t length) const {
  const pb::Descriptor* descriptor = impl_->pool.FindMessageTypeByName(protoType);
  if (descriptor == nullptr) return std::nullopt;
  const pb::FieldDescriptor* header_field = descriptor->FindFieldByName("sig_header");
  if (header_field == nullptr || header_field->cpp_type() != pb::FieldDescriptor::CPPTYPE_MESSAGE) return std::nullopt;
  const pb::FieldDescriptor* counter_field = header_field->message_type()->FindFieldByName("measurement_counter");
  if (counter_field == nullptr) return std::nullopt;
  std::unique_ptr<pb::Message> message(impl_->factory.GetPrototype(descriptor)->New());
  if (!message->ParseFromArray(bytes, static_cast<int>(length))) return std::nullopt;
  const pb::Message& header = message->GetReflection()->GetMessage(*message, header_field);
  switch (counter_field->cpp_type()) {
    case pb::FieldDescriptor::CPPTYPE_UINT32: return header.GetReflection()->GetUInt32(header, counter_field);
    case pb::FieldDescriptor::CPPTYPE_UINT64: return header.GetReflection()->GetUInt64(header, counter_field);
    default: return std::nullopt;
  }
}

}  // namespace vantage::inspector
