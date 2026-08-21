// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IMP-0119` / `SW-0119` -- the last COMPLETED cycle, on disk, as the
///   run proceeds.
///
///   `EXTEND` of `adas_sim/orchestrate/worker.py`, which checkpoints at RUN
///   granularity (one record per recording, written when that recording
///   finishes). Its own gap is the one this closes: a run whose component
///   segfaults never returns from the loop at all, so a per-run record
///   never gets written and the question *"how far did it get?"* has no
///   answer from outside the process. Per-cycle, it does.
///
///   Two deliberate properties:
///   - **Written after the cycle completes, never before** -- the file must
///     never name a cycle the output does not contain, which is exactly
///     what `UT-RUN-07` compares.
///   - **Replaced atomically** (write a sibling temp file, then `rename`)
///     -- a process killed mid-write must leave the PREVIOUS complete
///     record, never a half-written one. A checkpoint that can be corrupt
///     is a checkpoint nobody can act on.
///
///   The flush schedule is `io::ReadBounds`, the same three-axis bound
///   vocabulary `io::WriterBase` flushes on (`IMP-0041`'s own "reusing that
///   one bound vocabulary rather than inventing a second"). Hand-rolled
///   JSON: `simcore` has one vendored single-header JSON *reader*
///   (`third_party/`, `DD-02`) and this is four scalar fields -- pulling a
///   serializer in for it would be the heavier change.
/// @author Pavan Karimajji

#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <system_error>

#include "simcore/runner.hpp"

