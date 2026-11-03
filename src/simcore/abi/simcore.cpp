// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `simEngineCreate`/`simEngineRun`/`simEngineDestroy` (`IMP-0144`,
///   `WP-14`): the implementation behind `abi/simcore.h`. This is the ONE
///   place a Resolved Run Spec is turned into a live `PortBus` + `Runner`
///   + `Reader` + loaded `module_host::Component`s + `runner::Runner` --
///   `simengine/main.cpp` calls exactly these three functions and nothing
///   else (`SW-0141`), and `IT-11` calls them from a second, non-`simengine`
///   host to prove `SW-0144`.
///
///   **`WP-14a` (`IMP-0426`/`IMP-0427`), closing the two gaps `WP-14` named
///   above:** a real writer is now opened from the resolved Run Spec's own
///   declared `outputs.path`/`outputs.codec` (`runspec.hpp`'s `SpecOutputs`,
///   `R-SIM-6`) -- absent when the spec declares none, exactly as before
///   this package. And a real `PortResolver` is wired: a `DescriptorPool`
///   built from every loaded component's own `manifest().descriptor_set()`
///   bytes (`R-SIM-11` -- the catalogue was always on the wire, nothing
///   built a pool from it before this pass) resolves a mutation's port to
///   its message `Descriptor` by the spec's own declared `proto_type`. A
///   spec with zero `mutations` is unaffected: `mutate::Mutator::Touches`
///   is built from `mutations` alone and gates `ApplyTo` before the
///   resolver is ever called, so an empty `mutations` list makes this
///   resolver behave as a no-op by construction (`SW-0423`'s own Accept).
/// @author Pavan Karimajji

#include "simcore/abi/simcore.h"
#include "engine_access.hpp"

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cstring>
#include <fstream>
#include <random>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <winsock2.h>
#else
#include <unistd.h>
#endif
#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>
#include <google/protobuf/dynamic_message.h>

#include "simcore/bus.hpp"
#include "simcore/errors.hpp"
#include "simcore/io.hpp"
#include "simcore/module_host.hpp"
#include "simcore/mutate.hpp"
#include "simcore/runner.hpp"
#include "simcore/runspec.hpp"
#include "simcore/transport_publisher.hpp"

namespace {

using simcore::Error;
using simcore::ExitCode;
using simcore::Kind;
using simcore::Result;

void WriteErr(char* buf, std::size_t cap, const std::string& msg) {
  if (buf == nullptr || cap == 0) return;
  const std::size_t n = std::min(cap - 1, msg.size());
  std::memcpy(buf, msg.data(), n);
  buf[n] = '\0';
}

SimExitCode ToC(ExitCode code) { return static_cast<SimExitCode>(code); }

// `IMP-0060`: set when a run ends with the timeout outcome. The call that timed out may still be inside
// the component's library, and a second run in this process could load that library again beside it, so
// the process refuses engine runs from then on (batch runs one process per recording).
std::atomic<bool> g_timeout_abandoned{false};

SimExitCode EndedBy(const Error& error) {
  const ExitCode code = simcore::ExitCodeFor(error);
  if (code == ExitCode::Timeout) g_timeout_abandoned = true;
  return ToC(code);
}

bool RefusedAfterTimeout(char* err_buf, std::size_t err_buf_cap) {
  if (!g_timeout_abandoned) return false;
  WriteErr(err_buf, err_buf_cap,
           "expected an engine run in a process whose earlier run did not time out; found a component call that "
           "did not return within limits.exec_timeout_ms and may still be running -> restart the process");
  return true;
}

// Every registered-once-per-process codec this host knows how to read.
// `CodecRegistry::Register` fails a SECOND registration of one extension
// (IMP-0023), so this must run exactly once per process regardless of how
// many `simEngineCreate` calls follow -- `std::call_once`, not a static
// bool a caller could race.
void EnsureCodecsRegistered() {
  static std::once_flag once;
  std::call_once(once, [] {
    simcore::io::codecs::RegisterMcap(simcore::io::CodecRegistry::Instance());
    simcore::io::codecs::RegisterErg(simcore::io::CodecRegistry::Instance());
  });
}

Result<std::string> ReadFile(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return Result<std::string>::Fail(
        Error{Kind::Environment, "a readable Resolved Run Spec file", "could not open", path.string(),
              "check the path passed to simEngineCreate"});
  }
  std::ostringstream buf;
  buf << in.rdbuf();
  return Result<std::string>::Ok(buf.str());
}

// One input recording, as `simEngineCreate` has it open: its path (for an error to name) and its topic index.
struct InputIndex {
  std::string path;
  std::map<std::string, simcore::io::TopicInfo> topics;
};

// What the engine's writer is given besides the messages: the declared channels, and every recorded
// port's `record` policy (`manifest` `record_policies`, section 6a).
struct RecordingPlan {
  std::map<std::string, simcore::io::TopicInfo> topics;
  std::map<std::string, std::string> policies;  // port name -> full | excluded | decimate:<n>
};

std::string PolicyText(const simcore::runner::RecordPolicy& policy) {
  switch (policy.verb) {
    case simcore::runner::RecordVerb::kExcluded:
      return "excluded";
    case simcore::runner::RecordVerb::kDecimate:
      return "decimate:" + std::to_string(policy.decimate_n);
    case simcore::runner::RecordVerb::kFull:
      break;
  }
  return "full";
}

std::vector<std::uint8_t> ToByteVector(const std::string& text) {
  return std::vector<std::uint8_t>(text.begin(), text.end());
}

