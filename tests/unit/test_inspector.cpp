// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The inspector `vantage-inspect` (`WP-16`): `IMP-0092` (`formatStatus`, `writerGone`), `RCT:IMP-0038`
///   (`attachReadOnly`), `IMP-0093` and `IMP-0094` (`runDump`, `FollowCursor`, the ring read), `RCT:IMP-0039`
///   (`DynamicDecoder`), `IMP-0095`..`IMP-0100` (the five checks and `runCheck`) and `IMP-0091`, `IMP-0101` (the
///   executable's verbs and exit codes). Live measurements are built in-process with the writer's C API; a writer
///   that was killed is stood in for by a status written with a dead process id.
/// @author Pavan Karimajji

#include <google/protobuf/descriptor.pb.h>
#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <new>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "inspector.hpp"
#include "simcore/io.hpp"
#include "simcore/module_host.hpp"
#include "vantage/livemeas_writer.h"

namespace {

namespace layout = adas::livemeas;
namespace vi = vantage::inspector;
using adas::livemeas::MeasPortValue;
using adas::livemeas::MeasStage;
using vantage::livemeas::SharedRegion;

constexpr std::uint32_t kDeadPid = 0x7FFFFFF0u;
const std::vector<std::uint8_t> kSeven = {0x08, 0x07};  // t.Echo { counter: 7 }

std::string UniqueName(const char* tag) {
  static int counter = 0;
  return std::string("vnt_ins_") + tag + "_" + std::to_string(SharedRegion::currentProcessId()) + "_" +
         std::to_string(++counter);
}

// A descriptor set of three message types: t.Echo { counter }, t.Sig { measurement_counter }, t.Hdr { sig_header }.
std::string EchoDescriptorSet() {
  using google::protobuf::FieldDescriptorProto;
  google::protobuf::FileDescriptorSet set;
  auto* file = set.add_file();
  file->set_name("t.proto");
  file->set_package("t");
  file->set_syntax("proto3");
  const auto add_field = [](google::protobuf::DescriptorProto* message, const char* name, int number,
                            FieldDescriptorProto::Type type, const char* type_name = nullptr) {
    auto* field = message->add_field();
    field->set_name(name);
    field->set_number(number);
    field->set_type(type);
    field->set_label(FieldDescriptorProto::LABEL_OPTIONAL);
    if (type_name != nullptr) field->set_type_name(type_name);
  };
  add_field(file->add_message_type(), "counter", 1, FieldDescriptorProto::TYPE_UINT32);
  file->mutable_message_type(0)->set_name("Echo");
  auto* sig = file->add_message_type();
  sig->set_name("Sig");
  add_field(sig, "measurement_counter", 2, FieldDescriptorProto::TYPE_UINT32);
  auto* header = file->add_message_type();
  header->set_name("Hdr");
  add_field(header, "sig_header", 1, FieldDescriptorProto::TYPE_MESSAGE, ".t.Sig");
  return set.SerializeAsString();
}

using PortList = std::vector<std::pair<std::string, std::string>>;
using StageList = std::vector<std::pair<std::string, MeasStage::Mode>>;

layout::MeasDescription Describe(const PortList& ports, const StageList& stages = {}) {
  layout::MeasDescription description;
  description.set_recording("rec.mcap");
  description.set_descriptor_set(EchoDescriptorSet());
  for (const auto& [name, type] : ports) {
    auto* port = description.add_ports();
    port->set_name(name);
    port->set_proto_type(type);
  }
  for (const auto& [name, mode] : stages) {
    auto* stage = description.add_stages();
    stage->set_name(name);
    stage->set_mode(mode);
  }
  return description;
}

struct V {
  std::uint32_t port;
  std::vector<std::uint8_t> payload;
  std::uint32_t origin = MeasPortValue::ORIGIN_SIMULATED;
  std::uint64_t age_ns = 0;
  int bulk = 0;
};

// A live measurement written in this process.
class Live {
 public:
  Live(const char* tag, const layout::MeasDescription& description, std::uint32_t cycle_slots = 8,
       std::uint32_t cycle_size = 1024)
      : name_(UniqueName(tag)) {
    const std::string bytes = description.SerializeAsString();
    const LiveMeasGeometry geometry{cycle_slots, cycle_size, 2, 256};
    EXPECT_EQ(liveMeasOpen(name_.c_str(), &geometry, reinterpret_cast<const std::uint8_t*>(bytes.data()),
                           static_cast<std::uint32_t>(bytes.size()), &handle_),
              kLiveMeasOk);
  }
  ~Live() {
    if (handle_ != nullptr) liveMeasClose(handle_, 1);
  }
  const std::string& name() const { return name_; }
  void Step(std::uint64_t step, std::int64_t time_ns, const std::vector<V>& values,
            const std::vector<std::pair<std::uint32_t, std::pair<std::string, std::uint64_t>>>& badges = {}) {
    std::vector<LiveMeasValue> raw;
    for (const V& v : values) {
      raw.push_back(LiveMeasValue{v.port, v.payload.data(), static_cast<std::uint32_t>(v.payload.size()), v.origin,
                                  v.age_ns, v.bulk});
    }
    std::vector<LiveMeasBadge> raw_badges;
    for (const auto& b : badges) raw_badges.push_back(LiveMeasBadge{b.first, b.second.first.c_str(), b.second.second});
    ASSERT_EQ(liveMeasStep(handle_, step, time_ns, raw.data(), static_cast<std::uint32_t>(raw.size()),
                           raw_badges.data(), static_cast<std::uint32_t>(raw_badges.size())),
              kLiveMeasOk);
  }
  void Close(std::uint32_t outcome) {
    ASSERT_EQ(liveMeasClose(handle_, outcome), kLiveMeasOk);
    handle_ = nullptr;
  }

