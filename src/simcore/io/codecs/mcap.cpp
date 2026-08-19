// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   The `.mcap` codec (`DD-13`: the only registration `WP-06` lands) --
///   the C++ twin of `io/mcap.py`, over the same conancenter `mcap/1.2.0`
///   library `sil_host/src/recording_reader.cpp` already vendors. All
///   capabilities true (embedded schemas, random access, round-trip,
///   capture time, arbitrary topics, meta blocks) -- `io/mcap.py`'s own
///   `CAPABILITIES` value, ported.
///
///   **Scoping note (honest, not silent):** the *content* of the
///   `run_manifest` meta block is opaque bytes to this codec (`GetMeta`/
///   `WriteMeta`, keyed by `MetaKind`) -- `simcore` does not yet carry a
///   structured `RunManifest` type (that is a later `WP`'s artifact, once
///   something in C++ actually constructs one). One consequence: this
///   reader does not replicate `io/mcap.py`'s `manifest_version >=
///   CAPTURE_TIME_MANIFEST_VERSION` gate for whether `publishTime` is a
///   real capture stamp or an old writer's meaningless `publishTime ==
///   logTime` -- no `WP-06` test (`UT-IO-*`) exercises that gate, and this
///   codec's own writer always sets `publishTime` deliberately, so every
///   recording round-tripped through this codec alone is capture-time-aware
///   by construction. Reading a *legacy* pre-two-clock `.mcap` file through
///   this reader and trusting its `capture_time_ns` is the known gap;
///   revisit once `RunManifest` has a C++ home to read the version from.
/// @author Pavan Karimajji

#define MCAP_IMPLEMENTATION
#include <mcap/mcap.hpp>

#include "simcore/io.hpp"

namespace simcore::io::codecs {

namespace {

Error MakeError(Kind kind, std::string expected, std::string found, std::string where, std::string hint = "") {
  return Error{kind, std::move(expected), std::move(found), std::move(where), std::move(hint)};
}

const char kTopicProvenanceMetaName[] = "topic_provenance";

std::vector<std::uint8_t> ToBytes(const mcap::ByteArray& data) {
  return std::vector<std::uint8_t>(reinterpret_cast<const std::uint8_t*>(data.data()),
                                    reinterpret_cast<const std::uint8_t*>(data.data()) + data.size());
}

mcap::ByteArray FromBytes(const std::vector<std::uint8_t>& data) {
  return mcap::ByteArray(reinterpret_cast<const std::byte*>(data.data()),
                          reinterpret_cast<const std::byte*>(data.data()) + data.size());
}

class McapWriter final : public Writer {
 public:
  Result<bool> Open(const std::filesystem::path& path, const std::map<std::string, TopicInfo>& topics) override {
    // SW-0041: no chunk buffering -- each record lands in the Data section
    // as it is written, so a mid-run crash leaves a readable file up to the
    // last completed message rather than losing an unflushed chunk (the
    // mcap C++ library exposes no mid-stream chunk-flush primitive beyond
    // `close()`/`terminate()`, so direct-to-data-section writing is the
    // honest way to meet this Accept clause with what the library gives).
    mcap::McapWriterOptions options("");
    options.noChunking = true;
    const mcap::Status status = writer_.open(path.string(), options);
    if (!status.ok()) {
      return Result<bool>::Fail(MakeError(
          Kind::Environment, "a writable path for an mcap file", status.message, path.string()));
    }

    // Sorted topic order (P-8, SW-0040): deterministic channel numbering is
    // part of what makes two writes of the same messages byte-identical --
    // `topics` is a `std::map`, already iterated in sorted key order.
    mcap::KeyValueMap provenance;
    for (const auto& [topic, info] : topics) {
      mcap::Schema schema(
          info.schema_name.empty() ? topic : info.schema_name, info.schema_bytes.empty() ? "" : "protobuf",
          FromBytes(info.schema_bytes));
      writer_.addSchema(schema);
      mcap::Channel channel(topic, "protobuf", schema.id);
      writer_.addChannel(channel);
      channel_ids_[topic] = channel.id;
      provenance[topic] = ToString(info.provenance);
    }
    mcap::Metadata provenance_meta;
    provenance_meta.name = kTopicProvenanceMetaName;
    provenance_meta.metadata = provenance;
    (void)writer_.write(provenance_meta);

    return Result<bool>::Ok(true);
  }

