// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `EventQueue` and `Orchestrator` (`WP-04`, `IMP-0016`..`IMP-0021`,
///   `IMP-0050`): the order of events and its ties, the ranks inside a step,
///   one open run per stage, the commit and the tickets it makes, the step
///   numbers, parking and expiry through `NextRunnable`, the recording's end,
///   a jump, a stalled trigger against identity broken, counter gaps and
///   resets in the event log. Each case is built so a naive version fails it.
///   Unit tests of the parts; the system tests `SYT-ORC-*`, `SYT-STP-*` and
///   `SYT-SEL-*` are built in `WP-09`.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <cstdint>
#include <memory>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include <google/protobuf/descriptor.h>

#include "Bsd__Outputs/bsd_outputs.pb.h"
#include "simcore/io.hpp"
#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {
namespace {

const google::protobuf::Descriptor* Descriptor() { return adas::df::BsdOutputs::descriptor(); }

// A real contract message, so the header is read by reflection as in a run.
std::vector<std::uint8_t> Bytes(std::uint32_t measurement, std::uint32_t cycle, std::uint64_t time_us = 1) {
  adas::df::BsdOutputs message;
  adas::common::SignalHeader* header = message.mutable_sig_header();
  header->set_measurement_counter(measurement);
  header->set_cycle_counter(cycle);
  header->set_source_timestamp_us(time_us);
  std::vector<std::uint8_t> bytes(message.ByteSizeLong());
  message.SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
  return bytes;
}

SpecInput In(const std::string& port, const std::string& producer, const std::string& producer_port,
             bool previous_cycle = false) {
  SpecInput input;
  input.port = port;
  input.producer = producer;
  input.producer_port = producer_port;
  input.previous_cycle = previous_cycle;
  return input;
}

SpecStage Stage(const std::string& name, const std::string& trigger, std::vector<SpecInput> inputs = {},
                std::int64_t clock_period_ns = 0) {
  SpecStage stage;
  stage.name = name;
  stage.mode = "simulate";
  stage.trigger = trigger;
  stage.clock_period_ns = clock_period_ns;
  stage.inputs = std::move(inputs);
  return stage;
}

RunSpec Spec(std::vector<SpecStage> stages, std::int64_t readiness_limit_steps = 2) {
  RunSpec spec;
  spec.run_id = "orc";
  spec.stages = std::move(stages);
  spec.readiness_limit_steps = readiness_limit_steps;
  return spec;
}

// One orchestrator with its graph, bus and log; built in place (it holds references).
struct Rig {
  Rig(RunSpec s, const std::set<std::string>& controls, OrchestratorOptions options = {}, std::size_t depth = 8,
      const std::vector<std::string>& declared_ports = {})
      : spec(std::move(s)) {
    std::set<std::string> topics;
    for (const std::string& c : controls) topics.insert(io::CanonicalTopic(c));
    const Result<Graph> built = BuildGraph(spec, topics);
    if (!built.ok()) throw std::runtime_error(built.error().Format());
    graph = built.value();
    // Every port a test publishes on is declared (`WP-05`): the controls and
    // the wired producers by default, with no header type.
    for (const SpecStage& stage : spec.stages) {
      bus.DeclarePort(stage.name + ".control", static_cast<std::int64_t>(depth), nullptr);
      for (const SpecInput& input : stage.inputs) {
        bus.DeclarePort(input.producer + "." + input.producer_port, static_cast<std::int64_t>(depth), nullptr);
      }
    }
    // The recorded source ports some tests push on directly.
    for (const char* port : {"X.measured", "X.m", "X.noise"}) bus.DeclarePort(port, static_cast<std::int64_t>(depth), nullptr);
    for (const std::string& port : declared_ports) bus.DeclarePort(port, static_cast<std::int64_t>(depth), Descriptor());
    orc = std::make_unique<Orchestrator>(spec, graph, bus, log, options);
  }

  Result<bool> Begin() { return orc->BeginStep(); }
  void Control(const std::string& stage, std::int64_t t, std::vector<std::uint8_t> payload = {1}) {
    orc->Queue().PushRecorded(stage + ".control", t, 0, std::move(payload));
  }

