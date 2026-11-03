// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The live measurement writer library (`WP-14`): `liveMeasOpen`, `liveMeasStep`, `liveMeasClose` and
///   `sealAbandoned` against the layout header of `interfaces` alone -- `IMP-0071` (the C API and its
///   codes), `IMP-0072` (the shared region: a held name, a dead writer's name replaced),
///   `IMP-0073` (`MeasCycle` encoding, a repeated port index kept in order, `D30`), `IMP-0074` (close),
///   `IMP-0076` (the seal), and `RCT:IMP-0034`..`0037` (open, step, bulk, oversize).
///
///   A writer killed mid-run is stood in for by a status written with a dead process id. On POSIX a dead
///   writer's name is replaced (the region unlinked and created again); on Windows a named region lives
///   while any handle is open, so the test holds a handle on the dead writer's region and the open reuses
///   it. Which path ran is printed by `DeadWritersNameIsReplaced`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <atomic>
#include <cstddef>
#include <cstring>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "livemeas/livemeas_layout.hpp"
#include "livemeas/meas_cycle.pb.h"
#include "livemeas/shared_region.hpp"
#include "vantage/livemeas_seal.hpp"
#include "vantage/livemeas_writer.h"

namespace {

namespace layout = adas::livemeas;
using vantage::livemeas::SharedRegion;

constexpr std::uint32_t kDeadPid = 0x7FFFFFF0u;

std::string UniqueName(const char* tag) {
  static int counter = 0;
  return std::string("vnt_lmw_") + tag + "_" + std::to_string(SharedRegion::currentProcessId()) + "_" +
         std::to_string(++counter);
}

LiveMeasGeometry Geometry(std::uint32_t cycles = 4, std::uint32_t cycle_size = 512, std::uint32_t bulks = 2,
                          std::uint32_t bulk_size = 128) {
  return LiveMeasGeometry{cycles, cycle_size, bulks, bulk_size};
}

const std::vector<std::uint8_t> kDescription = {'d', 'e', 's', 'c', 'r', 'i', 'p', 't', 'i', 'o', 'n', '!', '?'};

LiveMeasHandle* Open(const std::string& name, const LiveMeasGeometry& g = Geometry()) {
  LiveMeasHandle* handle = nullptr;
  EXPECT_EQ(liveMeasOpen(name.c_str(), &g, kDescription.data(), static_cast<std::uint32_t>(kDescription.size()),
                         &handle),
            kLiveMeasOk);
  return handle;
}

std::unique_ptr<SharedRegion> Attach(const std::string& name, const char* suffix = "") {
  return SharedRegion::open(name + suffix, SharedRegion::Access::kReadOnly);
}

const layout::MeasStatus& StatusOf(const SharedRegion& region) {
  return *static_cast<const layout::MeasStatus*>(region.data());
}

// One cycle slot, copied the way a reader does; false when torn or empty.
bool ReadSlot(const SharedRegion& region, std::size_t index, layout::CycleSlotHeader& header,
              adas::livemeas::MeasCycle& cycle) {
  const layout::MeasStatus& s = StatusOf(region);
  std::vector<std::uint8_t> copy(s.cycleSlotSize);
  const auto* slot = static_cast<const std::uint8_t*>(region.data()) + layout::cycleSlotOffset(s, index);
  if (!layout::tryCopySlot<layout::CycleSlotHeader>(slot, s.cycleSlotSize, copy.data(), copy.size())) return false;
  std::memcpy(&header, copy.data(), sizeof(layout::CycleSlotHeader));
  return cycle.ParseFromArray(copy.data() + sizeof(layout::CycleSlotHeader), static_cast<int>(header.length));
}

LiveMeasValue Value(std::uint32_t port, const std::vector<std::uint8_t>& payload, std::uint32_t origin = 4,
                    std::uint64_t age = 0, int bulk = 0) {
  return LiveMeasValue{port, payload.data(), static_cast<std::uint32_t>(payload.size()), origin, age, bulk};
}

// A live measurement as a killed writer leaves it: running, magic valid, a process id that does not exist.
std::unique_ptr<SharedRegion> DeadWritersRegion(const std::string& name, const LiveMeasGeometry& g,
                                                std::uint32_t status_value = 1) {
  layout::MeasStatus shape{};
  shape.descriptionCapacity = static_cast<std::uint32_t>((kDescription.size() + 7u) & ~7u);
  shape.cycleSlotCount = g.cycle_slot_count;
  shape.cycleSlotSize = g.cycle_slot_size;
  shape.bulkSlotCount = g.bulk_slot_count;
  shape.bulkSlotSize = g.bulk_slot_size;
  std::unique_ptr<SharedRegion> region;
  EXPECT_NE(SharedRegion::createOrReplace(name, layout::dataSegmentSize(shape), nullptr, region),
            SharedRegion::Create::kFailed);
  auto& s = *static_cast<layout::MeasStatus*>(region->data());
  s.layoutVersion = layout::kLayoutVersion;
  s.runId = 7;
  s.writerPid = kDeadPid;
  s.descriptionCapacity = shape.descriptionCapacity;
  s.descriptionLength = static_cast<std::uint32_t>(kDescription.size());
  s.cycleSlotCount = g.cycle_slot_count;
  s.cycleSlotSize = g.cycle_slot_size;
  s.bulkSlotCount = g.bulk_slot_count;
  s.bulkSlotSize = g.bulk_slot_size;
  s.magic = layout::kMagic;
  s.status.store(status_value);
  return region;
}

}  // namespace

