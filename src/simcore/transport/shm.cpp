// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `SharedMemoryTransport` -- see `simcore/transport_shm.hpp` for
///   the design note. POSIX (shm_open/mmap) is the implementation this
///   module actually builds and tests against (this repo's real dev/CI
///   surface is `ubuntu_gcc`); the `_WIN32` branch (CreateFileMapping/
///   MapViewOfFile) compiles for `vs2026` but is unverified here, same
///   "compiles on both, verified live only where testable" posture
///   `R-SIM-24`/`docs/v2` already applies to windowed GL work -- native
///   Windows verification is a follow-on, not attempted in this pass.
/// @author Pavan Karimajji

#include "simcore/transport_shm.hpp"

#include <cassert>
#include <cstring>

#if defined(_WIN32)
#include <windows.h>
#else
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace simcore::transport {

namespace {
constexpr uint32_t kMagic = 0xADA5511Cu;

#if defined(_WIN32)
int64_t CurrentProcessId() { return static_cast<int64_t>(::GetCurrentProcessId()); }
bool ProcessAlive(int64_t pid) {
  if (pid <= 0) {
    return false;
  }
  HANDLE h = ::OpenProcess(SYNCHRONIZE, FALSE, static_cast<DWORD>(pid));
  if (h == nullptr) {
    return false;
  }
  DWORD wait = ::WaitForSingleObject(h, 0);
  ::CloseHandle(h);
  return wait == WAIT_TIMEOUT;  // still running
}
#else
int64_t CurrentProcessId() { return static_cast<int64_t>(::getpid()); }
bool ProcessAlive(int64_t pid) {
  if (pid <= 0) {
    return false;
  }
  // kill(pid, 0) sends no signal -- it only checks existence/permission.
  // EPERM still means the process exists (owned by someone else); any
  // other errno (ESRCH) means it does not.
  return ::kill(static_cast<pid_t>(pid), 0) == 0 || errno == EPERM;
}
#endif
}  // namespace

// Fixed-size POD, mapped directly into the segment -- no STL container
// (heap-owning types are meaningless shared across a process boundary,
// this file's own header comment). std::atomic<T> for a trivially-
// copyable, lock-free-eligible T has the same object representation
// across processes as long as both map the same compiler/ABI, which a
// single build's engine and player both are (R-SIM-11's "no sibling
// checkout" is about generated bindings, not the ABI of this contract).
struct SharedMemoryTransport::Header {
  std::atomic<uint32_t> magic;
  std::atomic<uint32_t> engineVersion;
  std::atomic<uint32_t> depth;
  std::atomic<uint32_t> writeIndex;
  std::atomic<uint32_t> readIndex;
  std::atomic<int64_t> engineAlivePid;  // 0 == no engine / reported dead
  std::atomic<uint64_t> lastPublishedTick;
};

struct SharedMemoryTransport::Slot {
  std::atomic<uint64_t> tick;
  std::atomic<uint32_t> size;
  std::atomic<uint32_t> unread;
  char portName[kShmMaxPortNameLen];
  uint8_t bytes[kShmMaxFrameBytes];
};

SharedMemoryTransport::SharedMemoryTransport(std::string name, Role role, std::size_t depth)
    : name_(std::move(name)), role_(role), depth_(depth) {
  if (role_ == Role::kEngine) {
    // The engine's ring exists the instant the object does, same as
    // InProcessTransport -- Publish() must never wait on a client's
    // attach() (SW-0352).
    MapSegment();
    assert(mapped_ && "engine failed to create its own shared-memory segment");
    header_->magic.store(kMagic, std::memory_order_relaxed);
    header_->engineVersion.store(kProtocolVersion, std::memory_order_relaxed);
    header_->depth.store(static_cast<uint32_t>(depth_), std::memory_order_relaxed);
    header_->writeIndex.store(0, std::memory_order_relaxed);
    header_->readIndex.store(0, std::memory_order_relaxed);
    header_->lastPublishedTick.store(0, std::memory_order_relaxed);
    for (std::size_t i = 0; i < depth_; ++i) {
      slots_[i].unread.store(0, std::memory_order_relaxed);
    }
    // Published last -- everything above must be visible before a client
    // sees a non-zero pid and starts trusting the header (release pairs
    // with engineAlive()'s acquire load).
    header_->engineAlivePid.store(CurrentProcessId(), std::memory_order_release);
  }
  // Role::kClient defers mapping to attach() -- the engine's segment may
  // not exist yet at construction time, and that is an attach()-time
  // AttachResult::kEngineUnavailable, not a constructor-time crash.
}

SharedMemoryTransport::~SharedMemoryTransport() {
  if (role_ == Role::kEngine && mapped_) {
    // An orderly shutdown looks identical to a crash to a still-attached
    // client -- SW-0356 does not distinguish the two, and manufacturing a
    // "clean" signal here would be a second, untested code path.
    header_->engineAlivePid.store(0, std::memory_order_release);
  }
  UnmapSegment();
}

std::size_t SharedMemoryTransport::SegmentBytes() const {
  return sizeof(Header) + depth_ * sizeof(Slot);
}

#if defined(_WIN32)

void SharedMemoryTransport::MapSegment() {
  std::size_t bytes = SegmentBytes();
  DWORD sizeHigh = static_cast<DWORD>(static_cast<uint64_t>(bytes) >> 32);
  DWORD sizeLow = static_cast<DWORD>(bytes & 0xFFFFFFFFu);
  HANDLE handle = nullptr;
  if (role_ == Role::kEngine) {
    handle = ::CreateFileMappingA(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, sizeHigh, sizeLow,
                                   name_.c_str());
  } else {
    handle = ::OpenFileMappingA(FILE_MAP_ALL_ACCESS, FALSE, name_.c_str());
  }
  if (handle == nullptr) {
    return;  // mapped_ stays false -- attach() reports kEngineUnavailable
  }
  void* addr = ::MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, bytes);
  if (addr == nullptr) {
    ::CloseHandle(handle);
    return;
  }
  mapHandle_ = handle;
  base_ = addr;
  header_ = reinterpret_cast<Header*>(base_);
  slots_ = reinterpret_cast<Slot*>(reinterpret_cast<uint8_t*>(base_) + sizeof(Header));
  mapped_ = true;
}

