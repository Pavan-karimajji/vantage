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

#include "third_party/nlohmann/json.hpp"

namespace simcore {

namespace {

using Json = nlohmann::json;

Error MakeError(std::string expected, std::string found, std::string where) {
  return Error{Kind::Authoring, std::move(expected), std::move(found), std::move(where), ""};
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

ImplRef ParseImpl(const Json& node) {
  ImplRef impl;
  impl.kind = node.at("kind").get<std::string>();
  impl.path = node.at("path").get<std::string>();
  impl.pattern = node.at("pattern").get<std::string>();
  for (const auto& entry : node.at("search")) {
    impl.search.push_back(entry.get<std::string>());
  }
  return impl;
}

SpecPort ParsePort(const Json& node) {
  SpecPort port;
  port.name = node.at("name").get<std::string>();
  port.dir = node.at("dir").get<std::string>();
  port.kind = node.at("kind").get<std::string>();
  port.proto_type = node.at("proto_type").get<std::string>();
  port.record = node.at("record").get<std::string>();
  port.sampling = node.at("sampling").get<std::string>();
  port.on_missing = node.at("on_missing").get<std::string>();
  const auto& fixed_slots = node.at("fixed_slots");
  if (!fixed_slots.is_null()) {
    port.fixed_slots = fixed_slots.get<bool>();
  }
  return port;
}

SpecInput ParseInput(const Json& node) {
  SpecInput input;
  input.port = node.at("port").get<std::string>();
  input.producer = node.at("producer").get<std::string>();
  input.producer_port = node.at("producer_port").get<std::string>();
  input.delay_steps = node.at("delay_steps").get<std::int64_t>();
  return input;
}

SpecStage ParseStage(const Json& node) {
  SpecStage stage;
  stage.name = node.at("name").get<std::string>();
  stage.mode = node.at("mode").get<std::string>();
  stage.impl = ParseImpl(node.at("impl"));
  stage.period_ns = node.at("period_ns").get<std::int64_t>();
  stage.abi_version = node.at("abi_version").get<int>();
  stage.config_bundle_sha256 = node.at("config_bundle_sha256").get<std::string>();
  for (const auto& port : node.at("ports")) {
    stage.ports.push_back(ParsePort(port));
  }
  for (const auto& input : node.at("inputs")) {
    stage.inputs.push_back(ParseInput(input));
  }
  return stage;
}

SpecMutation ParseMutation(const Json& node) {
  SpecMutation mutation;
  mutation.verb = node.at("verb").get<std::string>();
  const auto& address = node.at("address");
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

SpecSource ParseSource(const Json& node) {
  SpecSource source;
  source.path = node.at("path").get<std::string>();
  source.sha256 = node.at("sha256").get<std::string>();
  source.codec = node.at("codec").get<std::string>();
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
    if (!root.contains("schema")) {
      return Result<RunSpec>::Fail(
          MakeError("a 'schema' key", "absent", "simcore::LoadRunSpec"));
    }
    const auto schema = root.at("schema").get<std::string>();
    if (schema != "adas.sim.runspec/1.0") {
      return Result<RunSpec>::Fail(MakeError(
          "schema \"adas.sim.runspec/1.0\" (this reader's only supported version)",
          schema, "simcore::LoadRunSpec"));
    }

    RunSpec spec;
    spec.schema = schema;
    spec.run_id = root.at("run_id").get<std::string>();
    spec.spec_sha256 = root.at("spec_sha256").get<std::string>();
    const auto& grid_step = root.at("grid").at("step_ns");
    if (!grid_step.is_number_integer()) {
      // SW-0046's Accept clause: a period declared in configuration is
      // integer microseconds/nanoseconds, and a fractional value is
      // refused -- never rounded, because a rounded period accumulates
      // into drift that reads as an algorithm bug (R-SIM-18).
      return Result<RunSpec>::Fail(
          MakeError("an integer nanosecond value", grid_step.dump(), "grid.step_ns"));
    }
    spec.grid_step_ns = grid_step.get<std::int64_t>();

    for (const auto& source : root.at("sources")) {
      spec.sources.push_back(ParseSource(source));
    }
    for (const auto& stage : root.at("stages")) {
      const auto& period = stage.at("period_ns");
      if (!period.is_number_integer()) {
        return Result<RunSpec>::Fail(MakeError(
            "an integer nanosecond value", period.dump(),
            "stages[" + stage.value("name", std::string("?")) + "].period_ns"));
      }
      spec.stages.push_back(ParseStage(stage));
    }
    for (const auto& mutation : root.at("mutations")) {
      spec.mutations.push_back(ParseMutation(mutation));
    }
    for (const auto& name : root.at("order")) {
      spec.order.push_back(name.get<std::string>());
    }
    spec.coherence_verdict = root.at("coherence").at("verdict").get<std::string>();
    // WP-14a: optional on read -- every pre-WP-14a spec (including every
    // existing test fixture) omits this key entirely, and that must keep
    // parsing exactly as it did before (no declared output, `outputs.path`
    // stays empty). `.value(..., default)` reads a present sub-key without
    // requiring the other; an absent "outputs" object skips both.
    if (root.contains("outputs") && root.at("outputs").is_object()) {
      const auto& outputs_node = root.at("outputs");
      spec.outputs.path = outputs_node.value("path", std::string());
      spec.outputs.codec = outputs_node.value("codec", std::string());
    }
    // IMP-0139: same optional-on-read shape as `outputs` above -- an absent
    // "checkpoint" key (every pre-existing spec) parses to `checkpoint.path`
    // staying empty, which `simEngineCreate` reads as "no checkpoint".
    if (root.contains("checkpoint") && root.at("checkpoint").is_object()) {
      spec.checkpoint.path = root.at("checkpoint").value("path", std::string());
    }
    spec.limits_exec_timeout_ms = root.at("limits").at("exec_timeout_ms").get<int>();
    spec.limits_severity_exit = root.at("limits").at("severity_exit").get<std::string>();

    return Result<RunSpec>::Ok(std::move(spec));
  } catch (const Json::exception& exc) {
    return Result<RunSpec>::Fail(
        MakeError("every field design §3.1 requires", exc.what(), "simcore::LoadRunSpec"));
  }
}

}  // namespace simcore