// `RCT:IMP-0034`, `IMP-0071`: open writes the status, the description and the geometry as given, then runs.
TEST(LiveMeasWriter, IMP_0071_OpenWritesStatusDescriptionAndGeometry) {
  const std::string name = UniqueName("open");
  LiveMeasHandle* handle = Open(name, Geometry(4, 512, 2, 128));
  ASSERT_NE(handle, nullptr);
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const layout::MeasStatus& s = StatusOf(*data);
  EXPECT_EQ(layout::checkAttach(s), layout::AttachResult::kOk);
  EXPECT_EQ(s.layoutVersion, layout::kLayoutVersion);
  EXPECT_NE(s.runId, 0u);
  EXPECT_EQ(s.writerPid, SharedRegion::currentProcessId());
  EXPECT_EQ(s.status.load(), 1u);  // running
  EXPECT_EQ(s.outcome.load(), 0u);
  EXPECT_EQ(s.cycleSlotCount, 4u);
  EXPECT_EQ(s.cycleSlotSize, 512u);
  EXPECT_EQ(s.bulkSlotCount, 2u);
  EXPECT_EQ(s.bulkSlotSize, 128u);
  EXPECT_EQ(s.descriptionLength, kDescription.size());
  EXPECT_GE(s.descriptionCapacity, s.descriptionLength);
  EXPECT_EQ(0, std::memcmp(static_cast<const std::uint8_t*>(data->data()) + layout::descriptionOffset(),
                           kDescription.data(), kDescription.size()));
  EXPECT_EQ(s.heartbeat.load(), 0u);
  EXPECT_EQ(s.writeSequence.load(), 0u);
  std::unique_ptr<SharedRegion> bulk = Attach(name, layout::kBulkSegmentSuffix);
  ASSERT_NE(bulk, nullptr);
  EXPECT_GE(bulk->size(), layout::bulkSegmentSize(s));  // a Windows view is rounded up to a page
  EXPECT_EQ(liveMeasClose(handle, 1), kLiveMeasOk);
}

// `SYS-0028`'s half the writer owns: a new run id for every open under one name.
TEST(LiveMeasWriter, IMP_0071_ANewRunIdPerOpen) {
  const std::string name = UniqueName("runid");
  LiveMeasHandle* first = Open(name);
  std::unique_ptr<SharedRegion> a = Attach(name);
  ASSERT_NE(a, nullptr);
  const std::uint64_t first_id = StatusOf(*a).runId;
  ASSERT_EQ(liveMeasClose(first, 1), kLiveMeasOk);
  a.reset();
  LiveMeasHandle* second = Open(name);
  std::unique_ptr<SharedRegion> b = Attach(name);
  ASSERT_NE(b, nullptr);
  EXPECT_NE(StatusOf(*b).runId, first_id);
  EXPECT_EQ(liveMeasClose(second, 1), kLiveMeasOk);
}

