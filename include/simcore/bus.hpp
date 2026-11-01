// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `SI-02` -- `bus` (design doc §5, `WP-07`'s slice of it): the eight-field
///   signal header, the closed `Origin` set, `Unknown<T>`, a port value's
///   derived age, bulk-array references and the port catalogue. `WP-02`
///   (VANTAGE): per-port sample buffers, the header read at the door and
///   the identity checks; the old cycle reconstructor is gone (`IMP-0010`).
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <cstddef>
#include <deque>
#include <map>
#include <optional>
 
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "simcore/errors.hpp"
#include "simcore/runspec.hpp"

namespace google::protobuf {
class Descriptor;
}  // namespace google::protobuf

namespace simcore::bus {

// A port's own declared name, e.g. "bsd.outputs" -- already qualified by
// the component's function token (R-SIM-4), never by a stage/producer
// (SW-0389). The id of the module that produced a value, or "RECORDING"
// for an injected one -- a bare string for now; nothing in WP-07 needs a
// richer type.
using PortId = std::string;
using ProducerId = std::string;

// R-SIM-10's three-value per-stage mode, carried per value so a consumer
// cannot tell `simulate` from `measured` (SW-0057's own invariant, one
// level up).
enum class Mode { Simulate, Measured, Off };

// SW-0048: six values, closed. A `switch` over this enum must never carry
// a `default:` -- ANL-SW-15 diffs this enum's names against the published
// closed set on every build, so a seventh value not caught there is caught
// here as a compiler warning/error instead.
enum class Origin { Measured, Truth, Mocked, Simulated, Overridden, Unknown };

std::string ToString(Origin origin);

// DD-05 / SW-0060: a port's cycle class. `Static` carries no cycle
// structure, no hold semantics and no age -- see `AgeForKind` below.
enum class PortKind { Data, Control, Static };

std::string ToString(PortKind kind);

// SW-0047: value-or-explicit-unknown as a type, not a convention. No
// `operator T()`, no `value_or` -- the only way out is `.value()`, which
// throws rather than hand back a plausible-looking zero (`SW-0047`'s own
// "never presented as a zero" -- a silent default would be exactly that).
template <class T>
class Unknown {
 public:
  constexpr Unknown() = default;
  constexpr Unknown(T value) : has_value_(true), value_(value) {}  // NOLINT(google-explicit-constructor)

  static constexpr Unknown None() { return Unknown(); }

  constexpr bool has_value() const { return has_value_; }

  const T& value() const {
    if (!has_value_) {
      throw std::logic_error("Unknown<T>::value() called on an unknown field");
    }
    return value_;
  }

 private:
  bool has_value_ = false;
  T value_{};
};

// A formatter, not a conversion: prints "unknown" for an absent field
// rather than a caller reaching for `.value()` unchecked.
template <class T>
std::string Format(const Unknown<T>& field) {
  if (!field.has_value()) return "unknown";
  return std::to_string(field.value());
}

// SW-0043/SW-0044/SW-0046: the eight-field signal header. Every timing
// field is an integer-nanosecond `Unknown<T>` or always-known -- no
// floating-point time quantity anywhere in this type (ANL-SW-14).
//
// `t_capture_ns` deliberately has no constructor path from reception time:
// there is no constructor here at all (Header is an aggregate), so the one
// way to set it is to name the field, and the one way to leave it unset is
// to not. Reception time is not a member of this struct on purpose -- it
// lives on `io::RawMessage::log_time_ns`, on the recording envelope, which
// is a different type than this header (SW-0044, SYS-0284): two fields one
// word apart that mean opposite things is how the defaulting SW-0044
// forbids becomes an easy mistake instead of an unwritable one.
struct Header {
  Unknown<std::int64_t> t_source_ns;    // computation time -- from the source header
  Unknown<std::uint64_t> counter;       // cycle identity
  Unknown<std::uint32_t> status;        // validity
  Unknown<std::int64_t> t_capture_ns;   // validity instant -- never defaulted to reception
  std::int64_t t_sim_ns = 0;            // delivery cycle -- always known
  ProducerId producer;                  // module id, or "RECORDING"
  Mode mode = Mode::Off;
  bool is_repeat = false;               // no new data since last cycle
};

// SW-0059: a bulk array (point cloud, image, occupancy grid) is a
// reference into the recording, resolved at consume/draw time -- never
// copied into a tick structure or a scene (R-SIM-2, ported to the bus so
// it holds before the player exists). `present=false` is the "this port
// value carries no bulk data" case, distinct from a zero-byte one.
struct BulkRef {
  std::string topic;
  std::int64_t log_time_ns = 0;
  std::int64_t bytes = 0;
  bool present = false;
};

// The declared budget a `BulkRef` itself must stay under -- the point is
// that the reference is small BY CONSTRUCTION, not merely small in
// practice. `sizeof(BulkRef)` is well under this on every supported
// platform; the budget is stated in bytes (SW-0059's Accept clause), not
// derived from `sizeof`, so a future field added to `BulkRef` fails this
// check rather than silently widening the tick structure.
inline constexpr std::size_t kBulkRefBudgetBytes = 64;

Result<bool> CheckBulkBudget(const PortId& port, std::size_t actual_bytes);

// SW-0060: a `Static`-kind port's age is a category error, not a number --
// `AgeForKind` is where that degrades to `unknown` rather than a
// fabricated value. `derived` is whatever the capture/hold derivation
// (`value.cpp`) already computed; this only overrides it for `Static`.
Unknown<std::int64_t> AgeForKind(PortKind kind, Unknown<std::int64_t> derived);

// The port value every module entry point receives.
struct PortValue {
  PortId port;
  Header header;
  Origin origin = Origin::Unknown;
  PortKind kind = PortKind::Data;
  bool updated = true;                     // false when held
  Unknown<std::int64_t> hold_ns;           // set by the bus when held (WP-09's own hold schedule)
  std::vector<std::uint8_t> payload;       // raw bytes; structured/lazy decode wiring lands with module_host (WP-10)
  BulkRef bulk;                            // never inlined (SW-0059)

