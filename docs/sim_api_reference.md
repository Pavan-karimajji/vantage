# API reference — the symbols an implementation must produce

Status: **normative.** The architecture says *what and why*; the implementation
plan says *in what order*; **this document says exactly what to type.** It
exists so that a stage can be built without inventing a name, a signature or a
schema — every one of which would otherwise be a place where two stages disagree.

Read with: [`sim_naming_and_diagnostics.md`](sim_naming_and_diagnostics.md)
(`N-1..N-13` constrain every name below),
[`sim_portability.md`](sim_portability.md) (`P-1..P-10` constrain every I/O call),
[`sim_architecture.md`](sim_architecture.md) (why).

**Reading rule.** A signature here is a contract. Adding a parameter is a design
change and belongs in the architecture first. Adding a *keyword-only* parameter
with a default is not.

---

## 0. Conventions used below

- Python **3.12**, `from __future__ import annotations` in every module.
- `@dataclass(frozen=True, slots=True)` for value types; plain classes for
  things with behaviour; `typing.Protocol` for every extension point, so
  implementors need no base class and tests need no mocks.
- Times are **integer nanoseconds** (`P-8`). A parameter named `*_s` is a float
  and appears only at a human boundary (CLI, YAML, labels).
- Paths are `pathlib.Path` (`P-1`). Never `str`.
- Everything raising is one of §9's four error classes (`DG-5`).

---

## 1. Package map

```
modules/sim/src/adas_sim/
├── core/          tick, session, history, runner, ids, logging
├── model/         project configuration -> geometry               (R-SIM-3)
├── scene/         Prim / Layer / Scene, frames                    (R-SIM-2)
├── contracts/     SilComponent, Pipeline, ports, overrides, loader
├── io/            format codecs: read + write                     (R-SIM-14)
├── sources/       world-model clients                             (R-SIM-14)
├── view/          transport + viewport STATE -- no pixels         (R-SIM-17)
├── render/        theme, raster, matplotlib, foxglove             (R-SIM-2)
├── check/         expectations, report                            (R-SIM-8)
├── cli/           argument parsing only                           (GT-9)
└── app/           Vantage: shell, workspaces, panels              (GT-9)
```

`app/` and `cli/` contain **no logic** (`GT-9`). `core/`, `model/`, `scene/`,
`contracts/`, `io/`, `check/` never import `view/`, `render/`, `cli/` or
`app/`.

**There is deliberately no `sinks/`.** An early draft had one for recording
writers; `R-SIM-14` made readers and writers one symmetric codec table, so
writers live in `io/`. Two homes for one concept is how `sim convert` would
have become a feature instead of a consequence.

**`view/` is state, `render/` is pixels.** Keeping them apart is what lets
`UT-B2-3` assert that toggling a layer re-renders without re-executing.

Enforced by `UT-A1-6` (import-direction test over the module graph).

---

## 2. `core/` — time, values, sessions

### 2.1 `core/ids.py`

```python
def new_run_id(*, inputs: Mapping[str, str], clock: datetime | None = None) -> str:
    """`N-9` correlation id: '<UTC compact>-<8 hex>'.

    `inputs` is hashed to the hex suffix and MUST contain, sorted by key:
    pipeline_sha, recording_sha, project, component_build_shas (joined),
    bundle_sha, overrides_repr, seed. Two runs with identical inputs therefore
    share an id -- and a differing result under one id is a determinism finding,
    not a mystery.
    """
```

### 2.2 `core/tick.py`

```python
Origin = Literal["measured", "truth", "mocked", "simulated", "overridden"]

@dataclass(frozen=True, slots=True)
class PortValue:
    name: str                  # fully qualified, `N-2`: "df.aeb.outputs"
    message: Any               # a decoded protobuf message, or None when invalid
    origin: Origin
    valid: bool = True
    updated: bool = True       # False when held from an earlier tick (multi-rate)
    age_s: float = 0.0         # 0.0 when `updated`; else time since production
    def __repr__(self) -> str: ...        # `N-7`

@dataclass(frozen=True, slots=True)
class Tick:
    index: int
    t_ns: int                  # integer, accumulated from dt_ns -- never a float sum
    dt_ns: int
    ports: Mapping[str, PortValue]        # keyed by fully qualified name
    pose: Pose2D                          # ego pose in the world frame
    @property
    def t_s(self) -> float: return self.t_ns / 1e9      # derived, never fed back
    def port(self, name: str) -> PortValue: ...          # raises PortNotFound
```

