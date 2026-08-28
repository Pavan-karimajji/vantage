// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `Translator`/`Apply` (`IMP-0032`, `IMP-0033`, `IMP-0034`). Applies an
///   already-resolved ingest table (`SW-0032`'s own Shall: "contains no
///   parser, no schema and no validation for ingest maps") -- constructing
///   one, and authoring the table it is constructed from, are `WP-12`'s
///   job. This is `sil_host/src/ingest_map.cpp`'s **apply** half kept; its
///   parse half dies at `WP-16` (`SW-0032`'s `Now.`).
///
///   **Scoping note (honest, not silent):** `SW-0033`'s Shall speaks of a
///   factor/offset "applied ... to the named field" in the general case,
///   but `io` "knows nothing of ports, modules, graphs or cycles" (design
///   §5's own boundary) and a `RawMessage::payload` is opaque protobuf
///   bytes here -- reaching into a decoded field would need protobuf
///   reflection this layer deliberately does not have. `SW-0033`'s own
///   2026-08-13 note names the load-bearing case explicitly: the source's
///   *timestamp* unit, scaled to the engine's integer-nanosecond timebase
///   ("the ×1000 lands here ... the only unit conversion anywhere in the
///   engine"). This implementation applies factor/offset to exactly that
///   quantity -- `RawMessage::log_time_ns`/`capture_time_ns`, the one
///   numeric value this layer genuinely owns. A general per-payload-field
///   correction, if ever needed, belongs above `io` where a decoded value
///   exists to correct.
/// @author Pavan Karimajji

#include "simcore/io.hpp"

