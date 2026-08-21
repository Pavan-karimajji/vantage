// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `Component`/`Lifecycle`/`Quarantine`/`Dso` -- against the real
///   `echo_stub` fixture (tests/fixtures/echo_stub), same reasoning
///   `sil_host`'s own `Pipeline::Load` tests used it: a real, resolvable
///   library implementing `adas_sil_abi.h`, not a mock inside the test
///   binary.
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#include <cstdlib>
#include <filesystem>

#include <gtest/gtest.h>

using simcore::module_host::Component;
using simcore::module_host::Dso;
using simcore::module_host::ExecTimeout;
using simcore::module_host::Phase;
using simcore::module_host::PortMap;

namespace {

class EnvGuard {
 public:
  EnvGuard(const char* name, const std::string& value) : name_(name) {
#if defined(_WIN32)
  _putenv_s(name, value.c_str());
#else
  setenv(name, value.c_str(), 1);
#endif
  }
  ~EnvGuard() {
#if defined(_WIN32)
  _putenv_s(name_, "");
#else
  unsetenv(name_);
#endif
  }

 private:
  const char* name_;
};

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

}  // namespace

TEST(MhComponent, LoadReadsTheRealManifestOverTheAbi) {
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "mh_echo");
  auto result = Component::Load(EchoStubPath());
  ASSERT_TRUE(result.ok()) << result.error().Format();
  EXPECT_EQ(result.value().name(), "mh_echo");
  EXPECT_EQ(result.value().phase(), Phase::Loaded);
}

TEST(MhComponent, LoadFailsNamingEveryMissingCandidate) {
  auto result = Component::Load("/no/such/library.so");
  ASSERT_FALSE(result.ok());
  EXPECT_EQ(result.error().kind, simcore::Kind::Environment);
}

TEST(MhComponent, InitThenExecRunsUnderTheDeclaredLifecycle) {
  auto loaded = Component::Load(EchoStubPath());
  ASSERT_TRUE(loaded.ok()) << loaded.error().Format();
  Component component = std::move(loaded).value();

  auto init_result = component.Init();
  ASSERT_TRUE(init_result.ok()) << init_result.error().Format();
  EXPECT_EQ(component.phase(), Phase::Initialized);

  auto exec_result = component.Exec(50'000'000, PortMap{});
  ASSERT_TRUE(exec_result.ok()) << exec_result.error().Format();

  auto shutdown_result = component.Shutdown();
  ASSERT_TRUE(shutdown_result.ok()) << shutdown_result.error().Format();
  EXPECT_EQ(component.phase(), Phase::ShutdownDone);
}

TEST(MhComponent, ExecBeforeInitIsRefusedNamingTheMissingCall) {
  auto loaded = Component::Load(EchoStubPath());
  ASSERT_TRUE(loaded.ok()) << loaded.error().Format();
  Component component = std::move(loaded).value();

  auto exec_result = component.Exec(50'000'000, PortMap{});
  ASSERT_FALSE(exec_result.ok());
  EXPECT_EQ(exec_result.error().kind, simcore::Kind::Internal);
}

TEST(MhComponent, ResetAllowsReInitAfterShutdownWithoutReloadingTheDso) {
  auto loaded = Component::Load(EchoStubPath());
  ASSERT_TRUE(loaded.ok()) << loaded.error().Format();
  Component component = std::move(loaded).value();

  ASSERT_TRUE(component.Init().ok());
  ASSERT_TRUE(component.Shutdown().ok());

  auto reset_result = component.Reset();
  ASSERT_TRUE(reset_result.ok()) << reset_result.error().Format();
  EXPECT_EQ(component.phase(), Phase::Loaded);

  auto reinit_result = component.Init();
  ASSERT_TRUE(reinit_result.ok()) << reinit_result.error().Format();
  EXPECT_EQ(component.phase(), Phase::Initialized);
}

TEST(MhComponent, ResetBeforeShutdownIsRefused) {
  auto loaded = Component::Load(EchoStubPath());
  ASSERT_TRUE(loaded.ok()) << loaded.error().Format();
  Component component = std::move(loaded).value();

  ASSERT_TRUE(component.Init().ok());
  auto reset_result = component.Reset();
  ASSERT_FALSE(reset_result.ok());
  EXPECT_EQ(reset_result.error().kind, simcore::Kind::Internal);
}

TEST(MhComponent, UndersizedOutputPortGrowsOnceAndRetries) {
  EnvGuard port_guard("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "echo.out");
  EnvGuard cap_guard("ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES", "0");  // 1 byte written, 0-cap buffer forces a grow

  auto loaded = Component::Load(EchoStubPath());
  ASSERT_TRUE(loaded.ok()) << loaded.error().Format();
  Component component = std::move(loaded).value();
  ASSERT_TRUE(component.Init().ok());

  auto exec_result = component.Exec(50'000'000, PortMap{});
  ASSERT_TRUE(exec_result.ok()) << exec_result.error().Format();
  ASSERT_EQ(exec_result.value().count("echo.out"), 1u);
  EXPECT_EQ(exec_result.value().at("echo.out").size(), 1u);
}

TEST(MhComponent, HungExecTripsTheQuarantineAndRefusesFurtherCalls) {
  EnvGuard hang_guard("ADAS_SIL_TEST_STUB_HANG", "1");

  auto loaded = Component::Load(EchoStubPath());
  ASSERT_TRUE(loaded.ok()) << loaded.error().Format();
  Component component = std::move(loaded).value();
  ASSERT_TRUE(component.Init().ok());

  ExecTimeout budget(std::chrono::milliseconds(100));
  auto first = component.Exec(50'000'000, PortMap{}, {}, budget);
  ASSERT_FALSE(first.ok());
  EXPECT_TRUE(component.IsQuarantined());

  auto second = component.Exec(50'000'000, PortMap{}, {}, budget);
  ASSERT_FALSE(second.ok());
  EXPECT_NE(second.error().found.find("quarantined"), std::string::npos) << second.error().Format();
}
