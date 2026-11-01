// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IMP-0028`/`0029`/`0030`/`0114`/`0118` -- the step loop.
///
///   **ONE loop** (`SW-0109`, `ANL-SW-17`): `StepOnce()` is the only body that
///   advances the run, and `Run()` is a `while` around it. There is no second
///   `->Exec(` anywhere in `src/simcore/runner/**`; a grep for it is that
///   check's mechanised form, and this comment is where it is pointed.
///
///   **VANTAGE `c1` (`WP-05`).** The loop of `sil_host/src/resim_runner.cpp` and
///   `adas_sim/core/resim.py`, which grouped a recording by `log_time_ns` and
///   ran every stage on a grid, is replaced by one engine step (`ARCH §7`): the
///   `Orchestrator` decides when a run happens and in which order, this file
///   reads the recording ahead, selects a run's inputs, calls the component and
///   reports what it made. A `measured` or `off` stage has no component, so
///   nothing is ever called for it; its outputs reach the buffers as recorded
///   messages. The accumulation of the two ported sources is still not ported:
///   this file holds the read-ahead and one `io::Batch` per reader, and hands
///   each produced message to `io::WriterBase` as it is produced
///   (`SW-0025`, `SW-0041`).
///
///   **`IMP-0118` (`KEEP`)**: the readers are read-only in `read_ahead.cpp`.
///   Nothing the bus, the writer or a component produces is ever handed back
///   to them -- the only calls made on them are `Seek`, `ReadRange` and
///   `Describe`. `ANL-SW-25` is a static check over that fact.
/// @author Pavan Karimajji

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <limits>
#include <map>
#include <ostream>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include <google/protobuf/descriptor.h>

#include "common/cycle_control.pb.h"
#include "common/ref_sync.pb.h"
#include "simcore/runner.hpp"

