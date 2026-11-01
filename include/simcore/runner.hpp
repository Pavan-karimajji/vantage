// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `SI-06` -- `runner`: the step loop. ONE loop, constructed from the run
///   setup (`SW-0109`); `Run()` reaches the run only through `StepOnce()`, so a
///   stepped run and a continuous one cannot diverge (`ANL-SW-17`).
///
///   **VANTAGE `c1` (`WP-05`, `IMP-0024`, `IMP-0026`..`IMP-0031`).** The cycle
///   loop of `sil_host`/`resim.py`, which grouped a recording by `log_time_ns`
///   and ran every stage on a grid, is gone with `Scheduler`. `StepOnce` is one
///   engine step (`ARCH §7`): `Orchestrator::BeginStep`; per rank
///   `NextRunnable`, `RunStage` for each ticket, `Commit`; until `EndStep`. The
///   runner never decides when a run happens or in which order: it reads the
///   recording ahead (`ReadAhead`), selects a run's inputs (`SelectInputs`,
///   `RCT:IMP-0033`), builds its control message (`ControlWriter`,
///   `RCT:IMP-0032`), calls the component (`RunStage`) and reports the outputs
///   for commit.
///
///   Named gaps, closed by a later package: header-aware `EqualOutputs`
///   (`WP-06`; here the divergence latch still compares bytes of the recorded
///   message of the same instant), threads (`WP-07`), the live measurement
///   writer (`8b`; `SetLiveMeasurement` takes a sink the writer will fill),
///   `informational_only` on the wire (the `.mcap` codec has no per-message
///   slot, `SI-01`).
/// @author Pavan Karimajji

#pragma once

#include <chrono>
#include <cstdint>
#include <deque>
#include <filesystem>
#include <functional>
#include <iosfwd>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "simcore/bus.hpp"
#include "simcore/diagnostics.hpp"
#include "simcore/errors.hpp"
#include "simcore/io.hpp"
#include "simcore/module_host.hpp"
#include "simcore/mutate.hpp"
#include "simcore/orchestrator.hpp"
#include "simcore/runspec.hpp"
#include "simcore/transport_publisher.hpp"

namespace google::protobuf {
class Descriptor;
class DescriptorPool;
}  // namespace google::protobuf

namespace simcore::runner {

// ---------------------------------------------------------------------------
// injection.cpp -- IMP-0113 / SW-0113
// ---------------------------------------------------------------------------

// One port crossing from injected data into executed code. `producer` is
// the stage the value comes FROM -- a `measured` stage's name, or the
// reserved `"source"` keyword (`R-SIM-21`'s own exemption: `source` is a
// pipeline-grammar keyword, never an authoring choice).
struct BoundaryPort {
  std::string producer;  // a measured stage's name, or "source"
  std::string producer_port;
  std::string consumer;  // the simulate stage consuming it
  std::string consumer_port;
};

// SW-0113: the set of ports crossing `measured` -> `simulate`, computed
// once from the spec and logged as ONE structured event before tick 0 --
// never per tick, which would bury the one fact this exists to state.
struct InjectionBoundary {
  std::vector<BoundaryPort> ports;
  // `WiredSourcePorts`/`_wired_source_ports`' ported twin: every port
  // referenced as `source.<port>` by a non-`off` stage.
  std::vector<std::string> source_ports;

  // The structured event line, `event=run_start` (`simcore::Event`'s closed
  // vocabulary -- no thirteenth value invented for this; the boundary is a
  // FIELD of the run's own start event, which is also where `SW-0113`'s
  // "before the first tick" is trivially true).
  std::string FormatEvent(const std::string& run_id) const;
};

InjectionBoundary ComputeInjectionBoundary(const RunSpec& spec);

// ---------------------------------------------------------------------------
// divergence.cpp -- IMP-0116/IMP-0117 / SW-0116/SW-0117
// ---------------------------------------------------------------------------

// SW-0116: the FIRST tick at which a simulated port differs from the same
// port's recorded bytes -- tick, port and magnitude.
struct Divergence {
  std::uint64_t tick_index = 0;
  std::int64_t log_time_ns = 0;
  std::string stage;
  std::string port;
  std::size_t differing_bytes = 0;  // the magnitude: differing bytes, incl. a length difference
  std::size_t simulated_bytes = 0;
  std::size_t recorded_bytes = 0;
};

// No grace by default: the honest default is that everything from the
// divergence tick onward is informational. A non-zero window is a
// deliberate, configured relaxation, never something a caller gets by
// omission (`R-SIM-8`'s "no default tolerance", one level down).
inline constexpr std::uint64_t kDefaultGraceTicks = 0;

class DivergenceLatch {
 public:
  explicit DivergenceLatch(std::uint64_t grace_ticks = kDefaultGraceTicks) : grace_ticks_(grace_ticks) {}

