// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `lm_reader` (`WP-18`, `IMP-0114`; fixture `F-READER`): a test reader of a live measurement, built on the layout
///   header and `SharedRegion` alone -- it uses no decoder, no description and none of the inspector.
///
///     lm_reader <name> --stall                 attaches, prints "attached", reads nothing until it is killed
///     lm_reader <name> --kill-after N          reads N cycles, prints "read N", then waits to be killed
///     lm_reader <name> --layout-version V      claims layout version V: a measurement of another version is refused
///                                              as a real reader does (exit 6, naming both versions)
///     lm_reader <name> --write-byte            attempts one write into its read-only mapping: the reader faults
///     lm_reader --until-finished <name>        polls for the name every millisecond, maps it, waits until `status` is
///                                              finished, prints "outcome=<n>", exits 0
///   `--timeout-ms N` (default 60000) bounds the wait for the name and, for `--until-finished`, for the end; a reader
///   that did not get what it waited for exits 6.
/// @author Pavan Karimajji

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include "livemeas/livemeas_layout.hpp"
#include "livemeas/shared_region.hpp"

namespace {

namespace layout = adas::livemeas;
using vantage::livemeas::SharedRegion;
using Clock = std::chrono::steady_clock;

constexpr int kExitCannotAttach = 6;

std::unique_ptr<SharedRegion> WaitForName(const std::string& name, std::chrono::milliseconds timeout) {
  const auto until = Clock::now() + timeout;
  for (;;) {
    std::unique_ptr<SharedRegion> region = SharedRegion::open(name, SharedRegion::Access::kReadOnly);
    if (region != nullptr && region->size() >= sizeof(layout::MeasStatus)) {
      const auto& status = *static_cast<const layout::MeasStatus*>(region->data());
      if (status.magic == layout::kMagic) return region;
    }
    if (Clock::now() >= until) return nullptr;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
}

void WaitToBeKilled() {
  for (;;) std::this_thread::sleep_for(std::chrono::milliseconds(50));
}

int Usage(const std::string& cause) {
  std::cerr << "lm_reader: " << cause << "\n"
            << "usage: lm_reader <name> (--stall | --kill-after N | --layout-version V | --write-byte) [--timeout-ms N]\n"
            << "       lm_reader --until-finished <name> [--timeout-ms N]\n";
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  std::string name;
  std::string mode;
  std::uint64_t kill_after = 0;
  std::uint32_t version = 0;
  std::int64_t timeout_ms = 60000;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--stall" || arg == "--write-byte") {
      mode = arg;
    } else if (arg == "--kill-after" && i + 1 < argc) {
      mode = arg;
      kill_after = std::stoull(argv[++i]);
    } else if (arg == "--layout-version" && i + 1 < argc) {
      mode = arg;
      version = static_cast<std::uint32_t>(std::stoul(argv[++i]));
    } else if (arg == "--until-finished" && i + 1 < argc) {
      mode = arg;
      name = argv[++i];
    } else if (arg == "--timeout-ms" && i + 1 < argc) {
      timeout_ms = std::stoll(argv[++i]);
    } else if (name.empty() && arg.rfind("--", 0) != 0) {
      name = arg;
    } else {
      return Usage("unknown argument '" + arg + "'");
    }
  }
  if (name.empty()) return Usage("no live measurement name");
  if (mode.empty()) return Usage("no mode");

  std::unique_ptr<SharedRegion> region = WaitForName(name, std::chrono::milliseconds(timeout_ms));
  if (region == nullptr) {
    std::cerr << "lm_reader: no live measurement named '" << name << "' appeared\n";
    return kExitCannotAttach;
  }
  const auto& status = *static_cast<const layout::MeasStatus*>(region->data());

  if (mode == "--layout-version") {
    if (status.layoutVersion != version) {
      std::cerr << "lm_reader: layout mismatch: the writer's layout version is " << status.layoutVersion
                << ", this reader reads layout version " << version << "\n";
      return kExitCannotAttach;
    }
    std::cout << "attached\n" << std::flush;
    return 0;
  }
  if (mode == "--until-finished") {
    std::cout << "attached\n" << std::flush;
    const auto until = Clock::now() + std::chrono::milliseconds(timeout_ms);
    while (status.status.load(std::memory_order_acquire) != 3U) {
      if (Clock::now() >= until) {
        std::cerr << "lm_reader: '" << name << "' did not finish in time\n";
        return kExitCannotAttach;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::cout << "outcome=" << status.outcome.load(std::memory_order_acquire) << "\n" << std::flush;
    return 0;
  }
  if (mode == "--stall") {
    std::cout << "attached\n" << std::flush;
    WaitToBeKilled();
  }
  if (mode == "--write-byte") {
    std::cout << "writing\n" << std::flush;
    // The mapping is read-only: this store faults, and that is the case.
    *static_cast<volatile std::uint8_t*>(region->data()) = 1;
    std::cout << "write succeeded\n" << std::flush;  // the FAIL side
    return 0;
  }
  // --kill-after N: copy N cycles the way a reader does, then wait to be killed.
  std::vector<std::uint8_t> copy(status.cycleSlotSize);
  std::uint64_t read = 0;
  const auto until = Clock::now() + std::chrono::milliseconds(timeout_ms);
  while (read < kill_after) {
    if (status.writeSequence.load(std::memory_order_acquire) <= read) {
      if (Clock::now() >= until) return kExitCannotAttach;
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    const auto* base = static_cast<const std::uint8_t*>(region->data());
    const std::uint8_t* slot = base + layout::cycleSlotOffset(status, read % status.cycleSlotCount);
    if (layout::tryCopySlot<layout::CycleSlotHeader>(slot, status.cycleSlotSize, copy.data(), copy.size())) ++read;
  }
  std::cout << "read " << read << "\n" << std::flush;
  WaitToBeKilled();
}
