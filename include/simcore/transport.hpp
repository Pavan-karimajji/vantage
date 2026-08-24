// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `InProcessTransport` (`SI-25`, `WP-27`) -- the first of the two
///   implementations `SW-0349` requires against `modules/interfaces`'
///   `adas::transport::ITransport` (`R-IFACE-1`, `D-5`). The engine hosts
///   the player in the same process (`D-5`: "the engine hosts the player,
///   never the reverse") -- `Publish` and `tryReceive` are plain calls, no
///   marshalling, no wire format.
///
///   A bounded ring buffer, not a single slot: a slow consumer must drop
///   frames rather than force the producer to block or overwrite data the
///   consumer has not read yet mid-read (`SW-0353`). `Publish` overwrites
///   the oldest **unread** slot once the ring is full and never blocks on
///   room being available -- the one guarantee `SW-0353`'s "never applies
///   back-pressure to the run" reduces to at this layer. Each returned
///   `PortFrame`'s `data` points into this object's own owned storage
///   (`SW-0350`: no player component holds a pointer into engine memory),
///   valid until the next `tryReceive`/`detach` call on the frame's own
///   slot.
///
///   The second required implementation (local shared memory, the
///   cross-process case) is `WP-27`'s own remaining scope -- not attempted
///   here.
/// @author Pavan Karimajji

#pragma once

#include "transport/ITransport.hpp"
#include "simcore/transport_publisher.hpp"

#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

namespace simcore::transport {

class InProcessTransport : public adas::transport::ITransport, public TransportPublisher {
 public:
  // depth: ring capacity in frames. A small bound is deliberate -- a large
  // one just delays the drop `SW-0353` requires, it does not avoid it.
  explicit InProcessTransport(std::size_t depth = 8);

  // Producer side (engine only, not part of the ITransport contract): push
  // one port's bytes for one tick. Never blocks; may overwrite the oldest
  // unread slot (SW-0353). Copies `data` into owned storage immediately, so
  // the caller's own buffer is free to change the instant this returns.
  void Publish(uint64_t tickIndex, const std::string& portName, const uint8_t* data, std::size_t size) override;

  // Test/host hook: marks the engine as no longer alive. In-process, "the
  // engine dies" is the host process dying, which takes this object with
  // it -- this exists so SW-0356's observable contract (engineAlive() ==
  // false, lastTickReceived() still queryable) has a real shape to test
  // without actually crashing the process.
  void MarkEngineDead();

  // SW-0353's own "dropped frames are counted and reported" half --
  // incremented exactly where Publish() overwrites an unread slot (the
  // same condition that already moves readIndex_ past it), never
  // estimated separately.
  std::uint64_t DroppedFrames() const;

  // adas::transport::ITransport
  adas::transport::AttachResult attach(uint32_t clientVersion, uint32_t* outEngineVersion) override;
  void detach() override;
  bool tryReceive(adas::transport::PortFrame* outFrame) override;
  bool engineAlive() const override;
  uint64_t lastTickReceived() const override;

  static constexpr uint32_t kProtocolVersion = 1;

 private:
  struct Slot {
    uint64_t tick = 0;
    std::string port;
    std::vector<uint8_t> bytes;
    bool unread = false;
  };

  mutable std::mutex mutex_;
  std::vector<Slot> ring_;
  std::size_t writeIndex_ = 0;
  std::size_t readIndex_ = 0;
  std::size_t pending_ = 0;
  std::uint64_t dropped_ = 0;
  bool attached_ = false;
  bool engineAlive_ = true;
  // Backing storage for the frame most recently handed back by tryReceive
  // -- PortFrame::data must stay valid until the next call (header's own
  // contract), so the slot's bytes are moved here rather than left in the
  // ring where the next Publish() could reuse that slot.
  Slot lastReturned_;
};

}  // namespace simcore::transport
