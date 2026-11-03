// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `Readiness::Park`, `Retry`, `Expired` (`IMP-0022`, `WP-04`): a parked
///   ticket is retried at each later event until its sample is committed or
///   `readiness_limit_steps` steps have passed (rule 6). A limit of 0 means a
///   run never waits: a ticket whose sample is missing is expired the moment
///   it is parked. Steps are counted, never time.
/// @author Pavan Karimajji

#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {

Readiness::Readiness(std::int64_t limit_steps) : limit_steps_(limit_steps < 0 ? 0 : limit_steps) {}

void Readiness::Park(std::uint64_t ticket_id, std::uint64_t step) { parked_.emplace(ticket_id, step); }

bool Readiness::IsParked(std::uint64_t ticket_id) const { return parked_.count(ticket_id) != 0; }

std::uint64_t Readiness::Waited(std::uint64_t ticket_id, std::uint64_t step) const {
  const auto it = parked_.find(ticket_id);
  if (it == parked_.end() || step < it->second) return 0;
  return step - it->second;
}

bool Readiness::Expired(std::uint64_t ticket_id, std::uint64_t step) const {
  return IsParked(ticket_id) && Waited(ticket_id, step) >= static_cast<std::uint64_t>(limit_steps_);
}

Readiness::Verdict Readiness::Retry(std::uint64_t ticket_id, std::uint64_t step, bool sample_found) {
  if (sample_found) {
    Unpark(ticket_id);
    return Verdict::kReady;
  }
  if (Expired(ticket_id, step)) {
    Unpark(ticket_id);
    return Verdict::kExpired;
  }
  return Verdict::kWaiting;
}

void Readiness::Unpark(std::uint64_t ticket_id) { parked_.erase(ticket_id); }

void Readiness::Clear() { parked_.clear(); }

std::vector<std::uint64_t> Readiness::ParkedIds() const {
  std::vector<std::uint64_t> ids;
  for (const auto& [id, step] : parked_) ids.push_back(id);
  return ids;
}

}  // namespace simcore::orchestrator
