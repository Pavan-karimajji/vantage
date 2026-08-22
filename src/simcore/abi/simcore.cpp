// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `simEngineCreate`/`simEngineRun`/`simEngineDestroy` (`IMP-0144`,
///   `WP-14`): the implementation behind `abi/simcore.h`. This is the ONE
///   place a Resolved Run Spec is turned into a live `Scheduler` + `PortBus`
///   + `Reader` + loaded `module_host::Component`s + `runner::Runner` --
///   `simengine/main.cpp` calls exactly these three functions and nothing
///   else (`SW-0141`), and `IT-11` calls them from a second, non-`simengine`
///   host to prove `SW-0144`.
///
///   **Deliberately out of scope this slice, named rather than silently
///   dropped:** a spec carrying `mutations` is refused (`Authoring`) --
///   `mutate::Mutator`'s `PortResolver` needs a live protobuf field
///   catalogue (reflection over each port's declared `proto_type`), which
///   nothing in `simcore` builds yet outside test fixtures. Wiring a real
///   resolver is additive here, not a reversal, the moment that catalogue
///   exists. No writer is opened either -- this slice drives a read-only
///   resim, the same shape `sil_host/main.cpp` shipped (it never opened an
///   `mcap` writer of its own).
/// @author Pavan Karimajji

#include "simcore/abi/simcore.h"

#include <cstring>
#include <fstream>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

#include "simcore/bus.hpp"
#include "simcore/errors.hpp"
#include "simcore/io.hpp"
#include "simcore/module_host.hpp"
#include "simcore/runner.hpp"
#include "simcore/runspec.hpp"
#include "simcore/scheduler.hpp"

namespace {

using simcore::Error;
using simcore::ExitCode;
using simcore::Kind;
using simcore::Result;

void WriteErr(char* buf, std::size_t cap, const std::string& msg) {
  if (buf == nullptr || cap == 0) return;
  const std::size_t n = std::min(cap - 1, msg.size());
  std::memcpy(buf, msg.data(), n);
  buf[n] = '\0';
}

SimExitCode ToC(ExitCode code) { return static_cast<SimExitCode>(code); }

// Every registered-once-per-process codec this host knows how to read.
// `CodecRegistry::Register` fails a SECOND registration of one extension
// (IMP-0023), so this must run exactly once per process regardless of how
// many `simEngineCreate` calls follow -- `std::call_once`, not a static
// bool a caller could race.
void EnsureCodecsRegistered() {
  static std::once_flag once;
  std::call_once(once, [] {
    simcore::io::codecs::RegisterMcap(simcore::io::CodecRegistry::Instance());
    simcore::io::codecs::RegisterErg(simcore::io::CodecRegistry::Instance());
  });
}

Result<std::string> ReadFile(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return Result<std::string>::Fail(
        Error{Kind::Environment, "a readable Resolved Run Spec file", "could not open", path.string(),
              "check the path passed to simEngineCreate"});
  }
  std::ostringstream buf;
  buf << in.rdbuf();
  return Result<std::string>::Ok(buf.str());
}

}  // namespace

// One constructed engine: the spec plus every live object the cycle loop
// (`runner::Runner`) needs a non-owning pointer/reference to. Declaration
// order is destruction order, reversed -- `runner_` is declared LAST so it
// is destroyed FIRST, before the reader and the components it only
// borrows.
struct SimEngine {
  simcore::RunSpec spec;
  simcore::scheduler::Scheduler scheduler;
  simcore::bus::PortBus bus;
  std::unique_ptr<simcore::io::Reader> reader;
  std::vector<std::unique_ptr<simcore::module_host::Component>> owned_components;
  std::map<std::string, simcore::module_host::Component*> component_ptrs;
  std::optional<simcore::runner::Runner> runner;

  explicit SimEngine(simcore::RunSpec s) : spec(std::move(s)), scheduler(spec), bus(0) {}
};

int32_t simEngineAbiVersion() { return SIMCORE_ABI_VERSION; }