  RunSpec spec;
  Graph graph;
  bus::PortBus bus;
  EventLog log;
  std::unique_ptr<Orchestrator> orc;
};

const Orchestrator::ReadyFn kAllReady = [](const Ticket&) { return true; };
const Orchestrator::ReadyFn kNoneReady = [](const Ticket&) { return false; };

std::vector<std::string> Stages(const std::vector<Ticket>& tickets) {
  std::vector<std::string> names;
  for (const Ticket& t : tickets) names.push_back(t.stage);
  return names;
}

CommitReport Report(const Ticket& ticket, std::vector<CommittedOutput> outputs = {}) {
  CommitReport report;
  report.ticket_id = ticket.id;
  report.outputs = std::move(outputs);
  return report;
}

CommittedOutput Out(const std::string& port, std::uint32_t measurement, std::uint32_t cycle = 1) {
  CommittedOutput output;
  output.port = port;
  output.payload = Bytes(measurement, cycle);
  return output;
}

// ---------------------------------------------------------------------------
// IMP-0016: EventQueue
// ---------------------------------------------------------------------------

TEST(OrcQueue, AnInstantsRecordedMessagesComeInSourceOrderThenFileOrderThenClockTicksByRank) {
  EventQueue queue;
  queue.PushRecorded("p.late_file_first_source1", 100, /*source=*/1, {1});
  queue.PushRecorded("p.source0_first", 100, 0, {2});
  queue.PushRecorded("p.source0_second", 100, 0, {3});
  queue.AddClock("slow", /*rank=*/2, /*order=*/0, 100, 100, 100, 1000);
  queue.AddClock("fast", /*rank=*/1, /*order=*/5, 100, 100, 100, 1000);
  const std::vector<QueuedEvent> instant = queue.PopInstant();
  ASSERT_EQ(instant.size(), 5u);
  // A naive arrival-order queue would put source 1 first.
  EXPECT_EQ(instant[0].port, "p.source0_first");
  EXPECT_EQ(instant[1].port, "p.source0_second");
  EXPECT_EQ(instant[2].port, "p.late_file_first_source1");
  // Rank first: the rank 1 clock before the rank 2 clock, whatever the declaration order.
  EXPECT_EQ(instant[3].stage, "fast");
  EXPECT_EQ(instant[4].stage, "slow");
}

TEST(OrcQueue, SameRankClocksTickInStageDeclarationOrder) {
  EventQueue queue;
  queue.AddClock("later", 1, 3, 50, 0, 0, 100);
  queue.AddClock("earlier", 1, 1, 50, 0, 0, 100);
  const std::vector<QueuedEvent> instant = queue.PopInstant();
  ASSERT_EQ(instant.size(), 2u);
  EXPECT_EQ(instant[0].stage, "earlier");
  EXPECT_EQ(instant[1].stage, "later");
}

TEST(OrcQueue, TheEarliestInstantIsPoppedWholeAndTheNextFollows) {
  EventQueue queue;
  queue.PushRecorded("a", 300, 0, {});
  queue.PushRecorded("b", 100, 0, {});
  queue.PushRecorded("c", 100, 0, {});
  ASSERT_EQ(queue.NextTime(), std::optional<std::int64_t>(100));
  EXPECT_EQ(queue.PopInstant().size(), 2u);
  EXPECT_EQ(queue.NextTime(), std::optional<std::int64_t>(300));
  EXPECT_EQ(queue.PopInstant().size(), 1u);
  EXPECT_TRUE(queue.Empty());
}

TEST(OrcQueue, AClockTicksFromTheRecordingsFirstTimeAndStopsAtItsEnd) {
  EventQueue queue;
  queue.AddClock("c", 1, 0, 100, /*first=*/1000, /*from=*/1000, /*end=*/1300);
  std::vector<std::int64_t> times;
  while (!queue.Empty()) times.push_back(*queue.NextTime()), queue.PopInstant();
  EXPECT_EQ(times, (std::vector<std::int64_t>{1000, 1100, 1200, 1300}));  // not 1400
}

TEST(OrcQueue, ASliceTicksAtTheFullRunsInstantsNotFromItsOwnStart) {
  EventQueue queue;
  queue.AddClock("c", 1, 0, 100, /*first=*/1000, /*from=*/1250, /*end=*/1500);
  std::vector<std::int64_t> times;
  while (!queue.Empty()) times.push_back(*queue.NextTime()), queue.PopInstant();
  // A naive clock restarted at the slice start would tick 1250, 1350, 1450.
  EXPECT_EQ(times, (std::vector<std::int64_t>{1300, 1400, 1500}));
}

TEST(OrcQueue, ASliceStartOnATickKeepsThatTick) {
  EventQueue queue;
  queue.AddClock("c", 1, 0, 100, 1000, 1200, 1300);
  EXPECT_EQ(queue.NextTime(), std::optional<std::int64_t>(1200));
}

TEST(OrcQueue, ARecordedMessageAndAClockTickOfOneInstantArePoppedTogether) {
  EventQueue queue;
  queue.PushRecorded("p", 200, 0, {});
  queue.AddClock("c", 1, 0, 100, 0, 0, 1000);
  queue.PopInstant();  // the tick at 0
  queue.PopInstant();  // the tick at 100
  const std::vector<QueuedEvent> instant = queue.PopInstant();  // 200: the message and the tick
  ASSERT_EQ(instant.size(), 2u);
  EXPECT_EQ(instant[0].kind, QueuedEvent::Kind::kRecorded);
  EXPECT_EQ(instant[1].kind, QueuedEvent::Kind::kClock);
}

TEST(OrcQueue, AResetDropsTheRecordedEventsAndMovesTheClocks) {
  EventQueue queue;
  queue.PushRecorded("p", 100, 0, {});
  queue.AddClock("c", 1, 0, 100, 0, 0, 1000);
  queue.Reset(450);
  EXPECT_EQ(queue.NextTime(), std::optional<std::int64_t>(500));
  const std::vector<QueuedEvent> instant = queue.PopInstant();
  ASSERT_EQ(instant.size(), 1u);
  EXPECT_EQ(instant[0].kind, QueuedEvent::Kind::kClock);
}

// ---------------------------------------------------------------------------
// IMP-0017 / IMP-0018 / IMP-0019 / IMP-0020: a step
// ---------------------------------------------------------------------------

// B (rank 2) is declared before A and C (rank 1), so declaration order and
// rank order differ.
std::unique_ptr<Rig> MakeChain(std::int64_t limit = 2, OrchestratorOptions options = {}, bool previous_cycle = false) {
  return std::make_unique<Rig>(
      Spec({Stage("B", "in", {In("in", "A", "out", previous_cycle)}), Stage("A", "control"), Stage("C", "control")}, limit),
      std::set<std::string>{"A.control", "C.control"}, options, 8, std::vector<std::string>{"A.out"});
}

TEST(OrcStep, NoEventMeansNoStep) {
  auto rig = MakeChain();
  const Result<bool> began = rig->Begin();
  ASSERT_TRUE(began.ok());
  EXPECT_FALSE(began.value());
}

TEST(OrcStep, ARecordedControlMakesATicketAndEntersItsBuffer) {
  auto rig = MakeChain();
  rig->Control("A", 100);
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_EQ(rig->orc->Now(), 100);
  EXPECT_EQ(rig->orc->OpenTickets(), 1u);
  const bus::SampleBuffer* buffer = rig->bus.Buffer("A.control");
  ASSERT_NE(buffer, nullptr);
  EXPECT_EQ(buffer->Size(), 1u);  // a recorded message enters its buffer
}

TEST(OrcStep, TicketsAreHandedOutByRankThenDeclarationAndOneOpenRunPerStage) {
  auto rig = MakeChain();
  rig->Control("C", 100);
  rig->Control("A", 100);
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> first = rig->orc->NextRunnable(kAllReady);
  // Both rank 1, in declaration order (A before C), whatever the arrival order.
  EXPECT_EQ(Stages(first), (std::vector<std::string>{"A", "C"}));
  // Both are out and not committed: no stage gets a second open run.
  EXPECT_TRUE(rig->orc->NextRunnable(kAllReady).empty());
}

TEST(OrcStep, ARankIsNotHandedOutBeforeTheLowerRankCommits) {
  auto rig = MakeChain(/*limit=*/0);
  rig->Control("A", 100);
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> rank1 = rig->orc->NextRunnable(kAllReady);
  ASSERT_EQ(Stages(rank1), (std::vector<std::string>{"A"}));
  // B has no ticket yet: A's output is what triggers it.
  EXPECT_TRUE(rig->orc->NextRunnable(kAllReady).empty());
  ASSERT_TRUE(rig->orc->Commit({Report(rank1[0], {Out("A.out", 1)})}).ok());
  // The commit made B's ticket in the same step, and B is the next rank.
  const std::vector<Ticket> rank2 = rig->orc->NextRunnable(kAllReady);
  ASSERT_EQ(Stages(rank2), (std::vector<std::string>{"B"}));
  EXPECT_EQ(rank2[0].rank, 2);
  EXPECT_EQ(rank2[0].trigger_time_ns, 100);
  EXPECT_EQ(rank2[0].created_step, 0u);
}

TEST(OrcStep, TwoControlsOfOneStageAtOneInstantRunInOrderNotTogether) {
  auto rig = MakeChain();
  rig->Control("A", 100, {1});
  rig->Control("A", 100, {2});
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> first = rig->orc->NextRunnable(kAllReady);
  ASSERT_EQ(first.size(), 1u);  // a naive dispatcher hands both out
  EXPECT_EQ(first[0].trigger_payload, std::vector<std::uint8_t>{1});
  EXPECT_EQ(first[0].run_number, 0u);
  EXPECT_TRUE(rig->orc->NextRunnable(kAllReady).empty());  // run 1 waits for run 0 to commit
  ASSERT_TRUE(rig->orc->Commit({Report(first[0])}).ok());
  const std::vector<Ticket> second = rig->orc->NextRunnable(kAllReady);
  ASSERT_EQ(second.size(), 1u);
  EXPECT_EQ(second[0].trigger_payload, std::vector<std::uint8_t>{2});
  EXPECT_EQ(second[0].run_number, 1u);
}

TEST(OrcStep, ACommitEntersOutputsMarkedWithTheStepThatMadeThem) {
  auto rig = MakeChain();
  rig->Control("A", 100);
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> tickets = rig->orc->NextRunnable(kAllReady);
  ASSERT_TRUE(rig->orc->Commit({Report(tickets[0], {Out("A.out", 1)})}).ok());
  const bus::Sample* committed = rig->bus.Buffer("A.out")->Newest();
  ASSERT_NE(committed, nullptr);
  ASSERT_TRUE(committed->committed_step.has_value());
  EXPECT_EQ(*committed->committed_step, rig->orc->StepNumber());
  // A recorded sample carries no step.
  EXPECT_FALSE(rig->bus.Buffer("A.control")->Newest()->committed_step.has_value());
}

TEST(OrcStep, AnOutputIsCommittedInStageDeclarationOrderWhateverTheReportOrder) {
  // Both write the same port's buffer so its order shows who went first.
  auto rig = std::make_unique<Rig>(Spec({Stage("A", "control"), Stage("C", "control")}),
                                   std::set<std::string>{"A.control", "C.control"}, OrchestratorOptions{}, 8,
                                   std::vector<std::string>{"S.out"});
  rig->Control("A", 100);
  rig->Control("C", 100);
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> tickets = rig->orc->NextRunnable(kAllReady);
  ASSERT_EQ(tickets.size(), 2u);
  // Reported C first (counter 2), then A (counter 1): the buffer is still filled A first.
  ASSERT_TRUE(rig->orc->Commit({Report(tickets[1], {Out("S.out", 2)}), Report(tickets[0], {Out("S.out", 1)})}).ok());
  const auto& samples = rig->bus.Buffer("S.out")->Samples();
  ASSERT_EQ(samples.size(), 2u);
  EXPECT_EQ(samples[0].sig.measurement_counter.value(), 1u);
  EXPECT_EQ(samples[1].sig.measurement_counter.value(), 2u);
  EXPECT_EQ(rig->orc->RunsOf("A"), 1u);
  EXPECT_EQ(rig->orc->RunsOf("C"), 1u);
  EXPECT_EQ(rig->orc->OpenTickets(), 0u);
}

TEST(OrcStep, CommittingATicketNeverHandedOutIsRefused) {
  auto rig = MakeChain();
  rig->Control("A", 100);
  ASSERT_TRUE(rig->Begin().value());
  Ticket ghost;
  ghost.id = 999;
  EXPECT_FALSE(rig->orc->Commit({Report(ghost)}).ok());
  // An open ticket not yet handed out is refused too.
  CommitReport open;
  open.ticket_id = 1;
  EXPECT_FALSE(rig->orc->Commit({open}).ok());
}

TEST(OrcStep, AClockTickMakesATicketWithTheTicksInstant) {
  Rig rig(Spec({Stage("K", "", {}, /*clock=*/100)}), {}, [] {
    OrchestratorOptions o;
    o.first_reception_ns = 1000;
    o.start_ns = 1000;
    o.end_ns = 1200;
    return o;
  }());
  std::vector<std::int64_t> triggers;
  while (rig.Begin().value()) {
    for (const Ticket& t : rig.orc->NextRunnable(kAllReady)) {
      triggers.push_back(t.trigger_time_ns);
      EXPECT_EQ(t.start, StartKind::kClock);
      ASSERT_TRUE(rig.orc->Commit({Report(t)}).ok());
    }
    rig.orc->EndStep();
  }
  EXPECT_EQ(triggers, (std::vector<std::int64_t>{1000, 1100, 1200}));
}

TEST(OrcStep, StepNumbersCountFromZeroAndTheRunEndsWhenNothingIsLeft) {
  auto rig = MakeChain();
  rig->Control("A", 100);
  rig->Control("A", 200);
  EXPECT_EQ(rig->orc->StepNumber(), 0u);
  ASSERT_TRUE(rig->Begin().value());
  for (const Ticket& t : rig->orc->NextRunnable(kAllReady)) ASSERT_TRUE(rig->orc->Commit({Report(t)}).ok());
  EXPECT_EQ(rig->orc->EndStep(), StepEnd::kStepEnded);
  EXPECT_EQ(rig->orc->StepNumber(), 1u);
  ASSERT_TRUE(rig->Begin().value());
  for (const Ticket& t : rig->orc->NextRunnable(kAllReady)) ASSERT_TRUE(rig->orc->Commit({Report(t)}).ok());
  EXPECT_EQ(rig->orc->EndStep(), StepEnd::kRunEnded);
  EXPECT_EQ(rig->orc->StepNumber(), 2u);
  EXPECT_FALSE(rig->Begin().value());
}

TEST(OrcStep, AnInstantWithOnlyAMeasuredSampleIsAStepOfItsOwn) {
  auto rig = MakeChain();
  rig->orc->Queue().PushRecorded("X.measured", 100, 0, {7});
  rig->Control("A", 200);
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_EQ(rig->orc->Now(), 100);
  EXPECT_TRUE(rig->orc->NextRunnable(kAllReady).empty());
  EXPECT_EQ(rig->orc->EndStep(), StepEnd::kStepEnded);
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_EQ(rig->orc->Now(), 200);
  EXPECT_EQ(rig->orc->StepNumber(), 1u);
}

TEST(OrcStep, ATicketMadeThroughAPreviousCycleTriggerRunsInTheNextStepNotThisOne) {
  auto rig = MakeChain(/*limit=*/0, {}, /*previous_cycle=*/true);
  rig->Control("A", 100);
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> a = rig->orc->NextRunnable(kAllReady);
  ASSERT_TRUE(rig->orc->Commit({Report(a[0], {Out("A.out", 1)})}).ok());
  EXPECT_TRUE(rig->orc->NextRunnable(kAllReady).empty());  // same step: a naive version runs B here
  EXPECT_EQ(rig->orc->EndStep(), StepEnd::kStepEnded);
  ASSERT_TRUE(rig->Begin().value());  // no recorded event is left, yet B has a step to run in
  const std::vector<Ticket> b = rig->orc->NextRunnable(kAllReady);
  ASSERT_EQ(Stages(b), (std::vector<std::string>{"B"}));
  EXPECT_EQ(b[0].trigger_time_ns, 100);
}

// ---------------------------------------------------------------------------
// IMP-0022 through NextRunnable, IMP-0020: readiness and the recording's end
// ---------------------------------------------------------------------------

// The stage `A` reads a sample that "arrives" when `*found` turns true.
struct Gate {
  bool found = false;
  Orchestrator::ReadyFn Fn() {
    return [this](const Ticket&) { return found; };
  }
};

// Steps at 100, 200, ... so a parked ticket has later steps to wait through.
std::unique_ptr<Rig> ReadinessRig(std::int64_t limit, int steps) {
  auto rig = std::make_unique<Rig>(Spec({Stage("A", "control")}, limit), std::set<std::string>{"A.control"});
  rig->Control("A", 100);
  for (int i = 2; i <= steps; ++i) rig->orc->Queue().PushRecorded("X.noise", 100 * i, 0, {1});
  return rig;
}

TEST(OrcReadinessWait, ATicketWaitsInOrderForItsSampleAndRunsInTheStepItArrives) {
  auto rig = ReadinessRig(/*limit=*/3, 4);
  Gate gate;
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_TRUE(rig->orc->NextRunnable(gate.Fn()).empty());
  EXPECT_EQ(rig->orc->ParkedTickets(), 1u);
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_TRUE(rig->orc->NextRunnable(gate.Fn()).empty());
  gate.found = true;
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> run = rig->orc->NextRunnable(gate.Fn());
  ASSERT_EQ(run.size(), 1u);
  EXPECT_FALSE(run[0].readiness_expired);  // the sample came; no timeout
  EXPECT_EQ(run[0].waited_steps, 2u);
  EXPECT_EQ(run[0].trigger_time_ns, 100);  // the control header keeps the trigger's time
  EXPECT_EQ(rig->orc->Now(), 300);         // the step's time is the instant of processing
  EXPECT_EQ(rig->orc->ParkedTickets(), 0u);
}

TEST(OrcReadinessWait, ALimitOfTwoExpiresAtTheSecondLaterStepNotBefore) {
  auto rig = ReadinessRig(/*limit=*/2, 4);
  Gate gate;
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_TRUE(rig->orc->NextRunnable(gate.Fn()).empty());  // step 0: parked
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_TRUE(rig->orc->NextRunnable(gate.Fn()).empty());  // step 1: one step waited
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> run = rig->orc->NextRunnable(gate.Fn());  // step 2: two steps waited
  ASSERT_EQ(run.size(), 1u);
  EXPECT_TRUE(run[0].readiness_expired);
  EXPECT_EQ(run[0].waited_steps, 2u);
}

TEST(OrcReadinessWait, ALimitOfZeroNeverWaits) {
  auto rig = ReadinessRig(/*limit=*/0, 3);
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> run = rig->orc->NextRunnable(kNoneReady);
  ASSERT_EQ(run.size(), 1u);
  EXPECT_TRUE(run[0].readiness_expired);
  EXPECT_EQ(run[0].waited_steps, 0u);
  EXPECT_EQ(rig->orc->ParkedTickets(), 0u);
}

TEST(OrcReadinessWait, ALimitOfOneWaitsOneStepNotNone) {
  auto rig = ReadinessRig(/*limit=*/1, 3);
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_TRUE(rig->orc->NextRunnable(kNoneReady).empty());
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());
  const std::vector<Ticket> run = rig->orc->NextRunnable(kNoneReady);
  ASSERT_EQ(run.size(), 1u);
  EXPECT_TRUE(run[0].readiness_expired);
}

