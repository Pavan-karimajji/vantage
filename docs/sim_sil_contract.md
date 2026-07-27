# SIL Contract — the Python↔C boundary, generalized

Status: **concept, frozen for review 2026-07-27.** Part of the simulation
rework — see [sim_architecture.md](sim_architecture.md) for the whole picture.
This document owns L0/L1: how a host (Python, C++, anything) loads a component
DLL, discovers its ports, moves protobuf across the boundary, and composes
several components into a pipeline.

Governing rules: `R-SIL-1` (host-agnostic C-API DLL is the SIL delivery),
`R-ARCH-3` (protobuf crosses component boundaries only), `R-IFACE-1`
(`interfaces` is the contract repo). Existing detail:
[df_sil_dll.md](../../../docs/df_sil_dll.md).

---

## 1. What exists today

`modules/df/src/platform/df_sil/df_interface_c.h`:

```c
typedef struct { const uint8_t* data; size_t len; double ageS; int valid; }        DfReqBuf;
typedef struct { uint8_t* data; size_t cap; size_t len; int updated; }             DfProBuf;

DF_API int   dfApiVersion(void);
DF_API void* dfInit(const char* configPath);
DF_API int   dfExec(void* handle, double dtS,
                    const DfReqBuf* objects, const DfReqBuf* egoDyn, const DfReqBuf* vehSig,
                    DfProBuf* aebOutputs, DfProBuf* bsdOutputs,
                    DfProBuf* aebCompState, DfProBuf* bsdCompState);
DF_API void  dfShutdown(void* handle);
```

Two hosts call it: `modules/sil_host/main.cpp` (implicit linking, C++) and
`modules/df/tools/carla/df_ctypes.py` (explicit `LoadLibrary`, Python ctypes,
104 lines mirroring the header by hand, with a `dfApiVersion()` equality check
at load time so drift is a loud failure rather than a silent buffer misread).

**What is right about this and is kept unchanged:**

- **A pure-C header with zero C++ constructs.** This is what makes it
  host-agnostic (`../../../docs/df_sil_dll.md` rule 3). Non-negotiable.
- **`DfReqBuf`/`DfProBuf` as the wire form of `ReqPort<T>`/`ProPort<T>`**
  (rule 4). Serialized protobuf in, caller-owned output buffers out, filled up
  to `cap`. The metadata split is exactly right: `ageS`/`valid` inbound,
  `len`/`updated` outbound.
- **Caller-owned output memory.** The DLL never allocates for the host.
- **Exception safety at the boundary** — every `extern "C"` body wrapped in
  `try/catch(...)` (rule 12). A ctypes caller cannot catch a C++ exception at
  all, so this is load-bearing for the Python host specifically.
- **A monotonic API version, checked by the host at load** (rule 8).

Everything below changes *one* thing: how ports are named and passed.

---

## 2. The problem, precisely

`../../../docs/df_sil_dll.md` rule 11 states it in the repo's own words:

> *"Explicitly NOT solved by this step: running a second function (e.g. `bsd`)
> alongside `aeb`. `fnExec()`'s parameters are hardcoded to AEB's specific ports
> — there is no generic/variadic buffer mechanism. […] `fnExec()` itself would
> still need real, non-trivial editing […] a breaking change requiring an
> `fnApiVersion()` bump."*

That prediction has already come true once. `dfApiVersion` went **1 → 2** when
BSD landed: `dfExec` grew from five parameters to nine, `compState` was renamed
`aebCompState`, and four files changed in lockstep (`df_interface_c.h/.cpp`,
`df_ctypes.py`, `sil_host/main.cpp`, plus both Python drivers).

Projected against the roadmap in plan.md item 7 (ACC, LKA, LCA, LDW) and the
rear-safety set:

| Functions enabled | `dfExec` parameters | ABI version |
|---|---|---|
| AEB | 5 | 1 |
| AEB + BSD | 9 | 2 ← today |
| + ACC | 11 | 3 |
| + LCA | 13 | 4 |
| + LDW | 15 | 5 |
| + LKA | 17 | 6 |
| + RCTA/RCTB/DOW | 23 | 9 |

