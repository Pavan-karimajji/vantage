// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief `readCycles`, `runDump` (`WP-16`, `IMP-0093`, `RCT:IMP-0039`): every cycle of a live measurement copied
///   with `tryCopySlot` (a torn copy is read again), in step order, and one line per port value, the payload decoded
///   through the description's `descriptor_set` (`DynamicDecoder`).
/// @author Pavan Karimajji

#include <google/protobuf/text_format.h>

#include <algorithm>
#include <ostream>
#include <thread>

#include "inspector.hpp"

namespace vantage::inspector {

namespace layout = adas::livemeas;
using adas::livemeas::MeasPortValue;

namespace {

constexpr int kReadAttempts = 8;  // a torn copy is read again this many times, then counted as skipped
constexpr auto kPollInterval = std::chrono::milliseconds(20);

std::string OriginName(MeasPortValue::Origin origin) {
  std::string name = MeasPortValue::Origin_Name(origin);
  const std::string prefix = "ORIGIN_";
  return name.compare(0, prefix.size(), prefix) == 0 ? name.substr(prefix.size()) : name;
}

void PrintCycle(const CycleView& view, const adas::livemeas::MeasDescription& description, const DynamicDecoder& decoder,
                std::ostream& out) {
  std::map<std::uint32_t, std::size_t> run_of_port;  // the position among the port's values in this step
  for (const MeasPortValue& value : view.cycle.values()) {
    out << "step " << view.step << " port " << portName(description, value.port()) << " run "
        << run_of_port[value.port()]++ << " origin " << OriginName(value.origin()) << " age_ns " << value.age_ns()
        << " ";
    if (value.omitted()) {
      out << "omitted";
    } else if (value.has_bulk()) {
      out << "bulk slot " << value.bulk().slot() << " sequence " << value.bulk().sequence();
    } else {
      const std::string& type = value.port() < static_cast<std::uint32_t>(description.ports_size())
                                    ? description.ports(static_cast<int>(value.port())).proto_type()
                                    : std::string();
      out << decoder.decode(type, reinterpret_cast<const std::uint8_t*>(value.payload().data()), value.payload().size());
    }
    out << "\n";
  }
}

}  // namespace

std::optional<layout::MeasDescription> readDescription(const Attached& attached) {
  layout::MeasDescription description;
  const layout::MeasStatus& status = attached.status();
  if (!description.ParseFromArray(attached.description(), static_cast<int>(status.descriptionLength))) return std::nullopt;
  return description;
}

std::string portName(const layout::MeasDescription& description, std::uint32_t port) {
  if (port < static_cast<std::uint32_t>(description.ports_size())) return description.ports(static_cast<int>(port)).name();
  return "port " + std::to_string(port);
}

std::vector<CycleView> readCycles(const Attached& attached, FollowCursor& cursor) {
  const layout::MeasStatus& status = attached.status();
  const std::uint64_t written = status.writeSequence.load(std::memory_order_acquire);
  const FollowCursor::Range range = cursor.next(written, status.cycleSlotCount);
  std::vector<CycleView> views;
  std::vector<std::uint8_t> copy(status.cycleSlotSize);
  for (std::uint64_t ordinal = range.first; ordinal < range.last; ++ordinal) {
    const std::uint8_t* slot = attached.cycleSlot(static_cast<std::size_t>(ordinal % status.cycleSlotCount));
    bool copied = false;
    for (int attempt = 0; attempt < kReadAttempts && !copied; ++attempt) {
      copied = layout::tryCopySlot<layout::CycleSlotHeader>(slot, status.cycleSlotSize, copy.data(), copy.size());
      if (!copied) std::this_thread::yield();
    }
    const auto& header = *reinterpret_cast<const layout::CycleSlotHeader*>(copy.data());
    CycleView view;
    if (!copied) {
      cursor.addSkipped(1);
      continue;
    }
    view.step = header.step;
    view.simTimeNs = header.simTimeNs;
    if (!view.cycle.ParseFromArray(copy.data() + sizeof(layout::CycleSlotHeader), static_cast<int>(header.length))) {
      cursor.addSkipped(1);
      continue;
    }
    views.push_back(std::move(view));
  }
  std::stable_sort(views.begin(), views.end(), [](const CycleView& a, const CycleView& b) { return a.step < b.step; });
  // A slot read after the ring lapped it holds a later cycle, which its own ordinal hands out again.
  std::vector<CycleView> fresh;
  for (CycleView& view : views) {
    if (cursor.highestStep.has_value() && view.step <= *cursor.highestStep) continue;
    cursor.highestStep = view.step;
    fresh.push_back(std::move(view));
  }
  return fresh;
}

std::vector<CycleView> readToEnd(const Attached& attached, FollowCursor& cursor, std::string& goneLine) {
  const layout::MeasStatus& status = attached.status();
  std::vector<CycleView> all;
  const auto take = [&] {
    std::vector<CycleView> more = readCycles(attached, cursor);
    for (CycleView& view : more) all.push_back(std::move(view));
  };
  for (;;) {
    take();
    if (status.status.load(std::memory_order_acquire) == 3U) {
      take();  // what the writer wrote between the read and the status
      return all;
    }
    if (writerGone(status)) {
      take();
      goneLine = writerGoneLine(all.empty() ? status.heartbeat.load() : all.back().step);
      return all;
    }
    std::this_thread::sleep_for(kPollInterval);
  }
}

int runDump(const Attached& attached, const DumpOptions& options, std::ostream& out, std::ostream& err) {
  const std::optional<layout::MeasDescription> description = readDescription(attached);
  if (!description.has_value()) {
    err << "vantage-inspect: the description in the live measurement does not parse\n";
    return kInspectCannotAttach;
  }
  if (options.description) {
    layout::MeasDescription shown = *description;
    const std::size_t set_bytes = shown.descriptor_set().size();
    shown.clear_descriptor_set();
    std::string text;
    google::protobuf::TextFormat::PrintToString(shown, &text);
    out << text << "descriptor_set: " << set_bytes << " bytes\n";
    return kInspectOk;
  }
  const DynamicDecoder decoder(description->descriptor_set());
  const layout::MeasStatus& status = attached.status();
  FollowCursor cursor;
  for (;;) {
    const std::vector<CycleView> cycles = readCycles(attached, cursor);
    if (const std::uint64_t skipped = cursor.takeSkipped(); skipped > 0) out << skipped << " steps skipped\n";
    for (const CycleView& view : cycles) PrintCycle(view, *description, decoder, out);
    if (!options.follow) return kInspectOk;
    out.flush();
    if (status.status.load(std::memory_order_acquire) == 3U) {
      for (const CycleView& view : readCycles(attached, cursor)) PrintCycle(view, *description, decoder, out);
      return kInspectOk;
    }
    if (writerGone(status)) {
      for (const CycleView& view : readCycles(attached, cursor)) PrintCycle(view, *description, decoder, out);
      out << writerGoneLine(cursor.highestStep.value_or(status.heartbeat.load())) << "\n";
      return kInspectOk;
    }
    std::this_thread::sleep_for(kPollInterval);
  }
}

}  // namespace vantage::inspector
