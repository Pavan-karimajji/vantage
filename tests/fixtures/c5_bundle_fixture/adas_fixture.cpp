// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
// @author Pavan Karimajji
//
// S-C5, ST-C5-1 (Python-facing half): a minimal generic-ABI shared library
// implementing ONLY adasInit(NULL)'s bundle resolution and
// adasManifest()'s config_bundle_sha256 reporting -- the same two
// mechanisms modules/df/src/platform/df_sil/df_interface_c.cpp implements
// for real, mirrored here in ~60 dependency-free lines (no yaml-cpp, no
// protobuf, no df) so this environment (no Conan/C++ toolchain for a real
// df_sil build) can still prove the mechanism against a real dlopen'd
// library on a real filesystem. Hand-encodes the two ComponentManifest
// fields it needs directly in protobuf wire format (tag/varint-len/bytes)
// rather than linking libprotobuf, deliberately - this file exists to be
// small and dependency-free, not to be a second manifest builder.
//
// NOT a component under test, NOT df, NOT checked into any component's
// real build - lives only under tests/fixtures/, compiled on demand by
// tests/system/test_c5_relocatability.py.

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include <dlfcn.h>

namespace {

void appendVarint(std::vector<uint8_t>& out, uint64_t value) {
  while (value >= 0x80) {
    out.push_back(static_cast<uint8_t>(value) | 0x80);
    value >>= 7;
  }
  out.push_back(static_cast<uint8_t>(value));
}

void appendLenDelimited(std::vector<uint8_t>& out, int fieldNumber, const std::string& value) {
  appendVarint(out, (static_cast<uint64_t>(fieldNumber) << 3) | 2);  // wire type 2: LEN
  appendVarint(out, value.size());
  out.insert(out.end(), value.begin(), value.end());
}

std::filesystem::path resolveOwnLibraryDir() {
  Dl_info info{};
  if (dladdr(reinterpret_cast<void*>(&resolveOwnLibraryDir), &info) == 0 || info.dli_fname == nullptr) {
    return {};
  }
  return std::filesystem::path(info.dli_fname).parent_path();
}

std::string readBundleShaIfPresent() {
  const auto libDir = resolveOwnLibraryDir();
  if (libDir.empty()) {
    return "";
  }
  std::ifstream in(libDir / "config" / "bundle.sha256");
  std::string digest;
  if (in && std::getline(in, digest)) {
    return digest;
  }
  return "";
}

}  // namespace

extern "C" {

int32_t adasAbiVersion(void) {
  return 1;  // ADAS_SIL_ABI_VERSION (contracts/component.py)
}

size_t adasManifest(uint8_t* data, size_t cap) {
  std::vector<uint8_t> bytes;
  appendLenDelimited(bytes, 1, "fixture");  // ComponentManifest.component
  const std::string sha = readBundleShaIfPresent();
  if (!sha.empty()) {
    appendLenDelimited(bytes, 8, sha);  // ComponentManifest.config_bundle_sha256
  }
  if (data != nullptr && bytes.size() <= cap) {
    std::memcpy(data, bytes.data(), bytes.size());
  }
  return bytes.size();
}

void* adasInit(const char* configPath) {
  if (configPath != nullptr && configPath[0] != '\0') {
    return std::malloc(1);  // tier 1: explicit path always "succeeds" here
  }
  const auto libDir = resolveOwnLibraryDir();
  if (libDir.empty()) {
    return nullptr;
  }
  std::error_code ec;
  if (!std::filesystem::is_directory(libDir / "config", ec)) {
    return nullptr;  // tier 3: no bundle packed beside this library
  }
  return std::malloc(1);  // tier 2: bundle resolved
}

int32_t adasExec(void*, double, const void*, void*) {
  return 1;  // unused by this test - present only so ctypes binding succeeds
}

void adasShutdown(void* handle) {
  std::free(handle);
}

}  // extern "C"
