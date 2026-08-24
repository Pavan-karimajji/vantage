// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   The Resolved Run Spec (IF-09, design doc §3.1/§3.5) -- a POD tree, no
///   inference, no defaults. `LoadRunSpec` is the ONLY way `simcore` learns
///   what to run: no `.yaml` opened, no search path walked, no reference
///   grammar parsed (design §3.2's own enforcement table). The Python
///   producer is `adas_sim/runspec/emit.py::emit_run_spec` -- `DD-02` is
///   reversible at exactly these two symbols plus their Python twins.
///
///   Field names mirror the emitted JSON's own keys (snake_case), a
///   deliberate exception to this codebase's usual camelCase members
///   (R-NAME-2): a wire-format mirror struct that renamed its fields would
///   need a translation table between here and `load.cpp`, which is a
///   second copy of the schema free to drift from the first.
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "simcore/errors.hpp"

namespace simcore {

// design §3.1 -- stages[].impl. No search_path/stem interpretation lives
// here: `path` is already absolute, `search` is an audit trail only
// (SW-0003, SW-0018).
struct ImplRef {
  std::string kind;    // "dll" | "stubdll"
  std::string path;    // absolute, always
  std::string pattern;
  std::vector<std::string> search;
};

// design §3.1 -- stages[].ports[]. `record`/`sampling`/`on_missing` are
// ALWAYS present (SW-0009, SW-0010) -- the engine holds no default table.
struct SpecPort {
  std::string name;
  std::string dir;         // "pro" | "req"
  std::string kind;         // "data" (DD-05 widens this to "static" later)
  std::string proto_type;
  std::string record;
  std::string sampling;     // one of Sampling's five string forms
  std::string on_missing;
  std::optional<bool> fixed_slots;
};

// design §3.1 -- stages[].inputs[]. No reference grammar (SW-0007):
// `producer`/`producer_port` are already split, never a dotted string.
struct SpecInput {
  std::string port;
  std::string producer;
  std::string producer_port;
  std::int64_t delay_steps = 0;
};

struct SpecStage {
  std::string name;
  std::string mode;  // "simulate" | "measured" | "off"
  ImplRef impl;
  std::int64_t period_ns = 0;
  int abi_version = 0;
  std::string config_bundle_sha256;
  std::vector<SpecPort> ports;
  std::vector<SpecInput> inputs;
};

// design §3.1 -- mutations[].address. `path` is field names only; the one
// index (if any) applies to the address as a whole (IMP-0008's own
// documented limit -- `resolve_address`'s Python twin refuses the shape
// this cannot represent rather than losing it silently).
//
// `all_elements` (WP-11's own small, targeted addition): `resolve_address`
// (`runspec/address.py`) has produced this bit in its `ResolvedAddress`
// since `IMP-0008` landed (`WP-05`) -- `index == "*"` -- but `emit.py`'s
// own mutation dict never carried it through, and this mirror struct had
// nowhere to put it if it had. `select`/`drop[*]` (`IMP-0100`) has no real
// shape to build against without it, so it is added here and parsed in
// `load.cpp` (JSON `index: "*"`) rather than deferred a second time.
struct MutationAddress {
  std::string stage;
  std::string port;
  std::vector<std::string> path;
  std::optional<int> index;
  bool all_elements = false;
};

struct SpecMutation {
  std::string verb;  // const | hold | offset | scale | select | drop
  MutationAddress address;
  std::vector<double> operands;
  std::optional<std::int64_t> window_ns_start;
  std::optional<std::int64_t> window_ns_end;
};

// design §3.1 -- sources[]. `ingest`/`absent` are not yet represented here
// (WP-12's own ingest-map parser has not landed -- the Python emitter
// writes them as empty arrays today, IMP-0011's documented scope for this
// pass); adding them is an additive struct change, not a reversal.
struct SpecSource {
  std::string path;
  std::string sha256;
  std::string codec;
};

// design §3.1 -- the top-level `outputs` key. `emit.py::emit_run_spec`
// already carries an `outputs` parameter and the JSON schema already
// declares the key (`{"type": "object"}`, no sub-schema), but until now
// nothing read it back out -- the same "emitted, not yet parsed" gap
// `sources[].ingest`/`absent` were in before this struct's own note on
// them (WP-14a, found attempting WP-15b). `path` empty means "no
// recording output declared", which is also what every existing spec
// that omits the `outputs` key entirely parses to (this key is optional
// on read, matching every pre-WP-14a fixture). `codec` empty means
// "derive from `path`'s own extension", the same convention
// `CodecRegistry::OpenWrite` already applies by construction.
struct SpecOutputs {
  std::string path;
  std::string codec;
};

// IMP-0139's own gap, design-decided 2026-08-24: mirrors `SpecOutputs`
// exactly -- `path` empty means "no checkpoint declared", matching every
// spec (pre- and post- this change) that omits the `checkpoint` key, and
// gated in `simEngineCreate` the identical way `IMP-0426` gates the writer
// on `outputs.path`. Kept as its own top-level key, never derived from
// `outputs.path`, so checkpointing stays independently toggleable from
// output recording (`R-SIM-15`'s explicit-opt-in discipline).
struct SpecCheckpoint {
  std::string path;
};

struct RunSpec {
  std::string schema;
  std::string run_id;
  std::string spec_sha256;
  std::int64_t grid_step_ns = 0;
  std::vector<SpecSource> sources;
  std::vector<SpecStage> stages;
  std::vector<SpecMutation> mutations;
  std::vector<std::string> order;
  std::string coherence_verdict;
  SpecOutputs outputs;
  SpecCheckpoint checkpoint;
  int limits_exec_timeout_ms = 0;
  std::string limits_severity_exit;
};

// SW-0005: refuses a schema string outside the range this reader
// understands, naming both; a missing `schema` key names the omission.
// Never opens a file: `sources[].path`/`impl.path` are read as strings
// only, not dereferenced (SW-0412's own rehash-and-compare step is a
// deliberately separate, not-yet-built concern -- see load.cpp's own
// top-of-file note on why).
Result<RunSpec> LoadRunSpec(std::string_view json);

}  // namespace simcore
