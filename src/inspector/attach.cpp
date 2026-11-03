// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief `attachReadOnly`, `runAttach` (`WP-16`, `IMP-0092`, `RCT:IMP-0038`): both segments mapped read-only,
///   `checkAttach`, and a precise cause for every way attaching can fail. Sizes come from the status geometry
///   and `dataSegmentSize`/`bulkSegmentSize`, never from the mapping (a Windows mapping is rounded to a page).
/// @author Pavan Karimajji

#include <ostream>

#include "inspector.hpp"

namespace vantage::inspector {

namespace layout = adas::livemeas;
using livemeas::SharedRegion;

AttachReport attachReadOnly(const std::string& name) {
  AttachReport report;
  auto attached = std::make_unique<Attached>();
  attached->data = SharedRegion::open(name, SharedRegion::Access::kReadOnly);
  if (attached->data == nullptr) {
    report.outcome = AttachOutcome::kNoSuchName;
    report.cause = "no live measurement named '" + name + "'";
    return report;
  }
  if (attached->data->size() < sizeof(layout::MeasStatus)) {
    report.outcome = AttachOutcome::kTooSmall;
    report.cause = "'" + name + "' is smaller than a status block";
    return report;
  }
  const layout::MeasStatus& status = attached->status();
  switch (layout::checkAttach(status)) {
    case layout::AttachResult::kNotLiveMeasurement:
      report.outcome = AttachOutcome::kNotLiveMeasurement;
      report.cause = "'" + name + "' is not a live measurement (its magic is wrong)";
      return report;
    case layout::AttachResult::kLayoutMismatch:
      report.outcome = AttachOutcome::kLayoutMismatch;
      report.cause = "layout mismatch: the writer's layout version is " + std::to_string(status.layoutVersion) +
                     ", this inspector reads layout version " + std::to_string(layout::kLayoutVersion);
      return report;
    case layout::AttachResult::kStarting:
      report.outcome = AttachOutcome::kStarting;
      report.cause = "'" + name + "' is still starting (its description is not ready)";
      return report;
    case layout::AttachResult::kOk:
      break;
  }
  if (attached->data->size() < layout::dataSegmentSize(status) ||
      status.descriptionLength > status.descriptionCapacity) {
    report.outcome = AttachOutcome::kTooSmall;
    report.cause = "'" + name + "' is smaller than its status says (" + std::to_string(layout::dataSegmentSize(status)) +
                   " bytes wanted)";
    return report;
  }
  attached->bulk = SharedRegion::open(name + layout::kBulkSegmentSuffix, SharedRegion::Access::kReadOnly);
  if (attached->bulk == nullptr || attached->bulk->size() < layout::bulkSegmentSize(status)) {
    report.outcome = AttachOutcome::kTooSmall;
    report.cause = "the bulk segment of '" + name + "' is missing or smaller than the status says";
    return report;
  }
  report.outcome = AttachOutcome::kOk;
  report.attached = std::move(attached);
  return report;
}

int runAttach(const std::string& name, std::ostream& out, std::ostream& err) {
  AttachReport report = attachReadOnly(name);
  if (report.outcome != AttachOutcome::kOk) {
    err << "vantage-inspect: " << report.cause << "\n";
    return kInspectCannotAttach;
  }
  const layout::MeasStatus& status = report.attached->status();
  out << formatStatus(status);
  if (writerGone(status)) {
    // The step of the newest cycle in the ring; the heartbeat count when no cycle can be read.
    FollowCursor cursor;
    const std::vector<CycleView> cycles = readCycles(*report.attached, cursor);
    out << writerGoneLine(cycles.empty() ? status.heartbeat.load() : cycles.back().step)
        << (cycles.empty() ? " (the last heartbeat count; no cycle could be read)" : "") << "\n";
  }
  return kInspectOk;
}

}  // namespace vantage::inspector
