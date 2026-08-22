// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `SI-04` -- `module_host` (`WP-10`): loads one component's SIL DLL over
///   the generic ABI (`abi/module_abi.h`), tracks its lifecycle, marshals
///   `PortMap` <-> `AdasPortSet` and runs `Exec()` under a watchdog with
///   crash/hang isolation.
///
///   **Ported from `sil_host/src/{sil_component,exec_timeout}.cpp` and
///   `library_loader.cpp`'s open half** (`WP-10`'s own `DEDUPE`/`MOVE`
///   source, exactly the discipline `WP-09` used for `Scheduler`/`PortBus`)
///   -- real, working algorithm, not reinvented. Two deliberate departures
///   from the ported shape, both `simcore`-idiom rather than a design
///   change: (1) every fallible entry point returns `Result<T>`
///   (`simcore/errors.hpp`) instead of throwing `SilHostError` -- `simcore`
///   already has one closed error taxonomy (`WP-03`) and a second one
///   would be exactly the duplication `R-REQ-1`'s principle warns against
///   one level down; (2) `Dso::Open` folds `library_loader.cpp`'s
///   `ResolveLibrary` + `DynamicLibrary` constructor into one call
///   (`IMP-0079`'s own `DEDUPE` label), because sil_host's split across a
///   free function and a class constructor was two steps for one
///   operation with no caller that ever wanted them separately.
///
///   **New in this slice, not ported from anywhere** (`IMP-0084`..`0086`,
///   `IMP-0091`, `IMP-0093`): `Lifecycle` makes the load/init/shutdown
///   state machine explicit (`sil_host`'s own `SilComponent` tracked only
///   a `handle_ == nullptr` sentinel) and adds `Reset()` -- a `resim`
///   pass across several recordings needs to re-`Init()` a component
///   without reloading its `Dso`, which `sil_host` (one process, one run,
///   never reused) never needed. `Quarantine` operationalises `R-SIM-19`'s
///   per-stage `mode: isolated` bisection primitive for `Bench`'s
///   in-process case: a component that has already crashed or hung is
///   refused a further `Exec()` rather than re-entered, named at the
///   point of refusal. `ExecTimeout` wraps the ported `RunWithTimeout`
///   free function as a configured object so `Component::Exec` can carry
///   its own per-call budget without a caller re-threading a
///   `std::chrono::milliseconds` argument through every call site.
///
///   **Honestly out of scope this slice** (`IMP-0391`/`IMP-0392`): the
///   generated-shim/manifest-declaration half of `R-SIM-22` --
///   `scripts/gen_ports.py` turning a component's `conf/ports.yaml` into
///   compiled dispatch code -- is the PRODUCER side of the generic ABI
///   (already real, in `modules/interfaces/scripts/gen_sil_ports.py`,
///   consumed by `df`/`vdy`/`perception-core`'s own `conf/ports.yaml`).
///   `module_host` is the CONSUMER: `Component::ReadManifest` below
///   already needs no codegen at all -- it parses whatever
///   `adas.sil.ComponentManifest` bytes the loaded DLL reports, at run
///   time, via protobuf reflection, which is the whole point of the
///   two-call `adasManifest()` pattern (`R-SIM-4`: ports discovered, never
///   hardcoded). There is no host-side generated table this work package
///   has a real target to build against yet; forcing one now would be the
///   exact speculative generality this codebase's own style rules forbid.
/// @author Pavan Karimajji

#pragma once

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "Adas__Sil/component_manifest.pb.h"
#include "simcore/abi/module_abi.h"
#include "simcore/errors.hpp"

namespace simcore::module_host {

// One input port's real valid/age_s -- mirrors sil_host's own InputMeta
// (contracts.component.InputMeta's C++ twin). Default (valid=true,
// age_s=0.0) reproduces the pre-fault-injection behaviour for a port
// nothing perturbs.
struct InputMeta {
  bool valid = true;
  double age_s = 0.0;
};

using PortBytes = std::vector<std::uint8_t>;
using PortMap = std::map<std::string, PortBytes>;
using InputMetaMap = std::map<std::string, InputMeta>;

// IMP-0079/0080/0083: one loaded dynamic library. `Open` folds candidate-
// name resolution + platform load into one call (the DEDUPE this class
// exists for); `BoundSymbol<Fn>` is the ported `BindOrThrow` template,
// returning a `Result` rather than throwing.
class Dso {
 public:
  Dso(Dso&&) noexcept;
  Dso& operator=(Dso&&) noexcept;
  Dso(const Dso&) = delete;
  Dso& operator=(const Dso&) = delete;
  ~Dso();

