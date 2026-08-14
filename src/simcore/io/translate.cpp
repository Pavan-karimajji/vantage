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

Translator::Translator(std::vector<IngestRow> rows) {
  for (auto& row : rows) {
    by_topic_.emplace(row.raw_topic, std::move(row));
  }
}

Provenance Translator::OriginFor(const std::string& raw_topic) const {
  const auto it = by_topic_.find(raw_topic);
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

  const auto it = by_topic_.find(message.topic);
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

}  // namespace simcore::io