TEST(LiveMeasWriter, IMP_0072_ANameWhoseWriterLivesIsHeld) {
  const std::string name = UniqueName("held");
  LiveMeasHandle* first = Open(name);
  std::unique_ptr<SharedRegion> a = Attach(name);
  ASSERT_NE(a, nullptr);
  const std::uint64_t run_id = StatusOf(*a).runId;
  LiveMeasHandle* second = nullptr;
  const LiveMeasGeometry g = Geometry();
  EXPECT_EQ(liveMeasOpen(name.c_str(), &g, kDescription.data(), static_cast<std::uint32_t>(kDescription.size()), &second),
            kLiveMeasNameHeld);
  EXPECT_EQ(second, nullptr);
  EXPECT_EQ(StatusOf(*a).runId, run_id);       // the first writer's region is untouched
  EXPECT_EQ(StatusOf(*a).status.load(), 1u);
  EXPECT_EQ(liveMeasClose(first, 1), kLiveMeasOk);
}

TEST(LiveMeasWriter, IMP_0072_DeadWritersNameIsReplaced) {
  const std::string name = UniqueName("dead");
  const LiveMeasGeometry g = Geometry();
  std::unique_ptr<SharedRegion> dead = DeadWritersRegion(name, g);  // held open: a reader still maps it
  ASSERT_NE(dead, nullptr);
  LiveMeasHandle* handle = Open(name, g);
  ASSERT_NE(handle, nullptr);
  std::unique_ptr<SharedRegion> fresh = Attach(name);
  ASSERT_NE(fresh, nullptr);
  EXPECT_EQ(StatusOf(*fresh).writerPid, SharedRegion::currentProcessId());
  EXPECT_NE(StatusOf(*fresh).runId, 7u);
  EXPECT_EQ(StatusOf(*fresh).status.load(), 1u);
#if defined(_WIN32)
  std::cout << "[ path ] Windows: the dead writer's region, held by a handle, was reused\n";
#else
  std::cout << "[ path ] POSIX: the dead writer's name was unlinked and created again\n";
#endif
  EXPECT_EQ(liveMeasClose(handle, 1), kLiveMeasOk);
}

// `RCT:IMP-0035`, `IMP-0073`: values in the order given, a port index repeated is kept twice in order
// (`D30`), origin and age copied, badges after them; one slot per step; heartbeat and write sequence.
TEST(LiveMeasWriter, IMP_0073_StepsDecodeInOrderAndARepeatedPortIsKeptTwice) {
  const std::string name = UniqueName("step");
  LiveMeasHandle* handle = Open(name);
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const std::vector<std::uint8_t> a{1, 2, 3}, b{9}, c{7, 7};
  const LiveMeasValue values[] = {Value(2, a, 4, 0), Value(5, b, 1, 1500), Value(2, c, 4, 0)};  // port 2 twice
  const LiveMeasBadge badges[] = {{1, "B.in", 3}};
  ASSERT_EQ(liveMeasStep(handle, 0, 100'000'000, values, 3, badges, 1), kLiveMeasOk);
  ASSERT_EQ(liveMeasStep(handle, 1, 200'000'000, nullptr, 0, nullptr, 0), kLiveMeasOk);

  layout::CycleSlotHeader header{};
  adas::livemeas::MeasCycle cycle;
  ASSERT_TRUE(ReadSlot(*data, 0, header, cycle));
  EXPECT_EQ(header.step, 0u);
  EXPECT_EQ(header.simTimeNs, 100'000'000u);
  ASSERT_EQ(cycle.values_size(), 3);
  EXPECT_EQ(cycle.values(0).port(), 2u);
  EXPECT_EQ(cycle.values(0).payload(), std::string(a.begin(), a.end()));
  EXPECT_EQ(cycle.values(1).port(), 5u);
  EXPECT_EQ(cycle.values(1).origin(), adas::livemeas::MeasPortValue::ORIGIN_MEASURED);
  EXPECT_EQ(cycle.values(1).age_ns(), 1500u);
  EXPECT_EQ(cycle.values(2).port(), 2u);  // the stage's second run, after its first
  EXPECT_EQ(cycle.values(2).payload(), std::string(c.begin(), c.end()));
  ASSERT_EQ(cycle.badges_size(), 1);
  EXPECT_EQ(cycle.badges(0).subject(), "B.in");
  EXPECT_EQ(cycle.badges(0).count(), 3u);
  ASSERT_TRUE(ReadSlot(*data, 1, header, cycle));
  EXPECT_EQ(header.step, 1u);
  EXPECT_EQ(cycle.values_size(), 0);
  EXPECT_EQ(StatusOf(*data).writeSequence.load(), 2u);
  EXPECT_EQ(StatusOf(*data).heartbeat.load(), 2u);
  EXPECT_EQ(liveMeasClose(handle, 1), kLiveMeasOk);
}

