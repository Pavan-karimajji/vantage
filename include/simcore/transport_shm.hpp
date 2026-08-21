// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `SharedMemoryTransport` (`SI-25`, `WP-27`) -- the second of the two
///   implementations `SW-0349` requires against `modules/interfaces`'
///   `adas::transport::ITransport` (`R-IFACE-1`, `D-5`): the cross-process
///   case (`CN-0051`). Engine and player are separate processes joined by
///   one named shared-memory segment; there is no second, socket-based
///   control channel -- `SW-0351`'s "control and metadata **may** use a
///   separate channel" is optional, and putting the ring header in the
///   same segment as the frame bytes keeps this a single artifact to
///   create, open and tear down, with no second failure mode to handle.
///
///   Same ring-buffer discipline as `InProcessTransport`
///   (`simcore/transport.hpp`): a bounded ring, `Publish()` never blocks
///   and overwrites the oldest **unread** slot once full (`SW-0353`);
///   `attach()`/`detach()` touch no slot (`SW-0352`); a version mismatch
///   is refused before any data crosses (`SW-0355`). What differs from
///   the in-process case is entirely about *where the ring lives*: fixed-
///   size POD slots inside the mapped segment (no `std::string`/
///   `std::vector` -- those own heap memory private to one process's
///   address space and are meaningless shared across a process boundary),
///   lock-free `std::atomic` indices instead of a `std::mutex` (a mutex
///   needs `PTHREAD_PROCESS_SHARED`/a named kernel object either way for
///   the cross-process case, and gains nothing over atomics here because
///   there is exactly one writer and one reader), and liveness detected
///   by asking the OS whether the engine's own recorded process id still
///   exists, rather than a same-process flag (`SW-0356`) -- a real crash,
///   not a simulated one, is what a second process can actually observe.
///
///   `PortFrame::data` returned by `tryReceive` points directly into the
///   mapped segment (no copy -- `SW-0351`'s "the bulk read does not
///   copy"), valid until the next `tryReceive`/`detach` call on this
///   object, same contract `InProcessTransport` gives.
/// @author Pavan Karimajji

#pragma once

#include "transport/ITransport.hpp"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <string>

namespace simcore::transport {

// A frame larger than this is a startup-time configuration error, not a
// silent truncation -- see Publish()'s own contract below. Chosen well
// above any real port's tick payload (R-SIM-2's own inline-vs-referenced
// budget keeps bulk arrays out of a single Prim/port already); revisit
// only against a real oversized port, not speculatively.
inline constexpr std::size_t kShmMaxFrameBytes = 256 * 1024;
inline constexpr std::size_t kShmMaxPortNameLen = 64;

class SharedMemoryTransport : public adas::transport::ITransport {
 public:
  // The engine creates the named segment and owns its lifetime (unlinks it
  // on destruction); a client (player) opens an existing one and never
  // unlinks -- symmetric to a file's writer-creates/reader-opens
  // convention, so two processes launched in either order never race to
  // create the same name.
  enum class Role { kEngine, kClient };

  // name: platform-native shared-object name (POSIX: leading '/', no
  // further slashes; Windows: an opaque CreateFileMapping name) -- the
  // caller picks one, this class does not invent one, matching R-SIM-3a's
  // "never a second place to name a thing" discipline applied to IPC
  // naming. depth: ring capacity in frames, same rationale as
  // InProcessTransport's constructor -- small and deliberate, delaying
  // rather than avoiding SW-0353's drop.
  SharedMemoryTransport(std::string name, Role role, std::size_t depth = 8);
  ~SharedMemoryTransport() override;

  SharedMemoryTransport(const SharedMemoryTransport&) = delete;
  SharedMemoryTransport& operator=(const SharedMemoryTransport&) = delete;

  // Producer side (Role::kEngine only, not part of the ITransport
  // contract): push one port's bytes for one tick. Never blocks; may
  // overwrite the oldest unread slot (SW-0353). A frame over
  // kShmMaxFrameBytes or a port name over kShmMaxPortNameLen - 1 is a
  // caller defect -- asserted, never silently truncated (R-SIM-25's
  // "never a plausible default" applied to a byte budget, not just a
  // display field).
  void Publish(uint64_t tickIndex, const std::string& portName, const uint8_t* data, std::size_t size);

  // Test hook (Role::kEngine only, not part of the ITransport contract):
  // marks the engine's own recorded process id as gone without actually
  // killing this process, so SW-0356's observable contract has a shape a
  // single-process unit test can drive -- same purpose
  // InProcessTransport::MarkEngineDead() serves there. Real cross-process
  // death is detected independently via engineAlive()'s OS-level liveness
  // check on the recorded pid; this hook exists only because a unit test
  // cannot conveniently kill its own process mid-test.
  void SimulateEngineDeath();

  // adas::transport::ITransport
  adas::transport::AttachResult attach(uint32_t clientVersion, uint32_t* outEngineVersion) override;
  void detach() override;
  bool tryReceive(adas::transport::PortFrame* outFrame) override;
  bool engineAlive() const override;
  uint64_t lastTickReceived() const override;

  static constexpr uint32_t kProtocolVersion = 1;

 private:
  struct Header;  // defined in the .cpp -- POD layout mapped into the segment
  struct Slot;    // ditto

  std::string name_;
  Role role_;
  std::size_t depth_;
  bool mapped_ = false;
  bool attached_ = false;
  uint64_t lastTickReceived_ = 0;

#if defined(_WIN32)
  void* mapHandle_ = nullptr;
#else
  int fd_ = -1;
#endif
  void* base_ = nullptr;  // start of the mapped segment (Header, then depth_ Slots)
  Header* header_ = nullptr;
  Slot* slots_ = nullptr;

  std::size_t SegmentBytes() const;
  void MapSegment();    // Role::kEngine: create + zero-init; Role::kClient: open existing
  void UnmapSegment();
};

}  // namespace simcore::transport