  // SW-0116: compares one simulated port's bytes against the recording's
  // bytes for the SAME port at the SAME tick. Latches the first difference
  // and never re-triggers -- a later tick going back into agreement does
  // not clear it, and a second, different divergence never replaces the
  // first (which is what makes the reported tick identical across re-runs).
  //
  // **Byte equality, deliberately** (`WP-13`'s own named scope boundary):
  // `SW-0116`'s Accept asks for "the magnitude", and a NUMERIC magnitude
  // beyond a declared per-field band needs a per-component tolerance table
  // (`R-SIM-24`, `modules/<name>/sim/tolerance.yaml`) that nothing in this
  // repo emits yet, plus protobuf reflection to read the field. Byte
  // difference is a real, falsifiable magnitude today; the field-level band
  // is closed by `tolerance.yaml` becoming real data.
  void Observe(std::uint64_t tick_index, std::int64_t log_time_ns, const std::string& stage,
               const std::string& port, const std::vector<std::uint8_t>& simulated,
               const std::vector<std::uint8_t>& recorded);

  bool latched() const { return first_.has_value(); }
  const std::optional<Divergence>& first() const { return first_; }
  std::uint64_t grace_ticks() const { return grace_ticks_; }

  // SW-0117: true from `divergence tick + grace_ticks` onward. False
  // forever while nothing has diverged -- a run that never diverges never
  // flags a message.
  bool InformationalOnly(std::uint64_t tick_index) const;

 private:
  std::uint64_t grace_ticks_ = kDefaultGraceTicks;
  std::optional<Divergence> first_;
};

// ---------------------------------------------------------------------------
// checkpoint.cpp -- IMP-0119 / SW-0119
// ---------------------------------------------------------------------------

// The `progress.json` payload: the LAST COMPLETED cycle, known from
// outside the process (`SW-0119` -- a run whose component segfaults never
// returns from the loop at all, so the file, not a return value, is the
// only record of how far it got). Extends
// `adas_sim/orchestrate/worker.py`'s per-RUN checkpoint to per-CYCLE.
struct CheckpointRecord {
  std::string run_id;
  std::uint64_t tick_index = 0;
  std::int64_t log_time_ns = 0;
  bool completed = false;  // false in a file written before any cycle completed

  // IMP-0224 (SW-0224): the run's first observed divergence, if any --
  // `has_divergence` is the explicit presence flag (R-SIM-25: never
  // inferred from `divergence_tick_index == 0`, which is also tick 0's own
  // real value). Mirrors `simcore::runner::Divergence`'s own fields; kept
  // as plain scalars here rather than an `std::optional<Divergence>`
  // member so this struct's shape stays exactly what the hand-rolled JSON
  // reader/writer below can round-trip with no nested-object parsing.
  bool has_divergence = false;
  std::uint64_t divergence_tick_index = 0;
  std::int64_t divergence_log_time_ns = 0;
  std::string divergence_stage;
  std::string divergence_port;
  std::size_t divergence_differing_bytes = 0;
};

class Checkpoint {
 public:
  // `flush_bounds` is `io::ReadBounds` -- the SAME three-axis bound
  // vocabulary `WriterBase` flushes on (`IMP-0041`'s own "reusing that one
  // bound vocabulary rather than inventing a second"). `max_messages` here
  // counts completed cycles; `max_span_ns` counts recording time; a zero
  // axis does not bound. A default-constructed bounds means "write every
  // cycle", which is what `UT-RUN-07` needs and what a file whose whole
  // purpose is surviving a crash should default to.
  Checkpoint(std::filesystem::path path, std::string run_id, io::ReadBounds flush_bounds = io::ReadBounds{});