TEST(LiveMeasWriter, IMP_0071_TheRingWrapsOverTheOldestStep) {
  const std::string name = UniqueName("wrap");
  LiveMeasHandle* handle = Open(name, Geometry(2));
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const std::vector<std::uint8_t> p{1};
  const LiveMeasValue value = Value(0, p);
  for (std::uint64_t step = 0; step < 5; ++step) {
    ASSERT_EQ(liveMeasStep(handle, step, static_cast<std::int64_t>(step), &value, 1, nullptr, 0), kLiveMeasOk);
  }
  layout::CycleSlotHeader h0{}, h1{};
  adas::livemeas::MeasCycle c;
  ASSERT_TRUE(ReadSlot(*data, 0, h0, c));
  ASSERT_TRUE(ReadSlot(*data, 1, h1, c));
  EXPECT_EQ(h0.step, 4u);  // slot 0 holds step 4, slot 1 step 3
  EXPECT_EQ(h1.step, 3u);
  EXPECT_EQ(StatusOf(*data).writeSequence.load(), 5u);
  EXPECT_EQ(liveMeasClose(handle, 1), kLiveMeasOk);
}

// `RCT:IMP-0036`: a bulk value goes to `MeasBulk` first and the cycle carries a reference that resolves.
TEST(LiveMeasWriter, IMP_0071_ABulkValueLandsInMeasBulkAndItsReferenceResolves) {
  const std::string name = UniqueName("bulk");
  LiveMeasHandle* handle = Open(name);
  std::unique_ptr<SharedRegion> data = Attach(name);
  std::unique_ptr<SharedRegion> bulk = Attach(name, layout::kBulkSegmentSuffix);
  ASSERT_NE(data, nullptr);
  ASSERT_NE(bulk, nullptr);
  const std::vector<std::uint8_t> frame(64, 0xAB);
  const LiveMeasValue value = Value(3, frame, 1, 0, /*bulk=*/1);
  ASSERT_EQ(liveMeasStep(handle, 0, 0, &value, 1, nullptr, 0), kLiveMeasOk);
  layout::CycleSlotHeader header{};
  adas::livemeas::MeasCycle cycle;
  ASSERT_TRUE(ReadSlot(*data, 0, header, cycle));
  ASSERT_EQ(cycle.values_size(), 1);
  EXPECT_TRUE(cycle.values(0).payload().empty());  // no image bytes inline
  EXPECT_FALSE(cycle.values(0).omitted());
  ASSERT_TRUE(cycle.values(0).has_bulk());
  const layout::MeasStatus& s = StatusOf(*data);
  const std::uint32_t slot = cycle.values(0).bulk().slot();
  ASSERT_LT(slot, s.bulkSlotCount);
  std::vector<std::uint8_t> copy(s.bulkSlotSize);
  const auto* base = static_cast<const std::uint8_t*>(bulk->data()) + layout::bulkSlotOffset(s, slot);
  ASSERT_TRUE(layout::tryCopySlot<layout::BulkSlotHeader>(base, s.bulkSlotSize, copy.data(), copy.size()));
  layout::BulkSlotHeader bulk_header{};
  std::memcpy(&bulk_header, copy.data(), sizeof(bulk_header));
  EXPECT_EQ(bulk_header.sequence.load(), cycle.values(0).bulk().sequence());
  EXPECT_EQ(bulk_header.step, 0u);
  EXPECT_EQ(bulk_header.port, 3u);
  ASSERT_EQ(bulk_header.length, frame.size());
  EXPECT_EQ(0, std::memcmp(copy.data() + sizeof(layout::BulkSlotHeader), frame.data(), frame.size()));
  EXPECT_EQ(liveMeasClose(handle, 1), kLiveMeasOk);
}

