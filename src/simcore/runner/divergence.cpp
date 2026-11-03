// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IMP-0116`/`IMP-0117` / `SW-0116`/`SW-0117` -- first-divergence
///   detection and the per-message informational-only flag.
///
///   `NEW`: neither `resim_runner.cpp` nor `core/resim.py` compares a
///   simulated port against its recorded twin at all; both simply overwrite
///   the channel. There is nothing to port here, only the two rules to
///   implement:
///
///   1. **The FIRST difference latches.** A later tick agreeing again does
///      not clear it and a later, different difference does not replace it
///      -- which is what makes `SW-0116`'s "identical across re-runs" a
///      property of the mechanism rather than of the data.
///   2. **The flag is per message.** `SW-0117`'s Accept is a consumer
///      reading an *arbitrary slice* of the export, so a run-level header
///      cannot satisfy it: a slice that does not contain the header would
///      read clean.
/// @author Pavan Karimajji

#include <algorithm>
#include <cstddef>
#include <memory>
#include <optional>

#include <google/protobuf/descriptor.h>
#include <google/protobuf/dynamic_message.h>
#include <google/protobuf/message.h>

#include "simcore/runner.hpp"

namespace simcore::runner {

namespace pb = google::protobuf;

namespace {

// The value of an unsigned scalar field, or none when the message has no such
// field of that type.
std::optional<std::uint64_t> UnsignedField(const pb::Message& message, const char* name) {
  const pb::FieldDescriptor* field = message.GetDescriptor()->FindFieldByName(name);
  if (field == nullptr || field->is_repeated()) return std::nullopt;
  const pb::Reflection* reflection = message.GetReflection();
  if (field->cpp_type() == pb::FieldDescriptor::CPPTYPE_UINT32) return reflection->GetUInt32(message, field);
  if (field->cpp_type() == pb::FieldDescriptor::CPPTYPE_UINT64) return reflection->GetUInt64(message, field);
  return std::nullopt;
}

// `ARCH` section 7: a `refSync` is equal when it has the same entries and each
// has the same `measurement_counter` and `source_timestamp_us`. None when the
// message is not shaped like a `refSync`; the caller then compares bytes.
std::optional<bool> EqualRefSyncs(const pb::Message& a, const pb::Message& b) {
  const pb::FieldDescriptor* inputs = a.GetDescriptor()->FindFieldByName("inputs");
  if (inputs == nullptr || !inputs->is_repeated() || inputs->cpp_type() != pb::FieldDescriptor::CPPTYPE_MESSAGE) {
    return std::nullopt;
  }
  const pb::Reflection* reflection = a.GetReflection();
  const int count = reflection->FieldSize(a, inputs);
  if (count != reflection->FieldSize(b, inputs)) return false;
  for (int i = 0; i < count; ++i) {
    const pb::Message& left = reflection->GetRepeatedMessage(a, inputs, i);
    const pb::Message& right = reflection->GetRepeatedMessage(b, inputs, i);
    for (const char* name : {"measurement_counter", "source_timestamp_us"}) {
      const std::optional<std::uint64_t> left_value = UnsignedField(left, name);
      const std::optional<std::uint64_t> right_value = UnsignedField(right, name);
      if (!left_value.has_value() || !right_value.has_value()) return std::nullopt;
      if (*left_value != *right_value) return false;
    }
  }
  return true;
}

// Sets the `sig_header`'s `cycle_counter` to 0 when the message has both.
void ZeroCycleCounter(pb::Message& message) {
  const pb::FieldDescriptor* header = message.GetDescriptor()->FindFieldByName("sig_header");
  if (header == nullptr || header->is_repeated() || header->cpp_type() != pb::FieldDescriptor::CPPTYPE_MESSAGE) return;
  const pb::Reflection* reflection = message.GetReflection();
  if (!reflection->HasField(message, header)) return;
  pb::Message* sig = reflection->MutableMessage(&message, header);
  const pb::FieldDescriptor* cycle = sig->GetDescriptor()->FindFieldByName("cycle_counter");
  if (cycle == nullptr || cycle->is_repeated() || cycle->cpp_type() != pb::FieldDescriptor::CPPTYPE_UINT32) return;
  sig->GetReflection()->SetUInt32(sig, cycle, 0);
}

}  // namespace

bool EqualOutputs(const std::vector<std::uint8_t>& simulated, const std::vector<std::uint8_t>& recorded,
                  const pb::Descriptor* descriptor) {
  if (simulated == recorded) return true;
  if (descriptor == nullptr) return false;
  pb::DynamicMessageFactory factory;
  const pb::Message* prototype = factory.GetPrototype(descriptor);
  if (prototype == nullptr) return false;
  std::unique_ptr<pb::Message> left(prototype->New());
  std::unique_ptr<pb::Message> right(prototype->New());
  if (!left->ParseFromArray(simulated.data(), static_cast<int>(simulated.size())) ||
      !right->ParseFromArray(recorded.data(), static_cast<int>(recorded.size()))) {
    return false;  // not a message of this type: the bytes differ
  }
  if (descriptor->full_name() == "adas.common.RefSync") {
    const std::optional<bool> equal = EqualRefSyncs(*left, *right);
    if (equal.has_value()) return *equal;
  }
  ZeroCycleCounter(*left);
  ZeroCycleCounter(*right);
  std::string left_bytes;
  std::string right_bytes;
  left->SerializeToString(&left_bytes);
  right->SerializeToString(&right_bytes);
  return left_bytes == right_bytes;
}

void DivergenceLatch::Observe(std::uint64_t step, std::int64_t log_time_ns, const std::string& stage,
                              const std::string& port, const std::vector<std::uint8_t>& simulated,
                              const std::vector<std::uint8_t>& recorded, const pb::Descriptor* descriptor) {
  if (first_.has_value()) return;  // latched: never re-triggers (rule 1 above)
  if (EqualOutputs(simulated, recorded, descriptor)) return;

  // The magnitude, in the one unit available without a declared per-field
  // tolerance band (`R-SIM-24`'s `tolerance.yaml`, which nothing emits
  // yet): differing bytes over the common prefix, plus the length
  // difference. A length difference alone is still a real magnitude -- a
  // simulated message one byte longer than the recorded one differs by one.
  const std::size_t common = std::min(simulated.size(), recorded.size());
  std::size_t differing = 0;
  for (std::size_t i = 0; i < common; ++i) {
    if (simulated[i] != recorded[i]) ++differing;
  }
  differing += std::max(simulated.size(), recorded.size()) - common;

  Divergence divergence;
  divergence.tick_index = step;
  divergence.log_time_ns = log_time_ns;
  divergence.stage = stage;
  divergence.port = port;
  divergence.differing_bytes = differing;
  divergence.simulated_bytes = simulated.size();
  divergence.recorded_bytes = recorded.size();
  first_ = divergence;
}

bool DivergenceLatch::InformationalOnly(std::uint64_t tick_index) const {
  if (!first_.has_value()) return false;
  // Unsigned addition on two `uint64_t`s a run could never make overflow
  // (a tick index and a configured grace window), compared with `>=` so a
  // zero grace window flags the divergence tick itself.
  return tick_index >= first_->tick_index + grace_ticks_;
}

}  // namespace simcore::runner
