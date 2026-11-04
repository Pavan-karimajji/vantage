// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `lm_stress` (`WP-18`, `IMP-0116`; fixture `F-STRESS`, the contract's `F-LM-STRESS`): a writer filling a 2-slot
///   `MeasCycle` ring through the library at full speed, and one reader copying in a loop with `tryCopySlot`. What
///   the writer wrote at a step is a function of the step alone (`Expected`), so the writer's log of every step is
///   that function; the reader decodes each cycle it accepts and compares it with it. A torn copy accepted shows up
///   as a mismatch.
///
///     lm_stress [--seconds N] [--name NAME]
///   Prints `accepted=<n> rejected=<n> mismatches=<n> decode_errors=<n> steps=<n>` and exits 0 when at least one
///   cycle was accepted and none mismatched or failed to decode, else 1.
/// @author Pavan Karimajji

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include "livemeas/livemeas_layout.hpp"
#include "livemeas/meas_cycle.pb.h"
#include "livemeas/shared_region.hpp"
#include "vantage/livemeas_writer.h"

namespace {

namespace layout = adas::livemeas;
using vantage::livemeas::SharedRegion;
using Clock = std::chrono::steady_clock;

// What step `step` carries: port 0 a payload of 64..763 bytes whose every byte depends on the step, port 1 the step.
std::vector<std::uint8_t> Wide(std::uint64_t step) {
  std::vector<std::uint8_t> bytes(64 + (step * 37) % 700);
  for (std::size_t i = 0; i < bytes.size(); ++i) bytes[i] = static_cast<std::uint8_t>(step * 131 + i * 7);
  return bytes;
}

std::vector<std::uint8_t> Narrow(std::uint64_t step) {
  std::vector<std::uint8_t> bytes(8);
  for (int i = 0; i < 8; ++i) bytes[static_cast<std::size_t>(i)] = static_cast<std::uint8_t>(step >> (8 * i));
  return bytes;
}

}  // namespace

int main(int argc, char** argv) {
  int seconds = 60;
  std::string name = "vnt_stress_" + std::to_string(SharedRegion::currentProcessId());
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--seconds" && i + 1 < argc) seconds = std::atoi(argv[++i]);
    else if (arg == "--name" && i + 1 < argc) name = argv[++i];
    else {
      std::cerr << "usage: lm_stress [--seconds N] [--name NAME]\n";
      return 2;
    }
  }
  const LiveMeasGeometry geometry{2, 2048, 1, 64};
  LiveMeasHandle* handle = nullptr;
  const std::uint8_t description[8] = {'s', 't', 'r', 'e', 's', 's', '!', '!'};
  if (liveMeasOpen(name.c_str(), &geometry, description, sizeof(description), &handle) != kLiveMeasOk) {
    std::cerr << "lm_stress: cannot open '" << name << "'\n";
    return 1;
  }
  std::unique_ptr<SharedRegion> region = SharedRegion::open(name, SharedRegion::Access::kReadOnly);
  if (region == nullptr) return 1;
  const auto& status = *static_cast<const layout::MeasStatus*>(region->data());

  std::atomic<bool> stop{false};
  std::atomic<std::uint64_t> steps{0};
  std::thread writer([&] {
    std::uint64_t step = 0;
    while (!stop.load(std::memory_order_relaxed)) {
      const std::vector<std::uint8_t> wide = Wide(step);
      const std::vector<std::uint8_t> narrow = Narrow(step);
      const LiveMeasValue values[2] = {
          {0, wide.data(), static_cast<std::uint32_t>(wide.size()), 4, 0, 0},
          {1, narrow.data(), static_cast<std::uint32_t>(narrow.size()), 4, 0, 0}};
      liveMeasStep(handle, step, static_cast<std::int64_t>(step), values, 2, nullptr, 0);
      steps.store(++step, std::memory_order_relaxed);
    }
  });

  std::uint64_t accepted = 0, rejected = 0, mismatches = 0, decode_errors = 0;
  std::vector<std::uint8_t> copy(status.cycleSlotSize);
  const auto until = Clock::now() + std::chrono::seconds(seconds);
  std::uint64_t slot_index = 0;
  while (Clock::now() < until) {
    const auto* base = static_cast<const std::uint8_t*>(region->data());
    const std::uint8_t* slot = base + layout::cycleSlotOffset(status, slot_index++ % status.cycleSlotCount);
    if (!layout::tryCopySlot<layout::CycleSlotHeader>(slot, status.cycleSlotSize, copy.data(), copy.size())) {
      ++rejected;
      continue;
    }
    const auto& header = *reinterpret_cast<const layout::CycleSlotHeader*>(copy.data());
    if (header.sequence.load(std::memory_order_relaxed) == 0) continue;  // never written yet
    ++accepted;
    layout::MeasCycle cycle;
    if (!cycle.ParseFromArray(copy.data() + sizeof(layout::CycleSlotHeader), static_cast<int>(header.length))) {
      ++decode_errors;
      continue;
    }
    const std::vector<std::uint8_t> wide = Wide(header.step);
    const std::vector<std::uint8_t> narrow = Narrow(header.step);
    const bool same = cycle.values_size() == 2 && cycle.values(0).port() == 0 && cycle.values(1).port() == 1 &&
                      cycle.values(0).payload() == std::string(wide.begin(), wide.end()) &&
                      cycle.values(1).payload() == std::string(narrow.begin(), narrow.end()) &&
                      header.simTimeNs == header.step;
    if (!same) ++mismatches;
  }
  stop.store(true);
  writer.join();
  liveMeasClose(handle, 1);
  std::cout << "accepted=" << accepted << " rejected=" << rejected << " mismatches=" << mismatches
            << " decode_errors=" << decode_errors << " steps=" << steps.load() << "\n";
  return accepted > 0 && mismatches == 0 && decode_errors == 0 ? 0 : 1;
}
