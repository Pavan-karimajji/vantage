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
///     ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA (default "0"): "1" makes
///       `adasManifest()` also populate `descriptor_set` with a real,
///       serialized `FileDescriptorSet` (one message, `abi_test.AbiPort {
///       double value = 1; }`) and makes `adasExec()` emit a genuinely
///       encoded `AbiPort` instead of the single raw byte below --
///       `WP-14a`'s own `UT-ABI-02` needs a component whose manifest
///       carries a real catalogue (`R-SIM-11`) to prove
///       `simcore::abi`'s `PortResolver` against, and no existing fixture
///       did. Overrides `ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE` to
///       "abi_test.AbiPort" while active, since the two must agree.
///       ADAS_SIL_TEST_STUB_OUTPUT_VALUE (default "42"): the `double`
///       encoded into that message.
/// @author Pavan Karimajji

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>
#include <google/protobuf/dynamic_message.h>

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

double EnvOrDouble(const char* name, double fallback) {
  const char* value = std::getenv(name);
  if (value == nullptr) return fallback;
  try {
    return std::stod(value);
  } catch (...) {
    return fallback;
  }
}

// `ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA`'s own catalogue: one file, one
// message, one scalar field -- just enough for `WP-14a`'s `UT-ABI-02` to
// resolve a real `Descriptor` through `simcore::abi`'s `PortResolver` and
// apply a real override, mirroring the synthetic-schema technique
// `tests/unit/test_mut_core.cpp` already uses for `mutate`'s own tests
// (built programmatically, no `.proto` file, no `AdasInterfaces` schema
// dependency).
google::protobuf::FileDescriptorProto BuildAbiTestFileDescriptorProto() {
  google::protobuf::FileDescriptorProto fd;
  fd.set_name("abi_test.proto");
  fd.set_package("abi_test");
  fd.set_syntax("proto3");
  google::protobuf::DescriptorProto* port = fd.add_message_type();
  port->set_name("AbiPort");
  google::protobuf::FieldDescriptorProto* value_field = port->add_field();
  value_field->set_name("value");
  value_field->set_number(1);
  value_field->set_type(google::protobuf::FieldDescriptorProto::TYPE_DOUBLE);
  value_field->set_label(google::protobuf::FieldDescriptorProto::LABEL_OPTIONAL);
  return fd;
}

// A real, reflection-encoded `abi_test.AbiPort{value}` -- its own pool and
// factory are local and thrown away once the bytes are copied out, so this
// never shares state with `adasManifest()`'s own (separately built, same
// shape) `FileDescriptorProto`.
std::vector<uint8_t> EncodeAbiTestPort(double value) {
  google::protobuf::DescriptorPool pool;
  const google::protobuf::FileDescriptorProto fd = BuildAbiTestFileDescriptorProto();
  const google::protobuf::FileDescriptor* file = pool.BuildFile(fd);
  const google::protobuf::Descriptor* descriptor = file->FindMessageTypeByName("AbiPort");
  google::protobuf::DynamicMessageFactory factory(&pool);
  std::unique_ptr<google::protobuf::Message> message(factory.GetPrototype(descriptor)->New());
  const google::protobuf::FieldDescriptor* field = descriptor->FindFieldByName("value");
  message->GetReflection()->SetDouble(message.get(), field, value);
  std::vector<uint8_t> bytes(message->ByteSizeLong());
  message->SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
  return bytes;
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
  const bool realSchema = EnvOrBool("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", false);
  if (!outputPort.empty()) {
    ::adas::sil::PortSpec* spec = manifest.add_outputs();
    spec->set_name(outputPort);
    spec->set_proto_type(realSchema ? "abi_test.AbiPort"
                                     : EnvOr("ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE", "test.Echo"));
    spec->set_max_bytes(static_cast<uint32_t>(EnvOrU64("ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES", 64)));
    spec->set_period_us(EnvOrU64("ADAS_SIL_TEST_STUB_OUTPUT_PERIOD_US", 0));
  }
  if (realSchema) {
    google::protobuf::FileDescriptorSet file_set;
    *file_set.add_file() = BuildAbiTestFileDescriptorProto();
    manifest.set_descriptor_set(file_set.SerializeAsString());
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
  const bool realSchema = EnvOrBool("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", false);
  const std::vector<uint8_t> payload = realSchema
                                            ? EncodeAbiTestPort(EnvOrDouble("ADAS_SIL_TEST_STUB_OUTPUT_VALUE", 42.0))
                                            : std::vector<uint8_t>{0xAB};
  for (size_t i = 0; i < out->count; ++i) {
    if (out->ports[i].name == nullptr || outputPort != out->ports[i].name) continue;
    if (out->ports[i].cap >= payload.size()) {
      std::memcpy(out->ports[i].data, payload.data(), payload.size());
      out->ports[i].len = payload.size();
    } else {
      out->ports[i].len = payload.size();  // undersize -- Component::Exec's own grow-once path
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