namespace simcore::runner {

namespace {

constexpr const char* kSourceProducer = "source";

bus::Origin OriginOf(io::Provenance provenance) {
  switch (provenance) {
    case io::Provenance::kMeasured:
      return bus::Origin::Measured;
    case io::Provenance::kTruth:
      return bus::Origin::Truth;
    case io::Provenance::kMocked:
      return bus::Origin::Mocked;
    case io::Provenance::kSimulated:
      return bus::Origin::Simulated;
    case io::Provenance::kOverridden:
      return bus::Origin::Overridden;
    case io::Provenance::kUnknown:
      return bus::Origin::Unknown;
  }
  return bus::Origin::Unknown;  // never guess a grade (R-SIM-12)
}

std::string Trim(const std::string& raw) {
  std::size_t begin = 0;
  std::size_t end = raw.size();
  while (begin < end && std::isspace(static_cast<unsigned char>(raw[begin])) != 0) ++begin;
  while (end > begin && std::isspace(static_cast<unsigned char>(raw[end - 1])) != 0) --end;
  return raw.substr(begin, end - begin);
}

}  // namespace

// ---------------------------------------------------------------------------
// Topic <-> port-name transform (core/resim.py's own two one-liners)
// ---------------------------------------------------------------------------

std::string TopicToPortName(const std::string& topic) {
  std::size_t begin = 0;
  std::size_t end = topic.size();
  while (begin < end && topic[begin] == '/') ++begin;
  while (end > begin && topic[end - 1] == '/') --end;
  std::string out = topic.substr(begin, end - begin);
  std::replace(out.begin(), out.end(), '/', '.');
  return out;
}

// Delegates rather than re-implementing: `io::CanonicalTopic` is the single
// definition of the canonical spelling, and it is what the reader now
// normalises its own index to. Two independent copies of this transform --
// one used to build the index, one used to look it up -- is precisely how
// the index and the lookup drifted apart in the first place (F-1,
// step-zero campaign 2026-08-27). One definition, so they cannot.
//
// Behaviour is unchanged for a qualified port name: `CanonicalTopic` strips
// nothing (there are no slashes), replaces nothing, prepends '/' and turns
// only the FIRST dot into a slash -- a port name may itself contain dots
// ("<fn>.outputs", R-SIM-4) and those survive.
std::string PortNameToTopic(const std::string& qualified_port) {
  return io::CanonicalTopic(qualified_port);
}

std::optional<std::string> ProducerAddressOf(
    const RunSpec& spec, const std::string& stage, const std::string& port) {
  for (const SpecStage& candidate : spec.stages) {
    if (candidate.name != stage) continue;
    for (const SpecInput& input : candidate.inputs) {
      if (input.port == port) return input.producer + "." + input.producer_port;
    }
    return std::nullopt;  // the stage exists and simply does not wire this port
  }
  return std::nullopt;
}

bool MutationTouches(const RunSpec& spec, const std::string& stage, const std::string& port) {
  for (const SpecMutation& mutation : spec.mutations) {
    if (mutation.address.stage == stage && mutation.address.port == port) return true;
  }
  return false;
}

std::string RecordedTopicFor(
    const RunSpec& spec, const std::string& stage, const std::string& port, const std::string& dir) {
  if (dir == "req") {
    const std::optional<std::string> producer = ProducerAddressOf(spec, stage, port);
    // An unwired input has no producing identity to borrow, so it stays under
    // the consuming address -- honest: those bytes are what this stage
    // received, attributable to nobody.
    if (producer.has_value()) return PortNameToTopic(*producer);
  }
  return PortNameToTopic(stage + "." + port);
}

// ---------------------------------------------------------------------------
// IMP-0114 -- the record policy, and the derived topic list
// ---------------------------------------------------------------------------

bool RecordPolicy::WritesAt(std::uint64_t tick_index) const {
  switch (verb) {
    case RecordVerb::kFull:
      return true;
    case RecordVerb::kExcluded:
      return false;
    case RecordVerb::kDecimate:
      return decimate_n > 0 && (tick_index % static_cast<std::uint64_t>(decimate_n)) == 0;
  }
  return false;
}

Result<RecordPolicy> ParseRecordPolicy(const std::string& raw, const std::string& where) {
  const std::string value = Trim(raw);
  if (value == "full") return Result<RecordPolicy>::Ok(RecordPolicy{RecordVerb::kFull, 0});
  if (value == "excluded") return Result<RecordPolicy>::Ok(RecordPolicy{RecordVerb::kExcluded, 0});
  if (value.rfind("decimate", 0) == 0) {
    std::string rest = Trim(value.substr(std::string("decimate").size()));
    if (!rest.empty() && rest.front() == ':') rest = Trim(rest.substr(1));
    if (!rest.empty() && std::all_of(rest.begin(), rest.end(),
                                     [](char c) { return std::isdigit(static_cast<unsigned char>(c)) != 0; })) {
      const std::int64_t n = std::stoll(rest);
      if (n > 0) return Result<RecordPolicy>::Ok(RecordPolicy{RecordVerb::kDecimate, n});
    }
    return Result<RecordPolicy>::Fail(Error{Kind::Authoring, "decimate:<n> with a positive integer n",
                                            "'" + raw + "'", where, "e.g. 'decimate:10' keeps every 10th cycle"});
  }
  return Result<RecordPolicy>::Fail(Error{Kind::Authoring, "one of: full, excluded, decimate:<n>", "'" + raw + "'",
                                          where,
                                          "every declared port carries a concrete record policy (R-SIM-6, IMP-0009)"});
}

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------

const char* ToString(BadgeKind kind) {
  switch (kind) {
    case BadgeKind::kFallback:
      return "KIND_FALLBACK";
    case BadgeKind::kReadinessTimeout:
      return "KIND_READINESS_TIMEOUT";
    case BadgeKind::kIdentityBroken:
      return "KIND_IDENTITY_BROKEN";
    case BadgeKind::kComputedNotConsumed:
      return "KIND_COMPUTED_NOT_CONSUMED";
    case BadgeKind::kWarmingUp:
      return "KIND_WARMING_UP";
  }
  return "KIND_UNKNOWN";
}

// Everything the step loop owns that the orchestrator and the selection borrow
// by reference: kept on the heap so a `Runner` can be moved.
struct Runner::Impl {
  RunSpec spec;
  orchestrator::Graph graph;
  orchestrator::EventLog log;
  std::unique_ptr<orchestrator::Orchestrator> orchestrator;
  std::optional<orchestrator::ControlWriter> control;
  std::unique_ptr<ReadAhead> ahead;
  RecordedReference reference;
  bus::PortBus* bus = nullptr;
  std::map<std::string, bus::Origin> origins;
  std::set<std::string> queue_ports;      // recorded ports that enter a sample buffer
  std::set<std::string> reference_ports;  // recorded ports kept as reference (a `simulate` stage's outputs)
  std::vector<std::string> declared_ports;
  std::string plan_text;
  std::int64_t first_reception_ns = 0;
  std::size_t readiness_instants = 0;
  std::optional<std::int64_t> queued_instant;  // the recorded instant pushed to the queue, not yet begun
  bool cut = false;                            // the slice end was reached

  std::map<std::string, std::int64_t> last_run_ns;
  std::set<std::string> warming;
  std::map<std::pair<BadgeKind, std::string>, std::uint64_t> badges;
  std::map<std::string, std::size_t> identity_seen;

  // One step's own state.
  std::set<std::string> touched;                     // ports that got a sample this step
  std::map<std::string, bus::PortValue> delivered;   // what each run was handed this step

  std::ofstream event_file;
  std::size_t lines_written = 0;

  // The selection for a ticket, with the control header it is keyed by.
  Selection SelectFor(const orchestrator::Ticket& ticket, std::uint64_t step, std::int64_t now_ns,
                      orchestrator::ControlHeader& header, const SpecStage*& stage) const {
    stage = nullptr;
    for (const SpecStage& candidate : spec.stages) {
      if (candidate.name == ticket.stage) stage = &candidate;
    }
    const orchestrator::GraphStage* graph_stage = graph.Find(ticket.stage);
    const google::protobuf::Descriptor* trigger =
        ticket.start == orchestrator::StartKind::kInput ? bus->Descriptor(ticket.trigger_port) : nullptr;
    header = control->HeaderOf(ticket, *graph_stage, trigger);
    SelectContext context;
    context.spec = &spec;
    context.stage = stage;
    context.bus = bus;
    context.reference = &reference;
    context.ahead = ahead.get();
    context.origins = &origins;
    context.fallback_max_gap = spec.fallback_max_gap;
    context.now_ns = now_ns;
    context.step = step;
    return SelectInputs(context, ticket, header);
  }

