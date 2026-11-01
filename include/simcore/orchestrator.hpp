// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The orchestrator's parts (`VANTAGE_Architecture.md` §3.2, §5, §11;
///   `IMP-0011`..`IMP-0015`). This slice (`WP-03`) builds the graph, the
///   ranks, the start check and the plan text -- all of it pure functions of
///   the `RunSpec` (and, for the start check, the recording's topic index):
///   no library is loaded, no file opened, nothing executed.
///
///   `WP-04` (`IMP-0016`..`IMP-0023`, `IMP-0050`) adds the run-time parts:
///   `EventQueue`, `Orchestrator` (`BeginStep`, `NextRunnable`, `Commit`,
///   `EndStep`, `Jump`), `Readiness` and `EventLog`. They call no component,
///   open no file and read no wall clock; the runner feeds them recorded
///   messages and reports each run's outputs.
///
///   `WP-05` wires them: `Runner::Preflight` calls `BuildGraph` and `PlanText`
///   before any library loads, and `Runner::StepOnce` drives the
///   `Orchestrator` (`IMP-0028`, `IMP-0029`). `ControlWriter` (`RCT:IMP-0032`)
///   writes the control message of a run.
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <functional>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "simcore/bus.hpp"
#include "simcore/errors.hpp"
#include "simcore/runspec.hpp"

namespace google::protobuf {
class Descriptor;
}  // namespace google::protobuf

namespace simcore::orchestrator {

// How a `simulate` stage is started (rule 3): exactly one of the three.
enum class StartKind {
  kControl,  // `trigger: control` -- the stage's recorded control message
  kInput,    // `trigger: <input port>` -- a new `measurement_counter` on that input
  kClock,    // `clock_period_ns` above 0
};

// One wiring edge: `producer.producer_port` feeds `consumer.consumer_port`.
struct GraphEdge {
  std::string producer;
  std::string producer_port;
  std::string consumer;
  std::string consumer_port;
};

// One `simulate` stage, in the setup's declaration order.
struct GraphStage {
  std::string name;
  int rank = 0;  // 1 + the highest rank among the simulated stages it reads; 1 if none (§2.2)
  StartKind start = StartKind::kClock;
  std::string trigger_input;          // the port, for `StartKind::kInput`
  std::int64_t clock_period_ns = 0;   // for `StartKind::kClock`
  // `IMP-0014`: declared consumers exist and none of them is `simulate`; the
  // orchestrator raises `KIND_COMPUTED_NOT_CONSUMED` on it, once.
  bool computed_not_consumed = false;
};

struct Graph {
  std::vector<GraphStage> stages;  // `simulate` stages only, declaration order
  // Edges from a `simulate` producer to a `simulate` consumer, never a
  // `previous_cycle` input. These are the only edges that give rank.
  std::vector<GraphEdge> edges;
  // Every `previous_cycle` input of a `simulate` stage, whatever its producer.
  std::vector<GraphEdge> previous_cycle_inputs;

  // nullptr when `name` is not a `simulate` stage of this graph.
  const GraphStage* Find(const std::string& name) const;
};

// `IMP-0012`, `IMP-0013`, `IMP-0014`. Builds the graph from the wiring, ranks
// it, and checks every `simulate` stage has exactly one start. A load error
// (Kind::Authoring) names the loop's stages (rules 1, 2), or the stage and
// what was expected (rule 3). `recorded_topics` is the recording's topic index
// (`Reader::Describe()` keys); `<stage>.control` is looked up in it.
Result<Graph> BuildGraph(const RunSpec& spec, const std::set<std::string>& recorded_topics);

// `IMP-0012`: fills `GraphStage::rank` from `edges`, or fails naming the stages
// of a loop. Called by `BuildGraph`; public so a caller holding a graph it
// changed (and the tests) can rank it again.
Result<bool> Rank(Graph& graph);

// `IMP-0015`: the plan, from the `RunSpec` and the graph alone -- one line per
// `simulate` stage: rank, its start, its previous-cycle inputs. Deterministic
// text; loads no library and reads no recording.
std::string PlanText(const RunSpec& spec, const Graph& graph);

// ---------------------------------------------------------------------------
// WP-04: events, steps, readiness, the event log.
// ---------------------------------------------------------------------------

// `IMP-0023`: the closed list of entry kinds (`SYS-0037`). Every line of the
// event log carries one and the step number.
enum class EntryKind {
  kOutputCounterBreak,  // an output did not copy its control's measurement_counter (rule 3, `D18 (2)`)
  kFallbackBeyondGap,   // the counter fallback's best sample was beyond `fallback_max_gap` (`D18 (1)`)
  kCounterGap,
  kCounterReset,
  kStalledTrigger,
  kEvictionMiss,
  kFirstDivergence,
};

const char* ToString(EntryKind kind);

// One entry as a typed record. `Add` checks that the fields its kind needs
// are set and writes exactly those, in the order below:
//   output_counter_break  stage port wanted found
//   fallback_beyond_gap   stage port wanted found gap
//   counter_gap           port from to missed
//   counter_reset         port from to
//   stalled_trigger       stage port counter
//   eviction_miss         stage port wanted
//   first_divergence      stage port
struct LogEntry {
  EntryKind kind = EntryKind::kCounterGap;
  std::uint64_t step = 0;
  std::string stage;
  std::string port;
  std::optional<std::int64_t> wanted;
  std::optional<std::int64_t> found;
  std::optional<std::int64_t> gap;
  std::optional<std::int64_t> from;
  std::optional<std::int64_t> to;
  std::optional<std::int64_t> missed;
  std::optional<std::int64_t> counter;
};

// `IMP-0023`: the engine run's event log, in memory, in the order the
// orchestrator thread added the entries. One line per entry:
//   event=degrade step=<n> entry=<kind> key=value ...
// `event=` is a value of `simcore::Event` (no value is added). Where the lines
// are written is the runner's (`WP-05`).
struct EventLog {
  // Fails (Kind::Contract) naming the missing field when the kind needs one
  // the record does not set; nothing is added then.
  Result<bool> Add(const LogEntry& entry);