 private:
  std::string name_;
  LiveMeasHandle* handle_ = nullptr;
};

std::unique_ptr<vi::Attached> Attach(const std::string& name) {
  vi::AttachReport report = vi::attachReadOnly(name);
  EXPECT_EQ(report.outcome, vi::AttachOutcome::kOk) << report.cause;
  return std::move(report.attached);
}

// A region as a killed writer leaves it (or a writer of another layout): magic valid, the given pid and layout.
std::unique_ptr<SharedRegion> FakeRegion(const std::string& name, std::uint32_t layout_version, std::uint32_t pid,
                                         std::uint32_t status_value, std::uint64_t heartbeat = 5) {
  layout::MeasStatus shape{};
  shape.descriptionCapacity = 8;
  shape.cycleSlotCount = 2;
  shape.cycleSlotSize = 256;
  shape.bulkSlotCount = 1;
  shape.bulkSlotSize = 64;
  std::unique_ptr<SharedRegion> region;
  EXPECT_NE(SharedRegion::createOrReplace(name, layout::dataSegmentSize(shape), nullptr, region),
            SharedRegion::Create::kFailed);
  auto& s = *static_cast<layout::MeasStatus*>(region->data());
  s.layoutVersion = layout_version;
  s.runId = 9;
  s.writerPid = pid;
  s.descriptionCapacity = shape.descriptionCapacity;
  s.cycleSlotCount = shape.cycleSlotCount;
  s.cycleSlotSize = shape.cycleSlotSize;
  s.bulkSlotCount = shape.bulkSlotCount;
  s.bulkSlotSize = shape.bulkSlotSize;
  s.heartbeat.store(heartbeat);
  s.magic = layout::kMagic;
  s.status.store(status_value);
  return region;
}

vi::CycleView Cycle(std::uint64_t step, const std::vector<V>& values, std::uint64_t time_ns = 0) {
  vi::CycleView view;
  view.step = step;
  view.simTimeNs = time_ns;
  for (const V& v : values) {
    MeasPortValue* value = view.cycle.add_values();
    value->set_port(v.port);
    value->set_payload(std::string(v.payload.begin(), v.payload.end()));
    value->set_origin(static_cast<MeasPortValue::Origin>(v.origin));
    value->set_age_ns(v.age_ns);
  }
  return view;
}

void MarkOmitted(vi::CycleView& view, std::size_t index) { view.cycle.mutable_values(static_cast<int>(index))->set_omitted(true); }

std::filesystem::path TempPath(const std::string& name) { return std::filesystem::temp_directory_path() / name; }

std::string ReadAll(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  std::ostringstream text;
  text << in.rdbuf();
  return text.str();
}

struct Ran {
  int exit_code = -1;
  std::string error_text;
};

Ran RunInspect(const std::vector<std::string>& args) {
  const std::filesystem::path capture = TempPath(UniqueName("stderr") + ".txt");
  const auto result = simcore::module_host::RunIsolatedStage("inspect", std::filesystem::path(VANTAGE_INSPECT_EXECUTABLE),
                                                             args, std::chrono::seconds(20), capture);
  Ran ran;
  ran.exit_code = result.outcome == simcore::module_host::IsolatedOutcome::kOk ? 0 : result.exit_code;
  ran.error_text = ReadAll(capture);
  return ran;
}

const PortList kEchoPorts = {{"S.control", "t.Echo"}, {"S.refSync", "t.Echo"}, {"S.compState", "t.Echo"}};

}  // namespace

