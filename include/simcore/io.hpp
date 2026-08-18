// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   The `io` contract (`SI-01`, design §5): a recording is a **model**, a
///   format is a **codec** of about four read methods and four write
///   methods (R-SIM-14). Ported from `adas_sim.io.base`'s
///   `RecordingReader`/`RecordingWriter` Protocols + `io/registry.py` --
///   the shape is reusable, the language is not (`SW-0021`'s own `Now.`).
///
///   Nothing above `io` learns a format exists. A reader streams
///   (`SW-0025`): `ReadRange` returns one bounded `Batch` and never
///   materialises a whole recording -- the defect both `io/base.py` (a
///   message list) and `sil_host/src/recording_reader.cpp`
///   (`std::vector<RecordingTick> ticks_` over the whole file) share
///   (`SW-0025`'s own `Now.`).
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <filesystem>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "simcore/errors.hpp"

namespace simcore::io {

// R-SIM-12/N-5: a manufactured recording and a real one share a format,
// never an evidence grade. `kUnknown` is what a recording with no
// provenance metadata yields (SW-0039) -- never silently `kMeasured`.
enum class Provenance { kMeasured, kTruth, kMocked, kSimulated, kOverridden, kUnknown };

std::string ToString(Provenance provenance);

// SW-0038's closed set of meta-block kinds. Content is always opaque bytes
// to this layer (`io` "knows nothing of ports, modules, graphs or cycles" --
// design §5's own boundary note) -- a codec preserves an unrecognised block
// name on a round trip rather than refusing it (SW-0038's Accept), so this
// enum names the WELL-KNOWN kinds a caller can ask for by symbol; nothing
// stops a caller passing a different string key through the byte-oriented
// GetMeta/WriteMeta pair below.
enum class MetaKind { kRunManifest, kConfigBundle, kPluginIdentity, kLineage, kTolerance };

std::string ToString(MetaKind kind);

// SW-0039: a topic with no provenance block yields `kUnknown`, never a
// guessed value. `raw` is the block's own recorded string (absent when the
// codec/recording carries no provenance metadata for this topic at all).
Provenance OriginOrUnknown(const std::optional<std::string>& raw);

// SW-0022: six `bool`s, a value the registry reads without opening a file --
// never a method a codec instance could answer differently per file.
struct Capabilities {
  bool embedded_schemas = false;
  bool random_access = false;
  bool meta_blocks = false;
  bool arbitrary_topics = false;
  // False => cannot be a resim input (R-SIM-14) -- OpenRead refuses a codec
  // registered with this false (SW-0024, IMP-0024).
  bool round_trips = false;
  // A second, capture-time stamp distinct from reception (OD-9, CR-SIM-4).
  bool capture_time = false;
  bool write_only = false;
};

struct TopicInfo {
  std::string schema_name;
  Provenance provenance = Provenance::kUnknown;
  std::vector<std::uint8_t> schema_bytes;
};

// One `(topic, log_time_ns, capture_time_ns, bytes)` message (R-SIM-14's
// model). `capture_time_ns` is absent when the codec/recording predates the
// two-clock model -- never defaulted to `log_time_ns` (equality would
// manufacture a false `age_s` of `0.0`).
struct RawMessage {
  std::string topic;
  std::int64_t log_time_ns = 0;
  std::optional<std::int64_t> capture_time_ns;
  std::vector<std::uint8_t> payload;
  // SW-0033: set by `Translator::Apply` the one time a unit correction is
  // applied to this message, so a second `Apply` on the same message is
  // detectable and refused rather than silently double-converting.
  bool translated = false;
};

// SW-0026: three independent axes, whichever is reached first, each
// configurable. `0` means "this axis does not bound the batch" -- a caller
// wanting exactly one active axis leaves the other two at `0`, never a
// sentinel like `SIZE_MAX` that a reader would still have to special-case.
struct ReadBounds {
  std::size_t max_messages = 0;
  std::size_t max_bytes = 0;
  std::int64_t max_span_ns = 0;
};

enum class BatchEndReason { kCount, kBytes, kSpan, kEndOfStream };

struct Batch {
  std::vector<RawMessage> messages;
  BatchEndReason end_reason = BatchEndReason::kEndOfStream;
  // True once the underlying stream has nothing left to deliver -- the
  // caller's own loop-termination signal, distinct from `end_reason` (which
  // names why THIS batch ended, not whether another one follows).
  bool exhausted = false;
};

namespace detail {

// IMP-0025's shared implementation: "the only read entry point". Every
// codec's `Reader::ReadRange` delegates to this rather than re-implementing
// the three-axis bound logic (SW-0026) itself -- one place, checked once.
// `pull` returns the next raw message or `std::nullopt` at end of stream.
//
// `lookahead` is the codec's own single-message buffer, owned by the codec
// and threaded through by reference across `ReadRange` calls: when a
// message is pulled but does not fit the CURRENT batch (a bound already in
// force), it is stashed here rather than discarded, and is the first thing
// the NEXT call consumes. This is the one message of "ahead" state
// `pull()`'s forward-only shape needs -- peak resident memory stays the
// codec's own single-message buffer plus one `Batch` (SW-0025), never a
// whole-file container.
Batch AccumulateBatch(
    const ReadBounds& bounds, std::optional<RawMessage>& lookahead,
    const std::function<std::optional<RawMessage>()>& pull);

}  // namespace detail

// SW-0021: five pure virtuals on the read side. A concrete codec's reader
// implements exactly these and nothing else the engine calls (`final` on
// every codec, IMP-0021).
class Reader {
 public:
  virtual ~Reader() = default;