  const std::vector<std::string>& Lines() const { return lines_; }
  std::size_t Count(EntryKind kind) const;

 private:
  std::vector<std::string> lines_;
  std::map<EntryKind, std::size_t> counts_;
};

// `IMP-0016`: one entry of the queue. A recorded message (rank 0, so it enters
// its buffer before any run of its instant) or a clock tick of a stage.
struct QueuedEvent {
  enum class Kind { kRecorded, kClock };
  Kind kind = Kind::kRecorded;
  std::int64_t time_ns = 0;
  int rank = 0;                  // 0 for a recorded message, the stage's rank for a clock tick
  std::size_t stage_order = 0;   // declaration order; 0 for a recorded message
  std::size_t source_index = 0;  // index in `sources[]`, for a recorded message
  std::uint64_t arrival = 0;     // order of arrival in the queue
  std::string port;              // recorded: the qualified port ("<producer>.<port>")
  std::vector<std::uint8_t> payload;
  std::optional<std::int64_t> capture_time_ns;
  bus::Origin origin = bus::Origin::Measured;
  std::string stage;  // clock: the stage it starts
};

// `IMP-0016`: orders events by (simulation time, rank, stage declaration
// order, source index, arrival order). One instant's recorded messages come in
// `sources[]` order and then file order; the clock ticks of that instant follow
// them, by rank. Pure data: no clock is read.
//
// The caller pushes recorded messages in reception-time order and keeps the
// next one pushed until the stream is exhausted, so the earliest instant is
// never one a later push could precede.
class EventQueue {
 public:
  void PushRecorded(std::string port, std::int64_t time_ns, std::size_t source_index,
                    std::vector<std::uint8_t> payload, std::optional<std::int64_t> capture_time_ns = std::nullopt,
                    bus::Origin origin = bus::Origin::Measured);

  // A clock that ticks at `first_ns + k * period_ns` -- `first_ns` is the whole
  // recording's first reception time, also for a slice -- from the first tick
  // at or after `from_ns`, up to and including `end_ns`. A period of 0 or
  // below adds nothing.
  void AddClock(std::string stage, int rank, std::size_t stage_order, std::int64_t period_ns, std::int64_t first_ns,
                std::int64_t from_ns, std::int64_t end_ns);

  bool Empty() const;
  std::optional<std::int64_t> NextTime() const;
  // Removes and returns every event of the earliest instant, in order.
  std::vector<QueuedEvent> PopInstant();

  // `IMP-0021`: drops every recorded event (the read-ahead) and moves each
  // clock to its first tick at or after `from_ns`.
  void Reset(std::int64_t from_ns);

  // The last instant a clock may tick at. The runner learns the recording's
  // last reception time only when the read-ahead reaches the end of the
  // streams, and sets it then (`WP-05`).
  void SetClockEnd(std::int64_t end_ns);

 private:
  struct Clock {
    std::string stage;
    int rank = 0;
    std::size_t stage_order = 0;
    std::int64_t period_ns = 0;
    std::int64_t first_ns = 0;
    std::int64_t next_ns = 0;
    std::int64_t end_ns = 0;
  };
  static std::int64_t FirstTickAtOrAfter(const Clock& clock, std::int64_t from_ns);

