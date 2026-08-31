// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-IO-22` (addendum to `WP-06`'s own closed exit criteria, `SW-0021`/
///   `SW-0025`): the real `.mcap` codec's `ReadRange` returns the messages
///   its own `Write` calls produced, in log-time order, after `Close()`.
///
///   **Why this test did not already exist, found live (VZ-12, 2026-08-19):**
///   every existing UT-IO-* case against the real mcap codec either
///   round-trips a meta block (`UT-IO-18`/`19`) or diffs raw file bytes
///   (`UT-IO-20`/`21`); `UT-IO-01`'s own message-level round trip uses the
///   throwaway codec registered in that same file, never this one. So
///   nothing had ever driven a real message through `McapWriter::Write` and
///   back out through `McapReader::ReadRange`. Doing exactly that (building
///   `modules/viz`'s `Session`, VZ-12) surfaced a real bug: `ResetView`
///   requested `ReadOrder::LogTimeOrder`, which silently returns ZERO
///   messages against a file written with `noChunking = true` (`SW-0041`) --
///   the mcap library's log-time-ordered iteration merge-sorts across the
///   Chunk index, and a noChunking file has no Chunk records to merge. Fixed
///   by reading in `FileOrder` instead (`mcap.cpp::ResetView`) -- correct
///   because `SW-0040` already guarantees this codec's own writer emits
///   messages in call order, which is log-time order.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include "simcore/io.hpp"

namespace simcore::io {
namespace {

std::filesystem::path TempPath(const std::string& name) {
  return std::filesystem::temp_directory_path() / name;
}

TEST(UtIo22McapRoundtrip, WrittenMessagesReadBackInCallOrder) {
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());

  const std::filesystem::path path = TempPath("ut_io_22.mcap");
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  TopicInfo topic_a;
  topic_a.schema_name = "a.Schema";
  ASSERT_TRUE(writer.value()->Open(path, {{"df.a", topic_a}}).ok());

  // SW-0040: WriterBase never reorders -- a real recorder's own messages
  // arrive in log-time order already, which is the assumption ResetView's
  // FileOrder read now relies on (see this file's own top note).
  for (std::int64_t t_ns : {1000, 2000, 3000}) {
    RawMessage message;
    message.topic = "df.a";
    message.log_time_ns = t_ns;
    message.payload = {static_cast<std::uint8_t>(t_ns / 1000)};
    writer.value()->Write(message);
  }
  writer.value()->Close();

  auto reader = registry.OpenRead(path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(path).ok());

  ReadBounds bounds;
  bounds.max_messages = 100;
  const Batch batch = reader.value()->ReadRange(bounds);

  ASSERT_EQ(batch.messages.size(), 3u);
  EXPECT_TRUE(batch.exhausted);
  EXPECT_EQ(batch.messages[0].log_time_ns, 1000);
  EXPECT_EQ(batch.messages[1].log_time_ns, 2000);
  EXPECT_EQ(batch.messages[2].log_time_ns, 3000);
  EXPECT_EQ(batch.messages[0].payload, (std::vector<std::uint8_t>{1}));
}

TEST(UtIo22McapRoundtrip, SeekLandsOnTheFirstMessageAtOrAfterTheGivenTime) {
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());

  const std::filesystem::path path = TempPath("ut_io_22_seek.mcap");
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  ASSERT_TRUE(writer.value()->Open(path, {}).ok());
  for (std::int64_t t_ns : {1000, 2000, 3000}) {
    RawMessage message;
    message.topic = "df.a";
    message.log_time_ns = t_ns;
    message.payload = {static_cast<std::uint8_t>(t_ns / 1000)};
    writer.value()->Write(message);
  }
  writer.value()->Close();

  auto reader = registry.OpenRead(path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(path).ok());

  reader.value()->Seek(2000);
  ReadBounds bounds;
  bounds.max_messages = 100;
  const Batch batch = reader.value()->ReadRange(bounds);
  ASSERT_EQ(batch.messages.size(), 2u);
  EXPECT_EQ(batch.messages[0].log_time_ns, 2000);
  EXPECT_EQ(batch.messages[1].log_time_ns, 3000);
}

// IMP-0117: `informational_only` (`RawMessage`, `io.hpp`) round-trips per
// message through the real `.mcap` codec -- the codec-level carrier
// `WP-13`'s own row named as a gap, closed here as `WP-06`'s (`SI-01`)
// scope.
TEST(UtIo22McapRoundtrip, InformationalOnlyRoundTripsPerMessage) {
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());

  const std::filesystem::path path = TempPath("ut_io_22_informational_only.mcap");
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  ASSERT_TRUE(writer.value()->Open(path, {}).ok());

  for (const auto& [t_ns, flagged] : {std::pair{1000, false}, std::pair{2000, true}, std::pair{3000, false}}) {
    RawMessage message;
    message.topic = "df.a";
    message.log_time_ns = t_ns;
    message.payload = {static_cast<std::uint8_t>(t_ns / 1000)};
    message.informational_only = flagged;
    writer.value()->Write(message);
  }
  writer.value()->Close();

  auto reader = registry.OpenRead(path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(path).ok());

  ReadBounds bounds;
  bounds.max_messages = 100;
  const Batch batch = reader.value()->ReadRange(bounds);

  ASSERT_EQ(batch.messages.size(), 3u);
  EXPECT_FALSE(batch.messages[0].informational_only);
  EXPECT_TRUE(batch.messages[1].informational_only);
  EXPECT_FALSE(batch.messages[2].informational_only);
}