// IMP-0426, IMP-0052: the topics `Writer::Open` declares up front -- one per
// declared port of every non-`off` stage, the same "stage.port" universe
// `runner::Runner::Construct` derives its own `recorded_topics_` from
// (`cycle_loop.cpp`) -- and each one's `record` policy. A port whose policy is
// `excluded` has no topic (section 6a). Computed here rather than reused from
// that accessor because it is only available AFTER `Runner::Construct`, which
// itself needs an already-open `WriterBase` -- `Writer::Open` must run first.
//
// The origin of a topic a `simulate` stage computes is `simulated`. Every other
// topic is FED: its origin is the input recording's own (F-2), and an input
// that holds the topic without stating an origin is refused, naming it
// (`IMP-0052`, no default). A topic no input holds is one the engine itself
// writes for the run (a control it makes from the setup), and is `simulated`.
// The schema bytes are the component's own `FileDescriptorSet` for what it
// computes, the input's for what it carries.
simcore::Result<RecordingPlan> PlanRecording(
    const simcore::RunSpec& spec, const std::vector<InputIndex>& inputs,
    const std::map<std::string, simcore::module_host::Component*>& components) {
  RecordingPlan plan;
  std::set<std::string> claimed;
  const auto input_holding = [&inputs](const std::string& topic) -> const InputIndex* {
    for (const InputIndex& input : inputs) {
      if (input.topics.count(topic) != 0) return &input;
    }
    return nullptr;
  };
  const auto component_schema = [&components](const std::string& stage) -> std::vector<std::uint8_t> {
    const auto it = components.find(stage);
    return it == components.end() ? std::vector<std::uint8_t>{} : ToByteVector(it->second->manifest().descriptor_set());
  };

  // `pro` before `req`, for the reason `Runner::Construct` states at length:
  // a `req` port recorded under its producing address can resolve onto a
  // topic a `pro` port owns, and the producer must claim it first.
  for (const std::string& want_dir : {std::string("pro"), std::string("req")}) {
    for (const simcore::SpecStage& stage : spec.stages) {
      if (stage.mode == "off") continue;
      for (const simcore::SpecPort& port : stage.ports) {
        if (port.dir != want_dir) continue;
        const std::string qualified = stage.name + "." + port.name;
        const simcore::Result<simcore::runner::RecordPolicy> policy =
            simcore::runner::ParseRecordPolicy(port.record, "port '" + qualified + "'");
        if (!policy.ok()) return simcore::Result<RecordingPlan>::Fail(policy.error());
        // The SAME derivation `Runner::Construct` uses to name the messages it
        // writes (`RecordedTopicFor`) -- index and stream cannot disagree.
        const std::string topic = simcore::runner::RecordedTopicFor(spec, stage.name, port.name, port.dir);
        if (claimed.insert(topic).second) {
          plan.policies.emplace(simcore::io::PortNameOfTopic(topic), PolicyText(policy.value()));
          if (policy.value().verb != simcore::runner::RecordVerb::kExcluded) {
            simcore::io::TopicInfo info;
            info.schema_name = port.proto_type;
            if (port.dir == "pro" && stage.mode == "simulate") {
              info.provenance = simcore::io::Provenance::kSimulated;
              info.schema_bytes = component_schema(stage.name);
            } else if (const InputIndex* held = input_holding(topic)) {
              const simcore::io::TopicInfo& carried = held->topics.at(topic);
              if (carried.provenance == simcore::io::Provenance::kUnknown) {
                return simcore::Result<RecordingPlan>::Fail(simcore::Error{
                    simcore::Kind::Authoring, "the input recording to state an origin for topic '" + topic + "'",
                    "none in topic_provenance", held->path,
                    "write the recording with an origin for every topic (measured, truth, mocked, simulated or "
                    "overridden); the engine has no default"});
              }
              info.provenance = carried.provenance;
              info.schema_bytes = carried.schema_bytes;
              if (!carried.schema_name.empty()) info.schema_name = carried.schema_name;
            } else {
              info.provenance = simcore::io::Provenance::kSimulated;
              info.schema_bytes = component_schema(stage.name);
            }
            plan.topics.emplace(topic, std::move(info));
          }
        }

        // The post-mutation twin (`R-SIM-15`), declared here so the index says
        // `overridden` rather than leaving a reader to infer it.
        if (port.dir != "req") continue;
        const std::optional<std::string> producer =
            simcore::runner::ProducerAddressOf(spec, stage.name, port.name);
        if (!producer.has_value()) continue;
        const std::size_t dot = producer->find('.');
        if (dot == std::string::npos) continue;
        if (!simcore::runner::MutationTouches(spec, producer->substr(0, dot), producer->substr(dot + 1))) continue;
        const std::string twin = simcore::runner::PortNameToTopic(qualified);
        if (!claimed.insert(twin).second) continue;
        plan.policies.emplace(simcore::io::PortNameOfTopic(twin), PolicyText(policy.value()));
        if (policy.value().verb == simcore::runner::RecordVerb::kExcluded) continue;
        const auto source = plan.topics.find(topic);
        simcore::io::TopicInfo overridden;
        if (source != plan.topics.end()) {
          overridden = source->second;
        } else {
          overridden.schema_name = port.proto_type;
        }
        overridden.provenance = simcore::io::Provenance::kOverridden;
        plan.topics.emplace(twin, std::move(overridden));
      }
    }
  }
  return simcore::Result<RecordingPlan>::Ok(std::move(plan));
}

