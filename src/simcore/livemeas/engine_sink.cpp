// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `LiveMeasWriterSink` (`IMP-0081`): see `engine_sink.hpp`. A value whose port the description does not
///   list is not handed on; the writer's result code of a step is not an error of the engine run.
/// @author Pavan Karimajji

#include "engine_sink.hpp"

#include <vector>

namespace simcore::livemeas {

namespace {

std::uint32_t OriginNumber(bus::Origin origin) {
  switch (origin) {
    case bus::Origin::Measured: return adas::livemeas::MeasPortValue::ORIGIN_MEASURED;
    case bus::Origin::Truth: return adas::livemeas::MeasPortValue::ORIGIN_TRUTH;
    case bus::Origin::Mocked: return adas::livemeas::MeasPortValue::ORIGIN_MOCKED;
    case bus::Origin::Simulated: return adas::livemeas::MeasPortValue::ORIGIN_SIMULATED;
    case bus::Origin::Overridden: return adas::livemeas::MeasPortValue::ORIGIN_OVERRIDDEN;
    case bus::Origin::Unknown: break;
  }
  return adas::livemeas::MeasPortValue::ORIGIN_UNKNOWN;
}

std::uint32_t BadgeNumber(runner::BadgeKind kind) {
  adas::livemeas::MeasBadge::Kind parsed = adas::livemeas::MeasBadge::KIND_UNKNOWN;
  adas::livemeas::MeasBadge::Kind_Parse(runner::ToString(kind), &parsed);  // `KIND_FALLBACK` and so on
  return static_cast<std::uint32_t>(parsed);
}

}  // namespace

LiveMeasWriterSink::LiveMeasWriterSink(LiveMeasHandle* handle, const adas::livemeas::MeasDescription& description)
    : handle_(handle) {
  for (int i = 0; i < description.ports_size(); ++i) {
    port_index_.emplace(description.ports(i).name(), static_cast<std::uint32_t>(i));
  }
}

void LiveMeasWriterSink::OnStep(const runner::StepReport& report) {
  if (handle_ == nullptr) {
    if (next_ != nullptr) next_->OnStep(report);
    return;
  }
  std::vector<LiveMeasValue> values;
  values.reserve(report.values.size());
  for (const runner::StepValue& value : report.values) {
    const auto index = port_index_.find(value.port);
    if (index == port_index_.end() || value.payload == nullptr) continue;
    LiveMeasValue out{};
    out.port = index->second;
    out.payload = value.payload->data();
    out.length = static_cast<std::uint32_t>(value.payload->size());
    out.origin = OriginNumber(value.origin);
    out.age_ns = value.age_ns.has_value() ? static_cast<std::uint64_t>(*value.age_ns) : 0;
    out.bulk = value.bulk ? 1 : 0;
    values.push_back(out);
  }
  std::vector<LiveMeasBadge> badges;
  badges.reserve(report.badges.size());
  for (const runner::StepBadge& badge : report.badges) {
    badges.push_back(LiveMeasBadge{BadgeNumber(badge.kind), badge.subject.c_str(), badge.count});
  }
  liveMeasStep(handle_, report.step, report.sim_time_ns, values.data(), static_cast<std::uint32_t>(values.size()),
               badges.data(), static_cast<std::uint32_t>(badges.size()));
  if (next_ != nullptr) next_->OnStep(report);
}

}  // namespace simcore::livemeas
