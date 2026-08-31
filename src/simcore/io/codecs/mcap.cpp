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
///   **`capture_time_ns` gap closed (2026-08-31).** `simcore` still does not
///   carry a structured `RunManifest` type -- the *content* of the
///   `manifest` meta block (`MetaKind::kRunManifest`) stays opaque bytes to
///   this codec, same as `config_bundle`/`plugin_identity` -- but
///   `io/mcap.py`'s own `manifest_version >= CAPTURE_TIME_MANIFEST_VERSION`
///   gate (`R-SIM-14`: a file whose manifest predates the two-clock model
///   wrote `publishTime == logTime` unconditionally, so trusting it as a
///   real capture stamp would fabricate information the writer never had)
///   did not need a full `RunManifest` port to close -- only the one
///   integer field that gate reads. `DetermineCaptureTimeAwareness` (below)
///   does a narrow, targeted scalar read of `manifest_version:` out of the
///   same opaque bytes, mirroring the Python gate's *decision* exactly
///   without building the type Python decides it from. No manifest block at
///   all (this codec's own `UT-IO-22` fixtures, most ad-hoc test files) is
///   read the same way Python reads it: not capture-time-aware, `R-SIM-14`'s
///   "never defaulted to reception" default. This codec's own writer still
///   always sets `publishTime` deliberately (`McapWriter::Write`), so a
///   recording round-tripped through `--save`'s `overwrite_manifest_meta`
///   patch (which writes `manifest_version=2`, `io/base.py`) reads back
///   capture-time-aware by construction; one written and read by this
///   codec's *test* fixtures with no manifest patch reads back `nullopt`,
///   honestly, rather than a value nobody certified. Proven by three new
///   cases in `UtIo22McapRoundtrip` (`test_ut_io_mcap_roundtrip.cpp`) --
///   no new `UT-IO-nn` id allocated: nothing's `Verify` clause cites this
///   fix (`R-REQ-9` only mechanises a *cited* id), the same "regression
///   coverage, not a new requirement" shape `test_ut_io_erg_negative.cpp`'s
///   own top note already uses for a defect found outside the `WP` that
///   built the code it fixes.
/// @author Pavan Karimajji

#define MCAP_IMPLEMENTATION
#include <mcap/mcap.hpp>

#include <cctype>
#include <set>
#include <utility>

#include "simcore/io.hpp"

namespace simcore::io::codecs {

namespace {

Error MakeError(Kind kind, std::string expected, std::string found, std::string where, std::string hint = "") {
  return Error{kind, std::move(expected), std::move(found), std::move(where), std::move(hint)};
}

// Mirrors `io/mcap.py`'s own `CAPTURE_TIME_MANIFEST_VERSION = 2`
// (`io/base.py`) exactly -- the two must move together. No shared header
// exists between the Python and C++ sides (`simcore` links nothing
// first-party that could carry it), so this is a second, deliberately
// named copy of one integer, not an attempt to silently stay in sync.
constexpr int kCaptureTimeManifestVersion = 2;

// A narrow, targeted read of ONE scalar out of a `manifest` meta block's
// YAML bytes -- not a YAML parser, and not the `RunManifest` port this
// file's own top note says does not exist yet. Safe because the producer
// side is controlled: `io/base.py::manifest_to_dict` always emits
// `manifest_version` as a bare, unquoted top-level integer
// (`yaml.safe_dump(..., sort_keys=True)`), so a line matching
// `^manifest_version:\s*(\d+)` is exactly what every real file contains --
// this is not a general-purpose YAML scalar reader and must not be reused
// as one.
std::optional<int> ParseManifestVersion(const std::vector<std::uint8_t>& yaml_bytes) {
  static const char kKey[] = "manifest_version:";
  const std::string text(reinterpret_cast<const char*>(yaml_bytes.data()), yaml_bytes.size());
  std::size_t line_start = 0;
  while (line_start < text.size()) {
    const std::size_t line_end = text.find('\n', line_start);
    const std::string line = text.substr(line_start, (line_end == std::string::npos ? text.size() : line_end) - line_start);
    line_start = (line_end == std::string::npos) ? text.size() : line_end + 1;
    if (line.rfind(kKey, 0) != 0) continue;  // must be a top-level key, not indented/nested
    std::size_t digits_start = sizeof(kKey) - 1;  // -1 for the trailing NUL
    while (digits_start < line.size() && std::isspace(static_cast<unsigned char>(line[digits_start]))) ++digits_start;
    std::size_t digits_end = digits_start;
    while (digits_end < line.size() && std::isdigit(static_cast<unsigned char>(line[digits_end]))) ++digits_end;
    if (digits_end == digits_start) return std::nullopt;  // key present, value not a bare integer
    return std::stoi(line.substr(digits_start, digits_end - digits_start));
  }
  return std::nullopt;
}

const char kTopicProvenanceMetaName[] = "topic_provenance";
// IMP-0117 (`WP-13`'s own named gap, `include/simcore/io.hpp::RawMessage::
// informational_only`): a sibling `Metadata` record per flagged message,
// written immediately beside it (never accumulated -- SW-0040/SW-0041's
// "no reordering, no accumulation" applies to bookkeeping the same as to
// payloads). Reuses the `topic_provenance` precedent one level down: mcap's
// own `metadataIndexes()` is a `std::multimap`, so many records sharing this
// one name is a supported, not a repurposed, shape.
const char kInformationalOnlyMetaName[] = "informational_only";

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