### 2.3 `core/session.py`

```python
class Session:
    """An immutable, indexable run. The viewer's ONLY input (`R-SIM-13`)."""

    run_id: str
    name: str
    ticks: Sequence[Tick]
    events: Sequence[Event]
    meta: RunManifest
    deterministic: bool        # False for a live sim -> disables recompute-from-0

    @classmethod
    def open(cls, path: Path, *, codec: str | None = None) -> Session: ...
    def at(self, index: int) -> Tick: ...
    def seek_ns(self, t_ns: int) -> int: ...     # -> tick index, boundary-exact
    def signal(self, path: str, *, project: str = "base") -> tuple[tuple[int, object], ...]:
        """One address space (`NR-SIM-8`): '<component>.<port>.<field>' ·
        'source.*' · 'truth.*' · 'derived.*'. Delegates to
        `core/signals.resolve_series` (`S-B3` slice 6, not `view/signals.py`
        as `sim_implementation_plan.md`'s checklist names it -- checked with
        the user: `check/`'s expectation evaluator (`S-D6`) needs this too,
        headless, and `core/` is where every consumer can depend on it in
        the normal direction). Two corrections from the sketch this
        replaces: `object`, not `float` -- a state lane's signal (`§7.3`) is
        categorical, and forcing it through `float` would have made this
        method lie about what `derived.*`/state ports actually carry;
        `project` is real because `derived.*` resolution needs a
        `ProjectModel` (`core/history.LayerCtx`) and the sketch had no way
        to supply one -- defaults to `base` (`R-VAR-4`), matching every
        other `project=` in this codebase.
        """
    def __len__(self) -> int: ...
    def __repr__(self) -> str: ...
```

### 2.4 `view/transport.py` — the head (`R-SIM-17`)

*(In `view/`, not `core/`: transport is view state. `core/` must stay
importable by a headless resim that has no cursor.)*

```python
class Transport:
    head_tick: int             # furthest computed; ahead of it is EMPTY, not zero
    cursor: int
    review_mode: bool          # True once the user steps back from the head

    def play(self) -> None: ...
    def pause(self) -> None: ...
    def step_forward(self, n: int = 1) -> None: ...      # executes iff at head
    def step_back(self, n: int = 1) -> None:
        """Enters review mode. Never calls exec(); there is no inverse."""
    def advance(self, n: int, *, on_progress: Callable[[int, int], None],
                cancel: CancelToken) -> int:
        """Advance-N as ONE cancellable job. Returns the tick reached, which
        becomes `head_tick`. An expectation failing mid-advance drops a marker
        and does NOT abort (`viz 5.2`)."""

    def resume_options(self) -> tuple[ResumeOption, ...]:
        """Exactly two, both named. `RECOMPUTE_FROM_ZERO` is offered only when
        `session.deterministic`; otherwise it carries `.reason`. Silently
        continuing from a rewound tick is not representable in this API --
        that is the point (`R-SIM-17`)."""
```

### 2.5 `core/logging.py` (`N-10`)

```python
class Event(StrEnum):          # CLOSED vocabulary; adding a value is a review
    RUN_START = "run_start";      RUN_END = "run_end"
    STAGE_INIT = "stage_init";    STAGE_SHUTDOWN = "stage_shutdown"
    EXEC_OK = "exec_ok";          EXEC_FAIL = "exec_fail"
    PORT_MISSING = "port_missing"; PORT_OVERRIDDEN = "port_overridden"
    DEGRADE = "degrade";          EXPECT_PASS = "expect_pass"
    EXPECT_FAIL = "expect_fail";  BUNDLE_MISMATCH = "bundle_mismatch"

def log(event: Event, *, run: str, tick: int | None = None,
        stage: str | None = None, port: str | None = None,
        dur_us: int | None = None, msg: str = "", **fields: object) -> None:
    """Emits ONE line, fields in fixed order (`N-10`). `msg` comes last and may
    never replace a field."""
```

---

## 3. `contracts/` — stages, ports, wiring

### 3.1 `contracts/component.py`