  void Raise(BadgeKind kind, const std::string& subject) { ++badges[{kind, subject}]; }
};

Runner::Runner() = default;
Runner::Runner(Runner&&) noexcept = default;
Runner& Runner::operator=(Runner&&) noexcept = default;
Runner::~Runner() = default;

Result<PreflightResult> Runner::Preflight(const RunSpec& spec, const std::set<std::string>& topic_index) {
  std::set<std::string> canonical;
  for (const std::string& topic : topic_index) canonical.insert(io::CanonicalTopic(topic));
  for (const SpecStage& stage : spec.stages) {
    if (stage.mode != "measured") continue;
    std::string missing;
    for (const SpecPort& port : stage.ports) {
      if (port.dir != "pro") continue;
      if (canonical.count(io::CanonicalTopic(stage.name + "." + port.name)) != 0) continue;
      if (!missing.empty()) missing += ", ";
      missing += port.name;
    }
    if (!missing.empty()) {
      return Result<PreflightResult>::Fail(Error{Kind::Authoring,
                                                 "every output of a measured stage in the recording's topic index",
                                                 "stage '" + stage.name + "' lacks: " + missing, "RunSpec::stages",
                                                 "set the stage to simulate or off, or use a recording that holds them"});
    }
  }
  Result<orchestrator::Graph> graph = orchestrator::BuildGraph(spec, topic_index);
  if (!graph.ok()) return Result<PreflightResult>::Fail(graph.error());
  PreflightResult result;
  result.plan_text = orchestrator::PlanText(spec, graph.value());
  result.graph = std::move(graph).value();
  return Result<PreflightResult>::Ok(std::move(result));
}

Result<Runner> Runner::Construct(const RunSpec& spec, bus::PortBus& bus, std::vector<io::Reader*> readers,
                                 std::map<std::string, module_host::Component*> components,
                                 const google::protobuf::DescriptorPool* pool, io::WriterBase* writer,
                                 const mutate::Mutator* mutator, Options options) {
  Runner runner;
  runner.impl_ = std::make_unique<Impl>();
  Impl& impl = *runner.impl_;
  impl.spec = spec;
  impl.bus = &bus;
  runner.bus_ = &bus;
  runner.writer_ = writer;
  runner.mutator_ = mutator;
  runner.options_ = options;
  runner.components_ = std::move(components);
  runner.latch_ = DivergenceLatch(options.grace_ticks);

  for (const auto& stage : spec.stages) {
    const bool has_component = runner.components_.count(stage.name) != 0 &&
                               runner.components_.at(stage.name) != nullptr;
    if (stage.mode == "simulate") {
      if (!has_component) {
        return Result<Runner>::Fail(Error{Kind::Authoring, "a loaded component for every simulate stage",
                                          "stage '" + stage.name + "' has none", "RunSpec::stages",
                                          "set mode: measured or off, or load its library"});
      }
    } else if (stage.mode == "measured") {
      if (has_component) {
        // SW-0110's own Accept ("no module entry point is invoked") made
        // unbreakable rather than merely intended: a measured stage that
        // was handed a component is refused at construction, so no later
        // edit to this loop can start calling it.
        return Result<Runner>::Fail(Error{Kind::Authoring, "no loaded component for a measured stage",
                                          "stage '" + stage.name + "' was given one", "Runner::Construct",
                                          "a measured stage is fed from the recording and is never executed"});
      }
    } else if (stage.mode != "off") {
      return Result<Runner>::Fail(Error{Kind::Authoring, "one of: simulate, measured, off",
                                        "'" + stage.mode + "'", "stage '" + stage.name + "'", ""});
    }
  }

  // The topic index of the whole recording: every `sources[]` file is one.
  std::map<std::string, io::TopicInfo> described;
  std::set<std::string> topic_index;
  for (io::Reader* reader : readers) {
    for (const auto& [topic, info] : reader->Describe()) {
      topic_index.insert(topic);
      described.emplace(topic, info);
    }
  }
  Result<PreflightResult> preflight = Preflight(spec, topic_index);
  if (!preflight.ok()) return Result<Runner>::Fail(preflight.error());
  impl.graph = std::move(preflight.value().graph);
  impl.plan_text = std::move(preflight.value().plan_text);
  if (options.plan_out != nullptr) *options.plan_out << impl.plan_text;

  // IMP-0114: derived from the spec's own declared ports -- inputs AND
  // outputs -- never a hand-maintained list.
  //
  // **Two passes, `pro` before `req`, and the order matters** (F-3). Since a
  // `req` port is now recorded under its PRODUCING address, a consumer of
  // another stage's output derives the very topic that stage already records
  // as its own. Only one entry may own a topic, and it must be the producing
  // `pro` port: that port's own `record:` policy is the declaration that
  // governs this signal, and letting a consumer's entry claim it first would
  // let a `req` port marked `excluded` suppress a `pro` port marked `full`.
  // Claiming every `pro` topic before any `req` one removes that ordering
  // hazard rather than relying on the setup's stage order happening to be topological.
  std::set<std::string> claimed_topics;
  const auto build_topics = [&](const std::string& want_dir) -> Result<bool> {
    for (const SpecStage& stage : spec.stages) {
      if (stage.mode == "off") continue;
      for (const SpecPort& port : stage.ports) {
        if (port.dir != want_dir) continue;
        const std::string qualified = stage.name + "." + port.name;
        Result<RecordPolicy> policy = ParseRecordPolicy(port.record, "port '" + qualified + "'");
        if (!policy.ok()) return Result<bool>::Fail(policy.error());
        RecordedTopic topic;
        topic.topic = RecordedTopicFor(spec, stage.name, port.name, port.dir);
        topic.qualified_port = qualified;
        topic.stage = stage.name;
        topic.port = port.name;
        topic.dir = port.dir;
        topic.policy = policy.value();
        // Two consumers of one producer also collapse here, to one topic
        // carrying one value -- they read the same bus entry in the same
        // step, so the second entry would be a byte-identical duplicate.
        if (claimed_topics.insert(topic.topic).second) {
          runner.recorded_topics_.push_back(topic);
        }

        // R-SIM-15: an override may not masquerade as the source's own
        // bytes. Where a declared mutation touches this input, the producing
        // topic above keeps the TRUE upstream value and this extra entry
        // carries what the component was actually handed -- a second topic,
        // not a rename, so neither half is lost and the run stays
        // re-simulable.
        if (port.dir != "req") continue;
        const std::optional<std::string> producer = ProducerAddressOf(spec, stage.name, port.name);
        if (!producer.has_value()) continue;
        const std::size_t dot = producer->find('.');
        if (dot == std::string::npos) continue;
        if (!MutationTouches(spec, producer->substr(0, dot), producer->substr(dot + 1))) continue;
        RecordedTopic delivered = topic;
        delivered.topic = PortNameToTopic(qualified);
        delivered.post_mutation = true;
        if (claimed_topics.insert(delivered.topic).second) {
          runner.recorded_topics_.push_back(delivered);
        }
      }
    }
    return Result<bool>::Ok(true);
  };
  const Result<bool> pro_topics = build_topics("pro");
  if (!pro_topics.ok()) return Result<Runner>::Fail(pro_topics.error());
  const Result<bool> req_topics = build_topics("req");
  if (!req_topics.ok()) return Result<Runner>::Fail(req_topics.error());

  runner.boundary_ = ComputeInjectionBoundary(spec);

  // Declare every port the run publishes on (`WP-05`: declaration is mandatory).
  const auto describe = [&](const std::string& type, const std::string& port) -> const google::protobuf::Descriptor* {
    const google::protobuf::Descriptor* found = pool == nullptr ? nullptr : pool->FindMessageTypeByName(type);
    if (found == nullptr && port == "control") found = adas::common::CycleControl::descriptor();
    if (found == nullptr && port == "refSync") found = adas::common::RefSync::descriptor();
    return found;
  };
  const auto origin_of_topic = [&](const std::string& qualified) {
    const auto it = described.find(io::CanonicalTopic(qualified));
    return it == described.end() ? bus::Origin::Unknown : OriginOf(it->second.provenance);
  };
  for (const SpecStage& stage : spec.stages) {
    if (stage.mode == "off") continue;
    std::int64_t deepest = 2;
    for (const SpecPort& port : stage.ports) deepest = std::max(deepest, port.buffer_depth);
    for (const SpecPort& port : stage.ports) {
      const std::string qualified = stage.name + "." + port.name;
      const bool control_in = stage.mode == "simulate" && port.dir == "req" && port.name == "control";
      if (port.dir != "pro" && !control_in) continue;
      const google::protobuf::Descriptor* descriptor = describe(port.proto_type, port.name);
      bus.DeclarePort(qualified, port.buffer_depth, descriptor);
      impl.declared_ports.push_back(qualified);
      impl.origins[qualified] = origin_of_topic(qualified);
      if (stage.mode == "simulate" && port.dir == "pro") {
        impl.reference_ports.insert(qualified);
        impl.reference.Declare(qualified, static_cast<std::size_t>(port.buffer_depth), descriptor);
      } else {
        impl.queue_ports.insert(qualified);
      }
    }
    if (stage.mode == "simulate") {
      const std::string ref_sync = stage.name + ".refSync";
      if (!impl.reference.Declared(ref_sync)) {
        impl.reference_ports.insert(ref_sync);
        impl.reference.Declare(ref_sync, static_cast<std::size_t>(deepest), adas::common::RefSync::descriptor());
      }
    }
  }
  for (const std::string& source_port : runner.boundary_.source_ports) {
    const std::string qualified = std::string(kSourceProducer) + "." + source_port;
    std::int64_t depth = 1;
    for (const SpecStage& stage : spec.stages) {
      if (stage.mode == "off") continue;
      for (const SpecInput& input : stage.inputs) {
        if (input.producer != kSourceProducer || input.producer_port != source_port) continue;
        for (const SpecPort& port : stage.ports) {
          if (port.name == input.port && port.dir == "req") depth = std::max(depth, port.buffer_depth);
        }
      }
    }
    const auto info = described.find(io::CanonicalTopic(qualified));
    const google::protobuf::Descriptor* descriptor =
        (info == described.end() || pool == nullptr) ? nullptr : pool->FindMessageTypeByName(info->second.schema_name);
    bus.DeclarePort(qualified, depth, descriptor);
    impl.declared_ports.push_back(qualified);
    impl.origins[qualified] = origin_of_topic(qualified);
    impl.queue_ports.insert(qualified);
  }

  impl.readiness_instants = spec.readiness_limit_steps > 0 ? static_cast<std::size_t>(spec.readiness_limit_steps) : 0;
  impl.ahead = std::make_unique<ReadAhead>(std::move(readers), options.read_bounds);
  impl.ahead->Fill(impl.readiness_instants + 1);
  impl.first_reception_ns = impl.ahead->FirstTimeNs().value_or(0);

  orchestrator::OrchestratorOptions orch_options;
  orch_options.first_reception_ns = impl.first_reception_ns;
  orch_options.start_ns = options.slice.start_log_time_ns.value_or(impl.first_reception_ns);
  orch_options.end_ns = std::numeric_limits<std::int64_t>::max();
  for (const orchestrator::GraphStage& graph_stage : impl.graph.stages) {
    for (const SpecStage& stage : spec.stages) {
      if (stage.name != graph_stage.name) continue;
      for (const SpecPort& port : stage.ports) {
        if (port.dir == "pro" && described.count(io::CanonicalTopic(stage.name + "." + port.name)) != 0) {
          orch_options.stages_with_recorded_outputs.insert(stage.name);
        }
      }
    }
    if (graph_stage.computed_not_consumed) impl.Raise(BadgeKind::kComputedNotConsumed, graph_stage.name);
  }
  impl.control.emplace(impl.first_reception_ns);
  impl.orchestrator = std::make_unique<orchestrator::Orchestrator>(impl.spec, impl.graph, bus, impl.log, orch_options);

  if (!spec.outputs.path.empty()) {
    std::filesystem::path log_path(spec.outputs.path);
    log_path.replace_extension(".events.log");
    impl.event_file.open(log_path, std::ios::binary | std::ios::trunc);
    if (!impl.event_file) {
      return Result<Runner>::Fail(Error{Kind::Environment, "an event log file that can be created",
                                        "cannot open '" + log_path.string() + "'", "Runner::Construct",
                                        "the event log is written beside outputs.path"});
    }
  }

  runner.TopUp();
  return Result<Runner>::Ok(std::move(runner));
}

std::string Runner::BoundaryLine() const { return boundary_.FormatEvent(impl_->spec.run_id); }

const std::vector<std::string>& Runner::EventLogLines() const { return impl_->log.Lines(); }

void Runner::SetByteCounter(diagnostics::ByteCounter* byte_counter) { impl_->ahead->SetByteCounter(byte_counter); }

// Keeps the queue holding the whole next recorded instant, drops instants that
// only carry reference messages, and tells the clocks where the recording ends.
void Runner::TopUp() {
  Impl& impl = *impl_;
  const auto consume_reference = [&](const AheadInstant& instant) {
    for (const AheadMessage& message : instant.messages) {
      if (impl.reference_ports.count(message.port) != 0) {
        impl.reference.Add(message.port, instant.time_ns, message.message.payload);
      }
    }
  };
  const auto carries_queue_message = [&](const AheadInstant& instant) {
    return std::any_of(instant.messages.begin(), instant.messages.end(),
                       [&](const AheadMessage& message) { return impl.queue_ports.count(message.port) != 0; });
  };
  while (!impl.cut) {
    impl.ahead->Fill(impl.readiness_instants + 1);
    if (impl.queued_instant.has_value() || !impl.ahead->FrontComplete()) break;
    const AheadInstant* front = impl.ahead->Front();
    if (options_.slice.PastEnd(front->time_ns)) {
      impl.cut = true;
      impl.ahead->Stop();
      break;
    }
    if (!carries_queue_message(*front)) {  // nothing here starts a step: it is only reference
      consume_reference(impl.ahead->TakeFront());
      continue;
    }
    for (const AheadMessage& message : front->messages) {
      if (impl.queue_ports.count(message.port) == 0) continue;
      const auto origin = impl.origins.find(message.port);
      impl.orchestrator->Queue().PushRecorded(
          message.port, front->time_ns, message.source_index, message.message.payload, message.message.capture_time_ns,
          origin == impl.origins.end() ? bus::Origin::Measured : origin->second);
    }
    impl.queued_instant = front->time_ns;
  }

  const std::size_t held = impl.queued_instant.has_value() ? 1 : 0;
  if (impl.cut || (impl.ahead->Drained() && impl.ahead->Instants() <= held)) {
    std::int64_t end = impl.ahead->LastTimeNs().value_or(-1);
    if (options_.slice.end_log_time_ns.has_value()) end = std::min(end, *options_.slice.end_log_time_ns - 1);
    if (impl.cut && options_.slice.end_log_time_ns.has_value()) end = *options_.slice.end_log_time_ns - 1;
    impl.orchestrator->SetEnd(end);
  }
}

Result<bool> Runner::Prepare() {
  if (prepared_) return Result<bool>::Ok(true);
  prepared_ = true;
  if (options_.slice.start_log_time_ns.has_value()) return Seek(*options_.slice.start_log_time_ns);
  return Result<bool>::Ok(true);
}

Result<bool> Runner::Seek(std::int64_t to_ns) {
  Impl& impl = *impl_;
  const auto reseek = [&](std::int64_t at_ns) -> Result<bool> {
    impl.ahead->Seek(at_ns);
    impl.reference.Clear();
    impl.queued_instant.reset();
    impl.cut = false;
    impl.last_run_ns.clear();
    impl.warming.clear();
    impl.identity_seen.clear();
    impl.orchestrator->SetEnd(std::numeric_limits<std::int64_t>::max());
    TopUp();
    return Result<bool>::Ok(true);
  };
  const Result<bool> jumped = impl.orchestrator->Jump(to_ns, reseek);
  if (!jumped.ok()) return jumped;
  exhausted_ = false;
  outcome_.exhausted = false;
  return jumped;
}

Result<bool> Runner::RunTicket(const orchestrator::Ticket& ticket, std::vector<orchestrator::CommitReport>& reports) {
  Impl& impl = *impl_;
  const std::uint64_t step = impl.orchestrator->StepNumber();
  const std::int64_t now_ns = impl.orchestrator->Now();
  orchestrator::ControlHeader header;
  const SpecStage* stage = nullptr;
  const Selection selection = impl.SelectFor(ticket, step, now_ns, header, stage);
  const orchestrator::GraphStage* graph_stage = impl.graph.Find(ticket.stage);
  module_host::Component* component = components_.at(ticket.stage);

  const auto add = [&](orchestrator::LogEntry entry) -> Result<bool> {
    entry.step = step;
    return impl.log.Add(entry);
  };
  for (const InputSelection& input : selection.inputs) {
    const std::string subject = ticket.stage + "." + input.port;
    if (input.eviction_miss) {
      orchestrator::LogEntry entry;
      entry.kind = orchestrator::EntryKind::kEvictionMiss;
      entry.stage = ticket.stage;
      entry.port = input.port;
      entry.wanted = input.wanted;
      const Result<bool> added = add(entry);
      if (!added.ok()) return added;
    }
    if (input.beyond_gap) {
      orchestrator::LogEntry entry;
      entry.kind = orchestrator::EntryKind::kFallbackBeyondGap;
      entry.stage = ticket.stage;
      entry.port = input.port;
      entry.wanted = input.wanted;
      entry.found = input.found;
      entry.gap = input.gap;
      const Result<bool> added = add(entry);
      if (!added.ok()) return added;
    }
    if (input.readiness_timeout) impl.Raise(BadgeKind::kReadinessTimeout, subject);
    if (input.fallback) impl.Raise(BadgeKind::kFallback, subject);
  }

  RunStageArgs args;
  args.stage = stage;
  args.ticket = &ticket;
  args.selection = &selection;
  args.bus = bus_;
  args.mutator = mutator_;
  args.now_ns = now_ns;
  const auto last = impl.last_run_ns.find(ticket.stage);
  args.dt_ns = last == impl.last_run_ns.end() ? 0 : now_ns - last->second;
  if (header.measurement_counter != 0) args.control_counter = header.measurement_counter;
  const bool declares_control = std::any_of(stage->ports.begin(), stage->ports.end(), [](const SpecPort& port) {
    return port.dir == "req" && port.name == "control";
  });
  if (declares_control) {
    const google::protobuf::Descriptor* trigger =
        ticket.start == orchestrator::StartKind::kInput ? bus_->Descriptor(ticket.trigger_port) : nullptr;
    args.control = impl.control->Write(ticket, *graph_stage, trigger);
  }
  const ExecFn exec = [&](std::int64_t dt_ns, const module_host::PortMap& inputs,
                          const module_host::InputMetaMap& input_meta) {
    std::optional<module_host::ExecTimeout> timeout;
    if (options_.exec_timeout.has_value()) timeout.emplace(*options_.exec_timeout);
    return component->Exec(dt_ns, inputs, input_meta, timeout);
  };
  Result<RunStageResult> ran = RunStage(args, exec);
  if (!ran.ok()) return Result<bool>::Fail(ran.error());
  RunStageResult result = std::move(ran).value();
  for (orchestrator::LogEntry& entry : result.entries) {
    const Result<bool> added = add(entry);
    if (!added.ok()) return added;
  }
  impl.last_run_ns[ticket.stage] = now_ns;
  for (auto& [port, value] : result.delivered) impl.delivered[port] = std::move(value);

  // IMP-0116: against what the recording holds for this same port at this same instant.
  // KIND_WARMING_UP: a stage restarted mid-recording is badged until its
  // outputs first equal the recorded ones (byte equality here; `WP-06`
  // makes the comparison header-aware).
  if (ticket.warming_up) impl.warming.insert(ticket.stage);
  bool compared = false;
  bool equal = true;
  for (const orchestrator::CommittedOutput& output : result.report.outputs) {
    const std::vector<std::uint8_t>* recorded = impl.reference.AtTime(output.port, now_ns);
    if (recorded == nullptr) continue;
    const std::string bare = output.port.substr(ticket.stage.size() + 1);
    latch_.Observe(step, now_ns, ticket.stage, bare, output.payload, *recorded);
    compared = true;
    if (*recorded != output.payload) equal = false;
  }
  if (impl.warming.count(ticket.stage) != 0) {
    if (compared && equal && !ticket.restart) {
      impl.warming.erase(ticket.stage);
    } else {
      impl.Raise(BadgeKind::kWarmingUp, ticket.stage);
    }
  }
  reports.push_back(std::move(result.report));
  return Result<bool>::Ok(true);
}

Result<std::size_t> Runner::WriteStep(std::uint64_t step, std::int64_t now_ns) {
  Impl& impl = *impl_;
  std::size_t bytes_written = 0;
  if (writer_ == nullptr && transport_publisher_ == nullptr) return Result<std::size_t>::Ok(bytes_written);
  const bool informational = latch_.InformationalOnly(step);
  const auto newest = [&](const std::string& port) -> const bus::Sample* {
    const bus::SampleBuffer* buffer = bus_->Buffer(port);
    return buffer == nullptr ? nullptr : buffer->Newest();
  };
  for (const RecordedTopic& topic : recorded_topics_) {
    if (!topic.policy.WritesAt(step)) continue;
    bus::PortValue value;
    if (topic.dir == "req") {
      const std::optional<std::string> producer = ProducerAddressOf(impl.spec, topic.stage, topic.port);
      if (topic.post_mutation || !producer.has_value()) {
        // What the stage was handed this step, post-mutation -- or, for an
        // input nobody wired (its `control`), the message written for it.
        const auto delivered = impl.delivered.find(topic.qualified_port);
        if (delivered == impl.delivered.end()) continue;
        value = delivered->second;
      } else {
        // F-3: the producing-name entry takes the upstream value straight off
        // the buffer, before any override, so this topic means what its name says.
        if (impl.touched.count(*producer) == 0) continue;
        const bus::Sample* sample = newest(*producer);
        if (sample == nullptr) continue;
        value = sample->value;
      }
    } else {
      if (impl.touched.count(topic.qualified_port) == 0) continue;
      const bus::Sample* sample = newest(topic.qualified_port);
      if (sample == nullptr) continue;
      value = sample->value;
    }
    if (writer_ != nullptr) {
      io::RawMessage message;
      message.topic = topic.topic;
      message.log_time_ns = now_ns;
      if (value.header.t_capture_ns.has_value()) message.capture_time_ns = value.header.t_capture_ns.value();
      message.payload = value.payload;
      message.informational_only = informational;
      bytes_written += message.payload.size();
      writer_->WriteMessage(message);
    }
    // SI-25 transport (UT-TRN-*): the same value the recorder would have
    // written, named from the TOPIC (F-3), keyed by the step number.
    if (transport_publisher_ != nullptr) {
      transport_publisher_->Publish(step, TopicToPortName(topic.topic), value.payload.data(), value.payload.size());
    }
  }
  return Result<std::size_t>::Ok(bytes_written);
}

Result<bool> Runner::StepOnce() {
  if (!prepared_) {
    Result<bool> prepared = Prepare();
    if (!prepared.ok()) return prepared;
  }
  if (exhausted_) return Result<bool>::Ok(false);
  Impl& impl = *impl_;
  orchestrator::Orchestrator& orch = *impl.orchestrator;

  TopUp();
  const Result<bool> begun = orch.BeginStep();
  if (!begun.ok()) return begun;
  if (!begun.value()) {
    exhausted_ = true;
    outcome_.exhausted = true;
    return Result<bool>::Ok(false);
  }
  const std::uint64_t step = orch.StepNumber();
  const std::int64_t now_ns = orch.Now();
  impl.touched.clear();
  impl.delivered.clear();

  // The recorded instant just entered its buffers: note which ports got a
  // sample, keep a `simulate` stage's recorded outputs as reference, and queue
  // the next instant.
  if (impl.queued_instant.has_value() && *impl.queued_instant == now_ns) {
    const AheadInstant instant = impl.ahead->TakeFront();
    impl.queued_instant.reset();
    for (const AheadMessage& message : instant.messages) {
      if (impl.reference_ports.count(message.port) != 0) {
        impl.reference.Add(message.port, instant.time_ns, message.message.payload);
      } else if (impl.queue_ports.count(message.port) != 0) {
        impl.touched.insert(message.port);
      }
    }
  }
  TopUp();

  // ---- IMP-0029: per rank the runnable tickets run and commit, until the step ends.
  const auto ready = [&](const orchestrator::Ticket& ticket) {
    orchestrator::ControlHeader header;
    const SpecStage* stage = nullptr;
    return !impl.SelectFor(ticket, step, now_ns, header, stage).not_ready;
  };
  for (;;) {
    for (;;) {
      std::vector<orchestrator::Ticket> tickets = orch.NextRunnable(ready);
      if (tickets.empty()) break;
      std::vector<orchestrator::CommitReport> reports;
      for (const orchestrator::Ticket& ticket : tickets) {
        const Result<bool> ran = RunTicket(ticket, reports);
        if (!ran.ok()) return ran;
      }
      for (const orchestrator::CommitReport& report : reports) {
        for (const orchestrator::CommittedOutput& output : report.outputs) impl.touched.insert(output.port);
      }
      const Result<bool> committed = orch.Commit(reports);
      if (!committed.ok()) return committed;
    }
    const orchestrator::StepEnd end = orch.EndStep();
    if (end == orchestrator::StepEnd::kForcedParked) continue;
    if (end == orchestrator::StepEnd::kRunEnded) {
      exhausted_ = true;
      outcome_.exhausted = true;
    }
    break;
  }

  // KIND_IDENTITY_BROKEN: per sample, counted from the bus's tracker.
  for (const std::string& port : impl.declared_ports) {
    const std::size_t broken = bus_->Identity().Counts(port).identity_broken;
    std::size_t& seen = impl.identity_seen[port];
    if (broken > seen) impl.badges[{BadgeKind::kIdentityBroken, port}] += broken - seen;
    seen = broken;
  }

  // ---- IMP-0114: offer every value of this step to the writer; IMP-0117: from the
  // divergence point plus the grace window each carries the flag.
  const Result<std::size_t> written = WriteStep(step, now_ns);
  if (!written.ok()) return Result<bool>::Fail(written.error());

  // ---- IMP-0119: the step is complete -- and only now is it recorded as such.
  outcome_.cycles_executed += 1;
  outcome_.last_log_time_ns = now_ns;
  outcome_.divergence = latch_.first();
  if (checkpoint_ != nullptr) {
    // IMP-0139: the exact bytes delivered to every executing stage this step.
    // Set BEFORE RecordCompleted, which may flush synchronously.
    std::map<std::string, std::vector<std::uint8_t>> inputs_this_step;
    for (const auto& [qualified_port, value] : impl.delivered) inputs_this_step[qualified_port] = value.payload;
    checkpoint_->RecordInputs(inputs_this_step);
    checkpoint_->RecordCompleted(step, now_ns, written.value());
    // IMP-0224: AFTER RecordCompleted, so one write carries both.
    if (outcome_.divergence.has_value()) checkpoint_->RecordDivergence(*outcome_.divergence);
  }

  // The event log's file: every line added so far, flushed per step so a crash leaves it.
  if (impl.event_file.is_open()) {
    const std::vector<std::string>& lines = impl.log.Lines();
    for (; impl.lines_written < lines.size(); ++impl.lines_written) impl.event_file << lines[impl.lines_written] << '\n';
    impl.event_file.flush();
  }

  // IMP-0030: what the live measurement writer's `liveMeasStep` will be handed.
  if (live_sink_ != nullptr) {
    StepReport report;
    report.step = step;
    report.sim_time_ns = now_ns;
    for (const std::string& port : impl.declared_ports) {
      const bus::SampleBuffer* buffer = bus_->Buffer(port);
      const bus::Sample* sample = buffer == nullptr ? nullptr : buffer->Newest();
      if (sample == nullptr) continue;
      StepValue value;
      value.port = port;
      value.payload = &sample->value.payload;
      value.origin = sample->value.origin;
      value.age_ns = now_ns - sample->arrival_ns;
      report.values.push_back(std::move(value));
    }
    for (const auto& [key, count] : impl.badges) {
      if (count > 0) report.badges.push_back(StepBadge{key.first, key.second, count});
    }
    live_sink_->OnStep(report);
  }
  return Result<bool>::Ok(true);
}

Result<RunOutcome> Runner::Run() {
  Result<bool> prepared = Prepare();
  if (!prepared.ok()) return Result<RunOutcome>::Fail(prepared.error());
  for (;;) {
    // The single stepping entry point (ANL-SW-17). There is no alternative
    // body here, and adding one would be the defect that check names.
    Result<bool> stepped = StepOnce();
    if (!stepped.ok()) return Result<RunOutcome>::Fail(stepped.error());
    if (!stepped.value()) break;
  }
  if (checkpoint_ != nullptr) checkpoint_->Flush();
  if (writer_ != nullptr) writer_->Flush();
  return Result<RunOutcome>::Ok(outcome_);
}

}  // namespace simcore::runner
