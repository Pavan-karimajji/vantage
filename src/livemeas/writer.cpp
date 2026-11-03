// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The live measurement writer (`RCT:IMP-0034`..`0037`, `IMP-0074`): `liveMeasOpen`,
///   `liveMeasStep`, `liveMeasClose` over `SharedRegion`, with the layout of `interfaces`'
///   `livemeas_layout.hpp` and no layout of its own. No lock, no wait, no reader state; nothing
///   throws out of a call.
/// @author Pavan Karimajji

#include <atomic>
#include <cstring>
#include <memory>
#include <new>
#include <random>
#include <string>
#include <vector>

#include "livemeas/cycle_encoder.hpp"
#include "livemeas/livemeas_layout.hpp"
#include "livemeas/shared_region.hpp"
#include "vantage/livemeas_writer.h"

namespace vantage::livemeas {

namespace layout = adas::livemeas;

/// The writer of one engine run: both regions and the bulk ring's own write count.
class LiveMeasWriter {
 public:
  // `RCT:IMP-0034`
  static LiveMeasResult open(const std::string& name, const LiveMeasGeometry& g, const std::uint8_t* description,
                             std::uint32_t description_length, LiveMeasHandle** out);
  // `RCT:IMP-0035`..`0037`
  LiveMeasResult step(std::uint64_t step, std::int64_t sim_time_ns, const LiveMeasValue* values,
                      std::uint32_t value_count, const LiveMeasBadge* badges, std::uint32_t badge_count);
  // `IMP-0074`
  LiveMeasResult close(std::uint32_t outcome);

 private:
  layout::MeasStatus& status() const { return *static_cast<layout::MeasStatus*>(data_->data()); }
  std::uint8_t* cycleSlot(std::uint64_t index) const {
    return static_cast<std::uint8_t*>(data_->data()) + layout::cycleSlotOffset(status(), index);
  }
  std::uint8_t* bulkSlot(std::uint64_t index) const {
    return static_cast<std::uint8_t*>(bulk_->data()) + layout::bulkSlotOffset(status(), index);
  }
  BulkPlacement writeBulk(std::uint64_t step, const LiveMeasValue& value);

  std::string name_;
  std::unique_ptr<SharedRegion> data_;
  std::unique_ptr<SharedRegion> bulk_;
  std::uint64_t bulk_written_ = 0;  // `MeasBulk` frames written; the next slot is this modulo the count
};

}  // namespace vantage::livemeas

struct LiveMeasHandle {
  vantage::livemeas::LiveMeasWriter writer;
};