```python
class SilComponent(Protocol):
    """A stage that can execute. Two implementations ship:
    `CtypesSilComponent` (a real library) and `InProcessSilComponent`
    (a Python callable + a manifest) -- the latter is what `impl: stub:` uses
    and what lets every framework test run with no C++ built."""

    name: str
    manifest: ComponentManifest

    def init(self, config_path: Path | None = None) -> None: ...
    def exec(self, dt_ns: int, inputs: Mapping[str, bytes]) -> Mapping[str, bytes]: ...
    def shutdown(self) -> None: ...
    def abi_version(self) -> int: ...
```

The wire form is `bytes` deliberately: the framework never needs generated
bindings (`R-SIM-11`), decoding lazily from the manifest's `FileDescriptorSet`.

**Added at `S-C1c`, filling gaps this section left implicit** -- the
Protocol above was already normative; the concrete shapes below were not
spelled out anywhere and had to be invented during implementation, so they
are recorded here rather than left to drift across a second, undocumented
copy:

```python
#: `adas_sil_abi.h`'s own `#define ADAS_SIL_ABI_VERSION` -- the framework's
#: expected generation, compared against the live `adasAbiVersion()` at
#: load, never read FROM the component.
ADAS_SIL_ABI_VERSION = 1

@dataclass(frozen=True, slots=True)
class PortSpec:                        # component_manifest.proto's PortSpec, decoded
    name: str
    proto_type: str
    max_bytes: int = 0
    optional: bool = False
    owner_function: str = ""
    doc: str = ""

@dataclass(frozen=True, slots=True)
class ComponentManifest:               # component_manifest.proto's ComponentManifest, decoded
    component: str
    version: str
    abi_version: int
    build_id: str
    inputs: tuple[PortSpec, ...]
    outputs: tuple[PortSpec, ...]
    project: str
    config_bundle_sha256: str
    descriptor_set: bytes
    period_ns: int

def parse_manifest(raw: bytes) -> ComponentManifest: ...   # decodes adasManifest()'s bytes

def resolve_message_classes(manifest: ComponentManifest) -> Mapping[str, type]:
    """Message classes for every `proto_type` a manifest's ports use, from
    `descriptor_set` alone (`R-SIM-11`) -- no generated bindings, no
    `interfaces` checkout. Keyed by fully-qualified `proto_type`."""

class CtypesSilComponent:
    def __init__(self, path: Path) -> None: ...   # path already resolved -- see 3.2

class InProcessSilComponent:
    def __init__(
        self, name: str, manifest: ComponentManifest,
        fn: Callable[[int, Mapping[str, bytes]], Mapping[str, bytes]],
    ) -> None: ...
```

`ComponentManifest`'s own schema (needed to decode `adasManifest()`'s bytes
in the first place) is hand-built from `google.protobuf.descriptor_pb2` --
same technique as `scene/codec.py`'s `Scene` IR -- rather than importing
`interfaces`'s generated binding, since it is the bootstrap schema and has
no `descriptor_set` of its own to resolve from (`R-SIM-11` held literally).

### 3.2 `contracts/loader.py` — the ONE place a library is resolved (`P-5`)

```python
def resolve_library(stem: str, *, search: Sequence[Path]) -> Path:
    """'df_sil' -> df_sil.dll | libdf_sil.so | df_sil.so, by platform.

    Raises `EnvironmentError_` naming EVERY pattern tried and EVERY directory
    searched (`N-8`). A pipeline file is portable as written because this is the
    only place the platform is consulted."""
```

### 3.3 `contracts/pipeline.py`

```python
Mode = Literal["simulate", "measured", "off"]

@dataclass(frozen=True, slots=True)
class Stage:
    name: str
    mode: Mode
    impl: str | None                       # "dll:…" | "stub:…" | "stubdll:…" | "legacy:…"
    inputs: Mapping[str, str]              # port -> producer ref or "measured:/…"
    overrides: Mapping[str, Override] = field(default_factory=dict)   # `R-SIM-15`, field path -> verb

@dataclass(frozen=True, slots=True)
class SeveredChain:                        # added at S-C1c -- referenced below, never shaped until now
    upstream: str
    upstream_port: str
    measured: str
    downstream: str
    downstream_port: str

