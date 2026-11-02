// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `exec_probe` (`WP-09a`, `IMP-0042`; fixture `F-PROBE` of `SYT-RUN-08`, `SYT-THR-02`,
///   `SYT-THR-03`; serves `SYS-0008`, `SYS-0040`, `SYS-0041`): a component on the generic ABI
///   that declares no ports, appends one line on entering and one on leaving every
///   `adasExec()` to a call log, and spins a fixed time in between.
///
///   Its three settings are its bundle's: `adasInit(NULL)` reads
///   `<directory of this library>/config/default.yaml` (`R-SIM-3a`), flat `KEY: value`
///   lines, none of them with a default (a missing key makes `adasInit` return NULL):
///     PROBE_STAGE_NAME  the stage this copy stands for, written to every line
///     PROBE_LOG_FILE    the call log, one append-only write per line (one file may be shared by copies)
///     PROBE_SPIN_MS     how long every call spins, in milliseconds
///   A test puts one copy of this library per path it wants, each with its own `config/`.
///
///   Call-log line: `stage=<name> library=<path> thread=<id> event=enter|exit t_ns=<steady clock ns>`.
///   `t_ns` is a monotonic clock of the probe's own, for ordering lines of one log; it says nothing
///   to the engine, which reads no clock (`SYS-0017`).
/// @author Pavan Karimajji

#include <chrono>
#include <cstdint>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <thread>

#include "Adas__Sil/component_manifest.pb.h"
#include "adas/adas_sil_abi.h"

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define NOGDI
#include <windows.h>
#else
#include <dlfcn.h>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace {

struct Probe {
  std::string stage;
  std::string log_file;
  std::string library;
  std::int64_t spin_ms = 0;
};

void* AnchorOfThisLibrary() { return reinterpret_cast<void*>(&AnchorOfThisLibrary); }

std::string LibraryPath() {
#if defined(_WIN32)
  HMODULE module = nullptr;
  if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                          reinterpret_cast<LPCSTR>(&AnchorOfThisLibrary), &module)) {
    return {};
  }
  char buffer[MAX_PATH];
  const DWORD length = GetModuleFileNameA(module, buffer, MAX_PATH);
  return (length == 0 || length == MAX_PATH) ? std::string() : std::string(buffer, length);
#else
  Dl_info info;
  if (dladdr(AnchorOfThisLibrary(), &info) == 0 || info.dli_fname == nullptr) return {};
  return info.dli_fname;
#endif
}

std::string DirectoryOf(const std::string& path) {
  const std::size_t cut = path.find_last_of("/\\");
  return cut == std::string::npos ? std::string() : path.substr(0, cut);
}

bool ReadBundle(const std::string& file, Probe& probe) {
  std::ifstream in(file);
  if (!in) return false;
  bool have_stage = false, have_log = false, have_spin = false;
  std::string line;
  while (std::getline(in, line)) {
    const std::size_t colon = line.find(':');
    if (colon == std::string::npos) continue;
    const std::string key = line.substr(0, colon);
    std::string value = line.substr(colon + 1);
    const std::size_t first = value.find_first_not_of(" \t");
    const std::size_t last = value.find_last_not_of(" \t\r\n");
    value = first == std::string::npos ? std::string() : value.substr(first, last - first + 1);
    if (key == "PROBE_STAGE_NAME") {
      probe.stage = value;
      have_stage = true;
    } else if (key == "PROBE_LOG_FILE") {
      probe.log_file = value;
      have_log = true;
    } else if (key == "PROBE_SPIN_MS") {
      try {
        probe.spin_ms = std::stoll(value);
        have_spin = true;
      } catch (...) {
        return false;
      }
    }
  }
  return have_stage && have_log && have_spin;
}

std::int64_t NowNs() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch())
      .count();
}

// One line is one write on a handle opened for appending only, which the OS places at the end of
// the file atomically; two copies (two threads) sharing one log never overwrite each other.
void Append(const Probe& probe, const char* event) {
  std::ostringstream text;
  text << "stage=" << probe.stage << " library=" << probe.library << " thread=" << std::this_thread::get_id()
       << " event=" << event << " t_ns=" << NowNs() << '\n';
  const std::string line = text.str();
#if defined(_WIN32)
  const HANDLE file = CreateFileA(probe.log_file.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                                  OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (file == INVALID_HANDLE_VALUE) return;
  DWORD written = 0;
  WriteFile(file, line.data(), static_cast<DWORD>(line.size()), &written, nullptr);
  CloseHandle(file);
#else
  const int file = open(probe.log_file.c_str(), O_WRONLY | O_APPEND | O_CREAT, 0644);
  if (file < 0) return;
  const ssize_t written = write(file, line.data(), line.size());
  (void)written;
  close(file);
#endif
}

}  // namespace

extern "C" {

ADAS_SIL_API int32_t adasAbiVersion(void) { return ADAS_SIL_ABI_VERSION; }

ADAS_SIL_API size_t adasManifest(uint8_t* data, size_t cap) {
  ::adas::sil::ComponentManifest manifest;
  manifest.set_component("exec_probe");
  manifest.set_version("test");
  manifest.set_abi_version(ADAS_SIL_ABI_VERSION);
  manifest.set_build_id("test");
  const size_t needed = static_cast<size_t>(manifest.ByteSizeLong());
  if (data == nullptr || cap < needed) return needed;  // the two-call pattern's probe half
  manifest.SerializeToArray(data, static_cast<int>(needed));
  return needed;
}

ADAS_SIL_API void* adasInit(const char* configPath) {
  try {
    auto probe = std::make_unique<Probe>();
    probe->library = LibraryPath();
    const std::string bundle_dir = configPath != nullptr ? std::string(configPath) : DirectoryOf(probe->library) + "/config";
    if (probe->library.empty() || !ReadBundle(bundle_dir + "/default.yaml", *probe)) return nullptr;
    return probe.release();
  } catch (...) {
    return nullptr;
  }
}

ADAS_SIL_API int32_t adasExec(void* handle, double /*dtS*/, const AdasPortSet* /*in*/, AdasPortSet* /*out*/) {
  if (handle == nullptr) return 0;
  try {
    const Probe& probe = *static_cast<Probe*>(handle);
    Append(probe, "enter");
    const std::int64_t until = NowNs() + probe.spin_ms * 1'000'000;
    while (NowNs() < until) {
    }
    Append(probe, "exit");
    return 1;
  } catch (...) {
    return 0;
  }
}

ADAS_SIL_API void adasShutdown(void* handle) { delete static_cast<Probe*>(handle); }

}  // extern "C"
