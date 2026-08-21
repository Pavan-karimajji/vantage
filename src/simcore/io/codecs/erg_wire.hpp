// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `SM-05a`: a minimal, generic protobuf wire-format field walker, used
///   by `erg.cpp` to read `adas.sil.ComponentManifest`/`PortSpec` fields
///   out of a manifest sidecar's raw bytes **without linking the compiled
///   `AdasInterfaces` classes** -- `modules/sim`'s own `conf/build.yml`
///   comment states `simcore` requires nothing first-party, and
///   `interfaces` is first-party. This is not a second, competing
///   `.proto` definition (`R-IFACE-1` stays intact): it dispatches by
///   **field number and wire type alone**, the same forward/backward-
///   compatible guarantee protobuf's own generated code gives, and knows
///   nothing about `ComponentManifest`'s field *names* or *semantics* --
///   the caller (`erg.cpp`) supplies those.
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <functional>
#include <string_view>

namespace simcore::io::codecs::erg_detail {

// One decoded top-level field. `wire_type` follows the protobuf wire
// format (0=VARINT, 1=I64, 2=LEN, 5=I32) -- 3/4 (deprecated START_GROUP/
// END_GROUP) are never emitted here since proto3 never generates them.
struct WireField {
  int field_number = 0;
  int wire_type = 0;
  std::uint64_t varint_value = 0;   // wire_type == 0
  std::string_view bytes_value;     // wire_type == 2 (LEN): string/bytes/submessage
};

// Walks every top-level field in `data`, calling `visit` once per field in
// wire order. A field number the caller does not care about is still
// visited (never silently absorbed) -- the caller's own `visit` decides
// what to keep, matching `WalkFields`'s only job: turn bytes into a
// sequence of (field, wire type, value) triples, nothing more. Returns
// `false` on a malformed byte stream (a truncated varint, a LEN whose
// declared length overruns `data`) -- never a partial silent success.
bool WalkFields(std::string_view data, const std::function<void(const WireField&)>& visit);

}  // namespace simcore::io::codecs::erg_detail