  // Called AFTER a cycle has fully completed -- never before, or the file
  // would name a cycle the output does not contain. `bytes_this_cycle` is
  // the caller's own written-byte total for that cycle (`cycle_loop.cpp`'s
  // write pass) -- this class tracks no estimate of its own, matching
  // `max_bytes`'s own meaning on `io::WriterBase`.
  void RecordCompleted(std::uint64_t tick_index, std::int64_t log_time_ns, std::size_t bytes_this_cycle = 0);

  // `IMP-0139`: the exact bytes delivered to every executing stage's req
  // port this SAME cycle -- replaces the pending capture outright (never
  // merges across cycles, so a port dropped from `delivered` between two
  // calls does not linger as stale data from an earlier cycle). Written to
  // disk on `RecordCompleted`'s own flush schedule, one file per port,
  // under `<path>_input_capture/` beside `path` itself -- deliberately not
  // a second bounds axis: this data is only ever useful paired with
  // whichever cycle `progress.json` itself names, so it flushes exactly
  // when that does, never independently.
  //
  // **Call this BEFORE `RecordCompleted` for the same cycle, not after.**
  // `RecordCompleted`'s own unbounded-flush default writes synchronously
  // inside that call -- calling this afterward pairs the wrong cycle's
  // capture with `progress.json` (off by one, found live).
  void RecordInputs(const std::map<std::string, std::vector<std::uint8_t>>& delivered_this_cycle);

  // IMP-0224 (SW-0224): records the run's first observed divergence into
  // the SAME `progress.json` this class already owns -- a dedicated
  // cross-process channel already exists (`SW-0119`'s own reason for
  // being), so this is one more sticky field on it, not a second
  // mechanism. Written immediately (bypasses the bounded flush schedule
  // `RecordCompleted` uses) -- unlike a routine completed cycle, a
  // divergence is rare and worth persisting the instant it is known.
  // **Idempotent:** a second call is a silent no-op, matching
  // `DivergenceLatch`'s own "latches the first, never replaces it" --
  // the caller is expected to call this every cycle once latched (cheap,
  // since only the first call does any work).
  void RecordDivergence(const Divergence& divergence);

  // Forced write regardless of the accumulated bounds; always safe.
  void Flush();

  static Result<CheckpointRecord> Read(const std::filesystem::path& path);

  // `IMP-0139`: reads back whatever `RecordInputs` last flushed to disk --
  // the supervisor's own read half, called from a DIFFERENT process than
  // the one that wrote it (the crashed child), so this is a free function
  // over a path, never a method on a `Checkpoint` instance the supervisor
  // never constructed. Returns an empty map, never a `Result::Fail`, when
  // the directory does not exist -- "no capture available" is a normal,
  // named outcome (a crash before the first cycle completed), not an error.
  static std::map<std::string, std::vector<std::uint8_t>> ReadInputCapture(const std::filesystem::path& path);

 private:
  void Write();
  std::filesystem::path InputCaptureDir() const;

  std::filesystem::path path_;
  std::string run_id_;
  io::ReadBounds flush_bounds_;
  CheckpointRecord pending_;
  std::map<std::string, std::vector<std::uint8_t>> pending_inputs_;
  std::size_t since_flush_ = 0;
  std::size_t bytes_since_flush_ = 0;
  std::int64_t span_start_ns_ = 0;
  bool have_span_start_ = false;
};

// ---------------------------------------------------------------------------
// slice.cpp -- IMP-0120 / SW-0120
// ---------------------------------------------------------------------------

// A half-open `[start, end)` window in `log_time_ns`. Both ends optional:
// an absent `start` means "from the beginning", an absent `end` means "to
// the end of the recording". Expressed in `log_time_ns` rather than tick
// index because that is the only key the reader can SEEK on (`Reader::Seek`
// takes a `log_time_ns`); a tick-index slice would have to read from the
// start to count ticks, which is exactly the cost this exists to avoid.
struct Slice {
  std::optional<std::int64_t> start_log_time_ns;
  std::optional<std::int64_t> end_log_time_ns;

