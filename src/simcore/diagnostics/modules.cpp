// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `BuildModuleReport`/`DumpModuleReportText` (`IMP-0137`, `WP-15`) --
///   reports, as ONE set, the fields `module_host::Component` already
///   exposes individually (`Component::library_path`/`manifest()`): path
///   opened, ABI version, component version, build identity, config-bundle
///   hash. Nobody assembled them together before this; that is this file's
///   whole job (`SW-0137`'s own "Current state PARTIAL").
///
///   `R-SIM-25`/`NR-SIM-4`: an empty proto string field is never printed as
///   `""` -- printed empty is indistinguishable from "read but genuinely
///   blank" vs "the manifest never set this at all", so every field is
///   `kUnknown` unless the manifest actually carries a non-empty value.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <sstream>

namespace simcore::diagnostics {

namespace {
std::string OrUnknown(const std::string& value) { return value.empty() ? kUnknown : value; }
}  // namespace

ModuleReportEntry BuildModuleReportEntry(const std::string& stage_name,
                                          const module_host::Component& component) noexcept {
  ModuleReportEntry entry;
  entry.stage = stage_name;

  const std::filesystem::path path = component.library_path();
  entry.path_opened = path.empty() ? kUnknown : path.string();

  const ::adas::sil::ComponentManifest& manifest = component.manifest();
  // `abi_version` has no proto3 presence bit (a plain `int32`); 0 is never a
  // real ABI version (`SIMCORE_ABI_VERSION`/`ADAS_SIL_ABI_VERSION` both
  // start at 1), so 0 here means "the manifest never reported one".
  entry.abi_version = manifest.abi_version() == 0 ? kUnknown : std::to_string(manifest.abi_version());
  entry.component_version = OrUnknown(manifest.version());
  entry.build_id = OrUnknown(manifest.build_id());
  entry.config_bundle_hash = OrUnknown(manifest.config_bundle_sha256());

  return entry;
}

std::vector<ModuleReportEntry> BuildModuleReport(
    const std::map<std::string, module_host::Component*>& components) noexcept {
  std::vector<ModuleReportEntry> report;
  report.reserve(components.size());
  // `std::map` iteration is already stage-name order -- no separate sort
  // needed to keep this deterministic (UT-A4-12/P-8's own discipline).
  for (const auto& [stage, component] : components) {
    if (component == nullptr) continue;
    report.push_back(BuildModuleReportEntry(stage, *component));
  }
  return report;
}

std::string DumpModuleReportText(const std::vector<ModuleReportEntry>& entries) noexcept {
  std::ostringstream out;
  for (const ModuleReportEntry& entry : entries) {
    out << "module: " << entry.stage << " path=" << entry.path_opened << " abi_version=" << entry.abi_version
        << " component_version=" << entry.component_version << " build_id=" << entry.build_id
        << " config_bundle_hash=" << entry.config_bundle_hash << "\n";
  }
  return out.str();
}

}  // namespace simcore::diagnostics