  // 'df_sil' -> df_sil.dll (Windows) | libdf_sil.so | df_sil.so (else),
  // tried in that order per directory, directories tried in the order
  // given -- identical search rule to `sil_host`'s own `ResolveLibrary`.
  // `Result::Fail` names every candidate name and every directory tried
  // (N-8) on a resolve failure, or the platform loader's own error text
  // on a load failure.
  static Result<Dso> Open(const std::string& stem, const std::vector<std::filesystem::path>& search_dirs);

  // Loads exactly the file named -- no candidate-name resolution, for a
  // caller (`Component::Load`) that already has a real path rather than a
  // stem to search for. `Result::Fail(kEnvironment)` on a load failure,
  // naming the platform loader's own error text.
  static Result<Dso> OpenPath(const std::filesystem::path& path);

  const std::filesystem::path& path() const { return path_; }

  // `exec_timeout.hpp`'s own honest limit made concrete: once a call into
  // this library is known to be hung on a detached thread that will never
  // return, unloading the module out from under that thread's still-
  // executing code is worse than leaking the handle for the remaining
  // life of the process (`Component`'s destructor calls this instead of
  // letting `~Dso` run, IMP-0091/0093's own `Quarantine` wiring).
  void Leak();

  // nullptr if the symbol does not exist -- caller's job to error on
  // that, since only the caller knows whether the symbol is required.
  void* Symbol(const std::string& name) const;

  template <class Fn>
  Result<Fn> BoundSymbol(const std::string& name) const {
    void* symbol = Symbol(name);
    if (symbol == nullptr) {
      return Result<Fn>::Fail(Error{Kind::Environment, "a loadable library implementing the generic SIL ABI",
                                     "missing export '" + name + "'", path_.string(),
                                     "check the library was built against the current adas_sil_abi.h"});
    }
    return Result<Fn>::Ok(reinterpret_cast<Fn>(symbol));
  }

 private:
  Dso(std::filesystem::path path, void* handle);

  std::filesystem::path path_;
  void* handle_ = nullptr;
};

// IMP-0084/0085/0086: the load/init/shutdown state machine `sil_host`
// left implicit in a `handle_ == nullptr` sentinel. `Transition` refuses
// (naming the attempted edge) any move not in the table below;
// `Reset()` is the one new edge (`ShutdownDone` -> `Loaded`), letting a
// `resim` pass across several recordings re-`Init()` one already-loaded
// `Dso` without reloading it.
enum class Phase { Loaded, Initialized, ShutdownDone };

std::string ToString(Phase phase);

class Lifecycle {
 public:
  Phase phase() const { return phase_; }

  // Legal edges: Loaded -> Initialized (Init), Initialized -> ShutdownDone
  // (Shutdown), ShutdownDone -> Loaded (Reset, IMP-0085) and the identity
  // edge ShutdownDone -> ShutdownDone (a second Shutdown() is a no-op, not
  // an error -- mirrors `sil_host::SilComponent::~SilComponent()` always
  // calling `Shutdown()` even when a caller already did).
  Result<bool> Transition(Phase to);

 private:
  Phase phase_ = Phase::Loaded;
};

// IMP-0091: `R-SIM-19`'s per-stage `mode: isolated` bisection primitive,
// operationalised for `Bench`'s in-process case -- a component that has
// already crashed or hung inside `Exec()` is refused a further call
// rather than re-entered. Not a substitute for `Campaign`'s real
// subprocess isolation (a genuinely hung `exec()` still cannot be
// recovered from inside the same process, `exec_timeout.hpp`'s own
// honest limit, ported unchanged below) -- this only stops a KNOWN-bad
// component from being asked to run again.
enum class QuarantineReason { kNone, kCrashed, kTimedOut };

class Quarantine {
 public:
  bool IsQuarantined() const { return reason_ != QuarantineReason::kNone; }
  QuarantineReason reason() const { return reason_; }
  const std::string& detail() const { return detail_; }

  void Trip(QuarantineReason reason, std::string detail);
  void Clear();