class Pipeline:
    name: str
    stages: tuple[Stage, ...]
    base_grid_ns: int                      # added at S-C1c -- GCD of every declared period_ns (R-SIM-18)

    @classmethod
    def load(
        cls, path: Path, *, search: Sequence[Path] = (),
        components: Mapping[str, SilComponent] | None = None,
        recording: RecordingReader | None = None,
    ) -> Pipeline:
        """Validates at LOAD, never at first tick (`§5.14`). Checks, in order:
        1. every input port resolves (executing producer, or recording topic);
        2. `mode: measured` against a recording lacking the topics -> error;
        3. severed chain -> see `severed_chains()`;
        4. port type match against both manifests;
        5. no forward reference, no cycle.
        Every failure is `AuthoringError` and names both ends.

        `search`/`components`/`recording` added at `S-C1c` (keyword-only,
        defaulted -- not a signature change under this doc's own reading
        rule): `search` forwards to `resolve_library` for `dll:`/`stubdll:`
        stages; `components` supplies already-built stages -- the only way
        to satisfy `impl: stub:` until `S-C2`'s registry exists, and how a
        test injects a fake component with no file on disk; `recording` is
        what check 2 above reads `.topics()` from."""

    def exec(
        self, dt_ns: int, stimulus: Mapping[str, bytes], *,
        measured: Mapping[str, Mapping[str, bytes]] | None = None,
    ) -> Mapping[str, Mapping[str, bytes]]:
        """Added at `S-C1c` -- not shown in an earlier draft of this section,
        which listed `Pipeline`'s declarative methods only; execution turned
        out to need a real entry point and this is it. Runs EVERY stage
        EVERY call, single-rate, in declaration order: `stimulus` supplies
        `source.*` values, `measured` supplies each `mode: measured` stage's
        recorded outputs for this tick (`Pipeline` does no I/O itself --
        reading a recording is the caller's job). `mode: off` needs no
        special-casing: an `off` stage's entry is simply never added to the
        tick's output map, so a downstream reference to it is absent from
        whatever consumes it -- `valid=0`, the same convention
        `SilComponent` already uses for a missing input. Returns every
        stage's output ports this tick, keyed by stage name."""

    def step(
        self, dt_ns: int, stimulus: Mapping[str, bytes], *,
        measured: Mapping[str, Mapping[str, bytes]] | None = None,
    ) -> Mapping[str, PortValue]:
        """Added at `S-C1c` -- the multi-rate-aware entry point (`R-SIM-18`),
        built on `exec`'s per-stage dispatch. Advances the `Pipeline`'s own
        clock by `dt_ns`; a stage runs (or injects) only on its due tick
        against `base_grid_ns` -- `period_ns == 0` (undeclared) means due
        every call. A stage that is not due HOLDS its last output rather
        than re-running: `updated=False`, `age_s` the exact elapsed time
        since it was last actually due, from integer nanoseconds (`P-8`,
        never accumulated as float seconds). Returns one `core.tick.PortValue`
        per DECLARED output port, keyed by fully qualified `"<stage>.<port>"`
        name (matching `Tick.ports` directly, so a caller can fold a run's
        `step()` outputs straight into a `Tick`) -- the full declared port
        set every call, held or fresh, which is `R-SIM-10`'s invariant
        carried into multi-rate: a downstream stage wired to a not-due
        producer still sees that producer's last real value, not a gap."""

    def severed_chains(self) -> tuple[SeveredChain, ...]:
        """A `measured` stage between two `simulate` stages on ONE data path
        (`R-SIM-10`). Returned, not raised: the GUI auto-closes by default and
        the CLI warns. Forcing it open is legal and badges the orphan.
        `off -> measured -> simulate` is deliberately not flagged -- nothing
        computed into the gap."""

    def with_mode(self, stage: str, mode: Mode, *, close_gaps: bool = True) -> Pipeline:
        """Returns a NEW pipeline. `close_gaps` flips intervening stages, which
        is what makes the GUI toggle honest; the caller keeps the old object for
        undo."""

    def to_yaml(self) -> str: ...          # round-trips byte-identically (`UT-D8-1`)
```

### 3.4 `contracts/override.py` — the CLOSED verb list (`R-SIM-15`)

```python
class OverrideVerb(StrEnum):
    CONST = "const"; HOLD = "hold"; OFFSET = "offset"; SCALE = "scale"

