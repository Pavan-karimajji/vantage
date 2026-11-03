// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The supervision cell (`WP-17`): `IMP-0109` (`SupervisionCell` create, open, read after the worker's end) and
///   `IMP-0124` (the engine marks it through `simEngineSetSupervisionCell`: the last completed step, and a stage's
///   byte for the length of its call). The cell is shared memory and no file is written per call (`D31 (3)`).
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <atomic>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "livemeas/shared_region.hpp"
#include "simcore/abi/simcore.h"
#include "simcore/io.hpp"
#include "supervision_cell.hpp"

namespace {

using vantage::livemeas::SharedRegion;
using vantage::simengine::SupervisionCell;

std::string UniqueName(const char* tag) {
  static int counter = 0;
  return std::string("vnt_cell_") + tag + "_" + std::to_string(SharedRegion::currentProcessId()) + "_" +
         std::to_string(++counter);
}

std::filesystem::path TempPath(const std::string& name) { return std::filesystem::temp_directory_path() / name; }

std::string JsonEscape(const std::filesystem::path& path) {
  std::string out;
  for (char c : path.string()) {
    if (c == '\\' || c == '"') out.push_back('\\');
    out.push_back(c);
  }
  return out;
}

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

// Three heartbeat messages 10 ms apart; one clock-started stage `sut` running the echo stub.
std::filesystem::path WriteEchoSpec(const std::string& tag) {
  const std::filesystem::path recording = TempPath("cell_" + tag + ".mcap");
  simcore::io::CodecRegistry registry;
  EXPECT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
  auto writer = registry.OpenWrite(recording);
  EXPECT_TRUE(writer.ok());
  simcore::io::TopicInfo heartbeat;
  heartbeat.schema_name = "test.Heartbeat";
  EXPECT_TRUE(writer.value()->Open(recording, {{"/dummy/heartbeat", heartbeat}}).ok());
  for (std::int64_t t_ns : {0, 10'000'000, 20'000'000}) {
    simcore::io::RawMessage msg;
    msg.topic = "/dummy/heartbeat";
    msg.log_time_ns = t_ns;
    msg.payload = {0x01};
    writer.value()->Write(msg);
  }
  writer.value()->Close();
  const std::filesystem::path spec = TempPath("cell_" + tag + "_spec.json");
  std::ofstream out(spec);
  out << R"({
    "schema": "adas.sim.runspec/2.0", "run_id": "20261105T000000Z-cell", "spec_sha256": "0",
    "sources": [{"path": ")"
      << JsonEscape(recording) << R"(", "sha256": "0", "codec": "mcap"}],
    "stages": [{
      "name": "sut", "mode": "simulate", "impl": {"kind": "dll", "path": ")"
      << JsonEscape(EchoStubPath()) << R"("},
      "trigger": "", "clock_period_ns": 10000000, "abi_version": 1, "config_bundle_sha256": "",
      "ports": [{"name": "outputs", "dir": "pro", "kind": "data", "proto_type": "test.Echo",
                 "record": "full", "fixed_slots": null, "bulk": false, "buffer_depth": 16}],
      "inputs": []
    }],
    "mutations": [], "coherence_verdict": "clean", "readiness_limit_steps": 4, "fallback_max_gap": 4,
    "outputs": {}, "limits": {"exec_timeout_ms": 2000, "severity_exit": "crash"}
  })";
  return spec;
}

SimEngine* Create(const std::filesystem::path& spec) {
  char err[512] = {0};
  SimExitCode code = kSimExitOk;
  SimEngine* engine = simEngineCreate(spec.string().c_str(), nullptr, 2000, err, sizeof(err), &code);
  EXPECT_NE(engine, nullptr) << err;
  return engine;
}

std::uint8_t* StageBytes(SupervisionCell& cell) {
  return static_cast<std::uint8_t*>(cell.base()) + SIMCORE_SUPERVISION_CELL_HEADER_BYTES;
}

}  // namespace

