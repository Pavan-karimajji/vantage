// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SharedRegion` (`IMP-0072`): one named, process-shared memory region, the platform half of the
///   live measurement writer. Create, map read-write, map read-only, remove the name, and ask
///   whether a process is alive. `createOrReplace` returns `kNameHeld` for a name whose writer lives
///   and replaces a dead writer's. Two implementation files, `shared_region_posix.cpp` and
///   `shared_region_windows.cpp`; the build selects one.
///
///   A region knows nothing of the live measurement's layout: the caller's `HeldProbe` reads the
///   bytes of an existing region and says whether a live writer holds it.
///
///   **Windows:** a named region lives while any handle to it is open, so the region of a dead
///   writer that a reader still holds cannot be deleted. `createOrReplace` then reuses it when its
///   size fits the new one (zeroed first) and otherwise fails.
/// @author Pavan Karimajji

#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

namespace vantage::livemeas {

class SharedRegion {
 public:
  enum class Create { kCreated, kReplaced, kNameHeld, kFailed };
  enum class Access { kReadWrite, kReadOnly };

  /// True when the existing region's bytes say a live writer holds it.
  using HeldProbe = bool (*)(const void* base, std::size_t size);

  ~SharedRegion();
  SharedRegion(const SharedRegion&) = delete;
  SharedRegion& operator=(const SharedRegion&) = delete;

  /// Creates `name` with `size` zeroed bytes. An existing region is first offered to `held`: when it
  /// says a live writer holds it, `kNameHeld`; otherwise the region is replaced (`kReplaced`).
  static Create createOrReplace(const std::string& name, std::size_t size, HeldProbe held,
                                std::unique_ptr<SharedRegion>& out) noexcept;

  /// Maps an existing region; its size is discovered. Null when there is none.
  static std::unique_ptr<SharedRegion> open(const std::string& name, Access access) noexcept;

  /// Removes the name so no new reader maps it; mappings already made stay valid.
  static void remove(const std::string& name) noexcept;

  /// True when a process of that id exists.
  static bool isProcessAlive(std::uint32_t pid) noexcept;

  /// This process's id.
  static std::uint32_t currentProcessId() noexcept;

  void* data() const { return base_; }
  std::size_t size() const { return size_; }
  const std::string& name() const { return name_; }

 private:
  SharedRegion() = default;

  std::string name_;
  void* base_ = nullptr;
  std::size_t size_ = 0;
  void* handle_ = nullptr;  // Windows mapping handle
  int fd_ = -1;             // POSIX descriptor
};

}  // namespace vantage::livemeas
