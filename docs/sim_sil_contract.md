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

**Honest gap — identified as `OQ-11`, closed 2026-07-31 by scheduling it.** The
stated aspiration (`sim_architecture.md` §9) is that one pipeline description
file should run under Vantage *and* under `sil_host` unchanged. That was
**stated intent, not built**: `S-C1b` keeps `sil_host` working unmodified once
the generic functions are added, and `S-E2` later switches one call site — but
neither gives `sil_host` a pipeline reader. Today it is 54 lines of `main.cpp`
driving exactly one component, so wiring in a second one means hand-editing it.

That is now **`S-C7`**, a tracked stage with its own tests, because the
capability is what `sil_host` is *for*: its whole job is to run a complete
pipeline in simulation with no Python in the process (`FR-SIM-65`). One
component ticked in a loop is not a pipeline. See §9's first bullet for the
reasoning and the scope.

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

**Where the declaration lives, revised 2026-07-31 (`R-SIM-22`).** `S-C1b` put
the declaration in C++ — a named constant per port, plus two static tables, plus
a `buildManifest()` walking them, plus a dispatch block per function. That was
right for one component and is wrong for N: it is ~400 lines per component of
mechanical restatement, and it is `D1`'s own shape one level up (arch `D12`). The
declaration moves to **data**, beside the other per-component build data:

```yaml
# modules/df/conf/ports.yaml — the ONE declaration. R-VAR-3's neighbour.
component: df
period_ns: 50000000            # OQ-12: should come from the config bundle
inputs:
  - {name: objects, proto_type: adas.perception.DetectedObjectList, binds: detectedObjects, functions: [aeb, bsd]}
  - {name: egoDyn,  proto_type: adas.common.VehDyn,            binds: egoDyn,       functions: [aeb, bsd]}
  - {name: vehSig,  proto_type: adas.common.VehSig,            binds: vehSig,       functions: [bsd], optional: true}
outputs:
  - {name: "<fn>.outputs",   proto_type: "adas.df.<Fn>Outputs", binds: outputs,   max_bytes: 512, per_function: true}
  - {name: "<fn>.compState", proto_type: adas.df.CompState,     binds: compState, max_bytes: 256, per_function: true}
```

The build generates the constant block, both tables, `buildManifest()` and the
`adasExec` dispatch bindings from this, gated by `ENABLED_FUNCTIONS`
(`R-VAR-5`). Three properties follow, and each one is a defect that stops being
possible rather than a test that has to catch it:

- **`binds:` is the `ReqPort`/`ProPort` member name**, so `N-1`'s "the segment
  after the dot is byte-identical to the member" is *generated* rather than
  asserted by `UT-C1b-12`. The `aeb.comp_state`-vs-`compState` defect that the
  Phase C review found becomes unrepresentable.
- **The generated file is a build output** — never edited, never checked in. The
  checked-in `<component>.ports.yaml` stays a *dump of what was compiled*
  (`df_manifest_dump`), which is a reviewable diff, not a third hand-maintained
  copy.
- **An ABI evolution is one generator change**, not an eight-repo edit. This is
  the property `R-BUILD-6` wants and cannot give here, because these files are
  not byte-identical across components — each names its own ports.

**The handle-member-naming convention (`S-C1d`, frozen 2026-08-04).** `binds:`
names only the `ReqPort`/`ProPort` member (`detectedObjects`) — not which
port-set instance on the component's handle struct owns it, since a
component may or may not split its ports by function. The generator infers
this from `conf/ports.yaml` itself, never a second field or CLI flag:

- **Gated** (any port declares `functions:`/`owner_function`, e.g. `df`'s
  `aeb`/`bsd`): the handle member is `<fn>ReqPorts`/`<fn>ProPorts`
  (`handle.aebReqPorts.detectedObjects`) — one port-set instance per function,
  matching `DfHandle`'s existing shape.
- **Ungated** (no port ever names a function, e.g. `vdy` — a single
  always-on function with no `ENABLED_FUNCTIONS` split): the handle member is
  the bare singular `reqPorts`/`proPorts` (`handle.reqPorts.vehSig`), matching
  `VdyHandle`'s existing shape.

A component's shape is a property of its own port declarations, not a choice
the generator or a caller makes — so onboarding a third component costs
exactly the same `conf/ports.yaml`, whichever shape it turns out to have.