// A bulk payload larger than a bulk slot is omitted, never written across slots.
TEST(LiveMeasWriter, IMP_0071_ABulkPayloadLargerThanASlotIsOmitted) {
  const std::string name = UniqueName("bulkbig");
  LiveMeasHandle* handle = Open(name, Geometry(4, 512, 2, 64));
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const std::vector<std::uint8_t> frame(200, 0x11);
  const LiveMeasValue value = Value(1, frame, 1, 0, 1);
  ASSERT_EQ(liveMeasStep(handle, 0, 0, &value, 1, nullptr, 0), kLiveMeasOk);
  layout::CycleSlotHeader header{};
  adas::livemeas::MeasCycle cycle;
  ASSERT_TRUE(ReadSlot(*data, 0, header, cycle));
  ASSERT_EQ(cycle.values_size(), 1);
  EXPECT_TRUE(cycle.values(0).omitted());
  EXPECT_FALSE(cycle.values(0).has_bulk());
  EXPECT_EQ(liveMeasClose(handle, 1), kLiveMeasOk);
}

// `RCT:IMP-0037`: a payload that does not fit the slot is omitted and the step is still written.
TEST(LiveMeasWriter, IMP_0071_AnOversizePayloadIsOmittedAndTheStepIsWritten) {
  const std::string name = UniqueName("over");
  LiveMeasHandle* handle = Open(name, Geometry(4, 128));
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const std::vector<std::uint8_t> small{1, 2, 3}, big(400, 0x55);
  const LiveMeasValue values[] = {Value(0, small), Value(1, big), Value(2, small)};
  ASSERT_EQ(liveMeasStep(handle, 0, 0, values, 3, nullptr, 0), kLiveMeasOk);
  layout::CycleSlotHeader header{};
  adas::livemeas::MeasCycle cycle;
  ASSERT_TRUE(ReadSlot(*data, 0, header, cycle));
  ASSERT_EQ(cycle.values_size(), 3);
  EXPECT_EQ(cycle.values(0).payload().size(), 3u);
  EXPECT_TRUE(cycle.values(1).omitted());
  EXPECT_TRUE(cycle.values(1).payload().empty());
  EXPECT_EQ(cycle.values(2).payload().size(), 3u);  // the next was still tried
  EXPECT_EQ(StatusOf(*data).droppedCycles.load(), 0u);
  EXPECT_EQ(liveMeasClose(handle, 1), kLiveMeasOk);
}

