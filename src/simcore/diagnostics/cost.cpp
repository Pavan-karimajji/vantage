// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `CostReport`/`ByteCounter`/`ScopedTimer` (`IMP-0134`/`IMP-0135`/
///   `IMP-0136`, `WP-15`) -- per-run cost, measured, never estimated.
///   `ByteCounter::Observe` is meant to be called at the codec boundary
///   (once per `io::RawMessage` a `Reader::ReadRange` batch actually
///   delivered, with that message's own `payload.size()`) -- never derived
///   from a duration or a message count, which is `SW-0135`'s own
///   distinction ("counted, not estimated").
///
///   `SW-0136` ("timing measurement never influences results") is upheld
///   structurally, not by a runtime check: `ScopedTimer` writes only to a
///   `std::chrono::nanoseconds&` a caller owns, and nothing in `simcore`'s
///   scheduling (`scheduler/*.cpp`) or port-value path (`bus/*.cpp`,
///   `mutate/*.cpp`) includes this header at all -- a grep for
///   `diagnostics.hpp` outside `diagnostics/*.cpp` and the tests that
///   exercise it is `UT-EDG-05`'s own mechanised half.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <sstream>

namespace simcore::diagnostics {

void ByteCounter::Observe(const std::string& topic, std::size_t bytes) noexcept {
  per_topic_[topic] += bytes;
  total_ += bytes;
}

std::uint64_t ByteCounter::ForTopic(const std::string& topic) const noexcept {
  const auto it = per_topic_.find(topic);
  return it == per_topic_.end() ? 0 : it->second;
}

ScopedTimer::ScopedTimer(std::chrono::nanoseconds& accumulate_into) noexcept
    : target_(accumulate_into), start_(std::chrono::steady_clock::now()) {}

ScopedTimer::~ScopedTimer() { target_ += std::chrono::steady_clock::now() - start_; }

std::vector<std::string> CostReport::Reconcile(const CycleTrace* trace) const noexcept {
  std::vector<std::string> findings;

  std::chrono::nanoseconds module_total{0};
  for (const auto& [stage, duration] : time_per_module) module_total += duration;
  if (module_total > wall_time) {
    std::ostringstream msg;
    msg << "sum(time_per_module)=" << module_total.count() << "ns exceeds wall_time=" << wall_time.count()
        << "ns";
    findings.push_back(msg.str());
  }

  std::uint64_t topic_total = 0;
  for (const auto& [topic, bytes] : bytes_read_per_topic) topic_total += bytes;
  if (topic_total != bytes_read_total) {
    std::ostringstream msg;
    msg << "sum(bytes_read_per_topic)=" << topic_total << " != bytes_read_total=" << bytes_read_total;
    findings.push_back(msg.str());
  }

  if (trace != nullptr) {
    for (const auto& [stage, duration] : time_per_module) {
      const std::chrono::nanoseconds traced = trace->TotalDuration(stage);
      if (traced != duration) {
        std::ostringstream msg;
        msg << "time_per_module[" << stage << "]=" << duration.count()
            << "ns disagrees with CycleTrace total=" << traced.count() << "ns";
        findings.push_back(msg.str());
      }
    }
  }

  return findings;
}

}  // namespace simcore::diagnostics