TEST(SupervisionCell, IMP_0109_CreateThenOpenSharesStageBytesAndTheLastCompletedStep) {
  const std::string name = SupervisionCell::nameFor(SharedRegion::currentProcessId(), 1) + "_" + UniqueName("rt");
  std::unique_ptr<SupervisionCell> supervisor = SupervisionCell::create(name, 3);
  ASSERT_NE(supervisor, nullptr);
  EXPECT_TRUE(supervisor->stagesInCall({"a", "b", "c"}).empty());
  EXPECT_FALSE(supervisor->lastCompletedStep().has_value());

  std::unique_ptr<SupervisionCell> worker = SupervisionCell::open(name);
  ASSERT_NE(worker, nullptr);
  StageBytes(*worker)[1] = 1;  // stage b is in a call
  auto* header = static_cast<SimSupervisionCellHeader*>(worker->base());
  header->lastCompletedStep = 41;
  header->hasStep = 1;

  EXPECT_EQ(supervisor->stagesInCall({"a", "b", "c"}), std::vector<std::string>({"b"}));
  EXPECT_EQ(supervisor->lastCompletedStep(), std::optional<std::uint64_t>(41));
  EXPECT_EQ(static_cast<SimSupervisionCellHeader*>(supervisor->base())->stageCount, 3u);
  supervisor->remove();
}

TEST(SupervisionCell, IMP_0109_OpenOfANameNobodyHoldsOrOfAnotherRegionIsNull) {
  EXPECT_EQ(SupervisionCell::open(UniqueName("none")), nullptr);
  const std::string name = UniqueName("other");
  std::unique_ptr<SharedRegion> region;
  ASSERT_NE(SharedRegion::createOrReplace(name, 64, nullptr, region), SharedRegion::Create::kFailed);  // zeroed: no magic
  EXPECT_EQ(SupervisionCell::open(name), nullptr);
}

TEST(SupervisionCell, IMP_0124_TheEngineLeavesTheLastStepAndEveryStageByteZeroAfterARun) {
  SimEngine* engine = Create(WriteEchoSpec("run"));
  ASSERT_NE(engine, nullptr);
  const std::string name = UniqueName("run");
  std::unique_ptr<SupervisionCell> cell = SupervisionCell::create(name, 1);
  ASSERT_NE(cell, nullptr);
  ASSERT_EQ(simEngineSetSupervisionCell(engine, cell->base(), cell->length()), kSimExitOk);

  char err[512] = {0};
  std::int32_t more = 1;
  int steps = 0;
  while (more != 0) {
    ASSERT_EQ(simEngineStepOnce(engine, err, sizeof(err), &more), kSimExitOk) << err;
    if (more != 0) {
      ++steps;
      EXPECT_EQ(StageBytes(*cell)[0], 0) << "a stage byte is 0 between calls";
      EXPECT_EQ(cell->lastCompletedStep(), std::optional<std::uint64_t>(static_cast<std::uint64_t>(steps - 1)));
    }
  }
  ASSERT_EQ(steps, 3);
  EXPECT_EQ(cell->lastCompletedStep(), std::optional<std::uint64_t>(2)) << "the run's last step";
  EXPECT_TRUE(cell->stagesInCall({"sut"}).empty());
  simEngineDestroy(engine);
}

TEST(SupervisionCell, IMP_0124_ACellThatDoesNotMatchTheSetupIsRefusedAndNothingIsStored) {
  SimEngine* engine = Create(WriteEchoSpec("bad"));
  ASSERT_NE(engine, nullptr);
  std::unique_ptr<SupervisionCell> wrong_count = SupervisionCell::create(UniqueName("count"), 2);  // the setup has one stage
  ASSERT_NE(wrong_count, nullptr);
  EXPECT_EQ(simEngineSetSupervisionCell(engine, wrong_count->base(), wrong_count->length()), kSimExitConfig);
  std::unique_ptr<SharedRegion> not_a_cell;
  ASSERT_NE(SharedRegion::createOrReplace(UniqueName("magic"), 64, nullptr, not_a_cell), SharedRegion::Create::kFailed);
  EXPECT_EQ(simEngineSetSupervisionCell(engine, not_a_cell->data(), not_a_cell->size()), kSimExitConfig);
  EXPECT_EQ(simEngineSetSupervisionCell(engine, wrong_count->base(), 8), kSimExitConfig);
  char err[512] = {0};
  std::int32_t more = 1;
  ASSERT_EQ(simEngineStepOnce(engine, err, sizeof(err), &more), kSimExitOk) << err;
  EXPECT_FALSE(wrong_count->lastCompletedStep().has_value());
  simEngineDestroy(engine);
}
