// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `EventLog::Add` (`WP-04`, `IMP-0023`): the exact line of every entry
///   kind, the closed list refusing a record that lacks a field its kind
///   needs, and a parser that accepts only a listed kind with a step and
///   rejects a planted line (the shape `SYT-STP-06` checks over a real engine
///   run, built in `WP-09`).
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <optional>
#include <regex>
#include <string>

#include "simcore/orchestrator.hpp"

namespace simcore::orchestrator {
namespace {

LogEntry Entry(EntryKind kind) {
  LogEntry entry;
  entry.kind = kind;
  entry.step = 7;
  entry.stage = "B";
  entry.port = "A.out";
  entry.wanted = 11;
  entry.found = 9;
  entry.gap = 2;
  entry.from = 4;
  entry.to = 8;
  entry.missed = 3;
  entry.counter = 5;
  return entry;
}

// The closed list; a line is valid iff it names `event=`, a step and one of these.
std::optional<std::string> ParsedKind(const std::string& line) {
  static const std::regex pattern(
      R"(^event=degrade step=\d+ entry=(output_counter_break|fallback_beyond_gap|counter_gap|counter_reset|stalled_trigger|eviction_miss|first_divergence)( .*)?$)");
  std::smatch match;
  if (!std::regex_match(line, match, pattern)) return std::nullopt;
  return match[1].str();
}

TEST(OrcEventLog, EveryKindWritesItsExactLine) {
  struct Case {
    EntryKind kind;
    std::string line;
  };
  const Case cases[] = {
      {EntryKind::kOutputCounterBreak, "event=degrade step=7 entry=output_counter_break stage=B port=A.out wanted=11 found=9"},
      {EntryKind::kFallbackBeyondGap,
       "event=degrade step=7 entry=fallback_beyond_gap stage=B port=A.out wanted=11 found=9 gap=2"},
      {EntryKind::kCounterGap, "event=degrade step=7 entry=counter_gap port=A.out from=4 to=8 missed=3"},
      {EntryKind::kCounterReset, "event=degrade step=7 entry=counter_reset port=A.out from=4 to=8"},
      {EntryKind::kStalledTrigger, "event=degrade step=7 entry=stalled_trigger stage=B port=A.out counter=5"},
      {EntryKind::kEvictionMiss, "event=degrade step=7 entry=eviction_miss stage=B port=A.out wanted=11"},
      {EntryKind::kFirstDivergence, "event=degrade step=7 entry=first_divergence stage=B port=A.out"},
  };
  for (const Case& c : cases) {
    EventLog log;
    ASSERT_TRUE(log.Add(Entry(c.kind)).ok()) << ToString(c.kind);
    ASSERT_EQ(log.Lines().size(), 1u);
    EXPECT_EQ(log.Lines()[0], c.line);
    EXPECT_EQ(log.Count(c.kind), 1u);
    EXPECT_EQ(ParsedKind(log.Lines()[0]), std::string(ToString(c.kind)));
  }
}

TEST(OrcEventLog, TheKindsAreTheClosedListOfSeven) {
  const EntryKind all[] = {EntryKind::kOutputCounterBreak, EntryKind::kFallbackBeyondGap, EntryKind::kCounterGap,
                           EntryKind::kCounterReset,       EntryKind::kStalledTrigger,    EntryKind::kEvictionMiss,
                           EntryKind::kFirstDivergence};
  std::set<std::string> names;
  for (const EntryKind kind : all) names.insert(ToString(kind));
  EXPECT_EQ(names.size(), 7u);
}

TEST(OrcEventLog, ARecordMissingAFieldItsKindNeedsIsRefusedAndAddsNothing) {
  EventLog log;
  LogEntry entry = Entry(EntryKind::kFallbackBeyondGap);
  entry.gap.reset();
  const Result<bool> added = log.Add(entry);
  ASSERT_FALSE(added.ok());
  EXPECT_NE(added.error().Format().find("gap"), std::string::npos);
  EXPECT_TRUE(log.Lines().empty());
  EXPECT_EQ(log.Count(EntryKind::kFallbackBeyondGap), 0u);

  LogEntry no_port = Entry(EntryKind::kStalledTrigger);
  no_port.port.clear();
  EXPECT_FALSE(log.Add(no_port).ok());
  EXPECT_TRUE(log.Lines().empty());
}

TEST(OrcEventLog, AFieldTheKindDoesNotNameIsNotWritten) {
  EventLog log;
  ASSERT_TRUE(log.Add(Entry(EntryKind::kCounterReset)).ok());  // `Entry` also sets wanted, found, gap, missed
  EXPECT_EQ(log.Lines()[0].find("wanted="), std::string::npos);
  EXPECT_EQ(log.Lines()[0].find("missed="), std::string::npos);
}

TEST(OrcEventLog, LinesKeepTheOrderTheyWereAddedInAndCountPerKind) {
  EventLog log;
  LogEntry a = Entry(EntryKind::kStalledTrigger);
  a.step = 1;
  LogEntry b = Entry(EntryKind::kCounterGap);
  b.step = 2;
  LogEntry c = Entry(EntryKind::kStalledTrigger);
  c.step = 3;
  ASSERT_TRUE(log.Add(a).ok());
  ASSERT_TRUE(log.Add(b).ok());
  ASSERT_TRUE(log.Add(c).ok());
  ASSERT_EQ(log.Lines().size(), 3u);
  EXPECT_NE(log.Lines()[0].find("step=1 "), std::string::npos);
  EXPECT_NE(log.Lines()[1].find("step=2 "), std::string::npos);
  EXPECT_NE(log.Lines()[2].find("step=3 "), std::string::npos);
  EXPECT_EQ(log.Count(EntryKind::kStalledTrigger), 2u);
  EXPECT_EQ(log.Count(EntryKind::kCounterGap), 1u);
}

// The planted lines a parser of the closed list must reject: another kind, no
// step, a kind outside the list spelled like one.
TEST(OrcEventLog, AParserOfTheClosedListRejectsAPlantedLine) {
  EXPECT_FALSE(ParsedKind("event=degrade step=3 entry=other port=p").has_value());
  EXPECT_FALSE(ParsedKind("event=degrade entry=counter_gap port=p from=1 to=3 missed=1").has_value());
  EXPECT_FALSE(ParsedKind("event=degrade step=3 entry=counter_gaps port=p").has_value());
  EXPECT_TRUE(ParsedKind("event=degrade step=3 entry=counter_gap port=p from=1 to=3 missed=1").has_value());
}

}  // namespace
}  // namespace simcore::orchestrator