// ---- IMP-0092 -------------------------------------------------------------------------------------------------

TEST(Inspector, IMP_0092_FormatStatusPrintsStatusRunIdHeartbeatOutcomeAndGeometry) {
  Live live("fmt", Describe(kEchoPorts), 4, 512);
  live.Step(0, 0, {V{0, kSeven}});
  auto attached = Attach(live.name());
  ASSERT_NE(attached, nullptr);
  const std::string text = vi::formatStatus(attached->status());
  EXPECT_NE(text.find("status: running"), std::string::npos) << text;
  EXPECT_NE(text.find("run id: "), std::string::npos);
  EXPECT_NE(text.find("heartbeat: 1"), std::string::npos);
  EXPECT_NE(text.find("outcome: none yet"), std::string::npos);
  EXPECT_NE(text.find("cycles written: 1"), std::string::npos);
  EXPECT_NE(text.find("cycle slots: 4 x 512 bytes"), std::string::npos);
  EXPECT_NE(text.find("bulk slots: 2 x 256 bytes"), std::string::npos);
  live.Close(3);
  EXPECT_NE(vi::formatStatus(attached->status()).find("outcome: crash"), std::string::npos);
  EXPECT_NE(vi::formatStatus(attached->status()).find("status: finished"), std::string::npos);
}

TEST(Inspector, IMP_0092_WriterGoneIsFalseWhileTheWritersProcessLives) {
  Live live("alive", Describe(kEchoPorts));
  auto attached = Attach(live.name());
  ASSERT_NE(attached, nullptr);
  EXPECT_FALSE(vi::writerGone(attached->status(), std::chrono::milliseconds(30)));
}

TEST(Inspector, IMP_0092_WriterGoneIsTrueForADeadPidWithAStillHeartbeatAndFalseOtherwise) {
  const std::string gone = UniqueName("gone");
  auto region = FakeRegion(gone, layout::kLayoutVersion, kDeadPid, 1);
  EXPECT_TRUE(vi::writerGone(*static_cast<const layout::MeasStatus*>(region->data()), std::chrono::milliseconds(30)));

  // A status that is finished is not "gone": the writer ended on purpose.
  const std::string finished = UniqueName("fin");
  auto done = FakeRegion(finished, layout::kLayoutVersion, kDeadPid, 3);
  EXPECT_FALSE(vi::writerGone(*static_cast<const layout::MeasStatus*>(done->data()), std::chrono::milliseconds(30)));

  // A heartbeat that moves between the two reads says something still writes.
  const std::string moving = UniqueName("move");
  auto beating = FakeRegion(moving, layout::kLayoutVersion, kDeadPid, 1);
  auto& status = *static_cast<layout::MeasStatus*>(beating->data());
  std::thread beat([&] {
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    status.heartbeat.fetch_add(1);
  });
  EXPECT_FALSE(vi::writerGone(status, std::chrono::milliseconds(150)));
  beat.join();
  EXPECT_EQ(vi::writerGoneLine(12), "writer gone at step 12");
}

// ---- RCT:IMP-0038 ---------------------------------------------------------------------------------------------

