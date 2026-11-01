// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `Orchestrator` (`IMP-0017`..`IMP-0021`, `IMP-0050`, `WP-04`): the
///   event-driven step machine of `ARCH §7`. One step is all processing at one
///   simulation instant. Recorded messages enter their buffers (rank 0), a
///   ticket is made for each recorded control, new trigger-input
///   `measurement_counter` and clock tick, tickets are handed out by rank with
///   one open run per stage, a rank's outputs are committed and may make more
///   tickets in the same step, and the step ends when none is dispatchable.
///   Decides from sample headers, the setup and the queue alone: it calls no
///   component, changes no sample's bytes and reads no wall clock.
/// @author Pavan Karimajji

#include <algorithm>
#include <tuple>

#include "adas/counter.hpp"
#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {

namespace {

std::size_t DeclarationOrder(const RunSpec& spec, const std::string& stage) {
  for (std::size_t i = 0; i < spec.stages.size(); ++i) {
    if (spec.stages[i].name == stage) return i;
  }
  return spec.stages.size();
}

const SpecStage* FindSpecStage(const RunSpec& spec, const std::string& name) {
  for (const SpecStage& stage : spec.stages) {
    if (stage.name == name) return &stage;
  }
  return nullptr;
}

const SpecInput* TriggerInput(const SpecStage& stage, const std::string& trigger_input) {
  for (const SpecInput& input : stage.inputs) {
    if (input.port == trigger_input) return &input;
  }
  return nullptr;
}

std::string QualifiedTriggerPort(const SpecInput& input) { return input.producer + "." + input.producer_port; }

}  // namespace

Orchestrator::Orchestrator(const RunSpec& spec, const Graph& graph, bus::PortBus& bus, EventLog& log,
                           OrchestratorOptions options)
    : spec_(spec),
      graph_(graph),
      bus_(bus),
      log_(log),
      options_(std::move(options)),
      readiness_(spec.readiness_limit_steps) {
  for (const GraphStage& stage : graph_.stages) {
    stages_[stage.name];
    if (stage.start == StartKind::kClock) {
      queue_.AddClock(stage.name, stage.rank, DeclarationOrder(spec_, stage.name), stage.clock_period_ns,
                      options_.first_reception_ns, options_.start_ns, options_.end_ns);
    }
  }
}

std::uint64_t Orchestrator::RunsOf(const std::string& stage) const {
  const auto it = stages_.find(stage);
  return it == stages_.end() ? 0 : it->second.runs;
}

std::vector<std::size_t> Orchestrator::TriggeredBy(const std::string& port) const {
  std::vector<std::size_t> hit;
  for (std::size_t i = 0; i < graph_.stages.size(); ++i) {
    const GraphStage& stage = graph_.stages[i];
    if (stage.start != StartKind::kInput) continue;
    const SpecStage* spec_stage = FindSpecStage(spec_, stage.name);
    const SpecInput* input = spec_stage == nullptr ? nullptr : TriggerInput(*spec_stage, stage.trigger_input);
    if (input != nullptr && QualifiedTriggerPort(*input) == port) hit.push_back(i);
  }
  return hit;
}

bool Orchestrator::ContentDiffers(const std::string& port, const std::vector<std::uint8_t>& payload) const {
  const std::vector<std::size_t> stages = TriggeredBy(port);
  if (stages.empty()) return false;
  const bus::SignalHeader header = bus::ReadSignalHeader(payload, bus_.Descriptor(port));
  if (!header.measurement_counter.has_value()) return false;
  for (const std::size_t i : stages) {
    const auto it = stages_.find(graph_.stages[i].name);
    if (it == stages_.end() || !it->second.has_last_start) continue;
    if (adas::common::counterDistance(it->second.last_counter, header.measurement_counter.value()) == 0 &&
        it->second.last_payload != payload) {
      return true;
    }
  }
  return false;
}

void Orchestrator::CreateTicket(const GraphStage& stage, StartKind start, const std::string& port,
                                const std::vector<std::uint8_t>& payload, std::uint64_t not_before_step) {
  OpenTicket open;
  open.ticket.id = next_ticket_id_++;
  open.ticket.stage = stage.name;
  open.ticket.stage_order = DeclarationOrder(spec_, stage.name);
  open.ticket.rank = stage.rank;
  open.ticket.start = start;
  open.ticket.trigger_time_ns = now_ns_;
  open.ticket.trigger_port = port;
  open.ticket.trigger_payload = payload;
  open.ticket.created_step = step_;
  open.ticket.not_before_step = not_before_step;
  tickets_.push_back(std::move(open));
}

