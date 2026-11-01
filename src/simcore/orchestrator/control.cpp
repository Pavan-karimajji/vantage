// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `ControlWriter::Write` (`RCT:IMP-0032`, `WP-05`): the control message of
///   one run (`VANTAGE_Architecture.md` §3.2). The header comes from what
///   started the run: a recorded control gives its counter and time, a trigger
///   sample its header, a clock tick `k + 1` and the tick's instant. The
///   `cycle_counter` is the stage's own run count from 1, the sticker is OK,
///   and `op_mode` is RESTART on a stage's first run and after a jump,
///   otherwise the recorded `op_mode` of a recorded control, otherwise RUN.
///   It reads no `compState` and no clock (`RCT:SYS-0012`).
/// @author Pavan Karimajji

#include "adas/sig_status.hpp"
#include "common/cycle_control.pb.h"
#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {

ControlHeader ControlWriter::HeaderOf(const Ticket& ticket, const GraphStage& stage,
                                      const google::protobuf::Descriptor* trigger_descriptor) const {
  ControlHeader header;
  switch (ticket.start) {
    case StartKind::kClock: {
      const std::int64_t period = stage.clock_period_ns;
      const std::int64_t k = period > 0 ? (ticket.trigger_time_ns - first_reception_ns_) / period : 0;
      header.measurement_counter = static_cast<std::uint32_t>(k + 1);
      header.source_timestamp_us = static_cast<std::uint64_t>(ticket.trigger_time_ns / 1000);
      return header;
    }
    case StartKind::kControl:
    case StartKind::kInput: {
      const google::protobuf::Descriptor* descriptor =
          ticket.start == StartKind::kControl ? adas::common::CycleControl::descriptor() : trigger_descriptor;
      const bus::SignalHeader read = bus::ReadSignalHeader(ticket.trigger_payload, descriptor);
      if (read.measurement_counter.has_value()) header.measurement_counter = read.measurement_counter.value();
      if (read.source_timestamp_us.has_value()) header.source_timestamp_us = read.source_timestamp_us.value();
      return header;
    }
  }
  return header;
}

std::vector<std::uint8_t> ControlWriter::Write(const Ticket& ticket, const GraphStage& stage,
                                               const google::protobuf::Descriptor* trigger_descriptor) const {
  const ControlHeader header = HeaderOf(ticket, stage, trigger_descriptor);
  adas::common::CycleControl control;
  adas::common::SignalHeader* sig = control.mutable_sig_header();
  sig->set_measurement_counter(header.measurement_counter);
  sig->set_source_timestamp_us(header.source_timestamp_us);
  sig->set_cycle_counter(static_cast<std::uint32_t>(ticket.run_number + 1));
  sig->set_sig_status(adas::common::kSigStatusOk);

  adas::common::CycleControl::OpMode mode = adas::common::CycleControl::RUN;
  if (ticket.restart) {
    mode = adas::common::CycleControl::RESTART;
  } else if (ticket.start == StartKind::kControl) {
    adas::common::CycleControl recorded;
    if (recorded.ParseFromArray(ticket.trigger_payload.data(), static_cast<int>(ticket.trigger_payload.size()))) {
      mode = recorded.op_mode();
    }
  }
  control.set_op_mode(mode);

  std::vector<std::uint8_t> bytes(static_cast<std::size_t>(control.ByteSizeLong()));
  if (!bytes.empty()) control.SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
  return bytes;
}

}  // namespace simcore::orchestrator
