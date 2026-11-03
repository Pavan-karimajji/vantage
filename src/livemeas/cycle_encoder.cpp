// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `encodeCycle` (`IMP-0073`, `RCT:IMP-0037`): see `cycle_encoder.hpp`.
/// @author Pavan Karimajji

#include "livemeas/cycle_encoder.hpp"

#include <google/protobuf/io/coded_stream.h>

#include "livemeas/meas_cycle.pb.h"

namespace vantage::livemeas {

namespace {

using adas::livemeas::MeasBadge;
using adas::livemeas::MeasCycle;
using adas::livemeas::MeasPortValue;

// Bytes one repeated message field adds to its parent: a one-byte tag, the length, the message.
std::size_t FieldBytes(std::size_t message_bytes) {
  return 1 + google::protobuf::io::CodedOutputStream::VarintSize32(static_cast<std::uint32_t>(message_bytes)) +
         message_bytes;
}

MeasPortValue Build(const LiveMeasValue& value, const BulkPlacement& placement, bool keep_payload) {
  MeasPortValue out;
  out.set_port(value.port);
  out.set_origin(static_cast<MeasPortValue::Origin>(value.origin));
  out.set_age_ns(value.age_ns);
  if (value.bulk != 0) {
    if (placement.placed) {
      out.mutable_bulk()->set_slot(placement.slot);
      out.mutable_bulk()->set_sequence(placement.sequence);
    } else {
      out.set_omitted(true);  // the frame did not fit a MeasBulk slot
    }
  } else if (keep_payload) {
    if (value.payload != nullptr && value.length > 0) out.set_payload(value.payload, value.length);
  } else {
    out.set_omitted(true);
  }
  return out;
}

}  // namespace

EncodedCycle encodeCycle(const LiveMeasValue* values, std::uint32_t value_count,
                         const std::vector<BulkPlacement>& placements, const LiveMeasBadge* badges,
                         std::uint32_t badge_count, std::size_t capacity) {
  EncodedCycle result;
  MeasCycle cycle;

  std::size_t running = 0;
  for (std::uint32_t i = 0; i < badge_count; ++i) {
    MeasBadge* badge = cycle.add_badges();
    badge->set_kind(static_cast<MeasBadge::Kind>(badges[i].kind));
    if (badges[i].subject != nullptr) badge->set_subject(badges[i].subject);
    badge->set_count(badges[i].count);
    running += FieldBytes(badge->ByteSizeLong());
  }

  // Every value in its smallest form first (payload omitted, or the bulk reference); then, in order, a
  // payload is put back when the cycle still fits.
  std::vector<std::size_t> minimal(value_count);
  std::vector<std::size_t> full(value_count);
  for (std::uint32_t i = 0; i < value_count; ++i) {
    const BulkPlacement& placement = i < placements.size() ? placements[i] : BulkPlacement{};
    minimal[i] = FieldBytes(Build(values[i], placement, false).ByteSizeLong());
    full[i] = FieldBytes(Build(values[i], placement, true).ByteSizeLong());
    running += minimal[i];
  }
  if (running > capacity) return result;  // nothing fits: the step is dropped

  std::vector<bool> keep(value_count, false);
  for (std::uint32_t i = 0; i < value_count; ++i) {
    if (values[i].bulk != 0 || full[i] == minimal[i]) {
      keep[i] = true;
      continue;
    }
    if (running - minimal[i] + full[i] <= capacity) {
      running = running - minimal[i] + full[i];
      keep[i] = true;
    } else {
      ++result.omitted;
    }
  }
  for (std::uint32_t i = 0; i < value_count; ++i) {
    const BulkPlacement& placement = i < placements.size() ? placements[i] : BulkPlacement{};
    *cycle.add_values() = Build(values[i], placement, keep[i]);
  }
  // `add_values` after `add_badges` keeps field order irrelevant to the reader; the serialized form
  // lists values (field 1) before badges (field 2).
  if (!cycle.SerializeToString(&result.bytes) || result.bytes.size() > capacity) {
    result.bytes.clear();
    return result;
  }
  result.fits = true;
  return result;
}

}  // namespace vantage::livemeas