  bool bounded() const { return start_log_time_ns.has_value() || end_log_time_ns.has_value(); }
  // At or past the slice's exclusive end.
  bool PastEnd(std::int64_t log_time_ns) const;
  bool Contains(std::int64_t log_time_ns) const;
};

// Seeks `reader` to the slice start through the EXISTING `Reader::Seek`
// primitive -- never a re-implemented scan (`IMP-0030` is the offset-based
// upgrade of that same primitive, `WP-17`; this calls the interface, so it
// inherits the upgrade with no change here). A no-op for an unbounded
// start, so a caller never needs to ask whether to call it.
void SeekToSliceStart(io::Reader& reader, const Slice& slice);

// ---------------------------------------------------------------------------
// cycle_loop.cpp -- IMP-0109/0110/0112/0114/0118
// ---------------------------------------------------------------------------

struct RunOutcome {
  std::uint64_t cycles_executed = 0;
  std::int64_t last_log_time_ns = 0;
  bool exhausted = false;
  std::optional<Divergence> divergence;
};

// One resolved record policy (`R-SIM-6`, `IMP-0009`). Parsed from
// `SpecPort::record`, which is ALWAYS present (`runspec.hpp`) -- the
// engine holds no default table.
enum class RecordVerb { kFull, kExcluded, kDecimate };

struct RecordPolicy {
  RecordVerb verb = RecordVerb::kFull;
  std::int64_t decimate_n = 0;  // > 0 only for kDecimate
  bool WritesAt(std::uint64_t tick_index) const;
};

// `full` | `excluded` | `decimate:<n>` (also accepted: `decimate <n>`).
// Anything else is an `Authoring` error naming the string and the port --
// never a silent fallback to `full`, which would make an unreadable policy
// indistinguishable from a declared complete one (`R-SIM-6`'s whole point).
//
// **Known, named limitation, belonging to `IMP-0009`/`load.cpp`, not here:**
// `graph/pipeline.py` writes a decimate policy as the JSON object
// `{"decimate": n}`, and `runspec/load.cpp` reads `record` as a bare
// `std::string`, so the object form does not survive into `SpecPort::record`
// today. The string form above is what a C++-side spec can express; widening
// `load.cpp` is a one-line follow-up for whichever pass next edits it.
Result<RecordPolicy> ParseRecordPolicy(const std::string& raw, const std::string& where);

// One declared topic the recorder writes this run -- DERIVED from
// `RunSpec::stages[].ports[]` (`SW-0114`), never a hand-maintained list,
// which is what makes *"did we record everything the SUT reads?"* true by
// construction rather than by review.
struct RecordedTopic {
  // The topic actually written. For a `pro` port this is the producing
  // stage's own address. For a WIRED `req` port it is the **producing**
  // address (`/source/gen_object_list`), not the consuming one
  // (`/df/objects`) -- see `RecordedTopicFor` for why. An unwired `req`
  // port has no producer to name and keeps the consuming address.
  std::string topic;
  std::string qualified_port;  // "<stage>.<port>" -- always the CONSUMING address; the value-lookup key
  std::string stage;
  std::string port;
  std::string dir;  // "pro" | "req"
  RecordPolicy policy;
  // `true` only for the extra `req` entry emitted when a declared mutation
  // touches this port (`R-SIM-15`). It carries the POST-mutation bytes
  // actually delivered to the component, under the consuming address, and
  // is tagged `overridden` in the topic index -- so the producing topic
  // above keeps the source's own true bytes and neither is lost. Never
  // emitted when nothing overrides the port.
  bool post_mutation = false;
};

// One recorded port's bytes for one cycle, as pulled off the reader --
// `capture_time_ns` travels alongside the payload (rather than being
// dropped at this boundary) so a `measured`/`source`-fed publish can set
// `bus::PortValue::header.t_capture_ns` from the recording's own real
// capture stamp instead of leaving it unknown (`R-SIM-14`'s two-clock
// model: never defaulted to reception, but also never silently discarded
// when the recording actually carried one).
struct RecordedMessage {
  std::vector<std::uint8_t> payload;
  std::optional<std::int64_t> capture_time_ns;
};

// The topic <-> qualified-port-name transform, the C++ twin of
// `core/resim.py::_topic_to_port_name`/`_port_name_to_topic` (private
// one-liners there, for the same reason they are free functions here).
std::string TopicToPortName(const std::string& topic);
std::string PortNameToTopic(const std::string& qualified_port);

// `"<producer>.<producer_port>"` for a stage's declared input, read off
// `RunSpec::stages[].inputs`; `std::nullopt` when that input is unwired
// (a declared-optional port nobody connected, e.g. df's `vehSig`).
std::optional<std::string> ProducerAddressOf(
    const RunSpec& spec, const std::string& stage, const std::string& port);

// True when some declared `RunSpec::mutations` entry addresses exactly this
// producing port. Deliberately reads the SPEC rather than a live `Mutator`,
// so the recorder's topic index (built before any component loads) and the
// cycle loop (which has a `Mutator`) cannot answer it differently.
bool MutationTouches(const RunSpec& spec, const std::string& stage, const std::string& port);

// **The one derivation of "which topic does this declared port get recorded
// under"**, shared by `Runner::Construct` (which writes the messages) and
// `BuildOutputTopics` (which writes the index). They used to derive it
// separately; an index and a message stream that disagree about a topic's
// name is F-1's defect one level up, so there is now a single answer.
//
// A `req` port is recorded under its PRODUCING address. Recording it under
// the consuming stage's name -- what this did until 2026-08-28 -- means the
// producing names are absent from the result, so the recording can be
// replayed but never re-simulated: a `simulate` stage's inputs would have to
// name `df.objects`, and `df -> df` is rejected as a zero-delay cycle. That
// is one cut point, from a file `R-SIM-6` says exists precisely so that
// "a recording containing every stage's outputs supports any cut point".
std::string RecordedTopicFor(
    const RunSpec& spec, const std::string& stage, const std::string& port, const std::string& dir);

// ---------------------------------------------------------------------------
// read_ahead.cpp -- IMP-0026 (WP-05)
// ---------------------------------------------------------------------------

// One recorded message read ahead, with the port its topic names and the
// index of the `sources[]` file it came from.
struct AheadMessage {
  std::string port;  // "<producer>.<port>"
  std::size_t source_index = 0;
  io::RawMessage message;
};

// All the messages of one reception time, `sources[]` order then file order.
struct AheadInstant {
  std::int64_t time_ns = 0;
  std::vector<AheadMessage> messages;
};

// `IMP-0026`: every `sources[]` file read through `io::Reader::ReadRange`,
// merged by reception time then `sources[]` order, as far as the readiness
// limit past the instant being processed. `Find` searches by
// `measurement_counter`; the time rule never calls it.
class ReadAhead {
 public:
  // `bounds` bounds ONE `ReadRange` batch; all zeros reads a default batch.
  explicit ReadAhead(std::vector<io::Reader*> readers, io::ReadBounds bounds = io::ReadBounds{});

