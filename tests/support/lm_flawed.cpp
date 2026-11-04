// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `lm_flawed` (`WP-18`, `IMP-0115`; fixture `F-FLAWED-LM`): a test writer that makes a live measurement through the
///   three writer calls from a held source live measurement -- its description and every cycle -- with at most one
///   flaw, then waits for a gate file before it closes, so a test can attach `check` to the target first.
///
///     lm_flawed --source <name> --target <name> --gate <file> [--outcome N] [flaw]
///   flaw (none: a faithful copy):
///     --drop-port <step> <port>      the port's value(s) left out of that step
///     --skip-step <step>             that step not written at all
///     --drop-ref-sync <stage>        the stage's refSync value(s) left out of the first step from 3 on in which the
///                                    stage ran (its control was written in it); prints "flaw step=<n>" 
///     --alter-byte <step> <port>     one byte of the port's first value changed in that step
///     --lower-badge                  the count of the last badge seen in two steps lowered below its earlier count
///   Prints "ready" once everything is written, then waits for the gate file and closes with the source's outcome.
/// @author Pavan Karimajji

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <iostream>
#include <map>
#include <string>
#include <thread>
#include <vector>

#include "inspector.hpp"
#include "vantage/livemeas_writer.h"

namespace {

namespace vi = vantage::inspector;
using adas::livemeas::MeasPortValue;

int Usage(const std::string& cause) {
  std::cerr << "lm_flawed: " << cause << "\n"
            << "usage: lm_flawed --source <name> --target <name> --gate <file> [--outcome N] "
               "[--drop-port S P | --skip-step S | --drop-ref-sync S STAGE | --alter-byte S P | --lower-badge]\n";
  return 2;
}

std::uint32_t PortIndexOf(const adas::livemeas::MeasDescription& description, const std::string& name) {
  for (int i = 0; i < description.ports_size(); ++i) {
    if (description.ports(i).name() == name) return static_cast<std::uint32_t>(i);
  }
  return UINT32_MAX;
}

}  // namespace

