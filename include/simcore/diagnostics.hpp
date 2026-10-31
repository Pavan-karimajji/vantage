// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `WP-15` (`MP-2`, `SI-08`) -- engine diagnostics: `IMP-0131`..`0140`.
///   Six independently-useful facilities sharing one property, `SW-0140`:
///   **diagnostics never raise.** Every symbol here either cannot fail (a
///   pure in-memory transform, returned directly, `noexcept`) or CAN fail
///   at an I/O boundary, in which case it returns `Result<T>`
///   (`simcore/errors.hpp`) and is itself `noexcept` -- an unwritable
///   output directory, a full disk or a bad path is a reported failure,
///   never a thrown exception that would take the run down over a
///   diagnostic (`UT-EDG-09`'s own point).
///
///   `IMP-0131` (`graph_dump.cpp`) is a MOVE+adapt of
///   `sil_host/src/graph_dump.cpp` onto `simcore::RunSpec`, extended with a
///   structural comparison (`CompareGraphDumps`) so `IT-10` diffs the
///   engine's own emission against a second, independently-produced
///   prediction rather than eyeballing two strings.
///
///   `IMP-0076` (`ScheduleDump`) was retired by `WP-03` (`IMP-0015`): the
///   plan is `orchestrator::PlanText` (`orchestrator.hpp`,
///   `orchestrator/plan_dump.cpp`).
/// @author Pavan Karimajji

#pragma once

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "simcore/errors.hpp"
#include "simcore/module_host.hpp"
#include "simcore/runspec.hpp"

namespace simcore::diagnostics {

// ---------------------------------------------------------------------------
// graph_dump.cpp -- IMP-0131 / SW-0131
// ---------------------------------------------------------------------------

// One stage as the engine actually constructed it -- `impl` is the path (or
// stub id) the loaded `Dso` actually opened, not the spec's own string, so a
// spec/engine disagreement (e.g. a resolved-vs-declared path mismatch) is
// visible in the dump rather than papered over by re-printing the spec.
struct GraphStageView {
  std::string name;
  std::string mode;
  std::string impl;
  std::vector<std::string> inputs;  // "port = producer.producer_port", sorted
};

struct GraphView {
  std::string run_id;
  std::vector<GraphStageView> stages;  // declaration order, per R-SIM-1's
                                            // sibling discipline (UT-A4-12/P-8)
};

// `loaded_stages`: the stage names the engine actually holds a live
// `Component` for (a real construction's `component_ptrs` keys) -- a stage
// the spec lists but the engine never loaded (mode != "simulate", or a
// `simulate` stage whose `Component::Load` failed before this is even
// called) is reported with `impl = "unloaded"`, never silently omitted or
// silently shown as if it loaded (`R-SIM-25`, `NR-SIM-4`: no plausible
// default).
GraphView BuildGraphView(const RunSpec& spec, const std::vector<std::string>& loaded_stages);

// Deterministic, line-oriented text -- `std::map`/sorted-vector iteration
// throughout `BuildGraphView`, never hash order (same discipline
// `sil_host/src/graph_dump.cpp` used, ported here).
std::string DumpGraphText(const GraphView& view) noexcept;

// `IT-10`: a structural, line-oriented diff between the engine's own dump
// and a second, independently-produced prediction (typically the
// configuration layer's). Returns the FIRST diverging line -- never a full
// diff -- because `IT-10`'s job is "detected, not eyeballed", not a diff
// viewer.
struct GraphDumpDiff {
  bool matches = true;
  std::size_t first_diff_line = 0;
  std::string engine_line;
  std::string predicted_line;
};

GraphDumpDiff CompareGraphDumps(const std::string& engine_dump, const std::string& predicted_dump) noexcept;

// ---------------------------------------------------------------------------
// trace.cpp -- IMP-0132 / IMP-0133 / SW-0132 / SW-0133
// ---------------------------------------------------------------------------

enum class CycleOutcome { kRan, kHeld };

// One module, one tick. `inputs_received` names every qualified port
// (`<stage>.<port>`) the module was handed for this tick -- populated even
// on `kHeld` as an empty vector (a held module receives nothing), so
// "accounts for every module on every tick including held ones" (`SW-0132`
// Accept) is a property of the entry shape, not of a caller remembering to
// populate every field.
struct CycleTraceEntry {
  std::uint64_t tick_index = 0;
  std::string stage;
  CycleOutcome outcome = CycleOutcome::kHeld;
  std::vector<std::string> inputs_received;
  std::chrono::nanoseconds duration{0};  // always 0 for kHeld
};

// SW-0133: purely additive bookkeeping -- `Record` never reads a port value
// or a scheduling decision, only appends what a caller already computed. A
// caller that never constructs/uses a `CycleTrace` (the off-by-default
// case) produces byte-identical port values to one that does, because
// nothing in the cycle loop's own decision path consults this class
// (enforced by review/grep, same discipline `SW-0136` uses for `cost.cpp`,
// not by anything this class could check about itself).
class CycleTrace {
 public:
  void Record(CycleTraceEntry entry);