SimEngine* simEngineCreate(const char* run_spec_json_path, const char* config_path, int64_t exec_timeout_ms,
                            char* err_buf, std::size_t err_buf_cap, SimExitCode* out_exit_code) {
  if (out_exit_code != nullptr) *out_exit_code = kSimExitOk;
  if (run_spec_json_path == nullptr) {
    WriteErr(err_buf, err_buf_cap, "run_spec_json_path is NULL");
    if (out_exit_code != nullptr) *out_exit_code = kSimExitConfig;
    return nullptr;
  }

  const Result<std::string> json = ReadFile(run_spec_json_path);
  if (!json.ok()) {
    WriteErr(err_buf, err_buf_cap, json.error().Format());
    if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(json.error().kind));
    return nullptr;
  }

  Result<simcore::RunSpec> spec_result = simcore::LoadRunSpec(json.value());
  if (!spec_result.ok()) {
    WriteErr(err_buf, err_buf_cap, spec_result.error().Format());
    if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(spec_result.error().kind));
    return nullptr;
  }

  if (!spec_result.value().mutations.empty()) {
    WriteErr(err_buf, err_buf_cap,
             "this host does not yet wire a PortResolver for mutations (WP-14's own named scope limit)");
    if (out_exit_code != nullptr) *out_exit_code = kSimExitConfig;
    return nullptr;
  }
  if (spec_result.value().sources.empty()) {
    WriteErr(err_buf, err_buf_cap, "run spec declares no sources[] to read");
    if (out_exit_code != nullptr) *out_exit_code = kSimExitConfig;
    return nullptr;
  }

  auto engine = std::make_unique<SimEngine>(std::move(spec_result).value());

  EnsureCodecsRegistered();
  Result<std::unique_ptr<simcore::io::Reader>> reader_result =
      simcore::io::CodecRegistry::Instance().OpenRead(engine->spec.sources.front().path);
  if (!reader_result.ok()) {
    WriteErr(err_buf, err_buf_cap, reader_result.error().Format());
    if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(reader_result.error().kind));
    return nullptr;
  }
  engine->reader = std::move(reader_result).value();
  const Result<bool> open_result = engine->reader->Open(engine->spec.sources.front().path);
  if (!open_result.ok()) {
    WriteErr(err_buf, err_buf_cap, open_result.error().Format());
    if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(open_result.error().kind));
    return nullptr;
  }

  for (const simcore::SpecStage& stage : engine->spec.stages) {
    if (stage.mode != "simulate") continue;
    Result<simcore::module_host::Component> component_result =
        simcore::module_host::Component::Load(stage.impl.path);
    if (!component_result.ok()) {
      WriteErr(err_buf, err_buf_cap, component_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(component_result.error().kind));
      return nullptr;
    }
    auto component = std::make_unique<simcore::module_host::Component>(std::move(component_result).value());
    const std::filesystem::path cfg = config_path != nullptr ? std::filesystem::path(config_path)
                                                               : std::filesystem::path();
    const Result<bool> init_result = component->Init(cfg);
    if (!init_result.ok()) {
      WriteErr(err_buf, err_buf_cap, init_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(init_result.error().kind));
      return nullptr;
    }
    engine->component_ptrs[stage.name] = component.get();
    engine->owned_components.push_back(std::move(component));
  }

  simcore::runner::RunnerOptions options;
  if (exec_timeout_ms > 0) {
    options.exec_timeout = std::chrono::milliseconds(exec_timeout_ms);
  }
  Result<simcore::runner::Runner> runner_result = simcore::runner::Runner::Construct(
      engine->spec, engine->scheduler, engine->bus, *engine->reader, engine->component_ptrs,
      /*writer=*/nullptr, /*mutator=*/nullptr, options);
  if (!runner_result.ok()) {
    WriteErr(err_buf, err_buf_cap, runner_result.error().Format());
    if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(runner_result.error().kind));
    return nullptr;
  }
  engine->runner = std::move(runner_result).value();

  return engine.release();
}

SimExitCode simEngineRun(SimEngine* engine, char* err_buf, std::size_t err_buf_cap) {
  if (engine == nullptr || !engine->runner.has_value()) {
    WriteErr(err_buf, err_buf_cap, "simEngineRun called with no constructed engine");
    return kSimExitConfig;
  }
  const Result<simcore::runner::RunOutcome> outcome = engine->runner->Run();
  if (!outcome.ok()) {
    WriteErr(err_buf, err_buf_cap, outcome.error().Format());
    return ToC(simcore::DefaultExitCode(outcome.error().kind));
  }
  return kSimExitOk;
}

void simEngineDestroy(SimEngine* engine) {
  if (engine == nullptr) return;
  // Best-effort: a shutdown failure on one component must not stop the
  // rest from being asked to shut down too (mirrors
  // `sil_host::Pipeline::ShutdownComponents`'s own "every component gets
  // asked" shape).
  for (auto& component : engine->owned_components) {
    component->Shutdown();
  }
  delete engine;
}