  // Bytes read before the counter was attached are reported to it at once.
  void SetByteCounter(diagnostics::ByteCounter* byte_counter);

  // Reads until `instants` + 1 distinct reception times are held (the last may
  // be incomplete) or every reader is drained.
  void Fill(std::size_t instants);

  // True once every reader has nothing more to deliver.
  bool Drained() const { return drained_; }
  bool Empty() const { return instants_.empty(); }
  std::size_t Instants() const { return instants_.size(); }
  // The first instant holds all its messages: a later instant was seen, or
  // nothing more will come.
  bool FrontComplete() const { return !instants_.empty() && (instants_.size() > 1 || drained_); }
  const AheadInstant* Front() const { return instants_.empty() ? nullptr : &instants_.front(); }
  AheadInstant TakeFront();

  // The message on `port` whose `measurement_counter` is `counter`, read with
  // `descriptor`; null when none is held. Counters are compared only by
  // `counterDistance` (`RCT:SYS-0005`).
  const AheadMessage* Find(const std::string& port, std::uint32_t counter,
                           const google::protobuf::Descriptor* descriptor) const;
  // Every held message on `port`, oldest first.
  std::vector<const AheadMessage*> OnPort(const std::string& port) const;

  // Drops everything held, seeks every reader to `to_ns`, and skips what a
  // codec without a real `Seek` still delivers before it.
  void Seek(std::int64_t to_ns);
  // Drops everything held and reads no more (the slice end).
  void Stop();

  // The reception time of the first and of the latest message read.
  std::optional<std::int64_t> FirstTimeNs() const { return first_time_ns_; }
  std::optional<std::int64_t> LastTimeNs() const { return last_time_ns_; }

 private:
  void Refill(std::size_t reader);