namespace vantage::livemeas {

namespace {

constexpr std::uint32_t kMaxOutcome = 4;

std::size_t Align8(std::size_t n) { return (n + 7u) & ~static_cast<std::size_t>(7u); }

// Whether the bytes of an existing region say a live writer holds it.
bool HeldByLiveWriter(const void* base, std::size_t size) {
  if (size < sizeof(layout::MeasStatus)) return false;
  const auto& status = *static_cast<const layout::MeasStatus*>(base);
  if (status.magic != layout::kMagic) return false;
  return SharedRegion::isProcessAlive(status.writerPid);
}

std::uint64_t NewRunId() {
  std::random_device device;
  std::mt19937_64 engine((static_cast<std::uint64_t>(device()) << 32) ^ device());
  std::uint64_t id = 0;
  while (id == 0) id = engine();
  return id;
}

bool GeometryValid(const LiveMeasGeometry& g) {
  if (g.cycle_slot_count == 0 || g.bulk_slot_count == 0) return false;
  if (g.cycle_slot_size % 8 != 0 || g.bulk_slot_size % 8 != 0) return false;
  if (g.cycle_slot_size <= sizeof(layout::CycleSlotHeader)) return false;
  if (g.bulk_slot_size <= sizeof(layout::BulkSlotHeader)) return false;
  return true;
}

}  // namespace

LiveMeasResult LiveMeasWriter::open(const std::string& name, const LiveMeasGeometry& g,
                                    const std::uint8_t* description, std::uint32_t description_length,
                                    LiveMeasHandle** out) {
  if (name.empty() || out == nullptr || !GeometryValid(g)) return kLiveMeasBadArgument;
  if (description == nullptr && description_length != 0) return kLiveMeasBadArgument;

  // The geometry decides both segment sizes, through the layout header's own functions.
  layout::MeasStatus shape{};
  shape.descriptionCapacity = static_cast<std::uint32_t>(Align8(description_length));
  shape.cycleSlotCount = g.cycle_slot_count;
  shape.cycleSlotSize = g.cycle_slot_size;
  shape.bulkSlotCount = g.bulk_slot_count;
  shape.bulkSlotSize = g.bulk_slot_size;

  std::unique_ptr<SharedRegion> data;
  const SharedRegion::Create created =
      SharedRegion::createOrReplace(name, layout::dataSegmentSize(shape), &HeldByLiveWriter, data);
  if (created == SharedRegion::Create::kNameHeld) return kLiveMeasNameHeld;
  if (created == SharedRegion::Create::kFailed) return kLiveMeasOpenFailed;

  const std::string bulk_name = name + layout::kBulkSegmentSuffix;
  std::unique_ptr<SharedRegion> bulk;
  // The bulk region is the writer's own: whatever holds that name is replaced.
  const SharedRegion::Create bulk_created =
      SharedRegion::createOrReplace(bulk_name, layout::bulkSegmentSize(shape), nullptr, bulk);
  if (bulk_created == SharedRegion::Create::kFailed || bulk_created == SharedRegion::Create::kNameHeld) {
    SharedRegion::remove(name);
    return kLiveMeasOpenFailed;
  }

  auto* handle = new (std::nothrow) LiveMeasHandle();
  if (handle == nullptr) {
    SharedRegion::remove(name);
    SharedRegion::remove(bulk_name);
    return kLiveMeasInternalError;
  }
  LiveMeasWriter& w = handle->writer;
  w.name_ = name;
  w.data_ = std::move(data);
  w.bulk_ = std::move(bulk);

  // A reused region (Windows) may hold a dead writer's bytes: both are zero before anything is written.
  std::memset(w.data_->data(), 0, w.data_->size());
  std::memset(w.bulk_->data(), 0, w.bulk_->size());
  layout::MeasStatus& s = w.status();
  s.layoutVersion = layout::kLayoutVersion;
  s.runId = NewRunId();
  s.writerPid = SharedRegion::currentProcessId();
  s.descriptionCapacity = shape.descriptionCapacity;
  s.descriptionLength = description_length;
  s.cycleSlotCount = g.cycle_slot_count;
  s.cycleSlotSize = g.cycle_slot_size;
  s.bulkSlotCount = g.bulk_slot_count;
  s.bulkSlotSize = g.bulk_slot_size;
  s.status.store(0, std::memory_order_relaxed);
  s.outcome.store(0, std::memory_order_relaxed);
  s.heartbeat.store(0, std::memory_order_relaxed);
  s.writeSequence.store(0, std::memory_order_relaxed);
  s.droppedCycles.store(0, std::memory_order_relaxed);
  if (description_length > 0) {
    std::memcpy(static_cast<std::uint8_t*>(w.data_->data()) + layout::descriptionOffset(), description,
                description_length);
  }
  s.magic = layout::kMagic;
  s.status.store(1, std::memory_order_release);  // running
  *out = handle;
  return kLiveMeasOk;
}

BulkPlacement LiveMeasWriter::writeBulk(std::uint64_t step, const LiveMeasValue& value) {
  BulkPlacement placement;
  const layout::MeasStatus& s = status();
  if (value.length > s.bulkSlotSize - sizeof(layout::BulkSlotHeader)) return placement;  // omitted
  const std::uint32_t slot = static_cast<std::uint32_t>(bulk_written_ % s.bulkSlotCount);
  std::uint8_t* base = bulkSlot(slot);
  auto& header = *reinterpret_cast<layout::BulkSlotHeader*>(base);
  layout::beginSlot(header);
  header.step = step;
  header.length = value.length;
  header.port = value.port;
  if (value.length > 0 && value.payload != nullptr) {
    std::memcpy(base + sizeof(layout::BulkSlotHeader), value.payload, value.length);
  }
  layout::endSlot(header);
  ++bulk_written_;
  placement.placed = true;
  placement.slot = slot;
  placement.sequence = header.sequence.load(std::memory_order_relaxed);
  return placement;
}

LiveMeasResult LiveMeasWriter::step(std::uint64_t step, std::int64_t sim_time_ns, const LiveMeasValue* values,
                                    std::uint32_t value_count, const LiveMeasBadge* badges,
                                    std::uint32_t badge_count) {
  layout::MeasStatus& s = status();
  // heartbeat rises on every call, written or not.
  struct Beat {
    layout::MeasStatus& s;
    ~Beat() { s.heartbeat.fetch_add(1, std::memory_order_release); }
  } beat{s};

  std::vector<BulkPlacement> placements(value_count);
  for (std::uint32_t i = 0; i < value_count; ++i) {
    if (values[i].bulk != 0) placements[i] = writeBulk(step, values[i]);
  }
  const std::size_t capacity = s.cycleSlotSize - sizeof(layout::CycleSlotHeader);
  const EncodedCycle encoded = encodeCycle(values, value_count, placements, badges, badge_count, capacity);
  if (!encoded.fits) {
    s.droppedCycles.fetch_add(1, std::memory_order_relaxed);
    return kLiveMeasOk;
  }
  const std::uint64_t index = s.writeSequence.load(std::memory_order_relaxed) % s.cycleSlotCount;
  std::uint8_t* base = cycleSlot(index);
  auto& header = *reinterpret_cast<layout::CycleSlotHeader*>(base);
  layout::beginSlot(header);
  header.step = step;
  header.simTimeNs = static_cast<std::uint64_t>(sim_time_ns);
  header.length = static_cast<std::uint32_t>(encoded.bytes.size());
  std::memcpy(base + sizeof(layout::CycleSlotHeader), encoded.bytes.data(), encoded.bytes.size());
  layout::endSlot(header);
  s.writeSequence.fetch_add(1, std::memory_order_release);
  return kLiveMeasOk;
}

LiveMeasResult LiveMeasWriter::close(std::uint32_t outcome) {
  layout::MeasStatus& s = status();
  s.outcome.store(outcome, std::memory_order_release);
  s.status.store(3, std::memory_order_release);  // finished
  SharedRegion::remove(name_);
  SharedRegion::remove(name_ + layout::kBulkSegmentSuffix);
  return kLiveMeasOk;
}

}  // namespace vantage::livemeas