Every row is a breaking change to a production-facing header, a rebuild of both
hosts, and an edit to the hand-written ctypes mirror. And the count is only
half the cost: rule 11 also flags a modelling question the positional signature
**cannot express at all** — front-vs-rear object port differentiation
(`/front/objects` vs `/rear/objects`), left open since BSD's design because
there is no way to say it.

A second, independent problem: `perception-core` will eventually ship its own
C-API DLL. Under today's pattern that means a second bespoke header, a second
hand-written ctypes mirror, and a second bespoke host loop. There is no notion
of "a SIL component" — only "the `df` DLL".

---

## 3. The design: named port sets

One idea, applied twice (ABI + manifest).

### 3.1 The generic ABI

Declared once, in `modules/interfaces` (it *is* a cross-component contract, so
`R-IFACE-1` puts it there), as `interfaces/include/adas/adas_sil_abi.h`:

```c
#ifndef ADAS_SIL_ABI_H_
#define ADAS_SIL_ABI_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* One port, either direction. The union of DfReqBuf and DfProBuf plus a name.
   For an input:  data/len/ageS/valid are set by the host; cap/updated ignored.
   For an output: data/cap are set by the host; len/updated are set by the DLL. */
typedef struct {
  const char* name;   /* stable port id, e.g. "objects", "aeb.outputs"        */
  uint8_t*    data;   /* serialized protobuf                                  */
  size_t      len;    /* bytes present (in) / bytes written (out)             */
  size_t      cap;    /* capacity of data (out only)                          */
  double      ageS;   /* age of the input at this tick (in only)              */
  int32_t     valid;  /* 0/1 — was anything received this tick (in only)      */
  int32_t     updated;/* 0/1 — did the DLL write this port (out only)         */
} AdasPort;

typedef struct {
  AdasPort* ports;
  size_t    count;
} AdasPortSet;

/* ABI generation of THIS header. Bumped only when the structs or the call
   semantics above change — NOT when a component adds or removes a port.       */
ADAS_SIL_API int32_t adasAbiVersion(void);

/* Component identity + its port manifest, as a serialized
   adas.sil.ComponentManifest (see §3.2). Callable before adasInit.
   Returns the number of bytes written, or the required size if cap is too
   small (classic two-call pattern). */
ADAS_SIL_API size_t adasManifest(uint8_t* data, size_t cap);

/* configPath: the project's config bundle, or NULL to use the bundle packed
   beside this library (<library_dir>/config/, resolved from the module's own
   path). An explicit path always wins — see §3.4.                             */
ADAS_SIL_API void* adasInit(const char* configPath);

/* One cycle. Ports are matched BY NAME; order is irrelevant. A port the
   component does not know is ignored. A port it requires but does not receive
   is treated exactly as valid=0 is treated today.
   Returns 1 on success, 0 on failure.                                         */
ADAS_SIL_API int32_t adasExec(void* handle, double dtS,
                              const AdasPortSet* in, AdasPortSet* out);

ADAS_SIL_API void adasShutdown(void* handle);

#ifdef __cplusplus
}
#endif
#endif
```

Five exports, forever. **Adding a function adds a port name, not a parameter.**

The `ADAS_SIL_API` macro follows the existing `DF_API` pattern verbatim
(`__declspec(dllexport)` when building the component, `dllimport` otherwise) —
`../../../docs/df_sil_dll.md` rule 6, unchanged.

### 3.2 The port manifest