// The text of a top-level `key: value` line of a `manifest` block's YAML; `std::nullopt` when there is none.
// Not a YAML parser: the producers write `key: value` lines, quoted or plain, one per line, and this reads
// exactly one such scalar (the same narrow read `ParseManifestVersion` makes of `manifest_version`).
std::optional<std::string> TopLevelScalar(const std::string& yaml, const std::string& key) {
  const std::string prefix = key + ":";
  std::size_t start = 0;
  while (start < yaml.size()) {
    std::size_t end = yaml.find('\n', start);
    if (end == std::string::npos) end = yaml.size();
    const std::string line = yaml.substr(start, end - start);
    start = end + 1;
    if (line.rfind(prefix, 0) != 0) continue;
    std::string value = line.substr(prefix.size());
    const std::size_t first = value.find_first_not_of(" \t");
    const std::size_t last = value.find_last_not_of(" \t\r");
    if (first == std::string::npos) return std::nullopt;
    value = value.substr(first, last - first + 1);
    if (value.size() >= 2 && (value.front() == '\'' || value.front() == '"') && value.back() == value.front()) {
      value = value.substr(1, value.size() - 2);
    }
    if (value.empty()) return std::nullopt;
    return value;
  }
  return std::nullopt;
}

// A YAML scalar for `text`: single-quoted, so no value (a hex build id that reads as a number) changes type.
std::string YamlQuoted(const std::string& text) {
  std::string out = "'";
  for (const char c : text) out += c == '\'' ? std::string("''") : std::string(1, c);
  return out + "'";
}

// A YAML mapping key: plain when it is made of name characters, else quoted.
std::string YamlKey(const std::string& key) {
  const bool plain = !key.empty() && std::all_of(key.begin(), key.end(), [](unsigned char c) {
                       return std::isalnum(c) != 0 || c == '_' || c == '.' || c == '-';
                     });
  return plain ? key : YamlQuoted(key);
}

// `IMP-0052`: the `source_kind` the run's inputs state. Every input must state one, and they must agree.
simcore::Result<std::string> InputSourceKind(const simcore::RunSpec& spec,
                                             const std::vector<std::unique_ptr<simcore::io::Reader>>& readers) {
  std::optional<std::string> kind;
  std::string kind_from;
  for (std::size_t i = 0; i < readers.size(); ++i) {
    const std::string& path = spec.sources[i].path;
    const auto block = readers[i]->GetMeta(simcore::io::ToString(simcore::io::MetaKind::kRunManifest));
    const std::optional<std::string> stated =
        block.has_value() ? TopLevelScalar(std::string(block->begin(), block->end()), "source_kind") : std::nullopt;
    if (!stated.has_value()) {
      return simcore::Result<std::string>::Fail(simcore::Error{
          simcore::Kind::Authoring, "the input recording to state source_kind in its manifest", "none", path,
          "write the recording with a source_kind; the engine has no default"});
    }
    if (kind.has_value() && *kind != *stated) {
      return simcore::Result<std::string>::Fail(simcore::Error{
          simcore::Kind::Authoring, "the input recordings to state one source_kind",
          "'" + kind_from + "' and '" + *stated + "'", path,
          "a run with inputs of two kinds has no single kind to record"});
    }
    if (!kind.has_value()) {
      kind = stated;
      kind_from = *stated;
    }
  }
  return simcore::Result<std::string>::Ok(*kind);
}

// `IMP-0063`: SHA-256 of a byte string, lowercase hex (FIPS 180-4); the engine has no other hash and links no library for it.
std::string Sha256Hex(const std::string& data) {
  static const std::uint32_t k[64] = {
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98,
      0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
      0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8,
      0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
      0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819,
      0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
      0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
      0xc67178f2};
  std::uint32_t h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
  std::string message = data;
  const std::uint64_t bits = static_cast<std::uint64_t>(data.size()) * 8;
  message += static_cast<char>(0x80);
  while (message.size() % 64 != 56) message += '\0';
  for (int shift = 56; shift >= 0; shift -= 8) message += static_cast<char>((bits >> shift) & 0xff);
  const auto rotr = [](std::uint32_t x, int n) { return (x >> n) | (x << (32 - n)); };
  for (std::size_t block = 0; block < message.size(); block += 64) {
    std::uint32_t w[64];
    for (int t = 0; t < 16; ++t) {
      const unsigned char* b = reinterpret_cast<const unsigned char*>(message.data()) + block + 4 * t;
      w[t] = (std::uint32_t(b[0]) << 24) | (std::uint32_t(b[1]) << 16) | (std::uint32_t(b[2]) << 8) | b[3];
    }
    for (int t = 16; t < 64; ++t) {
      const std::uint32_t s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >> 3);
      const std::uint32_t s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >> 10);
      w[t] = w[t - 16] + s0 + w[t - 7] + s1;
    }
    std::uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
    for (int t = 0; t < 64; ++t) {
      const std::uint32_t t1 = hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + k[t] + w[t];
      const std::uint32_t t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
      hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
  }
  static const char digits[] = "0123456789abcdef";
  std::string hex;
  for (const std::uint32_t word : h) {
    for (int shift = 28; shift >= 0; shift -= 4) hex += digits[(word >> shift) & 0xf];
  }
  return hex;
}

// `IMP-0063`: the library file's bytes hashed, or empty when the file cannot be read.
std::string FileSha256Hex(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) return "";
  std::ostringstream bytes;
  bytes << in.rdbuf();
  return Sha256Hex(bytes.str());
}