std::vector<std::uint8_t> ManifestBytes(int version) {
  const std::string yaml = "manifest_version: " + std::to_string(version) + "\nrun_id: fx\n";
  return std::vector<std::uint8_t>(yaml.begin(), yaml.end());
}

// `R-SIM-14` / `mcap.cpp`'s own top note (2026-08-31): `capture_time_ns` is
// trusted from `publishTime` only for a file this codec has certified
// capture-time-aware -- never defaulted to reception. Regression coverage
// for the gap that note named, not a new `UT-IO-nn` requirement (see the
// note for why).
TEST(UtIo22McapRoundtrip, CaptureTimeReadsUnknownWithNoManifestBlock) {
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());

  const std::filesystem::path path = TempPath("ut_io_capture_time_no_manifest.mcap");
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  ASSERT_TRUE(writer.value()->Open(path, {}).ok());

  RawMessage message;
  message.topic = "df.a";
  message.log_time_ns = 1000;
  message.capture_time_ns = 5000;  // the writer sets publishTime deliberately...
  message.payload = {1};
  writer.value()->Write(message);
  writer.value()->Close();

  auto reader = registry.OpenRead(path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(path).ok());
  ReadBounds bounds;
  bounds.max_messages = 100;
  const Batch batch = reader.value()->ReadRange(bounds);

  ASSERT_EQ(batch.messages.size(), 1u);
  // ...but no `manifest` meta block exists to certify it, so the reader
  // must not trust it -- exactly the "no manifest at all" case `io/mcap.py`
  // also treats as not capture-time-aware (`manifest_version` defaults to
  // `0`, which fails `>= CAPTURE_TIME_MANIFEST_VERSION`).
  EXPECT_FALSE(batch.messages[0].capture_time_ns.has_value());
}

TEST(UtIo22McapRoundtrip, CaptureTimeReadsRealValueWhenManifestIsCaptureTimeAware) {
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());

  const std::filesystem::path path = TempPath("ut_io_capture_time_aware.mcap");
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  ASSERT_TRUE(writer.value()->Open(path, {}).ok());
  writer.value()->WriteMeta(ToString(MetaKind::kRunManifest), ManifestBytes(2));

  RawMessage message;
  message.topic = "df.a";
  message.log_time_ns = 1000;
  message.capture_time_ns = 5000;
  message.payload = {1};
  writer.value()->Write(message);
  writer.value()->Close();

  auto reader = registry.OpenRead(path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(path).ok());
  ReadBounds bounds;
  bounds.max_messages = 100;
  const Batch batch = reader.value()->ReadRange(bounds);

  ASSERT_EQ(batch.messages.size(), 1u);
  ASSERT_TRUE(batch.messages[0].capture_time_ns.has_value());
  EXPECT_EQ(*batch.messages[0].capture_time_ns, 5000);
}

// Planted violation (`R-REQ-9`): a manifest block genuinely exists, but its
// version predates the two-clock model -- `publishTime` on a file like this
// means nothing (an old writer set `publishTime == logTime` unconditionally),
// so trusting it here would be exactly the fabrication `R-SIM-14` forbids.
TEST(UtIo22McapRoundtrip, CaptureTimeReadsUnknownWhenManifestPredatesTwoClockModel) {
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());

  const std::filesystem::path path = TempPath("ut_io_capture_time_legacy_manifest.mcap");
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  ASSERT_TRUE(writer.value()->Open(path, {}).ok());
  writer.value()->WriteMeta(ToString(MetaKind::kRunManifest), ManifestBytes(1));

  RawMessage message;
  message.topic = "df.a";
  message.log_time_ns = 1000;
  message.payload = {1};
  // No explicit capture_time_ns -- the writer falls back to log_time_ns for
  // `publishTime` (`McapWriter::Write`'s own `value_or`), the real shape of
  // a pre-two-clock file.
  writer.value()->Write(message);
  writer.value()->Close();

  auto reader = registry.OpenRead(path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(path).ok());
  ReadBounds bounds;
  bounds.max_messages = 100;
  const Batch batch = reader.value()->ReadRange(bounds);

  ASSERT_EQ(batch.messages.size(), 1u);
  EXPECT_FALSE(batch.messages[0].capture_time_ns.has_value());
}

}  // namespace
}  // namespace simcore::io
