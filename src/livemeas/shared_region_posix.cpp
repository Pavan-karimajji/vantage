// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SharedRegion` on POSIX (`IMP-0072`): `shm_open`, `ftruncate`, `mmap`; the segment code of the
///   retired `src/simcore/transport/shm.cpp`, without its ring.
/// @author Pavan Karimajji

#include "livemeas/shared_region.hpp"

#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace vantage::livemeas {

namespace {
std::string PosixName(const std::string& name) { return !name.empty() && name[0] == '/' ? name : "/" + name; }
}  // namespace

SharedRegion::~SharedRegion() {
  if (base_ != nullptr) ::munmap(base_, size_);
  if (fd_ >= 0) ::close(fd_);
}

bool SharedRegion::isProcessAlive(std::uint32_t pid) noexcept {
  if (pid == 0) return false;
  // kill(pid, 0) sends no signal; EPERM still means the process exists.
  return ::kill(static_cast<pid_t>(pid), 0) == 0 || errno == EPERM;
}

std::uint32_t SharedRegion::currentProcessId() noexcept { return static_cast<std::uint32_t>(::getpid()); }

std::unique_ptr<SharedRegion> SharedRegion::open(const std::string& name, Access access) noexcept {
  try {
    const bool write = access == Access::kReadWrite;
    const int fd = ::shm_open(PosixName(name).c_str(), write ? O_RDWR : O_RDONLY, 0666);
    if (fd < 0) return nullptr;
    struct stat st {};
    if (::fstat(fd, &st) != 0 || st.st_size <= 0) {
      ::close(fd);
      return nullptr;
    }
    void* base = ::mmap(nullptr, static_cast<std::size_t>(st.st_size), write ? PROT_READ | PROT_WRITE : PROT_READ,
                        MAP_SHARED, fd, 0);
    if (base == MAP_FAILED) {
      ::close(fd);
      return nullptr;
    }
    std::unique_ptr<SharedRegion> region(new SharedRegion());
    region->name_ = name;
    region->base_ = base;
    region->size_ = static_cast<std::size_t>(st.st_size);
    region->fd_ = fd;
    return region;
  } catch (...) {
    return nullptr;
  }
}

void SharedRegion::remove(const std::string& name) noexcept {
  try {
    ::shm_unlink(PosixName(name).c_str());
  } catch (...) {
  }
}

SharedRegion::Create SharedRegion::createOrReplace(const std::string& name, std::size_t size, HeldProbe held,
                                                   std::unique_ptr<SharedRegion>& out) noexcept {
  try {
    bool replaced = false;
    {
      std::unique_ptr<SharedRegion> existing = open(name, Access::kReadOnly);
      if (existing != nullptr) {
        if (held != nullptr && held(existing->data(), existing->size())) return Create::kNameHeld;
        remove(name);
        replaced = true;
      }
    }
    const int fd = ::shm_open(PosixName(name).c_str(), O_CREAT | O_EXCL | O_RDWR, 0666);
    if (fd < 0) return Create::kFailed;
    if (::ftruncate(fd, static_cast<off_t>(size)) != 0) {
      ::close(fd);
      ::shm_unlink(PosixName(name).c_str());
      return Create::kFailed;
    }
    void* base = ::mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (base == MAP_FAILED) {
      ::close(fd);
      ::shm_unlink(PosixName(name).c_str());
      return Create::kFailed;
    }
    std::unique_ptr<SharedRegion> region(new SharedRegion());
    region->name_ = name;
    region->base_ = base;
    region->size_ = size;
    region->fd_ = fd;
    out = std::move(region);
    return replaced ? Create::kReplaced : Create::kCreated;
  } catch (...) {
    return Create::kFailed;
  }
}

}  // namespace vantage::livemeas
