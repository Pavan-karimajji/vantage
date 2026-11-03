// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `step_tap` (`WP-09a`, `IMP-0041`; fixture `F-TAP` of the system tests, serves `SYS-0032`,
///   `SYS-0035`): runs a run setup through the engine with a sink on
///   `Runner::SetLiveMeasurement` and prints one JSON line per engine step:
///   `{"step":N,"time_ns":T,"badges":[{"kind":"KIND_FALLBACK","subject":"B.in","count":3}]}`
///   (a badge appears once its count is above 0, counted since the run started).
///
///   argv: `<run_setup.json> [--config PATH] [--timeout-ms N] [--threads N]
///   [--jump-at-ms F --jump-to-ms T]`. The engine is built by `simEngineCreate`, so it is the
///   `simengine` wiring and no other; the `Runner` is reached through the internal
///   `SimEngineRunner`. With a jump, the first step whose simulation time is at or after F ms
///   is followed by one `simEngineSeek` to T ms (times are the recording's reception times in
///   ms, not offsets), and step numbers continue. Exit code: 0, or the `SimExitCode` of the
///   first failure (message on stderr); 2 on a bad argument.
/// @author Pavan Karimajji

#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>

#include "abi/engine_access.hpp"
#include "livemeas/engine_sink.hpp"
#include "simcore/abi/simcore.h"
#include "simcore/runner.hpp"

namespace {

using simcore::runner::StepBadge;
using simcore::runner::StepReport;

class Tap final : public simcore::runner::LiveMeasSink {
 public:
  void OnStep(const StepReport& report) override {
    std::cout << "{\"step\":" << report.step << ",\"time_ns\":" << report.sim_time_ns << ",\"badges\":[";
    bool first = true;
    for (const StepBadge& badge : report.badges) {
      if (!first) std::cout << ",";
      first = false;
      std::cout << "{\"kind\":\"" << simcore::runner::ToString(badge.kind) << "\",\"subject\":\"" << badge.subject
                << "\",\"count\":" << badge.count << "}";
    }
    std::cout << "]}\n";
    last_time_ns = report.sim_time_ns;
  }
  std::int64_t last_time_ns = 0;
};

bool ParseWhole(const char* text, std::int64_t& value) {
  char* end = nullptr;
  const long long parsed = std::strtoll(text, &end, 10);
  if (end == text || *end != '\0' || parsed < 0) return false;
  value = parsed;
  return true;
}

int Usage() {
  std::cerr << "usage: step_tap <run_setup.json> [--config PATH] [--timeout-ms N] [--threads N] "
               "[--jump-at-ms F --jump-to-ms T]\n";
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  std::string setup;
  std::string config;
  std::int64_t timeout_ms = 0;
  std::int64_t threads = 1;
  std::int64_t jump_at_ms = -1;
  std::int64_t jump_to_ms = -1;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const bool has_value = i + 1 < argc;
    if (arg == "--config" && has_value) {
      config = argv[++i];
    } else if (arg == "--timeout-ms" && has_value) {
      if (!ParseWhole(argv[++i], timeout_ms)) return Usage();
    } else if (arg == "--threads" && has_value) {
      if (!ParseWhole(argv[++i], threads) || threads < 1) return Usage();
    } else if (arg == "--jump-at-ms" && has_value) {
      if (!ParseWhole(argv[++i], jump_at_ms)) return Usage();
    } else if (arg == "--jump-to-ms" && has_value) {
      if (!ParseWhole(argv[++i], jump_to_ms)) return Usage();
    } else if (setup.empty() && arg.rfind("--", 0) != 0) {
      setup = arg;
    } else {
      return Usage();
    }
  }
  if (setup.empty() || (jump_at_ms < 0) != (jump_to_ms < 0)) return Usage();

  char err[512] = {0};
  SimExitCode code = kSimExitOk;
  SimEngine* engine = simEngineCreate(setup.c_str(), config.empty() ? nullptr : config.c_str(), timeout_ms, err,
                                      sizeof(err), &code);
  if (engine == nullptr) {
    std::cerr << "[step_tap] error: " << err << "\n";
    return static_cast<int>(code);
  }
  code = simEngineSetThreads(engine, static_cast<int32_t>(threads), err, sizeof(err));
  Tap tap;
  simcore::runner::Runner* runner = SimEngineRunner(engine);
  if (code == kSimExitOk && runner != nullptr) {
    // IMP-0081: with `outputs.livemeas` the runner already feeds the engine's writer sink; the tap
    // chains behind it, so it gets the same report instead of replacing the writer.
    if (auto* writer_sink = dynamic_cast<simcore::livemeas::LiveMeasWriterSink*>(runner->LiveMeasurement())) {
      writer_sink->SetNext(&tap);
    } else {
      runner->SetLiveMeasurement(&tap);
    }
    bool jumped = jump_at_ms < 0;
    int32_t more = 1;
    while (code == kSimExitOk && more != 0) {
      code = simEngineStepOnce(engine, err, sizeof(err), &more);
      if (code == kSimExitOk && !jumped && more != 0 && tap.last_time_ns >= jump_at_ms * 1'000'000) {
        jumped = true;
        code = simEngineSeek(engine, jump_to_ms * 1'000'000, err, sizeof(err));
      }
    }
  }
  if (code != kSimExitOk) std::cerr << "[step_tap] error: " << err << "\n";
  simEngineDestroy(engine);
  return static_cast<int>(code);
}