  void Write(const RawMessage& message) override {
    auto it = channel_ids_.find(message.topic);
    if (it == channel_ids_.end()) {
      // R-SIM-14's `arbitrary_topics` capability: a topic not declared at
      // `Open()` still gets a channel, schema-less -- registered on demand
      // rather than dropped, since this codec declares that capability true.
      mcap::Channel channel(message.topic, "protobuf", 0);
      writer_.addChannel(channel);
      it = channel_ids_.emplace(message.topic, channel.id).first;
    }
    mcap::Message msg;
    msg.channelId = it->second;
    msg.sequence = 0;
    msg.logTime = static_cast<std::uint64_t>(message.log_time_ns);
    msg.publishTime = static_cast<std::uint64_t>(message.capture_time_ns.value_or(message.log_time_ns));
    msg.dataSize = message.payload.size();
    msg.data = reinterpret_cast<const std::byte*>(message.payload.data());
    (void)writer_.write(msg);
  }

  void WriteMeta(const std::string& kind_name, const std::vector<std::uint8_t>& bytes) override {
    // Bytes stored under one flat key -- `io` treats meta content as
    // opaque (SW-0038's own "shall preserve unknown block kinds"), so no
    // structure beyond "one named blob of bytes" is imposed here.
    mcap::Metadata meta;
    meta.name = kind_name;
    meta.metadata["bytes"] = std::string(reinterpret_cast<const char*>(bytes.data()), bytes.size());
    (void)writer_.write(meta);
  }

  void Close() override { writer_.close(); }

 private:
  mcap::McapWriter writer_;
  std::map<std::string, mcap::ChannelId> channel_ids_;
};

class McapReader final : public Reader {
 public:
  ~McapReader() override {
    if (opened_) reader_.close();
  }

  Result<bool> Open(const std::filesystem::path& path) override {
    const mcap::Status status = reader_.open(path.string());
    if (!status.ok()) {
      return Result<bool>::Fail(MakeError(
          Kind::Environment, "a readable .mcap file", status.message, path.string(),
          "check the file exists and is a valid mcap recording"));
    }
    opened_ = true;
    const mcap::Status summary_status = reader_.readSummary(mcap::ReadSummaryMethod::AllowFallbackScan);
    if (!summary_status.ok()) {
      return Result<bool>::Fail(MakeError(
          Kind::Environment, "a readable .mcap summary", summary_status.message, path.string()));
    }
    ReadTopicProvenance();
    ResetView(0);
    return Result<bool>::Ok(true);
  }

  std::map<std::string, TopicInfo> Describe() const override {
    std::map<std::string, TopicInfo> result;
    for (const auto& [channel_id, channel] : reader_.channels()) {
      const mcap::SchemaPtr schema = reader_.schema(channel->schemaId);
      const auto provenance_it = provenance_by_topic_.find(channel->topic);
      const std::optional<std::string> raw =
          provenance_it != provenance_by_topic_.end() ? std::optional<std::string>(provenance_it->second)
                                                        : std::nullopt;
      TopicInfo info;
      info.schema_name = schema ? schema->name : "";
      info.provenance = OriginOrUnknown(raw);
      info.schema_bytes = schema ? ToBytes(schema->data) : std::vector<std::uint8_t>{};
      result[channel->topic] = std::move(info);
    }
    return result;
  }

  void Seek(std::int64_t log_time_ns) override { ResetView(static_cast<mcap::Timestamp>(log_time_ns)); }

  Batch ReadRange(const ReadBounds& bounds) override {
    return detail::AccumulateBatch(bounds, lookahead_, [this]() { return Pull(); });
  }

  void Close() override {
    if (opened_) {
      reader_.close();
      opened_ = false;
    }
  }

