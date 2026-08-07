/* Copyright (c) <ORG>. All Rights Reserved.
 * Proprietary and Confidential.
 * COMPONENT: SIM
 *
 * `ST-D6-1` (docs/sim_implementation_plan.md S-D6, `FR-SIM-46`): "day one,
 * end to end" -- a fresh component library with only a manifest is probed,
 * wired into a five-line pipeline, run, and its outputs appear in a
 * recording, with NO edit anywhere in modules/sim. `echo_stub.c` (the
 * sibling fixture `sim probe`'s own test uses) declares zero ports, so it
 * cannot demonstrate the "outputs appear" half -- this fixture is the same
 * zero-dependency, hand-encoded-manifest technique, extended with exactly
 * ONE output port ("echo") so a resim has something real to record.
 *
 * `adasManifest()` returns a hand-encoded `adas.sil.ComponentManifest`:
 *   field 1 (component, string)          = "echo_stub_with_output"
 *   field 3 (abi_version, int32)         = 1
 *   field 6 (outputs, repeated PortSpec) = [{name: "echo",
 *                                            proto_type: "echo.Echo",
 *                                            max_bytes: 64}]
 * `proto_type` names no real message and `descriptor_set` stays empty
 * (like `echo_stub.c`'s own "everything else defaults absent") -- the
 * claim this fixture proves is that BYTES reach a recording, never that
 * they decode into something meaningful (R-SIM-14: a recording carries
 * raw bytes plus a schema handle; decoding is a consumer's problem, not
 * the pipeline's). `adasExec` writes a fixed 4-byte payload into "echo"
 * every tick, so the recorded topic is never empty.
 */
#include "adas/adas_sil_abi.h"
#include <string.h>

int32_t adasAbiVersion(void) { return ADAS_SIL_ABI_VERSION; }

size_t adasManifest(uint8_t* data, size_t cap) {
  static const uint8_t kManifest[] = {
      0x0A, 0x15, 'e', 'c', 'h', 'o', '_', 's', 't', 'u', 'b', '_',
      'w', 'i', 't', 'h', '_', 'o', 'u', 't', 'p', 'u', 't',    /* field 1: component = "echo_stub_with_output" (21 chars) */
      0x18, 0x01,                                                /* field 3: abi_version = 1 */
      0x32, 0x13,                                                /* field 6: outputs, len=19 */
        0x0A, 0x04, 'e', 'c', 'h', 'o',                           /*   PortSpec.name = "echo" */
        0x12, 0x09, 'e', 'c', 'h', 'o', '.', 'E', 'c', 'h', 'o',  /*   PortSpec.proto_type = "echo.Echo" */
        0x18, 0x40,                                               /*   PortSpec.max_bytes = 64 */
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
  static const uint8_t kEcho[] = { 0xDE, 0xAD, 0xBE, 0xEF };
  if (out != NULL && out->ports != NULL) {
    for (size_t i = 0; i < out->count; ++i) {
      if (out->ports[i].name != NULL && strcmp(out->ports[i].name, "echo") == 0 &&
          out->ports[i].data != NULL && out->ports[i].cap >= sizeof(kEcho)) {
        memcpy(out->ports[i].data, kEcho, sizeof(kEcho));
        out->ports[i].len = sizeof(kEcho);
        out->ports[i].updated = 1;
      }
    }
  }
  return 1;
}

void adasShutdown(void* handle) { (void)handle; }
