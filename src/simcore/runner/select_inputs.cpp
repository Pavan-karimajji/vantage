// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SelectInputs` (`RCT:IMP-0033`, `WP-05`): `VANTAGE_Architecture.md` §6,
///   run when a ticket is dispatched, for every declared data input of the
///   stage in manifest order. By the recorded refSync first (the sample whose
///   `measurement_counter` equals the entry's, searched in the arrived samples
///   and then in the read-ahead); entry 0 gives an empty input; a named sample
///   not found is the counter fallback (`D18 (1)`) up to `fallback_max_gap`
///   and the time rule beyond it; a stage with no recorded refSync for the run
///   uses the time rule on every input. A named sample of a `simulate`
///   producer that is not committed yet makes the ticket wait. The function
///   only reads: it logs and raises nothing, and decides from headers
///   (`ReadSignalHeader`) and never from a payload.
/// @author Pavan Karimajji

#include <algorithm>

#include "adas/counter.hpp"
#include "common/ref_sync.pb.h"
#include "simcore/runner.hpp"

namespace simcore::runner {

namespace {

constexpr const char* kSourceProducer = "source";

const SpecStage* StageNamed(const RunSpec& spec, const std::string& name) {
  for (const SpecStage& stage : spec.stages) {
    if (stage.name == name) return &stage;
  }
  return nullptr;
}

const SpecInput* InputOf(const SpecStage& stage, const std::string& port) {
  for (const SpecInput& input : stage.inputs) {
    if (input.port == port) return &input;
  }
  return nullptr;
}

bus::Origin OriginOfPort(const SelectContext& context, const std::string& port) {
  if (context.origins == nullptr) return bus::Origin::Measured;
  const auto it = context.origins->find(port);
  return it == context.origins->end() ? bus::Origin::Measured : it->second;
}

// A read-ahead message as a sample: it has not arrived yet, so its arrival is
// the instant it was logged at.
bus::Sample SampleOf(const SelectContext& context, const std::string& port, const AheadMessage& message,
                     const google::protobuf::Descriptor* descriptor) {
  bus::Sample sample;
  sample.sig = bus::ReadSignalHeader(message.message.payload, descriptor);
  sample.arrival_ns = message.message.log_time_ns;
  sample.value.port = port;
  sample.value.origin = OriginOfPort(context, port);
  sample.value.payload = message.message.payload;
  sample.value.header.t_sim_ns = message.message.log_time_ns;
  if (message.message.capture_time_ns.has_value()) sample.value.header.t_capture_ns = *message.message.capture_time_ns;
  sample.value.header.producer = port.substr(0, port.find('.'));
  sample.value.header.mode = bus::Mode::Measured;
  return sample;
}

// The recorded refSync entries of the run: the message whose counter equals
// the control's, found in the arrived recorded messages and then ahead.
std::optional<adas::common::RefSync> RecordedRefSync(const SelectContext& context,
                                                     const orchestrator::ControlHeader& header) {
  if (header.measurement_counter == 0) return std::nullopt;
  const std::string port = context.stage->name + ".refSync";
  const std::vector<std::uint8_t>* payload =
      context.reference == nullptr ? nullptr : context.reference->Find(port, header.measurement_counter);
  std::vector<std::uint8_t> ahead_payload;
  if (payload == nullptr && context.ahead != nullptr) {
    const AheadMessage* message =
        context.ahead->Find(port, header.measurement_counter, adas::common::RefSync::descriptor());
    if (message != nullptr) {
      ahead_payload = message->message.payload;
      payload = &ahead_payload;
    }
  }
  if (payload == nullptr) return std::nullopt;
  adas::common::RefSync ref_sync;
  if (!ref_sync.ParseFromArray(payload->data(), static_cast<int>(payload->size()))) return std::nullopt;
  return ref_sync;
}

}  // namespace

Selection SelectInputs(const SelectContext& context, const orchestrator::Ticket& ticket,
                       const orchestrator::ControlHeader& header) {
  Selection selection;
  const SpecStage& stage = *context.stage;
  const std::optional<adas::common::RefSync> ref_sync = RecordedRefSync(context, header);

  for (const SpecPort& port : stage.ports) {
    if (port.dir != "req" || port.name == "control" || port.kind == "static") continue;
    InputSelection input;
    input.port = port.name;
    const SpecInput* wired = InputOf(stage, port.name);
    if (wired == nullptr) {
      input.offered = false;
      selection.inputs.push_back(std::move(input));
      continue;
    }
    input.producer_port = wired->producer + "." + wired->producer_port;
    const bus::SampleBuffer* buffer = context.bus->Buffer(input.producer_port);
    if (buffer == nullptr) {  // an `off` producer: indistinguishable from an unmapped input
      selection.inputs.push_back(std::move(input));
      continue;
    }
    const google::protobuf::Descriptor* descriptor = context.bus->Descriptor(input.producer_port);
    const SpecStage* producer = wired->producer == kSourceProducer ? nullptr : StageNamed(*context.spec, wired->producer);
    const bool simulated_producer = producer != nullptr && producer->mode == "simulate";

    // A previous-cycle input sees only samples committed in an earlier step.
    bus::SampleBuffer earlier(buffer->Depth());
    const bus::SampleBuffer* view = buffer;
    if (wired->previous_cycle) {
      for (const bus::Sample& held : buffer->Samples()) {
        if (!held.committed_step.has_value() || *held.committed_step < context.step) earlier.Push(held);
      }
      view = &earlier;
    }

    // The time rule (`ARCH §6` rule 4): the newest sample made no later than
    // the trigger; where either time is unknown, the newest that arrived by now.
    const auto time_rule = [&]() -> const bus::Sample* {
      if (header.source_timestamp_us == 0) return view->NewestNotAfter(context.now_ns);
      const std::deque<bus::Sample>& samples = view->Samples();
      for (auto held = samples.rbegin(); held != samples.rend(); ++held) {
        if (header.source_timestamp_us != 0 && held->sig.source_timestamp_us.has_value()) {
          if (held->sig.source_timestamp_us.value() <= header.source_timestamp_us) return &*held;
        } else if (held->arrival_ns <= context.now_ns) {
          return &*held;
        }
      }
      return nullptr;
    };
    const auto by_time_rule = [&]() {
      input.fallback = true;
      const bus::Sample* picked = time_rule();
      if (picked != nullptr) input.sample = *picked;
    };

    const adas::common::RefSyncEntry* entry = nullptr;
    if (ref_sync.has_value()) {
      for (const adas::common::RefSyncEntry& candidate : ref_sync->inputs()) {
        if (candidate.port() == port.name) entry = &candidate;
      }
    }
    if (entry == nullptr) {  // no recorded refSync for this run, or none for this input
      by_time_rule();
      selection.inputs.push_back(std::move(input));
      continue;
    }
    if (entry->measurement_counter() == 0) {  // the car read nothing for this input
      selection.inputs.push_back(std::move(input));
      continue;
    }

    const std::uint32_t wanted = entry->measurement_counter();
    input.wanted = wanted;
    const bus::CounterLookup lookup = view->FindByCounter(wanted);
    input.eviction_miss = lookup.sample == nullptr && lookup.eviction_miss;
    if (lookup.sample != nullptr) {
      input.sample = *lookup.sample;
      selection.inputs.push_back(std::move(input));
      continue;
    }
    if (simulated_producer && !ticket.readiness_expired) {
      if (!selection.not_ready) selection.waiting_on = input.producer_port;
      selection.not_ready = true;
      selection.inputs.push_back(std::move(input));
      continue;
    }
    if (simulated_producer) input.readiness_timeout = true;

    // A recorded producer: the car may have logged the sample after the control that names it.
    std::vector<const AheadMessage*> ahead_samples;
    if (!simulated_producer && context.ahead != nullptr) {
      ahead_samples = context.ahead->OnPort(input.producer_port);
      bool matched = false;
      for (const AheadMessage* message : ahead_samples) {
        const bus::Sample candidate = SampleOf(context, input.producer_port, *message, descriptor);
        if (!candidate.sig.measurement_counter.has_value()) continue;
        const std::int32_t distance = adas::common::counterDistance(wanted, candidate.sig.measurement_counter.value());
        if (distance == 0) {
          input.sample = candidate;
          matched = true;
          break;
        }
      }
      if (matched) {
        selection.inputs.push_back(std::move(input));
        continue;
      }
    }

    // The counter fallback (`D18 (1)`): the newest sample whose counter is not
    // after the wanted one, among the buffer's and the read-ahead's.
    std::optional<bus::Sample> best;
    std::int32_t best_gap = 0;
    const auto consider = [&](const bus::Sample& candidate) {
      if (!candidate.sig.measurement_counter.has_value()) return;
      const std::int32_t gap = adas::common::counterDistance(candidate.sig.measurement_counter.value(), wanted);
      if (gap < 0) return;  // made after the wanted one
      if (!best.has_value() || gap <= best_gap) {
        best = candidate;
        best_gap = gap;
      }
    };
    for (const bus::Sample& held : view->Samples()) consider(held);
    for (const AheadMessage* message : ahead_samples) {
      consider(SampleOf(context, input.producer_port, *message, descriptor));
    }
    input.fallback = true;
    if (!best.has_value()) {  // the input is empty
      selection.inputs.push_back(std::move(input));
      continue;
    }
    input.found = best->sig.measurement_counter.value();
    input.gap = best_gap;
    if (best_gap > context.fallback_max_gap) {
      input.beyond_gap = true;
      const bus::Sample* picked = time_rule();
      if (picked != nullptr) input.sample = *picked;
    } else {
      input.sample = *best;
    }
    selection.inputs.push_back(std::move(input));
  }
  return selection;
}

}  // namespace simcore::runner
