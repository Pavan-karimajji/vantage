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
///   **`WP-14a` (`IMP-0426`/`IMP-0427`), closing the two gaps `WP-14` named
///   above:** a real writer is now opened from the resolved Run Spec's own
///   declared `outputs.path`/`outputs.codec` (`runspec.hpp`'s `SpecOutputs`,
///   `R-SIM-6`) -- absent when the spec declares none, exactly as before
///   this package. And a real `PortResolver` is wired: a `DescriptorPool`
///   built from every loaded component's own `manifest().descriptor_set()`
///   bytes (`R-SIM-11` -- the catalogue was always on the wire, nothing
///   built a pool from it before this pass) resolves a mutation's port to
///   its message `Descriptor` by the spec's own declared `proto_type`. A
///   spec with zero `mutations` is unaffected: `mutate::Mutator::Touches`
///   is built from `mutations` alone and gates `ApplyTo` before the
///   resolver is ever called, so an empty `mutations` list makes this
///   resolver behave as a no-op by construction (`SW-0423`'s own Accept).
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

#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>
#include <google/protobuf/dynamic_message.h>

#include "simcore/bus.hpp"
#include "simcore/errors.hpp"
#include "simcore/io.hpp"
#include "simcore/module_host.hpp"
#include "simcore/mutate.hpp"
#include "simcore/runner.hpp"
#include "simcore/runspec.hpp"
#include "simcore/scheduler.hpp"
#include "simcore/transport_publisher.hpp"

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

// IMP-0426: the topics `Writer::Open` declares up front -- one per
// declared port of every non-`off` stage, the same "stage.port" universe
// `runner::Runner::Construct` derives its own `recorded_topics_` from
// (`cycle_loop.cpp`). Computed here rather than reused from that accessor
// because it is only available AFTER `Runner::Construct`, which itself
// needs an already-open `WriterBase` -- `Writer::Open` must run first. A
// port this map omits is not lost: `.mcap`'s `arbitrary_topics`
// capability (`R-SIM-14`) registers an unknown topic schema-less on first
// `Write`, so this is a completeness/labelling improvement, not a
// correctness dependency.
// `source_topics` is the INPUT recording's own index (`Reader::Describe()`),
// so a fed port's evidence grade can be carried forward rather than guessed
// -- see the `F-2` note inside.
std::map<std::string, simcore::io::TopicInfo> BuildOutputTopics(
    const simcore::RunSpec& spec, const std::map<std::string, simcore::io::TopicInfo>& source_topics) {
  std::map<std::string, simcore::io::TopicInfo> topics;
  const auto carried_provenance = [&source_topics](const std::string& producing_topic) {
    // F-2: carry the source topic's OWN grade. Absent from the index means
    // nobody established one, which is `kUnknown` -- never `kMeasured`
    // (`SW-0039`, and `OriginOrUnknown`'s own rule one layer down).
    const auto it = source_topics.find(producing_topic);
    if (it == source_topics.end()) return simcore::io::Provenance::kUnknown;
    return it->second.provenance;
  };

  // `pro` before `req`, for the reason `Runner::Construct` states at length:
  // a `req` port recorded under its producing address can resolve onto a
  // topic a `pro` port owns, and the producer must claim it first.
  for (const std::string& want_dir : {std::string("pro"), std::string("req")}) {
  for (const simcore::SpecStage& stage : spec.stages) {
    if (stage.mode == "off") continue;
    for (const simcore::SpecPort& port : stage.ports) {
      if (port.dir != want_dir) continue;
      const std::string qualified = stage.name + "." + port.name;
      // The SAME derivation `Runner::Construct` uses to name the messages it
      // writes (`RecordedTopicFor`) -- index and stream cannot disagree.
      const std::string topic = simcore::runner::RecordedTopicFor(spec, stage.name, port.name, port.dir);
      simcore::io::TopicInfo info;
      info.schema_name = port.proto_type;
      if (port.dir == "pro" && stage.mode == "simulate") {
        // Freshly computed by this run -- the one grade this engine is
        // entitled to assert on its own authority.
        info.provenance = simcore::io::Provenance::kSimulated;
      } else {
        // F-2: everything else is FED, and "fed" is a direction, not an
        // evidence grade. Tagging it `kMeasured` unconditionally -- what
        // this did until 2026-08-28 -- reports mocked CARLA stimulus as a
        // measurement, which is exactly what `R-SIM-12` exists to forbid:
        // *"a report must never let 'perception was measured' mean
        // 'perception was a mock'."* The closed set has four values; the
        // old expression could only ever emit two.
        info.provenance = carried_provenance(topic);
      }
      // First writer wins, mirroring `Runner::Construct`'s own claim rule:
      // a `pro` port owns its topic, and a `req` port that resolves onto it
      // must not overwrite the producer's grade with a carried one.
      topics.emplace(topic, info);

      // The post-mutation twin (`R-SIM-15`), declared here so the index says
      // `overridden` rather than leaving a reader to infer it.
      if (port.dir != "req") continue;
      const std::optional<std::string> producer =
          simcore::runner::ProducerAddressOf(spec, stage.name, port.name);
      if (!producer.has_value()) continue;
      const std::size_t dot = producer->find('.');
      if (dot == std::string::npos) continue;
      if (!simcore::runner::MutationTouches(spec, producer->substr(0, dot), producer->substr(dot + 1))) continue;
      simcore::io::TopicInfo overridden = info;
      overridden.provenance = simcore::io::Provenance::kOverridden;
      topics.emplace(simcore::runner::PortNameToTopic(qualified), overridden);
    }
  }
  }
  return topics;
}