 private:
  QuarantineReason reason_ = QuarantineReason::kNone;
  std::string detail_;
};

// IMP-0092: ported from `sil_host/src/exec_timeout.{hpp,cpp}` unchanged --
// `fail`/`crash`/`timeout` are three outcomes, never merged (R-SIM-19).
// Honest limit, carried from the source file's own comment: `sil_host`
// (and `module_host`, its C++ twin) is single-process -- a genuine hang
// inside `fn` cannot be killed from here without terminating the whole
// process. This function DETECTS and REPORTS a timeout; it does not
// recover from one. The worker thread is deliberately detached, never
// joined (joining would itself hang forever), and leaks for the
// remaining life of the process.
enum class ExecOutcome { kOk, kTimeout, kException };

struct ExecResult {
  ExecOutcome outcome = ExecOutcome::kOk;
  std::string error;  // exception text (kException); empty otherwise
};

ExecResult RunWithTimeout(const std::function<void()>& fn, std::chrono::milliseconds timeout);

// IMP-0093: `RunWithTimeout` as a configured object, new this slice --
// `Component::Exec` carries its own per-call budget without a caller
// re-threading a `std::chrono::milliseconds` argument through every call
// site.
class ExecTimeout {
 public:
  explicit ExecTimeout(std::chrono::milliseconds timeout) : timeout_(timeout) {}

  ExecResult Run(const std::function<void()>& fn) const { return RunWithTimeout(fn, timeout_); }

  std::chrono::milliseconds timeout() const { return timeout_; }

 private:
  std::chrono::milliseconds timeout_;
};

// IMP-0088/0089: the `PortMap` <-> `AdasPortSet` marshalling
// `sil_host::SilComponent::Exec` carried inline -- factored out here so
// it is independently testable and so `component.cpp` reads as
// load/lifecycle/dispatch, not buffer bookkeeping. `BuildInputPortSet`'s
// `names`/`ports` output params own storage for the duration of the call
// so `AdasPort.name`/`data` stay valid across `adasExec()` (mirrors the
// keepalive discipline the ported code already used).
namespace convert {

void BuildInputPortSet(const PortMap& inputs, const InputMetaMap& input_meta, std::vector<std::string>& names,
                       std::vector<AdasPort>& ports);

void BuildOutputPortSet(std::map<std::string, PortBytes>& out_buffers, std::vector<std::string>& names,
                        std::vector<AdasPort>& ports);

// Ports whose `len > cap` after an `adasExec()` call -- undersize is
// detected from the ports themselves, never from the call's own return
// value (the real `df_sil.dll` still returns success for a tick where one
// output port was too small).
std::vector<std::string> UndersizedPorts(const std::vector<AdasPort>& out_ports);

// Only ports the DLL marked `updated` are copied into the result --
// mirrors `sil_host::SilComponent::Exec`'s own final loop.
PortMap CollectUpdatedPorts(const std::vector<AdasPort>& out_ports);

}  // namespace convert

// IMP-0081/0087/0090/0094/0095/0394: one loaded component, over the
// generic ABI -- `sil_host::SilComponent`'s ported twin. Every export is
// bound at run time via `Dso::BoundSymbol`, never linked against
// (`module_host` resolves N arbitrary component libraries by stem,
// R-SIM-4: ports are discovered, never hardcoded).
class Component {
 public:
  Component(Component&&) noexcept = default;
  Component& operator=(Component&&) noexcept = default;
  Component(const Component&) = delete;
  Component& operator=(const Component&) = delete;
  ~Component();

  // IMP-0081: checks `adasAbiVersion()` against this host's own
  // `kAbiVersion`, then reads the manifest via the two-call pattern
  // (IMP-0090/0394) into the real generated `adas::sil::ComponentManifest`
  // and pre-builds one buffer per declared output port
  // (`max_bytes` if declared, `kDefaultOutputCap` otherwise).
  static Result<Component> Load(const std::filesystem::path& library_path);

  const std::string& name() const { return name_; }
  const ::adas::sil::ComponentManifest& manifest() const { return manifest_; }
  Phase phase() const { return lifecycle_.phase(); }
  bool IsQuarantined() const { return quarantine_.IsQuarantined(); }

  // WP-15 (SW-0137, `diagnostics/modules.cpp`): the on-disk path this
  // component's library was actually opened from -- empty (never a guess)
  // if this `Component` was default-constructed and never `Load`ed.
  std::filesystem::path library_path() const { return dso_.has_value() ? dso_->path() : std::filesystem::path(); }

  // config_path empty -> adasInit(NULL), the packed-bundle resolution
  // (R-SIM-3a). `Result::Fail(kEnvironment)` on a NULL handle, naming the
  // component.
  Result<bool> Init(const std::filesystem::path& config_path = {});
  Result<bool> Shutdown();