  // `Result`, never a thrown exception (`simcore`'s own convention,
  // `errors.hpp`) -- a bad path or a corrupt file is an `Environment`/
  // `Authoring` `Error`, not a `throw`.
  virtual Result<bool> Open(const std::filesystem::path& path) = 0;
  virtual std::map<std::string, TopicInfo> Describe() const = 0;
  virtual void Seek(std::int64_t log_time_ns) = 0;
  virtual Batch ReadRange(const ReadBounds& bounds) = 0;
  virtual void Close() = 0;

  // Extra beyond the five: meta-block access is common to every codec that
  // declares `meta_blocks`, so it lives on the interface rather than being
  // re-invented per codec (mirrors `io/mcap.py`'s `meta()`/
  // `config_bundle_bytes()` helpers, generalised to any declared kind).
  // `std::nullopt` when this recording carries no block of that kind.
  virtual std::optional<std::vector<std::uint8_t>> GetMeta(const std::string& kind_name) const = 0;
};

// SW-0021: four pure virtuals on the write side.
class Writer {
 public:
  virtual ~Writer() = default;

  virtual Result<bool> Open(const std::filesystem::path& path, const std::map<std::string, TopicInfo>& topics) = 0;
  // SW-0040/SW-0041: writes immediately, in call order -- no reordering, no
  // accumulation. `WriteMessage` (not the interface's own name, IMP-0041)
  // is `writer_base.cpp`'s shared entry point; `Write` is the raw per-codec
  // primitive it calls through to.
  virtual void Write(const RawMessage& message) = 0;
  virtual void WriteMeta(const std::string& kind_name, const std::vector<std::uint8_t>& bytes) = 0;
  virtual void Close() = 0;
  // Non-pure, default no-op: a codec whose own buffering needs an explicit
  // commit point (so a mid-run crash still leaves a readable file up to the
  // last completed tick, SW-0041's Accept) overrides it; one that already
  // writes through (like mcap's own writer) does not need to.
  virtual void Flush() {}
};

using ReaderFactory = std::function<std::unique_ptr<Reader>()>;
using WriterFactory = std::function<std::unique_ptr<Writer>()>;

// IMP-0040/IMP-0041: the shared write entry point -- every caller writes a
// run's output through `WriterBase::WriteMessage`, one tick at a time,
// rather than accumulating a `std::vector<RawMessage>` and writing it at
// the end (the shape `resim_runner.cpp` and `core/resim.py` shared,
// SW-0041's own `Now.`). Messages are forwarded to the wrapped `Writer` the
// moment they arrive -- input order is preserved by construction, since
// nothing here ever holds more than the one in flight (SW-0040: "no map
// iteration reaches the file"). `Flush()` is called on the same three axes
// `ReadBounds`/`AccumulateBatch` use, reusing that one bound vocabulary
// rather than inventing a second (IMP-0041).
class WriterBase {
 public:
  explicit WriterBase(Writer& writer, ReadBounds flush_bounds = ReadBounds{});

