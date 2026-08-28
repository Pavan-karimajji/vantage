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

#include <algorithm>

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

// See `io.hpp` for why this exists. Two steps, in this order:
//   1. reduce to the bare port address -- strip surrounding slashes, then
//      every remaining '/' becomes '.'  (so "/p/fn.out" and "p/fn.out" both
//      reduce to "p.fn.out");
//   2. re-spell it as a topic -- prepend '/', and turn only the FIRST '.'
//      back into '/', because a port name may itself contain dots
//      (`<function>.<port>`, R-SIM-4) and those must survive: "p.fn.out"
//      becomes "/p/fn.out", never "/p/fn/out".
// Idempotent by construction: step 2's output fed back through step 1 is
// step 1's own output.
std::string CanonicalTopic(const std::string& raw_topic) {
  std::size_t begin = 0;
  std::size_t end = raw_topic.size();
  while (begin < end && raw_topic[begin] == '/') ++begin;
  while (end > begin && raw_topic[end - 1] == '/') --end;
  std::string out = raw_topic.substr(begin, end - begin);
  std::replace(out.begin(), out.end(), '/', '.');
  out.insert(out.begin(), '/');
  const std::size_t dot = out.find('.');
  if (dot != std::string::npos) out[dot] = '/';
  return out;
}

}  // namespace simcore::io
