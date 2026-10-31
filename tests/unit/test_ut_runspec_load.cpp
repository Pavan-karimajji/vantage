// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `LoadRunSpec` reads schema `adas.sim.runspec/2.0` (`WP-01`, `IMP-0001`
///   to `IMP-0004`, `IMP-0049`): the new keys of `VANTAGE_Architecture.md`
///   section 2.3 are read, `sampling` and `on_missing` are refused
///   (`SYS-0002`), a missing `⊘` value is refused by name (`SYS-0003`),
///   only the accepted schema string loads (`SYS-0004`), and a retired or
///   unknown key is refused with its place (`SYS-0046`). These are unit
///   tests of the loader; the system tests `SYT-RUN-02`, `-03`, `-04` and
///   `-09` are built in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <string>

#include "simcore/runspec.hpp"
#include "third_party/nlohmann/json.hpp"

namespace simcore {
namespace {

using Json = nlohmann::json;

// A complete, valid setup: a measured stage `meas` and a simulated stage
// `sut` fed by it, with a live measurement declared.
Json ValidSetup() {
  return Json::parse(R"({
    "schema": "adas.sim.runspec/2.0",
    "run_id": "ut-runspec-load",
    "spec_sha256": "deadbeef",
    "sources": [{"path": "/abs/rec.mcap", "sha256": "0", "codec": "mcap", "ingest": [], "absent": []}],
    "stages": [
      {
        "name": "meas", "mode": "measured",
        "impl": {"kind": "dll", "path": "", "pattern": "", "search": []},
        "trigger": "", "clock_period_ns": 0, "abi_version": 1, "config_bundle_sha256": "",
        "ports": [{"name": "objects", "dir": "pro", "kind": "data", "proto_type": "test.Echo",
                   "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 8}],
        "inputs": []
      },
      {
        "name": "sut", "mode": "simulate",
        "impl": {"kind": "dll", "path": "/abs/sut.dll", "pattern": "", "search": []},
        "trigger": "control", "clock_period_ns": 0, "abi_version": 1, "config_bundle_sha256": "",
        "ports": [{"name": "objects", "dir": "req", "kind": "data", "proto_type": "test.Echo",
                   "record": "full", "fixed_slots": null, "bulk": true, "buffer_depth": 16}],
        "inputs": [{"port": "objects", "producer": "meas", "producer_port": "objects", "previous_cycle": true}]
      }
    ],
    "mutations": [],
    "coherence_verdict": "clean",
    "outputs": {"path": "/abs/out.mcap", "codec": "mcap",
                "livemeas": {"name": "vantage_test", "cycle_slot_count": 64, "cycle_slot_size": 4096,
                             "bulk_slot_count": 4, "bulk_slot_size": 65536}},
    "readiness_limit_steps": 12,
    "fallback_max_gap": 3,
    "limits": {"exec_timeout_ms": 1000, "severity_exit": "error"}
  })");
}

Result<RunSpec> Load(const Json& setup) { return LoadRunSpec(setup.dump()); }

// The refusal text, for substring checks; fails the test if the load succeeded.
std::string RefusalOf(const Json& setup) {
  const auto result = Load(setup);
  EXPECT_FALSE(result.ok()) << "the setup loaded but should have been refused";
  if (result.ok()) return "";
  EXPECT_EQ(result.error().kind, Kind::Authoring);
  return result.error().Format();
}

bool Mentions(const std::string& text, const std::string& what) { return text.find(what) != std::string::npos; }

// ---- IMP-0001: the new keys are read ---------------------------------------

TEST(UtRunSpecLoad01NewKeys, AValidSetupLoadsWithEveryNewKeyRead) {
  const auto result = Load(ValidSetup());
  ASSERT_TRUE(result.ok()) << result.error().Format();
  const RunSpec& spec = result.value();
  EXPECT_EQ(spec.schema, "adas.sim.runspec/2.0");
  EXPECT_EQ(spec.readiness_limit_steps, 12);
  EXPECT_EQ(spec.fallback_max_gap, 3);
  EXPECT_EQ(spec.coherence_verdict, "clean");
  ASSERT_EQ(spec.stages.size(), 2u);
  EXPECT_EQ(spec.stages[0].trigger, "");
  EXPECT_EQ(spec.stages[1].trigger, "control");
  EXPECT_EQ(spec.stages[1].clock_period_ns, 0);
  EXPECT_TRUE(spec.stages[1].inputs[0].previous_cycle);
  EXPECT_FALSE(spec.stages[0].ports[0].bulk);
  EXPECT_TRUE(spec.stages[1].ports[0].bulk);
  EXPECT_EQ(spec.stages[0].ports[0].buffer_depth, 8);
  EXPECT_EQ(spec.stages[1].ports[0].buffer_depth, 16);
  ASSERT_TRUE(spec.outputs.livemeas.has_value());
  EXPECT_EQ(spec.outputs.livemeas->name, "vantage_test");
  EXPECT_EQ(spec.outputs.livemeas->cycle_slot_count, 64);
  EXPECT_EQ(spec.outputs.livemeas->cycle_slot_size, 4096);
  EXPECT_EQ(spec.outputs.livemeas->bulk_slot_count, 4);
  EXPECT_EQ(spec.outputs.livemeas->bulk_slot_size, 65536);
}

TEST(UtRunSpecLoad01NewKeys, AStageWithAClockPeriodAndNoTriggerLoads) {
  Json setup = ValidSetup();
  setup["stages"][1]["trigger"] = "";
  setup["stages"][1]["clock_period_ns"] = 10'000'000;
  const auto result = Load(setup);
  ASSERT_TRUE(result.ok()) << result.error().Format();
  EXPECT_EQ(result.value().stages[1].clock_period_ns, 10'000'000);
}

// ---- IMP-0002 (SYT-RUN-02): sampling and on_missing are refused ------------

TEST(UtRunSpecLoad02RetiredPortKeys, SamplingOnAPortIsRefusedNamingTheKeyTheStageAndThePort) {
  Json setup = ValidSetup();
  setup["stages"][1]["ports"][0]["sampling"] = "latest_at_or_before";
  const std::string text = RefusalOf(setup);
  EXPECT_TRUE(Mentions(text, "sampling")) << text;
  EXPECT_TRUE(Mentions(text, "sut")) << text;
  EXPECT_TRUE(Mentions(text, "objects")) << text;
}

TEST(UtRunSpecLoad02RetiredPortKeys, OnMissingOnAPortIsRefusedNamingTheKeyTheStageAndThePort) {
  Json setup = ValidSetup();
  setup["stages"][0]["ports"][0]["on_missing"] = "hold";
  const std::string text = RefusalOf(setup);
  EXPECT_TRUE(Mentions(text, "on_missing")) << text;
  EXPECT_TRUE(Mentions(text, "meas")) << text;
  EXPECT_TRUE(Mentions(text, "objects")) << text;
}

// ---- IMP-0003 (SYT-RUN-03): a missing ⊘ value is refused by name -----------

TEST(UtRunSpecLoad03MissingValues, EachMissingTopLevelValueIsRefusedNamingTheKey) {
  for (const char* key : {"readiness_limit_steps", "fallback_max_gap"}) {
    Json setup = ValidSetup();
    setup.erase(key);
    const std::string text = RefusalOf(setup);
    EXPECT_TRUE(Mentions(text, key)) << key << ": " << text;
  }
}

TEST(UtRunSpecLoad03MissingValues, AMissingBufferDepthIsRefusedNamingTheKeyTheStageAndThePort) {
  Json setup = ValidSetup();
  setup["stages"][1]["ports"][0].erase("buffer_depth");
  const std::string text = RefusalOf(setup);
  EXPECT_TRUE(Mentions(text, "buffer_depth")) << text;
  EXPECT_TRUE(Mentions(text, "sut")) << text;
  EXPECT_TRUE(Mentions(text, "objects")) << text;
}

TEST(UtRunSpecLoad03MissingValues, EachMissingLiveMeasurementGeometryValueIsRefusedNamingTheKey) {
  for (const char* key : {"cycle_slot_count", "cycle_slot_size", "bulk_slot_count", "bulk_slot_size"}) {
    Json setup = ValidSetup();
    setup["outputs"]["livemeas"].erase(key);
    const std::string text = RefusalOf(setup);
    EXPECT_TRUE(Mentions(text, key)) << key << ": " << text;
  }
}

TEST(UtRunSpecLoad03MissingValues, ALiveMeasurementIsOptionalAndWhenAbsentNoGeometryIsRequired) {
  Json setup = ValidSetup();
  setup["outputs"].erase("livemeas");
  const auto result = Load(setup);
  ASSERT_TRUE(result.ok()) << result.error().Format();
  EXPECT_FALSE(result.value().outputs.livemeas.has_value());
}

TEST(UtRunSpecLoad03MissingValues, AValueThatIsNotAnIntegerIsRefusedNamingTheKey) {
  Json setup = ValidSetup();
  setup["readiness_limit_steps"] = 12.5;
  const std::string text = RefusalOf(setup);
  EXPECT_TRUE(Mentions(text, "readiness_limit_steps")) << text;
}

// ---- IMP-0004 (SYT-RUN-04): only the accepted schema string loads ----------

TEST(UtRunSpecLoad04Schema, AnotherSchemaStringIsRefusedNamingTheStringFoundAndTheStringExpected) {
  Json setup = ValidSetup();
  setup["schema"] = "adas.sim.runspec/1.0";
  const std::string text = RefusalOf(setup);
  EXPECT_TRUE(Mentions(text, "adas.sim.runspec/1.0")) << text;
  EXPECT_TRUE(Mentions(text, "adas.sim.runspec/2.0")) << text;
}

TEST(UtRunSpecLoad04Schema, AMissingSchemaIsRefusedNamingTheExpectedString) {
  Json setup = ValidSetup();
  setup.erase("schema");
  const std::string text = RefusalOf(setup);
  EXPECT_TRUE(Mentions(text, "adas.sim.runspec/2.0")) << text;
}

// ---- IMP-0049 (SYT-RUN-09): retired and unknown keys are refused -----------

TEST(UtRunSpecLoad05RetiredAndUnknownKeys, DelayStepsOnAnInputIsRefusedNamingTheKeyAndTheInput) {
  Json setup = ValidSetup();
  setup["stages"][1]["inputs"][0]["delay_steps"] = 0;
  const std::string text = RefusalOf(setup);
  EXPECT_TRUE(Mentions(text, "delay_steps")) << text;
  EXPECT_TRUE(Mentions(text, "sut")) << text;
  EXPECT_TRUE(Mentions(text, "inputs[objects]")) << text;
}

TEST(UtRunSpecLoad05RetiredAndUnknownKeys, GridStepAndOrderAtTheTopLevelAreRefusedNamingTheKeyAndTheTopLevel) {
  Json with_grid_step = ValidSetup();
  with_grid_step["grid_step_ns"] = 10'000'000;
  const std::string grid_text = RefusalOf(with_grid_step);
  EXPECT_TRUE(Mentions(grid_text, "grid_step_ns")) << grid_text;
  EXPECT_TRUE(Mentions(grid_text, "top level")) << grid_text;

  Json with_order = ValidSetup();
  with_order["order"] = Json::array({"meas", "sut"});
  const std::string order_text = RefusalOf(with_order);
  EXPECT_TRUE(Mentions(order_text, "order")) << order_text;
  EXPECT_TRUE(Mentions(order_text, "top level")) << order_text;
}

TEST(UtRunSpecLoad05RetiredAndUnknownKeys, AStagePeriodNsIsRefusedBecauseTheKeyIsNowClockPeriodNs) {
  Json setup = ValidSetup();
  setup["stages"][0]["period_ns"] = 10'000'000;
  const std::string text = RefusalOf(setup);
  EXPECT_TRUE(Mentions(text, "period_ns")) << text;
  EXPECT_TRUE(Mentions(text, "stages[meas]")) << text;
}

TEST(UtRunSpecLoad05RetiredAndUnknownKeys, AnUnknownKeyIsRefusedNamingTheKeyAndWhereItIs) {
  Json on_stage = ValidSetup();
  on_stage["stages"][1]["colour"] = "red";
  const std::string stage_text = RefusalOf(on_stage);
  EXPECT_TRUE(Mentions(stage_text, "colour")) << stage_text;
  EXPECT_TRUE(Mentions(stage_text, "stages[sut]")) << stage_text;

  Json on_port = ValidSetup();
  on_port["stages"][0]["ports"][0]["colour"] = "red";
  const std::string port_text = RefusalOf(on_port);
  EXPECT_TRUE(Mentions(port_text, "colour")) << port_text;
  EXPECT_TRUE(Mentions(port_text, "ports[objects]")) << port_text;

  Json at_top = ValidSetup();
  at_top["colour"] = "red";
  const std::string top_text = RefusalOf(at_top);
  EXPECT_TRUE(Mentions(top_text, "colour")) << top_text;
  EXPECT_TRUE(Mentions(top_text, "top level")) << top_text;
}

TEST(UtRunSpecLoad05RetiredAndUnknownKeys, KeysOfTheEarlierSchemaThatAreNotInThisOneAreRefused) {
  for (const char* key : {"diagnostics", "reference_build_sha256", "coherence", "grid"}) {
    Json setup = ValidSetup();
    setup[key] = Json::object();
    const std::string text = RefusalOf(setup);
    EXPECT_TRUE(Mentions(text, key)) << key << ": " << text;
  }
}

}  // namespace
}  // namespace simcore