  // SW-0045: derived, never stored. Capture time when known; else the
  // hold schedule; else a genuine, known zero (just produced this tick,
  // nothing to hold against) -- except for a `Static` port, where the
  // question itself does not apply (SW-0060).
  Unknown<std::int64_t> age_ns() const;
};

// `WP-02` (`VANTAGE_Architecture.md` section 3.4). The four header fields
// every sample carries, read once at the door of a port's buffer. Each is
// `Unknown` when the message has no `sig_header` (`R-IFACE-4`: an unfilled
// header is an explicit unknown, never a default). In the contract a 0
// `measurement_counter` or `source_timestamp_us` means unknown, so it is read
// as `Unknown`; a 0 `cycle_counter` or `sig_status` is a real value. The
// counters are
// `uint32` as on the wire and are compared only through
// `adas::common::counterDistance` (`RCT:SYS-0005`).
struct SignalHeader {
  Unknown<std::uint64_t> source_timestamp_us;
  Unknown<std::uint32_t> measurement_counter;
  Unknown<std::uint32_t> cycle_counter;
  Unknown<std::uint32_t> sig_status;
  bool present = false;  // the message carried a `sig_header` that parsed
};

// `IMP-0008`: reads the four fields by reflection on the field named
// `sig_header` (found by that name only) -- the only payload read behind a
// decision. A descriptor without the field, a message without it set, or
// bytes that do not parse give a header with every field `Unknown`.
SignalHeader ReadSignalHeader(const std::vector<std::uint8_t>& payload,
                              const google::protobuf::Descriptor* descriptor);

// One sample in a port's buffer: its header, the simulation time it arrived
// at, and the value (the origin and payload are on it, read through
// `origin()` and `payload()`).
struct Sample {
  SignalHeader sig;
  std::int64_t arrival_ns = 0;
  PortValue value;
  // `IMP-0019`: the step whose commit made this sample. Empty for a recorded
  // sample. A previous-cycle input takes only samples with a step before the
  // reader's own.
  std::optional<std::uint64_t> committed_step;

  Origin origin() const { return value.origin; }
  const std::vector<std::uint8_t>& payload() const { return value.payload; }
};

// What `SampleBuffer::FindByCounter` found. `eviction_miss` is true when the
// wanted counter is older than every sample still held and this buffer has
// already dropped samples -- the sample may have existed and been evicted.
struct CounterLookup {
  const Sample* sample = nullptr;
  bool eviction_miss = false;
};

// `IMP-0006`: the last `depth` samples of one port, oldest first. Never
// grows beyond `depth`; a push past it evicts the oldest. Counters are
// compared only with `counterDistance`.
class SampleBuffer {
 public:
  // A depth below 1 is held as 1: the newest sample is what `PortBus::Get`
  // answers with, so a buffer always keeps one.
  explicit SampleBuffer(std::size_t depth = 1);