// A step that cannot fit even with every payload omitted is counted, nothing is written, and the
// heartbeat still rises.
TEST(LiveMeasWriter, IMP_0071_AStepThatCannotFitIsCountedInDroppedCycles) {
  const std::string name = UniqueName("drop");
  LiveMeasHandle* handle = Open(name, Geometry(4, 40));  // 8 bytes of room after the slot header
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const std::vector<std::uint8_t> p{1};
  const LiveMeasValue values[] = {Value(5, p, 4, 1000), Value(6, p, 4, 1000), Value(7, p, 4, 1000)};
  ASSERT_EQ(liveMeasStep(handle, 0, 0, values, 3, nullptr, 0), kLiveMeasOk);
  EXPECT_EQ(StatusOf(*data).droppedCycles.load(), 1u);
  EXPECT_EQ(StatusOf(*data).writeSequence.load(), 0u);
  EXPECT_EQ(StatusOf(*data).heartbeat.load(), 1u);
  EXPECT_EQ(liveMeasClose(handle, 1), kLiveMeasOk);
}

// `IMP-0074`: outcome, then status finished; readers already attached keep reading.
TEST(LiveMeasWriter, IMP_0074_CloseSetsOutcomeThenFinishedAndAttachedReadersKeepReading) {
  const std::string name = UniqueName("close");
  LiveMeasHandle* handle = Open(name);
  std::unique_ptr<SharedRegion> data = Attach(name);
  ASSERT_NE(data, nullptr);
  const std::vector<std::uint8_t> p{4};
  const LiveMeasValue value = Value(0, p);
  ASSERT_EQ(liveMeasStep(handle, 0, 0, &value, 1, nullptr, 0), kLiveMeasOk);
  ASSERT_EQ(liveMeasClose(handle, 4), kLiveMeasOk);
  EXPECT_EQ(StatusOf(*data).status.load(), 3u);
  EXPECT_EQ(StatusOf(*data).outcome.load(), 4u);
  layout::CycleSlotHeader header{};
  adas::livemeas::MeasCycle cycle;
  EXPECT_TRUE(ReadSlot(*data, 0, header, cycle));
#if !defined(_WIN32)
  EXPECT_EQ(Attach(name), nullptr);  // the name is removed: no new reader attaches
#endif
}

// `IMP-0076`, `D18 (3)`: on a dead writer the seal changes `outcome` and `status` and not another byte, in
// either segment; the name is removed.
TEST(LiveMeasWriter, IMP_0076_SealOnADeadWriterChangesOnlyOutcomeAndStatus) {
  const std::string name = UniqueName("seal");
  const LiveMeasGeometry g = Geometry();
  std::unique_ptr<SharedRegion> dead = DeadWritersRegion(name, g);
  ASSERT_NE(dead, nullptr);
  // A step or two in the ring, so a changed slot would show.
  std::memset(static_cast<std::uint8_t*>(dead->data()) + sizeof(layout::MeasStatus), 0x5A,
              dead->size() - sizeof(layout::MeasStatus));
  std::unique_ptr<SharedRegion> reader = Attach(name);
  ASSERT_NE(reader, nullptr);
  const std::vector<std::uint8_t> before(static_cast<const std::uint8_t*>(reader->data()),
                                         static_cast<const std::uint8_t*>(reader->data()) + reader->size());
  EXPECT_EQ(vantage::sealAbandoned(name, 3), vantage::SealResult::kSealed);
  const std::vector<std::uint8_t> after(static_cast<const std::uint8_t*>(reader->data()),
                                        static_cast<const std::uint8_t*>(reader->data()) + reader->size());
  ASSERT_EQ(before.size(), after.size());
  std::vector<std::size_t> differing;
  for (std::size_t i = 0; i < before.size(); ++i) {
    if (before[i] != after[i]) differing.push_back(i);
  }
  const std::size_t outcome_at = offsetof(layout::MeasStatus, outcome);
  const std::size_t status_at = offsetof(layout::MeasStatus, status);
  for (std::size_t i : differing) {
    const bool in_outcome = i >= outcome_at && i < outcome_at + sizeof(std::uint32_t);
    const bool in_status = i >= status_at && i < status_at + sizeof(std::uint32_t);
    EXPECT_TRUE(in_outcome || in_status) << "byte " << i << " changed";
  }
  EXPECT_FALSE(differing.empty());
  EXPECT_EQ(StatusOf(*reader).outcome.load(), 3u);
  EXPECT_EQ(StatusOf(*reader).status.load(), 3u);
#if !defined(_WIN32)
  EXPECT_EQ(Attach(name), nullptr);
#endif
}

