// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `PortBus` -- see `simcore/bus.hpp` for the design note. Ported
///   from `sil_host/src/pipeline.cpp::Pipeline::Step`'s own
///   `lastOutput_`/`lastDueNs_` hold pair, widened to integer-nanosecond
///   `hold_ns` (`SW-0046`) instead of the C++ side's `double holdAgeS`.
/// @author Pavan Karimajji

#include "simcore/bus.hpp"

#include <algorithm>

namespace simcore::bus {

PortBus::PortBus(std::size_t byte_budget) : byte_budget_(byte_budget) {}

void PortBus::DeclarePort(const PortId& port, std::int64_t buffer_depth, const google::protobuf::Descriptor* descriptor) {
  Slot& slot = slots_[port];
  slot.buffer = SampleBuffer(buffer_depth < 1 ? std::size_t{1} : static_cast<std::size_t>(buffer_depth));
  slot.descriptor = descriptor;
}

const SampleBuffer* PortBus::Buffer(const PortId& port) const {
  const auto it = slots_.find(port);
  return it == slots_.end() ? nullptr : &it->second.buffer;
}

Result<bool> PortBus::Publish(const PortId& port, PortValue value, std::int64_t now_ns) {
  Slot& slot = slots_[port];
  const Sample* previous = slot.buffer.Newest();
  const bool reused = previous != nullptr && previous->payload().capacity() >= value.payload.size();

  value.port = port;
  value.updated = true;
  value.hold_ns = std::int64_t{0};

  Sample sample;
  sample.sig = ReadSignalHeader(value.payload, slot.descriptor);
  sample.arrival_ns = now_ns;
  sample.value = std::move(value);
  if (slot.descriptor != nullptr) identity_.Observe(port, sample.sig);
  slot.buffer.Push(std::move(sample));
  slot.last_produced_ns = now_ns;

  if (reused) {
    ++stats_.reuse_count;
  }

  std::size_t total = 0;
  for (const auto& [id, s] : slots_) {
    for (const Sample& held : s.buffer.Samples()) total += held.payload().capacity();
  }
  stats_.total_bytes = total;
  stats_.high_water_bytes = std::max(stats_.high_water_bytes, total);

  if (byte_budget_ != 0 && total > byte_budget_) {
    return Result<bool>::Fail(Error{
        Kind::Contract, "total buffer bytes within the declared budget", std::to_string(total), port,
        "declared budget " + std::to_string(byte_budget_) + " bytes"});
  }
  return Result<bool>::Ok(true);
}

PortValue PortBus::Get(const PortId& port, std::int64_t now_ns) const {
  const auto it = slots_.find(port);
  const Sample* newest = it == slots_.end() ? nullptr : it->second.buffer.Newest();
  if (newest == nullptr) {
    PortValue never_produced;
    never_produced.port = port;
    never_produced.origin = Origin::Unknown;
    never_produced.updated = false;
    return never_produced;
  }
  const Slot& slot = it->second;
  if (slot.last_produced_ns == now_ns) {
    return newest->value;  // fresh this tick, exactly as Publish() left it
  }
  PortValue held = newest->value;
  held.updated = false;
  held.hold_ns = now_ns - slot.last_produced_ns;
  return held;
}

std::vector<PortValue> PortBus::SetFor(const std::vector<PortId>& declared_ports, std::int64_t now_ns) const {
  std::vector<PortValue> result;
  result.reserve(declared_ports.size());
  for (const PortId& port : declared_ports) {
    result.push_back(Get(port, now_ns));
  }
  return result;
}

}  // namespace simcore::bus
