// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IMP-0109`/`0110`/`0112`/`0114`/`0118` -- the cycle loop.
///
///   **ONE loop** (`SW-0109`, `ANL-SW-17`): `StepOnce()` is the only body
///   that advances the run, and `Run()` is a `while` around it. There is no
///   second `Advance()` and no second `->Exec(` anywhere in
///   `src/simcore/runner/**`; a grep for either is that check's mechanised
///   form, and this comment is where it is pointed.
///
///   **Ported from `sil_host/src/resim_runner.cpp::RunResim` and
///   `adas_sim/core/resim.py::resim_pipeline`**, read directly: the
///   per-cycle stimulus extraction, the per-measured-stage recorded-output
///   extraction, the `dt_ns` from consecutive log times and the
///   `Exec`-under-a-timeout are all theirs. **The accumulation is not**:
///   both sources build the whole recording and the whole result in memory
///   first (`recording.ticks()` / `list(reader.messages())`, then
///   `results.emplace_back` / `results.append`). This file holds one
///   cycle's messages plus whatever a single `io::Batch` carried, and hands
///   each produced message to `io::WriterBase` as it is produced
///   (`SW-0025`, `SW-0041`).
///
///   **`IMP-0110`/`IMP-0112` are the SAME mechanism, not two branches.**
///   A stage is executed iff a loaded `module_host::Component` exists for
///   it. A `measured` stage has none -- its declared outputs are published
///   onto the bus straight from this cycle's recorded bytes -- and an `off`
///   stage has none and publishes nothing. Nowhere in this file is there an
///   `if (mode == "off")`: an `off` stage's ports are absent, and
///   `PortBus::Get` already answers for an absent port exactly as it
///   answers for an input nothing ever wired (`Origin::Unknown`,
///   `updated=false`, empty payload). That is `CN-0320`'s "no code path
///   distinguishes absent-because-off from absent-because-unmapped", and it
///   is true here by not writing the branch rather than by testing for it.
///
///   **`IMP-0118` (`KEEP`)**: `reader_` is read-only in this file. Nothing
///   the bus, the writer or a component produces is ever handed back to it
///   -- the only calls made on it are `Seek`, `ReadRange` and `Describe`.
///   `ANL-SW-25` is a static check over that fact.
/// @author Pavan Karimajji

#include <algorithm>
#include <cctype>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>

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

std::string PortNameToTopic(const std::string& qualified_port) {
  std::string out = "/" + qualified_port;
  // Only the FIRST dot separates producer from port: a port name may itself
  // contain dots ("<fn>.outputs", R-SIM-4), and `_topic_to_port_name`'s own
  // inverse in Python has the identical property for the topics this
  // framework writes ("/df/<fn>.outputs").
  const std::size_t dot = out.find('.');
  if (dot != std::string::npos) out[dot] = '/';
  return out;
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

Result<Runner> Runner::Construct(const RunSpec& spec, scheduler::Scheduler& scheduler, bus::PortBus& bus,
                                 io::Reader& reader, std::map<std::string, module_host::Component*> components,
                                 io::WriterBase* writer, const mutate::Mutator* mutator, Options options) {
  Runner runner;
  runner.spec_ = spec;
  runner.scheduler_ = &scheduler;
  runner.bus_ = &bus;
  runner.reader_ = &reader;
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
      runner.execute_stages_.push_back(stage.name);
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
      runner.inject_stages_.push_back(stage.name);
    } else if (stage.mode != "off") {
      return Result<Runner>::Fail(Error{Kind::Authoring, "one of: simulate, measured, off",
                                        "'" + stage.mode + "'", "stage '" + stage.name + "'", ""});
    }
    if (stage.mode == "off") continue;

    // IMP-0114: derived from the spec's own declared ports -- inputs AND
    // outputs -- never a hand-maintained list.
    for (const auto& port : stage.ports) {
      const std::string qualified = stage.name + "." + port.name;
      Result<RecordPolicy> policy = ParseRecordPolicy(port.record, "port '" + qualified + "'");
      if (!policy.ok()) return Result<Runner>::Fail(policy.error());
      RecordedTopic topic;
      topic.topic = PortNameToTopic(qualified);
      topic.qualified_port = qualified;
      topic.stage = stage.name;
      topic.port = port.name;
      topic.dir = port.dir;
      topic.policy = policy.value();
      runner.recorded_topics_.push_back(topic);
    }
  }
  return Result<Runner>::Ok(std::move(runner));
}

Result<bool> Runner::Prepare() {
  if (prepared_) return Result<bool>::Ok(true);
  boundary_ = ComputeInjectionBoundary(spec_);
  // SW-0113: ONE structured event, before tick 0.
  event_log_.push_back(boundary_.FormatEvent(spec_.run_id));
  SeekToSliceStart(*reader_, options_.slice);
  prepared_ = true;
  return Result<bool>::Ok(true);
}

