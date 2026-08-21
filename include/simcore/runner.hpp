// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `SI-06` -- `runner` (`WP-13`): the cycle loop. ONE loop, constructed
///   from the Resolved Run Spec (`SW-0109`); `Run()` reaches the run only
///   through `StepOnce()`, so a stepped run and a continuous one cannot
///   diverge (`ANL-SW-17`).
///
///   **Ported from `sil_host/src/resim_runner.cpp::RunResim` and
///   `adas_sim/core/resim.py::resim_pipeline`** -- the two existing,
///   working twins of this loop (`SW-0109`'s own `DONE.TWICE`), read
///   directly rather than reinvented, exactly the discipline `WP-09`/
///   `WP-10`/`WP-11` used. **The accumulation is deliberately NOT
///   ported:** both sources materialise the whole recording
///   (`RecordingReader::ticks()`, `list(reader.messages())`) and the whole
///   result (`TickOutputs`, `results.append`), which is the defect
///   `SW-0025`/`SW-0041` and `io.hpp`'s streaming contract exist to fix.
///   This runner holds at most one cycle's messages plus one `io::Batch`
///   at a time, and hands every produced message to `io::WriterBase` as it
///   is produced.
///
///   **Honestly out of scope this slice** (named rather than discovered by
///   failing):
///   1. **Cycle grouping is by `log_time_ns`**, the same key both ported
///      sources use -- NOT `bus::CycleReconstructor`'s recovery ladder.
///      `WP-08`'s own plan row already names the wire-level decode that
///      would feed the ladder (`t_source_ns`/`counter` out of raw payload
///      bytes) as a follow-on it did not attempt; without it the ladder has
///      nothing above rung 4 to select on, so wiring it here would change
///      the mechanism without changing the answer. Closed by that decode
///      landing.
///   2. **`informational_only` (`IMP-0117`) is set on the model, not yet on
///      the wire.** `io::RawMessage` carries the flag (beside `translated`,
///      the existing per-message producer-set bool) and every message the
///      runner writes carries it, which is what makes "per message, not per
///      file" real for anything reading through the model. Persisting it
///      through the `.mcap` codec needs a per-message metadata slot mcap
///      does not have; that is a codec design decision (`SI-01`), not a
///      runner one. Closed by a codec-level carrier being designed.
///   3. **The slice's cost claim (`ANL-SW-26`) is not measured**, because
///      the byte counter it asserts against is `IMP-0135` (`WP-15`,
///      `cost.cpp`, not started) and offset-based `Reader::Seek` is
///      `IMP-0030` (`WP-17`, `index.cpp`, not started). `Slice` seeks
///      through the EXISTING `Reader::Seek` primitive and stops at the
///      slice end -- correct, and re-assertable against the counter the
///      day it exists, with no change here.
/// @author Pavan Karimajji

#pragma once

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "simcore/bus.hpp"
#include "simcore/errors.hpp"
#include "simcore/io.hpp"
#include "simcore/module_host.hpp"
#include "simcore/mutate.hpp"
#include "simcore/runspec.hpp"
#include "simcore/scheduler.hpp"

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
  // Forced write regardless of the accumulated bounds; always safe.
  void Flush();

  static Result<CheckpointRecord> Read(const std::filesystem::path& path);

 private:
  void Write();

  std::filesystem::path path_;
  std::string run_id_;
  io::ReadBounds flush_bounds_;
  CheckpointRecord pending_;
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
// `graph/build.py` writes a decimate policy as the JSON object
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
  std::string topic;           // "/<stage>/<port>"
  std::string qualified_port;  // "<stage>.<port>"
  std::string stage;
  std::string port;
  std::string dir;  // "pro" | "req"
  RecordPolicy policy;
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
};

class Runner {
 public:
  using Options = RunnerOptions;

  // `components` is keyed by stage name and holds a NON-OWNING pointer per
  // stage the runner may execute. A stage in `mode: "measured"` or
  // `mode: "off"` has no entry -- `SW-0110`'s "shall not be executed" is
  // therefore not a runtime check the loop could forget, it is the absence
  // of anything to call. `writer` and `mutator` are both optional: a
  // read-only resim (`check/`) has no writer, and a spec with no mutations
  // needs no `Mutator`.
  //
  // `Result::Fail(Kind::Authoring)` when a `simulate` stage has no loaded
  // component, when a `measured`/`off` stage was handed one anyway, or when
  // a port's `record` policy string does not parse -- each naming the stage.
  static Result<Runner> Construct(const RunSpec& spec, scheduler::Scheduler& scheduler, bus::PortBus& bus,
                                  io::Reader& reader, std::map<std::string, module_host::Component*> components,
                                  io::WriterBase* writer = nullptr, const mutate::Mutator* mutator = nullptr,
                                  Options options = Options{});

  Runner(Runner&&) noexcept = default;
  Runner& operator=(Runner&&) noexcept = default;
  Runner(const Runner&) = delete;
  Runner& operator=(const Runner&) = delete;

  // Computed before tick 0: the injection boundary event and the seek to
  // the slice start. Idempotent; `StepOnce` calls it if a caller did not.
  Result<bool> Prepare();

  const InjectionBoundary& Boundary() const { return boundary_; }
  const std::vector<RecordedTopic>& RecordedTopics() const { return recorded_topics_; }
  const std::vector<std::string>& EventLog() const { return event_log_; }

  // ONE cycle. `ANL-SW-17`: this is the only body that advances the run --
  // `Run()` below calls it in a loop and contains no second copy of it, no
  // fast path and no mode flag reaching an alternative. A grep for a second
  // `scheduler_->Advance()` or a second `->Exec(` in
  // `src/simcore/runner/**` is that check's mechanised form.
  Result<bool> StepOnce();

  // Drives to the end of the recording or the end of the slice, whichever
  // comes first, by calling `StepOnce()` -- never by a second loop body.
  Result<RunOutcome> Run();

  bool exhausted() const { return exhausted_; }
  const RunOutcome& outcome() const { return outcome_; }
  std::optional<Divergence> FirstDivergence() const { return latch_.first(); }

  void SetCheckpoint(Checkpoint* checkpoint) { checkpoint_ = checkpoint; }

 private:
  Runner() = default;

  // Streams exactly one cycle's messages -- everything sharing the lowest
  // remaining `log_time_ns`. Never materialises more than one cycle plus
  // whatever a single `io::Batch` carried.
  bool PullCycle(std::map<std::string, RecordedMessage>& payloads_by_port, std::int64_t& log_time_ns);

  RunSpec spec_;
  scheduler::Scheduler* scheduler_ = nullptr;
  bus::PortBus* bus_ = nullptr;
  io::Reader* reader_ = nullptr;
  io::WriterBase* writer_ = nullptr;
  const mutate::Mutator* mutator_ = nullptr;
  Checkpoint* checkpoint_ = nullptr;
  Options options_;

  std::map<std::string, module_host::Component*> components_;
  std::vector<std::string> execute_stages_;  // simulate, and only simulate
  std::vector<std::string> inject_stages_;   // measured, and only measured
  std::vector<RecordedTopic> recorded_topics_;
  InjectionBoundary boundary_;
  DivergenceLatch latch_;
  RunOutcome outcome_;

  std::vector<io::RawMessage> carry_;  // at most one batch's leftover
  std::vector<std::string> event_log_;
  std::optional<std::int64_t> previous_log_time_ns_;
  bool prepared_ = false;
  bool exhausted_ = false;
  bool reader_drained_ = false;
};

}  // namespace simcore::runner
