// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-BUS-20`/`UT-BUS-21`/`UT-BUS-22` (`SW-0388`, `SW-0389`,
///   `SW-0390`): the port catalogue is derived from a `RunSpec`'s own
///   declared ports, a port's identity survives a producer split because
///   `PortDecl` carries no producer field, and a project may extend the
///   catalogue in its own namespace without colliding with a core port.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <string>
#include <utility>
#include <vector>

#include "simcore/bus.hpp"

namespace simcore::bus {
namespace {

SpecPort MakePort(std::string name, std::string proto_type) {
  SpecPort port;
  port.name = std::move(name);
  port.dir = "pro";
  port.kind = "data";
  port.proto_type = std::move(proto_type);
  port.record = "full";
  return port;
}

SpecStage MakeStage(std::string name, std::vector<SpecPort> ports) {
  SpecStage stage;
  stage.name = std::move(name);
  stage.mode = "simulate";
  stage.ports = std::move(ports);
  return stage;
}

// UT-BUS-20: resolve a catalogue at load...
TEST(UtBus20PortCatalogue, ResolvesTheUnionOfEveryStagesDeclaredPorts) {
  RunSpec spec;
  spec.stages.push_back(MakeStage("bsd", {MakePort("bsd.outputs", "adas.bsd.Outputs")}));
  spec.stages.push_back(MakeStage("aeb", {MakePort("aeb.outputs", "adas.aeb.Outputs"),
                                           MakePort("bsd.outputs", "adas.bsd.Outputs")}));  // aeb consumes bsd's ProPort

  const auto resolved = PortCatalogue::Resolve(spec);
  ASSERT_TRUE(resolved.ok());
  EXPECT_EQ(resolved.value().Size(), 2u);  // the shared port collapses to one entry

  const auto found = resolved.value().Find("bsd.outputs");
  ASSERT_TRUE(found.ok());
  EXPECT_EQ(found.value()->proto_type, "adas.bsd.Outputs");
}

// UT-BUS-20: ...then one whose version is out of range -- here, a
// declared payload type that disagrees between the two stages naming the
// same port, which is exactly what a version mismatch would also produce:
// two descriptions of one port that cannot both be resolved.
TEST(UtBus20PortCatalogue, ConflictingProtoTypeForOnePortNameFailsToResolve) {
  RunSpec spec;
  spec.stages.push_back(MakeStage("bsd", {MakePort("bsd.outputs", "adas.bsd.Outputs")}));
  spec.stages.push_back(MakeStage("aeb", {MakePort("bsd.outputs", "adas.bsd.OutputsV2")}));

  const auto resolved = PortCatalogue::Resolve(spec);
  ASSERT_FALSE(resolved.ok());
  EXPECT_EQ(resolved.error().kind, Kind::Authoring);
}

TEST(UtBus20PortCatalogue, UnresolvablePortNamesItAndListsKnownPorts) {
  RunSpec spec;
  spec.stages.push_back(MakeStage("bsd", {MakePort("bsd.outputs", "adas.bsd.Outputs")}));
  const auto resolved = PortCatalogue::Resolve(spec);
  ASSERT_TRUE(resolved.ok());

  const auto found = resolved.value().Find("nonexistent.port");
  ASSERT_FALSE(found.ok());
  EXPECT_NE(found.error().Format().find("nonexistent.port"), std::string::npos);
  EXPECT_NE(found.error().Format().find("bsd.outputs"), std::string::npos);
}

// UT-BUS-21: move a port between two producers -- `PortDecl` carries no
// producer field, so the same port name resolved from two differently-
// shaped RunSpecs (the "before the split" and "after the split" stage
// layouts) yields the identical declaration either way.
TEST(UtBus21ProducerIndependentIdentity, SplittingAComponentLeavesPortIdentityUnchanged) {
  RunSpec before;
  before.stages.push_back(MakeStage("bsd", {MakePort("bsd.outputs", "adas.bsd.Outputs"),
                                             MakePort("bsd.zone_state", "adas.bsd.ZoneState")}));

  RunSpec after;  // "bsd" split into "bsd_left"/"bsd_right"; port names unchanged
  after.stages.push_back(MakeStage("bsd_left", {MakePort("bsd.outputs", "adas.bsd.Outputs")}));
  after.stages.push_back(MakeStage("bsd_right", {MakePort("bsd.zone_state", "adas.bsd.ZoneState")}));

  const auto before_catalogue = PortCatalogue::Resolve(before);
  const auto after_catalogue = PortCatalogue::Resolve(after);
  ASSERT_TRUE(before_catalogue.ok());
  ASSERT_TRUE(after_catalogue.ok());

  for (const char* name : {"bsd.outputs", "bsd.zone_state"}) {
    const auto before_decl = before_catalogue.value().Find(name);
    const auto after_decl = after_catalogue.value().Find(name);
    ASSERT_TRUE(before_decl.ok());
    ASSERT_TRUE(after_decl.ok());
    EXPECT_EQ(before_decl.value()->name, after_decl.value()->name);
    EXPECT_EQ(before_decl.value()->proto_type, after_decl.value()->proto_type);
  }
}

// UT-BUS-22: declare a project-namespaced port...
TEST(UtBus22ProjectNamespace, ProjectLocalPortIsUsableAfterAdding) {
  RunSpec spec;
  spec.stages.push_back(MakeStage("bsd", {MakePort("bsd.outputs", "adas.bsd.Outputs")}));
  const auto resolved = PortCatalogue::Resolve(spec);
  ASSERT_TRUE(resolved.ok());
  PortCatalogue catalogue = resolved.value();  // Result<T>::value() is const-only; mutation needs an owned copy

  auto added = catalogue.AddProjectPort("acme", PortDecl{"acme::custom_signal", "adas.acme.Custom"});
  ASSERT_TRUE(added.ok());

  const auto found = catalogue.Find("acme::custom_signal");
  ASSERT_TRUE(found.ok());
  EXPECT_EQ(found.value()->proto_type, "adas.acme.Custom");
}

// UT-BUS-22: ...then one colliding with a core port.
TEST(UtBus22ProjectNamespace, CollidingWithACorePortIsRefusedNamingBoth) {
  RunSpec spec;
  spec.stages.push_back(MakeStage("bsd", {MakePort("bsd.outputs", "adas.bsd.Outputs")}));
  const auto resolved = PortCatalogue::Resolve(spec);
  ASSERT_TRUE(resolved.ok());
  PortCatalogue catalogue = resolved.value();

  const auto added = catalogue.AddProjectPort("acme", PortDecl{"bsd.outputs", "adas.acme.Impostor"});
  ASSERT_FALSE(added.ok());
  EXPECT_EQ(added.error().kind, Kind::Authoring);
  EXPECT_NE(added.error().Format().find("bsd.outputs"), std::string::npos);
  EXPECT_NE(added.error().Format().find("acme"), std::string::npos);
}

}  // namespace
}  // namespace simcore::bus