@dataclass(frozen=True, slots=True)
class Override:
    verb: OverrideVerb
    value: float | None = None             # required for const/offset/scale
    def apply(self, current: float, first: float) -> float: ...

def parse_override_verb(raw: str, *, where: str) -> OverrideVerb:
    """Added at `S-C1c`. The closed-list gate a pipeline's `overrides:` YAML
    goes through: a verb outside the four is `AuthoringError`, never a
    silent extension point."""
```

There is no `expression`, no `python`, no `callable`. A fifth verb is a design
change requiring a requirement; the survey in `docs/py` records why
(`FR-SIM-45`).

**Scope note (`S-C1c`):** `Override`/`OverrideVerb` and `Stage.overrides` are
declared and load-validated at `S-C1c` -- a verb outside the closed four is
caught at `Pipeline.load` time. Actually applying an override to a live
port's bytes, between wiring and `exec`/`step`, is `S-D6`'s job (its own
checklist entry already expects this); `Pipeline.exec`/`step` above do not
consult `Stage.overrides` yet.

---

## 4. `io/` — format codecs (`R-SIM-14`)

**`S-A4Δ` (`OD-9`, `CR-SIM-4`) added the second, capture-time stamp.** The
message shape gained an element and `Capabilities` gained a field; nothing
else in this section's shape changed.

```python
@dataclass(frozen=True, slots=True)
class Capabilities:
    embedded_schemas: bool
    random_access: bool
    meta_blocks: bool
    arbitrary_topics: bool
    round_trips: bool            # False => cannot be a resim input
    capture_time: bool            # a second, capture-time stamp (`S-A4Δ`)
    write_only: bool = False

class RecordingReader(Protocol):
    capabilities: ClassVar[Capabilities]
    def meta(self) -> RunManifest: ...
    def topics(self) -> Mapping[str, TopicInfo]: ...   # schema + provenance
    def messages(self, topics: Sequence[str] | None = None
                 ) -> Iterator[tuple[str, int, int | None, bytes]]:
        """(topic, log_time_ns, capture_time_ns, bytes). `capture_time_ns` is
        `None` when unknown -- never defaulted to `log_time_ns` -- and a
        recording whose manifest predates `CAPTURE_TIME_MANIFEST_VERSION`
        reports `None` for every message regardless of its bytes."""

class RecordingWriter(Protocol):
    capabilities: ClassVar[Capabilities]
    def open(self, path: Path, meta: RunManifest,
             topics: Mapping[str, TopicInfo]) -> None: ...
    def write(self, topic: str, log_time_ns: int, payload: bytes, *,
               capture_time_ns: int | None = None) -> None: ...
    def close(self) -> None: ...

def register(ext: str, *, reader=None, writer=None) -> None: ...
def reader_for(path: Path) -> RecordingReader: ...
def writer_for(path: Path) -> RecordingWriter:
    """Raises `AuthoringError` naming the missing capability when the target is
    `write_only` and the caller wanted a recording (`R-SIM-14`)."""
```

**Four methods each**, as promised. `io/csv.py` is `write_only=True,
round_trips=False` — which is how an export can never be fed back (`UT-D7-5`).

---

## 5. `scene/` — geometry, never pixels (`R-SIM-2`)

**Corrected at `S-A3`** (`sim_implementation_plan.md`'s own finding, `GT-7`):
this section previously showed a narrower 7-kind `Prim` with a generic
`coords: tuple[float, ...]` and no `pick_id`/`z`/`alpha` — which cannot
represent a `Heatmap` (a 2D array) or `Image` (bytes) at all. The shape
below is what `sim_visualization_spec.md` §2 and `sim_architecture.md` §5.3
(the master design doc) both specified and what is actually implemented in
`scene/types.py`.

```python
PrimKind = Literal[
    "polyline", "polygon", "box", "circle", "ellipse",
    "points", "arrow", "text", "grid", "heatmap", "image",
]                                   # closed set (sim_visualization_spec.md §2)

@dataclass(frozen=True)
class BulkRef:                     # a coordinate into the recording (`NR-SIM-43`, `OD-7`)
    topic: str
    log_time_ns: int
    field: str = ""
    count: int = 0
    encoding: str = ""