TEST(LiveMeasWriter, IMP_0076_SealWritesNothingWhenTheWriterLivesOrTheStatusIsFinished) {
  const std::string name = UniqueName("sealno");
  LiveMeasHandle* handle = Open(name);
  std::unique_ptr<SharedRegion> reader = Attach(name);
  ASSERT_NE(reader, nullptr);
  const std::vector<std::uint8_t> before(static_cast<const std::uint8_t*>(reader->data()),
                                         static_cast<const std::uint8_t*>(reader->data()) + reader->size());
  EXPECT_EQ(vantage::sealAbandoned(name, 3), vantage::SealResult::kWriterAlive);
  const std::vector<std::uint8_t> after(static_cast<const std::uint8_t*>(reader->data()),
                                        static_cast<const std::uint8_t*>(reader->data()) + reader->size());
  EXPECT_EQ(before, after);
  EXPECT_EQ(liveMeasClose(handle, 1), kLiveMeasOk);

  const std::string finished_name = UniqueName("sealfin");
  std::unique_ptr<SharedRegion> finished = DeadWritersRegion(finished_name, Geometry(), /*status=*/3);
  ASSERT_NE(finished, nullptr);
  EXPECT_EQ(vantage::sealAbandoned(finished_name, 3), vantage::SealResult::kAlreadyFinished);
  EXPECT_EQ(StatusOf(*finished).outcome.load(), 0u);
  EXPECT_EQ(vantage::sealAbandoned(UniqueName("nothing"), 3), vantage::SealResult::kNoSuchLiveMeasurement);
  EXPECT_EQ(vantage::sealAbandoned(finished_name, 0), vantage::SealResult::kBadArgument);
}

// A bad argument returns its code and never crashes (`IMP-0071`).
TEST(LiveMeasWriter, IMP_0071_ABadArgumentReturnsItsCodeNeverACrash) {
  LiveMeasHandle* handle = nullptr;
  const LiveMeasGeometry good = Geometry();
  const std::string name = UniqueName("bad");
  EXPECT_EQ(liveMeasOpen(nullptr, &good, kDescription.data(), 1, &handle), kLiveMeasBadArgument);
  EXPECT_EQ(liveMeasOpen(name.c_str(), nullptr, kDescription.data(), 1, &handle), kLiveMeasBadArgument);
  EXPECT_EQ(liveMeasOpen(name.c_str(), &good, kDescription.data(), 1, nullptr), kLiveMeasBadArgument);
  EXPECT_EQ(liveMeasOpen(name.c_str(), &good, nullptr, 5, &handle), kLiveMeasBadArgument);
  for (const LiveMeasGeometry bad : {Geometry(0), Geometry(4, 512, 0), Geometry(4, 16), Geometry(4, 512, 2, 8),
                                     Geometry(4, 514), Geometry(4, 512, 2, 130)}) {
    EXPECT_EQ(liveMeasOpen(name.c_str(), &bad, kDescription.data(), 1, &handle), kLiveMeasBadArgument);
    EXPECT_EQ(handle, nullptr);
  }
  EXPECT_EQ(liveMeasStep(nullptr, 0, 0, nullptr, 0, nullptr, 0), kLiveMeasBadArgument);
  EXPECT_EQ(liveMeasClose(nullptr, 1), kLiveMeasBadArgument);
  LiveMeasHandle* open_handle = Open(name);
  ASSERT_NE(open_handle, nullptr);
  EXPECT_EQ(liveMeasStep(open_handle, 0, 0, nullptr, 2, nullptr, 0), kLiveMeasBadArgument);
  EXPECT_EQ(liveMeasClose(open_handle, 0), kLiveMeasBadArgument);  // the handle is still open
  EXPECT_EQ(liveMeasClose(open_handle, 5), kLiveMeasBadArgument);
  EXPECT_EQ(liveMeasClose(open_handle, 1), kLiveMeasOk);
}