  std::vector<io::Reader*> readers_;
  io::ReadBounds bounds_;
  diagnostics::ByteCounter* byte_counter_ = nullptr;
  std::map<std::string, std::size_t> read_before_counter_;
  std::vector<std::deque<io::RawMessage>> carry_;
  std::vector<bool> reader_drained_;
  std::deque<AheadInstant> instants_;
  bool drained_ = false;
  std::optional<std::int64_t> floor_ns_;
  std::optional<std::int64_t> first_time_ns_;
  std::optional<std::int64_t> last_time_ns_;
};

// The recorded messages of the ports a `simulate` stage re-produces
// (`refSync`, `compState`, data outputs), kept to select inputs by the
// recorded refSync and to compare simulated outputs with. They never enter the
// sample buffers: the buffers hold what the engine itself produced.
class RecordedReference {
 public:
  void Declare(const std::string& port, std::size_t depth, const google::protobuf::Descriptor* descriptor);
  bool Declared(const std::string& port) const { return held_.count(port) != 0; }
  void Add(const std::string& port, std::int64_t time_ns, const std::vector<std::uint8_t>& payload);
  // The newest held payload on `port` with this `measurement_counter`.
  const std::vector<std::uint8_t>* Find(const std::string& port, std::uint32_t counter) const;
  // The payload on `port` received at exactly `time_ns`.
  const std::vector<std::uint8_t>* AtTime(const std::string& port, std::int64_t time_ns) const;
  void Clear();