void SharedMemoryTransport::UnmapSegment() {
  if (base_ != nullptr) {
    ::UnmapViewOfFile(base_);
    base_ = nullptr;
    header_ = nullptr;
    slots_ = nullptr;
  }
  if (mapHandle_ != nullptr) {
    ::CloseHandle(static_cast<HANDLE>(mapHandle_));
    mapHandle_ = nullptr;
  }
  // A named CreateFileMapping object is reference-counted by the OS and
  // disappears once every handle closes -- there is no separate "unlink"
  // step the way POSIX shm_open requires.
  mapped_ = false;
}

#else

void SharedMemoryTransport::MapSegment() {
  std::size_t bytes = SegmentBytes();
  if (role_ == Role::kEngine) {
    fd_ = ::shm_open(name_.c_str(), O_CREAT | O_RDWR | O_TRUNC, 0666);
    if (fd_ < 0) {
      return;
    }
    if (::ftruncate(fd_, static_cast<off_t>(bytes)) != 0) {
      ::close(fd_);
      fd_ = -1;
      return;
    }
  } else {
    fd_ = ::shm_open(name_.c_str(), O_RDWR, 0666);
    if (fd_ < 0) {
      return;  // engine hasn't created the segment yet
    }
  }
  void* addr = ::mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
  if (addr == MAP_FAILED) {
    ::close(fd_);
    fd_ = -1;
    return;
  }
  base_ = addr;
  header_ = reinterpret_cast<Header*>(base_);
  slots_ = reinterpret_cast<Slot*>(reinterpret_cast<uint8_t*>(base_) + sizeof(Header));
  mapped_ = true;
}

void SharedMemoryTransport::UnmapSegment() {
  if (base_ != nullptr) {
    ::munmap(base_, SegmentBytes());
    base_ = nullptr;
    header_ = nullptr;
    slots_ = nullptr;
  }
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
  if (role_ == Role::kEngine && mapped_) {
    // Only the creator unlinks -- a client that outlives the engine must
    // never destroy the name a not-yet-started engine could still create.
    ::shm_unlink(name_.c_str());
  }
  mapped_ = false;
}

#endif