TEST(OrcReadinessWait, AParkedTicketBlocksItsStagesLaterTickets) {
  auto rig = std::make_unique<Rig>(Spec({Stage("A", "control")}, 5), std::set<std::string>{"A.control"});
  rig->Control("A", 100);
  rig->Control("A", 200);
  Gate gate;
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_TRUE(rig->orc->NextRunnable(gate.Fn()).empty());
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());  // the second control's ticket exists now
  EXPECT_EQ(rig->orc->OpenTickets(), 2u);
  gate.found = true;
  const std::vector<Ticket> run = rig->orc->NextRunnable(gate.Fn());
  ASSERT_EQ(run.size(), 1u);
  EXPECT_EQ(run[0].trigger_time_ns, 100);  // the earlier ticket goes first, strictly in order
}

TEST(OrcReadinessWait, TheRecordingsEndRunsEveryParkedTicketInTheLastStepWithTheReadinessOutcome) {
  auto rig = std::make_unique<Rig>(Spec({Stage("A", "control")}, 50), std::set<std::string>{"A.control"});
  rig->Control("A", 100);
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_TRUE(rig->orc->NextRunnable(kNoneReady).empty());  // parked, the limit is far away
  // Nothing is left in the queue: the step is NOT ended, the ticket is forced.
  EXPECT_EQ(rig->orc->EndStep(), StepEnd::kForcedParked);
  EXPECT_EQ(rig->orc->StepNumber(), 0u);
  const std::vector<Ticket> run = rig->orc->NextRunnable(kNoneReady);
  ASSERT_EQ(run.size(), 1u);
  EXPECT_TRUE(run[0].readiness_expired);
  ASSERT_TRUE(rig->orc->Commit({Report(run[0])}).ok());
  EXPECT_EQ(rig->orc->EndStep(), StepEnd::kRunEnded);  // a naive end would have dropped the run
}

