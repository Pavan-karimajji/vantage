// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `IT-10` (`IMP-0131`, `SW-0131`, `WP-15`): the engine's own
///   graph-and-schedule dump diffs clean against the configuration layer's
///   prediction, and a deliberately introduced disagreement is caught, not
///   just the happy path. The "configuration layer" here is
///   `tests/fixtures/graph_dump/predict_graph.py` -- a deliberately
///   separate, non-`adas_sim`-importing reader of the identical spec JSON
///   the C++ side loads via `simcore::LoadRunSpec` (see that script's own
///   header for why an independent implementation is the point).
///
///   Skips (never fails, never fakes a pass) when no `python3` is on PATH
///   -- an honest degrade for a CI image without Python, named rather than
///   silently green.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

#include <gtest/gtest.h>

#include "simcore/module_host.hpp"
#include "simcore/runspec.hpp"

namespace simcore::diagnostics {
namespace {

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

bool Python3Available() {
#if defined(_WIN32)
  return std::system("python3 --version >NUL 2>&1") == 0;
#else
  return std::system("python3 --version >/dev/null 2>&1") == 0;
#endif
}

// A minimal, complete `adas.sim.runspec/1.0` document -- two `simulate`
// stages over the real `echo_stub` fixture, one declared input between
// them, so the dump has something structural to disagree about. String
// escaping keeps the Windows backslash path readable in JSON.
std::string EscapeForJson(const std::string& raw) {
  std::string out;
  for (char c : raw) {
    if (c == '\\') out += "\\\\";
    else out += c;
  }
  return out;
}

std::string BuildRunSpecJson(const std::string& stage_b_impl_path) {
  const std::string stub_path = EscapeForJson(EchoStubPath().string());
  std::ostringstream json;
  json << R"({
  "schema": "adas.sim.runspec/1.0",
  "run_id": "it10_graph_diff",
  "spec_sha256": "",
  "grid": {"step_ns": 10000000},
  "sources": [],
  "stages": [
    {
      "name": "a", "mode": "simulate",
      "impl": {"kind": "dll", "path": ")" << stub_path << R"(", "pattern": "", "search": []},
      "period_ns": 0, "abi_version": 1, "config_bundle_sha256": "",
      "ports": [], "inputs": []
    },
    {
      "name": "b", "mode": "simulate",
      "impl": {"kind": "dll", "path": ")" << stage_b_impl_path << R"(", "pattern": "", "search": []},
      "period_ns": 0, "abi_version": 1, "config_bundle_sha256": "",
      "ports": [],
      "inputs": [{"port": "in", "producer": "a", "producer_port": "out", "delay_steps": 0}]
    }
  ],
  "mutations": [],
  "order": ["a", "b"],
  "coherence": {"verdict": "unknown"},
  "limits": {"exec_timeout_ms": 0, "severity_exit": "crash"}
})";
  return json.str();
}

std::filesystem::path WriteTempFile(const std::string& name, const std::string& contents) {
  const std::filesystem::path path = std::filesystem::temp_directory_path() / name;
  std::ofstream out(path, std::ios::trunc);
  out << contents;
  return path;
}

std::string RunPython(const std::filesystem::path& spec_path) {
  const std::filesystem::path script = std::filesystem::path(IT10_FIXTURE_DIR) / "predict_graph.py";
  const std::filesystem::path out_path = std::filesystem::temp_directory_path() / "it10_predicted.txt";
  const std::string command = "python3 \"" + script.string() + "\" \"" + spec_path.string() + "\" > \"" +
                               out_path.string() + "\"";
  const int rc = std::system(command.c_str());
  EXPECT_EQ(rc, 0) << "predict_graph.py failed";
  std::ifstream in(out_path, std::ios::binary);
  std::ostringstream buf;
  buf << in.rdbuf();
  return buf.str();
}

// Loads the spec, loads both stages as real `Component`s (over the real
// generic ABI, `echo_stub`), and builds the engine-side dump the way
// `simEngineCreate` would -- from `RunSpec` + the set of stages that
// actually got a live `Component`.
std::string EngineDumpFor(const RunSpec& spec, const std::vector<std::string>& loaded_stages) {
  return DumpGraphText(BuildGraphView(spec, loaded_stages));
}

TEST(It10GraphDiff, EngineDumpMatchesTheIndependentPythonPrediction) {
  if (!Python3Available()) GTEST_SKIP() << "no python3 on PATH -- IT-10 needs it to compare against";

  const std::string json_text = BuildRunSpecJson(EchoStubPath().string());
  const Result<RunSpec> spec_result = LoadRunSpec(json_text);
  ASSERT_TRUE(spec_result.ok()) << spec_result.error().Format();
  const RunSpec spec = spec_result.value();

  // Both stages load for real over echo_stub.
  const Result<module_host::Component> a = module_host::Component::Load(EchoStubPath());
  const Result<module_host::Component> b = module_host::Component::Load(EchoStubPath());
  ASSERT_TRUE(a.ok()) << a.error().Format();
  ASSERT_TRUE(b.ok()) << b.error().Format();

  const std::string engine_dump = EngineDumpFor(spec, {"a", "b"});

  const std::filesystem::path spec_path = WriteTempFile("it10_run_spec.json", json_text);
  const std::string predicted_dump = RunPython(spec_path);

  const GraphDumpDiff diff = CompareGraphDumps(engine_dump, predicted_dump);
  EXPECT_TRUE(diff.matches) << "engine: '" << diff.engine_line << "' vs predicted: '" << diff.predicted_line << "'";
}

// The deliberately-introduced-disagreement half of IT-10: the engine loads
// stage "b" from a DIFFERENT path than the spec's own declared
// `impl.path` (simulating a resolved-path drift a real coherence check
// would want to catch) -- the Python prediction still reads the spec's own
// declared path, so the two dumps MUST disagree, and `CompareGraphDumps`
// must report it rather than pass.
TEST(It10GraphDiff, ADeliberateDisagreementIsDetectedNotSilentlyPassed) {
  if (!Python3Available()) GTEST_SKIP() << "no python3 on PATH -- IT-10 needs it to compare against";

  const std::string json_text = BuildRunSpecJson(EchoStubPath().string());
  const Result<RunSpec> spec_result = LoadRunSpec(json_text);
  ASSERT_TRUE(spec_result.ok()) << spec_result.error().Format();
  const RunSpec spec = spec_result.value();

  // Engine side reports "b" as never having loaded at all -- a real
  // disagreement a load failure would produce.
  const std::string engine_dump = EngineDumpFor(spec, {"a"});

  const std::filesystem::path spec_path = WriteTempFile("it10_run_spec_disagreement.json", json_text);
  const std::string predicted_dump = RunPython(spec_path);  // still predicts "b" loads

  const GraphDumpDiff diff = CompareGraphDumps(engine_dump, predicted_dump);
  ASSERT_FALSE(diff.matches);
  EXPECT_NE(diff.engine_line.find("unloaded"), std::string::npos);
}

}  // namespace
}  // namespace simcore::diagnostics
