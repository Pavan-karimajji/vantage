// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SupervisionCell` (`WP-17`, `IMP-0109`; `D31 (3)`): the shared memory a supervisor and its worker
///   share instead of a file written per component call. The layout is declared once, in
///   `simcore/abi/simcore.h`; this class only creates, opens and reads it, on `livemeas`'s `SharedRegion`.
///   The supervisor creates it (`create`), the worker opens it by name (`open`) and hands the mapping to
///   the engine (`simEngineSetSupervisionCell`); after the worker's end the supervisor reads
///   `stagesInCall` and `lastCompletedStep`, then removes it.
/// @author Pavan Karimajji

#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace vantage::livemeas {
class SharedRegion;
}

namespace vantage::simengine {

class SupervisionCell {
 public:
  ~SupervisionCell();

  /// The name of the supervisor `supervisorPid`'s cell for attempt `attempt`.
  static std::string nameFor(std::uint32_t supervisorPid, int attempt);

  /// Creates the cell zeroed, with the magic and `stageCount` set. Null when it cannot be created.
  static std::unique_ptr<SupervisionCell> create(const std::string& name, std::size_t stageCount);

  /// Opens an existing cell read-write. Null when there is none or it is not a cell.
  static std::unique_ptr<SupervisionCell> open(const std::string& name);

  /// The mapping, for `simEngineSetSupervisionCell`.
  void* base() const;
  std::uint64_t length() const;

  /// The names, among `stageNames` (run-setup order), whose byte is 1. Empty when none is in a call.
  std::vector<std::string> stagesInCall(const std::vector<std::string>& stageNames) const;

  /// The last completed step, or none when no step completed.
  std::optional<std::uint64_t> lastCompletedStep() const;

  /// Removes the cell's name so no new process maps it.
  void remove();

 private:
  SupervisionCell();
  std::unique_ptr<livemeas::SharedRegion> region_;
  std::string name_;
};

}  // namespace vantage::simengine
