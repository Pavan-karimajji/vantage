// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `IMP-0035`/`IMP-0036` (`WP-07`, `ARCH §8`): which tickets of one rank may
///   run side by side, and the barrier that ends the rank. Internal to
///   `src/simcore/runner/`; `StepOnce` is the only caller.
///
///   `ConflictTable` is decided once from the run setup, at load: two stages
///   conflict when one reads the other (any input of one whose producer is the
///   other, a `previous_cycle` input included) or when both are loaded from
///   the same library path (`IMP-0036`: they share the library's global state).
///   `DispatchRank` runs `run(i)` for every ticket `i` of the rank and returns
///   when all have returned. A ticket waits for every EARLIER (stage
///   declaration order) ticket it conflicts with, so conflicting tickets run
///   in the order one thread would run them. With `threads` at 1 (or one
///   ticket) every `run(i)` is called on the calling thread, in order, and the
///   first one that returns false ends the loop: the same code path, no worker.
///   With more, `min(threads, count)` workers pull tickets; the calling thread
///   only waits at the barrier. A worker never decides anything: `run` is the
///   caller's one call of `Component::Exec` on inputs fixed before dispatch.
/// @author Pavan Karimajji

#pragma once

#include <algorithm>
#include <cctype>
#include <condition_variable>
#include <cstddef>
#include <exception>
#include <filesystem>
#include <functional>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "simcore/runspec.hpp"

namespace simcore::runner {

class ConflictTable {
 public:
  ConflictTable() = default;

  // `IMP-0036`: the pairs of `simulate` stages that never run at the same time.
  static ConflictTable FromSpec(const RunSpec& spec) {
    ConflictTable table;
    std::vector<std::pair<std::string, std::string>> libraries;  // stage, library key
    for (const SpecStage& stage : spec.stages) {
      if (stage.mode != "simulate") continue;
      libraries.emplace_back(stage.name, LibraryKey(stage.impl.path));
    }
    for (std::size_t i = 0; i < libraries.size(); ++i) {
      for (std::size_t j = i + 1; j < libraries.size(); ++j) {
        if (libraries[i].second == libraries[j].second) table.Add(libraries[i].first, libraries[j].first);
      }
    }
    for (const SpecStage& stage : spec.stages) {
      if (stage.mode != "simulate") continue;
      for (const SpecInput& input : stage.inputs) {
        const bool producer_simulates = std::any_of(
            spec.stages.begin(), spec.stages.end(),
            [&](const SpecStage& other) { return other.name == input.producer && other.mode == "simulate"; });
        if (producer_simulates && input.producer != stage.name) table.Add(stage.name, input.producer);
      }
    }
    return table;
  }

  bool Conflicts(const std::string& a, const std::string& b) const { return pairs_.count(Key(a, b)) != 0; }
  bool empty() const { return pairs_.empty(); }

 private:
  static std::pair<std::string, std::string> Key(const std::string& a, const std::string& b) {
    return a < b ? std::make_pair(a, b) : std::make_pair(b, a);
  }
  void Add(const std::string& a, const std::string& b) { pairs_.insert(Key(a, b)); }

  // One key per library file: the same file reached by two spellings is one library.
  static std::string LibraryKey(const std::string& path) {
    std::error_code ec;
    std::filesystem::path resolved = std::filesystem::weakly_canonical(path, ec);
    if (ec) resolved = std::filesystem::path(path).lexically_normal();
    std::string key = resolved.generic_string();
#if defined(_WIN32)
    std::transform(key.begin(), key.end(), key.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
#endif
    return key;
  }

  std::set<std::pair<std::string, std::string>> pairs_;
};

// `conflicts(a, b)` takes two ticket indexes of the rank, `a` < `b`. `run(i)`
// returns false when ticket `i` failed; that only ends the loop on the calling
// thread. An exception from `run` on a worker is rethrown here, after the
// barrier, for the lowest ticket index that threw.
inline void DispatchRank(std::size_t count, int threads, const std::function<bool(std::size_t, std::size_t)>& conflicts,
                         const std::function<bool(std::size_t)>& run) {
  if (threads < 2 || count < 2) {
    for (std::size_t i = 0; i < count; ++i) {
      if (!run(i)) return;
    }
    return;
  }

  std::vector<std::vector<std::size_t>> waits_for(count);
  for (std::size_t later = 0; later < count; ++later) {
    for (std::size_t earlier = 0; earlier < later; ++earlier) {
      if (conflicts(earlier, later)) waits_for[later].push_back(earlier);
    }
  }
  std::mutex mutex;
  std::condition_variable changed;
  std::vector<char> started(count, 0);
  std::vector<char> done(count, 0);
  std::vector<std::exception_ptr> thrown(count);
  std::size_t started_count = 0;

  const auto worker = [&]() {
    for (;;) {
      std::size_t pick = count;
      {
        std::unique_lock<std::mutex> lock(mutex);
        for (;;) {
          if (started_count == count) return;
          for (std::size_t i = 0; i < count && pick == count; ++i) {
            if (started[i] != 0) continue;
            const bool free = std::all_of(waits_for[i].begin(), waits_for[i].end(),
                                          [&](std::size_t earlier) { return done[earlier] != 0; });
            if (free) pick = i;
          }
          if (pick != count) break;
          changed.wait(lock);
        }
        started[pick] = 1;
        ++started_count;
      }
      try {
        (void)run(pick);
      } catch (...) {
        thrown[pick] = std::current_exception();
      }
      {
        std::lock_guard<std::mutex> lock(mutex);
        done[pick] = 1;
      }
      changed.notify_all();
    }
  };

  const std::size_t pool_size = std::min<std::size_t>(static_cast<std::size_t>(threads), count);
  std::vector<std::thread> pool;
  pool.reserve(pool_size);
  for (std::size_t i = 0; i < pool_size; ++i) pool.emplace_back(worker);
  for (std::thread& thread : pool) thread.join();
  for (const std::exception_ptr& error : thrown) {
    if (error) std::rethrow_exception(error);
  }
}

}  // namespace simcore::runner