Ports are *declared* by the component, *discovered* by the host — the same
principle as `R-VAR-2` ("a project exists iff some module's `conf/build.yml`
declares it; a missing central roster is unrepresentable by design"). There is
no list of ports anywhere except inside the component that owns them.

Schema in `interfaces` as `proto/Adas__Sil/component_manifest.proto`:

```proto
message ComponentManifest {
  string component      = 1;   // "df", "perception-core"
  string version        = 2;   // component semver
  int32  abi_version    = 3;   // must equal adasAbiVersion()
  string build_id       = 4;   // git describe of the build that produced this DLL
  repeated PortSpec inputs  = 5;
  repeated PortSpec outputs = 6;
  // Configuration identity (OD-4, sim_architecture.md §5.6). The project this
  // DLL was built for, and the hash of the config bundle packed beside it.
  // Lets a host populate the run manifest without being told, and makes an
  // explicit-override / built-project mismatch detectable instead of silent.
  string project            = 7;   // "base", "2w_base", "cus1"
  string config_bundle_sha256 = 8; // empty until stage C5 lands

  // Every schema this component speaks, as a serialized FileDescriptorSet —
  // the messages named by PortSpec.proto_type plus their transitive
  // dependencies. The DLL already links all of them, so this costs a few kB
  // of rodata and deletes the host's dependency on generated bindings
  // entirely (§4.4). Same construction foxglove_stream.py already performs at
  // run time to build a channel schema from a DESCRIPTOR, moved to build time.
  bytes descriptor_set      = 9;
}

message PortSpec {
  string name          = 1;   // "objects", "aeb.outputs"
  string proto_type    = 2;   // fully-qualified: "adas.perception.GenObjectList"
  uint32 max_bytes     = 3;   // sizing hint for the host's output buffer
  bool   optional      = 4;   // may be absent without failing the cycle
  string owner_function= 5;   // "aeb" — empty for component-level ports
  string doc           = 6;
}
```

The manifest is **generated at build time from the same `ENABLED_FUNCTIONS`
list that gates the code** (`R-VAR-5`), so it cannot drift from what was
actually compiled: build with `bsd` disabled and `bsd.outputs` is simply not in
the manifest. It is emitted two ways, both from one source:

1. **embedded in the DLL**, returned by `adasManifest()` — authoritative, and
   what a host actually uses;
2. **written next to the artefact** as `df_sil.ports.yaml` — human-readable, and
   what code review, the GUI's port picker and the pipeline author read.

A gtest asserts the two agree, in the same slot `test_interface_c_api.cpp`
already occupies.

**`df`'s manifest today would be:**

```yaml
component: df
abi_version: 1
inputs:
  - {name: objects, proto_type: adas.perception.GenObjectList, optional: false}
  - {name: egoDyn,  proto_type: adas.vehicle.VehDyn,           optional: false}
  - {name: vehSig,  proto_type: adas.vehicle.VehSig,           optional: true}
outputs:
  - {name: aeb.outputs,    proto_type: adas.aeb.AebOutputs, max_bytes: 256, owner_function: aeb}
  - {name: aeb.comp_state, proto_type: adas.common.CompState, max_bytes: 256, owner_function: aeb}
  - {name: bsd.outputs,    proto_type: adas.bsd.BsdOutputs, max_bytes: 512, owner_function: bsd}
  - {name: bsd.comp_state, proto_type: adas.common.CompState, max_bytes: 256, owner_function: bsd}
```

Adding LCA appends two output lines. No header edit, no host edit, no ABI bump.

**Port naming rules** (freeze these, they become `R-SIM` rules):

- lowercase, dot-separated: `<function>.<port>` for function-owned ports,
  bare `<port>` for component-level ones;
- the segment before the dot is the same `ENABLED_FUNCTIONS` token used by
  `src/component/<fn>/` and `tests/<fn>/` — one vocabulary, three places;
- a port name is **API**: renaming one is a breaking change to the *manifest*,
  which is versioned by the component's own version, not by the ABI version;
- the still-open front/rear question (rule 11) becomes expressible without any
  ABI change: `front.objects` and `rear.objects` are just two names. This
  document does not decide it — it removes the reason it could not be decided.

### 3.3 What this does *not* change

`FunctionRunner`, `AebFunction`, `BsdFunction`, `ports.hpp` and everything under
`src/component/**` are untouched. `updateReqPort()`/`writeProBuf()` keep doing
exactly what they do; the only difference is that `adasExec` looks a port up by
name in a small table before calling them, instead of receiving it as parameter
number six. `../../../docs/df_sil_dll.md` rule 9 ("no changes to `src/component/*`") holds.

### 3.4 Config resolution (OD-4)

`dfInit(configPath)` takes a path to a single YAML today, supplied by the host
and pointing into the **source checkout** (`DEFAULT_CONFIG_PATH = DF_ROOT /
"src" / "project" / "base" / "default.yaml"`), while `ego_params.yaml` is
resolved separately through a compile-time-baked absolute path into the Conan
cache. Two halves, two mechanisms, both machine-local, and free to disagree —
see `sim_architecture.md` §5.6 for the full analysis.

`adasInit` resolves **one atomic bundle**, in this order:

1. **explicit `configPath`** — always wins, so a deliberate cross-project
   experiment stays possible;
2. **`NULL` → `<library_dir>/config/`** — the bundle the build packed beside
   this library, located from the module's own path (`GetModuleFileNameW` /
   `dladdr`). Platform-specific disk discovery inside the composition root is
   exactly where `R-ARCH-5` puts it, and `../../../docs/df_sil_dll.md` rule 2 already places
   `ParamLoader` there for the same reason;