Result<bool> Orchestrator::Enter(const std::string& port, const std::vector<std::uint8_t>& payload, bus::Origin origin,
                                 std::optional<std::int64_t> capture_time_ns,
                                 std::optional<std::uint64_t> committed_step) {
  const std::vector<std::size_t> triggered = TriggeredBy(port);
  bus::PublishInfo info;
  info.content_differs = ContentDiffers(port, payload);
  info.committed_step = committed_step;

  bus::PortValue value;
  value.origin = origin;
  value.payload = payload;
  value.header.t_sim_ns = now_ns_;
  if (capture_time_ns.has_value()) value.header.t_capture_ns = *capture_time_ns;
  value.header.producer = port.substr(0, port.find('.'));
  value.header.mode = committed_step.has_value() ? bus::Mode::Simulate : bus::Mode::Measured;
  const Result<bool> published = bus_.Publish(port, std::move(value), now_ns_, info);
  if (!published.ok()) return published;

  const bus::SampleBuffer* buffer = bus_.Buffer(port);
  const bus::Sample* sample = buffer == nullptr ? nullptr : buffer->Newest();
  if (sample == nullptr) return Result<bool>::Ok(true);

  // Counter gaps and resets, from the verdict the bus's tracker just gave.
  if (bus_.Descriptor(port) != nullptr && sample->sig.measurement_counter.has_value()) {
    const bus::IdentityResult verdict = bus_.Identity().Last(port);
    const std::int64_t to = sample->sig.measurement_counter.value();
    const std::int64_t from = static_cast<std::uint32_t>(sample->sig.measurement_counter.value() -
                                                          static_cast<std::uint32_t>(verdict.measurement_distance));
    LogEntry entry;
    entry.step = step_;
    entry.port = port;
    entry.from = from;
    entry.to = to;
    if (verdict.verdict == bus::IdentityVerdict::kCounterGap) {
      entry.kind = EntryKind::kCounterGap;
      entry.missed = verdict.missed;
      const Result<bool> added = log_.Add(entry);
      if (!added.ok()) return added;
    } else if (verdict.verdict == bus::IdentityVerdict::kCounterReset) {
      entry.kind = EntryKind::kCounterReset;
      const Result<bool> added = log_.Add(entry);
      if (!added.ok()) return added;
    }
  }

  // Trigger-input stages (`IMP-0050`).
  for (const std::size_t i : triggered) {
    const GraphStage& stage = graph_.stages[i];
    StageState& state = stages_[stage.name];
    if (!sample->sig.measurement_counter.has_value()) {
      // No counter to judge by: each sample is a trigger, and nothing is remembered.
      state.has_last_start = false;
      CreateTicket(stage, StartKind::kInput, port, payload, 0);
      continue;
    }
    const std::uint32_t counter = sample->sig.measurement_counter.value();
    if (state.has_last_start && adas::common::counterDistance(state.last_counter, counter) == 0) {
      if (state.last_payload == payload) {
        LogEntry entry;
        entry.kind = EntryKind::kStalledTrigger;
        entry.step = step_;
        entry.stage = stage.name;
        entry.port = port;
        entry.counter = counter;
        const Result<bool> added = log_.Add(entry);
        if (!added.ok()) return added;
      }
      // Other bytes: the tracker has counted identity broken; either way no run.
      continue;
    }
    state.has_last_start = true;
    state.last_counter = counter;
    state.last_payload = payload;
    const SpecStage* spec_stage = FindSpecStage(spec_, stage.name);
    const SpecInput* input = spec_stage == nullptr ? nullptr : TriggerInput(*spec_stage, stage.trigger_input);
    const bool deferred = committed_step.has_value() && input != nullptr && input->previous_cycle;
    CreateTicket(stage, StartKind::kInput, port, payload, deferred ? step_ + 1 : 0);
  }
  return Result<bool>::Ok(true);
}

Result<bool> Orchestrator::BeginStep() {
  const std::optional<std::int64_t> next = queue_.NextTime();
  if (!next.has_value()) {
    // A ticket made through a previous-cycle trigger waits for a step of its own.
    const bool deferred = std::any_of(tickets_.begin(), tickets_.end(), [this](const OpenTicket& open) {
      return !open.dispatched && open.ticket.not_before_step != 0 && open.ticket.not_before_step <= step_;
    });
    return Result<bool>::Ok(deferred);
  }
  now_ns_ = *next;
  const std::vector<QueuedEvent> instant = queue_.PopInstant();
  for (const QueuedEvent& event : instant) {
    if (event.kind == QueuedEvent::Kind::kClock) {
      const GraphStage* stage = graph_.Find(event.stage);
      if (stage != nullptr) CreateTicket(*stage, StartKind::kClock, "", {}, 0);
      continue;
    }
    const Result<bool> entered = Enter(event.port, event.payload, event.origin, event.capture_time_ns, std::nullopt);
    if (!entered.ok()) return entered;
    for (const GraphStage& stage : graph_.stages) {
      if (stage.start == StartKind::kControl && event.port == stage.name + ".control") {
        CreateTicket(stage, StartKind::kControl, event.port, event.payload, 0);
      }
    }
  }
  return Result<bool>::Ok(true);
}