// `IMP-0063`: this machine's name, as Python's `socket.gethostname()` gives it.
std::string HostName() {
  char name[256] = {0};
#ifdef _WIN32
  WSADATA data;
  const bool started = WSAStartup(MAKEWORD(2, 2), &data) == 0;
  if (gethostname(name, sizeof(name) - 1) != 0) name[0] = '\0';
  if (started) WSACleanup();
#else
  if (gethostname(name, sizeof(name) - 1) != 0) name[0] = '\0';
#endif
  return name;
}

// `IMP-0063`: random hex, drawn once per process -- two engine runs in one host process share it, two processes never do.
const std::string& ProcessNonce() {
  static const std::string nonce = [] {
    std::random_device device;
    static const char digits[] = "0123456789abcdef";
    std::string hex;
    for (int i = 0; i < 32; ++i) hex += digits[device() & 0xf];
    return hex;
  }();
  return nonce;
}

// One simulated stage of the `manifest`: its `build_id` and the SHA-256 of the library file it loaded.
struct ManifestComponent {
  std::string name;
  std::string build_id;
  std::string library_sha256;
};

// `IMP-0052`, `IMP-0063`, `IMP-0064`: the `manifest` entry of `RCT_Architecture.md` section 6a for an engine run --
// `run_kind: resim`, the input's `source_kind`, the simulated stages with their `build_id`, each port's policy,
// and beside C6's keys the engine's own: `run_id`, `host`, `process_nonce`, `run_spec_sha256`, each stage's
// `library_sha256` and the `divergence` (`D29 (1)`). Keys sorted, as the Python writer's were. Never a bundle hash.
std::string ManifestYaml(const std::string& source_kind, const std::vector<ManifestComponent>& components,
                         const std::map<std::string, std::string>& policies, const std::string& run_id,
                         const std::string& spec_sha256, const std::string& divergence) {
  std::string yaml = components.empty() ? "components: []\n" : "components:\n";
  for (const ManifestComponent& component : components) {
    yaml += "- build_id: " + YamlQuoted(component.build_id) + "\n  library_sha256: " +
            YamlQuoted(component.library_sha256) + "\n  name: " + YamlQuoted(component.name) + "\n";
  }
  yaml += "divergence: " + YamlQuoted(divergence) + "\nhost: " + YamlQuoted(HostName()) + "\nmanifest_version: 1\n" +
          "process_nonce: " + YamlQuoted(ProcessNonce()) + "\nrecord_policies:\n";
  for (const auto& [port, policy] : policies) yaml += "  " + YamlKey(port) + ": " + YamlQuoted(policy) + "\n";
  yaml += "run_id: " + YamlQuoted(run_id) + "\nrun_kind: resim\nrun_spec_sha256: " + YamlQuoted(spec_sha256) +
          "\nsource_kind: " + YamlQuoted(source_kind) + "\n";
  return yaml;
}

// `IMP-0059`: each simulated stage's bundle folder -- `config_path` when given, else `config/` beside its library,
// as `adasInit` resolves it -- as `<stage>/<relative POSIX path>` -> the file's exact text. A stage with no such
// folder gives no key.
std::map<std::string, std::string> ReadConfigBundles(
    const simcore::RunSpec& spec, const std::map<std::string, simcore::module_host::Component*>& components,
    const char* config_path) {
  std::map<std::string, std::string> bundle;
  for (const simcore::SpecStage& stage : spec.stages) {
    if (stage.mode != "simulate") continue;
    const auto it = components.find(stage.name);
    if (it == components.end()) continue;
    const std::filesystem::path folder = config_path != nullptr ? std::filesystem::path(config_path)
                                                                 : it->second->library_path().parent_path() / "config";
    std::error_code ec;
    if (!std::filesystem::is_directory(folder, ec)) continue;
    for (std::filesystem::recursive_directory_iterator entry(folder, ec), end; !ec && entry != end;
         entry.increment(ec)) {
      if (!entry->is_regular_file()) continue;
      std::ifstream in(entry->path(), std::ios::binary);
      std::ostringstream text;
      text << in.rdbuf();
      bundle[stage.name + "/" + std::filesystem::relative(entry->path(), folder).generic_string()] = text.str();
    }
  }
  return bundle;
}

// IMP-0427: builds a real `DescriptorPool` from every loaded component's
// own `manifest().descriptor_set()` bytes (`R-SIM-11` -- the catalogue is
// already on the wire; this is the first caller to turn it into a pool
// rather than leaving it opaque). Best-effort file-by-file: a component
// that declares no schema, or a file this pass cannot yet place (its own
// dependency not seen first), simply contributes nothing -- `resolve_port`
// then reports that port unresolvable, the same `Result::Fail` path
// `Mutator::ApplyTo` already takes for any unresolvable port, rather than
// this construction step failing the whole engine over one component's
// catalogue. Multiple passes handle shared dependency files (two
// components' `FileDescriptorSet`s both listing a common `.proto`) without
// requiring either set to already be topologically sorted.
void PopulateDescriptorPool(
    const std::vector<std::unique_ptr<simcore::module_host::Component>>& components,
    google::protobuf::DescriptorPool& pool) {
  std::vector<google::protobuf::FileDescriptorProto> pending;
  for (const auto& component : components) {
    const std::string& raw = component->manifest().descriptor_set();
    if (raw.empty()) continue;
    google::protobuf::FileDescriptorSet file_set;
    if (!file_set.ParseFromString(raw)) continue;  // malformed catalogue: named via an unresolved port later
    for (const auto& file_proto : file_set.file()) {
      pending.push_back(file_proto);
    }
  }
  for (std::size_t remaining = pending.size(); remaining > 0;) {
    std::vector<google::protobuf::FileDescriptorProto> next;
    std::size_t built_this_pass = 0;
    for (const auto& file_proto : pending) {
      if (pool.FindFileByName(file_proto.name()) != nullptr) continue;  // already built (shared dependency)
      if (pool.BuildFile(file_proto) != nullptr) {
        ++built_this_pass;
      } else {
        next.push_back(file_proto);  // a dependency not yet built -- retry next pass
      }
    }
    pending = std::move(next);
    if (built_this_pass == 0) break;  // no progress: the rest have an unmet or broken dependency
    remaining = pending.size();
  }
}

