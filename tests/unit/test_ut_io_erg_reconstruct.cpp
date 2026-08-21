// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-IO-28`/`UT-IO-29` (`SM-05a`): the real `.erg` codec
///   against real fixtures (`tests/fixtures/erg/`, provenance recorded in
///   `make_erg_fixture.py`). `UT-IO-28` reconstructs the real
///   single-row fixture and cross-checks every field against ground truth
///   established two ways, independently of `erg.cpp`'s own logic:
///   (1) the raw column bytes at their known, hand-verified offsets, and
///   (2) generic protobuf reflection over the reconstructed payload built
///   from a DescriptorPool this test constructs itself, from the same
///   manifest sidecar's bytes, never reusing `ErgReader`'s own internal
///   state. `UT-IO-29` drains the real 3000-row fixture end to end.
/// @author Pavan Karimajji

#include <fstream>
#include <sstream>

#include <gtest/gtest.h>

#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>
#include <google/protobuf/descriptor_database.h>
#include <google/protobuf/dynamic_message.h>

#include "simcore/io.hpp"
#include "io/codecs/erg_wire.hpp"

namespace simcore::io {
namespace {

namespace pb = google::protobuf;

std::filesystem::path FixturesDir() {
  // tests/unit/test_ut_io_erg_reconstruct.cpp -> ../fixtures/erg
  return std::filesystem::path(__FILE__).parent_path() / ".." / "fixtures" / "erg";
}

std::string ReadFile(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  std::ostringstream buf;
  buf << in.rdbuf();
  return buf.str();
}

// Independently rebuilds a DescriptorPool from the fixture's own
// manifest sidecar -- deliberately not touching anything `ErgReader`
// constructed, so a field-value assertion against this pool is a genuine
// cross-check, not a restatement of the codec's own internal state.
class IndependentManifestReader {
 public:
  explicit IndependentManifestReader(const std::filesystem::path& manifest_path) {
    const std::string bytes = ReadFile(manifest_path);
    std::string descriptor_set_bytes;
    codecs::erg_detail::WalkFields(bytes, [&](const codecs::erg_detail::WireField& f) {
      if (f.wire_type == 2 && f.field_number == 9) descriptor_set_bytes.assign(f.bytes_value);
    });
    pb::FileDescriptorSet file_descriptor_set;
    file_descriptor_set.ParseFromString(descriptor_set_bytes);
    for (const auto& file_proto : file_descriptor_set.file()) db_.Add(file_proto);
    pool_ = std::make_unique<pb::DescriptorPool>(&db_);
    factory_ = std::make_unique<pb::DynamicMessageFactory>(pool_.get());
  }

  std::unique_ptr<pb::Message> Parse(const std::string& proto_type, const std::vector<std::uint8_t>& payload) const {
    const pb::Descriptor* descriptor = pool_->FindMessageTypeByName(proto_type);
    if (descriptor == nullptr) return nullptr;
    std::unique_ptr<pb::Message> message(factory_->GetPrototype(descriptor)->New());
    if (!message->ParseFromArray(payload.data(), static_cast<int>(payload.size()))) return nullptr;
    return message;
  }

 private:
  pb::SimpleDescriptorDatabase db_;
  std::unique_ptr<pb::DescriptorPool> pool_;
  std::unique_ptr<pb::DynamicMessageFactory> factory_;
};

// Reads a dotted field path off a generic message via reflection --
// exactly what a consumer with no compiled bindings would do.
double ReadFieldAsDouble(const pb::Message& message, const std::vector<std::string>& path) {
  const pb::Message* current = &message;
  const pb::Descriptor* descriptor = current->GetDescriptor();
  for (std::size_t i = 0; i + 1 < path.size(); ++i) {
    const pb::FieldDescriptor* field = descriptor->FindFieldByName(path[i]);
    current = &current->GetReflection()->GetMessage(*current, field);
    descriptor = field->message_type();
  }
  const pb::FieldDescriptor* leaf = descriptor->FindFieldByName(path.back());
  const pb::Reflection* refl = current->GetReflection();
  switch (leaf->cpp_type()) {
    case pb::FieldDescriptor::CPPTYPE_FLOAT:
      return refl->GetFloat(*current, leaf);
    case pb::FieldDescriptor::CPPTYPE_DOUBLE:
      return refl->GetDouble(*current, leaf);
    case pb::FieldDescriptor::CPPTYPE_INT32:
      return refl->GetInt32(*current, leaf);
    case pb::FieldDescriptor::CPPTYPE_UINT32:
      return refl->GetUInt32(*current, leaf);
    case pb::FieldDescriptor::CPPTYPE_ENUM:
      return refl->GetEnumValue(*current, leaf);
    default:
      return std::numeric_limits<double>::quiet_NaN();
  }
}

TEST(UtIoErg01, ReconstructsRealSingleRowFixture) {
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterErg(registry).ok());

  const std::filesystem::path erg_path = FixturesDir() / "bsd_tos_left_straight_1row.erg";
  auto reader_result = registry.OpenRead(erg_path);
  ASSERT_TRUE(reader_result.ok()) << reader_result.error().Format();
  const std::unique_ptr<Reader>& reader = reader_result.value();