std::vector<Ticket> Orchestrator::NextRunnable(const ReadyFn& ready) {
  // Each stage's head: its earliest open ticket, unless that one is already out.
  std::vector<std::size_t> heads;
  std::set<std::string> seen;
  for (std::size_t i = 0; i < tickets_.size(); ++i) {
    if (!seen.insert(tickets_[i].ticket.stage).second) continue;
    if (tickets_[i].dispatched) continue;
    if (tickets_[i].ticket.not_before_step > step_) continue;
    heads.push_back(i);
  }
  std::sort(heads.begin(), heads.end(), [this](std::size_t a, std::size_t b) {
    const Ticket& x = tickets_[a].ticket;
    const Ticket& y = tickets_[b].ticket;
    return std::tie(x.rank, x.stage_order) < std::tie(y.rank, y.stage_order);
  });

  std::vector<Ticket> handed;
  std::size_t at = 0;
  while (at < heads.size() && handed.empty()) {
    const int rank = tickets_[heads[at]].ticket.rank;
    for (; at < heads.size() && tickets_[heads[at]].ticket.rank == rank; ++at) {
      OpenTicket& open = tickets_[heads[at]];
      Ticket& ticket = open.ticket;
      const bool found = !open.force_expired && ready(ticket);
      if (!found && !readiness_.IsParked(ticket.id)) readiness_.Park(ticket.id, step_);
      const std::uint64_t waited = readiness_.Waited(ticket.id, step_);
      bool expired = false;
      if (open.force_expired) {
        readiness_.Unpark(ticket.id);
        expired = true;
      } else {
        const Readiness::Verdict verdict = readiness_.Retry(ticket.id, step_, found);
        if (verdict == Readiness::Verdict::kWaiting) continue;
        expired = verdict == Readiness::Verdict::kExpired;
      }
      StageState& state = stages_[ticket.stage];
      ticket.run_number = state.runs;
      ticket.restart = state.restart_pending;
      ticket.warming_up = ticket.restart && options_.stages_with_recorded_outputs.count(ticket.stage) != 0 &&
                          ticket.trigger_time_ns != options_.first_reception_ns;
      ticket.waited_steps = waited;
      ticket.readiness_expired = expired;
      open.dispatched = true;
      handed.push_back(ticket);
    }
  }
  return handed;
}

Result<bool> Orchestrator::Commit(const std::vector<CommitReport>& reports) {
  auto find = [this](std::uint64_t id) {
    return std::find_if(tickets_.begin(), tickets_.end(),
                        [id](const OpenTicket& open) { return open.ticket.id == id; });
  };
  std::vector<const CommitReport*> ordered;
  for (const CommitReport& report : reports) {
    const auto it = find(report.ticket_id);
    if (it == tickets_.end() || !it->dispatched) {
      return Result<bool>::Fail(Error{Kind::Contract, "a ticket handed out and not yet committed",
                                      "ticket " + std::to_string(report.ticket_id), "Orchestrator::Commit", ""});
    }
    ordered.push_back(&report);
  }
  std::stable_sort(ordered.begin(), ordered.end(), [&](const CommitReport* a, const CommitReport* b) {
    return find(a->ticket_id)->ticket.stage_order < find(b->ticket_id)->ticket.stage_order;
  });
  for (const CommitReport* report : ordered) {
    const std::string stage = find(report->ticket_id)->ticket.stage;
    for (const CommittedOutput& output : report->outputs) {
      const Result<bool> entered = Enter(output.port, output.payload, output.origin, output.capture_time_ns, step_);
      if (!entered.ok()) return entered;
    }
    tickets_.erase(find(report->ticket_id));
    StageState& state = stages_[stage];
    ++state.runs;
    state.restart_pending = false;
  }
  return Result<bool>::Ok(true);
}

StepEnd Orchestrator::EndStep() {
  if (queue_.Empty()) {
    bool forced = false;
    for (OpenTicket& open : tickets_) {
      if (!open.dispatched && !open.force_expired && readiness_.IsParked(open.ticket.id)) {
        open.force_expired = true;
        forced = true;
      }
    }
    if (forced) return StepEnd::kForcedParked;
  }
  ++step_;
  return (queue_.Empty() && tickets_.empty()) ? StepEnd::kRunEnded : StepEnd::kStepEnded;
}

Result<bool> Orchestrator::Jump(std::int64_t to_ns, const SeekFn& seek) {
  queue_.Reset(to_ns);
  bus_.ClearSamples();
  tickets_.clear();
  readiness_.Clear();
  for (auto& [name, state] : stages_) {
    state.restart_pending = true;
    state.has_last_start = false;
    state.last_payload.clear();
  }
  now_ns_ = to_ns;
  if (seek) return seek(to_ns);
  return Result<bool>::Ok(true);
}

}  // namespace simcore::orchestrator