int main(int argc, char** argv) {
  std::string source, target, gate, flaw, port_arg, stage_arg;
  std::uint64_t step_arg = 0;
  std::uint32_t outcome = 0;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const auto next = [&]() -> std::string { return i + 1 < argc ? argv[++i] : std::string(); };
    if (arg == "--source") source = next();
    else if (arg == "--target") target = next();
    else if (arg == "--gate") gate = next();
    else if (arg == "--outcome") outcome = static_cast<std::uint32_t>(std::stoul(next()));
    else if (arg == "--flaw") continue;
    else if (arg == "--drop-port" || arg == "--alter-byte") { flaw = arg; step_arg = std::stoull(next()); port_arg = next(); }
    else if (arg == "--drop-ref-sync") { flaw = arg; stage_arg = next(); }
    else if (arg == "--skip-step") { flaw = arg; step_arg = std::stoull(next()); }
    else if (arg == "--lower-badge") flaw = arg;
    else return Usage("unknown argument '" + arg + "'");
  }
  if (source.empty() || target.empty() || gate.empty()) return Usage("--source, --target and --gate are required");

  vi::AttachReport report = vi::attachReadOnly(source);
  if (report.outcome != vi::AttachOutcome::kOk) {
    std::cerr << "lm_flawed: " << report.cause << "\n";
    return 6;
  }
  const vi::Attached& attached = *report.attached;
  const auto description = vi::readDescription(attached);
  if (!description.has_value()) return Usage("the source's description does not parse");
  vi::FollowCursor cursor;
  std::string gone;
  std::vector<vi::CycleView> cycles = vi::readToEnd(attached, cursor, gone);
  if (outcome == 0) outcome = attached.status().outcome.load();
  if (outcome < 1 || outcome > 4) outcome = 1;

  // The one flaw, applied to the copy of the cycles.
  const auto find_step = [&](std::uint64_t step) -> vi::CycleView* {
    for (vi::CycleView& view : cycles) {
      if (view.step == step) return &view;
    }
    return nullptr;
  };
  std::uint64_t skipped_step = UINT64_MAX;
  if (flaw == "--skip-step") skipped_step = step_arg;
  if (flaw == "--drop-ref-sync") {
    // The first step from 3 on in which the stage ran: its control is a value of age 0 in that step.
    const std::uint32_t control = PortIndexOf(*description, stage_arg + ".control");
    if (control == UINT32_MAX) return Usage("the description has no port '" + stage_arg + ".control'");
    bool found = false;
    for (const vi::CycleView& view : cycles) {
      if (view.step < 3) continue;
      for (const MeasPortValue& value : view.cycle.values()) {
        if (value.port() == control && value.age_ns() == 0 && !value.omitted()) {
          step_arg = view.step;
          found = true;
          break;
        }
      }
      if (found) break;
    }
    if (!found) return Usage("stage '" + stage_arg + "' never ran from step 3 on");
    std::cout << "flaw step=" << step_arg << "\n" << std::flush;
  }
  if (flaw == "--drop-port" || flaw == "--drop-ref-sync" || flaw == "--alter-byte") {
    vi::CycleView* view = find_step(step_arg);
    if (view == nullptr) return Usage("the source has no step " + std::to_string(step_arg));
    const std::string port = flaw == "--drop-ref-sync" ? stage_arg + ".refSync" : port_arg;
    const std::uint32_t index = PortIndexOf(*description, port);
    if (index == UINT32_MAX) return Usage("the description has no port '" + port + "'");
    adas::livemeas::MeasCycle changed;
    bool done = false;
    for (const MeasPortValue& value : view->cycle.values()) {
      if (value.port() == index && flaw != "--alter-byte") continue;  // left out
      MeasPortValue* copy = changed.add_values();
      *copy = value;
      if (flaw == "--alter-byte" && value.port() == index && !done && !copy->payload().empty()) {
        (*copy->mutable_payload())[copy->payload().size() - 1] ^= 0x01;
        done = true;
      }
    }
    *changed.mutable_badges() = view->cycle.badges();
    if (flaw != "--alter-byte" && changed.values_size() == view->cycle.values_size()) {
      return Usage("step " + std::to_string(step_arg) + " has no value on '" + port + "'");
    }
    if (flaw == "--alter-byte" && !done) return Usage("step " + std::to_string(step_arg) + " has no payload on '" + port + "'");
    view->cycle = changed;
  }
  if (flaw == "--lower-badge") {
    // The last badge that appears in two steps: its later count is put one below its earlier count.
    std::map<std::pair<int, std::string>, std::vector<std::pair<std::size_t, int>>> seen;  // key -> (cycle, badge index)
    for (std::size_t c = 0; c < cycles.size(); ++c) {
      for (int b = 0; b < cycles[c].cycle.badges_size(); ++b) {
        const auto& badge = cycles[c].cycle.badges(b);
        seen[{static_cast<int>(badge.kind()), badge.subject()}].emplace_back(c, b);
      }
    }
    bool lowered = false;
    for (auto& [key, places] : seen) {
      if (places.size() < 2) continue;
      const auto earlier = cycles[places[places.size() - 2].first].cycle.badges(places[places.size() - 2].second).count();
      if (earlier == 0) continue;
      cycles[places.back().first].cycle.mutable_badges(places.back().second)->set_count(earlier - 1);
      lowered = true;
      break;  // one flaw: the first such badge only
    }
    if (!lowered) return Usage("no badge appears in two steps");
  }

  // Write the target through the three calls.
  std::uint32_t max_cycle = 0;
  for (const vi::CycleView& view : cycles) max_cycle = std::max<std::uint32_t>(max_cycle, static_cast<std::uint32_t>(view.cycle.ByteSizeLong()));
  const auto& s = attached.status();
  LiveMeasGeometry geometry{static_cast<std::uint32_t>(cycles.size() + 2),
                            std::max<std::uint32_t>(s.cycleSlotSize, (max_cycle + 32 + 7) & ~7u), s.bulkSlotCount,
                            s.bulkSlotSize};
  const std::string description_bytes(reinterpret_cast<const char*>(attached.description()), s.descriptionLength);
  LiveMeasHandle* handle = nullptr;
  if (liveMeasOpen(target.c_str(), &geometry, reinterpret_cast<const std::uint8_t*>(description_bytes.data()),
                   static_cast<std::uint32_t>(description_bytes.size()), &handle) != kLiveMeasOk) {
    std::cerr << "lm_flawed: cannot open '" << target << "'\n";
    return 6;
  }
  for (const vi::CycleView& view : cycles) {
    if (view.step == skipped_step) continue;
    std::vector<LiveMeasValue> values;
    for (const MeasPortValue& value : view.cycle.values()) {
      values.push_back(LiveMeasValue{value.port(), reinterpret_cast<const std::uint8_t*>(value.payload().data()),
                                     static_cast<std::uint32_t>(value.payload().size()),
                                     static_cast<std::uint32_t>(value.origin()), value.age_ns(), 0});
    }
    std::vector<LiveMeasBadge> badges;
    for (const auto& badge : view.cycle.badges()) {
      badges.push_back(LiveMeasBadge{static_cast<std::uint32_t>(badge.kind()), badge.subject().c_str(), badge.count()});
    }
    liveMeasStep(handle, view.step, static_cast<std::int64_t>(view.simTimeNs), values.data(),
                 static_cast<std::uint32_t>(values.size()), badges.data(), static_cast<std::uint32_t>(badges.size()));
  }
  std::cout << "ready\n" << std::flush;
  while (!std::filesystem::exists(gate)) std::this_thread::sleep_for(std::chrono::milliseconds(5));
  liveMeasClose(handle, outcome);
  return 0;
}