  void WriteMessage(const RawMessage& message);
  // Forces a flush regardless of the accumulated-since-last-flush counters
  // -- always safe to call, e.g. at run end just before `Close()`.
  void Flush();

 private:
  Writer& writer_;
  ReadBounds flush_bounds_;
  std::size_t pending_messages_ = 0;
  std::size_t pending_bytes_ = 0;
  std::int64_t span_start_ns_ = 0;
  bool have_span_start_ = false;
};

// SW-0023/SW-0024: extension-keyed registration and lookup, symmetric
// where capabilities allow. A second registration of one extension is an
// `Internal` error naming both (IMP-0023); `OpenRead` on a write-only
// codec, or `OpenWrite` on a read-only one, is refused by capability
// (IMP-0024), never coerced.
class CodecRegistry {
 public:
  static CodecRegistry& Instance();

  Result<bool> Register(
      const std::string& ext, Capabilities capabilities, ReaderFactory reader_factory,
      WriterFactory writer_factory = nullptr);

  Result<std::unique_ptr<Reader>> OpenRead(const std::filesystem::path& path) const;
  Result<std::unique_ptr<Writer>> OpenWrite(const std::filesystem::path& path) const;

  // SW-0022: "a value the registry can read without opening a file" --
  // queries the declared `Capabilities` for a registered extension with no
  // Reader/Writer constructed and no path touched.
  Result<Capabilities> CapabilitiesFor(const std::string& ext) const;

  // Test/tooling seam: `UT-IO-*` registers throwaway codecs against a
  // fresh registry rather than the process-wide singleton, so tests never
  // interfere with each other's extension namespace.
  CodecRegistry() = default;

 private:
  struct Entry {
    Capabilities capabilities;
    ReaderFactory reader_factory;
    WriterFactory writer_factory;
  };

  std::string RegisteredExtensions() const;

  std::map<std::string, Entry> entries_;
};

namespace codecs {

// Registers the `.mcap` codec into `registry` -- `DD-13`: MCAP is the only
// registration `WP-06` lands, proving the format-neutral contract above
// against the one format available (`SI-01`'s io/mcap library, conancenter
// mcap/1.2.0, already vendored by `sil_host`). A caller registers
// explicitly, exactly once per registry -- C++ has no import-time
// side-effect registration the way `io/mcap.py`'s module-level `register()`
// call gets for free, and relying on static-init order across translation
// units would be exactly the kind of fragility this codebase's `Result<T>`
// discipline exists to avoid.
Result<bool> RegisterMcap(CodecRegistry& registry);

}  // namespace codecs

// SW-0032/0033/0034: one resolved ingest-table row, exactly the shape the
// (not-yet-landed, `WP-12`) ingest-map parser will eventually produce from
// a `modules/<name>/sim/ingest/*.yaml` -- `Translator` takes this shape
// directly and contains no parser of its own (SW-0032's own Shall).
struct IngestRow {
  std::string raw_topic;
  std::string port;
  // `Provenance` string form (`ToString`), or empty when the map states no
  // origin -- distinct from a topic ABSENT from the table (`OriginOrUnknown`
  // returns `kUnknown` for the latter regardless of this field).
  std::string origin;
  double factor = 1.0;
  double offset = 0.0;
  // Expected schema/type name for this topic; empty means "unchecked"
  // (SW-0034 only refuses a DECLARED mismatch -- an absent expectation is
  // not evidence of one).
  std::string proto_type;
};

// SW-0032: applies a resolved ingest table and contains no parser, no
// schema and no validation for ingest-map *files* -- constructing one takes
// the already-resolved rows (today, always empty: `RunSpec::sources[].ingest`
// emits `[]` until `WP-12`'s parser lands, `IMP-0011`). Building the
// mechanism now and authoring a real table later is `IMP-0388`'s own
// precedent ("Blocked-but-not-blocking").
class Translator {
 public:
  explicit Translator(std::vector<IngestRow> rows);

