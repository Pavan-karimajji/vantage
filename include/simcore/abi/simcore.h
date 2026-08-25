/* Copyright (c) <ORG>. All Rights Reserved.
 * Proprietary and Confidential.
 * COMPONENT: SIM
 * @file
 * @brief
 *   `SI-09`/`D-5` (`IMP-0144`, `WP-14`): `simcore`'s own embeddable C ABI --
 *   what a HOST (`simengine`, or any other host, `SW-0144`/`IT-11`) links
 *   against to construct and drive the engine. Plain C, `extern "C"`, so
 *   the boundary is loader/linker-stable the same way `abi/module_abi.h`
 *   is -- but the two headers are DIFFERENT ABIs, in opposite directions:
 *   `module_abi.h` (`adas_sil_abi.h`) is what a COMPONENT DLL exposes TO
 *   `module_host`; this header is what `simcore` itself exposes TO a host
 *   that embeds it. Do not conflate the two.
 *
 *   `D-1`: this ABI's only input is a Resolved Run Spec (`IF-09`) already
 *   on disk -- no configuration parser, no path search, no inference on
 *   this side of the boundary (that already happened in the Python
 *   emitter that produced the spec, `runspec/emit.py`). `sources[0].path`
 *   in that spec names the recording; nothing here takes a second path
 *   argument for it.
 *
 *   `IT-11` proves `SW-0144` by linking a test harness -- not `simengine`
 *   -- against exactly this header and this library, with no privileged
 *   access `simengine` itself does not also have.
 *
 *   `ABI_VERSION 2` (`SM-11`, `vantage`): two additions, both optional --
 *   a caller ignoring them gets `ABI_VERSION 1`'s exact behaviour
 *   (`simEngineRun`'s one-call run-to-completion is unchanged). `simEngine
 *   AttachTransport` and `simEngineStepOnce` exist for exactly one real
 *   need neither `simengine` nor `IT-11`'s own host had: an IN-PROCESS
 *   host that renders every tick AS it computes (`D-5`: "the engine hosts
 *   the player, never the reverse") needs a per-tick hook to pump a
 *   renderer between cycles, which `simEngineRun`'s single blocking call
 *   structurally cannot give it. `transport_publisher` is `void*` rather
 *   than a typed pointer because `simcore::transport::TransportPublisher`
 *   is a C++ type this plain-C header cannot name -- the same "opaque
 *   pointer, cast internally" shape `SimEngine*` itself already uses one
 *   level up; a caller constructs the real transport object in C++ (this
 *   header is included from a `.cpp`, same as every other user of it) and
 *   passes it straight through uninterpreted.
 *
 *   **Caller MUST convert to `simcore::transport::TransportPublisher*`
 *   BEFORE erasing to `void*`.** Both real transport classes
 *   (`InProcessTransport`, `SharedMemoryTransport`) multiply-inherit
 *   `adas::transport::ITransport` AND `TransportPublisher`, so the two
 *   base subobjects sit at different addresses whenever `TransportPublisher`
 *   is not literally the first base listed (it is not, in either class).
 *   The compiler applies that offset adjustment only while it still has
 *   both types in view -- erasing straight from the derived pointer skips
 *   it, and this function's own internal `static_cast<TransportPublisher*>
 *   (void*)` cannot recover it from a bare `void*` (no type information
 *   survives the erasure to correct it). Found live: doing this wrong
 *   does not crash -- it silently attaches to the wrong subobject and
 *   delivers no real frames. Correct: `TransportPublisher* p = &transport;
 *   simEngineAttachTransport(engine, p);` (the implicit derived-to-base
 *   conversion happens on the FIRST line, while both types are visible).
 * @author Pavan Karimajji
 */

#ifndef SIMCORE_ABI_SIMCORE_H_
#define SIMCORE_ABI_SIMCORE_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Bumped on any incompatible change to the functions/enum values below --
 * `simEngineAbiVersion()` is this host's own version-check hook, the same
 * two-call discovery shape `module_abi.h`'s `adasAbiVersion()` uses one
 * layer down. */
#define SIMCORE_ABI_VERSION 2

typedef struct SimEngine SimEngine;