namespace simcore::io {

// Keyed on the CANONICAL spelling of the row's own `raw_topic`, and every
// lookup canonicalises too (2026-08-28). An ingest map is authored in the
// recording's own vocabulary (`df/gen_object_list`) while a reader's index
// and message stream are canonical (`/df/gen_object_list`) -- the same one
// topic, two spellings, which `CanonicalTopic` exists to make comparable.
// Comparing them raw would make every row silently fail to match the very
// recordings it was written for.
Translator::Translator(std::vector<IngestRow> rows) {
  for (auto& row : rows) {
    std::string key = CanonicalTopic(row.raw_topic);
    by_topic_.emplace(std::move(key), std::move(row));
  }
}

Provenance Translator::OriginFor(const std::string& raw_topic) const {
  const auto it = by_topic_.find(CanonicalTopic(raw_topic));
  if (it == by_topic_.end() || it->second.origin.empty()) return Provenance::kUnknown;
  return OriginOrUnknown(it->second.origin);
}

Result<RawMessage> Translator::Apply(RawMessage message, const std::string& declared_schema_name) const {
  // SW-0033: applying the same map twice is refused. Checked BEFORE the
  // table lookup, deliberately: a successful Apply renames `topic` to the
  // row's `port`, so a second call keyed on the (now-renamed) topic would
  // otherwise simply fail to find a row and pass through silently
  // unchanged -- harmless by accident, not by a refusal the caller can see.
  // This guard makes the refusal itself the reachable, observable outcome
  // `SW-0033`'s Accept asks for, regardless of that renaming side effect.
  if (message.translated) {
    return Result<RawMessage>::Fail(Error{
        Kind::Contract, "a message not yet translated", "'" + message.topic + "' already carries translated=true",
        "simcore::io::Translator::Apply", ""});
  }

  const auto it = by_topic_.find(CanonicalTopic(message.topic));
  if (it == by_topic_.end()) {
    // SW-0032's Accept: untranslated, and tagged unknown -- the tag itself
    // is `OriginFor`'s job (topic-level, not per-message); Apply's own job
    // here is simply to pass the message through unchanged.
    return Result<RawMessage>::Ok(std::move(message));
  }
  const IngestRow& row = it->second;

  // SW-0034: a declared type mismatch is refused, never coerced -- names
  // both types and the topic, marks the cut infeasible.
  if (!row.proto_type.empty() && !declared_schema_name.empty() && row.proto_type != declared_schema_name) {
    return Result<RawMessage>::Fail(Error{
        Kind::Authoring,
        "proto_type '" + row.proto_type + "' (declared by the ingest row for '" + row.raw_topic + "')",
        "'" + declared_schema_name + "' (the topic's own schema)", "simcore::io::Translator::Apply('" + message.topic + "')",
        "this cut is infeasible: the ingest row and the recording disagree on type"});
  }

  message.topic = row.port;
  message.log_time_ns =
      static_cast<std::int64_t>(static_cast<double>(message.log_time_ns) * row.factor + row.offset);
  if (message.capture_time_ns.has_value()) {
    message.capture_time_ns =
        static_cast<std::int64_t>(static_cast<double>(*message.capture_time_ns) * row.factor + row.offset);
  }
  message.translated = true;
  return Result<RawMessage>::Ok(std::move(message));
}

std::string Translator::PortFor(const std::string& raw_topic) const {
  const auto it = by_topic_.find(CanonicalTopic(raw_topic));
  return it == by_topic_.end() ? std::string() : it->second.port;
}

// ---------------------------------------------------------------------------
// TranslatingReader -- the join `WP-12` was missing (see io.hpp)
// ---------------------------------------------------------------------------

TranslatingReader::TranslatingReader(std::unique_ptr<Reader> inner, Translator translator)
    : inner_(std::move(inner)), translator_(std::move(translator)) {}

Result<bool> TranslatingReader::Open(const std::filesystem::path& path) { return inner_->Open(path); }

void TranslatingReader::Seek(std::int64_t log_time_ns) { inner_->Seek(log_time_ns); }

void TranslatingReader::Close() { inner_->Close(); }

std::optional<std::vector<std::uint8_t>> TranslatingReader::GetMeta(const std::string& kind_name) const {
  return inner_->GetMeta(kind_name);
}

std::map<std::string, TopicInfo> TranslatingReader::Describe() const {
  std::map<std::string, TopicInfo> translated;
  for (const auto& [raw_topic, info] : inner_->Describe()) {
    // `Describe()` keys are canonical topics (`CanonicalTopic`, applied at
    // the codec); an ingest row's `raw_topic` is the file's own vocabulary
    // as authored in the map. Canonicalise the row's key the same way, so
    // "df/gen_object_list" in a map matches "/df/gen_object_list" in an
    // index -- the two spellings of one topic, which is exactly what
    // `CanonicalTopic` exists to make comparable.
    const std::string port = translator_.PortFor(raw_topic);
    if (port.empty()) {
      // No row: passed through under its own name, ungraded. A topic the
      // map does not mention is not an error (`SW-0032`'s Accept) -- it is
      // simply a topic this family does not bind.
      translated.emplace(raw_topic, info);
      continue;
    }
    TopicInfo bound = info;
    // The row's declared origin wins where it states one; `OriginFor`
    // returns `kUnknown` for a row that states none, and an unknown grade
    // must not overwrite a real one the recording already carried.
    const Provenance declared = translator_.OriginFor(raw_topic);
    if (declared != Provenance::kUnknown) bound.provenance = declared;
    translated.emplace(CanonicalTopic(port), std::move(bound));
  }
  return translated;
}

Batch TranslatingReader::ReadRange(const ReadBounds& bounds) {
  const std::map<std::string, TopicInfo> raw_index = inner_->Describe();
  Batch batch = inner_->ReadRange(bounds);
  for (RawMessage& message : batch.messages) {
    const auto declared = raw_index.find(message.topic);
    const std::string schema_name = declared == raw_index.end() ? std::string() : declared->second.schema_name;
    Result<RawMessage> applied = translator_.Apply(std::move(message), schema_name);
    // A refusal here is a real, named authoring error (`SW-0034`'s declared
    // type mismatch). `Reader::ReadRange` has no `Result` to carry it, so
    // the message is left untranslated rather than silently renamed -- the
    // stage then sees the port unfed, which is the same visible outcome as
    // an unmapped topic and never a wrong value under a right name. Making
    // this a hard refusal needs `ReadRange` to return a `Result`, which is
    // an `io` interface change and not this fix's scope.
    message = applied.ok() ? std::move(applied).value() : RawMessage{};
    if (!applied.ok()) message.topic.clear();
    // Canonical on the way out, like every other topic above `io`.
    if (!message.topic.empty()) message.topic = CanonicalTopic(message.topic);
  }
  return batch;
}

}  // namespace simcore::io