    if (message.informational_only) {
      mcap::Metadata flag;
      flag.name = kInformationalOnlyMetaName;
      flag.metadata["topic"] = message.topic;
      flag.metadata["log_time_ns"] = std::to_string(message.log_time_ns);
      (void)writer_.write(flag);
    }
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
    ReadInformationalOnly();
    DetermineCaptureTimeAwareness();
    BuildTopicIndex();
    ResetView(0);
    return Result<bool>::Ok(true);
  }

  // The index is normalised and cached ONCE, here, rather than rebuilt per
  // call: `Describe()` is called from inside the per-cycle loop
  // (`cycle_loop.cpp`'s `StepOnce`), and canonicalising there would pay for
  // the whole map on every tick. `readSummary(AllowFallbackScan)` in `Open`
  // has already established the full channel set, so there is nothing left
  // to discover later.
  std::map<std::string, TopicInfo> Describe() const override { return topics_; }

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
  // `CanonicalTopic` is applied HERE, at the reader boundary, so nothing
  // above `io` ever sees a recording's own historical spelling. Provenance
  // is looked up under the file's raw topic (that is how it was written)
  // and stored under the canonical one.
  //
  // A collision -- two raw spellings of one canonical topic in a single
  // file -- keeps the FIRST entry rather than letting the later one win
  // silently; the map is ordered, so "first" is deterministic. Such a file
  // would be malformed (the same port recorded twice under two spellings),
  // and this layer is not the right place to raise on it, but it must not
  // depend on iteration luck either.
  void BuildTopicIndex() {
    topics_.clear();
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
      topics_.emplace(CanonicalTopic(channel->topic), std::move(info));
    }
  }

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

  void ReadInformationalOnly() {
    const auto range = reader_.metadataIndexes().equal_range(kInformationalOnlyMetaName);
    for (auto it = range.first; it != range.second; ++it) {
      mcap::Record record;
      if (!mcap::McapReader::ReadRecord(*reader_.dataSource(), it->second.offset, &record).ok()) continue;
      mcap::Metadata metadata;
      if (!mcap::McapReader::ParseMetadata(record, &metadata).ok()) continue;
      const auto topic_it = metadata.metadata.find("topic");
      const auto time_it = metadata.metadata.find("log_time_ns");
      if (topic_it == metadata.metadata.end() || time_it == metadata.metadata.end()) continue;
      // Canonical key, because `Pull()` canonicalises the topic it looks up
      // with -- the two halves of this pair must be spelled the same way or
      // the flag silently never matches (F-1's own defect, one scale down).
      informational_only_.emplace(CanonicalTopic(topic_it->second), std::stoll(time_it->second));
    }
  }

  // `R-SIM-14`: whether `publishTime` means anything is a property of the
  // FILE (which writer produced it, and whether anything ever certified
  // it), not of any one message -- mirrors `io/mcap.py::RecordingReader.
  // messages`'s own `capture_aware` computation, once per `Open()`, read
  // by every `Pull()` rather than re-derived per message.
  void DetermineCaptureTimeAwareness() {
    const auto manifest_bytes = GetMeta(ToString(MetaKind::kRunManifest));
    if (!manifest_bytes.has_value()) {
      capture_time_aware_ = false;  // no manifest at all -- nothing certified publishTime
      return;
    }
    const std::optional<int> version = ParseManifestVersion(*manifest_bytes);
    capture_time_aware_ = version.has_value() && *version >= kCaptureTimeManifestVersion;
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
    // Canonical here too, not just in the index: a raw spelling that leaks
    // above `io` is exactly what let the index and the payload path disagree
    // (F-1). Everything downstream sees one form.
    msg.topic = CanonicalTopic(mv.channel->topic);
    msg.log_time_ns = static_cast<std::int64_t>(mv.message.logTime);
    // R-SIM-14: `publishTime` is trusted as a real capture stamp only for a
    // file this gate has certified capture-time-aware (`DetermineCapture
    // TimeAwareness`, once per `Open()`) -- never defaulted to reception,
    // which would manufacture an `age_s` of exactly `0.0` indistinguishable
    // from a true one.
    msg.capture_time_ns = capture_time_aware_
        ? std::optional<std::int64_t>(static_cast<std::int64_t>(mv.message.publishTime))
        : std::nullopt;
    const auto* byte_ptr = reinterpret_cast<const std::uint8_t*>(mv.message.data);
    msg.payload.assign(byte_ptr, byte_ptr + mv.message.dataSize);
    msg.informational_only = informational_only_.count({msg.topic, msg.log_time_ns}) > 0;
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
  std::set<std::pair<std::string, std::int64_t>> informational_only_;
  // Canonicalised once in `Open`; see `BuildTopicIndex`.
  std::map<std::string, TopicInfo> topics_;
  // Set once in `Open` by `DetermineCaptureTimeAwareness`; read by every
  // `Pull()`. Defaults false -- the same "unknown until certified
  // otherwise" posture `R-SIM-14` requires of every reader.
  bool capture_time_aware_ = false;
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