  std::vector<QueuedEvent> recorded_;  // kept sorted
  std::vector<Clock> clocks_;
  std::uint64_t next_arrival_ = 0;
};

// A run ticket (`ARCH §2.2`): the orchestrator's note that a run is due.
struct Ticket {
  std::uint64_t id = 0;
  std::string stage;
  std::size_t stage_order = 0;
  int rank = 0;
  StartKind start = StartKind::kClock;
  std::int64_t trigger_time_ns = 0;      // the instant of the trigger; a run in a later step keeps it
  std::string trigger_port;              // control or trigger-input port; empty for a clock
  std::vector<std::uint8_t> trigger_payload;  // the recorded control, or the trigger sample
  std::uint64_t created_step = 0;
  std::uint64_t not_before_step = 0;     // a ticket made through a previous-cycle trigger waits for a later step
  std::uint64_t run_number = 0;          // set at dispatch: runs of this stage before this one
  bool restart = false;                  // set at dispatch: first run of the stage, or first after a jump
  bool warming_up = false;               // set at dispatch: restart, not at the recording's start, outputs recorded
  std::uint64_t waited_steps = 0;        // set at dispatch: steps spent parked
  bool readiness_expired = false;        // set at dispatch: the limit passed (or the recording ended) and a named sample is still missing
};

// `IMP-0022`: parked tickets and the readiness limit (rule 6).
class Readiness {
 public:
  enum class Verdict { kReady, kWaiting, kExpired };

  // `limit_steps` is `readiness_limit_steps`; 0 means a run never waits.
  explicit Readiness(std::int64_t limit_steps);

  // Parks the ticket at `step`; parking again keeps the first step.
  void Park(std::uint64_t ticket_id, std::uint64_t step);
  bool IsParked(std::uint64_t ticket_id) const;
  std::uint64_t Waited(std::uint64_t ticket_id, std::uint64_t step) const;
  // Waited at least the limit.
  bool Expired(std::uint64_t ticket_id, std::uint64_t step) const;
  // At a later event: the sample is found -> kReady (unparked); else the limit
  // passed -> kExpired (unparked); else kWaiting.
  Verdict Retry(std::uint64_t ticket_id, std::uint64_t step, bool sample_found);
  void Unpark(std::uint64_t ticket_id);
  void Clear();
  std::size_t ParkedCount() const { return parked_.size(); }
  std::vector<std::uint64_t> ParkedIds() const;

 private:
  std::int64_t limit_steps_ = 0;
  std::map<std::uint64_t, std::uint64_t> parked_;  // ticket id -> step parked at
};

// One output of a run, as the runner reports it for commit.
struct CommittedOutput {
  std::string port;  // qualified: "<stage>.<port>"
  std::vector<std::uint8_t> payload;
  bus::Origin origin = bus::Origin::Simulated;
  std::optional<std::int64_t> capture_time_ns;
};

struct CommitReport {
  std::uint64_t ticket_id = 0;
  std::vector<CommittedOutput> outputs;
};

struct OrchestratorOptions {
  std::int64_t first_reception_ns = 0;  // the whole recording's first reception time
  std::int64_t start_ns = 0;            // the slice start; equals first_reception_ns without a slice
  std::int64_t end_ns = 0;              // the recording's last reception time: clocks stop here
  // Stages the recording holds outputs of: only they are warming up (`D17 (4)`).
  std::set<std::string> stages_with_recorded_outputs;
};

enum class StepEnd {
  kStepEnded,     // the step number advanced
  kForcedParked,  // the recording ended with tickets parked: they are now expired; the step is NOT ended, dispatch again
  kRunEnded,      // the step number advanced and nothing is left
};

// `IMP-0017`..`IMP-0021`, `IMP-0050`. The event-driven step machine of
// `ARCH §7`. It decides from sample headers, the setup and the queue alone.
class Orchestrator {
 public:
  using ReadyFn = std::function<bool(const Ticket&)>;
  using SeekFn = std::function<Result<bool>(std::int64_t to_ns)>;

  // Every reference outlives the orchestrator. The bus's ports are declared by
  // the caller (depth and descriptor), as before.
  Orchestrator(const RunSpec& spec, const Graph& graph, bus::PortBus& bus, EventLog& log,
               OrchestratorOptions options);

  // Recorded messages and the clock ticks go through this queue.
  EventQueue& Queue() { return queue_; }

  // `IMP-0017`: takes the earliest instant, enters each recorded message of it
  // into its buffer through `IdentityTracker::Observe`, and creates one ticket
  // per recorded control, new trigger-input `measurement_counter` or clock
  // tick. Ok(false): no event is left, no step began. `IMP-0050`: a trigger
  // sample at `counterDistance` 0 from the one that last started a run of the
  // stage starts none -- same bytes, a `stalled_trigger` entry; other bytes,
  // identity broken, and the sample still enters its buffer.
  Result<bool> BeginStep();