3. **neither resolvable** → `adasInit` returns `NULL`, same failure contract as
   today.

The bundle contains `project.yaml` (the component's own calibration, including
`BSD_SENSOR_*` / `BSD_CLASS_*`, which the DLL already reads),
`vehicle/ego_params.yaml` from `shared_config`, the port manifest and
`bundle.sha256`. `ParamLoader` reads a directory rather than a file; nothing
else about it changes.

**Admission rule:** a file enters the bundle *iff* the DLL reads it at run time.
Nothing simulation-specific ever enters — no world-model binding, no sensor
error model, no fault injection. Those live with the tooling
(`sim_architecture.md` §5.6's table).

**Mismatch is a warning, not a silent wrong answer.** When the host passes an
explicit path whose project differs from `manifest.project`, the framework says
so — because today the equivalent combination (`cus1/default.yaml` against a
`base`-built DLL, giving cus1 function calibration with base ego params) is
accepted without a word.

`config_bundle_sha256` is empty until stage C5; a host treats an empty value as
"unverified provenance" and reports it rather than assuming agreement.

---

## 4. The Python side

Three classes, in `modules/sim/src/adas_sim/contracts/`.

### 4.1 `SilComponent` — one loaded DLL

```python
comp = SilComponent.load(Path("df_sil.dll"))
comp.manifest.component        # "df"
comp.manifest.outputs          # [PortSpec, …]  — discovered, not hardcoded
handle = comp.init(config_path)
out = comp.exec(handle, dt_s, {"objects": objects_msg,
                               "egoDyn":  veh_dyn_msg,
                               "vehSig":  veh_sig_msg})
out["bsd.outputs"]             # a parsed BsdOutputs, resolved from the manifest
```

`SilComponent` replaces `df_ctypes.py` entirely and is **component-agnostic** —
loading `perception_core_sil.dll` is the same call. What it does internally:

- `ctypes.WinDLL` + `argtypes`/`restype` for the five generic exports;
- `adasAbiVersion()` checked against the framework's expected generation — the
  same loud-failure discipline `df_ctypes.py` already has, kept;
- `adasManifest()` → parse `ComponentManifest`;
- **proto class resolution from the manifest's own descriptor set** (§4.4) —
  no generated Python bindings involved at all. That is the whole of "python to
  C adaptability with protobuf, done properly";
- serialization in, buffer allocation sized by `max_bytes`, parse out;
- `updated == 0` → the port is absent from the returned mapping, not present
  with a stale value.

**`SilComponent` is a Protocol, with two implementations.** `CtypesSilComponent`
loads a real DLL over the generic ABI; `InProcessSilComponent` is a Python
callable plus a manifest. The second is the *same mechanism* `impl: stub:` uses
(§4.2), so it costs nothing extra — and it means every `Pipeline`, `Runner`,
`Session` and wiring-validation test runs with **zero build dependency**. The
ctypes path is exercised separately against a real `df_sil.dll`, skipped when
that build is absent. A framework whose own test suite needs a C++ toolchain is
a framework nobody runs the tests for.

**Two lifetime rules that must survive the rewrite**, because both are real
traps that today's code gets right and a naive rewrite gets wrong:

1. **Keepalive.** ctypes does not hold a reference to the bytes backing a
   pointer. `df_ctypes.make_req_buf()` returns `(struct, keepalive)` and the
   caller must keep the second alive across the call. `SilComponent` owns per-
   port buffers for the lifetime of the handle instead of allocating per tick —
   which fixes the trap *and* removes ~8 allocations per tick.
2. **`valid=0` is not `data=NULL`.** `../../../docs/df_sil_dll.md` §1 records a real bug here:
   an all-default protobuf serializes to zero bytes and `.data()` may be
   `nullptr`, so a `data != nullptr` check wrongly rejected a legitimately empty
   `GenObjectList` and forced `CompState` to `ERROR`. The host's `valid` flag is
   the sole "was something received" signal. Carried forward verbatim into
   `AdasPort` semantics, and asserted by a test.

### 4.2 `Pipeline` — ordered components, wired by name

```python
pipeline = Pipeline.from_yaml(path, project="base")
tick_out = pipeline.exec(dt_s, stimulus)   # dict[port_name, Message]
```

```yaml
project: base
components:
  - name: perception-core
    impl: "dll:{build}/perception_core_sil.dll"
    inputs:
      camera.front: source.camera_front
      radar.rear:   source.radar_rear
  - name: df
    impl: "dll:{build}/df_sil.dll"
    inputs:
      objects: perception-core.gen_object_list
      egoDyn:  source.veh_dyn
      vehSig:  source.veh_sig
```

**`mode:` and `impl:` — two independent fields** (`sim_architecture.md` §5.10).
`mode:` answers *is this stage executed, or are its outputs injected*; `impl:`
answers *if executed, by what*. Splitting them is what makes the per-stage
measured/simulate toggle a one-field flip rather than a pipeline rewrite:

| `mode:` | Behaviour | Needs from the recording |
|---|---|---|
| `simulate` | the stage runs; `impl:` selects what runs it | nothing |
| `measured` | the stage does **not** run; its output ports are injected from the recording, and its declared inputs are not consumed | that stage's output topics |
| `off` | neither run nor injected; consumers see `valid=0` | nothing |

| `impl:` | What runs it | Python host | `sil_host` |
|---|---|---|---|
| `dll:<lib>` | a real component's SIL library | yes | yes |
| `stub:<name>` | a Python model standing in for a missing component | yes | **no** |
| `stubdll:<lib>` | the same idea, built as a DLL on this ABI | yes | yes |

`impl:` is **retained on a `measured` stage** so the toggle is reversible
without re-authoring. `config:` is optional and defaults to the bundle packed
beside the library (§3.4). Today's single-component run is
`- {name: df, mode: simulate, impl: "dll:df_sil.dll"}` with everything wired
from `source.*`.

A `measured` stage is validated at load, not at first tick: the pipeline
resolves each of its declared output ports against the recording's topic index
and **fails at startup naming the missing topics**. A stage whose outputs are
only partly present is a failure, not a partial injection.

A `stub:` is a plain Python callable registered under a name, with the **same
port contract** as the component it stands in for — declared in a
`<name>.ports.yaml` beside it, validated identically. That is what keeps it
substitutable: swapping `stub:carla_ground_truth` for
`dll:perception_core_sil.dll` changes one line and nothing downstream.

Rules:

- Components execute in declaration order, single-threaded — matching
  `FunctionRunner`'s own deliberate choice (`../../../docs/df_sil_dll.md` rule 11: sequential,
  in registration order, likely an ISO 26262 consideration).
