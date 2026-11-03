// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `held_probe` (`WP-15`, `IMP-0088`; the stage `F-LM-HELD` of `VANTAGE_Test_Spec.md` adds to a case,
///   serves `SYS-0058`): a component on the generic ABI that nobody reads, whose first call returns
///   only once a gate file exists, so a test can attach a reader to a held run.
///
///   Ports: inputs `control` (`adas.common.CycleControl`) and `in` (`adas.lab.LabSample`); outputs
///   `refSync` (`adas.common.RefSync`, one entry naming the `in` sample read) and `compState`
///   (`adas.df.CompState`, RUNNING). Each output's `measurement_counter`, `source_timestamp_us`,
///   `cycle_counter` and `sig_status` are copied from its control.
///
///   Its one setting is its bundle's: `adasInit(NULL)` reads `<directory of this library>/config/default.yaml`
///   (`R-SIM-3a`), a flat `KEY: value` line, with no default (a missing key makes `adasInit` return NULL):
///     PROBE_GATE_FILE  the file whose existence releases the first call
/// @author Pavan Karimajji

#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <memory>
#include <string>
#include <thread>

#include "Adas__Sil/component_manifest.pb.h"
#include "adas/adas_sil_abi.h"
#include "common/cycle_control.pb.h"
#include "common/ref_sync.pb.h"
#include "common/comp_state.pb.h"
#include "lab/lab_sample.pb.h"

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define NOGDI
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace {

struct Probe {
  std::string gate_file;
  bool released = false;
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
  std::string line;
  while (std::getline(in, line)) {
    const std::size_t colon = line.find(':');
    if (colon == std::string::npos || line.substr(0, colon) != "PROBE_GATE_FILE") continue;
    std::string value = line.substr(colon + 1);
    const std::size_t first = value.find_first_not_of(" \t");
    const std::size_t last = value.find_last_not_of(" \t\r\n");
    probe.gate_file = first == std::string::npos ? std::string() : value.substr(first, last - first + 1);
    return !probe.gate_file.empty();
  }
  return false;
}

bool FileExists(const std::string& path) {
  std::ifstream in(path);
  return static_cast<bool>(in);
}

const AdasPort* Find(const AdasPortSet* set, const char* name) {
  if (set == nullptr) return nullptr;
  for (std::size_t i = 0; i < set->count; ++i) {
    if (set->ports[i].name != nullptr && std::strcmp(set->ports[i].name, name) == 0) return &set->ports[i];
  }
  return nullptr;
}

AdasPort* FindOut(AdasPortSet* set, const char* name) {
  if (set == nullptr) return nullptr;
  for (std::size_t i = 0; i < set->count; ++i) {
    if (set->ports[i].name != nullptr && std::strcmp(set->ports[i].name, name) == 0) return &set->ports[i];
  }
  return nullptr;
}

void Put(AdasPortSet* out, const char* name, const std::string& bytes) {
  AdasPort* port = FindOut(out, name);
  if (port == nullptr) return;
  if (port->cap >= bytes.size()) std::memcpy(port->data, bytes.data(), bytes.size());
  port->len = bytes.size();
  port->updated = 1;
}

void CopyHeader(const adas::common::SignalHeader& from, adas::common::SignalHeader* to) {
  to->set_source_timestamp_us(from.source_timestamp_us());
  to->set_measurement_counter(from.measurement_counter());
  to->set_cycle_counter(from.cycle_counter());
  to->set_sig_status(from.sig_status());
}

}  // namespace

extern "C" {

ADAS_SIL_API int32_t adasAbiVersion(void) { return ADAS_SIL_ABI_VERSION; }

ADAS_SIL_API size_t adasManifest(uint8_t* data, size_t cap) {
  ::adas::sil::ComponentManifest manifest;
  manifest.set_component("held_probe");
  manifest.set_version("test");
  manifest.set_abi_version(ADAS_SIL_ABI_VERSION);
  manifest.set_build_id("test");
  ::adas::sil::PortSpec* control = manifest.add_inputs();
  control->set_name("control");
  control->set_proto_type("adas.common.CycleControl");
  control->set_max_bytes(64);
  ::adas::sil::PortSpec* in = manifest.add_inputs();
  in->set_name("in");
  in->set_proto_type("adas.lab.LabSample");
  in->set_max_bytes(64);
  ::adas::sil::PortSpec* ref_sync = manifest.add_outputs();
  ref_sync->set_name("refSync");
  ref_sync->set_proto_type("adas.common.RefSync");
  ref_sync->set_max_bytes(128);
  ::adas::sil::PortSpec* comp_state = manifest.add_outputs();
  comp_state->set_name("compState");
  comp_state->set_proto_type("adas.df.CompState");
  comp_state->set_max_bytes(128);
  const size_t needed = static_cast<size_t>(manifest.ByteSizeLong());
  if (data == nullptr || cap < needed) return needed;  // the two-call pattern's probe half
  manifest.SerializeToArray(data, static_cast<int>(needed));
  return needed;
}

ADAS_SIL_API void* adasInit(const char* configPath) {
  try {
    auto probe = std::make_unique<Probe>();
    const std::string library = LibraryPath();
    const std::string bundle_dir = configPath != nullptr ? std::string(configPath) : DirectoryOf(library) + "/config";
    if (library.empty() || !ReadBundle(bundle_dir + "/default.yaml", *probe)) return nullptr;
    return probe.release();
  } catch (...) {
    return nullptr;
  }
}

ADAS_SIL_API int32_t adasExec(void* handle, double /*dtS*/, const AdasPortSet* in, AdasPortSet* out) {
  if (handle == nullptr) return 0;
  try {
    Probe& probe = *static_cast<Probe*>(handle);
    if (!probe.released) {
      while (!FileExists(probe.gate_file)) std::this_thread::sleep_for(std::chrono::milliseconds(5));
      probe.released = true;
    }
    adas::common::CycleControl control;
    const AdasPort* control_port = Find(in, "control");
    if (control_port == nullptr || control_port->data == nullptr ||
        !control.ParseFromArray(control_port->data, static_cast<int>(control_port->len))) {
      return 0;
    }
    adas::common::RefSync ref_sync;
    CopyHeader(control.sig_header(), ref_sync.mutable_sig_header());
    const AdasPort* sample_port = Find(in, "in");
    adas::lab::LabSample sample;
    if (sample_port != nullptr && sample_port->valid != 0 && sample_port->data != nullptr &&
        sample.ParseFromArray(sample_port->data, static_cast<int>(sample_port->len))) {
      adas::common::RefSyncEntry* entry = ref_sync.add_inputs();
      entry->set_port("in");
      entry->set_measurement_counter(sample.sig_header().measurement_counter());
      entry->set_source_timestamp_us(sample.sig_header().source_timestamp_us());
      entry->set_cycle_counter(sample.sig_header().cycle_counter());
      entry->set_sig_status(sample.sig_header().sig_status());
    }
    adas::df::CompState comp_state;
    CopyHeader(control.sig_header(), comp_state.mutable_sig_header());
    comp_state.set_function("held_probe");
    comp_state.set_state(adas::df::CompState::RUNNING);
    Put(out, "refSync", ref_sync.SerializeAsString());
    Put(out, "compState", comp_state.SerializeAsString());
    return 1;
  } catch (...) {
    return 0;
  }
}

ADAS_SIL_API void adasShutdown(void* handle) { delete static_cast<Probe*>(handle); }

}  // extern "C"
