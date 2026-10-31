// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-BUS-04` (`SW-0046`): every time quantity `simcore` loads from
///   configuration is an integer nanosecond value, and a fractional one is
///   refused rather than silently truncated. Exercised at the one door
///   configuration enters the engine through -- `LoadRunSpec` (R-SIM-11) --
///   using a minimal Resolved Run Spec (the `F-SPEC` fixture's own shape,
///   design §3.1) rather than the full four-layer YAML pipeline, which is
///   `config/`'s own concern and produces exactly this JSON.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <string>

#include "simcore/runspec.hpp"

namespace simcore {
namespace {

// `clock_period_ns_literal` is substituted verbatim as JSON, so both
// `20000000` (integer) and `20000000.5` (fractional) can be exercised
// through the same builder.
std::string MinimalRunSpecJson(const std::string& clock_period_ns_literal) {
  return R"({
    "schema": "adas.sim.runspec/2.0",
    "run_id": "ut-bus-04",
    "spec_sha256": "deadbeef",
    "sources": [],
    "stages": [
      {
        "name": "echo_stub",
        "mode": "simulate",
        "impl": {"kind": "dll", "path": "/abs/echo_stub.dll", "pattern": "", "search": []},
        "trigger": "",
        "clock_period_ns": )" + clock_period_ns_literal + R"(,
        "abi_version": 1,
        "config_bundle_sha256": "deadbeef",
        "ports": [],
        "inputs": []
      }
    ],
    "mutations": [],
    "coherence_verdict": "clean",
    "readiness_limit_steps": 4,
    "fallback_max_gap": 4,
    "limits": {"exec_timeout_ms": 1000, "severity_exit": "error"}
  })";
}

TEST(UtBus04IntegerNanoseconds, IntegerClockPeriodLoads) {
  const auto result = LoadRunSpec(MinimalRunSpecJson("20000000"));
  ASSERT_TRUE(result.ok()) << (result.ok() ? "" : result.error().Format());
  ASSERT_EQ(result.value().stages.size(), 1u);
  EXPECT_EQ(result.value().stages[0].clock_period_ns, 20'000'000);
}

TEST(UtBus04IntegerNanoseconds, FractionalClockPeriodIsRefused) {
  const auto result = LoadRunSpec(MinimalRunSpecJson("20000000.5"));
  ASSERT_FALSE(result.ok());
  EXPECT_EQ(result.error().kind, Kind::Authoring);
  EXPECT_NE(result.error().Format().find("clock_period_ns"), std::string::npos);
}

}  // namespace
}  // namespace simcore
