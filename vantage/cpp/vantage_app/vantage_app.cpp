// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `WP-34` (`SM-11`): `vantage`'s real windowed `main()` -- the piece
///   `WP-32`/`WP-33` left open (host_loop.hpp's own top note). Parses argv,
///   starts a `sim::vantage::EngineThread` (the engine on its own thread,
///   engine integration plan E-4: it used to be stepped from the window's
///   own frame loop) and hands `viz::render_gl::RunPlayerWindow` a
///   non-blocking `next_tick` that only pops finished cycles, plus the
///   host's own toolbar buttons (Run/Pause, Step, pace, step-locked) as data
///   -- the same window/GL/ImGui loop `viz_player`'s own
///   `player_app.cpp` drives, extracted for exactly this reuse
///   (`player_runner.hpp`'s own top note has the full account of why this
///   file never includes an ImGui/GLFW header itself).
///
///   **Argv, settled scope (not `vantage.py`'s full surface):** a
///   positional run-spec JSON path (`simEngineCreate`'s own
///   `run_spec_json_path`), `--config <path>` (forwarded to
///   `EmbeddedEngine::Create`'s `config_path` -- same "adasInit(NULL)
///   bundle auto-resolution is not built yet" caveat `vantage.py`'s own
///   `--config` help text already carries), `--project <name>` (accepted
///   for CLI parity with `vantage.py`, not yet consumed -- `simEngineCreate`
///   takes a config path, not a project name), and `--plugin-root <dir>`
///   (repeatable, forwarded to `RunConfig::plugin_dirs`). `--pipeline`/
///   `--search` are `vantage.py`'s own GUI-driven pipeline-construction
///   flow with no C++ equivalent yet -- parsed and refused with a named
///   error rather than silently ignored.
///
///   **Inherited, not re-litigated, from `frame_bridge.hpp`'s own top
///   note:** every `PortValue::schema_bytes`/`schema_name` this run
///   produces is empty (no manifest source wired into the bridge yet), and
///   `Tick::t_ns` carries the engine's own cycle count, not true elapsed
///   nanoseconds.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <cstdio>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <vector>

#include "vantage/engine_thread.hpp"
#include "vantage/host_loop.hpp"
#include "viz/render_gl/player_runner.hpp"
#include "viz/session/source.hpp"
#include "viz/session/tick.hpp"

namespace {

constexpr std::int64_t kExecTimeoutMs = 2000;

}  // namespace