TEST(Inspector, RCT_IMP_0038_AttachMapsBothSegmentsAndReadsTheDescription) {
  Live live("attach", Describe(kEchoPorts, {{"S", MeasStage::MODE_SIMULATE}}));
  auto attached = Attach(live.name());
  ASSERT_NE(attached, nullptr);
  ASSERT_NE(attached->bulk, nullptr);
  const auto description = vi::readDescription(*attached);
  ASSERT_TRUE(description.has_value());
  EXPECT_EQ(description->ports_size(), 3);
  EXPECT_EQ(description->stages(0).name(), "S");
}

TEST(Inspector, RCT_IMP_0038_AttachOfANameNobodyHoldsIsNoSuchName) {
  const vi::AttachReport report = vi::attachReadOnly(UniqueName("nobody"));
  EXPECT_EQ(report.outcome, vi::AttachOutcome::kNoSuchName);
  EXPECT_NE(report.cause.find("no live measurement named"), std::string::npos);
}

TEST(Inspector, RCT_IMP_0038_ALayoutMismatchNamesBothVersionsAndReadsNothing) {
  const std::string name = UniqueName("layout");
  auto region = FakeRegion(name, layout::kLayoutVersion + 1, kDeadPid, 1);
  const vi::AttachReport report = vi::attachReadOnly(name);
  EXPECT_EQ(report.outcome, vi::AttachOutcome::kLayoutMismatch);
  EXPECT_NE(report.cause.find(std::to_string(layout::kLayoutVersion + 1)), std::string::npos) << report.cause;
  EXPECT_NE(report.cause.find("reads layout version " + std::to_string(layout::kLayoutVersion)), std::string::npos);
  EXPECT_EQ(report.attached, nullptr);
}

TEST(Inspector, RCT_IMP_0038_ARegionSmallerThanItsStatusSaysIsCannotAttach) {
  const std::string name = UniqueName("small");
  std::unique_ptr<SharedRegion> region;
  ASSERT_NE(SharedRegion::createOrReplace(name, sizeof(layout::MeasStatus), nullptr, region), SharedRegion::Create::kFailed);
  auto& s = *static_cast<layout::MeasStatus*>(region->data());
  s.layoutVersion = layout::kLayoutVersion;
  s.descriptionCapacity = 1u << 20;  // the status says far more than the mapping holds
  s.cycleSlotCount = 64;
  s.cycleSlotSize = 1u << 20;
  s.bulkSlotCount = 1;
  s.bulkSlotSize = 64;
  s.magic = layout::kMagic;
  s.status.store(1);
  const vi::AttachReport report = vi::attachReadOnly(name);
  EXPECT_EQ(report.outcome, vi::AttachOutcome::kTooSmall);
}

// ---- IMP-0094, RCT:IMP-0039 ------------------------------------------------------------------------------------

TEST(Inspector, IMP_0094_ARingOfTwoSlotsReadAfterFiveStepsReportsTheSkippedSteps) {
  Live live("ring", Describe(kEchoPorts), 2, 512);
  for (std::uint64_t step = 0; step < 5; ++step) live.Step(step, static_cast<std::int64_t>(step) * 10, {V{0, kSeven}});
  auto attached = Attach(live.name());
  ASSERT_NE(attached, nullptr);
  vi::FollowCursor cursor;
  const std::vector<vi::CycleView> cycles = vi::readCycles(*attached, cursor);
  ASSERT_EQ(cycles.size(), 2u);
  EXPECT_EQ(cycles[0].step, 3u);
  EXPECT_EQ(cycles[1].step, 4u);
  EXPECT_EQ(cursor.takeSkipped(), 3u);
  EXPECT_EQ(cursor.takeSkipped(), 0u);
  // The next step is read once, with nothing skipped.
  live.Step(5, 50, {V{0, kSeven}});
  const std::vector<vi::CycleView> more = vi::readCycles(*attached, cursor);
  ASSERT_EQ(more.size(), 1u);
  EXPECT_EQ(more[0].step, 5u);
  EXPECT_EQ(cursor.takeSkipped(), 0u);
  EXPECT_TRUE(vi::readCycles(*attached, cursor).empty());
}

