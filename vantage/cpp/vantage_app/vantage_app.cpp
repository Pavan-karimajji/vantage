// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `WP-34` (`SM-11`): `vantage`'s real windowed `main()` -- the piece
///   `WP-32`/`WP-33` left open (host_loop.hpp's own top note). Parses argv,
///   builds a `sim::vantage::EmbeddedEngine` from a run-spec, and hands a
///   `next_tick` callback wrapping `EmbeddedEngine::StepOnce` +
///   `viz::session::PushSource::NextTick` to `viz::render_gl::
///   RunPlayerWindow` -- the same window/GL/ImGui loop `viz_player`'s own
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

#include "vantage/host_loop.hpp"
#include "viz/render_gl/player_runner.hpp"
#include "viz/session/source.hpp"
#include "viz/session/tick.hpp"

namespace {

constexpr std::size_t kPushSourceDepth = 200;  // mirrors RunPlayerWindow's own kHistoryDepth
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

  viz::session::PushSource sink(kPushSourceDepth);
  simcore::Result<bool> sink_opened = sink.Open();
  if (!sink_opened.ok()) {
    std::fprintf(stderr, "vantage_app: %s\n", sink_opened.error().Format().c_str());
    return 1;
  }

  simcore::Result<sim::vantage::EmbeddedEngine> created =
      sim::vantage::EmbeddedEngine::Create(run_spec_path, config_path, kExecTimeoutMs);
  if (!created.ok()) {
    std::fprintf(stderr, "vantage_app: %s\n", created.error().Format().c_str());
    return 1;
  }
  // `std::move(created).value()` (the `&&`-qualified `Result<T>::value()`
  // overload) is not portable across every `adas-sim` package this repo
  // might resolve against -- host_loop.cpp's own `RunEmbedded` already
  // works around an older cached package lacking it via this identical
  // `const_cast` idiom (also established in `modules/viz/tests/unit/
  // test_session.cpp`), so this stays buildable regardless of which
  // `errors.hpp` a given build resolves.
  sim::vantage::EmbeddedEngine engine = std::move(const_cast<sim::vantage::EmbeddedEngine&>(created.value()));

  auto next_tick = [&]() -> std::optional<viz::session::Tick> {
    engine.StepOnce(sink);  // no-op past exhaustion or a prior step failure -- sink just holds
    return sink.NextTick();
  };

  viz::render_gl::RunConfig config;
  config.window_title = "vantage";
  config.plugin_dirs = std::move(plugin_dirs);
  config.bundle_path = bundle_path.empty() ? nullptr : bundle_path.c_str();

  const int exit_code = viz::render_gl::RunPlayerWindow(config, next_tick);
  if (!engine.ok()) {
    std::fprintf(stderr, "vantage_app: engine error: %s\n", engine.error().c_str());
    return exit_code == 0 ? 1 : exit_code;
  }
  return exit_code;
}