void SharedMemoryTransport::Publish(uint64_t tickIndex, const std::string& portName,
                                     const uint8_t* data, std::size_t size) {
  assert(role_ == Role::kEngine && "Publish() is the engine-side producer API");
  assert(mapped_);
  assert(size <= kShmMaxFrameBytes && "frame exceeds the segment's fixed slot budget");
  assert(portName.size() < kShmMaxPortNameLen && "port name exceeds the segment's fixed slot budget");

  uint32_t depth = header_->depth.load(std::memory_order_relaxed);
  uint32_t idx = header_->writeIndex.load(std::memory_order_relaxed);
  Slot& slot = slots_[idx];
  bool wasUnread = slot.unread.load(std::memory_order_acquire) != 0;

  std::memcpy(slot.portName, portName.c_str(), portName.size());
  slot.portName[portName.size()] = '\0';
  std::memcpy(slot.bytes, data, size);
  slot.size.store(static_cast<uint32_t>(size), std::memory_order_relaxed);
  slot.tick.store(tickIndex, std::memory_order_relaxed);
  // Publishes the frame's bytes -- everything above must be visible to a
  // reader that observes unread==1 (pairs with tryReceive's acquire load).
  slot.unread.store(1, std::memory_order_release);

  uint32_t next = (idx + 1) % depth;
  header_->writeIndex.store(next, std::memory_order_relaxed);
  if (wasUnread) {
    // Ring was full -- the slot just overwritten was the oldest unread
    // frame, so the read cursor must skip past it rather than re-read
    // stale data on its next turn (SW-0353: silent to the producer,
    // never a block). Same logic InProcessTransport::Publish uses.
    header_->readIndex.store(next, std::memory_order_release);
  }
  header_->lastPublishedTick.store(tickIndex, std::memory_order_release);
}

void SharedMemoryTransport::SimulateEngineDeath() {
  assert(role_ == Role::kEngine);
  assert(mapped_);
  header_->engineAlivePid.store(0, std::memory_order_release);
}

adas::transport::AttachResult SharedMemoryTransport::attach(uint32_t clientVersion,
                                                              uint32_t* outEngineVersion) {
  if (!mapped_ && role_ == Role::kClient) {
    MapSegment();
  }
  if (!mapped_ || header_->magic.load(std::memory_order_acquire) != kMagic) {
    if (outEngineVersion != nullptr) {
      *outEngineVersion = 0;
    }
    return adas::transport::AttachResult::kEngineUnavailable;
  }

  uint32_t engineVersion = header_->engineVersion.load(std::memory_order_relaxed);
  if (outEngineVersion != nullptr) {
    *outEngineVersion = engineVersion;
  }
  // A depth mismatch means the two ends were built against different
  // wire-layout assumptions for this same segment name -- the same class
  // of refusal SW-0355 asks for, not a separate error path.
  if (clientVersion != engineVersion || header_->depth.load(std::memory_order_relaxed) != depth_) {
    return adas::transport::AttachResult::kVersionMismatch;
  }
  if (!engineAlive()) {
    return adas::transport::AttachResult::kEngineUnavailable;
  }
  attached_ = true;
  return adas::transport::AttachResult::kOk;
}

void SharedMemoryTransport::detach() {
  attached_ = false;
  // Deliberately does not unmap or touch the ring -- Publish() keeps
  // running unaffected by attach state (SW-0352), and a re-attach simply
  // resumes reading from wherever the ring is, same as InProcessTransport.
}

bool SharedMemoryTransport::tryReceive(adas::transport::PortFrame* outFrame) {
  if (!attached_ || !mapped_) {
    return false;
  }
  uint32_t depth = header_->depth.load(std::memory_order_relaxed);
  uint32_t idx = header_->readIndex.load(std::memory_order_relaxed);
  Slot& slot = slots_[idx];
  if (slot.unread.load(std::memory_order_acquire) == 0) {
    return false;
  }
  // Zero-copy -- outFrame->data points straight into the mapped segment
  // (SW-0351: the bulk read does not copy), valid until the next
  // tryReceive/detach call on this object, same contract
  // InProcessTransport gives.
  outFrame->tickIndex = slot.tick.load(std::memory_order_relaxed);
  outFrame->portName = slot.portName;
  outFrame->size = slot.size.load(std::memory_order_relaxed);
  outFrame->data = slot.bytes;
  slot.unread.store(0, std::memory_order_release);
  header_->readIndex.store((idx + 1) % depth, std::memory_order_relaxed);
  lastTickReceived_ = outFrame->tickIndex;
  return true;
}

bool SharedMemoryTransport::engineAlive() const {
  if (!mapped_ || header_->magic.load(std::memory_order_acquire) != kMagic) {
    return false;
  }
  int64_t pid = header_->engineAlivePid.load(std::memory_order_acquire);
  return ProcessAlive(pid);
}

uint64_t SharedMemoryTransport::lastTickReceived() const { return lastTickReceived_; }

}  // namespace simcore::transport