- `source.*` refers to the `StimulusSource`; anything else is
  `<component>.<port>` from an earlier component in the list.
- **Wiring is validated against the manifests at load**, not at first exec: a
  type mismatch (`proto_type` differs), a missing required input, or a
  reference to a port no component produces is a startup error naming both
  ends. A forward reference (component B feeding component A that runs first)
  is rejected explicitly rather than silently delivering last tick's value.
- Today's runs are the one-element case, and `df_only.yaml` is checked in as
  such. Nothing about §7's perception scale-out needs a code change here.

### 4.3 `PortBuffer` — sizing

`max_bytes` from the manifest is a hint, not a guarantee. Today's code uses
`make_pro_buf(256)` for every output, chosen once by hand. Two failure modes to
handle explicitly:

- **Too small** — `adasExec` returns 0 today (`"output buffer too small"`).
  `SilComponent` distinguishes this from a genuine failure by re-reading
  `port.len`, growing to it and retrying **once**, then raising if it still
  fails. A grow event is logged, because a manifest whose `max_bytes` is
  chronically low is a manifest bug worth fixing.
- **Unbounded growth** — a `GenObjectList` with 50 slots is not small. Buffers
  are per-handle and reused, so growth is amortised to at most one realloc per
  port per run.

---

### 4.4 Message classes come from the manifest, not from generated bindings

