// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `LiveMeasWriterSink` (`IMP-0081`): the engine's `LiveMeasSink` that hands each `StepReport` to the
///   writer's `liveMeasStep` and then, when one is set, to a second sink -- the step tap, `F-TAP` -- so
///   the tap and the writer get one report (`SYS-0072`).
/// @author Pavan Karimajji

#pragma once

#include <map>
#include <string>

#include "livemeas/meas_cycle.pb.h"
#include "livemeas/meas_description.pb.h"
#include "simcore/runner.hpp"
#include "vantage/livemeas_writer.h"

namespace simcore::livemeas {

class LiveMeasWriterSink final : public runner::LiveMeasSink {
 public:
  /// `handle` is the writer's; the port index of a value is its place in `description.ports`.
  LiveMeasWriterSink(LiveMeasHandle* handle, const adas::livemeas::MeasDescription& description);

  /// The sink that gets the same report after the writer; null for none.
  void SetNext(runner::LiveMeasSink* next) { next_ = next; }

  /// Called when the writer's handle is closed: the writer is not called again, the second sink still is.
  void Detach() { handle_ = nullptr; }

  void OnStep(const runner::StepReport& report) override;

 private:
  LiveMeasHandle* handle_;
  std::map<std::string, std::uint32_t> port_index_;
  runner::LiveMeasSink* next_ = nullptr;
};

}  // namespace simcore::livemeas
