// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `MetaKind`/`Provenance` naming plus `OriginOrUnknown` (`IMP-0038`,
///   `IMP-0039`). Ports `io/base.Provenance`'s closed set and
///   `io/mcap.py`'s "no provenance block -> `Provenance.UNKNOWN`" rule.
/// @author Pavan Karimajji

#include "simcore/io.hpp"

namespace simcore::io {

std::string ToString(Provenance provenance) {
  switch (provenance) {
    case Provenance::kMeasured:
      return "measured";
    case Provenance::kTruth:
      return "truth";
    case Provenance::kMocked:
      return "mocked";
    case Provenance::kSimulated:
      return "simulated";
    case Provenance::kOverridden:
      return "overridden";
    case Provenance::kUnknown:
      return "unknown";
  }
  return "unknown";  // unreachable for a valid Provenance; never guess a real tag
}

std::string ToString(MetaKind kind) {
  switch (kind) {
    case MetaKind::kRunManifest:
      return "run_manifest";
    case MetaKind::kConfigBundle:
      return "config_bundle";
    case MetaKind::kPluginIdentity:
      return "plugin_identity";
    case MetaKind::kLineage:
      return "lineage";
    case MetaKind::kTolerance:
      return "tolerance";
  }
  return "";  // unreachable for a valid MetaKind
}

// SW-0039: a recording carrying no provenance metadata for a topic yields
// `kUnknown` -- never `kMeasured` (never "the common case" as a default).
Provenance OriginOrUnknown(const std::optional<std::string>& raw) {
  if (!raw.has_value()) return Provenance::kUnknown;
  static const std::pair<const char*, Provenance> kValues[] = {
      {"measured", Provenance::kMeasured}, {"truth", Provenance::kTruth},
      {"mocked", Provenance::kMocked},     {"simulated", Provenance::kSimulated},
      {"overridden", Provenance::kOverridden}, {"unknown", Provenance::kUnknown},
  };
  for (const auto& [name, value] : kValues) {
    if (*raw == name) return value;
  }
  // An unrecognised string is exactly as informative as no string at all --
  // degrade visibly to `kUnknown` rather than raise for a forward-compatible
  // provenance value this build does not yet know about.
  return Provenance::kUnknown;
}

}  // namespace simcore::io