// `WP-15b` follow-on (`engine.bridge._fault_mutations`): a `run.faults`
// `corrupt` verb is translated, on the Python side, into a `const` mutation
// addressed `{stage: "source", port: <port>}` -- reusing the mutation
// vocabulary/window/consumer-side matching this file already wires (`R-SIM-
// 21`'s reserved `source.<port>` keyword) rather than a second, unwired
// mechanism. But `resolve_port` below only ever looked in `spec.stages` for
// a message `Descriptor`, and `"source"` is never a `SpecStage` -- a source
// port has no component manifest, only whatever schema the RECORDING itself
// declares per topic (`R-SIM-11`). This does the same best-effort,
// multi-pass build `PopulateDescriptorPool` does for component manifests,
// from every topic's own `TopicInfo::schema_bytes` instead -- so a `const`
// mutation targeting `source.<port>.<field>` can resolve a `Descriptor` the
// same way one targeting a real stage's own port already does.
void PopulateDescriptorPoolFromTopics(const std::map<std::string, simcore::io::TopicInfo>& topics,
                                       google::protobuf::DescriptorPool& pool) {
  std::vector<google::protobuf::FileDescriptorProto> pending;
  for (const auto& [topic, info] : topics) {
    if (info.schema_bytes.empty()) continue;
    google::protobuf::FileDescriptorSet file_set;
    if (!file_set.ParseFromArray(info.schema_bytes.data(), static_cast<int>(info.schema_bytes.size()))) continue;
    for (const auto& file_proto : file_set.file()) {
      pending.push_back(file_proto);
    }
  }
  for (std::size_t remaining = pending.size(); remaining > 0;) {
    std::vector<google::protobuf::FileDescriptorProto> next;
    std::size_t built_this_pass = 0;
    for (const auto& file_proto : pending) {
      if (pool.FindFileByName(file_proto.name()) != nullptr) continue;
      if (pool.BuildFile(file_proto) != nullptr) {
        ++built_this_pass;
      } else {
        next.push_back(file_proto);
      }
    }
    pending = std::move(next);
    if (built_this_pass == 0) break;
    remaining = pending.size();
  }
}

}  // namespace

// One constructed engine: the spec plus every live object the cycle loop
// (`runner::Runner`) needs a non-owning pointer/reference to. Declaration
// order is destruction order, reversed -- `runner_` is declared LAST so it
// is destroyed FIRST, before the reader, the components, the writer, the
// descriptor pool and the mutator it only borrows.
struct SimEngine {
  simcore::RunSpec spec;
  simcore::bus::PortBus bus;
  // One reader per `sources[]` entry: together they are one recording.
  std::vector<std::unique_ptr<simcore::io::Reader>> readers;
  // The union of the readers' topic indexes, kept for the mutation resolver.
  std::map<std::string, simcore::io::TopicInfo> topics;
  std::vector<std::unique_ptr<simcore::module_host::Component>> owned_components;
  std::map<std::string, simcore::module_host::Component*> component_ptrs;
  // IMP-0426: the underlying codec `Writer`, and the `WriterBase` wrapping
  // it that `Runner` actually writes through -- both absent (no writer
  // opened, matching pre-`WP-14a` behaviour) when the spec declares no
  // `outputs.path`.
  std::unique_ptr<simcore::io::Writer> writer_impl;
  std::optional<simcore::io::WriterBase> writer_base;
  // IMP-0427: the real per-run schema catalogue and the `Mutator` resolving
  // against it -- always constructed, even for zero `mutations` (see this
  // file's own top note on why that is still a no-op).
  google::protobuf::DescriptorPool descriptor_pool;
  std::unique_ptr<google::protobuf::DynamicMessageFactory> message_factory;
  std::optional<simcore::mutate::Mutator> mutator;
  // IMP-0139: absent (no checkpoint written) when the spec declares no
  // `checkpoint.path` -- same shape as `writer_base` above, gated the
  // identical way in `simEngineCreate`. Declared BEFORE `runner` so it
  // outlives the `Runner` that borrows a raw pointer to it (declaration
  // order is destruction order, reversed -- this struct's own top note).
  std::optional<simcore::runner::Checkpoint> checkpoint;
  std::optional<simcore::runner::Runner> runner;
  // `IMP-0064`: what the `manifest` block is made of, kept from create until the recording closes.
  struct ManifestParts {
    std::string source_kind;
    std::vector<ManifestComponent> components;
    std::map<std::string, std::string> policies;
  };
  std::optional<ManifestParts> manifest_parts;

  explicit SimEngine(simcore::RunSpec s) : spec(std::move(s)), bus(0) {}
};

simcore::runner::Runner* SimEngineRunner(SimEngine* engine) {
  return engine != nullptr && engine->runner.has_value() ? &*engine->runner : nullptr;
}

