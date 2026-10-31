// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `LoadRunSpec` (`SW-0005`, design §3.5) -- parses the JSON text
///   `emit_run_spec`/`write_run_spec` produced into a `RunSpec` tree.
///
///   **Scoped, honestly, for this pass** (`WP-05`, `IMP-0412`): the design
///   also wants `LoadRunSpec` to rehash every `sources[].path` on disk and
///   refuse a mismatch against the emitted `sha256`. That needs both a
///   SHA-256 implementation and real file I/O -- neither belongs in a
///   "parse this string" function bolted on under time pressure, and
///   `design §3.3a`'s own rule ("the probe reads through the same
///   interfaces the run uses") argues the rehash belongs behind
///   `io.hpp::Reader` (`WP-06`, not yet built) rather than a second,
///   independent file reader invented here. `LoadRunSpec` opens no file;
///   the rehash-and-compare step is a follow-up once `io.hpp` exists to
///   do it through the one interface a real run also uses.
/// @author Pavan Karimajji

#include "simcore/runspec.hpp"

#include <initializer_list>

#include "third_party/nlohmann/json.hpp"

namespace simcore {

namespace {

using Json = nlohmann::json;

Error MakeError(std::string expected, std::string found, std::string where) {
  return Error{Kind::Authoring, std::move(expected), std::move(found), std::move(where), ""};
}

// IMP-0004: the one schema string this reader loads.
constexpr const char* kRunSpecSchema = "adas.sim.runspec/2.0";

// Thrown by the checks below and caught once in `LoadRunSpec`, which turns
// it into the same `Result::Fail` every other refusal here returns.
struct LoadFailure {
  Error error;
};

// Keys an earlier schema carried that the run setup no longer has
// (`VANTAGE_Architecture.md` §2.3, `gone`). A setup that carries one is
// refused, never read and ignored (`D18 (4)`).
bool IsRetiredKey(const std::string& key) {
  return key == "sampling" || key == "on_missing" || key == "delay_steps" || key == "grid_step_ns" ||
         key == "order" || key == "grid" || key == "period_ns";
}

// IMP-0002, IMP-0049: every key of `node` must be one the schema names. The
// error names the key and where it is (top level, or the stage, port or
// input that holds it).
void RequireKnownKeys(const Json& node, std::initializer_list<const char*> allowed, const std::string& where) {
  if (!node.is_object()) {
    throw LoadFailure{MakeError("an object", node.dump(), where)};
  }
  for (auto it = node.begin(); it != node.end(); ++it) {
    bool known = false;
    for (const char* name : allowed) {
      if (it.key() == name) known = true;
    }
    if (known) continue;
    Error error = MakeError("only keys the run setup schema names", "key '" + it.key() + "'", where);
    if (IsRetiredKey(it.key())) {
      error.hint = "'" + it.key() + "' is retired and is never read (VANTAGE_Architecture.md section 2.3)";
    }
    throw LoadFailure{std::move(error)};
  }
}

// IMP-0003: a `⊘` value is the key present and an integer; there is no
// default for it anywhere in the engine.
std::int64_t RequireInteger(const Json& node, const char* key, const std::string& where) {
  const std::string full = where == "top level" ? std::string(key) : where + "." + key;
  if (!node.contains(key)) {
    throw LoadFailure{MakeError("an integer value for '" + full + "' (no default exists)", "absent", full)};
  }
  const Json& value = node.at(key);
  if (!value.is_number_integer()) {
    throw LoadFailure{MakeError("an integer value for '" + full + "'", value.dump(), full)};
  }
  return value.get<std::int64_t>();
}

std::optional<std::int64_t> OptionalInt64(const Json& node) {
  if (node.is_null()) return std::nullopt;
  return node.get<std::int64_t>();
}

// WP-11: `index` is `null` | an integer | the literal string `"*"` --
// `resolve_address`'s own closed index grammar (`[i]`/`[*]`, never a
// predicate), reaching the wire format now that `MutationAddress` has
// somewhere to put it (`runspec.hpp`'s own note on this addition).
struct ParsedIndex {
  std::optional<int> index;
  bool all_elements = false;
};

ParsedIndex ParseMutationIndex(const Json& node) {
  if (node.is_null()) return {};
  if (node.is_string()) {
    if (node.get<std::string>() != "*") {
      // Same exception family LoadRunSpec's own top-level try/catch
      // already handles (Json::exception) -- no new catch clause needed.
      throw Json::type_error::create(302, "mutations[].address.index string must be '*'", &node);
    }
    return {std::nullopt, true};
  }
  return {node.get<int>(), false};
}

ImplRef ParseImpl(const Json& node, const std::string& where) {
  RequireKnownKeys(node, {"kind", "path", "pattern", "search"}, where);
  ImplRef impl;
  impl.kind = node.at("kind").get<std::string>();
  impl.path = node.at("path").get<std::string>();
  impl.pattern = node.at("pattern").get<std::string>();
  for (const auto& entry : node.at("search")) {
    impl.search.push_back(entry.get<std::string>());
  }
  return impl;
}

SpecPort ParsePort(const Json& node, const std::string& where) {
  RequireKnownKeys(node, {"name", "dir", "kind", "proto_type", "record", "fixed_slots", "bulk", "buffer_depth"}, where);
  SpecPort port;
  port.name = node.at("name").get<std::string>();
  port.dir = node.at("dir").get<std::string>();
  port.kind = node.at("kind").get<std::string>();
  port.proto_type = node.at("proto_type").get<std::string>();
  port.record = node.at("record").get<std::string>();
  const auto& fixed_slots = node.at("fixed_slots");
  if (!fixed_slots.is_null()) {
    port.fixed_slots = fixed_slots.get<bool>();
  }
  port.bulk = node.at("bulk").get<bool>();
  port.buffer_depth = RequireInteger(node, "buffer_depth", where);
  return port;
}

SpecInput ParseInput(const Json& node, const std::string& where) {
  RequireKnownKeys(node, {"port", "producer", "producer_port", "previous_cycle"}, where);
  SpecInput input;
  input.port = node.at("port").get<std::string>();
  input.producer = node.at("producer").get<std::string>();
  input.producer_port = node.at("producer_port").get<std::string>();
  input.previous_cycle = node.at("previous_cycle").get<bool>();
  return input;
}

SpecStage ParseStage(const Json& node, const std::string& where) {
  RequireKnownKeys(node, {"name", "mode", "impl", "trigger", "clock_period_ns", "abi_version", "config_bundle_sha256",
                          "ports", "inputs"}, where);
  SpecStage stage;
  stage.name = node.at("name").get<std::string>();
  stage.mode = node.at("mode").get<std::string>();
  stage.impl = ParseImpl(node.at("impl"), where + ".impl");
  stage.trigger = node.at("trigger").get<std::string>();
  stage.clock_period_ns = node.at("clock_period_ns").get<std::int64_t>();
  stage.abi_version = node.at("abi_version").get<int>();
  stage.config_bundle_sha256 = node.at("config_bundle_sha256").get<std::string>();
  for (const auto& port : node.at("ports")) {
    stage.ports.push_back(ParsePort(port, where + ".ports[" + port.value("name", std::string("?")) + "]"));
  }
  for (const auto& input : node.at("inputs")) {
    stage.inputs.push_back(ParseInput(input, where + ".inputs[" + input.value("port", std::string("?")) + "]"));
  }
  return stage;
}

SpecMutation ParseMutation(const Json& node, const std::string& where) {
  RequireKnownKeys(node, {"verb", "address", "operands", "window_ns"}, where);
  SpecMutation mutation;
  mutation.verb = node.at("verb").get<std::string>();
  const auto& address = node.at("address");
  RequireKnownKeys(address, {"stage", "port", "path", "index"}, where + ".address");
  mutation.address.stage = address.at("stage").get<std::string>();
  mutation.address.port = address.at("port").get<std::string>();
  for (const auto& segment : address.at("path")) {
    mutation.address.path.push_back(segment.get<std::string>());
  }
  const ParsedIndex parsed_index = ParseMutationIndex(address.at("index"));
  mutation.address.index = parsed_index.index;
  mutation.address.all_elements = parsed_index.all_elements;
  for (const auto& operand : node.at("operands")) {
    mutation.operands.push_back(operand.get<double>());
  }
  const auto& window = node.at("window_ns");
  mutation.window_ns_start = OptionalInt64(window.at(0));
  mutation.window_ns_end = OptionalInt64(window.at(1));
  return mutation;
}

SpecSource ParseSource(const Json& node, const std::string& where) {
  RequireKnownKeys(node, {"path", "sha256", "codec", "ingest", "absent"}, where);
  SpecSource source;
  source.path = node.at("path").get<std::string>();
  source.sha256 = node.at("sha256").get<std::string>();
  source.codec = node.at("codec").get<std::string>();
  // `ingest`/`absent`: optional on read, exactly like `outputs`/`checkpoint`
  // above -- every spec written before 2026-08-28 emitted them as empty
  // arrays and every spec written before THAT omitted them entirely, so a
  // missing key and an empty array must parse the same way (no ingest
  // table, i.e. the recording's topics already are port names).
  //
  // No validation here beyond shape. `SW-0032` puts the parser, the schema
  // and the vocabulary in `WP-12`'s Python side; this reads an
  // already-resolved table, and inventing a second validator here would be
  // the second copy that rule exists to prevent.
  if (node.contains("ingest")) {
    for (const auto& row : node.at("ingest")) {
      RequireKnownKeys(row, {"raw_topic", "port", "origin", "proto_type", "factor", "offset"}, where + ".ingest");
      io::IngestRow parsed;
      parsed.raw_topic = row.value("raw_topic", std::string());
      parsed.port = row.value("port", std::string());
      parsed.origin = row.value("origin", std::string());
      parsed.proto_type = row.value("proto_type", std::string());
      parsed.factor = row.value("factor", 1.0);
      parsed.offset = row.value("offset", 0.0);
      source.ingest.push_back(std::move(parsed));
    }
  }
  if (node.contains("absent")) {
    for (const auto& row : node.at("absent")) {
      RequireKnownKeys(row, {"port", "reason"}, where + ".absent");
      source.absent.emplace_back(row.value("port", std::string()), row.value("reason", std::string()));
    }
  }
  return source;
}

}  // namespace

Result<RunSpec> LoadRunSpec(std::string_view json_text) {
  Json root;
  try {
    root = Json::parse(json_text);
  } catch (const Json::parse_error& exc) {
    return Result<RunSpec>::Fail(
        MakeError("well-formed JSON", exc.what(), "simcore::LoadRunSpec"));
  }

  try {
    // IMP-0004: the schema string is checked first, so a setup of another
    // version is refused on that string and not on whichever of its keys
    // this version no longer names.
    const std::string expected_schema = std::string("schema \"") + kRunSpecSchema + "\"";
    if (!root.contains("schema")) {
      return Result<RunSpec>::Fail(MakeError(expected_schema, "no 'schema' key", "simcore::LoadRunSpec"));
    }
    const Json& schema_node = root.at("schema");
    if (!schema_node.is_string() || schema_node.get<std::string>() != kRunSpecSchema) {
      return Result<RunSpec>::Fail(MakeError(expected_schema, "schema " + schema_node.dump(), "simcore::LoadRunSpec"));
    }
    RequireKnownKeys(root, {"schema", "run_id", "spec_sha256", "sources", "stages", "mutations", "outputs", "checkpoint",
                            "limits", "coherence_verdict", "readiness_limit_steps", "fallback_max_gap"},
                     "top level");

    RunSpec spec;
    spec.schema = kRunSpecSchema;
    spec.run_id = root.at("run_id").get<std::string>();
    spec.spec_sha256 = root.at("spec_sha256").get<std::string>();
    spec.readiness_limit_steps = RequireInteger(root, "readiness_limit_steps", "top level");
    spec.fallback_max_gap = RequireInteger(root, "fallback_max_gap", "top level");

    std::size_t source_index = 0;
    for (const auto& source : root.at("sources")) {
      spec.sources.push_back(ParseSource(source, "sources[" + std::to_string(source_index++) + "]"));
    }
    for (const auto& stage : root.at("stages")) {
      const std::string where = "stages[" + stage.value("name", std::string("?")) + "]";
      if (stage.is_object() && stage.contains("clock_period_ns") && !stage.at("clock_period_ns").is_number_integer()) {
        // SW-0046's Accept clause: a period declared in configuration is
        // integer microseconds/nanoseconds, and a fractional value is
        // refused -- never rounded, because a rounded period accumulates
        // into drift that reads as an algorithm bug (R-SIM-18).
        return Result<RunSpec>::Fail(MakeError(
            "an integer nanosecond value", stage.at("clock_period_ns").dump(), where + ".clock_period_ns"));
      }
      spec.stages.push_back(ParseStage(stage, where));
    }
    std::size_t mutation_index = 0;
    for (const auto& mutation : root.at("mutations")) {
      spec.mutations.push_back(ParseMutation(mutation, "mutations[" + std::to_string(mutation_index++) + "]"));
    }
    spec.coherence_verdict = root.at("coherence_verdict").get<std::string>();
    // WP-14a: optional on read -- every pre-WP-14a spec (including every
    // existing test fixture) omits this key entirely, and that must keep
    // parsing exactly as it did before (no declared output, `outputs.path`
    // stays empty). `.value(..., default)` reads a present sub-key without
    // requiring the other; an absent "outputs" object skips both.
    if (root.contains("outputs") && root.at("outputs").is_object()) {
      const auto& outputs_node = root.at("outputs");
      RequireKnownKeys(outputs_node, {"path", "codec", "livemeas"}, "outputs");
      spec.outputs.path = outputs_node.value("path", std::string());
      spec.outputs.codec = outputs_node.value("codec", std::string());
      // `livemeas` absent: no live measurement. Present: all four geometry
      // values are `⊘` and must be there (IMP-0003).
      if (outputs_node.contains("livemeas")) {
        const auto& live = outputs_node.at("livemeas");
        RequireKnownKeys(live, {"name", "cycle_slot_count", "cycle_slot_size", "bulk_slot_count", "bulk_slot_size"},
                         "outputs.livemeas");
        SpecLiveMeas parsed;
        parsed.name = live.at("name").get<std::string>();
        parsed.cycle_slot_count = RequireInteger(live, "cycle_slot_count", "outputs.livemeas");
        parsed.cycle_slot_size = RequireInteger(live, "cycle_slot_size", "outputs.livemeas");
        parsed.bulk_slot_count = RequireInteger(live, "bulk_slot_count", "outputs.livemeas");
        parsed.bulk_slot_size = RequireInteger(live, "bulk_slot_size", "outputs.livemeas");
        spec.outputs.livemeas = std::move(parsed);
      }
    }
    // IMP-0139: same optional-on-read shape as `outputs` above -- an absent
    // "checkpoint" key (every pre-existing spec) parses to `checkpoint.path`
    // staying empty, which `simEngineCreate` reads as "no checkpoint".
    if (root.contains("checkpoint") && root.at("checkpoint").is_object()) {
      RequireKnownKeys(root.at("checkpoint"), {"path"}, "checkpoint");
      spec.checkpoint.path = root.at("checkpoint").value("path", std::string());
    }
    RequireKnownKeys(root.at("limits"), {"exec_timeout_ms", "severity_exit"}, "limits");
    spec.limits_exec_timeout_ms = root.at("limits").at("exec_timeout_ms").get<int>();
    spec.limits_severity_exit = root.at("limits").at("severity_exit").get<std::string>();

    return Result<RunSpec>::Ok(std::move(spec));
  } catch (const LoadFailure& failure) {
    return Result<RunSpec>::Fail(failure.error);
  } catch (const Json::exception& exc) {
    return Result<RunSpec>::Fail(
        MakeError("every field design §3.1 requires", exc.what(), "simcore::LoadRunSpec"));
  }
}

}  // namespace simcore
