/* Copyright (c) <ORG>. All Rights Reserved.
 * Proprietary and Confidential.
 * COMPONENT: SIM
 *
 * A minimal, dependency-free generic-ABI component for `sim probe <lib>`'s
 * own test (S-D6): pure C, no protobuf library, no AdasInterfaces link --
 * `adasManifest()` returns a HAND-ENCODED protobuf wire-format
 * `adas.sil.ComponentManifest` (interfaces/proto/Adas__Sil/
 * component_manifest.proto), just two fields:
 *   field 1 (component, string)    = "echo_stub"
 *   field 3 (abi_version, int32)   = 1
 * Everything else defaults absent/zero on the reading side, which is
 * exactly what CtypesSilComponent's own parse_manifest already treats as
 * "undeclared" (empty inputs/outputs, period_ns=0, project=""). Compiled
 * standalone with `gcc -shared -fPIC` against ONLY
 * `interfaces/include/adas/adas_sil_abi.h` (pure C, zero dependencies by
 * design) -- proof this doesn't need Conan, protobuf, or C++ to exist,
 * only a real dynamic library CtypesSilComponent can genuinely dlopen.
 */
#include "adas/adas_sil_abi.h"
#include <string.h>

int32_t adasAbiVersion(void) { return ADAS_SIL_ABI_VERSION; }

size_t adasManifest(uint8_t* data, size_t cap) {
  static const uint8_t kManifest[] = {
      0x0A, 0x09, 'e', 'c', 'h', 'o', '_', 's', 't', 'u', 'b',  /* field 1: component = "echo_stub" */
      0x18, 0x01,                                               /* field 3: abi_version = 1 */
  };
  const size_t needed = sizeof(kManifest);
  if (data == NULL || cap < needed) return needed;
  memcpy(data, kManifest, needed);
  return needed;
}

void* adasInit(const char* configPath) {
  (void)configPath;
  static int dummy = 0;
  return &dummy;
}

int32_t adasExec(void* handle, double dtS, const AdasPortSet* in, AdasPortSet* out) {
  (void)handle; (void)dtS; (void)in;
  if (out != NULL) out->count = 0;
  return 1;
}

void adasShutdown(void* handle) { (void)handle; }
