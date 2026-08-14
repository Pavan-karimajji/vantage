// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-IO-01`..`UT-IO-04` (`SW-0021`..`SW-0024`): the codec contract
///   itself -- a throwaway codec against `Reader`/`Writer`, capability
///   declaration queried with no file opened, extension-keyed registration
///   and its refusal cases.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <fstream>

#include "simcore/io.hpp"

namespace simcore::io {
namespace {

// UT-IO-01's own throwaway codec: a trivial length-prefixed binary format,
// self-contained in this test file -- nothing outside it and the registry
// changes to add this "format" (SW-0021's Accept).
class ThrowawayWriter final : public Writer {
 public:
  Result<bool> Open(const std::filesystem::path& path, const std::map<std::string, TopicInfo>&) override {
    out_.open(path, std::ios::binary | std::ios::trunc);
    return Result<bool>::Ok(out_.is_open());
  }
  void Write(const RawMessage& message) override {
    const auto topic_len = static_cast<std::uint32_t>(message.topic.size());
    const auto payload_len = static_cast<std::uint32_t>(message.payload.size());
    out_.write(reinterpret_cast<const char*>(&topic_len), sizeof(topic_len));
    out_.write(message.topic.data(), topic_len);
    out_.write(reinterpret_cast<const char*>(&message.log_time_ns), sizeof(message.log_time_ns));
    out_.write(reinterpret_cast<const char*>(&payload_len), sizeof(payload_len));
    out_.write(reinterpret_cast<const char*>(message.payload.data()), payload_len);
  }
  void WriteMeta(const std::string&, const std::vector<std::uint8_t>&) override {}
  void Close() override { out_.close(); }

 private:
  std::ofstream out_;
};

class ThrowawayReader final : public Reader {
 public:
  Result<bool> Open(const std::filesystem::path& path) override {
    in_.open(path, std::ios::binary);
    return Result<bool>::Ok(in_.is_open());
  }
  std::map<std::string, TopicInfo> Describe() const override { return {}; }
  void Seek(std::int64_t) override {}
  Batch ReadRange(const ReadBounds& bounds) override {
    return detail::AccumulateBatch(bounds, lookahead_, [this]() { return Pull(); });
  }
  void Close() override { in_.close(); }
  std::optional<std::vector<std::uint8_t>> GetMeta(const std::string&) const override { return std::nullopt; }

 private:
  std::optional<RawMessage> Pull() {
    std::uint32_t topic_len = 0;
    if (!in_.read(reinterpret_cast<char*>(&topic_len), sizeof(topic_len))) return std::nullopt;
    RawMessage msg;
    msg.topic.resize(topic_len);
    in_.read(msg.topic.data(), topic_len);
    in_.read(reinterpret_cast<char*>(&msg.log_time_ns), sizeof(msg.log_time_ns));
    std::uint32_t payload_len = 0;
    in_.read(reinterpret_cast<char*>(&payload_len), sizeof(payload_len));
    msg.payload.resize(payload_len);
    in_.read(reinterpret_cast<char*>(msg.payload.data()), payload_len);
    return msg;
  }