TEST(OrcReadinessWait, AParkedTicketIsNotForcedWhileTheRecordingHasMoreToCome) {
  auto rig = ReadinessRig(/*limit=*/50, 2);
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_TRUE(rig->orc->NextRunnable(kNoneReady).empty());
  EXPECT_EQ(rig->orc->EndStep(), StepEnd::kStepEnded);
}

// ---------------------------------------------------------------------------
// IMP-0021: a jump
// ---------------------------------------------------------------------------

TEST(OrcJump, EmptiesBuffersTicketsAndReadAheadAndTheStepNumberContinues) {
  OrchestratorOptions options;
  options.first_reception_ns = 100;
  auto rig = std::make_unique<Rig>(Spec({Stage("A", "control")}, 0), std::set<std::string>{"A.control"}, options, 8,
                                   std::vector<std::string>{"A.control"});
  rig->Control("A", 100, Bytes(1, 1));
  rig->Control("A", 200, Bytes(2, 2));
  rig->Control("A", 300, Bytes(3, 3));
  ASSERT_TRUE(rig->Begin().value());
  for (const Ticket& t : rig->orc->NextRunnable(kAllReady)) ASSERT_TRUE(rig->orc->Commit({Report(t)}).ok());
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());  // step 1: a ticket is open, not run
  ASSERT_EQ(rig->orc->OpenTickets(), 1u);
  ASSERT_EQ(rig->orc->StepNumber(), 1u);

  std::int64_t seek_to = -1;
  ASSERT_TRUE(rig->orc->Jump(5000, [&](std::int64_t to) {
                seek_to = to;
                return Result<bool>::Ok(true);
              }).ok());
  EXPECT_EQ(seek_to, 5000);
  EXPECT_EQ(rig->orc->OpenTickets(), 0u);
  EXPECT_EQ(rig->bus.Buffer("A.control")->Size(), 0u);  // no old sample is seen
  EXPECT_TRUE(rig->orc->Queue().Empty());               // the read-ahead is gone
  EXPECT_EQ(rig->orc->StepNumber(), 1u);                // numbers continue

  rig->Control("A", 5000, Bytes(9, 9));
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_EQ(rig->orc->StepNumber(), 1u);  // not back at 0
  EXPECT_EQ(rig->orc->EndStep(), StepEnd::kStepEnded);
  EXPECT_EQ(rig->orc->StepNumber(), 2u);
}