*What does **not** change:* `src/component/**` is still untouched, the shim is
still a name-lookup onto the existing body (`df_sil_dll.md` rule 9), and the
manifest is still generated from `ENABLED_FUNCTIONS` so it cannot drift from
what was compiled. Only the authorship of the mechanical part moves.

#### 3.2a The consumer half — binding a port name from outside the DLL

`R-SIM-4` fixed how a port is *declared and discovered*. It left the other end
implicit, and the gap showed up immediately (`R-SIM-21`, arch `D13`): the first
real plug-in written against this contract,
`modules/df/sim/layers/bsd.py`, addresses its own component's port as the
literal `"df.bsd.outputs"`.

That literal is wrong in a way worth being precise about, because "it works
today" is true:

| Segment | What it actually is | Why that breaks |
|---|---|---|
| `df` | the **stage name** from a pipeline YAML — `Pipeline` builds addresses as `f"{stage.name}.{port.name}"` | an authoring choice, not an identity. Rename the stage and the binding dies |
| `bsd.outputs` | a C++ constant in another repo | bound to the dispatch by `UT-C1b-11/12`, and to this file by nothing |

And the failure is silent: `scene/registry.py`'s `requires` gate returns `()`
when a port is missing, so a broken binding renders as *no overlay* — which on
screen means "the algorithm did not warn". A debugging tool that answers a
question wrongly and confidently is worse than one that refuses to answer.

**The contract, therefore:**

1. A plug-in names a port **relative to its own component**, with an explicit
   self-reference: `self.bsd.outputs`. It never spells a stage name, because it
   cannot know one.
2. **Resolution happens once, at load**, against the manifests actually present
   in the run — producing the concrete address (`df.bsd.outputs`, or
   `driving_functions.bsd.outputs`, whatever the pipeline called it).
3. **A name that resolves against no manifest is an `AuthoringError`** naming
   the plug-in, the port requested, and every port the component's manifest does
   declare (`N-8`). Never an empty layer, never a warning.
4. The same resolver serves **every** consumer of a port address — layer
   `requires`, `Prim` field lookups, `expect:` predicates (`S-C3`), workspace
   files (`S-D3`), plot panels and CSV export column selection. One resolver,
   because four resolvers is how the third one starts accepting a name the first
   one rejects.

This is `R-SIM-4`'s own sentence — *"ports are named and discovered, never
positional"* — applied to the half that reads them.

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
  string proto_type    = 2;   // fully-qualified: "adas.perception.DetectedObjectList"
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
  - {name: objects, proto_type: adas.perception.DetectedObjectList, optional: false}
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
   `DetectedObjectList` and forced `CompState` to `ERROR`. The host's `valid` flag is
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

- **Too small** — this paragraph originally claimed `adasExec` returns 0
  on an undersized buffer; **found wrong by testing at `S-C1c`, against the
  real `df_sil.dll`**: `adasExec` returns success (1) even when one output
  port was undersized -- that port is simply left `updated=0` while every
  other port still writes normally. `CtypesSilComponent` therefore detects
  undersize from the ports themselves (`port.len > port.cap`, checked on
  every port unconditionally after every call), never from the return
  code -- gating on the return code would mean the grow path silently never
  fires. Distinguished from a genuine failure this way, `SilComponent`
  grows to the reported `port.len` and retries **once**, then raises if it
  still fails. A grow event is logged, because a manifest whose `max_bytes`
  is chronically low is a manifest bug worth fixing.
- **Unbounded growth** — a `DetectedObjectList` with 50 slots is not small. Buffers
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

- ~~**One bundle per component, or one per pipeline?**~~ **Closed 2026-07-31 —
  per component, permanently** (`OQ-1`, `OD-11`). See below.
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
- ~~**`sil_host` has no generic pipeline reader yet (`OQ-11`).**~~ **Closed
  2026-07-31 — it is being built** (`FR-SIM-65`, stage `S-C7`). The question
  was never really open: §0 and `sim_architecture.md` §9 asserted the capability
  as fact while this list carried it as undecided, and two documents disagreeing
  about whether something exists is a `GT-7` failure rather than a genuine
  open point. The honest choices were to build it or to stop claiming it, and
  the claim is load-bearing — *"one concept, two hosts"* is a slogan without it,
  and a second host that cannot read the pipeline file is a second host with its
  own composition model, which is the thing §9's standing rule exists to
  prevent. It is also small: read the pipeline file, resolve N libraries, read
  each manifest, wire ports by name, tick on the derived base grid. Every piece
  it needs already exists in `interfaces` as C and protobuf after `S-C1a`, and
  the semantics are already specified (`R-SIM-10` for `mode:`/`impl:`,
  `R-SIM-18` for the schedule). `sil_host` executes `dll:`/`stubdll:` stages
  plus `mode: measured` injection, and never a Python `stub:` — the boundary is
  unchanged, only the composition is no longer hand-written in `main.cpp`.
