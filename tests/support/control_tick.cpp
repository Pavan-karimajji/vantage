// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `control_tick` (`WP-11`, `IMP-0055`; fixture `F-TICK` of `SYT-ORC-12`,
///   serves `SYS-0050`): the `measurement_counter` of the control a clock-started
///   stage gets at tick k. argv: [clock_period_ns, tick]. Builds the control with
///   `ControlWriter::Write` (first reception time 0) and prints its
///   `measurement_counter` as a decimal number on one line. No stage runs and no
///   library is loaded. Exit 0 on success, 2 on a bad argument.
/// @author Pavan Karimajji

#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#include "common/cycle_control.pb.h"
#include "simcore/orchestrator.hpp"

namespace {

bool ParseWhole(const char* text, std::int64_t& value) {
  char* end = nullptr;
  const long long parsed = std::strtoll(text, &end, 0);
  if (end == text || *end != '\0' || parsed < 0) return false;
  value = parsed;
  return true;
}

}  // namespace

int main(int argc, char** argv) {
  std::int64_t period_ns = 0;
  std::int64_t tick = 0;
  if (argc != 3 || !ParseWhole(argv[1], period_ns) || !ParseWhole(argv[2], tick) || period_ns <= 0) {
    std::cerr << "usage: control_tick <clock_period_ns> <tick>\n";
    return 2;
  }

  simcore::orchestrator::GraphStage stage;
  stage.name = "A";
  stage.start = simcore::orchestrator::StartKind::kClock;
  stage.clock_period_ns = period_ns;
  simcore::orchestrator::Ticket ticket;
  ticket.stage = "A";
  ticket.start = simcore::orchestrator::StartKind::kClock;
  ticket.trigger_time_ns = tick * period_ns;

  const simcore::orchestrator::ControlWriter writer(/*first_reception_ns=*/0);
  const std::vector<std::uint8_t> bytes = writer.Write(ticket, stage, nullptr);
  adas::common::CycleControl control;
  if (!control.ParseFromArray(bytes.data(), static_cast<int>(bytes.size()))) {
    std::cerr << "control_tick: the control did not parse\n";
    return 1;
  }
  std::cout << control.sig_header().measurement_counter() << "\n";
  return 0;
}