  void Push(Sample sample);

  // The sample whose `measurement_counter` equals `counter`. A sample whose
  // counter is unknown never matches, and a wanted 0 (unknown) finds nothing.
  CounterLookup FindByCounter(std::uint32_t counter) const;  // counts an eviction miss, hence `mutable` below
  // The newest sample whose counter is not after `counter`. Samples with an
  // unknown counter are skipped; a wanted 0 (unknown) finds nothing.
  const Sample* NewestCounterNotAfter(std::uint32_t counter) const;
  // The newest sample that arrived at or before `time_ns` (arrival time is
  // always known).
  const Sample* NewestNotAfter(std::int64_t time_ns) const;
  // The newest sample whose `source_timestamp_us` is not after the wanted
  // one -- the key of the time rule (`ARCH` section 6). Samples with an
  // unknown source time are skipped, and a wanted 0 (unknown) finds nothing;
  // the caller then uses `NewestNotAfter` (the arrival-time half of the rule).
  const Sample* NewestSourceTimeNotAfter(std::uint64_t source_timestamp_us) const;
  const Sample* Newest() const;

  std::size_t Size() const { return samples_.size(); }
  std::size_t Depth() const { return depth_; }
  std::size_t Evicted() const { return evicted_; }
  std::size_t EvictionMisses() const { return eviction_misses_; }
  const std::deque<Sample>& Samples() const { return samples_; }

 private:
  std::size_t depth_ = 1;
  std::deque<Sample> samples_;
  std::size_t evicted_ = 0;
  mutable std::size_t eviction_misses_ = 0;
};

// `IMP-0009`: per port, what the two counters of a sample say against the
// previous one (`D17 (3)`). Reported as a returned value and as counts; the
// event log that records gaps and resets is `WP-04`'s (`IMP-0023`), and the
// badge `KIND_IDENTITY_BROKEN` is raised from `kIdentityBroken` by whoever
// owns the badge then.
enum class IdentityVerdict {
  kFirst,            // no earlier sample on this port
  kNotComparable,    // this sample's measurement_counter is unknown: it is not judged and nothing changes
  kOk,
  kCounterGap,       // measurement_counter moved forward by more than one
  kCounterReset,     // both counters went back: the sender restarted
  kIdentityBroken,   // measurement_counter went back or repeated while cycle_counter counted up
};

struct IdentityResult {
  IdentityVerdict verdict = IdentityVerdict::kFirst;
  std::int32_t measurement_distance = 0;  // counterDistance(previous, current)
  std::int32_t cycle_distance = 0;
  std::uint32_t missed = 0;               // samples skipped, for kCounterGap
};

struct IdentityCounts {
  std::size_t samples = 0;   // samples judged (known measurement_counter)
  std::size_t unknown = 0;   // samples not judged because the measurement_counter is unknown
  std::size_t gaps = 0;
  std::size_t resets = 0;
  std::size_t identity_broken = 0;
};

class IdentityTracker {
 public:
  // `content_differs` (`IMP-0050`): the caller knows this sample's bytes differ
  // from those of a sample with the same `measurement_counter`. At a
  // measurement distance of 0 that is identity broken whatever the cycle
  // counter does (`D17 (3)`); at any other distance it changes nothing.
  IdentityResult Observe(const PortId& port, const SignalHeader& header, bool content_differs = false);

  // Zero counts for a port never observed.
  IdentityCounts Counts(const PortId& port) const;
  IdentityResult Last(const PortId& port) const;

 private:
  struct PortState {
    bool has_previous = false;
    std::uint32_t measurement = 0;
    std::uint32_t cycle = 0;
    IdentityCounts counts;
    IdentityResult last;
  };
  std::map<PortId, PortState> state_;
};

// SW-0056/0057/0058 (`WP-09`): the bus buffers, held-value cache and
// buffer-budget accounting. `Publish` marks a port's fresh value for THIS
// tick; `Get` always answers -- the last real value, marked not-updated
// with the exact elapsed nanoseconds since it was produced, when nothing
// was published at `now_ns` (`SW-0056`, ported from
// `sil_host/src/pipeline.cpp::Step`'s own `lastOutput_`/`lastDueNs_`
// pair). `SetFor` is what makes `SW-0057`'s own invariant real: called
// with a stage's FULL declared port set regardless of any producer's
// due-ness or mode, so a consumer cannot tell `simulate` from `measured`
// (R-SIM-10).
// What the orchestrator knows about a sample the bus cannot: that its bytes
// differ from an earlier sample of the same counter (`IMP-0050`), and the step
// that committed it (`IMP-0019`).
struct PublishInfo {
  bool content_differs = false;
  std::optional<std::uint64_t> committed_step;
};

class PortBus {
 public:
  struct BufferStats {
    std::size_t reuse_count = 0;      // a Publish that fit inside the existing buffer's capacity
    std::size_t high_water_bytes = 0;
    std::size_t total_bytes = 0;      // current
  };