  std::optional<std::vector<std::uint8_t>> GetMeta(const std::string& kind_name) const override {
    const auto range = reader_.metadataIndexes().equal_range(kind_name);
    if (range.first == range.second) return std::nullopt;
    mcap::Record record;
    if (!mcap::McapReader::ReadRecord(*const_cast<McapReader*>(this)->reader_.dataSource(), range.first->second.offset, &record)
             .ok()) {
      return std::nullopt;
    }
    mcap::Metadata metadata;
    if (!mcap::McapReader::ParseMetadata(record, &metadata).ok()) return std::nullopt;
    const auto value_it = metadata.metadata.find("bytes");
    if (value_it == metadata.metadata.end()) return std::nullopt;
    return std::vector<std::uint8_t>(value_it->second.begin(), value_it->second.end());
  }

 private:
  void ReadTopicProvenance() {
    const auto range = reader_.metadataIndexes().equal_range(kTopicProvenanceMetaName);
    if (range.first == range.second) return;
    mcap::Record record;
    if (!mcap::McapReader::ReadRecord(*reader_.dataSource(), range.first->second.offset, &record).ok()) return;
    mcap::Metadata metadata;
    if (!mcap::McapReader::ParseMetadata(record, &metadata).ok()) return;
    for (const auto& [topic, value] : metadata.metadata) {
      provenance_by_topic_[topic] = value;
    }
  }

  void ResetView(mcap::Timestamp start_time) {
    lookahead_.reset();
    mcap::ReadMessageOptions options(start_time, mcap::MaxTime);
    // `LogTimeOrder` silently yields ZERO messages against a file written
    // with `McapWriterOptions::noChunking = true` (SW-0041, McapWriter::Open
    // above): the mcap library's log-time-ordered iteration merge-sorts
    // across the Chunk index, and a noChunking file has no Chunk records to
    // merge -- found live (VZ-12, 2026-08-19) writing a real recording with
    // this codec and reading it straight back through `ReadRange`, which no
    // existing UT-IO-* test exercises (every real-mcap test round-trips meta
    // blocks or diffs raw bytes; UT-IO-01's message-level test uses the
    // throwaway codec, never this one). `FileOrder` is correct for what this
    // codec ever reads: SW-0040 already guarantees THIS codec's own writer
    // emits messages in call order, which is log-time order (WriterBase
    // forwards messages the moment they arrive, never reordering).
    options.readOrder = mcap::ReadMessageOptions::ReadOrder::FileOrder;
    view_.emplace(reader_.readMessages(on_problem_, options));
    iterator_.emplace(view_->begin());
  }

  std::optional<RawMessage> Pull() {
    if (!iterator_.has_value() || !view_.has_value() || *iterator_ == view_->end()) return std::nullopt;
    const mcap::MessageView& mv = **iterator_;
    RawMessage msg;
    msg.topic = mv.channel->topic;
    msg.log_time_ns = static_cast<std::int64_t>(mv.message.logTime);
    msg.capture_time_ns = static_cast<std::int64_t>(mv.message.publishTime);
    const auto* byte_ptr = reinterpret_cast<const std::uint8_t*>(mv.message.data);
    msg.payload.assign(byte_ptr, byte_ptr + mv.message.dataSize);
    ++(*iterator_);
    return msg;
  }

  mcap::McapReader reader_;
  bool opened_ = false;
  mcap::ProblemCallback on_problem_ = [](const mcap::Status&) {};
  std::optional<mcap::LinearMessageView> view_;
  std::optional<mcap::LinearMessageView::Iterator> iterator_;
  std::optional<RawMessage> lookahead_;
  std::map<std::string, std::string> provenance_by_topic_;
};

}  // namespace

Result<bool> RegisterMcap(CodecRegistry& registry) {
  Capabilities capabilities;
  capabilities.embedded_schemas = true;
  capabilities.random_access = true;
  capabilities.meta_blocks = true;
  capabilities.arbitrary_topics = true;
  capabilities.round_trips = true;
  capabilities.capture_time = true;

  return registry.Register(
      ".mcap", capabilities, []() -> std::unique_ptr<Reader> { return std::make_unique<McapReader>(); },
      []() -> std::unique_ptr<Writer> { return std::make_unique<McapWriter>(); });
}

}  // namespace simcore::io::codecs
