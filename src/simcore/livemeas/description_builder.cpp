// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `BuildMeasDescription` (`IMP-0078`): see `description_builder.hpp`. `build_id` is the loaded
///   manifest's, and empty for a stage whose library was not loaded (`R-SIM-25`: unknown, never a
///   guess).
/// @author Pavan Karimajji

#include "description_builder.hpp"

#include <cstdio>
#include <filesystem>
#include <set>
#include <vector>

#include <google/protobuf/descriptor.pb.h>

namespace simcore::livemeas {

namespace {

using adas::livemeas::MeasBundle;
using adas::livemeas::MeasDescription;
using adas::livemeas::MeasOverride;
using adas::livemeas::MeasStage;

constexpr const char* kSource = "source";

MeasStage::Mode ModeOf(const std::string& mode) {
  if (mode == "simulate") return MeasStage::MODE_SIMULATE;
  if (mode == "measured") return MeasStage::MODE_MEASURED;
  if (mode == "off") return MeasStage::MODE_OFF;
  return MeasStage::MODE_UNKNOWN;
}

MeasOverride::Verb VerbOf(const std::string& verb) {
  if (verb == "const") return MeasOverride::VERB_CONST;
  if (verb == "hold") return MeasOverride::VERB_HOLD;
  if (verb == "offset") return MeasOverride::VERB_OFFSET;
  if (verb == "scale") return MeasOverride::VERB_SCALE;
  if (verb == "select") return MeasOverride::VERB_SELECT;
  if (verb == "drop") return MeasOverride::VERB_DROP;
  return MeasOverride::VERB_UNKNOWN;
}

std::string AddressOf(const MutationAddress& address) {
  std::string out = address.stage + "." + address.port;
  for (const std::string& field : address.path) out += "." + field;
  if (address.all_elements) {
    out += "[*]";
  } else if (address.index.has_value()) {
    out += "[" + std::to_string(*address.index) + "]";
  }
  return out;
}

std::string ArgumentOf(const std::vector<double>& operands) {
  std::string out;
  for (std::size_t i = 0; i < operands.size(); ++i) {
    char text[40];
    std::snprintf(text, sizeof(text), "%.17g", operands[i]);
    if (i != 0) out += ",";
    out += text;
  }
  return out;
}

}  // namespace

MeasDescription BuildMeasDescription(const RunSpec& spec,
                                     const std::map<std::string, module_host::Component*>& components,
                                     const std::map<std::string, io::TopicInfo>& topics) {
  MeasDescription description;
  if (!spec.sources.empty()) {
    description.set_recording(std::filesystem::path(spec.sources.front().path).filename().string());
  }
  description.set_readiness_limit_steps(static_cast<std::uint32_t>(spec.readiness_limit_steps));

  std::set<std::string> source_ports_seen;
  for (const SpecStage& stage : spec.stages) {
    MeasStage* out = description.add_stages();
    out->set_name(stage.name);
    out->set_mode(ModeOf(stage.mode));
    out->set_impl(stage.impl.path.empty() ? stage.impl.kind : stage.impl.kind + ":" + stage.impl.path);
    const auto component = components.find(stage.name);
    if (component != components.end() && component->second != nullptr) {
      out->set_build_id(component->second->manifest().build_id());
    }
    out->set_trigger(stage.trigger);
    out->set_clock_period_ns(static_cast<std::uint64_t>(stage.clock_period_ns));
    for (const SpecInput& input : stage.inputs) {
      if (input.previous_cycle) out->add_previous_cycle_inputs(input.port);
    }
    if (!stage.config_bundle_sha256.empty()) {
      MeasBundle* bundle = description.add_bundles();
      bundle->set_stage(stage.name);
      bundle->set_kind(MeasBundle::KIND_CONFIG);
      if (!stage.impl.path.empty()) {
        bundle->set_path((std::filesystem::path(stage.impl.path).parent_path() / "config").generic_string());
      }
      bundle->set_sha256(stage.config_bundle_sha256);
    }
  }

  for (const SpecStage& stage : spec.stages) {
    if (stage.mode == "off") continue;
    for (const SpecPort& port : stage.ports) {
      adas::livemeas::MeasPort* out = description.add_ports();
      out->set_name(stage.name + "." + port.name);
      out->set_proto_type(port.proto_type);
      out->set_bulk(port.bulk);
    }
  }
  // A recorded source port is a port of the run too: a stage input wired to it reads its newest sample.
  for (const SpecStage& stage : spec.stages) {
    if (stage.mode == "off") continue;
    for (const SpecInput& input : stage.inputs) {
      if (input.producer != kSource) continue;
      const std::string name = std::string(kSource) + "." + input.producer_port;
      if (!source_ports_seen.insert(name).second) continue;
      std::string proto_type;
      bool bulk = false;
      for (const SpecStage& reader : spec.stages) {
        for (const SpecInput& wired : reader.inputs) {
          if (wired.producer != kSource || wired.producer_port != input.producer_port) continue;
          for (const SpecPort& port : reader.ports) {
            if (port.name != wired.port) continue;
            if (proto_type.empty()) proto_type = port.proto_type;
            bulk = bulk || port.bulk;
          }
        }
      }
      adas::livemeas::MeasPort* out = description.add_ports();
      out->set_name(name);
      out->set_proto_type(proto_type);
      out->set_bulk(bulk);
    }
  }

  // The union of every schema the run names, one entry per file.
  google::protobuf::FileDescriptorSet merged;
  std::set<std::string> files_seen;
  const auto add_set = [&](const google::protobuf::FileDescriptorSet& set) {
    for (const google::protobuf::FileDescriptorProto& file : set.file()) {
      if (files_seen.insert(file.name()).second) *merged.add_file() = file;
    }
  };
  for (const SpecStage& stage : spec.stages) {
    const auto component = components.find(stage.name);
    if (component == components.end() || component->second == nullptr) continue;
    google::protobuf::FileDescriptorSet set;
    const std::string& raw = component->second->manifest().descriptor_set();
    if (!raw.empty() && set.ParseFromString(raw)) add_set(set);
  }
  for (const auto& [topic, info] : topics) {
    if (info.schema_bytes.empty()) continue;
    google::protobuf::FileDescriptorSet set;
    if (set.ParseFromArray(info.schema_bytes.data(), static_cast<int>(info.schema_bytes.size()))) add_set(set);
  }
  description.set_descriptor_set(merged.SerializeAsString());

  for (const SpecMutation& mutation : spec.mutations) {
    MeasOverride* out = description.add_overrides();
    out->set_address(AddressOf(mutation.address));
    out->set_verb(VerbOf(mutation.verb));
    out->set_argument(ArgumentOf(mutation.operands));
  }
  return description;
}

}  // namespace simcore::livemeas