TEST(OrcJump, TheNextRunOfEveryStageIsARestartAndOnlyTheFirstOfThem) {
  auto rig = std::make_unique<Rig>(Spec({Stage("A", "control")}, 0), std::set<std::string>{"A.control"});
  rig->Control("A", 100);
  rig->Control("A", 200);
  ASSERT_TRUE(rig->Begin().value());
  std::vector<Ticket> first = rig->orc->NextRunnable(kAllReady);
  EXPECT_TRUE(first[0].restart);  // the first run of the stage
  ASSERT_TRUE(rig->orc->Commit({Report(first[0])}).ok());
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());
  std::vector<Ticket> second = rig->orc->NextRunnable(kAllReady);
  EXPECT_FALSE(second[0].restart);  // then RUN
  ASSERT_TRUE(rig->orc->Commit({Report(second[0])}).ok());
  rig->orc->EndStep();

  ASSERT_TRUE(rig->orc->Jump(900, nullptr).ok());
  rig->Control("A", 900);
  rig->Control("A", 1000);
  ASSERT_TRUE(rig->Begin().value());
  std::vector<Ticket> after = rig->orc->NextRunnable(kAllReady);
  EXPECT_TRUE(after[0].restart);
  EXPECT_EQ(after[0].run_number, 2u);  // runs are counted across the jump
  ASSERT_TRUE(rig->orc->Commit({Report(after[0])}).ok());
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());
  EXPECT_FALSE(rig->orc->NextRunnable(kAllReady)[0].restart);
}