// IMP-0427: builds a real `DescriptorPool` from every loaded component's
// own `manifest().descriptor_set()` bytes (`R-SIM-11` -- the catalogue is
// already on the wire; this is the first caller to turn it into a pool
// rather than leaving it opaque). Best-effort file-by-file: a component
// that declares no schema, or a file this pass cannot yet place (its own
// dependency not seen first), simply contributes nothing -- `resolve_port`
// then reports that port unresolvable, the same `Result::Fail` path
// `Mutator::ApplyTo` already takes for any unresolvable port, rather than
// this construction step failing the whole engine over one component's
// catalogue. Multiple passes handle shared dependency files (two
// components' `FileDescriptorSet`s both listing a common `.proto`) without
// requiring either set to already be topologically sorted.
void PopulateDescriptorPool(
    const std::vector<std::unique_ptr<simcore::module_host::Component>>& components,
    google::protobuf::DescriptorPool& pool) {
  std::vector<google::protobuf::FileDescriptorProto> pending;
  for (const auto& component : components) {
    const std::string& raw = component->manifest().descriptor_set();
    if (raw.empty()) continue;
    google::protobuf::FileDescriptorSet file_set;
    if (!file_set.ParseFromString(raw)) continue;  // malformed catalogue: named via an unresolved port later
    for (const auto& file_proto : file_set.file()) {
      pending.push_back(file_proto);
    }
  }
  for (std::size_t remaining = pending.size(); remaining > 0;) {
    std::vector<google::protobuf::FileDescriptorProto> next;
    std::size_t built_this_pass = 0;
    for (const auto& file_proto : pending) {
      if (pool.FindFileByName(file_proto.name()) != nullptr) continue;  // already built (shared dependency)
      if (pool.BuildFile(file_proto) != nullptr) {
        ++built_this_pass;
      } else {
        next.push_back(file_proto);  // a dependency not yet built -- retry next pass
      }
    }
    pending = std::move(next);
    if (built_this_pass == 0) break;  // no progress: the rest have an unmet or broken dependency
    remaining = pending.size();
  }
}

// `WP-15b` follow-on (`engine.bridge._fault_mutations`): a `run.faults`
// `corrupt` verb is translated, on the Python side, into a `const` mutation
// addressed `{stage: "source", port: <port>}` -- reusing the mutation
// vocabulary/window/consumer-side matching this file already wires (`R-SIM-
// 21`'s reserved `source.<port>` keyword) rather than a second, unwired
// mechanism. But `resolve_port` below only ever looked in `spec.stages` for
// a message `Descriptor`, and `"source"` is never a `SpecStage` -- a source
// port has no component manifest, only whatever schema the RECORDING itself
// declares per topic (`R-SIM-11`). This does the same best-effort,
// multi-pass build `PopulateDescriptorPool` does for component manifests,
// from every topic's own `TopicInfo::schema_bytes` instead -- so a `const`
// mutation targeting `source.<port>.<field>` can resolve a `Descriptor` the
// same way one targeting a real stage's own port already does.
void PopulateDescriptorPoolFromTopics(const std::map<std::string, simcore::io::TopicInfo>& topics,
                                       google::protobuf::DescriptorPool& pool) {
  std::vector<google::protobuf::FileDescriptorProto> pending;
  for (const auto& [topic, info] : topics) {
    if (info.schema_bytes.empty()) continue;
    google::protobuf::FileDescriptorSet file_set;
    if (!file_set.ParseFromArray(info.schema_bytes.data(), static_cast<int>(info.schema_bytes.size()))) continue;
    for (const auto& file_proto : file_set.file()) {
      pending.push_back(file_proto);
    }
  }
  for (std::size_t remaining = pending.size(); remaining > 0;) {
    std::vector<google::protobuf::FileDescriptorProto> next;
    std::size_t built_this_pass = 0;
    for (const auto& file_proto : pending) {
      if (pool.FindFileByName(file_proto.name()) != nullptr) continue;
      if (pool.BuildFile(file_proto) != nullptr) {
        ++built_this_pass;
      } else {
        next.push_back(file_proto);
      }
    }
    pending = std::move(next);
    if (built_this_pass == 0) break;
    remaining = pending.size();
  }
}

}  // namespace