Today every Python host starts with

```python
INTERFACES_GENERATED_PY = MODULES_ROOT / "interfaces" / "build" / "generated_py"
sys.path.insert(0, str(INTERFACES_GENERATED_PY))
from Bsd__Outputs import bsd_outputs_pb2
```

which forces `modules/interfaces` to be **checked out and built** with
`-DADAS_GENERATE_PYTHON_PROTO=ON` before a resim can run — and hardcodes a
component's message types into a host that is meant to be component-agnostic.

`ComponentManifest.descriptor_set` removes both. The host builds classes at run
time:

```python
pool = descriptor_pool.DescriptorPool()
fds = descriptor_pb2.FileDescriptorSet.FromString(manifest.descriptor_set)
for f in fds.file:
    pool.Add(f)
cls = message_factory.GetMessageClass(pool.FindMessageTypeByName(spec.proto_type))
```

Consequences, all of them things the objection in `sim_architecture.md` §5.9
asked for:

- **no `interfaces` checkout and no proto codegen** to resim;
- **no component-specific import anywhere in the framework** — `R-SIM-1`
  satisfied by construction rather than by discipline;
- **the schema and the binary cannot drift.** A DLL always describes the
  messages *it was compiled against*, so a stale `generated_py` can no longer
  disagree with the library that produced the bytes;
- each component owns its own pool, so two components built against different
  `interfaces` revisions can be driven in one pipeline and the mismatch is
  *visible* rather than a parse error.

The framework may still import generated bindings when they happen to be
present (convenient in development, and required for a source that *constructs*
stimuli rather than reading them). It must never *require* them.

---

## 5. OD-2 — generic ABI now, or a descriptor over the current one?

The cheap alternative is to leave `dfExec` alone and describe its positional
signature in YAML that the Python host reads:

```yaml
exec_signature: [handle, dtS, in:objects, in:egoDyn, in:vehSig,
                 out:aeb.outputs, out:bsd.outputs, out:aeb.comp_state, out:bsd.comp_state]
```

Honest comparison:

| | Descriptor over `dfExec` | Generic `adasExec` |
|---|---|---|
| C++ change | none | new header, `adasExec` shim over the existing body, manifest generator, ABI export |
| `sil_host` change | none | one call site |
| Python change | `df_ctypes.py` becomes generic-ish | `df_ctypes.py` deleted |
| Adding a function | still edits the header + bumps ABI + edits the descriptor | one manifest line, generated |
| Second component (`perception-core`) | second bespoke header + second descriptor | works out of the box |
| Front/rear port question (rule 11) | still inexpressible | expressible |
| Cost later | grows with every function and every component | flat |

**Recommendation: the generic ABI, now.** The migration cost is at its
historical minimum — one component has a C API, the second does not exist yet,
and the ABI has already been bumped once for exactly this reason. The
descriptor option is a real fallback if C++ churn must be avoided this quarter;
it is strictly a deferral, not a different destination.

---

## 6. Migration

Staged so the tree works after every step. This is Phase C1 in
[sim_architecture.md](sim_architecture.md) §8.

