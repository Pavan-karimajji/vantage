// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   Shared test fixtures of the step loop's parts (`WP-05`): an in-memory
///   `Reader` over a message vector, a `Writer` that keeps what it is given,
///   and real contract messages (`CycleControl` as a generic data message with
///   a `sig_header`, `RefSync`) so a header is read by reflection as in a run.
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "common/cycle_control.pb.h"
#include "common/ref_sync.pb.h"
#include "simcore/io.hpp"

namespace simcore::testing {

class VectorReader final : public io::Reader {
 public:
  VectorReader(std::vector<io::RawMessage> messages, std::map<std::string, io::TopicInfo> topics)
      : messages_(std::move(messages)), topics_(std::move(topics)) {}

  Result<bool> Open(const std::filesystem::path&) override { return Result<bool>::Ok(true); }
  std::map<std::string, io::TopicInfo> Describe() const override { return topics_; }
  void Seek(std::int64_t log_time_ns) override {
    lookahead_.reset();
    index_ = 0;
    while (index_ < messages_.size() && messages_[index_].log_time_ns < log_time_ns) ++index_;
  }
  io::Batch ReadRange(const io::ReadBounds& bounds) override {
    return io::detail::AccumulateBatch(bounds, lookahead_, [this]() -> std::optional<io::RawMessage> {
      if (index_ >= messages_.size()) return std::nullopt;
      ++pulled_;
      return messages_[index_++];
    });
  }
  void Close() override {}
  std::optional<std::vector<std::uint8_t>> GetMeta(const std::string&) const override { return std::nullopt; }

  std::size_t pulled() const { return pulled_; }

 private:
  std::vector<io::RawMessage> messages_;
  std::map<std::string, io::TopicInfo> topics_;
  std::optional<io::RawMessage> lookahead_;
  std::size_t index_ = 0;
  std::size_t pulled_ = 0;
};

class CapturingWriter final : public io::Writer {
 public:
  Result<bool> Open(const std::filesystem::path&, const std::map<std::string, io::TopicInfo>&) override {
    return Result<bool>::Ok(true);
  }
  void Write(const io::RawMessage& message) override { written.push_back(message); }
  void WriteMeta(const std::string&, const std::vector<std::uint8_t>&) override {}
  void Close() override {}

  std::vector<io::RawMessage> written;
};

// A data message with a real `sig_header` (the type is `CycleControl`; any
// message with the header would do).
inline std::vector<std::uint8_t> Data(std::uint32_t measurement_counter, std::uint64_t source_us = 0,
                                      std::uint32_t cycle = 1,
                                      adas::common::CycleControl::OpMode op = adas::common::CycleControl::RUN) {
  adas::common::CycleControl message;
  adas::common::SignalHeader* header = message.mutable_sig_header();
  header->set_measurement_counter(measurement_counter);
  header->set_source_timestamp_us(source_us);
  header->set_cycle_counter(cycle);
  header->set_sig_status(1);
  message.set_op_mode(op);
  std::vector<std::uint8_t> bytes(static_cast<std::size_t>(message.ByteSizeLong()));
  if (!bytes.empty()) message.SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
  return bytes;
}

// A recorded refSync: its own header counter, and one entry per (input, counter).
inline std::vector<std::uint8_t> RefSyncOf(std::uint32_t measurement_counter,
                                           const std::vector<std::pair<std::string, std::uint32_t>>& entries) {
  adas::common::RefSync message;
  message.mutable_sig_header()->set_measurement_counter(measurement_counter);
  for (const auto& [port, counter] : entries) {
    adas::common::RefSyncEntry* entry = message.add_inputs();
    entry->set_port(port);
    entry->set_measurement_counter(counter);
  }
  std::vector<std::uint8_t> bytes(static_cast<std::size_t>(message.ByteSizeLong()));
  if (!bytes.empty()) message.SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
  return bytes;
}

inline io::RawMessage Message(const std::string& topic, std::int64_t time_ns, std::vector<std::uint8_t> payload) {
  io::RawMessage message;
  message.topic = topic;
  message.log_time_ns = time_ns;
  message.payload = std::move(payload);
  return message;
}

inline io::TopicInfo Topic(const std::string& schema, io::Provenance provenance = io::Provenance::kMeasured) {
  io::TopicInfo info;
  info.schema_name = schema;
  info.provenance = provenance;
  return info;
}

}  // namespace simcore::testing