  // byte_budget: 0 means "no declared budget" (SW-0058's own wording --
  // a bus a caller never bounds is not a defect, it is a caller that
  // declared no limit).
  explicit PortBus(std::size_t byte_budget = 0);

  // SW-0058: refuses (naming the port and the budget) once total buffer
  // bytes across every port would exceed a declared budget -- the value
  // is still stored (an over-budget Publish is a reported condition, not
  // a dropped one; the scheduler decides what to do with the refusal).
  Result<bool> Publish(const PortId& port, PortValue value, std::int64_t now_ns, const PublishInfo& info = PublishInfo{});

  // SW-0056: never absent -- a port never published returns an
  // `Origin::Unknown`, `updated=false` value naming the port, not a
  // missing-key lookup a caller could forget to guard.
  PortValue Get(const PortId& port, std::int64_t now_ns) const;

  // SW-0057.
  std::vector<PortValue> SetFor(const std::vector<PortId>& declared_ports, std::int64_t now_ns) const;

  // `IMP-0007`: sizes the port's buffer by its `buffer_depth` and names the
  // message type whose `sig_header` is read for every sample entering it. A
  // null descriptor keeps the depth and reads no header. Declaring again
  // replaces the declaration and keeps no earlier sample.
  //
  // A port that is published without being declared keeps one sample and
  // reads no header. That fallback exists only so tests that default-
  // construct a `PortBus` stay unchanged; `WP-05` makes declaration
  // mandatory on the engine path.
  void DeclarePort(const PortId& port, std::int64_t buffer_depth, const google::protobuf::Descriptor* descriptor);

  // `IMP-0021`: empties every port's buffer and the identity tracker; every
  // declaration (depth, descriptor) stays.
  void ClearSamples();

  // The descriptor a port was declared with; null for an undeclared port.
  const google::protobuf::Descriptor* Descriptor(const PortId& port) const;

  // Null for a port never declared or published.
  const SampleBuffer* Buffer(const PortId& port) const;

  const IdentityTracker& Identity() const { return identity_; }

  BufferStats Stats() const { return stats_; }

 private:
  struct Slot {
    SampleBuffer buffer;
    const google::protobuf::Descriptor* descriptor = nullptr;
    std::int64_t last_produced_ns = 0;
  };

  std::map<PortId, Slot> slots_;
  IdentityTracker identity_;
  std::size_t byte_budget_ = 0;
  BufferStats stats_;
};

// SW-0388/SW-0389/SW-0390: a port's identity is its own declared name --
// never a producer/stage prefix (SW-0389) -- optionally namespaced by a
// project (`"<project>::<port>"`, SW-0390). No producer field: splitting
// a component into two must invalidate no recording, pipeline, plug-in or
// ingest map that already names this port (IMP-0389).
struct PortDecl {
  std::string name;
  std::string proto_type;
};

// SW-0388: a versioned catalogue, resolved at load -- derived, never
// authored or adopted (design `A-4`). The core set is the union of every
// stage's declared ports in the run, which is already what compiled
// (R-SIM-22): `RunSpec::stages[].ports[]` is that manifest data, by the
// time `simcore` sees it, so deriving costs nothing a second description
// would.
class PortCatalogue {
 public:
  static Result<PortCatalogue> Resolve(const RunSpec& spec);

  // SW-0388's Accept: an unresolvable port fails naming the port and
  // listing every port the catalogue does declare (R-SIM-21's own shape --
  // never a silent empty result).
  Result<const PortDecl*> Find(std::string_view qualified_name) const;

  // SW-0390: adds a project-local port after the core set. Refused,
  // naming both, if `project` collides with a core port's own name.
  Result<bool> AddProjectPort(std::string_view project, PortDecl decl);

  std::size_t Size() const;

 private:
  std::vector<PortDecl> core_;
  std::vector<PortDecl> project_;
};

}  // namespace simcore::bus
