// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `convert::` implementation -- the `PortMap` <-> `AdasPortSet`
///   marshalling factored out of `sil_host::SilComponent::Exec`
///   (`IMP-0088`/`IMP-0089`).
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

namespace simcore::module_host::convert {

void BuildInputPortSet(const PortMap& inputs, const InputMetaMap& input_meta, std::vector<std::string>& names,
                       std::vector<AdasPort>& ports) {
  // `names` owns storage for the duration of the call so `AdasPort.name`
  // stays valid across `adasExec()` -- mirrors ctypes' own keepalive list,
  // via ordinary object lifetime instead.
  names.clear();
  names.reserve(inputs.size());
  ports.assign(inputs.size(), AdasPort{});

  std::size_t i = 0;
  for (const auto& [port_name, payload] : inputs) {
    names.push_back(port_name);
    auto meta_it = input_meta.find(port_name);
    const InputMeta meta = meta_it != input_meta.end() ? meta_it->second : InputMeta{};
    ports[i].name = names.back().c_str();
    ports[i].data = const_cast<std::uint8_t*>(payload.data());
    ports[i].len = payload.size();
    ports[i].cap = 0;
    ports[i].ageS = meta.age_s;
    ports[i].valid = meta.valid ? 1 : 0;
    ports[i].updated = 0;
    ++i;
  }
}

void BuildOutputPortSet(std::map<std::string, PortBytes>& out_buffers, std::vector<std::string>& names,
                        std::vector<AdasPort>& ports) {
  names.clear();
  names.reserve(out_buffers.size());
  ports.assign(out_buffers.size(), AdasPort{});

  std::size_t i = 0;
  for (auto& [port_name, buffer] : out_buffers) {
    names.push_back(port_name);
    ports[i].name = names.back().c_str();
    ports[i].data = buffer.data();
    ports[i].len = 0;
    ports[i].cap = buffer.size();
    ports[i].ageS = 0.0;
    ports[i].valid = 0;
    ports[i].updated = 0;
    ++i;
  }
}

std::vector<std::string> UndersizedPorts(const std::vector<AdasPort>& out_ports) {
  std::vector<std::string> undersized;
  for (const auto& port : out_ports) {
    if (port.len > port.cap) {
      undersized.emplace_back(port.name);
    }
  }
  return undersized;
}

PortMap CollectUpdatedPorts(const std::vector<AdasPort>& out_ports) {
  PortMap result;
  for (const auto& port : out_ports) {
    if (port.updated) {
      result[port.name] = PortBytes(port.data, port.data + port.len);
    }
  }
  return result;
}

}  // namespace simcore::module_host::convert