int main(int argc, char** argv) {
  std::string run_spec_path;
  std::string config_path;
  std::string project = "base";
  std::vector<std::filesystem::path> plugin_dirs;
  std::string bundle_path;

  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--config" && i + 1 < argc) {
      config_path = argv[++i];
    } else if (arg == "--project" && i + 1 < argc) {
      project = argv[++i];
    } else if (arg == "--plugin-root" && i + 1 < argc) {
      plugin_dirs.push_back(argv[++i]);
    } else if (arg == "--bundle" && i + 1 < argc) {
      // Same explicit flag `viz_player`'s own `player_app.cpp` takes --
      // there is no auto-derivation from `--plugin-root` anywhere in this
      // codebase today (R-SIM-3a's "beside the DLL" resolution is a build-
      // time deploy convention, not a runtime lookup this host performs).
      bundle_path = argv[++i];
    } else if (arg == "--pipeline" || arg == "--search") {
      std::fprintf(stderr,
                    "vantage_app: '%s' is not yet implemented in the native host -- "
                    "use vantage.bat (the Python launcher) for a pipeline run\n",
                    arg.c_str());
      return 1;
    } else if (run_spec_path.empty()) {
      run_spec_path = arg;
    } else {
      std::fprintf(stderr, "vantage_app: unrecognized argument '%s'\n", arg.c_str());
      return 1;
    }
  }
  (void)project;  // accepted for CLI parity with vantage.py; not yet consumed (see this file's own top note)

  if (run_spec_path.empty()) {
    std::fprintf(stderr,
                  "usage: vantage_app <run_spec.json> [--config <path>] [--project <name>] "
                  "[--plugin-root <dir>]... [--bundle <path>]\n");
    return 1;
  }

  // E-4: the engine runs on its own thread (created, stepped and destroyed there); the window only pops what
  // it has finished. No PushSource on this path: the worker produces Ticks straight into the hand-over.
  sim::vantage::EngineThread engine(sim::vantage::MakeEmbeddedFactory(run_spec_path, config_path, kExecTimeoutMs));
  std::string start_error;
  if (!engine.Start(&start_error)) {
    std::fprintf(stderr, "vantage_app: %s\n", start_error.c_str());
    return 1;
  }

  auto next_tick = [&engine]() -> std::optional<viz::session::Tick> { return engine.NextTick(); };

  // Vantage's own controls, as data for the toolbar's host slot. Called on the window thread each frame;
  // every press hands off to the engine thread through EngineThread's own locked setters.
  auto host_buttons = [&engine]() {
    std::vector<viz::render_gl::HostButton> buttons;
    const bool running = engine.Running();
    const bool over = engine.Finished() || engine.Failed();
    const sim::vantage::PaceSetting pace = engine.Pace();
    buttons.push_back({running ? "Pause" : "Run", !over, false, [&engine, running] { engine.SetRunning(!running); }});
    buttons.push_back({"Step", !running && !over, false, [&engine] { engine.RequestStep(); }});
    char hz_label[32];
    std::snprintf(hz_label, sizeof(hz_label), "%g cycles/s", pace.hz);
    buttons.push_back({"max", true, pace.max, [&engine, pace] {
                         sim::vantage::PaceSetting next = pace;
                         next.max = true;
                         engine.SetPace(next);
                       }});
    buttons.push_back({hz_label, true, !pace.max, [&engine, pace] {
                         sim::vantage::PaceSetting next = pace;
                         next.max = false;
                         engine.SetPace(next);
                       }});
    const bool locked = engine.StepLocked();
    buttons.push_back({"step-locked", true, locked, [&engine, locked] { engine.SetStepLocked(!locked); }});
    return buttons;
  };

  auto host_notes = [&engine]() {
    std::vector<viz::render_gl::StatusNote> notes;
    // Where the engine is, always: the viewed cycle can be frozen or stepped back while the engine runs on.
    char where[96];
    const sim::vantage::PaceSetting pace = engine.Pace();
    char pace_text[32];
    if (pace.max) {
      std::snprintf(pace_text, sizeof(pace_text), "pace max");
    } else {
      std::snprintf(pace_text, sizeof(pace_text), "%g cycles/s", pace.hz);
    }
    std::snprintf(where, sizeof(where), "engine at cycle %llu - %s%s, %s",
                  static_cast<unsigned long long>(engine.CyclesProduced()),
                  engine.Finished() || engine.Failed() ? "stopped" : (engine.Running() ? "running" : "paused"),
                  engine.StepLocked() ? ", step-locked" : "", pace_text);
    notes.push_back({where, viz::render_gl::NoteSeverity::kInfo});
    if (engine.Failed()) {
      notes.push_back({"engine error: " + engine.Error(), viz::render_gl::NoteSeverity::kWarning});
    } else if (engine.Finished()) {
      notes.push_back({"run finished after " + std::to_string(engine.CyclesProduced()) + " cycles",
                       viz::render_gl::NoteSeverity::kInfo});
    }
    return notes;
  };

  viz::render_gl::RunConfig config;
  config.window_title = "vantage";
  config.plugin_dirs = std::move(plugin_dirs);
  config.bundle_path = bundle_path.empty() ? nullptr : bundle_path.c_str();
  config.time_owner = df_viz::TimeOwner::kEngine;  // the engine owns time; viz only looks
  config.host_buttons = host_buttons;
  config.host_notes = host_notes;
  config.host_dropped = [&engine]() -> std::uint64_t { return engine.Dropped(); };

  const int exit_code = viz::render_gl::RunPlayerWindow(config, next_tick);
  engine.Stop();  // closing the window stops and joins the worker, from running, paused or step-locked
  if (engine.CyclesProduced() > 0) {
    std::fprintf(stderr, "vantage_app: engine made %llu cycles, %.1f us each inside the engine, %llu not kept by the window\n",
                 static_cast<unsigned long long>(engine.CyclesProduced()),
                 engine.BusySeconds() * 1e6 / static_cast<double>(engine.CyclesProduced()),
                 static_cast<unsigned long long>(engine.Dropped()));
  }
  if (engine.Failed()) {
    std::fprintf(stderr, "vantage_app: engine error: %s\n", engine.Error().c_str());
    return exit_code == 0 ? 1 : exit_code;
  }
  return exit_code;
}