- **The generated shim's failure mode is different from a hand-written one's
  (`R-SIM-22`).** A hand-written shim fails at compile time, on the line you
  typed. A generated one can fail at *generate* time, in a file nobody opened,
  with an error naming the generator instead of the declaration — which is the
  same complaint `R-BUILD` has about machinery that hides its inputs. The
  mitigation is stated so `S-C1d` does not have to rediscover it: the generator
  validates `conf/ports.yaml` against the ports header **before** emitting
  anything, and every diagnostic names the YAML key and line, never the emitted
  C++. A generator that reports errors in its own output is a generator that
  gets worked around.

---

### 9.1 `OQ-1` — one bundle per component, permanently

*Resolved 2026-07-31. `OD-11`.*

**A bundle is a build output of a component; a pipeline is a run-time
composition.** That sentence settles it. A per-pipeline bundle would have to be
either *built* — but pipelines are not built, they are written — or *assembled by
hand* from N components' calibration, which creates a second place to edit a
value and is precisely what `R-SIM-3a` forbids ("the bundle is a build output,
never a second place to edit"). It would also make `adasInit(NULL)`'s
module-relative resolution the *exception* rather than the rule, since the host
would pass an explicit path to every component — turning §3.4's deliberate escape
hatch into the default path.

So the multi-component problem is real but it is a **consistency question, not a
storage question**, and it is answered by two load-time checks:

1. **Project agreement — a warning with an escape.** Every component's manifest
   reports its `project`. The pipeline loader compares them; a disagreement names
   both components and both projects. It is overridable
   (`allow_mixed_projects: true`), because a deliberate cross-project experiment
   is legitimate and §5.6 already preserves it — but the override is declared,
   badged in the HUD and recorded in the run manifest, like every other override
   in this design.
2. **Ego-parameter agreement — a hard error, with no escape.** Every bundle
   carries its own copy of `shared_config`'s `vehicle/ego_params.yaml`. Copies
   built from one `shared_config` revision agree; copies that do not mean two
   components in one pipeline disagree about the wheelbase. That is a wrong
   result *and* a wrong picture simultaneously, with no legitimate reading, so it
   fails at load (`§5.14`'s hard-fault class) rather than warning.

The second check is the reason this question was worth asking: the per-component
bundle's one genuine risk is N copies of a shared file, and nothing was checking
them. It costs one hash comparison.

**Rejected.** *A project-level bundle superseding the per-component ones* — see
above; and `R-VAR-4`'s `projects/<name>/` is the **authoring** home, which is
already true and is not the same as a delivered artifact. *No check at all,
until a second component exists* — the previous position; it is cheaper to write
the comparison than to remember to add it, and the failure it prevents is silent.

### 9.2 `OQ-12` — `period_ns` is calibration, declared per function

*Resolved 2026-07-31. `OD-12`. Answers `DF-1`'s open half.*

`R-SIM-18` is right that a rate is **declared by the component** — a rate a host
could override would let the picture disagree with what the ECU runs. But `df`
declares it as `constexpr uint64_t kPeriodNs = 50000000`, so a rate sweep needs a
rebuild: the "frozen in code instead of config" shape in the one place `NR-SIM-6`
explicitly forbids it. Three decisions close it.

**1. It comes from the config bundle and is *reported* through the manifest.**
The manifest stays the discovery surface (nothing about `R-SIM-18`'s GCD
scheduler changes); the *number* is calibration, read at `adasInit` from the
bundle like every other calibrated value.

**2. The key is in integer microseconds.** `<COMPONENT>_<FN>_PERIOD_US: 50000`,
per `R-NAME-3` (ALL_CAPS, domain prefix, unit suffix). Not seconds: a YAML float
of `0.05` is not exactly representable in binary, so seconds-to-nanoseconds
introduces a rounding step — and a rounded period accumulating into drift that
reads as an algorithm bug is the exact failure `R-SIM-18` already refuses to
tolerate in the GCD check. Not milliseconds: 12.5 ms exists. Integer
microseconds is exact, covers every plausible rate, and multiplies to nanoseconds
by 1000.

**3. Per function, with a per-component default — decided now because deciding
later is expensive.** Today `df`'s functions all run at 20 Hz, so per-component
is *sufficient*; it is not *cheap to change later*. Moving to per-function
afterwards changes the manifest schema, the scheduler's unit of dueness, and
every consumer's reasoning about `updated`/`age_s` — because *"the stage is due"*
becomes *"this port is due"*. Doing it now costs one optional key in
`conf/ports.yaml` and one field on `PortSpec`.

**The part that could have gone wrong, and how it is avoided.** `adasExec` runs a
whole DLL, so if AEB is 20 Hz and BSD is 10 Hz inside one library, the host
cannot execute half a component. The temptation is to pass a due-set into
`adasExec` — which grows the ABI, i.e. `D1` returning. Instead:

> **The component is scheduled at the GCD of its own functions' periods; the
> ports carry their function's period so `updated` and `age_s` are correct per
> port; and the DLL decides internally what to run — it already reads the same
> bundle and already knows its `ENABLED_FUNCTIONS`.**

No ABI parameter, no host edit, and `R-SIM-18`'s base grid is unchanged — it just
takes more periods as input.

**And it is self-checking.** `AdasPort` already carries `updated` across the
boundary, so the DLL reports what it actually did while the framework's schedule
only *predicts* it. **The DLL's flag is authoritative; a disagreement is
reported, not hidden** — a component whose internal rate gating has drifted from
its declared period is exactly the kind of defect that otherwise surfaces months
later as an unexplained stale value.

**Rejected.** *Leave it a C++ literal* — `NR-SIM-6` forbids it and a sweep is the
core calibration workflow. *Let the pipeline set the rate* — `R-SIM-18`'s stated
reason stands: the picture would be free to disagree with the ECU. *Per component
only, revisit if functions diverge* — the revisit is a schema change plus a
semantics change to `updated`, which is the definition of expensive-later.

---

## 10. What a component owes the framework — the checklist (`NR-SIM-48`)

*Added 2026-08-06 by sim audit run 3.* `R-SIM-16` says *"a component
onboards itself"*. That is only true if what **onboarded** means is written
down, and until this section it was not — it was spread across `R-SIM-20`,
`R-SIM-22`, `R-SIM-23`, `R-SIM-24` and `R-SIM-3a`, one obligation each, with no
place a component could be checked against all of them at once.

**The measurement that produced this section.** `vdy` is a real second
component on the generic ABI — `S-C1d`'s own second-component proof, 18/18
gtest — and it carries **no `modules/vdy/sim/` directory at all**. Neither does
`perception-core`. So every component-side obligation below is satisfied
**exactly once, by `df`**. A rule proven once has been *implemented*; it has not
been *shown to generalise*, and the component it was designed against is the
worst possible witness for it.

### The table

| # | Artifact | Required? | Rule | `df` | `vdy` | `perception-core` |
|---|---|---|---|---|---|---|
| 1 | `conf/build.yml` — variants, requires, platforms | **required** | `R-VAR-3` | ✅ | ✅ | ✅ |
| 2 | `conf/ports.yaml` — the ONE port declaration | **required** | `R-SIM-22` | ✅ | ✅ | ✅ *(2026-08-06)* |
| 3 | `src/component/**` port structs the generator reads | **required** | `R-SIM-22` | ✅ | ✅ | ✅ *(2026-08-06)* |
| 4 | `src/platform/<name>_sil/` — the generated generic-ABI shim | **required** | `R-SIM-4`, `R-SIM-22` | ✅ | ✅ | ✅ *(2026-08-06, `ST-D6-4`'s own build queue row 1)* |
| 5 | `src/project/<p>/default.yaml` — calibration | **required** | `R-VAR-4` | ✅ | ❌ **corrected 2026-08-06** — no `src/project/` directory exists in `vdy` at all; its ego-state calibration is read entirely from the cross-component `adas-shared-config` package instead. The `✅` above was never measured; `component_checklist` (`ST-D6-4`) is what found it | ✅ *(2026-08-06)* |
| 6 | Config bundle packed beside the library | **required** | `R-SIM-3a` | ✅ | ❌ **corrected 2026-08-06** — `vdy_sil/CMakeLists.txt` calls no `adas_pack_config_bundle()` and nothing else packs one; `adasInit(NULL)` has nothing to resolve. Same measurement gap as row 5 | ❌ *(deliberate — mirrors `vdy_sil`, `ST-D6-4`'s build queue row 1 own account)* |
| 7 | `<COMPONENT>_<FN>_PERIOD_US` in calibration | **required** | `OD-12`, `R-SIM-18` | ✅ | ❌ **corrected 2026-08-06** — follows row 5: no `src/project/` means no calibration file to declare it in. `vdy_interface_c.cpp`'s own `periodLookupUs` passthrough was never wrong about this — ungated, so nothing calls it — but the manifest's declared source, row 5, was never really there | ✅ *(declared, real; still unread by the generated `periodLookupUs` path — `perception-core` is ungated, same as `vdy`)* |

**Rows 5–7, `vdy` column, corrected 2026-08-06 (`ST-D6-4`, sim build queue
row 3).** The three `✅`s above were asserted, not measured, when this table
was first written — `component_checklist()`, the mechanism this row
built, is what actually looked and found `modules/vdy/src/project/` does not
exist. This is not a regression: `vdy` never had it. It is the table's own
claim that was wrong, corrected here rather than quietly left — and it is
exactly the class of finding this checklist exists to surface (row 3's own
framing: *"this is the check that would have caught row 2"*). **Not fixed
here** — `vdy`'s calibration wiring is real, functional source, outside a
docs-only row's mandate, same discipline the audit itself already applies
elsewhere in this ledger.
| 8 | `sim/plugin.yaml` + `sim/layers/**` | **conditional** | `R-SIM-20` | ✅ | ➖ *legitimately none* | ✅ *(2026-08-06)* |
| 9 | `sim/ingest/**` — the map for foreign recordings | **conditional** | `R-SIM-23` | ✅ | ➖ | ❌ *(none yet; no foreign recordings)* |
| 10 | `sim/pipelines/**` | optional | `R-SIM-16` | ✅ | ❌ | ❌ |
| 11 | `sim/viewpoints.yaml`, `sim/sensor_models/**` | optional | `R-SIM-9`, `FR-SIM-15` | ✅ | ❌ | ❌ |
| 12 | **`sim/tolerance.yaml`** — determinism bounds | **conditional** | `R-SIM-24` | ❌ | ❌ | ❌ |
| 13 | Scenarios with `expect:` blocks | **conditional** | `R-SIM-8`, `CR-SIM-3` | ✅ *(18)* | ❌ | ❌ |

Legend: ✅ present · ❌ missing · ➖ **legitimately** absent, and that
distinction is the whole point of the table.

### Three readings of it, in order of how much they matter

**1. Row 12 is a gap for every component, including `df`.** `R-SIM-24` mandates
a per-component tolerance file with `default: exact`, integers and enums
non-overridable, and **a mandatory `why:` on every row**. It exists **nowhere in
the repository**. So determinism axes C (rebuilt binary) and D (different
machine) — the two the rule declares *measured and tracked* rather than gated —
have **no declared bound to compare against, for anybody**. `sim determinism`
ships and works; what it reads on those two axes is absent, so the axes it was
built to measure are the axes it cannot currently report a verdict on.

**2. Row 8's `➖` for `vdy` is correct and must stay expressible.** `vdy`
produces `VehDyn` — a state vector, not geometry. It has nothing to draw, so it
needs no layer provider, and a checklist that failed it for that would be
wrong. **This is why `NR-SIM-48` is deliberately not a gate.** The value is that
an absence becomes *declared* rather than *unnoticed* — `R-SIM-23`'s `absent:`
discipline, one level up.

**3. Row 4 is `perception-core`'s only real blocker**, and it is the one thing
audit run 3 deliberately did not write, because it could not compile it. See
`modules/perception-core/docs/perception_core_decomposition.md` §4 for the exact
remaining file list and the exact build commands.

### How this stops being prose

`ST-D6-4` (`S-D6`): **`sim doctor --component <name>`** reports a component
against this table, run against `df`, `vdy` and `perception-core`, producing the
**same shape** of report and naming each absence with whether it is legitimate
or a gap. A checklist nobody runs is a checklist that describes the day it was
written.