TEST(Inspector, RCT_IMP_0039_DumpDecodesAPayloadThroughTheDescriptorSetOnly) {
  const vi::DynamicDecoder decoder(EchoDescriptorSet());
  EXPECT_EQ(decoder.decode("t.Echo", kSeven.data(), kSeven.size()), "counter: 7");
  EXPECT_NE(decoder.decode("t.Missing", kSeven.data(), kSeven.size()).find("unknown type"), std::string::npos);
  // A type the binary itself was compiled with is not found by name: only the set's files are in the pool.
  const vi::DynamicDecoder empty{std::string()};
  EXPECT_NE(empty.decode("adas.livemeas.MeasCycle", kSeven.data(), kSeven.size()).find("unknown type"), std::string::npos);
  const std::vector<std::uint8_t> header = {0x0A, 0x02, 0x10, 0x09};  // t.Hdr { sig_header { measurement_counter: 9 } }
  EXPECT_EQ(decoder.measurementCounter("t.Hdr", header.data(), header.size()), std::optional<std::uint64_t>(9));
  EXPECT_FALSE(decoder.measurementCounter("t.Echo", kSeven.data(), kSeven.size()).has_value());
}

// ---- IMP-0093 -------------------------------------------------------------------------------------------------

TEST(Inspector, IMP_0093_DumpPrintsOneLinePerValueWithItsRunPositionOriginAndDecodedPayload) {
  Live live("dump", Describe(kEchoPorts));
  live.Step(0, 0, {V{0, kSeven, MeasPortValue::ORIGIN_MEASURED}, V{0, {0x08, 0x08}}, V{1, kSeven, MeasPortValue::ORIGIN_SIMULATED, 40}});
  auto attached = Attach(live.name());
  ASSERT_NE(attached, nullptr);
  std::ostringstream out, err;
  EXPECT_EQ(vi::runDump(*attached, vi::DumpOptions{}, out, err), vi::kInspectOk);
  const std::string text = out.str();
  EXPECT_NE(text.find("step 0 port S.control run 0 origin MEASURED age_ns 0 counter: 7\n"), std::string::npos) << text;
  EXPECT_NE(text.find("step 0 port S.control run 1 origin SIMULATED age_ns 0 counter: 8\n"), std::string::npos) << text;
  EXPECT_NE(text.find("step 0 port S.refSync run 0 origin SIMULATED age_ns 40 counter: 7\n"), std::string::npos) << text;
}

TEST(Inspector, IMP_0093_DumpPrintsAnOmittedValueAndABulkReferenceAsSuch) {
  Live live("bulk", Describe({{"X.big", "t.Echo"}, {"X.frame", "t.Echo"}}), 4, 256);
  std::vector<std::uint8_t> too_big(400, 0x41);  // larger than a cycle slot: omitted
  live.Step(0, 0, {V{0, too_big}, V{1, kSeven, MeasPortValue::ORIGIN_MEASURED, 0, 1}});
  auto attached = Attach(live.name());
  ASSERT_NE(attached, nullptr);
  std::ostringstream out, err;
  EXPECT_EQ(vi::runDump(*attached, vi::DumpOptions{}, out, err), vi::kInspectOk);
  EXPECT_NE(out.str().find("port X.big run 0 origin SIMULATED age_ns 0 omitted\n"), std::string::npos) << out.str();
  EXPECT_NE(out.str().find("port X.frame run 0 origin MEASURED age_ns 0 bulk slot 0 sequence 2\n"), std::string::npos)
      << out.str();
}

TEST(Inspector, IMP_0093_DumpDescriptionPrintsTheDecodedDescription) {
  Live live("desc", Describe(kEchoPorts, {{"S", MeasStage::MODE_SIMULATE}}));
  auto attached = Attach(live.name());
  ASSERT_NE(attached, nullptr);
  std::ostringstream out, err;
  vi::DumpOptions options;
  options.description = true;
  EXPECT_EQ(vi::runDump(*attached, options, out, err), vi::kInspectOk);
  EXPECT_NE(out.str().find("recording: \"rec.mcap\""), std::string::npos) << out.str();
  EXPECT_NE(out.str().find("name: \"S.refSync\""), std::string::npos);
  EXPECT_NE(out.str().find("descriptor_set: "), std::string::npos);
}