@dataclass(frozen=True, slots=True)
class Prim:
    kind: PrimKind
    # -- universal --
    frame: str = "ego"              # `R-COORD-1`
    style: str = ""                 # SEMANTIC token: "zone.entry" -- never a colour
    pick_id: str | None = None
    z: int = 0
    alpha: float = 1.0
    width_px: float | None = None   # the ONE pixel exception: line weight
    offset_px: tuple[float, float] | None = None   # and label offset
    # -- everything below is `None` unless `kind` uses it; all METRES/RADIANS --
    points_m: tuple[tuple[float, float], ...] | None = None   # polyline/polygon/points
    closed: bool = False                                      # polyline
    filled: bool = True                                        # polygon
    hatch: str | None = None                                   # polygon
    marker: str | None = None                                  # points
    cx_m: float | None = None; cy_m: float | None = None       # box/circle/ellipse
    length_m: float | None = None; width_m: float | None = None; height_m: float | None = None   # box
    yaw_rad: float | None = None                               # box, ellipse
    r_m: float | None = None                                   # circle
    a_m: float | None = None; b_m: float | None = None         # ellipse
    x_m: float | None = None; y_m: float | None = None         # arrow, text
    dx_m: float | None = None; dy_m: float | None = None       # arrow
    text: str | None = None; anchor: str | None = None         # text
    spacing_m: float | None = None; extent_m: float | None = None   # grid
    x0_m: float | None = None; y0_m: float | None = None
    cell_dx_m: float | None = None; cell_dy_m: float | None = None
    values: tuple[tuple[float, ...], ...] | None = None        # heatmap
    data: bytes | None = None; format: str | None = None       # image
    bulk: BulkRef | None = None     # reference in place of inline data (`NR-SIM-43`)
    derived: bool = False          # `R-SIM-7` stopgap marker, per-prim (`OD-6`)

@dataclass(frozen=True, slots=True)
class Layer:
    id: str                        # "df.aeb.corridor" -- fully qualified (`N-2`)
    group: str
    prims: tuple[Prim, ...] = ()
    label: str = ""                 # human text for the layer panel
    z: int = 0                      # draw order within the scene
    level: int = 1                 # 1 always-on .. 3 internal debug
    default_on: bool = True
    derived: bool = False          # `R-SIM-7` stopgap marker

class LayerProvider(Protocol):
    id: ClassVar[str]
    def __call__(self, ctx: LayerCtx) -> Sequence[Layer]: ...
```

**`Layer.__post_init__` (added `S-A3Δ`, `OD-6`/`OD-7`):** a `Layer(derived=False)`
containing a `Prim(derived=True)` raises `AuthoringError`; a prim inlining more
than `scene/types.py`'s `MAX_INLINE_PRIM_ELEMENTS` elements (points, heatmap
cells, or image bytes) raises `ContractError` naming the layer, the prim kind
and the count -- reference it with `BulkRef` instead (`NR-SIM-43`).

A provider **must not**: compute a pixel, read the viewport, import a renderer /
`cv2` / `matplotlib` / Qt, touch disk, or hold state between ticks. `LayerCtx`
gives it the tick, a read-only `HistoryView`, the `FrameTree` and the
`ProjectModel` — everything it may legitimately need, so the bans cost nothing.

Enforced by `GT-2` (import scan) and `UT-B1-13` (a provider called twice with
the same ctx returns equal layers).

---

## 6. `model/` — configuration is the source of geometry (`R-SIM-3`)

```python
class ProjectModel:
    project: str
    bundle_sha256: str
    bundle_origin: Literal["embedded", "library", "checkout"]   # ALWAYS stated

    @classmethod
    def resolve(cls, *, recording: Path | None, library_dir: Path | None,
                explicit: Path | None) -> ProjectModel:
        """Order: explicit > embedded-in-recording > library config/ > checkout.
        The chosen origin is recorded and shown in the HUD -- two readers
        agreeing by coincidence is the failure this prevents (`R-SIM-3a`)."""

    def ego(self) -> EgoModel: ...
    def footprint(self, class_name: str) -> Footprint:
        """A fallback rather than a measurement carries
        `assumed_geometry=True`, and is drawn with that style (`R-SIM-3`)."""
    def sensor(self, sensor_id: str) -> SensorModel: ...
    def camera(self, camera_id: str) -> CameraModel: ...