void SimEngineClearTimeoutRefusalForTest() { g_timeout_abandoned = false; }

int32_t simEngineAbiVersion() { return SIMCORE_ABI_VERSION; }

SimEngine* simEngineCreate(const char* run_spec_json_path, const char* config_path, int64_t exec_timeout_ms,
                            char* err_buf, std::size_t err_buf_cap, SimExitCode* out_exit_code) {
  if (out_exit_code != nullptr) *out_exit_code = kSimExitOk;
  if (run_spec_json_path == nullptr) {
    WriteErr(err_buf, err_buf_cap, "run_spec_json_path is NULL");
    if (out_exit_code != nullptr) *out_exit_code = kSimExitConfig;
    return nullptr;
  }
  if (RefusedAfterTimeout(err_buf, err_buf_cap)) {
    if (out_exit_code != nullptr) *out_exit_code = kSimExitInfra;
    return nullptr;
  }

  const Result<std::string> json = ReadFile(run_spec_json_path);
  if (!json.ok()) {
    WriteErr(err_buf, err_buf_cap, json.error().Format());
    if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(json.error().kind));
    return nullptr;
  }

  Result<simcore::RunSpec> spec_result = simcore::LoadRunSpec(json.value());
  if (!spec_result.ok()) {
    WriteErr(err_buf, err_buf_cap, spec_result.error().Format());
    if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(spec_result.error().kind));
    return nullptr;
  }

  if (spec_result.value().sources.empty()) {
    WriteErr(err_buf, err_buf_cap, "run spec declares no sources[] to read");
    if (out_exit_code != nullptr) *out_exit_code = kSimExitConfig;
    return nullptr;
  }

  auto engine = std::make_unique<SimEngine>(std::move(spec_result).value());

  EnsureCodecsRegistered();
  for (const simcore::SpecSource& source : engine->spec.sources) {
    Result<std::unique_ptr<simcore::io::Reader>> reader_result =
        simcore::io::CodecRegistry::Instance().OpenRead(source.path);
    if (!reader_result.ok()) {
      WriteErr(err_buf, err_buf_cap, reader_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(reader_result.error().kind));
      return nullptr;
    }
    std::unique_ptr<simcore::io::Reader> reader = std::move(reader_result).value();
    // `WP-12`'s ingest table, applied (2026-08-28, `F-4`/`#5`). Wrapped ONLY
    // when the source actually carries rows, so a recording this framework
    // produced -- whose topics already are port names -- takes the identical
    // path it always did, with no decorator in it at all.
    if (!source.ingest.empty()) {
      reader = std::make_unique<simcore::io::TranslatingReader>(std::move(reader), simcore::io::Translator(source.ingest));
    }
    const Result<bool> open_result = reader->Open(source.path);
    if (!open_result.ok()) {
      WriteErr(err_buf, err_buf_cap, open_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(open_result.error().kind));
      return nullptr;
    }
    engine->readers.push_back(std::move(reader));
  }

  // `IMP-0028`: the graph, the ranks and the plan from the setup and the
  // recording's topic index alone, before any library loads. The plan and the
  // boundary line go to stderr; a refusal is a load error.
  std::set<std::string> topic_index;
  std::vector<InputIndex> input_indexes;
  for (std::size_t i = 0; i < engine->readers.size(); ++i) {
    InputIndex input{engine->spec.sources[i].path, engine->readers[i]->Describe()};
    for (const auto& [topic, info] : input.topics) {
      topic_index.insert(topic);
      engine->topics.emplace(topic, info);
    }
    input_indexes.push_back(std::move(input));
  }
  {
    const Result<simcore::runner::PreflightResult> preflight =
        simcore::runner::Runner::Preflight(engine->spec, topic_index);
    if (!preflight.ok()) {
      WriteErr(err_buf, err_buf_cap, preflight.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(preflight.error().kind));
      return nullptr;
    }
    std::cerr << preflight.value().plan_text;
    std::cerr << simcore::runner::ComputeInjectionBoundary(engine->spec).FormatEvent(engine->spec.run_id) << "\n";
  }

  for (const simcore::SpecStage& stage : engine->spec.stages) {
    if (stage.mode != "simulate") continue;
    Result<simcore::module_host::Component> component_result =
        simcore::module_host::Component::Load(stage.impl.path);
    if (!component_result.ok()) {
      WriteErr(err_buf, err_buf_cap, component_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(component_result.error().kind));
      return nullptr;
    }
    auto component = std::make_unique<simcore::module_host::Component>(std::move(component_result).value());
    const std::filesystem::path cfg = config_path != nullptr ? std::filesystem::path(config_path)
                                                               : std::filesystem::path();
    const Result<bool> init_result = component->Init(cfg);
    if (!init_result.ok()) {
      WriteErr(err_buf, err_buf_cap, init_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(init_result.error().kind));
      return nullptr;
    }
    engine->component_ptrs[stage.name] = component.get();
    engine->owned_components.push_back(std::move(component));
  }

  // IMP-0426: open a real writer iff the resolved spec declares one.
  // Absent `outputs.path` leaves `writer_base` unset, matching this
  // function's own pre-`WP-14a` read-only behaviour exactly.
  if (!engine->spec.outputs.path.empty()) {
    Result<std::unique_ptr<simcore::io::Writer>> writer_result =
        simcore::io::CodecRegistry::Instance().OpenWrite(engine->spec.outputs.path);
    if (!writer_result.ok()) {
      WriteErr(err_buf, err_buf_cap, writer_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(writer_result.error().kind));
      return nullptr;
    }
    engine->writer_impl = std::move(writer_result).value();
    // The input recording's own index is already available (the reader was
    // opened above), which is what lets a fed topic carry its real grade
    // forward instead of being labelled `measured` by direction (F-2).
    Result<RecordingPlan> plan = PlanRecording(engine->spec, input_indexes, engine->component_ptrs);
    if (!plan.ok()) {
      WriteErr(err_buf, err_buf_cap, plan.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(plan.error().kind));
      return nullptr;
    }
    Result<std::string> source_kind = InputSourceKind(engine->spec, engine->readers);
    if (!source_kind.ok()) {
      WriteErr(err_buf, err_buf_cap, source_kind.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(source_kind.error().kind));
      return nullptr;
    }
    const Result<bool> writer_open_result = engine->writer_impl->Open(engine->spec.outputs.path, plan.value().topics);
    if (!writer_open_result.ok()) {
      WriteErr(err_buf, err_buf_cap, writer_open_result.error().Format());
      if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(writer_open_result.error().kind));
      return nullptr;
    }
    SimEngine::ManifestParts parts;
    parts.source_kind = source_kind.value();
    parts.policies = plan.value().policies;
    for (const simcore::SpecStage& stage : engine->spec.stages) {
      const auto component = engine->component_ptrs.find(stage.name);
      if (stage.mode == "simulate" && component != engine->component_ptrs.end()) {
        parts.components.push_back({stage.name, component->second->manifest().build_id(),
                                    FileSha256Hex(component->second->library_path())});
      }
    }
    engine->manifest_parts = std::move(parts);  // written once, when the recording closes (`IMP-0064`)
    const std::map<std::string, std::string> bundles =
        ReadConfigBundles(engine->spec, engine->component_ptrs, config_path);
    if (!bundles.empty()) {
      engine->writer_impl->WriteMetaBlock(simcore::io::ToString(simcore::io::MetaKind::kConfigBundle), bundles);
    }
    engine->writer_base.emplace(*engine->writer_impl);
  }

  // IMP-0427: a real per-run catalogue and resolver, always wired -- a
  // spec with zero `mutations` still gets one, and it is a no-op by
  // construction (this file's own top note).
  PopulateDescriptorPool(engine->owned_components, engine->descriptor_pool);
  // `WP-15b` follow-on: also from every recorded topic's own schema, so a
  // `source.<port>`-addressed mutation (a translated `run.faults` `corrupt`
  // entry, `engine.bridge._fault_mutations`, or a real user override) can
  // resolve a `Descriptor` too -- a source port has no `SpecStage` manifest
  // to draw one from otherwise (this file's own note on `PopulateDescriptor
  // PoolFromTopics`).
  PopulateDescriptorPoolFromTopics(engine->topics, engine->descriptor_pool);
  engine->message_factory = std::make_unique<google::protobuf::DynamicMessageFactory>(&engine->descriptor_pool);
  simcore::mutate::Mutator::PortResolver resolve_port =
      [&spec = engine->spec, &pool = engine->descriptor_pool, &topics = engine->topics](
          const std::string& stage, const std::string& port) -> std::optional<simcore::mutate::PortInfo> {
    for (const simcore::SpecStage& candidate : spec.stages) {
      if (candidate.name != stage) continue;
      for (const simcore::SpecPort& candidate_port : candidate.ports) {
        if (candidate_port.name != port) continue;
        const google::protobuf::Descriptor* descriptor = pool.FindMessageTypeByName(candidate_port.proto_type);
        if (descriptor == nullptr) return std::nullopt;
        return simcore::mutate::PortInfo{descriptor, candidate_port.fixed_slots};
      }
    }
    if (stage == "source") {
      const auto it = topics.find(simcore::runner::PortNameToTopic(stage + "." + port));
      if (it == topics.end() || it->second.schema_name.empty()) return std::nullopt;
      const google::protobuf::Descriptor* descriptor = pool.FindMessageTypeByName(it->second.schema_name);
      if (descriptor == nullptr) return std::nullopt;
      // A source port carries no `SpecPort::fixed_slots` of its own
      // (`select`/`drop[*]` on the stimulus is not a case this pass adds --
      // only `const`, from a translated `corrupt` fault, reaches this
      // branch today); `std::nullopt` matches every real component's own
      // still-unset `fixed_slots` (`runspec/address.py`'s own note on why
      // that stays `None` until `S-C1d` lands).
      return simcore::mutate::PortInfo{descriptor, std::nullopt};
    }
    return std::nullopt;
  };
  engine->mutator.emplace(engine->spec.mutations, std::move(resolve_port));

  // `limits.exec_timeout_ms` of the setup is the default; the argument overrides it when above 0.
  simcore::runner::RunnerOptions options;
  if (engine->spec.limits_exec_timeout_ms > 0) {
    options.exec_timeout = std::chrono::milliseconds(engine->spec.limits_exec_timeout_ms);
  }
  if (exec_timeout_ms > 0) {
    options.exec_timeout = std::chrono::milliseconds(exec_timeout_ms);
  }
  std::vector<simcore::io::Reader*> reader_ptrs;
  for (const auto& reader : engine->readers) reader_ptrs.push_back(reader.get());
  Result<simcore::runner::Runner> runner_result = simcore::runner::Runner::Construct(
      engine->spec, engine->bus, std::move(reader_ptrs), engine->component_ptrs, &engine->descriptor_pool,
      engine->writer_base.has_value() ? &*engine->writer_base : nullptr, &*engine->mutator, options);
  if (!runner_result.ok()) {
    WriteErr(err_buf, err_buf_cap, runner_result.error().Format());
    if (out_exit_code != nullptr) *out_exit_code = ToC(simcore::DefaultExitCode(runner_result.error().kind));
    return nullptr;
  }
  engine->runner = std::move(runner_result).value();

  // IMP-0139: open a real checkpoint iff the resolved spec declares one --
  // the same gate `IMP-0426` uses for the writer above. Absent
  // `checkpoint.path` leaves `checkpoint` unset and `Runner::checkpoint_`
  // `nullptr`, matching every pre-existing spec's behaviour exactly.
  if (!engine->spec.checkpoint.path.empty()) {
    engine->checkpoint.emplace(engine->spec.checkpoint.path, engine->spec.run_id);
    engine->runner->SetCheckpoint(&*engine->checkpoint);
  }

  return engine.release();
}

