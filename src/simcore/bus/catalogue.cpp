// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `PortCatalogue` (`IMP-0388`, `IMP-0389`, `IMP-0390`; `SW-0388`,
///   `SW-0389`, `SW-0390`). `Resolve` derives the core catalogue from
///   `RunSpec::stages[].ports[]` -- already the manifest data, by the time
///   `simcore` sees it (R-SIM-22) -- rather than authoring or adopting a
///   second description of a port set the build already generated
///   (design `A-4`, `OQ-11`).
/// @author Pavan Karimajji

#include "simcore/bus.hpp"

#include <algorithm>

namespace simcore::bus {

namespace {

std::string NearMatches(const std::vector<PortDecl>& core, const std::vector<PortDecl>& project) {
  std::string list;
  for (const auto& decl : core) {
    if (!list.empty()) list += ", ";
    list += decl.name;
  }
  for (const auto& decl : project) {
    if (!list.empty()) list += ", ";
    list += decl.name;
  }
  return list.empty() ? "(the catalogue is empty)" : list;
}

}  // namespace

Result<PortCatalogue> PortCatalogue::Resolve(const RunSpec& spec) {
  PortCatalogue catalogue;
  for (const auto& stage : spec.stages) {
    for (const auto& port : stage.ports) {
      const auto existing = std::find_if(
          catalogue.core_.begin(), catalogue.core_.end(),
          [&](const PortDecl& decl) { return decl.name == port.name; });
      if (existing != catalogue.core_.end()) {
        if (existing->proto_type != port.proto_type) {
          return Result<PortCatalogue>::Fail(Error{
              Kind::Authoring,
              "one payload type for port \"" + port.name + "\"",
              existing->proto_type + " and " + port.proto_type,
              "simcore::bus::PortCatalogue::Resolve",
              "a port's identity is its own name, independent of which stage declares it -- SW-0389",
          });
        }
        continue;  // same port declared by more than one stage (e.g. a ReqPort and its ProPort): one entry
      }
      catalogue.core_.push_back(PortDecl{port.name, port.proto_type});
    }
  }
  return Result<PortCatalogue>::Ok(std::move(catalogue));
}

Result<const PortDecl*> PortCatalogue::Find(std::string_view qualified_name) const {
  for (const auto& decl : core_) {
    if (decl.name == qualified_name) return Result<const PortDecl*>::Ok(&decl);
  }
  for (const auto& decl : project_) {
    if (decl.name == qualified_name) return Result<const PortDecl*>::Ok(&decl);
  }
  return Result<const PortDecl*>::Fail(Error{
      Kind::Authoring,
      "a port the catalogue declares",
      std::string(qualified_name),
      "simcore::bus::PortCatalogue::Find",
      "known ports: " + NearMatches(core_, project_),
  });
}

Result<bool> PortCatalogue::AddProjectPort(std::string_view project, PortDecl decl) {
  const auto collision = std::find_if(core_.begin(), core_.end(),
                                       [&](const PortDecl& core_decl) { return core_decl.name == decl.name; });
  if (collision != core_.end()) {
    return Result<bool>::Fail(Error{
        Kind::Authoring,
        "a project-local port name not already used by a core port",
        decl.name,
        "simcore::bus::PortCatalogue::AddProjectPort(project=" + std::string(project) + ")",
        "a project-local name may not collide with a core one -- SW-0390",
    });
  }
  project_.push_back(std::move(decl));
  return Result<bool>::Ok(true);
}

std::size_t PortCatalogue::Size() const { return core_.size() + project_.size(); }

}  // namespace simcore::bus