  const std::vector<CycleTraceEntry>& entries() const { return entries_; }

  // Reconciliation hooks for `SW-0132`'s Accept ("timing reconciles with
  // per-module statistics") -- a caller compares these against
  // `CostReport::time_per_module`.
  std::chrono::nanoseconds TotalDuration(const std::string& stage) const;
  std::size_t RanCount(const std::string& stage) const;
  std::size_t HeldCount(const std::string& stage) const;

  // Every (tick_index, stage) pair the trace recorded, exactly once each --
  // `SW-0132`'s "every module on every tick" made checkable: a caller
  // compares this against the scheduler's own `Order()` x `[0, ticks)`
  // cross-product.
  std::vector<std::pair<std::uint64_t, std::string>> CoveredCells() const;

 private:
  std::vector<CycleTraceEntry> entries_;
};

// ---------------------------------------------------------------------------
// cost.cpp -- IMP-0134 / IMP-0135 / IMP-0136 / SW-0134 / SW-0135 / SW-0136
// ---------------------------------------------------------------------------

// `SW-0136`: nothing on this type is ever read by a scheduling decision, a
// port value or an output -- it exists to be filled DURING a run and read
// back AFTER, never consulted mid-run. `Reconcile()` is the only method
// that reads its own fields, and it is diagnostic-only (returns findings,
// changes nothing).
struct CostReport {
  std::chrono::nanoseconds wall_time{0};
  std::uint64_t cycles_executed = 0;
  std::map<std::string, std::chrono::nanoseconds> time_per_module;
  std::chrono::nanoseconds time_reading{0};
  std::uint64_t bytes_read_total = 0;
  std::map<std::string, std::uint64_t> bytes_read_per_topic;

  // `SW-0134` Accept: "all five present and reconcile with each other and
  // with the cycle trace". Returns one human-readable finding per
  // disagreement (empty = consistent) -- `time_per_module` summed must not
  // exceed `wall_time`, `bytes_read_per_topic` summed must equal
  // `bytes_read_total` (`SW-0135`'s own "per-topic total equals run
  // total"), and, when `trace` is given, `time_per_module` must equal
  // `trace->TotalDuration` per stage.
  std::vector<std::string> Reconcile(const CycleTrace* trace = nullptr) const noexcept;
};

// `IMP-0135`: bytes are counted, never estimated -- `Observe` is meant to be
// called exactly once per `io::RawMessage` actually pulled off a codec's
// `Batch` (the codec boundary, `SW-0135`'s own Shall), with that message's
// real `payload.size()`. A run that decodes no image topic therefore
// reports exactly zero bytes for it, because nothing ever calls `Observe`
// for a topic nothing pulled -- there is no default entry to zero out.
class ByteCounter {
 public:
  void Observe(const std::string& topic, std::size_t bytes) noexcept;

  std::uint64_t Total() const noexcept { return total_; }
  std::uint64_t ForTopic(const std::string& topic) const noexcept;
  const std::map<std::string, std::uint64_t>& PerTopic() const noexcept { return per_topic_; }

 private:
  std::map<std::string, std::uint64_t> per_topic_;
  std::uint64_t total_ = 0;
};

// A measured duration accumulator -- deliberately the ONLY thing in
// `cost.cpp` that reads a clock, and deliberately returning nothing a
// caller could feed back into `Scheduler`/`bus` (`SW-0136`'s "no measured
// duration shall enter a scheduling decision" made structural: this type
// has no accessor a scheduling path could call, only a private target
// reference it writes to on destruction).
class ScopedTimer {
 public:
  explicit ScopedTimer(std::chrono::nanoseconds& accumulate_into) noexcept;
  ~ScopedTimer();
  ScopedTimer(const ScopedTimer&) = delete;
  ScopedTimer& operator=(const ScopedTimer&) = delete;
  ScopedTimer(ScopedTimer&&) = delete;
  ScopedTimer& operator=(ScopedTimer&&) = delete;