  // `IMP-0018`: the open tickets of the lowest rank that has a stage head
  // (a stage's earliest open ticket) whose named samples `ready` finds, in
  // stage declaration order. A head not ready is parked; it is handed out
  // with `readiness_expired` once the limit passed. A stage with a ticket
  // already handed out and not committed gets none.
  std::vector<Ticket> NextRunnable(const ReadyFn& ready);

  // `IMP-0019`: removes the reported tickets, enters each one's outputs into
  // the buffers in stage declaration order marked with this step, and creates
  // the tickets they trigger in the same step.
  Result<bool> Commit(const std::vector<CommitReport>& reports);

  // `IMP-0020`: see `StepEnd`.
  StepEnd EndStep();

  // Moves the end of every clock (see `EventQueue::SetClockEnd`).
  void SetEnd(std::int64_t end_ns) { queue_.SetClockEnd(end_ns); }

  // `IMP-0021`: empties every buffer, the read-ahead and every open ticket,
  // forgets the last trigger sample of each stage, calls `seek` (the runner's
  // reader seek), and makes every stage's next run a restart. The step number
  // continues.
  Result<bool> Jump(std::int64_t to_ns, const SeekFn& seek);

  std::uint64_t StepNumber() const { return step_; }
  std::int64_t Now() const { return now_ns_; }
  std::size_t OpenTickets() const { return tickets_.size(); }
  std::size_t ParkedTickets() const { return readiness_.ParkedCount(); }
  std::uint64_t RunsOf(const std::string& stage) const;

 private:
  struct StageState {
    std::uint64_t runs = 0;
    bool restart_pending = true;
    bool has_last_start = false;
    std::uint32_t last_counter = 0;
    std::vector<std::uint8_t> last_payload;
  };
  struct OpenTicket {
    Ticket ticket;
    bool dispatched = false;
    bool force_expired = false;
  };

  // The trigger-input stages `port` feeds, as indices into `graph_.stages`.
  std::vector<std::size_t> TriggeredBy(const std::string& port) const;
  // Whether `payload` repeats a trigger counter with other bytes.
  bool ContentDiffers(const std::string& port, const std::vector<std::uint8_t>& payload) const;
  // Publishes one sample, logs its counter gap or reset, and creates the
  // tickets it triggers. `committed_step` is empty for a recorded sample.
  Result<bool> Enter(const std::string& port, const std::vector<std::uint8_t>& payload, bus::Origin origin,
                     std::optional<std::int64_t> capture_time_ns, std::optional<std::uint64_t> committed_step);
  void CreateTicket(const GraphStage& stage, StartKind start, const std::string& port,
                    const std::vector<std::uint8_t>& payload, std::uint64_t not_before_step);

  const RunSpec& spec_;
  const Graph& graph_;
  bus::PortBus& bus_;
  EventLog& log_;
  OrchestratorOptions options_;
  EventQueue queue_;
  Readiness readiness_;
  std::map<std::string, StageState> stages_;
  std::vector<OpenTicket> tickets_;  // creation order
  std::uint64_t step_ = 0;
  std::int64_t now_ns_ = 0;
  std::uint64_t next_ticket_id_ = 1;
};

// `RCT:IMP-0032` (`ARCH §3.2`): the control message of a run. A recorded
// control gives its `measurement_counter` and `source_timestamp_us` and, when
// the run is not a restart, its `op_mode`; a trigger sample gives its header; a
// clock tick is numbered `k + 1` from the recording's first reception time with
// the tick's instant as its time. The `cycle_counter` is the stage's own count
// of runs from 1, the sticker is OK, and `op_mode` is RESTART on the first run
// and after a jump. `compState` is never read (`RCT:SYS-0012`).
struct ControlHeader {
  std::uint32_t measurement_counter = 0;  // 0: unknown
  std::uint64_t source_timestamp_us = 0;  // 0: unknown
};

class ControlWriter {
 public:
  explicit ControlWriter(std::int64_t first_reception_ns) : first_reception_ns_(first_reception_ns) {}

  // What starts the run, as the two header fields. `trigger_descriptor` types
  // the trigger sample of a `kInput` ticket (null: its header is unknown).
  ControlHeader HeaderOf(const Ticket& ticket, const GraphStage& stage,
                         const google::protobuf::Descriptor* trigger_descriptor) const;

  // The serialized `adas.common.CycleControl` for the run.
  std::vector<std::uint8_t> Write(const Ticket& ticket, const GraphStage& stage,
                                  const google::protobuf::Descriptor* trigger_descriptor) const;

 private:
  std::int64_t first_reception_ns_ = 0;
};

}  // namespace simcore::orchestrator