  // `declared_schema_name` is the topic's own `TopicInfo::schema_name`
  // (what the codec reports it actually carries) -- SW-0034 compares it
  // against the row's `proto_type`, never against something the message's
  // bytes alone could tell us. A topic absent from the table is delivered
  // untranslated, tagged `kUnknown` (SW-0032's Accept) -- never a Result
  // failure, since "no row for this topic" is not itself an error.
  Result<RawMessage> Apply(RawMessage message, const std::string& declared_schema_name) const;

  // The resolved `Provenance` for a topic per this table -- `kUnknown` when
  // absent, matching `Apply`'s own tagging (kept as a query so a caller can
  // resolve a `TopicInfo` without also transforming a message).
  Provenance OriginFor(const std::string& raw_topic) const;

 private:
  std::map<std::string, IngestRow> by_topic_;
};

// Forward-declared so `LazyPayload<T>::Get` below can call it unqualified:
// two-phase name lookup only finds a non-dependent, non-ADL-eligible free
// function (no arguments, so no ADL) if it is declared before the template
// DEFINITION, not merely before first instantiation -- MSVC accepts the
// call either way (a known MSVC lookup laxity), which is why this compiled
// clean on every `vs2026` build and only broke the first time `simcore`
// built under GCC's strict two-phase lookup (SM-02's own live verification,
// 2026-08-18). Full declaration (with `DecodeCount`/`ResetDecodeCount`)
// stays below, where it always lived.
void BumpDecodeCount_();

// IMP-0027: `RawMessage::payload` is bytes; decoding into `T` happens at
// first structured access and is memoised per message -- extends
// `core/tick.py::PortValue`'s existing lazy-parse idea, moved to C++
// (SW-0027's own `Now.`).
template <class T>
class LazyPayload {
 public:
  using Parser = std::function<T(const std::vector<std::uint8_t>&)>;

  explicit LazyPayload(std::vector<std::uint8_t> bytes) : bytes_(std::move(bytes)) {}

  const T& Get(const Parser& parse) {
    if (!decoded_) {
      value_ = parse(bytes_);
      decoded_ = true;
      BumpDecodeCount_();
    }
    return value_;
  }

  bool decoded() const { return decoded_; }
  const std::vector<std::uint8_t>& raw() const { return bytes_; }

 private:
  std::vector<std::uint8_t> bytes_;
  T value_{};
  bool decoded_ = false;
};

// UT-IO-07's own seam ("count decodes"): a process-wide counter every
// `LazyPayload<T>::Get` bumps on first decode, regardless of `T`. Test-only
// in spirit, but not test-guarded -- a real caller measuring "did my graph
// decode an image nobody consumed" (SW-0027's Accept) needs the same
// counter, not a second one. A free function, not a template member, so its
// one definition (`decode.cpp`) serves every `LazyPayload<T>` instantiation.
// `BumpDecodeCount_` itself is forward-declared above, ahead of
// `LazyPayload` (see the note there); redeclared here only to sit beside
// its two siblings, same signature, no effect on the program.
std::size_t DecodeCount();
void ResetDecodeCount();
void BumpDecodeCount_();

}  // namespace simcore::io
