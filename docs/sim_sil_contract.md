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

## 0. Background — plain-language, for someone new to this

Read this section first if you haven't worked with a compiled C library
crossing a language boundary before. Sections 1 onward describe the actual
mechanism precisely and assume you already know what an ABI, a DLL export and
protobuf serialization are; this section explains *why any of it matters
here*, assuming none of that.

### The actual problem, without jargon

`df` compiles down to one file: `df_sil.dll`. Anything that wants to use it —
a C++ test program (`sil_host`), a Python script driving a CARLA scenario —
calls into that compiled file through exactly one function, `dfExec()`. Today
that function looks like:

```c
int dfExec(void* handle, double dtS, const DfReqBuf* objects, const DfReqBuf* egoDyn,
           const DfReqBuf* vehSig, DfProBuf* aebOutputs, DfProBuf* bsdOutputs,
           DfProBuf* aebCompState, DfProBuf* bsdCompState);
```

Picture a vending machine with one physical button per snack — that's this
function: one fixed parameter per input or output. It works, but every time a
new snack (a new driving function — ACC, LCA, LDW, LKA, ...) is added, someone
has to physically add a button and rewire the machine, and **everyone who
already uses the machine has to relearn the new layout**, because the layout
itself changed. This already happened once for real: adding BSD alongside AEB
grew this function from 5 parameters to 9, and every caller (`sil_host`, the
Python bridge) had to be edited to match, in lockstep. Six more functions are
still coming (§2's table below runs the numbers out to 23 parameters). Every
one of those additions is a breaking change to a compiled library that ripples
out to every caller by hand.

### What "ABI" means, concretely

"ABI" (Application Binary Interface) just names *the fixed shape of how
outside code calls into a compiled library* — which functions exist, what
order their parameters come in, how the raw bytes of each one are laid out in
memory. It matters here specifically because `df_sil.dll` is **compiled**: by
the time anything calls it, there is no compiler around to check "did you pass
the right type in the right order?" Both sides are just handing raw memory
addresses across a boundary, and if they don't agree on the shape byte-for-byte
the failure is silent corruption, not a compile error. That is also exactly why
the header declaring these functions is plain C, with none of C++'s classes or
namespaces: C's calling rules are simple and universal enough that literally
anything — C, C++, or Python via `ctypes` — can call it without knowing
anything about our internal C++ code.

### The fix: a note, instead of buttons

Instead of "press button 3 and button 7," the redesign hands the machine a
note listing what's wanted, by name:

```c
int32_t adasExec(void* handle, double dtS, const AdasPortSet* in, AdasPortSet* out);
```

`AdasPortSet` is just "an array of named pieces of data" (each one: a name
like `"objects"` or `"bsd.outputs"`, a pointer to bytes, a size, a valid flag).
**This signature never changes again**, no matter how many functions get
added — a new function means a new name appearing in the array at run time,
never a new parameter in the code. A build with only AEB enabled and a build
with all nine functions enabled call `adasExec` with the *identical* C
signature; only the contents of the arrays differ.

### Why there's also a "manifest," and why it's a `.proto` file

If ports are just named blobs, whoever calls the library needs a way to ask
"okay, what ports do you actually have, and what do they mean?" That's the
**manifest** — the vending machine printing its own menu on request: here's
what exists, here's the direction (in/out), here's what type each one is. It
is not the real driving-function data itself (that's still `AebOutputs`,
`BsdOutputs`, ...) — it's a small description *of* that data, generated
automatically from whichever functions were actually compiled in
(`ENABLED_FUNCTIONS`), so it can never drift from the truth.

Every other structured message crossing a component boundary in this codebase
is already a `.proto` file in `interfaces`, for consistency and because it
gives serialization in both C++ and Python for free. The manifest is exactly
that kind of thing, so it is one more `.proto` file, following the same
pattern already used for `AebOutputs`/`VehDyn`/etc. That is the only reason
this change touches `proto/` at all.

### Why `interfaces`, and not `df` or `sil_host`

`interfaces` is this codebase's one shared rulebook repo, specifically so that
when a second component (`perception-core`, eventually) ships its own compiled
library, it does not invent a private, slightly different version of "how do I
talk to my library." If this lived inside `df`, `perception-core` would later
have to copy-paste it (or reinvent it) — two rulebooks free to quietly drift
apart. Defined once in `interfaces`, every library (`df` today,
`perception-core` later) and every caller (`sil_host`, Python tooling, `sim`'s
own viewer) reads from the same page.

`sil_host` specifically is not the right home either — it is *one particular
caller* of a library, not the place the shared agreement between *all*
callers and *all* libraries gets defined. And the new header
(`interfaces/include/adas/adas_sil_abi.h`) lives in its own folder, separate
from `interfaces/cpp/` (C++-only interfaces for our own components talking to
each other), because this header must work for any language at all, with zero
C++ features — it needs to visibly be a different kind of thing.

### `sil_host` and `sim` (Vantage) — one concept, two hosts

Worth stating plainly, since it is easy to assume these are two competing
tools: **they are not.** Both are meant to be driven by the exact same idea —
a component's ports are named and discoverable via its manifest, and each
stage in a run answers two questions: is it actually executed, or is its
output injected from a recording (`mode: simulate` / `measured` / `off`), and
if executed, by what (`impl: dll:` / `stub:` / `stubdll:`). `sim_architecture.md`
§5.10 calls this **"the single concept"** — a deliberate decision (`OD-2`), not
an accident.

The difference between the two tools is capability, not concept:

- **`sil_host`** — a small, dependency-free C++ program. No Python, no
  interpreter overhead, which makes it the one place a timing measurement is
  actually trustworthy, and the closest thing to a real, non-simulation
  integrator using these DLLs. It can run a real compiled library (`dll:`) or
  a compiled stand-in (`stubdll:`), and it can replay recorded values
  (`measured`) — but it can never run a Python-written stand-in (`stub:`),
  because it has no Python interpreter, and it must never grow its own bespoke
  way of inventing test data (`sim_architecture.md` §9). If it needs a
  stand-in, that stand-in is built once as a `stubdll:`, usable by both tools.
- **`adas_sim` (Vantage)** — the Python framework: development, inspection,
  recording, visualization, and every stand-in type, including quick
  Python-only ones.

**Honest gap, not yet closed:** the stated aspiration (`sim_architecture.md`
§9) is that one pipeline description file should run under Vantage *and* run
under `sil_host` unchanged. Today, only the ABI-level compatibility is
actually scheduled: `sil_host` keeps working unmodified once the generic
functions are added (`sim_implementation_plan.md` `S-C1b`), and later one call
site switches it from the old function to the new one (`S-E2`). Building an
actual generic "read the same pipeline file, wire together however many
components it names" engine inside `sil_host` is not yet a tracked, scheduled
stage — it is stated intent, not yet built. Tracked as an open point below and
as `OQ-11` in `sim_requirements.md` §11, rather than left as an assumption.

### The ABI is a skeleton, not the architecture

Worth being explicit about, because it is easy to conflate the two: `adasExec`
and the other four functions are deliberately **empty of architecture**. This
skeleton does not know how many components exist, what they are called, or how
they are wired together — the same way a standard electrical socket does not
know what appliance will plug into it or how a house's rooms are laid out. It
only guarantees that whatever plugs in speaks the same shape: named ports in,
named ports out, discoverable via a manifest. That emptiness is the point — it
is what let this survive AEB, then AEB+BSD, and will let it survive
ACC/LCA/LDW/LKA and `perception-core` without ever changing again.

**The actual architecture is everything built *on top of* that skeleton**: how
many components exist and what each one does, how their ports get wired
together (the `mode:`/`impl:` pipeline model, §5.10 above), who is allowed to
run what (`sil_host`'s narrower boundary vs. Vantage's full range), and where
that model still has a real hole (`OQ-11`). None of that lives in
`adas_sil_abi.h` itself — it lives in the pipeline/manifest design
(`sim_architecture.md`, `sim_sil_contract.md` §4) and in whichever host is
doing the composing. A single component's `adasExec` call is never where two
components meet; that composition always happens one level up, in the host.

### Where to go from here

Sections 1 onward here (and `sim_architecture.md` §5.10/§9) describe the
actual mechanism in implementation-level detail; `sim_implementation_plan.md`'s
`S-C1a`/`S-C1b`/`S-C1c` stages are the checkbox-tracked order this is actually
being built in.

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

/* The one place this number is spelled out. Every component's adasAbiVersion()
   returns exactly this — never its own hardcoded literal, or two compiled
   libraries could silently disagree about which generation they speak.
   Bumped only when the structs or the call semantics above change — NOT when
   a component adds or removes a port.                                         */
#define ADAS_SIL_ABI_VERSION 1

ADAS_SIL_API int32_t adasAbiVersion(void);

/* Component identity + its port manifest, as a serialized
   adas.sil.ComponentManifest (see §3.2). Callable before adasInit.
   Returns the number of bytes written, or the required size if cap is too
   small (classic two-call pattern). */
ADAS_SIL_API size_t adasManifest(uint8_t* data, size_t cap);

/* configPath: the project's config bundle, or NULL to use the bundle packed
   beside this library (<library_dir>/config/, resolved from the module's own
   path). An explicit path always wins — see §3.4.
   Returns NULL when the configuration cannot be resolved. NEVER returns a
   handle carrying silently-defaulted calibration: a run that produces
   plausible numbers from no configuration is the failure NR-SIM-4 forbids,
   and it is indistinguishable from a correct run at every later layer.       */
ADAS_SIL_API void* adasInit(const char* configPath);

/* One cycle. Ports are matched BY NAME; order is irrelevant. A port the
   component does not know is ignored. A port it requires but does not receive
   is treated exactly as valid=0 is treated today.
   dtS is float seconds, NOT integer nanoseconds, deliberately: it is what
   every component's exec(dtS) already takes, and changing it would mean
   touching src/component/** (rule 9). Framework time stays integer ns
   (P-8) and converts in exactly one place, CtypesSilComponent.exec (§4.1).
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

  // This stage's declared cycle time (R-SIM-18). Rate is DISCOVERED, exactly
  // like the port set: the pipeline derives its base grid as the GCD of the
  // declared periods, and a period that is not an integer multiple of that
  // grid is a load error naming both numbers. 0 means "undeclared" — the
  // pipeline then runs the stage every tick and says so in the run manifest.
  // Component-level rather than per PortSpec: a due tick governs the whole
  // exec(), and R-SIM-18's hold semantics (outputs held, updated=False,
  // age_s growing) are a property of the stage that did not run, not of an
  // individual port. A component whose functions genuinely need different
  // rates is two stages, not one manifest carrying two periods.
  uint64 period_ns          = 10;
}

message PortSpec {
  string name          = 1;   // "objects", "aeb.compState"
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
period_ns: 50000000          # 20 Hz, R-SIM-18
inputs:
  - {name: objects, proto_type: adas.perception.GenObjectList, optional: false}
  - {name: egoDyn,  proto_type: adas.common.VehDyn,            optional: false}
  - {name: vehSig,  proto_type: adas.common.VehSig,            optional: true}
outputs:
  - {name: aeb.outputs,   proto_type: adas.df.AebOutputs, max_bytes: 256, owner_function: aeb}
  - {name: aeb.compState, proto_type: adas.df.CompState,  max_bytes: 256, owner_function: aeb}
  - {name: bsd.outputs,   proto_type: adas.df.BsdOutputs, max_bytes: 512, owner_function: bsd}
  - {name: bsd.compState, proto_type: adas.df.CompState,  max_bytes: 256, owner_function: bsd}
```

*(`proto_type` values above are the real package names `interfaces` compiles —
`adas.common.VehDyn`, `adas.df.AebOutputs`. An earlier draft of this section
invented `adas.vehicle.*` / `adas.aeb.*`, which exist nowhere.)*

Adding LCA appends two output lines. No header edit, no host edit, no ABI bump.

**Port naming rules** (freeze these, they become `R-SIM` rules):

- lowercase-initial, dot-separated: `<function>.<port>` for function-owned
  ports, bare `<port>` for component-level ones;
- the segment before the dot is the same `ENABLED_FUNCTIONS` token used by
  `src/component/<fn>/` and `tests/<fn>/` — one vocabulary, three places;
- **the segment after the dot is byte-identical to the `ReqPort`/`ProPort`
  member name in that function's `<fn>_ports.hpp`** — `aeb.compState`, because
  the member is `compState`. This is `N-1` applied to the second half of the
  name: the whole promise is that `grep -rn compState` returns the vertical
  slice (ports header → manifest → `adasExec` dispatch → topic → signal path →
  `expect:` string), and a port called `aeb.comp_state` breaks it at the first
  hop. **`snake_case` is the proto *field* convention (`R-NAME-4`) and stops
  at the message boundary; a port name is a C++-side identifier travelling
  outward, so it follows `R-NAME-2` camelCase.** A port whose name does not
  match a real member is a build-time error (`UT-C1b-11`), not a review note;
- a port name is **API**: renaming one is a breaking change to the *manifest*,
  which is versioned by the component's own version, not by the ABI version;
- the still-open front/rear question (rule 11) becomes expressible without any
  ABI change: `front.objects` and `rear.objects` are just two names. This
  document does not decide it — it removes the reason it could not be decided.

**One table, two readers.** `buildManifest()` and `adasExec`'s dispatch must
**iterate one static port table**, never two hand-written lists that happen to
agree. Two lists is the `R-SIM-16` failure ("a second description free to drift
from the manifest") in its most damaging form, because `adasExec` *silently
ignores an unrecognised port name* for forward compatibility: a manifest typo
therefore produces a host that dutifully supplies a port the DLL never reads,
`valid == 0` downstream, neutral outputs, and a green run that computed
nothing. Declaring the ports once removes the failure rather than testing for
it.

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
3. **neither resolvable** → `adasInit` returns `NULL`.

**This is *not* "the same failure contract as today", and an earlier draft of
this section said it was.** Today's `dfInit` swallows an unreadable config:
`ParamLoader`'s constructor catches `YAML::Exception` and leaves an empty node,
so every function initialises on its own defaults and `dfInit` hands back a
perfectly valid handle. Passing `NULL` therefore produces a run that computes
plausible numbers from no calibration, reports its built `project` in the
manifest, and is indistinguishable from a correct run at every later layer —
the exact substitution `NR-SIM-4` forbids and the one `R-SIM-3a` exists to make
impossible. `adasInit` owes the stricter contract from the moment it exists,
**not** from the moment `S-C5` packs a real bundle: until then `NULL` is
unresolvable and must fail, because "unresolvable" is the honest answer.
`dfInit`'s own behaviour is left alone (`S-C1b` is additive; changing it would
alter the positional path `sil_host` still calls) — the strictness lives in
`adasInit`, which is the one that made the promise.

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
                 out:aeb.outputs, out:bsd.outputs, out:aeb.compState, out:bsd.compState]
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
- ~~**Time and determinism across components.**~~ **Closed by `R-SIM-18`**
  (`OQ-2`): a stage declares `period_ns` in its manifest (§3.2), the pipeline
  derives the base grid as the GCD of the declared periods, a non-multiple
  period is a load error naming both numbers, and a stage that is not due holds
  its outputs (`updated=False`, `age_s` from integer nanoseconds). Perception at
  30 Hz beside functions at 20 Hz is therefore expressible without a decision
  per pipeline. Built in `S-C1c` (`UT-C1c-20/21`).
- **Non-Windows.** `ctypes.WinDLL` becomes `ctypes.CDLL` behind one helper; the
  header already handles the export macro. Untested until a Linux target
  exists, and flagged rather than assumed.
- **`sil_host` has no generic pipeline reader yet (`OQ-11`).** §0 and
  `sim_architecture.md` §9 state the intent that one pipeline description file
  should run unchanged under both Vantage and `sil_host`. Today only ABI-level
  compatibility is scheduled (`S-C1b`, `S-E2`) — a real C++ engine inside
  `sil_host` that parses the same pipeline YAML and wires together an
  arbitrary set of named components is not yet a tracked stage. Until it
  exists, wiring a second component (e.g. `perception-core`) into `sil_host`
  means hand-editing `main.cpp`, still on the same named-port/manifest model,
  just without the "point it at the same file Vantage reads" convenience.