// One constructed engine: the spec plus every live object the cycle loop
// (`runner::Runner`) needs a non-owning pointer/reference to. Declaration
// order is destruction order, reversed -- `runner_` is declared LAST so it
// is destroyed FIRST, before the reader, the components, the writer, the
// descriptor pool and the mutator it only borrows.
struct SimEngine {
  simcore::RunSpec spec;
  simcore::scheduler::Scheduler scheduler;
  simcore::bus::PortBus bus;
  std::unique_ptr<simcore::io::Reader> reader;
  std::vector<std::unique_ptr<simcore::module_host::Component>> owned_components;
  std::map<std::string, simcore::module_host::Component*> component_ptrs;
  // IMP-0426: the underlying codec `Writer`, and the `WriterBase` wrapping
  // it that `Runner` actually writes through -- both absent (no writer
  // opened, matching pre-`WP-14a` behaviour) when the spec declares no
  // `outputs.path`.
  std::unique_ptr<simcore::io::Writer> writer_impl;
  std::optional<simcore::io::WriterBase> writer_base;
  // IMP-0427: the real per-run schema catalogue and the `Mutator` resolving
  // against it -- always constructed, even for zero `mutations` (see this
  // file's own top note on why that is still a no-op).
  google::protobuf::DescriptorPool descriptor_pool;
  std::unique_ptr<google::protobuf::DynamicMessageFactory> message_factory;
  std::optional<simcore::mutate::Mutator> mutator;
  // IMP-0139: absent (no checkpoint written) when the spec declares no
  // `checkpoint.path` -- same shape as `writer_base` above, gated the
  // identical way in `simEngineCreate`. Declared BEFORE `runner` so it
  // outlives the `Runner` that borrows a raw pointer to it (declaration
  // order is destruction order, reversed -- this struct's own top note).
  std::optional<simcore::runner::Checkpoint> checkpoint;
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

  // IMP-0426: open a real writer iff the resolved spec declares one.
  // Absent `outputs.path` leaves `writer_base` unset, matching this
  // function's own pre-`WP-14a` read-only behaviour exactly.
  if (!engine->spec.outputs.path.empty()) {
    Result<std::unique_ptr<simcore::io::Writer>> writer_result =
        simcore::io::CodecRegistry::Instance().OpenWrite(engine->spec.outputs.path);
    if (!writer_result.ok()) {
      WriteErr(err_buf, err_buf_cap, writer_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(writer_result.error().kind));
      return nullptr;
    }
    engine->writer_impl = std::move(writer_result).value();
    // The input recording's own index is already available (the reader was
    // opened above), which is what lets a fed topic carry its real grade
    // forward instead of being labelled `measured` by direction (F-2).
    const Result<bool> writer_open_result = engine->writer_impl->Open(
        engine->spec.outputs.path, BuildOutputTopics(engine->spec, engine->reader->Describe()));
    if (!writer_open_result.ok()) {
      WriteErr(err_buf, err_buf_cap, writer_open_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(writer_open_result.error().kind));
      return nullptr;
    }
    engine->writer_base.emplace(*engine->writer_impl);
  }