  // IMP-0085: `ShutdownDone` -> `Loaded`, so `Init()` can run again
  // without reloading the `Dso`. `Result::Fail` if called from any other
  // phase (naming it) -- resetting a component that was never shut down
  // would leak its live handle.
  Result<bool> Reset();

  // `Result::Fail(kInternal)` if not `Initialized` or if quarantined
  // (naming the reason, IMP-0091); `Result::Fail(kContract)` if an output
  // port is still undersized after one grow-and-retry. `exec_timeout`,
  // when given, runs the call under `ExecTimeout` and trips the
  // quarantine on `kTimeout`/`kException` rather than propagating a
  // `SIGSEGV`-adjacent state back into a re-usable `Component`.
  Result<PortMap> Exec(std::int64_t dt_ns, const PortMap& inputs, const InputMetaMap& input_meta = {},
                       std::optional<ExecTimeout> exec_timeout = std::nullopt);

 private:
  Component() = default;

  Result<bool> ReadManifest();
  void BuildOutBuffers();
  Result<PortMap> ExecOnce(std::int64_t dt_ns, const PortMap& inputs, const InputMetaMap& input_meta);

  using AdasAbiVersionFn = std::int32_t (*)();
  using AdasManifestFn = std::size_t (*)(std::uint8_t*, std::size_t);
  using AdasInitFn = void* (*)(const char*);
  using AdasExecFn = std::int32_t (*)(void*, double, const AdasPortSet*, AdasPortSet*);
  using AdasShutdownFn = void (*)(void*);

  std::optional<Dso> dso_;
  Lifecycle lifecycle_;
  Quarantine quarantine_;
  std::string name_;
  ::adas::sil::ComponentManifest manifest_;
  void* handle_ = nullptr;

  AdasAbiVersionFn adas_abi_version_fn_ = nullptr;
  AdasManifestFn adas_manifest_fn_ = nullptr;
  AdasInitFn adas_init_fn_ = nullptr;
  AdasExecFn adas_exec_fn_ = nullptr;
  AdasShutdownFn adas_shutdown_fn_ = nullptr;

  std::map<std::string, PortBytes> out_buffers_;
};

// ---------------------------------------------------------------------------
// isolate.cpp -- IMP-0096 / SW-0096 (WP-14)
// ---------------------------------------------------------------------------

// `R-SIM-19`'s per-stage `mode: isolated` bisection primitive, made real
// out-of-process: `Quarantine` (above) only protects a component ALREADY
// known bad from being re-entered inside THIS process; it cannot recover
// from a genuine hang or a segfault, which takes the whole process with
// it. `RunIsolatedStage` runs a second `simengine` process (`DD-09`: "the
// isolated stage is a second simengine", `src/simengine/main.cpp`) and
// classifies what happened to it -- `fail`/`crash`/`timeout` are three
// outcomes and are never merged (`R-SIM-19`).
enum class IsolatedOutcome {
  kOk,            // exited 0
  kFail,          // exited nonzero, cleanly -- the child reported its own error
  kCrashed,       // terminated abnormally (POSIX signal / an unhandled-exception
                   // exit status on Windows) -- the child never got to report
  kTimedOut,      // still running past the deadline; killed by this call
  kFailedToStart  // the process itself could not be spawned
};

std::string ToString(IsolatedOutcome outcome);

struct IsolatedRunResult {
  IsolatedOutcome outcome = IsolatedOutcome::kFailedToStart;
  std::string stage;    // the stage this run isolated, named back per SW-0096's Accept
  int exit_code = 0;    // meaningful only for kOk/kFail
  std::string detail;   // spawn failure text, or empty
};

// Spawns `executable` with `args` (argv[1:]) and waits up to `timeout`.
// `stage` is carried through into the result purely for reporting -- this
// function itself never inspects `args` to find it, so a caller free to
// pass any argv shape a future `simengine` flag needs.
//
// `stderr_capture_path` (WP-15, `diagnostics/reproducer.cpp`'s own crash-
// path hook, `SW-0139`): when non-empty, the child's stderr is redirected
// to this file instead of inherited, so a caller can read it back after a
// `kCrashed`/`kFail` outcome and fold it into a reproducer package. Empty
// (the default) preserves the exact inherited-stderr behaviour every
// existing caller already relies on -- this is purely additive.
IsolatedRunResult RunIsolatedStage(const std::string& stage, const std::filesystem::path& executable,
                                    const std::vector<std::string>& args, std::chrono::milliseconds timeout,
                                    const std::filesystem::path& stderr_capture_path = {});

}  // namespace simcore::module_host