| Step | Change | Verified by |
|---|---|---|
| 1 | Add `adas_sil_abi.h` + `component_manifest.proto` to `interfaces`. Nothing consumes them yet. | `interfaces` builds; Python bindings generate |
| 2 | `df_sil` exports the five generic entry points **alongside** the existing four. `adasExec` is a thin name-lookup shim onto the current body — both paths live, both tested. | `test_interface_c_api.cpp` gains a generic-path mirror of every existing assertion; results identical |
| 3 | Manifest generator wired to `ENABLED_FUNCTIONS`; `df_sil.ports.yaml` emitted; gtest asserts embedded == emitted | build with `bsd` off ⇒ `bsd.*` absent from both |
| 4 | `adas_sim.contracts.SilComponent` + `Pipeline`; framework drives `df` through the generic path | a resim run produces byte-identical outputs to the `dfExec` path on all 18 recordings |
| 5 | `sil_host/main.cpp` moves to the generic path | `sil_host` runs unchanged end to end |
| 6 | Delete `dfExec`/`dfInit`/`dfShutdown`/`dfApiVersion` and `df_ctypes.py`; `adasAbiVersion()` stays at 1 | nothing references the old symbols; `../../../docs/df_sil_dll.md` updated |
| 7 | **(stage C5)** Build packs the config bundle beside the library; `ParamLoader` reads a directory; `adasInit(NULL)` resolves module-relative; `project`/`config_bundle_sha256` populated | the build output plus its `config/` runs with no Conan cache and no checkout present; `ADAS_EGO_PARAMS_PATH`'s absolute compile-time bake is deleted |

Step 2 is the important one: **both ABIs coexist and are tested against each
other**, so the switch is verified by equality rather than by inspection. This
mirrors the verification discipline already used for the `tools/carla`
relocation (compare resolved values before and after, don't reason about them).

---

## 7. Versioning after the change

Three independent version numbers, deliberately:

| Version | Bumped when | Breaks |
|---|---|---|
| `adasAbiVersion()` | `AdasPort`/`AdasPortSet` layout or `adasExec` semantics change | every host, every component |
| component `version` in the manifest | any port added, removed or renamed | hosts that *pin* a port; a discovering host adapts |
| proto message version (`interfaces`) | schema change to a port's message | governed by existing `interfaces` rules |

The key win: **adding a function no longer touches row 1.** It touches row 2,
and a host that discovers ports rather than hardcoding them keeps working.

A recording therefore carries all three (see
[sim_resim_and_recording.md](sim_resim_and_recording.md)), which is what makes
"this recording was produced by a SUT you no longer have" a detectable
condition instead of a silent misread.

---

## 8. Testing

- **C++ (`df_tests`)** — the existing `InterfaceCApiTest` suite, mirrored onto
  the generic path during migration step 2, plus: unknown input port ignored;
  missing required input behaves as `valid=0`; output buffer too small returns
  the required size; manifest matches `ENABLED_FUNCTIONS`; embedded manifest ==
  emitted YAML.
- **Python (`modules/sim/tests`)** — `SilComponent` against a **stub DLL** built
  in-tree that implements the generic ABI over a trivial echo component, so the
  framework's tests do not depend on `df` being built. Pipeline wiring
  validation (type mismatch, missing producer, forward reference) is pure
  Python and needs no DLL at all.
- **Cross-check** — migration step 4's byte-identical comparison across all 18
  recordings is the acceptance test for the whole change, and is cheap to
  re-run.

---

## 9. Open points

- **One bundle per component, or one per pipeline?** §3.4 gives each component
  its own bundle beside its own library, which is right while components are
  built independently. A multi-component pipeline then holds N bundles that all
  claim a `project` — and nothing yet forces them to claim the *same* one. The
  cheap guard (the pipeline loader rejects mixed projects unless told otherwise)
  is enough until a second component exists; whether a project-level bundle
  should supersede the per-component ones is deferred (`R-VAR-4` already
  anticipates it by putting calibration under `projects/<name>/`).
- **Time and determinism across components.** `dtS` is passed per component
  today. A pipeline must decide whether all components see the same `dtS` (yes,
  for now) and what happens when one runs at a different rate than another
  (real for perception at 30 Hz vs functions at 20 Hz). Scoped in
  [sim_resim_and_recording.md](sim_resim_and_recording.md) §5, not decided here.
- **Non-Windows.** `ctypes.WinDLL` becomes `ctypes.CDLL` behind one helper; the
  header already handles the export macro. Untested until a Linux target
  exists, and flagged rather than assumed.