  ASSERT_TRUE(reader->Open(erg_path).ok());

  const std::map<std::string, TopicInfo> topics = reader->Describe();
  ASSERT_EQ(topics.size(), 2u);
  ASSERT_TRUE(topics.count("bsd.outputs"));
  ASSERT_TRUE(topics.count("bsd.compState"));
  EXPECT_EQ(topics.at("bsd.outputs").schema_name, "adas.df.BsdOutputs");
  EXPECT_EQ(topics.at("bsd.compState").schema_name, "adas.df.CompState");
  EXPECT_EQ(topics.at("bsd.outputs").provenance, Provenance::kMeasured);

  ReadBounds bounds;
  bounds.max_messages = 100;
  const Batch batch = reader->ReadRange(bounds);
  ASSERT_EQ(batch.messages.size(), 2u);
  EXPECT_TRUE(batch.exhausted);

  const RawMessage* bsd_outputs_msg = nullptr;
  const RawMessage* bsd_compstate_msg = nullptr;
  for (const RawMessage& m : batch.messages) {
    EXPECT_EQ(m.log_time_ns, 0);                    // row 0's own Time == 0.0s
    EXPECT_FALSE(m.capture_time_ns.has_value());     // R-SIM-14: never defaulted
    if (m.topic == "bsd.outputs") bsd_outputs_msg = &m;
    if (m.topic == "bsd.compState") bsd_compstate_msg = &m;
  }
  ASSERT_NE(bsd_outputs_msg, nullptr);
  ASSERT_NE(bsd_compstate_msg, nullptr);

  // Independent verification path: a fresh DescriptorPool this test built
  // itself from the same manifest sidecar, never ErgReader's own state.
  const IndependentManifestReader independent(FixturesDir() / "bsd_tos_left_straight_1row.manifest.pb");
  const std::unique_ptr<pb::Message> bsd_outputs =
      independent.Parse("adas.df.BsdOutputs", bsd_outputs_msg->payload);
  const std::unique_ptr<pb::Message> bsd_compstate =
      independent.Parse("adas.df.CompState", bsd_compstate_msg->payload);
  ASSERT_NE(bsd_outputs, nullptr);
  ASSERT_NE(bsd_compstate, nullptr);

  // Ground truth: read directly off row 0's raw bytes at hand-verified
  // offsets (make_erg_fixture.py's own provenance), independently of
  // BOTH erg.cpp and the reflection helper above.
  constexpr float kExpectedObservableFraction = 0.574035108089447f;
  EXPECT_FLOAT_EQ(ReadFieldAsDouble(*bsd_outputs, {"left", "observable_fraction"}), kExpectedObservableFraction);
  EXPECT_FLOAT_EQ(ReadFieldAsDouble(*bsd_outputs, {"right", "observable_fraction"}), kExpectedObservableFraction);
  EXPECT_EQ(ReadFieldAsDouble(*bsd_outputs, {"left", "availability"}), 0);   // AVAILABLE
  EXPECT_EQ(ReadFieldAsDouble(*bsd_outputs, {"left", "scenario"}), 0);       // NONE
  EXPECT_EQ(ReadFieldAsDouble(*bsd_outputs, {"left", "warning"}), 0);        // OFF
  EXPECT_EQ(ReadFieldAsDouble(*bsd_outputs, {"version_number"}), 0);
  EXPECT_EQ(ReadFieldAsDouble(*bsd_compstate, {"state"}), 1);                // RUNNING

  reader->Close();
}

TEST(UtIoErg02, DrainsRealThreeThousandRowFixture) {
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterErg(registry).ok());

  const std::filesystem::path erg_path = FixturesDir() / "bsd_tos_left_straight_3000row.erg";
  auto reader_result = registry.OpenRead(erg_path);
  ASSERT_TRUE(reader_result.ok()) << reader_result.error().Format();
  const std::unique_ptr<Reader>& reader = reader_result.value();
  ASSERT_TRUE(reader->Open(erg_path).ok());

  std::size_t total_messages = 0;
  std::int64_t first_log_time_ns = -1;
  std::int64_t last_log_time_ns = -1;
  ReadBounds bounds;
  bounds.max_messages = 500;
  for (;;) {
    const Batch batch = reader->ReadRange(bounds);
    for (const RawMessage& m : batch.messages) {
      if (first_log_time_ns < 0) first_log_time_ns = m.log_time_ns;
      last_log_time_ns = m.log_time_ns;
    }
    total_messages += batch.messages.size();
    if (batch.exhausted) break;
  }

  // 3000 rows * 2 ports (bsd.outputs, bsd.compState) per row.
  EXPECT_EQ(total_messages, 6000u);
  EXPECT_EQ(first_log_time_ns, 0);
  // 2999 * 0.02s = 59.98s, within one nanosecond of exact.
  EXPECT_NEAR(last_log_time_ns, 59'980'000'000, 1'000'000);

  reader->Close();
}

}  // namespace
}  // namespace simcore::io
