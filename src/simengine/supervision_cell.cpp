// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `SupervisionCell` (`WP-17`, `IMP-0109`): the implementation of the class the header describes.
/// @author Pavan Karimajji

#include "supervision_cell.hpp"

#include <atomic>
#include <cstring>

#include "livemeas/shared_region.hpp"
#include "simcore/abi/simcore.h"

namespace vantage::simengine {

using livemeas::SharedRegion;

SupervisionCell::SupervisionCell() = default;
SupervisionCell::~SupervisionCell() = default;

std::string SupervisionCell::nameFor(std::uint32_t supervisorPid, int attempt) {
  return "vantage_supervision_" + std::to_string(supervisorPid) + "_" + std::to_string(attempt);
}

std::unique_ptr<SupervisionCell> SupervisionCell::create(const std::string& name, std::size_t stageCount) {
  std::unique_ptr<SharedRegion> region;
  const std::size_t size = SIMCORE_SUPERVISION_CELL_HEADER_BYTES + stageCount;
  const SharedRegion::Create created = SharedRegion::createOrReplace(name, size, nullptr, region);
  if (created == SharedRegion::Create::kFailed || created == SharedRegion::Create::kNameHeld) return nullptr;
  std::memset(region->data(), 0, region->size());
  auto* header = static_cast<SimSupervisionCellHeader*>(region->data());
  header->stageCount = stageCount;
  header->magic = SIMCORE_SUPERVISION_CELL_MAGIC;
  std::unique_ptr<SupervisionCell> cell(new SupervisionCell());
  cell->region_ = std::move(region);
  cell->name_ = name;
  return cell;
}

std::unique_ptr<SupervisionCell> SupervisionCell::open(const std::string& name) {
  std::unique_ptr<SharedRegion> region = SharedRegion::open(name, SharedRegion::Access::kReadWrite);
  if (region == nullptr || region->size() < SIMCORE_SUPERVISION_CELL_HEADER_BYTES) return nullptr;
  const auto* header = static_cast<const SimSupervisionCellHeader*>(region->data());
  if (header->magic != SIMCORE_SUPERVISION_CELL_MAGIC) return nullptr;
  if (region->size() < SIMCORE_SUPERVISION_CELL_HEADER_BYTES + header->stageCount) return nullptr;
  std::unique_ptr<SupervisionCell> cell(new SupervisionCell());
  cell->region_ = std::move(region);
  cell->name_ = name;
  return cell;
}

void* SupervisionCell::base() const { return region_->data(); }
std::uint64_t SupervisionCell::length() const { return region_->size(); }

std::vector<std::string> SupervisionCell::stagesInCall(const std::vector<std::string>& stageNames) const {
  std::vector<std::string> in_call;
  const auto* header = static_cast<const SimSupervisionCellHeader*>(region_->data());
  const auto* bytes = static_cast<const std::uint8_t*>(region_->data()) + SIMCORE_SUPERVISION_CELL_HEADER_BYTES;
  for (std::size_t i = 0; i < stageNames.size() && i < header->stageCount; ++i) {
    if (reinterpret_cast<const std::atomic<std::uint8_t>*>(bytes + i)->load(std::memory_order_acquire) != 0) {
      in_call.push_back(stageNames[i]);
    }
  }
  return in_call;
}

std::optional<std::uint64_t> SupervisionCell::lastCompletedStep() const {
  const auto* header = static_cast<const SimSupervisionCellHeader*>(region_->data());
  const auto* has = reinterpret_cast<const std::atomic<std::uint64_t>*>(&header->hasStep);
  if (has->load(std::memory_order_acquire) == 0) return std::nullopt;
  return reinterpret_cast<const std::atomic<std::uint64_t>*>(&header->lastCompletedStep)->load(std::memory_order_acquire);
}

void SupervisionCell::remove() { SharedRegion::remove(name_); }

}  // namespace vantage::simengine