```

---

## 7. `check/` — expectations are data (`R-SIM-8`)

```python
class Predicate(StrEnum):
    EQUALS = "equals"; ALWAYS = "always"; NEVER = "never"
    DURING = "during"; WHENEVER = "whenever"; BECOMES = "becomes"

@dataclass(frozen=True, slots=True)
class Expectation:
    signal: str                  # one address space, `NR-SIM-8`
    predicate: Predicate
    value: object
    within_s: float | None       # REQUIRED for BECOMES; no default tolerance
    anchor_from: str | None      # provenance when derived offline

    def evaluate(self, session: Session) -> ExpectResult: ...
```

`Expectation.load` raises `AuthoringError` when a `BECOMES` carries no
`within_s` — a silent default is how a timing test stops testing timing.

---

## 8. `sources/` — world-model clients

```python
class Source(Protocol):
    name: ClassVar[str]
    def emits(self) -> frozenset[str]:
        """What this world can produce: 'objects_truth', 'camera/<id>',
        'radar_detections', 'radar_cube', 'veh_dyn'. A pipeline asking for more
        is a startup error naming BOTH ends (`R-SIM-10`)."""
    def start(self, scenario: Scenario) -> None: ...
    def poll(self) -> Mapping[str, bytes]: ...
    def stop(self) -> None: ...
```

Kept separate from `io/` on purpose: different abstractions, different reasons
to change — and, per `N-12`, a traceback then says whether the *file* or the
*world* lied.

---

## 9. Errors — the closed taxonomy (`DG-5`)

```python
class SimError(Exception):
    exit_code: ClassVar[int]
    def __init__(self, *, expected: str, found: str, where: str,
                 hint: str = "") -> None: ...
    # `N-8`: a message is never an identifier alone. The constructor makes the
    # four parts mandatory, so a bad message is a TypeError at author time.

class AuthoringError(SimError):    exit_code = 2   # the YAML is wrong
class EnvironmentError_(SimError): exit_code = 3   # a library/bundle is missing
class ContractError(SimError):     exit_code = 4   # ABI/manifest mismatch
class InternalError(SimError):     exit_code = 70  # a framework bug

class ProvenanceWarning(Warning):
    """A WARNING, never an error. A project mismatch, a missing bundle or an
    unknown-provenance recording degrades visibly and the run continues
    (`R-SIM-3a`, `R-SIM-6`). Raising here would make the honest path the
    inconvenient one, which is how people start suppressing warnings."""
```

Anything uncaught is `internal` **by definition** — failing to classify is the
bug, even when bad input provoked it.

---

## 10. CLI surface (`cli/`, argument parsing only)

| Verb | Signature | Stage |
|---|---|---|
| `sim record` | `<scenario> -o <out> [--project]` | S-C2 |
| `sim run` | `<scenario> [--record] [--view] [--pipeline]` | S-C2 |
| `sim resim` | `<recording> [--view] [--save]` | S-C1c |
| `sim view` / `render` | `<session> [--preset] [--at]` | S-B3 / S-B4 |
| `sim check` | `<scenario-set> [--report]` | S-C3 |
| `sim diff` | `<a> <b>` | S-D1 |
| `sim list` | `ports\|topics\|layers\|signals\|scenarios\|pipelines` | S-D6 |
| `sim probe` | `<lib>` | S-D6 |
| `sim explain` | `<name> [--session]` | S-D6 |
| `sim doctor` | `[--pipeline] [--recording]` | S-D6 |
| `sim convert` | `<in> <out>` | S-D7 |
| `sim export` | `<in> <out> --ports …` | S-D7 |
| `sim batch` | `<recordings…> --pipeline [-j N] [--report]` | S-D7 |

Entry point: `sim = adas_sim.cli:main` in `pyproject.toml` — so the launcher is
generated per platform rather than written by us (`P-6`).

---

## 11. What this document does not fix

Deliberately, so an implementing session knows where judgement is expected:

- **Internal helpers.** Anything not listed here is free.
- **Panel widget structure** inside `app/` — only its behaviour is specified
  (`sim_player.md`).
- **Renderer internals** — the `Renderer` protocol is fixed
  (`render(scene, viewport) -> bytes|None`); how it draws is not.
- **The `legacy:` adapter's config shape** — scoped in S-D6, unimplemented until
  a binary that needs it exists.
