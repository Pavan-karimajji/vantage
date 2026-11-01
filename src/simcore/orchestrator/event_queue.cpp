// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `EventQueue` (`IMP-0016`, `WP-04`): events ordered by (simulation
///   time, rank, stage declaration order, source index, arrival order). A
///   recorded message has rank 0, so every message of an instant enters its
///   buffer before any run of that instant; its messages come in `sources[]`
///   order and then file order. A clock ticks at the whole recording's first
///   reception time plus whole periods -- for a slice too, which only skips
///   the ticks before its start.
/// @author Pavan Karimajji

#include <algorithm>
#include <tuple>

#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {

namespace {

bool Before(const QueuedEvent& a, const QueuedEvent& b) {
  return std::tie(a.time_ns, a.rank, a.stage_order, a.source_index, a.arrival) <
         std::tie(b.time_ns, b.rank, b.stage_order, b.source_index, b.arrival);
}

}  // namespace

void EventQueue::PushRecorded(std::string port, std::int64_t time_ns, std::size_t source_index,
                              std::vector<std::uint8_t> payload, std::optional<std::int64_t> capture_time_ns,
                              bus::Origin origin) {
  QueuedEvent event;
  event.kind = QueuedEvent::Kind::kRecorded;
  event.time_ns = time_ns;
  event.source_index = source_index;
  event.arrival = next_arrival_++;
  event.port = std::move(port);
  event.payload = std::move(payload);
  event.capture_time_ns = capture_time_ns;
  event.origin = origin;
  recorded_.insert(std::upper_bound(recorded_.begin(), recorded_.end(), event, Before), std::move(event));
}

std::int64_t EventQueue::FirstTickAtOrAfter(const Clock& clock, std::int64_t from_ns) {
  if (from_ns <= clock.first_ns) return clock.first_ns;
  const std::int64_t late = from_ns - clock.first_ns;
  return clock.first_ns + ((late + clock.period_ns - 1) / clock.period_ns) * clock.period_ns;
}

void EventQueue::AddClock(std::string stage, int rank, std::size_t stage_order, std::int64_t period_ns,
                          std::int64_t first_ns, std::int64_t from_ns, std::int64_t end_ns) {
  if (period_ns <= 0) return;
  Clock clock;
  clock.stage = std::move(stage);
  clock.rank = rank;
  clock.stage_order = stage_order;
  clock.period_ns = period_ns;
  clock.first_ns = first_ns;
  clock.end_ns = end_ns;
  clock.next_ns = FirstTickAtOrAfter(clock, from_ns);
  clocks_.push_back(std::move(clock));
}

std::optional<std::int64_t> EventQueue::NextTime() const {
  std::optional<std::int64_t> next;
  if (!recorded_.empty()) next = recorded_.front().time_ns;
  for (const Clock& clock : clocks_) {
    if (clock.next_ns > clock.end_ns) continue;
    if (!next.has_value() || clock.next_ns < *next) next = clock.next_ns;
  }
  return next;
}

bool EventQueue::Empty() const { return !NextTime().has_value(); }

std::vector<QueuedEvent> EventQueue::PopInstant() {
  std::vector<QueuedEvent> instant;
  const std::optional<std::int64_t> time = NextTime();
  if (!time.has_value()) return instant;

  auto last = recorded_.begin();
  while (last != recorded_.end() && last->time_ns == *time) ++last;
  instant.insert(instant.end(), std::make_move_iterator(recorded_.begin()), std::make_move_iterator(last));
  recorded_.erase(recorded_.begin(), last);

  for (Clock& clock : clocks_) {
    if (clock.next_ns != *time || clock.next_ns > clock.end_ns) continue;
    QueuedEvent tick;
    tick.kind = QueuedEvent::Kind::kClock;
    tick.time_ns = *time;
    tick.rank = clock.rank;
    tick.stage_order = clock.stage_order;
    tick.arrival = next_arrival_++;
    tick.stage = clock.stage;
    instant.push_back(std::move(tick));
    clock.next_ns += clock.period_ns;
  }
  std::stable_sort(instant.begin(), instant.end(), Before);
  return instant;
}

void EventQueue::Reset(std::int64_t from_ns) {
  recorded_.clear();
  for (Clock& clock : clocks_) clock.next_ns = FirstTickAtOrAfter(clock, from_ns);
}

}  // namespace simcore::orchestrator