/* Mirrors `simcore::ExitCode` (`errors.hpp`, `docs/v2/errors.yaml`)
 * exactly -- `SW-0148`: the executable's exit code (and this ABI's own
 * return value) is always a member of this published set, never a raw
 * platform or library code. */
typedef enum SimExitCode {
  kSimExitOk = 0,
  kSimExitConfig = 2,
  kSimExitCoherence = 3,
  kSimExitModule = 4,
  kSimExitInput = 5,
  kSimExitInfra = 6,
  kSimExitTimeout = 7,
  kSimExitCrash = 8,
} SimExitCode;

int32_t simEngineAbiVersion(void);

/* Constructs the engine from a Resolved Run Spec file (`run_spec_json_path`)
 * -- loads the spec, opens its recorded source(s), loads and initialises
 * every `simulate`-mode stage's component library, and builds the one
 * cycle loop (`simcore::runner::Runner`). `config_path` may be NULL, which
 * resolves the packed config bundle beside each component's own library
 * (`R-SIM-3a`, `adasInit(NULL)`). `exec_timeout_ms` <= 0 means no per-
 * `exec()` timeout.
 *
 * On failure returns NULL, writes a human-readable message into `err_buf`
 * (best-effort, truncated to fit, always NUL-terminated when `err_buf_cap`
 * > 0) and, when `out_exit_code` is non-NULL, names the taxonomy code the
 * failure maps to (`SW-0148`). */
SimEngine* simEngineCreate(const char* run_spec_json_path, const char* config_path, int64_t exec_timeout_ms,
                            char* err_buf, size_t err_buf_cap, SimExitCode* out_exit_code);

/* Runs to completion (or to the end of a configured slice) -- one
 * `Prepare()` plus a `StepOnce()` loop, `simcore::runner::Runner::Run`'s
 * own shape (`ANL-SW-17`: no second loop body exists anywhere behind
 * this call). Not re-entrant on one handle from two threads. */
SimExitCode simEngineRun(SimEngine* engine, char* err_buf, size_t err_buf_cap);

/* `ABI_VERSION 2`. Wires a `simcore::transport::TransportPublisher*`
 * (`transport_publisher`, opaquely typed -- this header's own top note)
 * into the constructed engine's cycle loop, the identical non-owning
 * pointer `runner::Runner::SetTransportPublisher` already takes one layer
 * down -- every declared port's value is offered to it each cycle,
 * independent of whether a writer exists (`SW-0353`-shaped: a caller with
 * nothing attached pays nothing extra). Call before the first
 * `simEngineStepOnce`/`simEngineRun`; `engine` non-NULL and constructed is
 * the only precondition, matching `SetTransportPublisher`'s own "never
 * blocks, no ownership taken" contract. Passing NULL detaches (restores
 * `ABI_VERSION 1` behaviour). */
void simEngineAttachTransport(SimEngine* engine, void* transport_publisher);

/* `ABI_VERSION 2`. One `runner::Runner::StepOnce()` -- the same body
 * `simEngineRun`'s own internal loop calls repeatedly (`ANL-SW-17`: no
 * second loop exists behind either entry point), exposed so an in-process
 * host can pump a renderer between cycles (this header's own top note).
 * `out_continue` is set to 0 once the source is exhausted (mirrors
 * `Runner::StepOnce`'s own `Result<bool>`: `false` means done, not a
 * failure) and 1 otherwise; a caller loops while `*out_continue != 0` and
 * `simEngineStepOnce`'s own return is `kSimExitOk`, the exact shape
 * `simEngineRun`'s internal loop already uses. Calling this after the
 * source is exhausted is a config-kind refusal, never a crash. */
SimExitCode simEngineStepOnce(SimEngine* engine, char* err_buf, size_t err_buf_cap, int32_t* out_continue);

/* Shuts down every loaded component and releases the engine. Safe to call
 * exactly once per handle returned by `simEngineCreate`; `engine` may be
 * NULL (no-op), matching `adasShutdown`'s own null-tolerant convention one
 * layer down. */
void simEngineDestroy(SimEngine* engine);

#ifdef __cplusplus
}
#endif

#endif /* SIMCORE_ABI_SIMCORE_H_ */