SimExitCode simEngineRun(SimEngine* engine, char* err_buf, std::size_t err_buf_cap) {
  if (engine == nullptr || !engine->runner.has_value()) {
    WriteErr(err_buf, err_buf_cap, "simEngineRun called with no constructed engine");
    return kSimExitConfig;
  }
  if (RefusedAfterTimeout(err_buf, err_buf_cap)) return kSimExitInfra;
  const Result<simcore::runner::RunOutcome> outcome = engine->runner->Run();
  if (!outcome.ok()) {
    WriteErr(err_buf, err_buf_cap, outcome.error().Format());
    return EndedBy(outcome.error());
  }
  return kSimExitOk;
}

SimExitCode simEngineSetThreads(SimEngine* engine, int32_t threads, char* err_buf, std::size_t err_buf_cap) {
  if (engine == nullptr || !engine->runner.has_value()) {
    WriteErr(err_buf, err_buf_cap, "simEngineSetThreads called with no constructed engine");
    return kSimExitConfig;
  }
  if (threads < 1) {
    WriteErr(err_buf, err_buf_cap, "threads must be at least 1, got " + std::to_string(threads));
    return kSimExitConfig;
  }
  engine->runner->SetThreads(threads);
  return kSimExitOk;
}

void simEngineAttachTransport(SimEngine* engine, void* transport_publisher) {
  if (engine == nullptr || !engine->runner.has_value()) return;
  engine->runner->SetTransportPublisher(
      static_cast<simcore::transport::TransportPublisher*>(transport_publisher));
}