  std::ifstream in_;
  std::optional<RawMessage> lookahead_;
};

Capabilities RoundTripCaps() {
  Capabilities caps;
  caps.round_trips = true;
  return caps;
}

std::filesystem::path TempPath(const std::string& name) {
  return std::filesystem::temp_directory_path() / name;
}

TEST(UtIo01CodecContract, ThrowawayCodecRoundTripsAgainstTheSharedContract) {
  CodecRegistry registry;
  const auto registered = registry.Register(
      ".throwaway", RoundTripCaps(), []() -> std::unique_ptr<Reader> { return std::make_unique<ThrowawayReader>(); },
      []() -> std::unique_ptr<Writer> { return std::make_unique<ThrowawayWriter>(); });
  ASSERT_TRUE(registered.ok());

  const std::filesystem::path path = TempPath("ut_io_01.throwaway");
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  ASSERT_TRUE(writer.value()->Open(path, {}).ok());
  RawMessage msg;
  msg.topic = "a.topic";
  msg.log_time_ns = 42;
  msg.payload = {1, 2, 3};
  writer.value()->Write(msg);
  writer.value()->Close();

  auto reader = registry.OpenRead(path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(path).ok());
  const Batch batch = reader.value()->ReadRange(ReadBounds{});
  ASSERT_EQ(batch.messages.size(), 1u);
  EXPECT_EQ(batch.messages[0].topic, "a.topic");
  EXPECT_EQ(batch.messages[0].log_time_ns, 42);
  EXPECT_EQ(batch.messages[0].payload, (std::vector<std::uint8_t>{1, 2, 3}));
}

TEST(UtIo02Capabilities, QueriedWithNoFileOpened) {
  CodecRegistry registry;
  Capabilities round_trip = RoundTripCaps();
  Capabilities write_only;
  write_only.round_trips = false;

  ASSERT_TRUE(registry
                  .Register(
                      ".a", round_trip, []() -> std::unique_ptr<Reader> { return std::make_unique<ThrowawayReader>(); },
                      []() -> std::unique_ptr<Writer> { return std::make_unique<ThrowawayWriter>(); })
                  .ok());
  ASSERT_TRUE(registry
                  .Register(
                      ".b", write_only, nullptr,
                      []() -> std::unique_ptr<Writer> { return std::make_unique<ThrowawayWriter>(); })
                  .ok());

  const auto caps_a = registry.CapabilitiesFor(".a");
  const auto caps_b = registry.CapabilitiesFor(".b");
  ASSERT_TRUE(caps_a.ok());
  ASSERT_TRUE(caps_b.ok());
  EXPECT_TRUE(caps_a.value().round_trips);
  EXPECT_FALSE(caps_b.value().round_trips);

  const auto unknown = registry.CapabilitiesFor(".nope");
  EXPECT_FALSE(unknown.ok());
}

TEST(UtIo03Registration, ExtensionLookupAndDuplicateRefusal) {
  CodecRegistry registry;
  ASSERT_TRUE(registry
                  .Register(
                      ".throwaway", RoundTripCaps(),
                      []() -> std::unique_ptr<Reader> { return std::make_unique<ThrowawayReader>(); },
                      []() -> std::unique_ptr<Writer> { return std::make_unique<ThrowawayWriter>(); })
                  .ok());

  const auto opened = registry.OpenRead(TempPath("whatever.throwaway"));
  EXPECT_TRUE(opened.ok());

  const auto unknown = registry.OpenRead(TempPath("whatever.unknown_ext"));
  EXPECT_FALSE(unknown.ok());

  const auto duplicate = registry.Register(
      ".throwaway", RoundTripCaps(), []() -> std::unique_ptr<Reader> { return std::make_unique<ThrowawayReader>(); },
      []() -> std::unique_ptr<Writer> { return std::make_unique<ThrowawayWriter>(); });
  EXPECT_FALSE(duplicate.ok());
  if (!duplicate.ok()) {
    EXPECT_EQ(duplicate.error().kind, Kind::Internal);
  }
}

TEST(UtIo04ReadersAndWritersSymmetric, RoundTripRequiresAWriterAndWriteOnlyRefusesOpenRead) {
  CodecRegistry registry;

  // A round_trip codec registered with no WriterFactory is refused at
  // Register() itself (IMP-0024).
  const auto missing_writer = registry.Register(
      ".rt", RoundTripCaps(), []() -> std::unique_ptr<Reader> { return std::make_unique<ThrowawayReader>(); },
      nullptr);
  EXPECT_FALSE(missing_writer.ok());

  // A non-round-trip (write-only) codec registers fine with just a writer,
  // and OpenRead refuses it by capability (SW-0024's Accept), never a
  // coercion.
  Capabilities write_only;
  write_only.round_trips = false;
  ASSERT_TRUE(registry
                  .Register(
                      ".export", write_only, nullptr,
                      []() -> std::unique_ptr<Writer> { return std::make_unique<ThrowawayWriter>(); })
                  .ok());

  const auto opened_write = registry.OpenWrite(TempPath("whatever.export"));
  EXPECT_TRUE(opened_write.ok());

  const auto opened_read = registry.OpenRead(TempPath("whatever.export"));
  EXPECT_FALSE(opened_read.ok());
  if (!opened_read.ok()) {
    EXPECT_EQ(opened_read.error().kind, Kind::Authoring);
  }
}

}  // namespace
}  // namespace simcore::io