TEST(OrcJump, OnlyAStageTheRecordingHoldsOutputsOfIsWarmingUpAndNotAtTheRecordingsStart) {
  OrchestratorOptions options;
  options.first_reception_ns = 100;
  options.stages_with_recorded_outputs = {"A"};
  auto rig = std::make_unique<Rig>(Spec({Stage("A", "control"), Stage("C", "control")}, 0),
                                   std::set<std::string>{"A.control", "C.control"}, options);
  // First run at the recording's start: not warming up.
  rig->Control("A", 100);
  rig->Control("C", 100);
  ASSERT_TRUE(rig->Begin().value());
  for (const Ticket& t : rig->orc->NextRunnable(kAllReady)) {
    EXPECT_FALSE(t.warming_up) << t.stage;
    ASSERT_TRUE(rig->orc->Commit({Report(t)}).ok());
  }
  rig->orc->EndStep();
  ASSERT_TRUE(rig->orc->Jump(500, nullptr).ok());
  rig->Control("A", 500);
  rig->Control("C", 500);
  ASSERT_TRUE(rig->Begin().value());
  for (const Ticket& t : rig->orc->NextRunnable(kAllReady)) {
    EXPECT_TRUE(t.restart);
    EXPECT_EQ(t.warming_up, t.stage == "A") << t.stage;  // C: the recording holds none of its outputs
  }
}