bool Runner::PullCycle(std::map<std::string, RecordedMessage>& payloads_by_port, std::int64_t& log_time_ns) {
  payloads_by_port.clear();
  bool have_time = false;
  std::int64_t cycle_time_ns = 0;

  for (;;) {
    if (carry_.empty()) {
      if (reader_drained_) break;
      io::Batch batch = reader_->ReadRange(options_.read_bounds);
      if (batch.exhausted) reader_drained_ = true;
      carry_ = std::move(batch.messages);
      if (carry_.empty()) break;
    }
    std::size_t consumed = 0;
    bool boundary_hit = false;
    for (; consumed < carry_.size(); ++consumed) {
      const io::RawMessage& msg = carry_[consumed];
      if (!have_time) {
        cycle_time_ns = msg.log_time_ns;
        have_time = true;
      } else if (msg.log_time_ns != cycle_time_ns) {
        boundary_hit = true;
        break;
      }
      payloads_by_port[TopicToPortName(msg.topic)] = RecordedMessage{msg.payload, msg.capture_time_ns};
      if (byte_counter_ != nullptr) byte_counter_->Observe(msg.topic, msg.payload.size());
    }
    carry_.erase(carry_.begin(), carry_.begin() + static_cast<std::ptrdiff_t>(consumed));
    if (boundary_hit) break;
  }

  if (!have_time) return false;
  log_time_ns = cycle_time_ns;
  return true;
}

