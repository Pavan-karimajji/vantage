// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `UT-EDG-06` (`IMP-0137`, `WP-15`): `BuildModuleReport` reports,
///   as ONE set, every field `Component::ReadManifest` already exposes
///   individually -- against the real `echo_stub` fixture, same reasoning
///   `test_mh_component.cpp` already established for `module_host` itself.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <filesystem>

#include <gtest/gtest.h>

namespace simcore::diagnostics {
namespace {

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

TEST(UtEdg06ModuleReport, EveryFieldPresentAndMatchesTheRealManifest) {
  Result<module_host::Component> loaded = module_host::Component::Load(EchoStubPath());
  ASSERT_TRUE(loaded.ok()) << loaded.error().Format();
  module_host::Component component = std::move(loaded).value();

  const ModuleReportEntry entry = BuildModuleReportEntry("sut", component);
  EXPECT_EQ(entry.stage, "sut");
  EXPECT_EQ(entry.path_opened, EchoStubPath().string());
  // echo_stub's own fixture sets version="test", build_id="test" (see
  // tests/fixtures/echo_stub/echo_stub.cpp) and never sets
  // config_bundle_sha256 -- so that one field alone is "unknown".
  EXPECT_EQ(entry.component_version, "test");
  EXPECT_EQ(entry.build_id, "test");
  EXPECT_NE(entry.abi_version, kUnknown);  // echo_stub reports a real ABI version
  EXPECT_EQ(entry.config_bundle_hash, kUnknown);
}

TEST(UtEdg06ModuleReport, BuildModuleReportCoversEveryComponentKeyedByStageName) {
  Result<module_host::Component> a = module_host::Component::Load(EchoStubPath());
  Result<module_host::Component> b = module_host::Component::Load(EchoStubPath());
  ASSERT_TRUE(a.ok());
  ASSERT_TRUE(b.ok());
  module_host::Component component_a = std::move(a).value();
  module_host::Component component_b = std::move(b).value();

  std::map<std::string, module_host::Component*> components = {{"a", &component_a}, {"b", &component_b}};
  const std::vector<ModuleReportEntry> report = BuildModuleReport(components);
  ASSERT_EQ(report.size(), 2u);
  EXPECT_EQ(report[0].stage, "a");
  EXPECT_EQ(report[1].stage, "b");

  const std::string text = DumpModuleReportText(report);
  EXPECT_NE(text.find("module: a "), std::string::npos);
  EXPECT_NE(text.find("module: b "), std::string::npos);
}

}  // namespace
}  // namespace simcore::diagnostics
