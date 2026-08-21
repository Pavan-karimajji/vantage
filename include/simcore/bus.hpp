// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `SI-02` -- `bus` (design doc §5, `WP-07`'s slice of it): the eight-field
///   signal header, the closed `Origin` set, `Unknown<T>`, a port value's
///   derived age, bulk-array references and the port catalogue. Cycle
///   reconstruction (`CycleReconstructor`, `PortBus`) is `WP-08`/`WP-09` --
///   deliberately not declared here yet (no speculative forward-declares
///   for a class this WP does not implement).
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <cstddef>
#include <map>
#include <optional>
 
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "simcore/errors.hpp"
#include "simcore/runspec.hpp"

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

// The port value every module entry point receives. Quality/rung
// (`WP-08`, `IMP-0052`) are not fields yet -- cycle reconstruction has not
// landed, and adding them speculatively here would be a second, unused
// copy of a decision that WP hasn't made.
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

// SW-0050: the recovery ladder's own order, ascending strength -- the
// enum's declaration order IS the ladder (design skeleton's own words).
// `SourceCycleId` is currently always demoted to a weaker rung in
// practice: no source/format in this codebase supplies an out-of-band
// cycle identifier yet (`OQ-01`'s own "changing the answer makes rung 1
// inert, not wrong") -- the mechanism exists and is tested (a synthetic
// rung-1 fixture), even though no real recording exercises it today.
enum class Rung : std::uint8_t { SourceCycleId, HeaderCounter, SourceTime, ReceptionTime };
std::string ToString(Rung rung);

// SW-0052: travels on the value, never a side report -- HeaderCounter/
// SourceCycleId are identity markers (Exact); SourceTime is a time-based
// inference (Derived); ReceptionTime is the weakest available proxy
// (Approximated).
enum class Quality : std::uint8_t { Exact, Derived, Approximated };
std::string ToString(Quality quality);

// One port's message, decoded far enough to carry the ladder's own
// candidate fields. **Scope note (WP-08's own explicit first-slice
// decision, 2026-08-21):** decoding these out of raw wire bytes via
// protobuf reflection (the same technique the `.erg` codec already uses)
// is a named follow-on, not this slice -- `CycleReconstructor` below
// takes an already-decoded `PortMessage`, so the ladder/gap/repeat/
// measured-rate logic is built and tested against real behaviour before
// the wire-decode integration is attempted.
struct PortMessage {
  PortId port;
  Unknown<std::uint64_t> source_cycle_id;  // rung 1 -- format-specific, out-of-band
  Unknown<std::uint64_t> counter;          // rung 2 -- the signal header's own cycle counter
  Unknown<std::int64_t> t_source_ns;       // rung 3
  Unknown<std::int64_t> t_capture_ns;      // carried through, not itself a rung
  std::int64_t t_recv_ns = 0;              // rung 4 -- always known (the recording envelope's own stamp)
  std::vector<std::uint8_t> payload;
};

// SW-0051: a port may be forced to a WORSE rung than the ladder would
// pick naturally; never a better one than the data can support (that is
// an Authoring error, named at `Ingest` time).
struct LadderFloor {
  PortId port;
  Rung floor = Rung::ReceptionTime;
};

// SW-0053: a counter discontinuity, reported once per port per run --
// the missing cycles are never synthesised.
struct Gap {
  PortId port;
  std::uint64_t from = 0;
  std::uint64_t to = 0;
  std::uint64_t missed = 0;
};

// SW-0050's own "reported with the offending pair of stamps" -- a port
// whose source time was not monotonic, demoted for that one message.
struct Demotion {
  PortId port;
  Rung from = Rung::SourceTime;
  Rung to = Rung::ReceptionTime;
  std::int64_t previous_t_source_ns = 0;
  std::int64_t offending_t_source_ns = 0;
};

// SW-0055: a running mean/jitter for one port, compared against its
// declared period. `mismatch` is true once the measured mean falls
// outside a declared band of the declared period.
struct RateReport {
  bool has_data = false;
  double mean_period_ns = 0.0;
  double jitter_ns = 0.0;
  bool mismatch = false;
};

// SW-0049: one reconstructed cycle carries every expected port's message
// keyed by port name -- "multi-port input sets", never "one port each"
// (the exact defect this class exists to fix).
struct Cycle {
  std::map<PortId, PortMessage> ports;
};

// SW-0049/0050/0051/0053/0054/0055/0387: the per-port recovery ladder,
// counter-gap and repeat detection, and measured-rate tracking. Cross-
// port grouping (SW-0049's own fix) joins messages sharing the same
// cycle KEY -- the value the selected rung actually produced for that
// message -- never by equality of file/reception timestamps
// (`io/base.py::group_by_log_time`'s and `recording_reader.cpp`'s own
// defect, ported nowhere).
class CycleReconstructor {
 public:
  CycleReconstructor(std::vector<PortId> expected_ports, std::vector<LadderFloor> floors = {});

  // Selects this message's rung/quality per the ladder (demoted if its
  // source time is non-monotonic for this port), buckets it into the
  // cycle sharing its key, and updates gap/repeat/rate tracking.
  // `Result::Fail` only for SW-0051's Authoring case: a floor demanding a
  // rung stronger than this port's data has ever supported.
  Result<bool> Ingest(const PortMessage& msg);

  // The oldest cycle holding every expected port, in ascending key order
  // -- `std::nullopt` while any expected port is still missing from it.
  std::optional<Cycle> TakeCompleteCycle();

  Rung RungUsed(const PortId& port) const;
  Quality QualityUsed(const PortId& port) const;
  const std::vector<Gap>& Gaps() const;
  const std::vector<Demotion>& Demotions() const;
  bool IsRepeat(const PortId& port) const;
  RateReport MeasuredRate(const PortId& port, std::int64_t declared_period_ns, double band = 0.2) const;

 private:
  struct PortState {
    Rung last_rung = Rung::ReceptionTime;
    Quality last_quality = Quality::Approximated;
    bool is_repeat = false;
    Unknown<std::int64_t> last_t_source_ns;
    Unknown<std::uint64_t> last_counter;
    Unknown<std::uint64_t> last_freshness_counter;
    Unknown<std::int64_t> last_freshness_source_ns;
    Unknown<std::int64_t> last_rate_ns;
    std::size_t rate_samples = 0;
    double rate_sum_ns = 0.0;
    double rate_sum_sq_ns = 0.0;
  };

  std::vector<PortId> expected_ports_;
  std::vector<LadderFloor> floors_;
  std::map<PortId, PortState> state_;
  std::map<std::int64_t, Cycle> pending_;  // keyed by cycle key, ascending
  std::vector<Gap> gaps_;
  std::vector<Demotion> demotions_;

  const LadderFloor* FindFloor(const PortId& port) const;
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
