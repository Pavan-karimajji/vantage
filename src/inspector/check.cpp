// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief The five checks and `runCheck` (`WP-16`, `IMP-0095`..`0100`): `check` follows a live measurement to its end,
///   then holds the cycles it read against what the description declares. Every stage and port name comes from the
///   description; this file holds no name of either (`SYS-0087`, `ANL-05`). The only names it spells are the three
///   roles of a stage's ports, which it joins to a stage name from the description.
/// @author Pavan Karimajji

#include <map>
#include <ostream>
#include <set>

#include "inspector.hpp"
#include "simcore/io.hpp"

namespace vantage::inspector {

namespace layout = adas::livemeas;
using adas::livemeas::MeasBadge;
using adas::livemeas::MeasPortValue;
using adas::livemeas::MeasStage;

namespace {

const char* const kControlRole = "control";
const char* const kRefSyncRole = "refSync";
const char* const kCompStateRole = "compState";

std::string Joined(const std::string& stage, const char* role) { return stage + "." + role; }

std::string OriginText(MeasPortValue::Origin origin) { return MeasPortValue::Origin_Name(origin); }

// The index of port `name` in the description, or none.
std::optional<std::uint32_t> PortIndex(const layout::MeasDescription& description, const std::string& name) {
  for (int i = 0; i < description.ports_size(); ++i) {
    if (description.ports(i).name() == name) return static_cast<std::uint32_t>(i);
  }
  return std::nullopt;
}

// The values of one port in one cycle, in run order.
std::vector<const MeasPortValue*> ValuesOf(const CycleView& view, std::uint32_t port) {
  std::vector<const MeasPortValue*> values;
  for (const MeasPortValue& value : view.cycle.values()) {
    if (value.port() == port) values.push_back(&value);
  }
  return values;
}

}  // namespace

// IMP-0095: after a port's first value, every step carries a value or an `omitted` mark for it. A port that never
// has a value (a stage input read through its producer's port) has no first value, so it gives no finding.
std::vector<std::string> checkPorts(const layout::MeasDescription& description, const std::vector<CycleView>& cycles) {
  std::vector<std::string> findings;
  for (int p = 0; p < description.ports_size(); ++p) {
    bool started = false;
    for (const CycleView& view : cycles) {
      bool has_value = false;
      bool has_mark = false;
      for (const MeasPortValue& value : view.cycle.values()) {
        if (value.port() != static_cast<std::uint32_t>(p)) continue;
        (value.omitted() ? has_mark : has_value) = true;
      }
      if (!started) {
        started = has_value;
        continue;
      }
      if (!has_value && !has_mark) {
        findings.push_back("step " + std::to_string(view.step) + ": port " + description.ports(p).name() +
                           " has neither a value nor an omitted mark");
      }
    }
  }
  return findings;
}

// IMP-0096: each step is the previous step plus one; a step lost to lapping is one too.
std::vector<std::string> checkSteps(const std::vector<CycleView>& cycles, std::uint64_t skipped) {
  std::vector<std::string> findings;
  for (std::size_t i = 1; i < cycles.size(); ++i) {
    const std::uint64_t previous = cycles[i - 1].step;
    if (cycles[i].step != previous + 1) {
      findings.push_back("step " + std::to_string(cycles[i].step) + " follows step " + std::to_string(previous) +
                         ", expected step " + std::to_string(previous + 1));
    }
  }
  if (skipped > 0) {
    findings.push_back(std::to_string(skipped) + " steps lost to lapping: the reader did not keep up with the ring");
  }
  return findings;
}

// IMP-0097: a simulated stage's runs in a step are the control values written in it (`age_ns` 0); each run leaves, in that step, one value
// on the stage's control, refSync and compState ports (`age_ns` 0, in run order). A value carried from an earlier
// step counts for no run: it is what a run that published nothing leaves.
std::vector<std::string> checkRuns(const layout::MeasDescription& description, const std::vector<CycleView>& cycles) {
  std::vector<std::string> findings;
  for (const MeasStage& stage : description.stages()) {
    if (stage.mode() != MeasStage::MODE_SIMULATE) continue;
    const std::optional<std::uint32_t> control = PortIndex(description, Joined(stage.name(), kControlRole));
    if (!control.has_value()) continue;  // nothing identifies this stage's runs
    for (const CycleView& view : cycles) {
      std::size_t runs = 0;
      for (const MeasPortValue* value : ValuesOf(view, *control)) runs += (!value->omitted() && value->age_ns() == 0) ? 1 : 0;
      for (const char* role : {kControlRole, kRefSyncRole, kCompStateRole}) {
        const std::string port = Joined(stage.name(), role);
        const std::optional<std::uint32_t> index = PortIndex(description, port);
        if (!index.has_value()) continue;
        std::size_t written = 0;  // values this step wrote
        for (const MeasPortValue* value : ValuesOf(view, *index)) {
          if (!value->omitted() && value->age_ns() == 0) ++written;
        }
        for (std::size_t run = 0; run < runs; ++run) {
          if (run < written) continue;
          findings.push_back("step " + std::to_string(view.step) + ": stage " + stage.name() + " run " +
                             std::to_string(run) + " has no value on port " + port);
        }
      }
    }
  }
  return findings;
}

// IMP-0099: a badge's count never falls.
std::vector<std::string> checkBadges(const std::vector<CycleView>& cycles) {
  std::vector<std::string> findings;
  std::map<std::pair<int, std::string>, std::pair<std::uint64_t, std::uint64_t>> last;  // count, step
  for (const CycleView& view : cycles) {
    for (const MeasBadge& badge : view.cycle.badges()) {
      const auto key = std::make_pair(static_cast<int>(badge.kind()), badge.subject());
      const auto found = last.find(key);
      if (found != last.end() && badge.count() < found->second.first) {
        findings.push_back("badge " + MeasBadge::Kind_Name(badge.kind()) + " of " + badge.subject() +
                           ": count " + std::to_string(badge.count()) + " at step " + std::to_string(view.step) +
                           " is lower than " + std::to_string(found->second.first) + " at step " +
                           std::to_string(found->second.second));
      }
      last[key] = {badge.count(), view.step};
    }
  }
  return findings;
}

// IMP-0098: each value of a port whose origin is not simulated or overridden is the recording's newest message on
// the port's topic at or before the step's simulation time -- the same counter, the same bytes. A recording names
// its topics after its ports (`09a`, C6): the port `S.out` is the topic `/S/out`.
std::vector<std::string> checkAgainstRecording(const layout::MeasDescription& description,
                                               const std::vector<CycleView>& cycles, const std::string& recordingPath) {
  std::vector<std::string> findings;
  simcore::io::CodecRegistry registry;
  if (!simcore::io::codecs::RegisterMcap(registry).ok()) return {"the recording codec could not be registered"};
  const simcore::Result<std::unique_ptr<simcore::io::Reader>> opened = registry.OpenRead(recordingPath);
  if (!opened.ok()) return {"the recording cannot be read: " + opened.error().Format()};
  simcore::io::Reader& reader = *opened.value();
  const simcore::Result<bool> read_open = reader.Open(recordingPath);
  if (!read_open.ok()) return {"the recording cannot be read: " + read_open.error().Format()};
  std::set<std::string> topics;  // canonical spelling: a port `S.out` is the topic `/S/out`
  for (const auto& [topic, info] : reader.Describe()) topics.insert(simcore::io::CanonicalTopic(topic));

  std::set<std::string> wanted;
  for (const CycleView& view : cycles) {
    for (const MeasPortValue& value : view.cycle.values()) {
      if (value.omitted() || value.origin() == MeasPortValue::ORIGIN_SIMULATED ||
          value.origin() == MeasPortValue::ORIGIN_OVERRIDDEN) {
        continue;
      }
      wanted.insert(portName(description, value.port()));
    }
  }
  std::map<std::string, std::vector<std::pair<std::int64_t, std::vector<std::uint8_t>>>> held;  // by port, log time
  for (const std::string& port : wanted) {
    if (topics.count(simcore::io::CanonicalTopic(port)) == 0) {
      std::string held_topics;
      for (const std::string& topic : topics) held_topics += (held_topics.empty() ? "" : ", ") + topic;
      findings.push_back("port " + port + " has no topic in the recording (it holds: " + held_topics + ")");
    }
  }
  simcore::io::ReadBounds bounds;
  bounds.max_messages = 1024;
  for (;;) {
    simcore::io::Batch batch = reader.ReadRange(bounds);
    for (simcore::io::RawMessage& message : batch.messages) {
      const std::string port = simcore::io::PortNameOfTopic(simcore::io::CanonicalTopic(message.topic));
      if (wanted.count(port) != 0) held[port].emplace_back(message.log_time_ns, std::move(message.payload));
    }
    if (batch.exhausted) break;
  }
  const DynamicDecoder decoder(description.descriptor_set());
  for (const CycleView& view : cycles) {
    for (const MeasPortValue& value : view.cycle.values()) {
      if (value.omitted() || value.has_bulk() || value.origin() == MeasPortValue::ORIGIN_SIMULATED ||
          value.origin() == MeasPortValue::ORIGIN_OVERRIDDEN) {
        continue;
      }
      const std::string port = portName(description, value.port());
      const auto it = held.find(port);
      if (it == held.end()) continue;
      const std::vector<std::uint8_t>* newest = nullptr;
      for (const auto& [time_ns, payload] : it->second) {
        if (time_ns <= static_cast<std::int64_t>(view.simTimeNs)) newest = &payload;
      }
      const std::string where = "step " + std::to_string(view.step) + ": port " + port + " (origin " +
                                OriginText(value.origin()) + ")";
      if (newest == nullptr) {
        findings.push_back(where + " has no recorded message at or before its simulation time");
        continue;
      }
      const std::string& live = value.payload();
      const bool same = live.size() == newest->size() &&
                        std::equal(live.begin(), live.end(), reinterpret_cast<const char*>(newest->data()));
      if (same) continue;
      const std::string& type = value.port() < static_cast<std::uint32_t>(description.ports_size())
                                    ? description.ports(static_cast<int>(value.port())).proto_type()
                                    : std::string();
      const auto live_counter =
          decoder.measurementCounter(type, reinterpret_cast<const std::uint8_t*>(live.data()), live.size());
      const auto recorded_counter = decoder.measurementCounter(type, newest->data(), newest->size());
      std::string detail = "payload bytes differ from the recording";
      if (live_counter.has_value() && recorded_counter.has_value() && *live_counter != *recorded_counter) {
        detail += ", and measurement_counter is " + std::to_string(*live_counter) + " against " +
                  std::to_string(*recorded_counter);
      }
      findings.push_back(where + ": " + detail);
    }
  }
  return findings;
}

// IMP-0100: follows to the end, runs the five checks, one line per finding.
int runCheck(const Attached& attached, const CheckOptions& options, std::ostream& out, std::ostream& err) {
  const std::optional<layout::MeasDescription> description = readDescription(attached);
  if (!description.has_value()) {
    err << "vantage-inspect: the description in the live measurement does not parse\n";
    return kInspectCannotAttach;
  }
  FollowCursor cursor;
  std::string gone_line;
  const std::vector<CycleView> cycles = readToEnd(attached, cursor, gone_line);
  if (const std::uint64_t skipped = cursor.takeSkipped(); skipped > 0) out << skipped << " steps skipped\n";
  if (!gone_line.empty()) out << gone_line << "\n";

  std::vector<std::string> findings = checkPorts(*description, cycles);
  for (const std::vector<std::string>& more :
       {checkSteps(cycles, cursor.totalSkipped()), checkRuns(*description, cycles), checkBadges(cycles)}) {
    findings.insert(findings.end(), more.begin(), more.end());
  }
  if (!options.recording.empty()) {
    const std::vector<std::string> more = checkAgainstRecording(*description, cycles, options.recording);
    findings.insert(findings.end(), more.begin(), more.end());
  }
  for (const std::string& finding : findings) out << finding << "\n";
  return findings.empty() ? kInspectOk : kInspectFound;
}

}  // namespace vantage::inspector
