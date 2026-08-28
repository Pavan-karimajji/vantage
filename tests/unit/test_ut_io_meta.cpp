// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-IO-18`/`UT-IO-19` (`SW-0038`/`SW-0039`), against the `.mcap`
///   codec: every declared `MetaKind` (plus an undeclared kind name) reads
///   back exactly as written, and a topic with no provenance block at all
///   -- a foreign recording, written with the raw mcap library directly,
///   bypassing our own writer's automatic `topic_provenance` block -- reads
///   as `Provenance::kUnknown`, never a guessed `kMeasured`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

// Declarations only -- codecs/mcap.cpp's own translation unit already
// defines MCAP_IMPLEMENTATION over <mcap/mcap.hpp> (reader AND writer),
// linked in via simcore. A second MCAP_IMPLEMENTATION here would
// duplicate-define mcap/types.inl's symbols (mirrors
// sil_host/tests/system/test_st_c7_2_two_stage_resim.cpp's identical note).
#include <mcap/writer.hpp>

#include "simcore/io.hpp"

namespace simcore::io {
namespace {

std::filesystem::path TempPath(const std::string& name) {
  return std::filesystem::temp_directory_path() / name;
}

TEST(UtIo18MetaBlocks, EveryDeclaredKindPlusAnUndeclaredOneRoundTrips) {
  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());

  const std::filesystem::path path = TempPath("ut_io_18.mcap");
  auto writer = registry.OpenWrite(path);
  ASSERT_TRUE(writer.ok());
  ASSERT_TRUE(writer.value()->Open(path, {}).ok());

  const std::vector<MetaKind> kinds = {
      MetaKind::kRunManifest, MetaKind::kConfigBundle, MetaKind::kPluginIdentity, MetaKind::kLineage,
      MetaKind::kTolerance,
  };
  for (const MetaKind kind : kinds) {
    const std::string content = "content-for-" + ToString(kind);
    writer.value()->WriteMeta(ToString(kind), std::vector<std::uint8_t>(content.begin(), content.end()));
  }
  // SW-0038's Accept: an undeclared kind name still round-trips.
  const std::string undeclared_content = "an undeclared kind's bytes";
  writer.value()->WriteMeta("future_kind_nobody_named_yet", std::vector<std::uint8_t>(undeclared_content.begin(), undeclared_content.end()));
  writer.value()->Close();

  auto reader = registry.OpenRead(path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(path).ok());

  for (const MetaKind kind : kinds) {
    const auto block = reader.value()->GetMeta(ToString(kind));
    ASSERT_TRUE(block.has_value()) << ToString(kind);
    const std::string expected = "content-for-" + ToString(kind);
    EXPECT_EQ(std::string(block->begin(), block->end()), expected);
  }
  const auto undeclared_block = reader.value()->GetMeta("future_kind_nobody_named_yet");
  ASSERT_TRUE(undeclared_block.has_value());
  EXPECT_EQ(std::string(undeclared_block->begin(), undeclared_block->end()), undeclared_content);

  const auto absent = reader.value()->GetMeta("nothing_was_ever_written_here");
  EXPECT_FALSE(absent.has_value());
}

TEST(UtIo19NoProvenanceBlock, ForeignRecordingWithNoProvenanceYieldsUnknown) {
  const std::filesystem::path path = TempPath("ut_io_19_foreign.mcap");
  {
    // Written with the raw mcap library, deliberately bypassing our own
    // McapWriter -- this is what "a recording carrying no provenance
    // metadata" (SW-0039) means: a file this framework did not produce.
    mcap::McapWriter raw_writer;
    mcap::McapWriterOptions options("");
    ASSERT_TRUE(raw_writer.open(path.string(), options).ok());
    mcap::Schema schema("placeholder", "", "");
    raw_writer.addSchema(schema);
    mcap::Channel channel("foreign/topic", "", schema.id);
    raw_writer.addChannel(channel);
    mcap::Message message;
    message.channelId = channel.id;
    message.sequence = 1;
    message.logTime = 1;
    message.publishTime = 1;
    const std::uint8_t payload = 0;
    message.dataSize = 1;
    message.data = reinterpret_cast<const std::byte*>(&payload);
    ASSERT_TRUE(raw_writer.write(message).ok());
    raw_writer.close();
  }

  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterMcap(registry).ok());
  auto reader = registry.OpenRead(path);
  ASSERT_TRUE(reader.ok());
  ASSERT_TRUE(reader.value()->Open(path).ok());

  // The index is canonicalised at load (`io::CanonicalTopic`), so a file
  // written with the older slash-less spelling is found under the canonical
  // one -- the literal is spelled out rather than computed, so this also
  // pins WHICH form the index uses.
  const std::map<std::string, TopicInfo> topics = reader.value()->Describe();
  const auto it = topics.find("/foreign/topic");
  ASSERT_NE(it, topics.end());
  EXPECT_EQ(it->second.provenance, Provenance::kUnknown);
  EXPECT_EQ(topics.count("foreign/topic"), 0u);  // never both spellings
}

}  // namespace
}  // namespace simcore::io
