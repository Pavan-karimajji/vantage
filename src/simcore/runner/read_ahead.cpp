// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `ReadAhead` (`IMP-0026`, `WP-05`): every `sources[]` file read through
///   `io::Reader::ReadRange`, merged by reception time then `sources[]` order
///   (a tie inside one file keeps file order), as far as the readiness limit
///   past the instant being processed. `Find` searches by
///   `measurement_counter`; the time rule never calls it. `RecordedReference`
///   (below) keeps the recorded messages of the ports a `simulate` stage
///   re-produces, for refSync selection and the divergence latch.
/// @author Pavan Karimajji

#include <algorithm>

#include "adas/counter.hpp"
#include "simcore/runner.hpp"

namespace simcore::runner {

namespace {

// One `ReadRange` batch when the caller bounds nothing: the read-ahead is
// streaming, so it never asks a codec for a whole file at once.
constexpr std::size_t kDefaultBatchMessages = 64;

}  // namespace

ReadAhead::ReadAhead(std::vector<io::Reader*> readers, io::ReadBounds bounds)
    : readers_(std::move(readers)), bounds_(bounds) {
  if (bounds_.max_messages == 0 && bounds_.max_bytes == 0 && bounds_.max_span_ns == 0) {
    bounds_.max_messages = kDefaultBatchMessages;
  }
  carry_.resize(readers_.size());
  reader_drained_.assign(readers_.size(), false);
  drained_ = readers_.empty();
}

void ReadAhead::Refill(std::size_t reader) {
  if (reader_drained_[reader]) return;
  io::Batch batch = readers_[reader]->ReadRange(bounds_);
  if (batch.exhausted) reader_drained_[reader] = true;
  for (io::RawMessage& message : batch.messages) {
    if (floor_ns_.has_value() && message.log_time_ns < *floor_ns_) continue;
    if (byte_counter_ != nullptr) {
      byte_counter_->Observe(message.topic, message.payload.size());
    } else {
      read_before_counter_[message.topic] += message.payload.size();
    }
    carry_[reader].push_back(std::move(message));
  }
}

void ReadAhead::SetByteCounter(diagnostics::ByteCounter* byte_counter) {
  byte_counter_ = byte_counter;
  // What `Construct` already read to learn the recording's first instant.
  if (byte_counter_ != nullptr) {
    for (const auto& [topic, bytes] : read_before_counter_) byte_counter_->Observe(topic, bytes);
  }
  read_before_counter_.clear();
}

void ReadAhead::Fill(std::size_t instants) {
  while (instants_.size() <= instants) {
    // Every reader that still can must show its next message before the
    // earliest one is known.
    for (std::size_t i = 0; i < readers_.size(); ++i) {
      while (carry_[i].empty() && !reader_drained_[i]) Refill(i);
    }
    std::optional<std::size_t> pick;
    for (std::size_t i = 0; i < readers_.size(); ++i) {
      if (carry_[i].empty()) continue;
      if (!pick.has_value() || carry_[i].front().log_time_ns < carry_[*pick].front().log_time_ns) pick = i;
    }
    if (!pick.has_value()) {
      drained_ = true;
      return;
    }
    io::RawMessage message = std::move(carry_[*pick].front());
    carry_[*pick].pop_front();
    const std::int64_t time_ns = message.log_time_ns;
    if (!first_time_ns_.has_value()) first_time_ns_ = time_ns;
    last_time_ns_ = time_ns;
    if (instants_.empty() || instants_.back().time_ns != time_ns) {
      instants_.push_back(AheadInstant{time_ns, {}});
    }
    AheadMessage ahead;
    ahead.port = TopicToPortName(message.topic);
    ahead.source_index = *pick;
    ahead.message = std::move(message);
    instants_.back().messages.push_back(std::move(ahead));
  }
}

AheadInstant ReadAhead::TakeFront() {
  AheadInstant front = std::move(instants_.front());
  instants_.pop_front();
  return front;
}

const AheadMessage* ReadAhead::Find(const std::string& port, std::uint32_t counter,
                                    const google::protobuf::Descriptor* descriptor) const {
  for (const AheadInstant& instant : instants_) {
    for (const AheadMessage& message : instant.messages) {
      if (message.port != port) continue;
      const bus::SignalHeader header = bus::ReadSignalHeader(message.message.payload, descriptor);
      if (!header.measurement_counter.has_value()) continue;
      const std::int32_t distance = adas::common::counterDistance(counter, header.measurement_counter.value());
      if (distance == 0) return &message;
    }
  }
  return nullptr;
}

std::vector<const AheadMessage*> ReadAhead::OnPort(const std::string& port) const {
  std::vector<const AheadMessage*> found;
  for (const AheadInstant& instant : instants_) {
    for (const AheadMessage& message : instant.messages) {
      if (message.port == port) found.push_back(&message);
    }
  }
  return found;
}

void ReadAhead::Seek(std::int64_t to_ns) {
  instants_.clear();
  for (std::size_t i = 0; i < readers_.size(); ++i) {
    carry_[i].clear();
    reader_drained_[i] = false;
    readers_[i]->Seek(to_ns);
  }
  drained_ = readers_.empty();
  floor_ns_ = to_ns;
}

void ReadAhead::Stop() {
  instants_.clear();
  for (std::size_t i = 0; i < readers_.size(); ++i) carry_[i].clear();
  drained_ = true;
}

// ---------------------------------------------------------------------------
// RecordedReference
// ---------------------------------------------------------------------------

void RecordedReference::Declare(const std::string& port, std::size_t depth,
                                const google::protobuf::Descriptor* descriptor) {
  Port& slot = held_[port];
  slot.depth = depth < 1 ? std::size_t{1} : depth;
  slot.descriptor = descriptor;
}

void RecordedReference::Add(const std::string& port, std::int64_t time_ns, const std::vector<std::uint8_t>& payload) {
  const auto it = held_.find(port);
  if (it == held_.end()) return;
  Port& slot = it->second;
  Held entry;
  entry.time_ns = time_ns;
  entry.payload = payload;
  entry.counter = bus::ReadSignalHeader(payload, slot.descriptor).measurement_counter;
  slot.held.push_back(std::move(entry));
  while (slot.held.size() > slot.depth) slot.held.pop_front();
}

const std::vector<std::uint8_t>* RecordedReference::Find(const std::string& port, std::uint32_t counter) const {
  const auto it = held_.find(port);
  if (it == held_.end()) return nullptr;
  for (auto held = it->second.held.rbegin(); held != it->second.held.rend(); ++held) {
    if (!held->counter.has_value()) continue;
    const std::int32_t distance = adas::common::counterDistance(counter, held->counter.value());
    if (distance == 0) return &held->payload;
  }
  return nullptr;
}

const std::vector<std::uint8_t>* RecordedReference::AtTime(const std::string& port, std::int64_t time_ns) const {
  const auto it = held_.find(port);
  if (it == held_.end()) return nullptr;
  for (auto held = it->second.held.rbegin(); held != it->second.held.rend(); ++held) {
    if (held->time_ns == time_ns) return &held->payload;
  }
  return nullptr;
}

void RecordedReference::Clear() {
  for (auto& [port, slot] : held_) slot.held.clear();
}

}  // namespace simcore::runner
