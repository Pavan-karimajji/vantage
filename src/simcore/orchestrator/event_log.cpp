// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `EventLog::Add` (`IMP-0023`, `WP-04`): one line per entry --
///   `event=degrade step=<n> entry=<kind> key=value ...` -- with the entry
///   kind from the closed `EntryKind` list. A record missing a field its
///   kind needs is refused and adds nothing, so a line always carries the
///   fields `ARCH §5` and `§6` name for its kind.
/// @author Pavan Karimajji

#include <string>

#include "simcore/events.hpp"
#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {

const char* ToString(EntryKind kind) {
  switch (kind) {
    case EntryKind::kOutputCounterBreak:
      return "output_counter_break";
    case EntryKind::kFallbackBeyondGap:
      return "fallback_beyond_gap";
    case EntryKind::kCounterGap:
      return "counter_gap";
    case EntryKind::kCounterReset:
      return "counter_reset";
    case EntryKind::kStalledTrigger:
      return "stalled_trigger";
    case EntryKind::kEvictionMiss:
      return "eviction_miss";
    case EntryKind::kFirstDivergence:
      return "first_divergence";
  }
  return "";
}

namespace {

struct LineBuilder {
  const LogEntry& entry;
  std::string line;
  std::string missing;

  void Text(const char* key, const std::string& value) {
    if (value.empty()) {
      if (missing.empty()) missing = key;
      return;
    }
    line += std::string(" ") + key + "=" + value;
  }
  void Number(const char* key, const std::optional<std::int64_t>& value) {
    if (!value.has_value()) {
      if (missing.empty()) missing = key;
      return;
    }
    line += std::string(" ") + key + "=" + std::to_string(*value);
  }
};

}  // namespace

Result<bool> EventLog::Add(const LogEntry& entry) {
  LineBuilder b{entry, "", ""};
  switch (entry.kind) {
    case EntryKind::kOutputCounterBreak:
      b.Text("stage", entry.stage);
      b.Text("port", entry.port);
      b.Number("wanted", entry.wanted);
      b.Number("found", entry.found);
      break;
    case EntryKind::kFallbackBeyondGap:
      b.Text("stage", entry.stage);
      b.Text("port", entry.port);
      b.Number("wanted", entry.wanted);
      b.Number("found", entry.found);
      b.Number("gap", entry.gap);
      break;
    case EntryKind::kCounterGap:
      b.Text("port", entry.port);
      b.Number("from", entry.from);
      b.Number("to", entry.to);
      b.Number("missed", entry.missed);
      break;
    case EntryKind::kCounterReset:
      b.Text("port", entry.port);
      b.Number("from", entry.from);
      b.Number("to", entry.to);
      break;
    case EntryKind::kStalledTrigger:
      b.Text("stage", entry.stage);
      b.Text("port", entry.port);
      b.Number("counter", entry.counter);
      break;
    case EntryKind::kEvictionMiss:
      b.Text("stage", entry.stage);
      b.Text("port", entry.port);
      b.Number("wanted", entry.wanted);
      break;
    case EntryKind::kFirstDivergence:
      b.Text("stage", entry.stage);
      b.Text("port", entry.port);
      break;
  }
  if (!b.missing.empty()) {
    return Result<bool>::Fail(Error{Kind::Contract, std::string("field '") + b.missing + "' set",
                                    "not set", std::string("event log entry ") + ToString(entry.kind), ""});
  }
  lines_.push_back(std::string("event=") + simcore::ToString(Event::kDegrade) +
                   " step=" + std::to_string(entry.step) + " entry=" + ToString(entry.kind) + b.line);
  ++counts_[entry.kind];
  return Result<bool>::Ok(true);
}

std::size_t EventLog::Count(EntryKind kind) const {
  const auto it = counts_.find(kind);
  return it == counts_.end() ? 0 : it->second;
}

}  // namespace simcore::orchestrator