TEST(OrcJump, AFailingSeekIsReturnedAndStillLeavesNothingOld) {
  auto rig = std::make_unique<Rig>(Spec({Stage("A", "control")}, 0), std::set<std::string>{"A.control"});
  rig->Control("A", 100);
  ASSERT_TRUE(rig->Begin().value());
  const Result<bool> jumped = rig->orc->Jump(10, [](std::int64_t) {
    return Result<bool>::Fail(Error{Kind::Environment, "a seekable recording", "no", "seek", ""});
  });
  EXPECT_FALSE(jumped.ok());
  EXPECT_EQ(rig->orc->OpenTickets(), 0u);
}

TEST(OrcJump, AClockStageTicksAtTheFullRunsInstantsAfterTheJump) {
  OrchestratorOptions options;
  options.first_reception_ns = 1000;
  options.start_ns = 1000;
  options.end_ns = 2000;
  Rig rig(Spec({Stage("K", "", {}, 100)}, 0), {}, options);
  ASSERT_TRUE(rig.orc->Jump(1450, nullptr).ok());
  ASSERT_TRUE(rig.Begin().value());
  EXPECT_EQ(rig.orc->Now(), 1500);
}

// ---------------------------------------------------------------------------
// IMP-0050: stalled trigger against identity broken
// ---------------------------------------------------------------------------

// `T` starts on a new measurement_counter of the recorded port `source.in_x`.
std::unique_ptr<Rig> TriggerRig(std::size_t depth = 8) {
  return std::make_unique<Rig>(Spec({Stage("T", "in_x", {In("in_x", "source", "in_x")})}, 0), std::set<std::string>{},
                               OrchestratorOptions{}, depth, std::vector<std::string>{"source.in_x"});
}

// Plays one recorded sample as its own step and returns the tickets it made.
std::size_t Play(Rig& rig, std::int64_t t, const std::vector<std::uint8_t>& bytes) {
  rig.orc->Queue().PushRecorded("source.in_x", t, 0, bytes);
  EXPECT_TRUE(rig.Begin().value());
  const std::vector<Ticket> tickets = rig.orc->NextRunnable(kAllReady);
  for (const Ticket& ticket : tickets) {
    EXPECT_TRUE(rig.orc->Commit({Report(ticket)}).ok());
  }
  rig.orc->EndStep();
  return tickets.size();
}

TEST(OrcTrigger, ANewMeasurementCounterStartsARunAndTheSameCounterWithTheSameBytesDoesNot) {
  auto rig = TriggerRig();
  EXPECT_EQ(Play(*rig, 100, Bytes(1, 1)), 1u);
  EXPECT_EQ(Play(*rig, 200, Bytes(1, 1)), 0u);  // stalled: no run
  EXPECT_EQ(Play(*rig, 300, Bytes(2, 2)), 1u);
  EXPECT_EQ(rig->orc->RunsOf("T"), 2u);  // one run per distinct counter
  EXPECT_EQ(rig->log.Count(EntryKind::kStalledTrigger), 1u);
  ASSERT_EQ(rig->log.Lines().size(), 1u);
  EXPECT_EQ(rig->log.Lines()[0], "event=degrade step=1 entry=stalled_trigger stage=T port=source.in_x counter=1");
  EXPECT_EQ(rig->bus.Identity().Counts("source.in_x").identity_broken, 0u);
}

TEST(OrcTrigger, TheSameCounterWithOtherBytesIsIdentityBrokenNotStalledAndStartsNoRun) {
  auto rig = TriggerRig();
  EXPECT_EQ(Play(*rig, 100, Bytes(1, 1, /*time_us=*/10)), 1u);
  // Same measurement_counter and the same cycle_counter, other content: a naive
  // "same counter is a stall" logs stalled_trigger; a tracker without the byte
  // compare calls it ok.
  EXPECT_EQ(Play(*rig, 200, Bytes(1, 1, /*time_us=*/99)), 0u);
  EXPECT_EQ(rig->log.Count(EntryKind::kStalledTrigger), 0u);
  EXPECT_EQ(rig->bus.Identity().Counts("source.in_x").identity_broken, 1u);
  EXPECT_EQ(rig->bus.Buffer("source.in_x")->Size(), 2u);  // the sample still entered its buffer
}

TEST(OrcTrigger, TheComparisonSurvivesABufferOfDepthOne) {
  auto rig = TriggerRig(/*depth=*/1);  // the earlier sample is evicted the moment the next arrives
  EXPECT_EQ(Play(*rig, 100, Bytes(4, 4)), 1u);
  EXPECT_EQ(Play(*rig, 200, Bytes(4, 4)), 0u);
  EXPECT_EQ(rig->log.Count(EntryKind::kStalledTrigger), 1u);  // bytes were kept by the orchestrator
  EXPECT_EQ(Play(*rig, 300, Bytes(4, 4, 77)), 0u);
  EXPECT_EQ(rig->bus.Identity().Counts("source.in_x").identity_broken, 1u);
}