TEST(Inspector, IMP_0093_FollowStopsOnceTheMeasurementIsFinishedAndPrintsTheSkippedSteps) {
  Live live("follow", Describe(kEchoPorts), 2, 512);
  for (std::uint64_t step = 0; step < 4; ++step) live.Step(step, 0, {V{0, kSeven}});
  auto attached = Attach(live.name());
  ASSERT_NE(attached, nullptr);
  live.Close(1);
  std::ostringstream out, err;
  vi::DumpOptions options;
  options.follow = true;
  EXPECT_EQ(vi::runDump(*attached, options, out, err), vi::kInspectOk);
  EXPECT_NE(out.str().find("2 steps skipped\n"), std::string::npos) << out.str();
  EXPECT_NE(out.str().find("step 3 port S.control"), std::string::npos);
}

// ---- IMP-0095 .. IMP-0099 --------------------------------------------------------------------------------------

TEST(Inspector, IMP_0095_APortDroppedFromAMiddleStepIsAFindingAndAnUnvaluedPortIsNot) {
  // S.control (0) and S.refSync (1) from step 0; S.compState (2) from step 1; "X.in" (3) never has a value.
  const layout::MeasDescription description = Describe({{"S.control", "t.Echo"}, {"S.refSync", "t.Echo"},
                                                         {"S.compState", "t.Echo"}, {"X.in", "t.Echo"}});
  std::vector<vi::CycleView> clean = {Cycle(0, {V{0, kSeven}, V{1, kSeven}}),
                                      Cycle(1, {V{0, kSeven}, V{1, kSeven}, V{2, kSeven}}),
                                      Cycle(2, {V{0, kSeven}, V{1, kSeven}, V{2, kSeven}})};
  EXPECT_TRUE(vi::checkPorts(description, clean).empty());

  std::vector<vi::CycleView> planted = clean;
  planted[1] = Cycle(1, {V{0, kSeven}, V{2, kSeven}});  // S.refSync dropped from the middle step
  const std::vector<std::string> findings = vi::checkPorts(description, planted);
  ASSERT_EQ(findings.size(), 1u);
  EXPECT_EQ(findings[0], "step 1: port S.refSync has neither a value nor an omitted mark");

  // An omitted mark stands for the value.
  planted[1] = Cycle(1, {V{0, kSeven}, V{1, {}}, V{2, kSeven}});
  MarkOmitted(planted[1], 1);
  EXPECT_TRUE(vi::checkPorts(description, planted).empty());
}

TEST(Inspector, IMP_0096_AStepThatIsNotThePreviousPlusOneNamesBothNumbersAndALappedStepIsAFinding) {
  const std::vector<vi::CycleView> clean = {Cycle(4, {}), Cycle(5, {}), Cycle(6, {})};
  EXPECT_TRUE(vi::checkSteps(clean, 0).empty());
  const std::vector<vi::CycleView> gap = {Cycle(4, {}), Cycle(5, {}), Cycle(8, {})};
  const std::vector<std::string> findings = vi::checkSteps(gap, 0);
  ASSERT_EQ(findings.size(), 1u);
  EXPECT_EQ(findings[0], "step 8 follows step 5, expected step 6");
  const std::vector<std::string> lapped = vi::checkSteps(clean, 3);
  ASSERT_EQ(lapped.size(), 1u);
  EXPECT_NE(lapped[0].find("3 steps lost to lapping"), std::string::npos);
}