SimExitCode simEngineStepOnce(SimEngine* engine, char* err_buf, std::size_t err_buf_cap, int32_t* out_continue) {
  if (out_continue != nullptr) *out_continue = 0;
  if (engine == nullptr || !engine->runner.has_value()) {
    WriteErr(err_buf, err_buf_cap, "simEngineStepOnce called with no constructed engine");
    return kSimExitConfig;
  }
  if (RefusedAfterTimeout(err_buf, err_buf_cap)) return kSimExitInfra;
  const Result<bool> step = engine->runner->StepOnce();
  if (!step.ok()) {
    WriteErr(err_buf, err_buf_cap, step.error().Format());
    return EndedBy(step.error());
  }
  if (out_continue != nullptr) *out_continue = step.value() ? 1 : 0;
  return kSimExitOk;
}

SimExitCode simEngineSeek(SimEngine* engine, int64_t to_ns, char* err_buf, std::size_t err_buf_cap) {
  if (engine == nullptr || !engine->runner.has_value()) {
    WriteErr(err_buf, err_buf_cap, "simEngineSeek called with no constructed engine");
    return kSimExitConfig;
  }
  const Result<bool> jumped = engine->runner->Seek(to_ns);
  if (!jumped.ok()) {
    WriteErr(err_buf, err_buf_cap, jumped.error().Format());
    return ToC(simcore::DefaultExitCode(jumped.error().kind));
  }
  return kSimExitOk;
}

void simEngineDestroy(SimEngine* engine) {
  if (engine == nullptr) return;
  // Best-effort: a shutdown failure on one component must not stop the
  // rest from being asked to shut down too (mirrors
  // `sil_host::Pipeline::ShutdownComponents`'s own "every component gets
  // asked" shape).
  for (auto& component : engine->owned_components) {
    component->Shutdown();
  }
  // IMP-0426: finalise the recording (mcap's footer/index is written on
  // `Close()`, not on `Runner::Run()`'s own end-of-run `Flush()`) -- always,
  // regardless of whether `simEngineRun` was ever called or how it ended,
  // so a partial run still leaves a readable file up to its last completed
  // message.
  if (engine->writer_impl) {
    if (engine->manifest_parts.has_value()) {
      // `IMP-0064`: `manifest` is written once, here, for every outcome that closes the recording.
      std::string divergence = "unknown";
      if (engine->runner.has_value()) {
        const std::optional<simcore::runner::Divergence> first = engine->runner->FirstDivergence();
        if (first.has_value()) {
          divergence = "step=" + std::to_string(first->tick_index) + " stage=" + first->stage + " port=" + first->port;
        } else if (engine->runner->OutputsCompared()) {
          divergence = "none";
        }
      }
      const SimEngine::ManifestParts& parts = *engine->manifest_parts;
      engine->writer_impl->WriteMetaBlock(
          simcore::io::ToString(simcore::io::MetaKind::kRunManifest),
          {{"yaml", ManifestYaml(parts.source_kind, parts.components, parts.policies, engine->spec.run_id,
                                 engine->spec.spec_sha256, divergence)}});
    }
    engine->writer_impl->Close();
  }
  delete engine;
}