extern "C" {

LiveMeasResult liveMeasOpen(const char* name, const LiveMeasGeometry* geometry, const uint8_t* description,
                            uint32_t description_length, LiveMeasHandle** out_handle) {
  try {
    if (out_handle != nullptr) *out_handle = nullptr;
    if (name == nullptr || geometry == nullptr) return kLiveMeasBadArgument;
    return vantage::livemeas::LiveMeasWriter::open(name, *geometry, description, description_length, out_handle);
  } catch (...) {
    return kLiveMeasInternalError;
  }
}

LiveMeasResult liveMeasStep(LiveMeasHandle* handle, uint64_t step, int64_t sim_time_ns, const LiveMeasValue* values,
                            uint32_t value_count, const LiveMeasBadge* badges, uint32_t badge_count) {
  try {
    if (handle == nullptr) return kLiveMeasBadArgument;
    if ((values == nullptr && value_count != 0) || (badges == nullptr && badge_count != 0)) return kLiveMeasBadArgument;
    return handle->writer.step(step, sim_time_ns, values, value_count, badges, badge_count);
  } catch (...) {
    return kLiveMeasInternalError;
  }
}

LiveMeasResult liveMeasClose(LiveMeasHandle* handle, uint32_t outcome) {
  try {
    if (handle == nullptr || outcome < 1 || outcome > vantage::livemeas::kMaxOutcome) return kLiveMeasBadArgument;
    const LiveMeasResult result = handle->writer.close(outcome);
    delete handle;
    return result;
  } catch (...) {
    return kLiveMeasInternalError;
  }
}

}  // extern "C"