 private:
  std::chrono::nanoseconds& target_;
  std::chrono::steady_clock::time_point start_;
};

// ---------------------------------------------------------------------------
// modules.cpp -- IMP-0137 / SW-0137
// ---------------------------------------------------------------------------

inline constexpr const char* kUnknown = "unknown";

// One loaded component's identity, as one set -- every field present or
// literally the string `"unknown"` (`kUnknown`), never a plausible default
// (a config-bundle hash of `""` is reported as `unknown`, never as `""`
// which a reader could mistake for "no bundle" vs "not read yet").
struct ModuleReportEntry {
  std::string stage;
  std::string path_opened;
  std::string abi_version;
  std::string component_version;
  std::string build_id;
  std::string config_bundle_hash;
};

ModuleReportEntry BuildModuleReportEntry(const std::string& stage_name,
                                          const module_host::Component& component) noexcept;

std::vector<ModuleReportEntry> BuildModuleReport(
    const std::map<std::string, module_host::Component*>& components) noexcept;

std::string DumpModuleReportText(const std::vector<ModuleReportEntry>& entries) noexcept;

// ---------------------------------------------------------------------------
// breakpoints.cpp -- IMP-0138 / SW-0138
// ---------------------------------------------------------------------------

// Closed comparison set (R-SIM-15's spirit, applied to break conditions
// rather than mutation verbs) -- six comparators, never an expression
// string.
enum class Comparator { kEq, kNe, kLt, kGt, kLe, kGe };

bool CompareLiteral(Comparator comparator, double lhs, double rhs) noexcept;

// Exactly one halt kind per condition -- a closed shape (cycle index / time
// / module entry / port predicate), never an open expression tree.
// `on_port.field_path` is intentionally unstructured today: this slice
// evaluates a port's raw BYTE LENGTH against the literal (`CheckPortLength`
// below), because a real per-field comparison needs protobuf reflection
// over the port's declared `proto_type` (`R-SIM-24`'s tolerance-table
// discipline is the nearest existing precedent, not yet wired into
// `simcore`) -- named as a scope limit, not silently narrowed.
struct BreakCondition {
  std::optional<std::uint64_t> at_cycle;
  std::optional<std::int64_t> at_time_ns;
  std::optional<std::string> on_module_entry;

  struct PortCheck {
    std::string qualified_port;  // "<stage>.<port>"
    Comparator comparator = Comparator::kEq;
    double literal = 0.0;  // compared against the port's byte length
  };
  std::optional<PortCheck> on_port;
};

// One evaluator per halt kind -- a caller invokes the matching `Check*` at
// the point in its own loop where that fact becomes available (before
// `Scheduler::Advance()` for `CheckCycle`/`CheckTime`, before `Component::
// Exec` for `CheckModuleEntry`, after a port's bytes are known for
// `CheckPortLength`). Each is a pure predicate: no state, no side effect,
// so a caller can evaluate the same condition against many ticks without
// resetting anything.
bool CheckCycle(const BreakCondition& condition, std::uint64_t tick_index) noexcept;
bool CheckTime(const BreakCondition& condition, std::int64_t log_time_ns) noexcept;
bool CheckModuleEntry(const BreakCondition& condition, const std::string& stage_about_to_run) noexcept;
bool CheckPortLength(const BreakCondition& condition, const std::string& qualified_port,
                     std::size_t byte_length) noexcept;

// ---------------------------------------------------------------------------
// reproducer.cpp -- IMP-0139 / SW-0139
// ---------------------------------------------------------------------------

// Everything `WriteReproducer` needs, gathered by the caller BEFORE calling
// it (this function never re-derives any of it): the run spec to copy in
// verbatim, the input capture at the failing cycle, one formatted module-
// identity line (`DumpModuleReportText` on the crashed stage's own entry is
// the intended source), and whatever stderr the crashed process produced.
struct ReproducerInput {
  std::filesystem::path run_spec_path;
  std::uint64_t failing_cycle = 0;
  std::map<std::string, std::vector<std::uint8_t>> input_capture;
  std::string module_identity;
  std::string captured_stderr;
};

struct ReproducerResult {
  std::filesystem::path package_dir;
  std::vector<std::string> files_written;
};

// SW-0139/SW-0140: writes `<output_dir>/<run_id_or_ts>/` containing
// `run_spec.json` (copied), `input_capture/<qualified_port>.bin`,
// `module_identity.txt` and `stderr.txt`. Every filesystem call goes
// through the `std::error_code` overload -- never the throwing one -- so
// this function is genuinely `noexcept`: an unwritable directory, a full
// disk or a bad path is `Result::Fail(Kind::Environment)`, naming the path
// and the operation that failed, never an exception unwinding through a
// crash handler that is itself reacting to a crash.
Result<ReproducerResult> WriteReproducer(const std::filesystem::path& output_dir,
                                          const ReproducerInput& input) noexcept;

}  // namespace simcore::diagnostics
