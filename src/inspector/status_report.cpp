// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief `formatStatus`, `writerGone` (`WP-16`, `IMP-0092`): the status block as text, and the one test of a dead
///   writer: `status` running, the writer's process not alive, and a heartbeat that did not move across two reads.
/// @author Pavan Karimajji

#include <sstream>
#include <thread>

#include "inspector.hpp"

namespace vantage::inspector {

namespace layout = adas::livemeas;

namespace {

const char* StatusName(std::uint32_t status) {
  switch (status) {
    case 0: return "starting";
    case 1: return "running";
    case 2: return "paused";
    case 3: return "finished";
    default: return "unknown";
  }
}

const char* OutcomeName(std::uint32_t outcome) {
  switch (outcome) {
    case 0: return "none yet";
    case 1: return "pass";
    case 2: return "fail";
    case 3: return "crash";
    case 4: return "timeout";
    default: return "unknown";
  }
}

}  // namespace

std::string formatStatus(const layout::MeasStatus& s) {
  std::ostringstream out;
  out << "status: " << StatusName(s.status.load()) << "\n"
      << "run id: " << std::hex << s.runId << std::dec << "\n"
      << "writer pid: " << s.writerPid << "\n"
      << "heartbeat: " << s.heartbeat.load() << "\n"
      << "outcome: " << OutcomeName(s.outcome.load()) << "\n"
      << "cycles written: " << s.writeSequence.load() << "\n"
      << "cycles dropped: " << s.droppedCycles.load() << "\n"
      << "layout version: " << s.layoutVersion << "\n"
      << "description: " << s.descriptionLength << " of " << s.descriptionCapacity << " bytes\n"
      << "cycle slots: " << s.cycleSlotCount << " x " << s.cycleSlotSize << " bytes\n"
      << "bulk slots: " << s.bulkSlotCount << " x " << s.bulkSlotSize << " bytes\n";
  return out.str();
}

bool writerGone(const layout::MeasStatus& s, std::chrono::milliseconds apart) {
  if (s.status.load(std::memory_order_acquire) != 1U) return false;
  if (livemeas::SharedRegion::isProcessAlive(s.writerPid)) return false;
  const std::uint64_t before = s.heartbeat.load(std::memory_order_acquire);
  std::this_thread::sleep_for(apart);
  return s.heartbeat.load(std::memory_order_acquire) == before;
}

std::string writerGoneLine(std::uint64_t step) { return "writer gone at step " + std::to_string(step); }

}  // namespace vantage::inspector