Result<bool> Runner::StepOnce() {
  if (!prepared_) {
    Result<bool> prepared = Prepare();
    if (!prepared.ok()) return prepared;
  }
  if (exhausted_) return Result<bool>::Ok(false);

  std::map<std::string, RecordedMessage> recorded;
  std::int64_t t_ns = 0;
  // A codec whose `Seek` is a no-op still yields a correct slice: cycles
  // before the slice start are skipped here rather than executed. A codec
  // with a real `Seek` (mcap) simply never delivers them.
  for (;;) {
    if (!PullCycle(recorded, t_ns)) {
      exhausted_ = true;
      outcome_.exhausted = true;
      return Result<bool>::Ok(false);
    }
    if (options_.slice.PastEnd(t_ns)) {
      exhausted_ = true;
      outcome_.exhausted = true;
      return Result<bool>::Ok(false);
    }
    if (options_.slice.Contains(t_ns)) break;
  }

  const std::int64_t dt_ns = previous_log_time_ns_.has_value() ? t_ns - *previous_log_time_ns_ : 0;
  previous_log_time_ns_ = t_ns;
  const std::uint64_t tick_index = scheduler_->tick_index();
  const std::int64_t now_ns = scheduler_->now_ns();

  const std::map<std::string, io::TopicInfo> topics = reader_->Describe();
  auto origin_for = [&topics](const std::string& qualified_port) {
    const auto it = topics.find(PortNameToTopic(qualified_port));
    // SW-0039/R-SIM-12: an origin nobody can establish reads `unknown`,
    // never a guessed grade -- a topic this recording's own index does not
    // describe is exactly that case, not evidence it was "measured".
    if (it == topics.end()) return bus::Origin::Unknown;
    return OriginOf(it->second.provenance);
  };

  // ---- IMP-0110: a measured stage, and every source-fed port, publish
  // from the recording. No component exists for either, so nothing is
  // executed for them anywhere below.
  auto publish_recorded = [&](const std::string& qualified_port, const std::string& producer) -> Result<bool> {
    const auto it = recorded.find(qualified_port);
    if (it == recorded.end()) return Result<bool>::Ok(false);
    bus::PortValue value;
    value.port = qualified_port;
    value.origin = origin_for(qualified_port);
    value.updated = true;
    value.payload = it->second.payload;
    value.header.t_sim_ns = now_ns;
    if (it->second.capture_time_ns.has_value()) value.header.t_capture_ns = it->second.capture_time_ns.value();
    value.header.producer = producer;
    value.header.mode = bus::Mode::Measured;
    return bus_->Publish(qualified_port, std::move(value), now_ns);
  };

  for (const std::string& port : boundary_.source_ports) {
    Result<bool> published = publish_recorded(std::string(kSourceProducer) + "." + port, kSourceProducer);
    if (!published.ok()) return published;
  }
  for (const std::string& stage_name : inject_stages_) {
    for (const auto& stage : spec_.stages) {
      if (stage.name != stage_name) continue;
      for (const auto& port : stage.ports) {
        if (port.dir != "pro") continue;
        Result<bool> published = publish_recorded(stage.name + "." + port.name, stage.name);
        if (!published.ok()) return published;
      }
    }
  }

  // ---- Execution. `Order()` is the spec's own resolved order (SW-0072);
  // a stage with no loaded component is simply not in `components_`, which
  // is what makes measured and off need no branch of their own here.
  //
  // IMP-0114's own "every stage's inputs -- not just outputs -- is
  // recorded" (R-SIM-6) needs the value actually DELIVERED to a `req` port
  // this cycle, post-mutation: the bus stores a req port's value under its
  // PRODUCER's own qualified name (e.g. "meas.objects"), never under the
  // consuming stage's local name ("sut.objects"), so the write pass below
  // cannot recover it with a second `bus_->Get(topic.qualified_port, ...)`
  // -- that key was never published under that name. This map is the one
  // place that delivered value is captured, keyed exactly as
  // `RecordedTopic::qualified_port` already is for a `req` port
  // ("<stage>.<port>"), so the write pass can look it up directly.
  std::map<std::string, bus::PortValue> delivered_req_;
  for (const std::string& stage_name : scheduler_->Order()) {
    const auto component_it = components_.find(stage_name);
    if (component_it == components_.end() || component_it->second == nullptr) continue;
    if (!scheduler_->IsDue(stage_name)) continue;

    const SpecStage* stage = nullptr;
    for (const auto& candidate : spec_.stages) {
      if (candidate.name == stage_name) stage = &candidate;
    }
    if (stage == nullptr) continue;

    // SW-0057: the FULL declared req port set, every cycle, regardless of
    // which producers ran -- so a consumer cannot tell simulate from
    // measured from absent.
    module_host::PortMap inputs;
    module_host::InputMetaMap input_meta;
    for (const auto& port : stage->ports) {
      if (port.dir != "req") continue;
      std::string qualified = port.name;
      for (const auto& input : stage->inputs) {
        if (input.port == port.name) qualified = input.producer + "." + input.producer_port;
      }
      bus::PortValue value = bus_->Get(qualified, now_ns);
      if (mutator_ != nullptr) {
        const std::size_t dot = qualified.find('.');
        const std::string producer = dot == std::string::npos ? std::string() : qualified.substr(0, dot);
        const std::string bare = dot == std::string::npos ? qualified : qualified.substr(dot + 1);
        if (mutator_->Touches(producer, bare)) {
          Result<bool> applied = mutator_->ApplyTo(value, bare, now_ns);
          if (!applied.ok()) return applied;
        }
      }
      inputs[port.name] = value.payload;
      module_host::InputMeta meta;
      meta.valid = value.origin != bus::Origin::Unknown;
      meta.age_s = value.age_ns().has_value() ? static_cast<double>(value.age_ns().value()) / 1e9 : 0.0;
      input_meta[port.name] = meta;
      // IMP-0114: the exact bytes delivered to this port this cycle,
      // post-mutation -- what the write pass below records for a `req`
      // topic (see this loop's own top-of-block note).
      delivered_req_[stage_name + "." + port.name] = value;
    }

    std::optional<module_host::ExecTimeout> timeout;
    if (options_.exec_timeout.has_value()) timeout.emplace(*options_.exec_timeout);
    Result<module_host::PortMap> executed = component_it->second->Exec(dt_ns, inputs, input_meta, timeout);
    if (!executed.ok()) return Result<bool>::Fail(executed.error());

    for (const auto& [port_name, payload] : executed.value()) {
      const std::string qualified = stage_name + "." + port_name;
      // IMP-0116: compare against what the recording holds for this same
      // port at this same cycle, before the value is published or written.
      const auto recorded_it = recorded.find(qualified);
      if (recorded_it != recorded.end()) {
        latch_.Observe(tick_index, t_ns, stage_name, port_name, payload, recorded_it->second.payload);
      }
      bus::PortValue value;
      value.port = qualified;
      value.origin = bus::Origin::Simulated;
      value.updated = true;
      value.payload = payload;
      value.header.t_sim_ns = now_ns;
      value.header.t_capture_ns = t_ns;
      value.header.producer = stage_name;
      value.header.mode = bus::Mode::Simulate;
      Result<bool> published = bus_->Publish(qualified, std::move(value), now_ns);
      if (!published.ok()) return published;
    }
  }

  // ---- IMP-0114: offer every declared port to the writer, filtered only
  // by its own declared policy. IMP-0117: every message written from the
  // divergence point plus the grace window carries the flag.
  //
  // A `req` topic's value is never a second `bus_->Get(topic.qualified_port,
  // ...)` -- the bus never holds anything under a consuming stage's LOCAL
  // name for its own inputs, so that lookup would always miss and silently
  // drop every declared input topic (`delivered_req_`'s own top-of-block
  // note above). Two sources, tried in order: (1) `delivered_req_` -- the
  // EXACT bytes actually delivered this cycle, post-mutation, for a stage
  // that executed; (2) for a stage with no loaded component (a `measured`
  // stage's own declared inputs -- it consumes nothing IN this process, so
  // nothing is ever "delivered" to it here) the producer-qualified address
  // resolved from `RunSpec::stages[].inputs`, the same resolution the
  // execution loop uses, read straight off the bus. A `req` port whose
  // stage executed but was not due this cycle has no delivered value and
  // is correctly not written -- there was no delivery to record.
  auto resolve_producer_qualified = [this](const std::string& stage_name2,
                                           const std::string& port_name2) -> std::optional<std::string> {
    for (const auto& candidate : spec_.stages) {
      if (candidate.name != stage_name2) continue;
      for (const auto& input : candidate.inputs) {
        if (input.port == port_name2) return input.producer + "." + input.producer_port;
      }
    }
    return std::nullopt;
  };

  std::size_t bytes_written_this_cycle = 0;
  if (writer_ != nullptr || transport_publisher_ != nullptr) {
    const bool informational = latch_.InformationalOnly(tick_index);
    for (const RecordedTopic& topic : recorded_topics_) {
      if (!topic.policy.WritesAt(tick_index)) continue;
      bus::PortValue value;
      if (topic.dir == "req") {
        const auto delivered_it = delivered_req_.find(topic.qualified_port);
        if (delivered_it != delivered_req_.end()) {
          value = delivered_it->second;
        } else {
          const std::optional<std::string> producer_qualified = resolve_producer_qualified(topic.stage, topic.port);
          if (!producer_qualified.has_value()) continue;  // an unwired input has nothing to record
          value = bus_->Get(*producer_qualified, now_ns);
          if (value.origin == bus::Origin::Unknown) continue;
        }
      } else {
        value = bus_->Get(topic.qualified_port, now_ns);
        if (value.origin == bus::Origin::Unknown) continue;  // nothing has ever produced it
      }
      if (writer_ != nullptr) {
        io::RawMessage message;
        message.topic = topic.topic;
        message.log_time_ns = t_ns;
        if (value.header.t_capture_ns.has_value()) message.capture_time_ns = value.header.t_capture_ns.value();
        message.payload = value.payload;
        message.informational_only = informational;
        bytes_written_this_cycle += message.payload.size();
        writer_->WriteMessage(message);
      }
      // SI-25 transport (UT-TRN-*): the same value the recorder would have
      // written, handed to the live-viewer publisher instead/as well --
      // independent of whether a writer exists at all (a resim with no
      // writer can still be watched live).
      if (transport_publisher_ != nullptr) {
        transport_publisher_->Publish(tick_index, topic.qualified_port, value.payload.data(), value.payload.size());
      }
    }
  }

  // ---- IMP-0119: the cycle is complete -- and only now is it recorded as
  // such (a checkpoint written earlier could name a cycle the output does
  // not contain).
  outcome_.cycles_executed += 1;
  outcome_.last_log_time_ns = t_ns;
  outcome_.divergence = latch_.first();
  if (checkpoint_ != nullptr) {
    // IMP-0139: the exact bytes delivered to every executing stage's req
    // port THIS cycle -- the same map IMP-0114's own write pass already
    // reads from (see `delivered_req_`'s own top-of-block note above).
    // Set BEFORE RecordCompleted, not after: RecordCompleted's own
    // unbounded-flush default writes synchronously inside that call, so
    // recording inputs afterward would flush the PREVIOUS cycle's capture
    // paired with THIS cycle's progress.json (found live, off by one cycle,
    // before this ordering was fixed).
    std::map<std::string, std::vector<std::uint8_t>> inputs_this_cycle;
    for (const auto& [qualified_port, value] : delivered_req_) inputs_this_cycle[qualified_port] = value.payload;
    checkpoint_->RecordInputs(inputs_this_cycle);
    checkpoint_->RecordCompleted(tick_index, t_ns, bytes_written_this_cycle);
    // IMP-0224: AFTER RecordCompleted, not before -- so if this is the
    // cycle divergence first latches, the same write that carries it also
    // carries THIS cycle's own completed tick_index/log_time_ns, not the
    // previous cycle's (RecordDivergence's own Write() is immediate,
    // independent of RecordCompleted's bounded flush schedule). A no-op on
    // every cycle after the first divergence (RecordDivergence's own
    // idempotence).
    if (outcome_.divergence.has_value()) checkpoint_->RecordDivergence(*outcome_.divergence);
  }

  scheduler_->Advance();
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