TEST(Inspector, IMP_0097_ARunWithNoRefSyncValueNamesStageStepAndPort) {
  const layout::MeasDescription description = Describe(kEchoPorts, {{"S", MeasStage::MODE_SIMULATE}, {"M", MeasStage::MODE_MEASURED}});
  // Step 0: two runs, two values on each port. Step 1: two runs, the second leaves no refSync value.
  const std::vector<vi::CycleView> clean = {
      Cycle(0, {V{0, kSeven}, V{0, kSeven}, V{1, kSeven}, V{1, kSeven}, V{2, kSeven}, V{2, kSeven}}),
      Cycle(1, {V{0, kSeven}, V{1, kSeven}, V{2, kSeven}})};
  EXPECT_TRUE(vi::checkRuns(description, clean).empty());
  const std::vector<vi::CycleView> planted = {
      Cycle(0, {V{0, kSeven}, V{0, kSeven}, V{1, kSeven}, V{2, kSeven}, V{2, kSeven}})};
  const std::vector<std::string> findings = vi::checkRuns(description, planted);
  ASSERT_EQ(findings.size(), 1u);
  EXPECT_EQ(findings[0], "step 0: stage S run 1 has no value on port S.refSync");
  // A value carried from an earlier step counts for no run: both runs lack a refSync value written in this step.
  const std::vector<vi::CycleView> carried = {
      Cycle(0, {V{0, kSeven}, V{0, kSeven}, V{1, kSeven, MeasPortValue::ORIGIN_SIMULATED, 500}, V{2, kSeven}, V{2, kSeven}})};
  const std::vector<std::string> strict = vi::checkRuns(description, carried);
  ASSERT_EQ(strict.size(), 2u);
  EXPECT_EQ(strict[0], "step 0: stage S run 0 has no value on port S.refSync");
  EXPECT_EQ(strict[1], "step 0: stage S run 1 has no value on port S.refSync");
}

TEST(Inspector, IMP_0099_ABadgeCountThatFallsNamesBadgeSubjectAndBothSteps) {
  const auto with_badge = [](std::uint64_t step, std::uint64_t count) {
    vi::CycleView view = Cycle(step, {});
    auto* badge = view.cycle.add_badges();
    badge->set_kind(adas::livemeas::MeasBadge::KIND_FALLBACK);
    badge->set_subject("B.in");
    badge->set_count(count);
    return view;
  };
  EXPECT_TRUE(vi::checkBadges({with_badge(0, 1), with_badge(1, 3), with_badge(2, 3)}).empty());
  const std::vector<std::string> findings = vi::checkBadges({with_badge(0, 1), with_badge(1, 3), with_badge(2, 2)});
  ASSERT_EQ(findings.size(), 1u);
  EXPECT_EQ(findings[0], "badge KIND_FALLBACK of B.in: count 2 at step 2 is lower than 3 at step 1");
}

TEST(Inspector, IMP_0098_AMeasuredValueThatDiffersFromTheRecordingIsAFindingASimulatedOneIsNot) {
  const std::filesystem::path path = TempPath(UniqueName("rec") + ".mcap");
  {
    simcore::io::CodecRegistry registry;
    ASSERT_TRUE(simcore::io::codecs::RegisterMcap(registry).ok());
    auto writer = registry.OpenWrite(path);
    ASSERT_TRUE(writer.ok());
    simcore::io::TopicInfo topic;
    topic.schema_name = "t.Echo";
    ASSERT_TRUE(writer.value()->Open(path, {{"/S/out", topic}}).ok());
    simcore::io::RawMessage message;
    message.topic = "/S/out";
    message.log_time_ns = 50;
    message.payload = kSeven;
    writer.value()->Write(message);
    writer.value()->Close();
  }
  const layout::MeasDescription description = Describe({{"S.out", "t.Echo"}});
  const std::vector<std::uint8_t> other = {0x08, 0x09};
  const std::vector<vi::CycleView> matching = {Cycle(0, {V{0, kSeven, MeasPortValue::ORIGIN_MEASURED}}, 100)};
  EXPECT_TRUE(vi::checkAgainstRecording(description, matching, path.string()).empty());

  const std::vector<vi::CycleView> differing = {Cycle(0, {V{0, other, MeasPortValue::ORIGIN_MEASURED}}, 100)};
  const std::vector<std::string> findings = vi::checkAgainstRecording(description, differing, path.string());
  ASSERT_EQ(findings.size(), 1u);
  EXPECT_EQ(findings[0], "step 0: port S.out (origin ORIGIN_MEASURED): payload bytes differ from the recording");

  const std::vector<vi::CycleView> simulated = {Cycle(0, {V{0, other, MeasPortValue::ORIGIN_SIMULATED}}, 100),
                                                Cycle(1, {V{0, other, MeasPortValue::ORIGIN_OVERRIDDEN}}, 100)};
  EXPECT_TRUE(vi::checkAgainstRecording(description, simulated, path.string()).empty());

  const std::vector<vi::CycleView> early = {Cycle(0, {V{0, kSeven, MeasPortValue::ORIGIN_MEASURED}}, 10)};
  const std::vector<std::string> before = vi::checkAgainstRecording(description, early, path.string());
  ASSERT_EQ(before.size(), 1u);
  EXPECT_NE(before[0].find("no recorded message at or before its simulation time"), std::string::npos);
  std::filesystem::remove(path);
}