  // IMP-0427: a real per-run catalogue and resolver, always wired -- a
  // spec with zero `mutations` still gets one, and it is a no-op by
  // construction (this file's own top note).
  PopulateDescriptorPool(engine->owned_components, engine->descriptor_pool);
  // `WP-15b` follow-on: also from every recorded topic's own schema, so a
  // `source.<port>`-addressed mutation (a translated `run.faults` `corrupt`
  // entry, `engine.bridge._fault_mutations`, or a real user override) can
  // resolve a `Descriptor` too -- a source port has no `SpecStage` manifest
  // to draw one from otherwise (this file's own note on `PopulateDescriptor
  // PoolFromTopics`).
  PopulateDescriptorPoolFromTopics(engine->reader->Describe(), engine->descriptor_pool);
  engine->message_factory = std::make_unique<google::protobuf::DynamicMessageFactory>(&engine->descriptor_pool);
  simcore::mutate::Mutator::PortResolver resolve_port =
      [&spec = engine->spec, &pool = engine->descriptor_pool, &reader = *engine->reader](
          const std::string& stage, const std::string& port) -> std::optional<simcore::mutate::PortInfo> {
    for (const simcore::SpecStage& candidate : spec.stages) {
      if (candidate.name != stage) continue;
      for (const simcore::SpecPort& candidate_port : candidate.ports) {
        if (candidate_port.name != port) continue;
        const google::protobuf::Descriptor* descriptor = pool.FindMessageTypeByName(candidate_port.proto_type);
        if (descriptor == nullptr) return std::nullopt;
        return simcore::mutate::PortInfo{descriptor, candidate_port.fixed_slots};
      }
    }
    if (stage == "source") {
      const std::map<std::string, simcore::io::TopicInfo> topics = reader.Describe();
      const auto it = topics.find(simcore::runner::PortNameToTopic(stage + "." + port));
      if (it == topics.end() || it->second.schema_name.empty()) return std::nullopt;
      const google::protobuf::Descriptor* descriptor = pool.FindMessageTypeByName(it->second.schema_name);
      if (descriptor == nullptr) return std::nullopt;
      // A source port carries no `SpecPort::fixed_slots` of its own
      // (`select`/`drop[*]` on the stimulus is not a case this pass adds --
      // only `const`, from a translated `corrupt` fault, reaches this
      // branch today); `std::nullopt` matches every real component's own
      // still-unset `fixed_slots` (`runspec/address.py`'s own note on why
      // that stays `None` until `S-C1d` lands).
      return simcore::mutate::PortInfo{descriptor, std::nullopt};
    }
    return std::nullopt;
  };
  engine->mutator.emplace(engine->spec.mutations, std::move(resolve_port));

  simcore::runner::RunnerOptions options;
  if (exec_timeout_ms > 0) {
    options.exec_timeout = std::chrono::milliseconds(exec_timeout_ms);
  }
  Result<simcore::runner::Runner> runner_result = simcore::runner::Runner::Construct(
      engine->spec, engine->scheduler, engine->bus, *engine->reader, engine->component_ptrs,
      engine->writer_base.has_value() ? &*engine->writer_base : nullptr, &*engine->mutator, options);
  if (!runner_result.ok()) {
    WriteErr(err_buf, err_buf_cap, runner_result.error().Format());
    if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(runner_result.error().kind));
    return nullptr;
  }
  engine->runner = std::move(runner_result).value();

  // IMP-0139: open a real checkpoint iff the resolved spec declares one --
  // the same gate `IMP-0426` uses for the writer above. Absent
  // `checkpoint.path` leaves `checkpoint` unset and `Runner::checkpoint_`
  // `nullptr`, matching every pre-existing spec's behaviour exactly.
  if (!engine->spec.checkpoint.path.empty()) {
    engine->checkpoint.emplace(engine->spec.checkpoint.path, engine->spec.run_id);
    engine->runner->SetCheckpoint(&*engine->checkpoint);
  }

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

void simEngineAttachTransport(SimEngine* engine, void* transport_publisher) {
  if (engine == nullptr || !engine->runner.has_value()) return;
  engine->runner->SetTransportPublisher(
      static_cast<simcore::transport::TransportPublisher*>(transport_publisher));
}

SimExitCode simEngineStepOnce(SimEngine* engine, char* err_buf, std::size_t err_buf_cap, int32_t* out_continue) {
  if (out_continue != nullptr) *out_continue = 0;
  if (engine == nullptr || !engine->runner.has_value()) {
    WriteErr(err_buf, err_buf_cap, "simEngineStepOnce called with no constructed engine");
    return kSimExitConfig;
  }
  const Result<bool> step = engine->runner->StepOnce();
  if (!step.ok()) {
    WriteErr(err_buf, err_buf_cap, step.error().Format());
    return ToC(simcore::DefaultExitCode(step.error().kind));
  }
  if (out_continue != nullptr) *out_continue = step.value() ? 1 : 0;
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
  // IMP-0426: finalise the recording (mcap's footer/index is written on
  // `Close()`, not on `Runner::Run()`'s own end-of-run `Flush()`) -- always,
  // regardless of whether `simEngineRun` was ever called or how it ended,
  // so a partial run still leaves a readable file up to its last completed
  // message.
  if (engine->writer_impl) engine->writer_impl->Close();
  delete engine;
}