 private:
  struct Held {
    std::int64_t time_ns = 0;
    std::vector<std::uint8_t> payload;
    bus::Unknown<std::uint32_t> counter;
  };
  struct Port {
    std::size_t depth = 1;
    const google::protobuf::Descriptor* descriptor = nullptr;
    std::deque<Held> held;
  };
  std::map<std::string, Port> held_;
};

// ---------------------------------------------------------------------------
// select_inputs.cpp -- RCT:IMP-0033 (WP-05)
// ---------------------------------------------------------------------------

// One declared data input of a stage, as the runner hands it over.
struct InputSelection {
  std::string port;           // the stage's input name
  std::string producer_port;  // "<producer>.<port>"; empty when the input is unwired
  bool offered = true;        // false: nothing is handed over for this input
  std::optional<bus::Sample> sample;  // empty: an empty input
  bool fallback = false;           // KIND_FALLBACK
  bool readiness_timeout = false;  // KIND_READINESS_TIMEOUT
  bool eviction_miss = false;      // the wanted sample may have been evicted
  // The counter fallback's numbers (`D18 (1)`); `beyond_gap` when the best
  // sample was too far and the time rule picked instead.
  bool beyond_gap = false;
  std::optional<std::int64_t> wanted;
  std::optional<std::int64_t> found;
  std::optional<std::int64_t> gap;
};

struct Selection {
  std::vector<InputSelection> inputs;  // manifest order
  // A named sample from a `simulate` producer is not committed yet: the
  // orchestrator parks the ticket (`ARCH §6` rule 5).
  bool not_ready = false;
  std::string waiting_on;  // the producer port
};

struct SelectContext {
  const RunSpec* spec = nullptr;
  const SpecStage* stage = nullptr;
  const bus::PortBus* bus = nullptr;
  const RecordedReference* reference = nullptr;
  const ReadAhead* ahead = nullptr;
  const std::map<std::string, bus::Origin>* origins = nullptr;
  std::int64_t fallback_max_gap = 0;
  std::int64_t now_ns = 0;
  std::uint64_t step = 0;
};

// `ARCH §6`: runs when a ticket is dispatched, for every declared data input
// of the stage in manifest order. `header` is the control's: the recorded
// refSync entry is the one whose `measurement_counter` equals it. A pure
// function of the buffers, the read-ahead and the ticket: it logs and raises
// nothing; the caller does, from the fields of `Selection`.
Selection SelectInputs(const SelectContext& context, const orchestrator::Ticket& ticket,
                       const orchestrator::ControlHeader& header);

// ---------------------------------------------------------------------------
// run_stage.cpp -- IMP-0027 (WP-05)
// ---------------------------------------------------------------------------

using ExecFn = std::function<Result<module_host::PortMap>(std::int64_t dt_ns, const module_host::PortMap& inputs,
                                                          const module_host::InputMetaMap& input_meta)>;

struct RunStageArgs {
  const SpecStage* stage = nullptr;
  const orchestrator::Ticket* ticket = nullptr;
  const Selection* selection = nullptr;
  std::vector<std::uint8_t> control;  // empty: the stage declares no `control` input
  const bus::PortBus* bus = nullptr;  // the descriptors of the stage's outputs
  const mutate::Mutator* mutator = nullptr;
  std::int64_t now_ns = 0;
  std::int64_t dt_ns = 0;  // simulation time since this stage's previous run; 0 for its first
  // The control's `measurement_counter`; empty when unknown.
  std::optional<std::uint32_t> control_counter;
};

struct RunStageResult {
  orchestrator::CommitReport report;                   // the stage's updated outputs, for `Commit`
  std::map<std::string, bus::PortValue> delivered;     // "<stage>.<port>" -> exactly what the component was handed
  std::vector<orchestrator::LogEntry> entries;         // `output_counter_break` (step left for the caller to fill)
};

// `IMP-0027`: builds the port set from the control and the selection (an
// input with no sample is handed over empty, an unwired input is not offered),
// applies the declared overrides, calls `exec`, and reports each output whose
// `measurement_counter` differs from the control's. Never retries: an error
// from `exec` is returned as it came.
Result<RunStageResult> RunStage(const RunStageArgs& args, const ExecFn& exec);

// ---------------------------------------------------------------------------
// The step tap (IMP-0030)
// ---------------------------------------------------------------------------

enum class BadgeKind { kFallback, kReadinessTimeout, kIdentityBroken, kComputedNotConsumed, kWarmingUp };

// `MeasBadge.Kind`'s names: `KIND_FALLBACK` and so on.
const char* ToString(BadgeKind kind);

struct StepBadge {
  BadgeKind kind = BadgeKind::kFallback;
  std::string subject;       // the stage or port it is about
  std::uint64_t count = 0;   // since the engine run started
};

struct StepValue {
  std::string port;
  const std::vector<std::uint8_t>* payload = nullptr;  // valid during the call
  bus::Origin origin = bus::Origin::Unknown;
  std::optional<std::int64_t> age_ns;
};

struct StepReport {
  std::uint64_t step = 0;
  std::int64_t sim_time_ns = 0;
  std::vector<StepValue> values;   // every declared port with a sample
  std::vector<StepBadge> badges;   // every badge with a count above 0
};

// What the live measurement writer's `liveMeasStep` call fills (`ARCH §10.1`).
class LiveMeasSink {
 public:
  virtual ~LiveMeasSink() = default;
  virtual void OnStep(const StepReport& report) = 0;
};

// Declared OUTSIDE `Runner` (and aliased back in as `Runner::Options`)
// because a nested class's default member initialisers are not complete
// until its enclosing class is, so `Options options = Options{}` as a
// default argument on a member of `Runner` is ill-formed -- GCC rejects it
// outright (MSVC accepts it, the same two-phase asymmetry `io.hpp`'s own
// `BumpDecodeCount_` note records).
struct RunnerOptions {
  // Bound on ONE reader batch -- never on the run. Default (all zeros)
  // means the codec's own end-of-stream is the only bound, which is
  // still streaming: `AccumulateBatch` hands back one batch, not a file.
  io::ReadBounds read_bounds;
  Slice slice;
  std::uint64_t grace_ticks = kDefaultGraceTicks;
  std::optional<std::chrono::milliseconds> exec_timeout;
  // `Construct` prints `PlanText` here when set. `simEngineCreate` prints it
  // itself, before any library loads.
  std::ostream* plan_out = nullptr;
};

// `IMP-0028`: what is decided from the run setup and the recording's topic
// index alone, before any library loads.
struct PreflightResult {
  orchestrator::Graph graph;
  std::string plan_text;  // `PlanText`
};

class Runner {
 public:
  using Options = RunnerOptions;

  // `IMP-0028`: builds the graph and the ranks, checks every `simulate` stage
  // has exactly one start (`BuildGraph`), and refuses a `measured` stage
  // whose outputs the topic index lacks, naming the stage and the ports. A
  // pure function: it loads nothing and opens nothing.
  static Result<PreflightResult> Preflight(const RunSpec& spec, const std::set<std::string>& topic_index);