// ---- IMP-0100 -------------------------------------------------------------------------------------------------

TEST(Inspector, IMP_0100_CheckOfACleanMeasurementFindsNothingAndOfAFlawedOneExitsOne) {
  for (const bool flawed : {false, true}) {
    Live live(flawed ? "flawed" : "clean", Describe(kEchoPorts, {{"S", MeasStage::MODE_SIMULATE}}));
    for (std::uint64_t step = 0; step < 4; ++step) {
      std::vector<V> values = {V{0, kSeven}, V{1, kSeven}, V{2, kSeven}};
      if (flawed && step == 2) values.erase(values.begin() + 1);  // S.refSync dropped from step 2
      live.Step(step, static_cast<std::int64_t>(step) * 10, values);
    }
    auto attached = Attach(live.name());
    ASSERT_NE(attached, nullptr);
    live.Close(1);
    std::ostringstream out, err;
    const int code = vi::runCheck(*attached, vi::CheckOptions{}, out, err);
    if (flawed) {
      EXPECT_EQ(code, vi::kInspectFound);
      EXPECT_NE(out.str().find("step 2: port S.refSync has neither a value nor an omitted mark\n"), std::string::npos)
          << out.str();
    } else {
      EXPECT_EQ(code, vi::kInspectOk) << out.str();
      EXPECT_TRUE(out.str().empty()) << out.str();
    }
  }
}

// ---- IMP-0091, IMP-0101: the executable -------------------------------------------------------------------------

TEST(Inspector, IMP_0091_AnUnknownVerbExitsTwoNamingIt) {
  const Ran ran = RunInspect({"frobnicate", "somename"});
  EXPECT_EQ(ran.exit_code, vi::kInspectUsage);
  EXPECT_NE(ran.error_text.find("unknown verb 'frobnicate'"), std::string::npos) << ran.error_text;
}

TEST(Inspector, IMP_0091_AttachOfANameNobodyHoldsExitsSixNamingIt) {
  const std::string name = UniqueName("exe_none");
  const Ran ran = RunInspect({"attach", name});
  EXPECT_EQ(ran.exit_code, vi::kInspectCannotAttach);
  EXPECT_NE(ran.error_text.find(name), std::string::npos) << ran.error_text;
}

TEST(Inspector, IMP_0091_ALayoutVersionMismatchExitsSixNamingBothVersions) {
  const std::string name = UniqueName("exe_layout");
  auto region = FakeRegion(name, layout::kLayoutVersion + 1, kDeadPid, 1);
  const Ran ran = RunInspect({"dump", name});
  EXPECT_EQ(ran.exit_code, vi::kInspectCannotAttach);
  EXPECT_NE(ran.error_text.find("layout version is " + std::to_string(layout::kLayoutVersion + 1)), std::string::npos)
      << ran.error_text;
  EXPECT_NE(ran.error_text.find("reads layout version " + std::to_string(layout::kLayoutVersion)), std::string::npos);
}

TEST(Inspector, IMP_0101_TheExecutableAttachesToALiveMeasurementAndDumpsIt) {
  Live live("exe_live", Describe(kEchoPorts));
  live.Step(0, 0, {V{0, kSeven}});
  const Ran ran = RunInspect({"attach", live.name()});
  EXPECT_EQ(ran.exit_code, vi::kInspectOk) << ran.error_text;
  const Ran dump = RunInspect({"dump", live.name(), "--description"});
  EXPECT_EQ(dump.exit_code, vi::kInspectOk) << dump.error_text;
}
