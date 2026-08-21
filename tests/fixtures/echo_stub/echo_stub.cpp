// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   echo_stub -- a minimal generic-ABI component for `module_host`'s own
///   tests. Ported verbatim from `sil_host/tests/fixtures/echo_stub/
///   echo_stub.cpp` (same reasoning: `Component::Load`'s tests need a
///   real, resolvable library implementing `adas_sil_abi.h`, not a mock
///   inside the test binary -- `simcore` has no components= test-
///   injection seam any more than `sil_host`'s own `Pipeline` did).
///
///   Empty port set BY DEFAULT. Component name and declared period_ns are
///   read from environment variables at CALL time inside adasManifest()
///   (never cached at load time), so one built DLL serves every test case
///   with no rebuild: ADAS_SIL_TEST_STUB_NAME (default "echo_stub"),
///   ADAS_SIL_TEST_STUB_PERIOD_NS (default "0").
///
///   ONE optional output port, same "read at call time" design, proves
///   `Component::Exec`'s grow-once-and-retry path against a real
///   undersized buffer:
///     ADAS_SIL_TEST_STUB_OUTPUT_PORT (default "" -- no output port at all)
///     ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE (default "test.Echo")
///     ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES (default 64)
///     ADAS_SIL_TEST_STUB_OUTPUT_PERIOD_US (default 0)
///     ADAS_SIL_TEST_STUB_OUTPUT_DUE (default "1"): "0" leaves the port
///       un-updated this call, deliberately host-controlled.
///     ADAS_SIL_TEST_STUB_HANG (default "0"): "1" spins forever inside
///       adasExec() -- proves `Component::Exec`'s `ExecTimeout`/
///       `Quarantine` wiring against a genuinely hung call, the one path
///       `RunWithTimeout`'s own ported unit tests cannot reach through a
///       real ABI boundary.
/// @author Pavan Karimajji

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

#include "Adas__Sil/component_manifest.pb.h"
#include "adas/adas_sil_abi.h"

namespace {

std::string EnvOr(const char* name, const std::string& fallback) {
  const char* value = std::getenv(name);
  return value != nullptr ? std::string(value) : fallback;
}

uint64_t EnvOrU64(const char* name, uint64_t fallback) {
  const char* value = std::getenv(name);
  if (value == nullptr) return fallback;
  try {
    return static_cast<uint64_t>(std::stoull(value));
  } catch (...) {
    return fallback;
  }
}

bool EnvOrBool(const char* name, bool fallback) {
  const char* value = std::getenv(name);
  if (value == nullptr) return fallback;
  return std::string(value) != "0";
}

}  // namespace

extern "C" {

ADAS_SIL_API int32_t adasAbiVersion(void) {
  return ADAS_SIL_ABI_VERSION;
}

ADAS_SIL_API size_t adasManifest(uint8_t* data, size_t cap) {
  ::adas::sil::ComponentManifest manifest;
  manifest.set_component(EnvOr("ADAS_SIL_TEST_STUB_NAME", "echo_stub"));
  manifest.set_version("test");
  manifest.set_abi_version(ADAS_SIL_ABI_VERSION);
  manifest.set_build_id("test");
  manifest.set_period_ns(EnvOrU64("ADAS_SIL_TEST_STUB_PERIOD_NS", 0));
  const std::string outputPort = EnvOr("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "");
  if (!outputPort.empty()) {
    ::adas::sil::PortSpec* spec = manifest.add_outputs();
    spec->set_name(outputPort);
    spec->set_proto_type(EnvOr("ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE", "test.Echo"));
    spec->set_max_bytes(static_cast<uint32_t>(EnvOrU64("ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES", 64)));
    spec->set_period_us(EnvOrU64("ADAS_SIL_TEST_STUB_OUTPUT_PERIOD_US", 0));
  }

  const size_t needed = static_cast<size_t>(manifest.ByteSizeLong());
  if (data == nullptr || cap < needed) {
    return needed;  // the two-call pattern's probe half (adas_sil_abi.h)
  }
  manifest.SerializeToArray(data, static_cast<int>(needed));
  return needed;
}

ADAS_SIL_API void* adasInit(const char* configPath) {
  (void)configPath;  // no real configuration -- always succeeds
  static int dummyHandle = 0;
  return &dummyHandle;
}

ADAS_SIL_API int32_t adasExec(void* handle, double dtS, const AdasPortSet* in, AdasPortSet* out) {
  (void)handle;
  (void)dtS;
  (void)in;
  if (EnvOrBool("ADAS_SIL_TEST_STUB_HANG", false)) {
    // Deliberately never returns -- see ADAS_SIL_TEST_STUB_HANG above.
    // sleep_for (not a spin loop) is the real observable side effect that
    // keeps this from being an as-if-terminating loop under optimization.
    for (;;) {
      std::this_thread::sleep_for(std::chrono::seconds(1));
    }
  }
  if (out == nullptr) {
    return 1;
  }
  const std::string outputPort = EnvOr("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "");
  if (outputPort.empty() || !EnvOrBool("ADAS_SIL_TEST_STUB_OUTPUT_DUE", true)) {
    return 1;
  }
  for (size_t i = 0; i < out->count; ++i) {
    if (out->ports[i].name == nullptr || outputPort != out->ports[i].name) continue;
    static constexpr uint8_t kPayload[] = {0xAB};
    if (out->ports[i].cap >= sizeof(kPayload)) {
      std::memcpy(out->ports[i].data, kPayload, sizeof(kPayload));
      out->ports[i].len = sizeof(kPayload);
    } else {
      out->ports[i].len = sizeof(kPayload);  // undersize -- Component::Exec's own grow-once path
    }
    out->ports[i].updated = 1;
    break;
  }
  return 1;
}

ADAS_SIL_API void adasShutdown(void* handle) {
  (void)handle;
}

}  // extern "C"