  // `components` is keyed by stage name and holds a NON-OWNING pointer per
  // `simulate` stage; a stage in `mode: "measured"` or `"off"` has none.
  // `readers` holds one reader per `sources[]` entry, in order; together they
  // are one recording. Every port the run publishes on is declared on `bus`
  // here, from the setup. `pool` resolves each port's message type (a null
  // pool, or a type it lacks, declares the port with no header).
  //
  // `Result::Fail(Kind::Authoring)` for everything `Preflight` refuses, when a
  // `simulate` stage has no loaded component, when a `measured`/`off` stage
  // was handed one anyway, or when a record policy string does not parse.
  static Result<Runner> Construct(const RunSpec& spec, bus::PortBus& bus, std::vector<io::Reader*> readers,
                                  std::map<std::string, module_host::Component*> components,
                                  const google::protobuf::DescriptorPool* pool = nullptr,
                                  io::WriterBase* writer = nullptr, const mutate::Mutator* mutator = nullptr,
                                  Options options = Options{});

  Runner(Runner&&) noexcept;
  Runner& operator=(Runner&&) noexcept;
  Runner(const Runner&) = delete;
  Runner& operator=(const Runner&) = delete;
  ~Runner();

  // The seek to the slice start. Idempotent; `StepOnce` calls it if a caller did not.
  Result<bool> Prepare();

  const InjectionBoundary& Boundary() const { return boundary_; }
  const std::vector<RecordedTopic>& RecordedTopics() const { return recorded_topics_; }
  // The `event=run_start` line (`SW-0113`); it is not an event log entry.
  std::string BoundaryLine() const;
  // The event log's lines so far (`orchestrator::EventLog`).
  const std::vector<std::string>& EventLogLines() const;

  // ONE engine step (`ARCH §7`). `ANL-SW-17`: this is the only body that
  // advances the run -- `Run()` calls it in a loop and has no second copy of
  // it. Ok(false): no step was left to run.
  Result<bool> StepOnce();

  // Drives to the end of the recording or the end of the slice by calling
  // `StepOnce()` -- never by a second loop body.
  Result<RunOutcome> Run();

  // `simEngineSeek`: the engine is moved to `to_ns` (`Orchestrator::Jump`).
  Result<bool> Seek(std::int64_t to_ns);

  bool exhausted() const { return exhausted_; }
  const RunOutcome& outcome() const { return outcome_; }
  std::optional<Divergence> FirstDivergence() const { return latch_.first(); }

  void SetCheckpoint(Checkpoint* checkpoint) { checkpoint_ = checkpoint; }

  // `IMP-0135`: optional; `ReadAhead` is the one place bytes are read off the wire.
  void SetByteCounter(diagnostics::ByteCounter* byte_counter);

  // `SI-25` `transport`: optional; every value written this step is handed to
  // the publisher, keyed by the step number. Retired with the live
  // measurement writer (8b).
  void SetTransportPublisher(transport::TransportPublisher* publisher) { transport_publisher_ = publisher; }

  // `IMP-0030`: the sink the live measurement writer's `liveMeasStep` call
  // fills (`ARCH §10.1`). After each step it gets the step number, the
  // simulation time, every port value with origin and age, and the step's
  // badges. With no sink, nothing is built.
  void SetLiveMeasurement(LiveMeasSink* sink) { live_sink_ = sink; }

 private:
  Runner();
  struct Impl;

  void TopUp();
  Result<bool> RunTicket(const orchestrator::Ticket& ticket, std::vector<orchestrator::CommitReport>& reports);
  // Offers this step's values to the writer, the publisher; returns the bytes written.
  Result<std::size_t> WriteStep(std::uint64_t step, std::int64_t now_ns);

  std::unique_ptr<Impl> impl_;
  bus::PortBus* bus_ = nullptr;
  io::WriterBase* writer_ = nullptr;
  const mutate::Mutator* mutator_ = nullptr;
  Checkpoint* checkpoint_ = nullptr;
  transport::TransportPublisher* transport_publisher_ = nullptr;
  LiveMeasSink* live_sink_ = nullptr;
  Options options_;

  std::map<std::string, module_host::Component*> components_;
  std::vector<RecordedTopic> recorded_topics_;
  InjectionBoundary boundary_;
  DivergenceLatch latch_;
  RunOutcome outcome_;

  bool prepared_ = false;
  bool exhausted_ = false;
};

}  // namespace simcore::runner
