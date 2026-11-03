// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The inspector's shared declarations (`WP-16`, `IMP-0091`..`0100`; `RCT:IMP-0038`, `0039`): attach to a live
///   measurement read-only, read its cycles, dump them, check them. Nothing here names a stage or a port: every
///   name comes from the description the writer put in the measurement (`SYS-0087`).
/// @author Pavan Karimajji

#pragma once

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iosfwd>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "livemeas/livemeas_layout.hpp"
#include "livemeas/meas_cycle.pb.h"
#include "livemeas/meas_description.pb.h"
#include "livemeas/shared_region.hpp"

namespace google::protobuf {
class DescriptorPool;
}

namespace vantage::inspector {

/// `IMP-0091`: the exit codes (the `SimExitCode` values for ok, config and infra).
enum InspectExit : int {
  kInspectOk = 0,            ///< nothing found
  kInspectFound = 1,         ///< `check` found something
  kInspectUsage = 2,         ///< a usage error
  kInspectCannotAttach = 6,  ///< no such name, a layout mismatch, a region too small
};

// ---- attach (`IMP-0092`, `RCT:IMP-0038`) ----------------------------------------------------------------

/// Both segments, mapped read-only. Every size used below comes from the status geometry.
struct Attached {
  std::unique_ptr<livemeas::SharedRegion> data;
  std::unique_ptr<livemeas::SharedRegion> bulk;

  const adas::livemeas::MeasStatus& status() const {
    return *static_cast<const adas::livemeas::MeasStatus*>(data->data());
  }
  const std::uint8_t* description() const {
    return static_cast<const std::uint8_t*>(data->data()) + adas::livemeas::descriptionOffset();
  }
  const std::uint8_t* cycleSlot(std::size_t i) const {
    return static_cast<const std::uint8_t*>(data->data()) + adas::livemeas::cycleSlotOffset(status(), i);
  }
};

enum class AttachOutcome { kOk, kNoSuchName, kNotLiveMeasurement, kLayoutMismatch, kStarting, kTooSmall };

struct AttachReport {
  AttachOutcome outcome = AttachOutcome::kNoSuchName;
  std::string cause;  ///< one line naming why, empty on kOk
  std::unique_ptr<Attached> attached;
};

/// Maps `name` and its bulk segment read-only and runs `checkAttach`. A layout mismatch names both versions and
/// reads nothing more; a mapping smaller than the status says it is is `kTooSmall`.
AttachReport attachReadOnly(const std::string& name);

/// The verb `attach`: prints the status, and whether the writer is gone. Returns an `InspectExit`.
int runAttach(const std::string& name, std::ostream& out, std::ostream& err);

// ---- status (`IMP-0092`) ---------------------------------------------------------------------------------

/// Status, run id, heartbeat, outcome and geometry, one "key: value" per line.
std::string formatStatus(const adas::livemeas::MeasStatus& status);

/// True when `status` says running, the writer's process is not alive and the heartbeat did not change across two
/// reads `apart` apart.
bool writerGone(const adas::livemeas::MeasStatus& status,
                std::chrono::milliseconds apart = std::chrono::milliseconds(200));

/// "writer gone at step N".
std::string writerGoneLine(std::uint64_t step);

// ---- read (`IMP-0094`, `IMP-0093`, `RCT:IMP-0039`) -----------------------------------------------------------

struct CycleView {
  std::uint64_t step = 0;
  std::uint64_t simTimeNs = 0;
  adas::livemeas::MeasCycle cycle;
};

/// The reader's own position in the cycle ring, in cycles written.
class FollowCursor {
 public:
  struct Range {
    std::uint64_t first = 0;
    std::uint64_t last = 0;  ///< one past the last
  };
  /// The cycles still to read when `writeSequence` cycles have been written into `slotCount` slots: those the
  /// writer has overwritten unread are added to the skipped count, and the position moves to `last`.
  Range next(std::uint64_t writeSequence, std::uint32_t slotCount);
  void addSkipped(std::uint64_t n) { skipped_ += n; pending_skipped_ += n; }
  /// The steps skipped since the last call (for the "N steps skipped" line).
  std::uint64_t takeSkipped() {
    const std::uint64_t n = pending_skipped_;
    pending_skipped_ = 0;
    return n;
  }
  std::uint64_t totalSkipped() const { return skipped_; }
  /// The highest step handed out so far, so a slot read again after the ring lapped it is not handed out twice.
  std::optional<std::uint64_t> highestStep;

 private:
  std::uint64_t position_ = 0;
  std::uint64_t skipped_ = 0;
  std::uint64_t pending_skipped_ = 0;
};

/// Every complete cycle not yet read, in step order (`tryCopySlot` on each slot, a torn copy read again a small
/// fixed number of times and then counted as skipped).
std::vector<CycleView> readCycles(const Attached& attached, FollowCursor& cursor);

/// Decodes a payload by a message type name through a descriptor set and nothing else (`SYS-0078`).
class DynamicDecoder {
 public:
  explicit DynamicDecoder(const std::string& descriptorSet);
  ~DynamicDecoder();
  DynamicDecoder(const DynamicDecoder&) = delete;
  DynamicDecoder& operator=(const DynamicDecoder&) = delete;

  /// The payload in protobuf text format on one line; a note in angle brackets when the type is unknown or the
  /// bytes do not parse.
  std::string decode(const std::string& protoType, const std::uint8_t* bytes, std::size_t length) const;

  /// `sig_header.measurement_counter` of the payload, by reflection; none when the type has no such field.
  std::optional<std::uint64_t> measurementCounter(const std::string& protoType, const std::uint8_t* bytes,
                                                  std::size_t length) const;

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

struct DumpOptions {
  bool description = false;  ///< print the decoded description and stop
  bool follow = false;       ///< keep reading until the measurement is finished or the writer is gone
};

/// The verb `dump`. Returns an `InspectExit`.
int runDump(const Attached& attached, const DumpOptions& options, std::ostream& out, std::ostream& err);

/// Reads `attached` to its end the way `--follow` does (until `status` is finished or the writer is gone) and
/// returns every cycle read; the writer-gone line, if any, is in `goneLine`.
std::vector<CycleView> readToEnd(const Attached& attached, FollowCursor& cursor, std::string& goneLine);

/// The description the writer put in the measurement; none when it does not parse.
std::optional<adas::livemeas::MeasDescription> readDescription(const Attached& attached);

/// The port name of value `value` per the description, or "port <n>" when the index is outside it.
std::string portName(const adas::livemeas::MeasDescription& description, std::uint32_t port);

// ---- check (`IMP-0095`..`0100`) ---------------------------------------------------------------------------

std::vector<std::string> checkPorts(const adas::livemeas::MeasDescription& description,
                                    const std::vector<CycleView>& cycles);
std::vector<std::string> checkSteps(const std::vector<CycleView>& cycles, std::uint64_t skipped);
std::vector<std::string> checkRuns(const adas::livemeas::MeasDescription& description,
                                   const std::vector<CycleView>& cycles);
std::vector<std::string> checkBadges(const std::vector<CycleView>& cycles);
std::vector<std::string> checkAgainstRecording(const adas::livemeas::MeasDescription& description,
                                               const std::vector<CycleView>& cycles, const std::string& recordingPath);

struct CheckOptions {
  std::string recording;  ///< `--recording`; empty: the recording check is not run
};

/// The verb `check`. Returns an `InspectExit`.
int runCheck(const Attached& attached, const CheckOptions& options, std::ostream& out, std::ostream& err);

}  // namespace vantage::inspector
