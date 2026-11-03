// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SharedRegion` on Windows (`IMP-0072`): `CreateFileMapping` / `MapViewOfFile`. A named mapping
///   lives while any handle is open (`ARCH §14` Q8), so `remove` does nothing and a dead writer's
///   mapping that a reader still holds is reused when its size fits.
/// @author Pavan Karimajji

#include "livemeas/shared_region.hpp"

#include <cstring>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

namespace vantage::livemeas {

namespace {

// The size of a mapped view's region, rounded to a page.
std::size_t ViewSize(void* base) {
  MEMORY_BASIC_INFORMATION info{};
  if (::VirtualQuery(base, &info, sizeof(info)) == 0) return 0;
  return static_cast<std::size_t>(info.RegionSize);
}

}  // namespace

SharedRegion::~SharedRegion() {
  if (base_ != nullptr) ::UnmapViewOfFile(base_);
  if (handle_ != nullptr) ::CloseHandle(static_cast<HANDLE>(handle_));
}

bool SharedRegion::isProcessAlive(std::uint32_t pid) noexcept {
  if (pid == 0) return false;
  HANDLE h = ::OpenProcess(SYNCHRONIZE, FALSE, static_cast<DWORD>(pid));
  if (h == nullptr) return false;
  const DWORD wait = ::WaitForSingleObject(h, 0);
  ::CloseHandle(h);
  return wait == WAIT_TIMEOUT;  // still running
}

std::uint32_t SharedRegion::currentProcessId() noexcept { return static_cast<std::uint32_t>(::GetCurrentProcessId()); }

std::unique_ptr<SharedRegion> SharedRegion::open(const std::string& name, Access access) noexcept {
  try {
    const bool write = access == Access::kReadWrite;
    const DWORD rights = write ? FILE_MAP_ALL_ACCESS : FILE_MAP_READ;
    HANDLE handle = ::OpenFileMappingA(rights, FALSE, name.c_str());
    if (handle == nullptr) return nullptr;
    void* base = ::MapViewOfFile(handle, rights, 0, 0, 0);
    if (base == nullptr) {
      ::CloseHandle(handle);
      return nullptr;
    }
    std::unique_ptr<SharedRegion> region(new SharedRegion());
    region->name_ = name;
    region->base_ = base;
    region->size_ = ViewSize(base);
    region->handle_ = handle;
    return region;
  } catch (...) {
    return nullptr;
  }
}

void SharedRegion::remove(const std::string&) noexcept {
  // A named mapping disappears with its last handle; there is no name to unlink.
}

SharedRegion::Create SharedRegion::createOrReplace(const std::string& name, std::size_t size, HeldProbe held,
                                                   std::unique_ptr<SharedRegion>& out) noexcept {
  try {
    const DWORD high = static_cast<DWORD>(static_cast<std::uint64_t>(size) >> 32);
    const DWORD low = static_cast<DWORD>(size & 0xFFFFFFFFu);
    HANDLE handle = ::CreateFileMappingA(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, high, low, name.c_str());
    if (handle == nullptr) return Create::kFailed;
    const bool existed = ::GetLastError() == ERROR_ALREADY_EXISTS;
    void* base = ::MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, 0);
    if (base == nullptr) {
      ::CloseHandle(handle);
      return Create::kFailed;
    }
    const std::size_t mapped = ViewSize(base);
    if (existed) {
      if (held != nullptr && held(base, mapped)) {
        ::UnmapViewOfFile(base);
        ::CloseHandle(handle);
        return Create::kNameHeld;
      }
      // The dead writer's region is still held by a handle: reuse it when the new size fits.
      if (mapped < size) {
        ::UnmapViewOfFile(base);
        ::CloseHandle(handle);
        return Create::kFailed;
      }
      std::memset(base, 0, mapped);
    }
    std::unique_ptr<SharedRegion> region(new SharedRegion());
    region->name_ = name;
    region->base_ = base;
    region->size_ = size;
    region->handle_ = handle;
    out = std::move(region);
    return existed ? Create::kReplaced : Create::kCreated;
  } catch (...) {
    return Create::kFailed;
  }
}

}  // namespace vantage::livemeas
