// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `CycleReconstructor` (`WP-08`, `SI-02`) -- the per-port recovery
///   ladder (`SW-0049`/`0050`), forced-floor validation (`SW-0051`),
///   gap/repeat detection (`SW-0053`/`0054`) and measured-rate tracking
///   (`SW-0055`/`0387`).
///
///   **Scope note, this slice (2026-08-21):** takes an already-decoded
///   `PortMessage` -- the reflection-based decode of a `SignalHeader` out
///   of raw wire bytes (`io::RawMessage::payload`, the same technique the
///   `.erg` codec already uses against a manifest's `FileDescriptorSet`,
///   `R-SIM-11`) is a named follow-on, not built here. This class's own
///   ladder/gap/repeat/rate logic is real and tested against real
///   behaviour first, independent of that wiring.
/// @author Pavan Karimajji

#include "simcore/bus.hpp"

#include <algorithm>
#include <cmath>

namespace simcore::bus {

std::string ToString(Rung rung) {
  switch (rung) {
    case Rung::SourceCycleId:
      return "source_cycle_id";
    case Rung::HeaderCounter:
      return "header_counter";
    case Rung::SourceTime:
      return "source_time";
    case Rung::ReceptionTime:
      return "reception_time";
  }
  return "unknown";
}

std::string ToString(Quality quality) {
  switch (quality) {
    case Quality::Exact:
      return "exact";
    case Quality::Derived:
      return "derived";
    case Quality::Approximated:
      return "approximated";
  }
  return "unknown";
}

namespace {

// Whether this message's own data actually carries the field the given
// rung reads -- independent of any other rung's availability. `SW-0051`'s
// "a rung the data cannot support" is exactly this, for whichever rung a
// floor names; the ladder's own natural descent (below) is the same
// predicate applied in strength order.
bool HasFieldForRung(const PortMessage& msg, Rung rung) {
  switch (rung) {
    case Rung::SourceCycleId:
      return msg.source_cycle_id.has_value();
    case Rung::HeaderCounter:
      return msg.counter.has_value();
    case Rung::SourceTime:
      return msg.t_source_ns.has_value();
    case Rung::ReceptionTime:
      return true;  // the recording envelope's own stamp -- always known
  }
  return false;
}

std::int64_t CycleKeyFor(const PortMessage& msg, Rung rung) {
  switch (rung) {
    case Rung::SourceCycleId:
      return static_cast<std::int64_t>(msg.source_cycle_id.value());
    case Rung::HeaderCounter:
      return static_cast<std::int64_t>(msg.counter.value());
    case Rung::SourceTime:
      return msg.t_source_ns.value();
    case Rung::ReceptionTime:
      return msg.t_recv_ns;
  }
  return msg.t_recv_ns;
}

Quality QualityForRung(Rung rung) {
  switch (rung) {
    case Rung::SourceCycleId:
    case Rung::HeaderCounter:
      return Quality::Exact;
    case Rung::SourceTime:
      return Quality::Derived;
    case Rung::ReceptionTime:
      return Quality::Approximated;
  }
  return Quality::Approximated;
}

}  // namespace

CycleReconstructor::CycleReconstructor(std::vector<PortId> expected_ports, std::vector<LadderFloor> floors)
    : expected_ports_(std::move(expected_ports)), floors_(std::move(floors)) {
  for (const auto& port : expected_ports_) {
    state_.emplace(port, PortState{});
  }
}

const LadderFloor* CycleReconstructor::FindFloor(const PortId& port) const {
  for (const auto& floor : floors_) {
    if (floor.port == port) return &floor;
  }
  return nullptr;
}

Result<bool> CycleReconstructor::Ingest(const PortMessage& msg) {
  PortState& state = state_[msg.port];

  // SW-0050: descend the ladder to the strongest rung this message's own
  // data actually supports. SourceTime is skipped (demoted straight to
  // ReceptionTime) when this port's source time regressed -- "evaluated
  // per port, never across ports" (SW-0050's own Accept clause).
  Rung natural = Rung::ReceptionTime;
  if (HasFieldForRung(msg, Rung::SourceCycleId)) {
    natural = Rung::SourceCycleId;
  } else if (HasFieldForRung(msg, Rung::HeaderCounter)) {
    natural = Rung::HeaderCounter;
  } else if (HasFieldForRung(msg, Rung::SourceTime)) {
    const bool monotonic =
        !state.last_t_source_ns.has_value() || msg.t_source_ns.value() >= state.last_t_source_ns.value();
    if (monotonic) {
      natural = Rung::SourceTime;
    } else {
      demotions_.push_back(Demotion{
          msg.port, Rung::SourceTime, Rung::ReceptionTime, state.last_t_source_ns.value(),
          msg.t_source_ns.value()});
      natural = Rung::ReceptionTime;
    }
  }
  if (msg.t_source_ns.has_value()) {
    state.last_t_source_ns = msg.t_source_ns;
  }

  // SW-0051: a configured floor may only ask for a rung this message's
  // own data actually supports -- never claim a higher rung than the
  // data provides, regardless of what the ladder chose naturally.
  Rung final_rung = natural;
  if (const LadderFloor* floor = FindFloor(msg.port); floor != nullptr) {
    if (!HasFieldForRung(msg, floor->floor)) {
      return Result<bool>::Fail(Error{
          Kind::Authoring, "a rung this port's data supports", ToString(floor->floor), msg.port,
          "the natural (best-supported) rung for this message was " + ToString(natural)});
    }
    final_rung = floor->floor;
  }

  state.last_rung = final_rung;
  state.last_quality = QualityForRung(final_rung);

  // SW-0054: freshness key is the counter when present, else source
  // time -- independent of which rung was finally selected (a forced
  // floor changes grouping, never what "unchanged" means).
  if (msg.counter.has_value()) {
    state.is_repeat = state.last_freshness_counter.has_value() && state.last_freshness_counter.value() == msg.counter.value();
    state.last_freshness_counter = msg.counter;
  } else if (msg.t_source_ns.has_value()) {
    state.is_repeat = state.last_freshness_source_ns.has_value() &&
                       state.last_freshness_source_ns.value() == msg.t_source_ns.value();
    state.last_freshness_source_ns = msg.t_source_ns;
  } else {
    state.is_repeat = false;
  }

  // SW-0053: a counter discontinuity, reported once, never synthesised.
  // A decrease is treated as a reset/wrap, not a gap (uint32 wrap is the
  // wire's own concern, R-IFACE-4 -- not reproduced here).
  if (msg.counter.has_value()) {
    if (state.last_counter.has_value()) {
      const std::uint64_t previous = state.last_counter.value();
      const std::uint64_t current = msg.counter.value();
      if (current > previous + 1) {
        gaps_.push_back(Gap{msg.port, previous, current, current - previous - 1});
      }
    }
    state.last_counter = msg.counter;
  }

  // SW-0055/SW-0387: t_source_ns preferred over reception time for rate
  // tracking wherever both exist.
  const std::int64_t rate_now = msg.t_source_ns.has_value() ? msg.t_source_ns.value() : msg.t_recv_ns;
  if (state.last_rate_ns.has_value()) {
    const double delta = static_cast<double>(rate_now - state.last_rate_ns.value());
    state.rate_sum_ns += delta;
    state.rate_sum_sq_ns += delta * delta;
    ++state.rate_samples;
  }
  state.last_rate_ns = rate_now;

  // SW-0052: stamped onto the stored message itself -- ToPortValue reads
  // these back directly, so the value a module receives carries them with
  // no side lookup against this class's own state.
  PortMessage stamped = msg;
  stamped.rung = final_rung;
  stamped.quality = state.last_quality;
  stamped.is_repeat = state.is_repeat;

  const std::int64_t key = CycleKeyFor(msg, final_rung);
  pending_[key].ports[msg.port] = std::move(stamped);

  return Result<bool>::Ok(true);
}

PortValue ToPortValue(const PortMessage& msg) {
  PortValue value;
  value.port = msg.port;
  value.header.t_source_ns = msg.t_source_ns;
  value.header.counter = msg.counter;
  value.header.t_capture_ns = msg.t_capture_ns;
  value.header.is_repeat = msg.is_repeat;
  value.payload = msg.payload;
  value.rung = msg.rung;
  value.quality = msg.quality;
  return value;
}

std::optional<Cycle> CycleReconstructor::TakeCompleteCycle() {
  for (auto it = pending_.begin(); it != pending_.end(); ++it) {
    bool complete = std::all_of(expected_ports_.begin(), expected_ports_.end(), [&](const PortId& port) {
      return it->second.ports.count(port) != 0;
    });
    if (complete) {
      Cycle cycle = std::move(it->second);
      pending_.erase(it);
      return cycle;
    }
  }
  return std::nullopt;
}

Rung CycleReconstructor::RungUsed(const PortId& port) const {
  auto it = state_.find(port);
  return it != state_.end() ? it->second.last_rung : Rung::ReceptionTime;
}

Quality CycleReconstructor::QualityUsed(const PortId& port) const {
  auto it = state_.find(port);
  return it != state_.end() ? it->second.last_quality : Quality::Approximated;
}

const std::vector<Gap>& CycleReconstructor::Gaps() const { return gaps_; }

const std::vector<Demotion>& CycleReconstructor::Demotions() const { return demotions_; }

bool CycleReconstructor::IsRepeat(const PortId& port) const {
  auto it = state_.find(port);
  return it != state_.end() && it->second.is_repeat;
}

RateReport CycleReconstructor::MeasuredRate(const PortId& port, std::int64_t declared_period_ns, double band) const {
  auto it = state_.find(port);
  if (it == state_.end() || it->second.rate_samples == 0) {
    return RateReport{};
  }
  const PortState& state = it->second;
  const double mean = state.rate_sum_ns / static_cast<double>(state.rate_samples);
  const double variance = std::max(0.0, state.rate_sum_sq_ns / static_cast<double>(state.rate_samples) - mean * mean);
  RateReport report;
  report.has_data = true;
  report.mean_period_ns = mean;
  report.jitter_ns = std::sqrt(variance);
  report.mismatch = std::abs(mean - static_cast<double>(declared_period_ns)) >
                     band * static_cast<double>(declared_period_ns);
  return report;
}

}  // namespace simcore::bus