TEST(OrcTrigger, AStalledSampleDoesNotMoveTheLastStarter) {
  auto rig = TriggerRig();
  EXPECT_EQ(Play(*rig, 100, Bytes(1, 1, 10)), 1u);
  EXPECT_EQ(Play(*rig, 200, Bytes(1, 1, 99)), 0u);  // broken: bytes differ
  // Back to the starter's own bytes: still a stall against the sample that started the run.
  EXPECT_EQ(Play(*rig, 300, Bytes(1, 1, 10)), 0u);
  EXPECT_EQ(rig->log.Count(EntryKind::kStalledTrigger), 1u);
}

TEST(OrcTrigger, ACounterThatWrapsAroundIsStillANewCounter) {
  auto rig = TriggerRig();
  EXPECT_EQ(Play(*rig, 100, Bytes(0xFFFFFFFFu, 5)), 1u);
  EXPECT_EQ(Play(*rig, 200, Bytes(1, 6)), 1u);  // 0 is unknown; 1 follows the wrap
  EXPECT_EQ(rig->log.Count(EntryKind::kStalledTrigger), 0u);
}

TEST(OrcTrigger, ASampleWithNoCounterStartsARunEachTime) {
  auto rig = TriggerRig();
  EXPECT_EQ(Play(*rig, 100, Bytes(0, 1)), 1u);
  EXPECT_EQ(Play(*rig, 200, Bytes(0, 1)), 1u);  // nothing to judge a repeat by
  EXPECT_EQ(rig->log.Count(EntryKind::kStalledTrigger), 0u);
}

TEST(OrcTrigger, AJumpForgetsTheLastStarter) {
  auto rig = TriggerRig();
  EXPECT_EQ(Play(*rig, 100, Bytes(7, 7)), 1u);
  ASSERT_TRUE(rig->orc->Jump(500, nullptr).ok());
  EXPECT_EQ(Play(*rig, 500, Bytes(7, 7)), 1u);  // the same sample after a jump is a first, not a stall
  EXPECT_EQ(rig->log.Count(EntryKind::kStalledTrigger), 0u);
}

// ---------------------------------------------------------------------------
// IMP-0017 / IMP-0023: counter gaps and resets reach the event log
// ---------------------------------------------------------------------------

TEST(OrcLog, ACounterGapAndAResetAreWrittenWithTheirStep) {
  Rig rig(Spec({Stage("A", "control")}, 0), {"A.control"}, OrchestratorOptions{}, 8, {"X.m"});
  auto play = [&](std::int64_t t, const std::vector<std::uint8_t>& bytes) {
    rig.orc->Queue().PushRecorded("X.m", t, 0, bytes);
    ASSERT_TRUE(rig.Begin().value());
    rig.orc->EndStep();
  };
  play(100, Bytes(10, 10));
  play(200, Bytes(14, 11));  // 11, 12, 13 missed
  play(300, Bytes(15, 12));  // ok: nothing logged
  play(400, Bytes(3, 2));    // both counters back: a reset
  ASSERT_EQ(rig.log.Lines().size(), 2u);
  EXPECT_EQ(rig.log.Lines()[0], "event=degrade step=1 entry=counter_gap port=X.m from=10 to=14 missed=3");
  EXPECT_EQ(rig.log.Lines()[1], "event=degrade step=3 entry=counter_reset port=X.m from=15 to=3");
  EXPECT_EQ(rig.log.Count(EntryKind::kCounterGap), 1u);
  EXPECT_EQ(rig.log.Count(EntryKind::kCounterReset), 1u);
}

TEST(OrcLog, APortDeclaredWithNoMessageTypeIsNotJudgedAndLogsNothing) {
  Rig rig(Spec({Stage("A", "control")}, 0), {"A.control"});
  rig.orc->Queue().PushRecorded("X.m", 100, 0, Bytes(1, 1));
  rig.orc->Queue().PushRecorded("X.m", 200, 0, Bytes(9, 2));
  ASSERT_TRUE(rig.Begin().value());
  rig.orc->EndStep();
  ASSERT_TRUE(rig.Begin().value());
  EXPECT_TRUE(rig.log.Lines().empty());  // no descriptor, no header read, no verdict
}

TEST(OrcLog, ACommittedOutputGapIsLoggedInTheStepThatMadeIt) {
  auto rig = MakeChain(0);
  rig->Control("A", 100);
  rig->Control("A", 200);
  ASSERT_TRUE(rig->Begin().value());
  std::vector<Ticket> first = rig->orc->NextRunnable(kAllReady);
  ASSERT_TRUE(rig->orc->Commit({Report(first[0], {Out("A.out", 1, 1)})}).ok());
  for (const Ticket& b : rig->orc->NextRunnable(kAllReady)) ASSERT_TRUE(rig->orc->Commit({Report(b)}).ok());
  rig->orc->EndStep();
  ASSERT_TRUE(rig->Begin().value());
  first = rig->orc->NextRunnable(kAllReady);
  ASSERT_TRUE(rig->orc->Commit({Report(first[0], {Out("A.out", 5, 2)})}).ok());
  ASSERT_EQ(rig->log.Lines().size(), 1u);
  EXPECT_EQ(rig->log.Lines()[0], "event=degrade step=1 entry=counter_gap port=A.out from=1 to=5 missed=3");
}

}  // namespace
}  // namespace simcore::orchestrator
