// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `InProcessTransport` -- see `simcore/transport.hpp` for the
///   design note.
/// @author Pavan Karimajji

#include "simcore/transport.hpp"

#include <algorithm>

namespace simcore::transport {

InProcessTransport::InProcessTransport(std::size_t depth) : ring_(depth) {}

void InProcessTransport::Publish(uint64_t tickIndex, const std::string& portName,
                                  const uint8_t* data, std::size_t size) {
  std::lock_guard<std::mutex> lock(mutex_);
  Slot& slot = ring_[writeIndex_];
  bool wasUnread = slot.unread;
  slot.tick = tickIndex;
  slot.port = portName;
  slot.bytes.assign(data, data + size);
  slot.unread = true;
  writeIndex_ = (writeIndex_ + 1) % ring_.size();
  if (wasUnread) {
    // Ring was full -- the slot just overwritten was the oldest unread
    // frame, so the read cursor must skip past it rather than re-read
    // stale data on its next turn (SW-0353: the drop is silent to the
    // producer, never a block).
    readIndex_ = writeIndex_;
    ++dropped_;
  } else {
    ++pending_;
  }
}

std::uint64_t InProcessTransport::DroppedFrames() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return dropped_;
}

void InProcessTransport::MarkEngineDead() {
  std::lock_guard<std::mutex> lock(mutex_);
  engineAlive_ = false;
}

adas::transport::AttachResult InProcessTransport::attach(uint32_t clientVersion,
                                                           uint32_t* outEngineVersion) {
  if (outEngineVersion != nullptr) {
    *outEngineVersion = kProtocolVersion;
  }
  if (clientVersion != kProtocolVersion) {
    // Refused before any data crosses (SW-0355) -- attach() itself never
    // touches the ring, so a refused attach is as non-perturbing as a
    // successful one (SW-0352).
    return adas::transport::AttachResult::kVersionMismatch;
  }
  std::lock_guard<std::mutex> lock(mutex_);
  if (!engineAlive_) {
    return adas::transport::AttachResult::kEngineUnavailable;
  }
  attached_ = true;
  return adas::transport::AttachResult::kOk;
}

void InProcessTransport::detach() {
  std::lock_guard<std::mutex> lock(mutex_);
  attached_ = false;
  // Deliberately does not drain or reset the ring -- Publish() keeps
  // running unaffected by attach state (SW-0352's non-perturbing
  // guarantee), and a re-attach simply resumes reading from wherever the
  // ring is.
}

bool InProcessTransport::tryReceive(adas::transport::PortFrame* outFrame) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!attached_ || pending_ == 0) {
    return false;
  }
  lastReturned_ = std::move(ring_[readIndex_]);
  ring_[readIndex_].unread = false;
  readIndex_ = (readIndex_ + 1) % ring_.size();
  --pending_;
  outFrame->tickIndex = lastReturned_.tick;
  outFrame->portName = lastReturned_.port.c_str();
  outFrame->data = lastReturned_.bytes.data();
  outFrame->size = lastReturned_.bytes.size();
  return true;
}

bool InProcessTransport::engineAlive() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return engineAlive_;
}

uint64_t InProcessTransport::lastTickReceived() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return lastReturned_.tick;
}

}  // namespace simcore::transport
