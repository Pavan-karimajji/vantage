// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `RunStage` (`IMP-0027`, `WP-05`): one run of one stage. It builds the port
///   set from the control message (`RCT:IMP-0032`) and the selection
///   (`RCT:IMP-0033`) -- an input with no sample is handed over empty and
///   invalid, an unwired input is not offered -- applies the declared
///   overrides, calls the component through `exec` (the caller binds it to
///   `Component::Exec` under `limits.exec_timeout_ms`), and reports each output
///   whose `measurement_counter` differs from the control's (`D18 (2)`). It
///   never retries, never changes `op_mode` and reads no `compState`.
/// @author Pavan Karimajji

#include "adas/counter.hpp"
#include "simcore/runner.hpp"

namespace simcore::runner {

Result<RunStageResult> RunStage(const RunStageArgs& args, const ExecFn& exec) {
  const SpecStage& stage = *args.stage;
  RunStageResult result;
  module_host::PortMap inputs;
  module_host::InputMetaMap input_meta;

  for (const InputSelection& input : args.selection->inputs) {
    if (!input.offered) continue;
    bus::PortValue value;
    if (input.sample.has_value()) value = input.sample->value;
    if (args.mutator != nullptr && !input.producer_port.empty()) {
      const std::size_t dot = input.producer_port.find('.');
      const std::string producer = input.producer_port.substr(0, dot);
      const std::string bare = dot == std::string::npos ? input.producer_port : input.producer_port.substr(dot + 1);
      if (args.mutator->Touches(producer, bare)) {
        const Result<bool> applied = args.mutator->ApplyTo(value, bare, args.now_ns);
        if (!applied.ok()) return Result<RunStageResult>::Fail(applied.error());
      }
    }
    inputs[input.port] = value.payload;
    module_host::InputMeta meta;
    meta.valid = value.origin != bus::Origin::Unknown;
    meta.age_s = input.sample.has_value() ? static_cast<double>(args.now_ns - input.sample->arrival_ns) / 1e9 : 0.0;
    input_meta[input.port] = meta;
    value.port = stage.name + "." + input.port;
    result.delivered[value.port] = std::move(value);
  }

  if (!args.control.empty()) {
    bus::PortValue control;
    control.port = stage.name + ".control";
    control.origin = bus::Origin::Simulated;
    control.payload = args.control;
    control.header.t_sim_ns = args.now_ns;
    control.header.producer = "orchestrator";
    control.header.mode = bus::Mode::Simulate;
    inputs["control"] = args.control;
    input_meta["control"] = module_host::InputMeta{};
    result.delivered[control.port] = std::move(control);
  }

  Result<module_host::PortMap> executed = exec(args.dt_ns, inputs, input_meta);
  if (!executed.ok()) return Result<RunStageResult>::Fail(executed.error());

  result.report.ticket_id = args.ticket->id;
  for (const auto& [port_name, payload] : executed.value()) {
    const std::string qualified = stage.name + "." + port_name;
    orchestrator::CommittedOutput output;
    output.port = qualified;
    output.payload = payload;
    output.origin = bus::Origin::Simulated;
    output.capture_time_ns = args.now_ns;
    result.report.outputs.push_back(std::move(output));

    if (!args.control_counter.has_value()) continue;
    const bus::SignalHeader header = bus::ReadSignalHeader(payload, args.bus->Descriptor(qualified));
    if (!header.measurement_counter.has_value()) continue;
    const std::int32_t distance =
        adas::common::counterDistance(*args.control_counter, header.measurement_counter.value());
    if (distance == 0) continue;
    orchestrator::LogEntry entry;
    entry.kind = orchestrator::EntryKind::kOutputCounterBreak;
    entry.stage = stage.name;
    entry.port = port_name;
    entry.wanted = *args.control_counter;
    entry.found = header.measurement_counter.value();
    result.entries.push_back(std::move(entry));
  }
  return Result<RunStageResult>::Ok(std::move(result));
}

}  // namespace simcore::runner