namespace simcore::runner {

namespace {

std::string JsonEscape(const std::string& raw) {
  std::string out;
  for (char c : raw) {
    if (c == '"' || c == '\\') out.push_back('\\');
    out.push_back(c);
  }
  return out;
}

// A minimal scalar extractor for the four keys this file itself writes --
// deliberately NOT a JSON parser (`Read` is the mirror of `Write`, one
// file's private format, not a general reader). The quoted-string branch
// scans for the closing quote and unescapes `JsonEscape`'s own two escaped
// characters (`"`, `\`) in the same pass -- a naive `find('"', pos + 1)`
// would stop at an ESCAPED quote inside the value and, even where it
// happened to land on the real closing quote, would hand back the escaped
// form unchanged (`run\13` round-tripping as `run\\13`), corrupting any
// `run_id` containing either character.
bool FindValue(const std::string& text, const std::string& key, std::string& out) {
  const std::string needle = "\"" + key + "\"";
  const std::size_t key_pos = text.find(needle);
  if (key_pos == std::string::npos) return false;
  std::size_t pos = text.find(':', key_pos + needle.size());
  if (pos == std::string::npos) return false;
  ++pos;
  while (pos < text.size() && (text[pos] == ' ' || text[pos] == '\n' || text[pos] == '\t')) ++pos;
  if (pos >= text.size()) return false;
  if (text[pos] == '"') {
    std::string unescaped;
    std::size_t i = pos + 1;
    bool closed = false;
    for (; i < text.size(); ++i) {
      if (text[i] == '\\' && i + 1 < text.size()) {
        unescaped.push_back(text[i + 1]);
        ++i;
        continue;
      }
      if (text[i] == '"') {
        closed = true;
        break;
      }
      unescaped.push_back(text[i]);
    }
    if (!closed) return false;
    out = std::move(unescaped);
    return true;
  }
  const std::size_t end = text.find_first_of(",}\n", pos);
  out = text.substr(pos, end == std::string::npos ? std::string::npos : end - pos);
  while (!out.empty() && (out.back() == ' ' || out.back() == '\r')) out.pop_back();
  return true;
}

}  // namespace

Checkpoint::Checkpoint(std::filesystem::path path, std::string run_id, io::ReadBounds flush_bounds)
    : path_(std::move(path)), run_id_(std::move(run_id)), flush_bounds_(flush_bounds) {
  pending_.run_id = run_id_;
}

void Checkpoint::RecordCompleted(std::uint64_t tick_index, std::int64_t log_time_ns, std::size_t bytes_this_cycle) {
  pending_.tick_index = tick_index;
  pending_.log_time_ns = log_time_ns;
  pending_.completed = true;
  ++since_flush_;
  bytes_since_flush_ += bytes_this_cycle;
  if (!have_span_start_) {
    span_start_ns_ = log_time_ns;
    have_span_start_ = true;
  }

  // Same shape as `WriterBase::WriteMessage`'s own bound evaluation: a zero
  // axis does not bound, and a bounds with every axis zero means "every
  // cycle" (the default, and the only setting a crash-diagnosis file should
  // ever be given without a written reason). `max_bytes` counts the same
  // quantity `bytes_this_cycle` carries in -- the caller's own written-byte
  // total for the cycle just completed (`cycle_loop.cpp`'s write pass), not
  // a size this class estimates on its own (`R-SIM-25`: never estimate what
  // nothing produced).
  const bool bounded = flush_bounds_.max_messages != 0 || flush_bounds_.max_bytes != 0 ||
                       flush_bounds_.max_span_ns != 0;
  if (!bounded) {
    Flush();
    return;
  }
  if (flush_bounds_.max_messages != 0 && since_flush_ >= flush_bounds_.max_messages) {
    Flush();
    return;
  }
  if (flush_bounds_.max_bytes != 0 && bytes_since_flush_ >= flush_bounds_.max_bytes) {
    Flush();
    return;
  }
  if (flush_bounds_.max_span_ns != 0 && log_time_ns - span_start_ns_ >= flush_bounds_.max_span_ns) {
    Flush();
  }
}

void Checkpoint::Flush() {
  if (!pending_.completed) return;  // nothing has completed: never claim a cycle
  Write();
  since_flush_ = 0;
  bytes_since_flush_ = 0;
  have_span_start_ = false;
}

void Checkpoint::Write() {
  std::filesystem::path temp = path_;
  temp += ".tmp";
  {
    std::ofstream out(temp, std::ios::binary | std::ios::trunc);
    if (!out) return;  // a checkpoint that cannot be written never fails the run
    out << "{\n";
    out << "  \"run_id\": \"" << JsonEscape(pending_.run_id) << "\",\n";
    out << "  \"last_completed_tick_index\": " << pending_.tick_index << ",\n";
    out << "  \"last_completed_log_time_ns\": " << pending_.log_time_ns << ",\n";
    out << "  \"completed\": " << (pending_.completed ? "true" : "false") << "\n";
    out << "}\n";
    out.flush();
  }
  std::error_code ec;
  std::filesystem::rename(temp, path_, ec);
  if (ec) {
    // Windows `rename` refuses an existing destination through some
    // filesystems; remove-then-rename is the documented fallback and is
    // still the smallest window this can be reduced to without a
    // platform-specific `ReplaceFile`/`renameat2` path.
    std::filesystem::remove(path_, ec);
    std::filesystem::rename(temp, path_, ec);
  }
}

Result<CheckpointRecord> Checkpoint::Read(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return Result<CheckpointRecord>::Fail(Error{Kind::Environment, "a readable progress.json", "cannot open",
                                                path.string(),
                                                "the run may have been killed before its first cycle completed"});
  }
  std::ostringstream buffer;
  buffer << in.rdbuf();
  const std::string text = buffer.str();

  CheckpointRecord record;
  std::string value;
  if (FindValue(text, "run_id", value)) record.run_id = value;
  if (FindValue(text, "last_completed_tick_index", value)) {
    record.tick_index = static_cast<std::uint64_t>(std::stoull(value));
  }
  if (FindValue(text, "last_completed_log_time_ns", value)) {
    record.log_time_ns = static_cast<std::int64_t>(std::stoll(value));
  }
  if (FindValue(text, "completed", value)) record.completed = (value == "true");
  return Result<CheckpointRecord>::Ok(record);
}

}  // namespace simcore::runner
