// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `Component` implementation -- ported from
///   `sil_host/src/sil_component.cpp` (`IMP-0081`/`0087`/`0090`/`0095`),
///   extended with `Lifecycle`/`Quarantine`/`ExecTimeout` integration
///   (`IMP-0094`) and the two-call manifest read wired to the real
///   generated `adas::sil::ComponentManifest` (`IMP-0394`).
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#include <algorithm>
#include <optional>

namespace simcore::module_host {

namespace {

// `max_bytes` fallback for a port the manifest declares with
// `max_bytes: 0` (undeclared) -- grow-once-and-retry corrects a wrong
// guess. Mirrors `sil_component.cpp`'s own `kDefaultOutputCap` exactly.
constexpr std::size_t kDefaultOutputCap = 256;

}  // namespace

Component::~Component() {
  // A component quarantined for a timeout has a detached thread still
  // executing inside its Dso (exec_timeout.hpp's own honest limit) --
  // calling back into it via adasShutdown, or unmapping it via ~Dso, is
  // worse than leaking both for the remaining life of the process.
  if (quarantine_.reason() == QuarantineReason::kTimedOut) {
    if (dso_.has_value()) {
      dso_->Leak();
    }
    return;
  }
  if (handle_ != nullptr && adas_shutdown_fn_ != nullptr) {
    adas_shutdown_fn_(handle_);
    handle_ = nullptr;
  }
}

Result<Component> Component::Load(const std::filesystem::path& library_path) {
  Result<Dso> dso_result = Dso::OpenPath(library_path);
  if (!dso_result.ok()) {
    return Result<Component>::Fail(dso_result.error());
  }

  Component component;
  component.dso_ = std::move(dso_result).value();

  const std::string path = library_path.string();

  Result<Component::AdasAbiVersionFn> abi_ver = component.dso_->BoundSymbol<AdasAbiVersionFn>("adasAbiVersion");
  if (!abi_ver.ok()) return Result<Component>::Fail(abi_ver.error());
  Result<Component::AdasManifestFn> manifest_fn = component.dso_->BoundSymbol<AdasManifestFn>("adasManifest");
  if (!manifest_fn.ok()) return Result<Component>::Fail(manifest_fn.error());
  Result<Component::AdasInitFn> init_fn = component.dso_->BoundSymbol<AdasInitFn>("adasInit");
  if (!init_fn.ok()) return Result<Component>::Fail(init_fn.error());
  Result<Component::AdasExecFn> exec_fn = component.dso_->BoundSymbol<AdasExecFn>("adasExec");
  if (!exec_fn.ok()) return Result<Component>::Fail(exec_fn.error());
  Result<Component::AdasShutdownFn> shutdown_fn = component.dso_->BoundSymbol<AdasShutdownFn>("adasShutdown");
  if (!shutdown_fn.ok()) return Result<Component>::Fail(shutdown_fn.error());

  component.adas_abi_version_fn_ = abi_ver.value();
  component.adas_manifest_fn_ = manifest_fn.value();
  component.adas_init_fn_ = init_fn.value();
  component.adas_exec_fn_ = exec_fn.value();
  component.adas_shutdown_fn_ = shutdown_fn.value();

  const std::int32_t found = component.adas_abi_version_fn_();
  if (found != kAbiVersion) {
    return Result<Component>::Fail(Error{Kind::Contract, "ABI version " + std::to_string(kAbiVersion),
                                          "ABI version " + std::to_string(found), "adasAbiVersion() in " + path,
                                          "rebuild the component or the framework, whichever is behind"});
  }

  Result<bool> manifest_read = component.ReadManifest();
  if (!manifest_read.ok()) {
    return Result<Component>::Fail(manifest_read.error());
  }
  component.name_ = component.manifest_.component();
  component.BuildOutBuffers();

  return Result<Component>::Ok(std::move(component));
}

Result<bool> Component::ReadManifest() {
  // The two-call pattern `adasManifest()` documents: probe the required
  // size with cap=0, then fill a buffer of exactly that size. Mirrors
  // `sil_component.cpp::ReadManifest`.
  const std::size_t needed = adas_manifest_fn_(nullptr, 0);
  std::vector<std::uint8_t> buf(needed);
  const std::size_t written = adas_manifest_fn_(buf.empty() ? nullptr : buf.data(), needed);
  if (!manifest_.ParseFromArray(buf.data(), static_cast<int>(written))) {
    return Result<bool>::Fail(Error{Kind::Contract, "a valid serialized adas.sil.ComponentManifest",
                                     "bytes that failed to parse", "adasManifest()",
                                     "the component and this host disagree about the manifest schema"});
  }
  return Result<bool>::Ok(true);
}

void Component::BuildOutBuffers() {
  for (const auto& spec : manifest_.outputs()) {
    const std::size_t cap = spec.max_bytes() != 0 ? spec.max_bytes() : kDefaultOutputCap;
    out_buffers_[spec.name()] = PortBytes(cap);
  }
}

Result<bool> Component::Init(const std::filesystem::path& config_path) {
  Result<bool> transitioned = lifecycle_.Transition(Phase::Initialized);
  if (!transitioned.ok()) {
    return transitioned;
  }
  const std::string encoded = config_path.empty() ? std::string() : config_path.string();
  handle_ = adas_init_fn_(config_path.empty() ? nullptr : encoded.c_str());
  if (handle_ == nullptr) {
    return Result<bool>::Fail(
        Error{Kind::Environment, "a resolved configuration bundle", "NULL handle",
              "adasInit for component '" + name_ + "' (configPath=" + (config_path.empty() ? "NULL)" : encoded + ")"),
              "pass an explicit config_path, or build a config/ bundle beside the library (R-SIM-3a)"});
  }
  return Result<bool>::Ok(true);
}

Result<bool> Component::Shutdown() {
  Result<bool> transitioned = lifecycle_.Transition(Phase::ShutdownDone);
  if (!transitioned.ok()) {
    return transitioned;
  }
  if (handle_ != nullptr) {
    adas_shutdown_fn_(handle_);
    handle_ = nullptr;
  }
  return Result<bool>::Ok(true);
}

Result<bool> Component::Reset() {
  return lifecycle_.Transition(Phase::Loaded);
}

Result<PortMap> Component::ExecOnce(std::int64_t dt_ns, const PortMap& inputs, const InputMetaMap& input_meta) {
  const double dt_s = static_cast<double>(dt_ns) / 1'000'000'000.0;

  std::vector<std::string> in_names;
  std::vector<AdasPort> in_ports;
  convert::BuildInputPortSet(inputs, input_meta, in_names, in_ports);
  AdasPortSet in_set{in_ports.empty() ? nullptr : in_ports.data(), in_ports.size()};

  std::vector<std::string> out_names;
  std::vector<AdasPort> out_ports;
  convert::BuildOutputPortSet(out_buffers_, out_names, out_ports);
  AdasPortSet out_set{out_ports.empty() ? nullptr : out_ports.data(), out_ports.size()};

  std::int32_t ok = adas_exec_fn_(handle_, dt_s, &in_set, &out_set);

  std::vector<std::string> undersized = convert::UndersizedPorts(out_ports);
  if (!undersized.empty()) {
    for (const auto& port_name : undersized) {
      const auto found = std::find_if(out_ports.begin(), out_ports.end(),
                                       [&](const AdasPort& p) { return port_name == p.name; });
      out_buffers_[port_name].assign(found->len, std::uint8_t{0});
    }
    convert::BuildOutputPortSet(out_buffers_, out_names, out_ports);
    out_set = AdasPortSet{out_ports.empty() ? nullptr : out_ports.data(), out_ports.size()};
    ok = adas_exec_fn_(handle_, dt_s, &in_set, &out_set);

    const std::vector<std::string> still_undersized = convert::UndersizedPorts(out_ports);
    if (!still_undersized.empty()) {
      std::string joined;
      for (std::size_t k = 0; k < still_undersized.size(); ++k) {
        if (k != 0) joined += ", ";
        joined += still_undersized[k];
      }
      return Result<PortMap>::Fail(Error{Kind::Contract, "adasExec() output ports to fit after growing once",
                                          "still undersized after growing: " + joined, name_ + ".exec",
                                          "the manifest's max_bytes for these ports is chronically wrong"});
    }
  } else if (!ok) {
    return Result<PortMap>::Fail(Error{Kind::Internal, "adasExec() to return success",
                                        "adasExec() returned 0, no port undersized", name_ + ".exec",
                                        "a component-side failure unrelated to buffer sizing"});
  }

  return Result<PortMap>::Ok(convert::CollectUpdatedPorts(out_ports));
}

Result<PortMap> Component::Exec(std::int64_t dt_ns, const PortMap& inputs, const InputMetaMap& input_meta,
                                 std::optional<ExecTimeout> exec_timeout) {
  if (quarantine_.IsQuarantined()) {
    return Result<PortMap>::Fail(Error{Kind::Internal, "a component not already quarantined",
                                        "quarantined: " + quarantine_.detail(), name_ + ".exec",
                                        "this component crashed or timed out earlier in this session (R-SIM-19); "
                                        "reload it to try again"});
  }
  if (lifecycle_.phase() != Phase::Initialized) {
    return Result<PortMap>::Fail(Error{Kind::Internal, "init() called before exec()", "no handle", name_ + ".exec",
                                        "call init() once before the first exec()"});
  }

  if (!exec_timeout.has_value()) {
    return ExecOnce(dt_ns, inputs, input_meta);
  }

  std::optional<Result<PortMap>> inner;
  const ExecResult watchdog = exec_timeout->Run([&]() { inner = ExecOnce(dt_ns, inputs, input_meta); });
  switch (watchdog.outcome) {
    case ExecOutcome::kOk:
      return *inner;
    case ExecOutcome::kTimeout:
      quarantine_.Trip(QuarantineReason::kTimedOut, watchdog.error);
      return Result<PortMap>::Fail(Error{Kind::Internal, "adasExec() to return within the configured timeout",
                                          watchdog.error, name_ + ".exec",
                                          "component quarantined (R-SIM-19); it refuses further exec() calls "
                                          "this session"});
    case ExecOutcome::kException:
      quarantine_.Trip(QuarantineReason::kCrashed, watchdog.error);
      return Result<PortMap>::Fail(Error{Kind::Internal, "adasExec() to complete without throwing", watchdog.error,
                                          name_ + ".exec",
                                          "component quarantined (R-SIM-19); it refuses further exec() calls "
                                          "this session"});
  }
  return Result<PortMap>::Fail(
      Error{Kind::Internal, "one of ExecOutcome's three values", "none", name_ + ".exec", ""});
}

}  // namespace simcore::module_host
