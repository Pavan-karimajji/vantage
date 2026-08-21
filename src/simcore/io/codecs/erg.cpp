// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `SM-05a`: the `.erg` codec -- reads a real CarMaker result file
///   (binary `.erg` + text `.erg.info` sidecar) and reconstructs full,
///   real port messages (e.g. a real `BsdOutputs`), not raw scalar
///   signals -- the user's own explicit choice over the lighter
///   scalar-signal-only design (`resilient-bouncing-hopper.md`'s own
///   design fork).
///
///   **The manifest sidecar.** `Reader::Open(path)` takes only a path; a
///   `.erg` file carries no descriptor of its own (unlike `.mcap`, whose
///   `embedded_schemas` capability is true). A same-directory sidecar,
///   `<erg-stem>.manifest.pb` -- the real `adas.sil.ComponentManifest`
///   bytes `adasManifest()` already serves -- is discovered the same way
///   `.erg.info` itself is. Absent sidecar is a hard `Open()` error, never
///   a silent scalar-only degrade (the user chose full resim).
///
///   **Why `ComponentManifest`/`PortSpec` are hand-walked
///   (`erg_wire.hpp`), not parsed via the compiled `AdasInterfaces`
///   classes:** `modules/sim/conf/build.yml`'s own comment states
///   `simcore` requires nothing first-party, and `interfaces` is
///   first-party. `erg_wire.hpp`'s walker dispatches by field number and
///   wire type alone -- the same forward/backward-compatible contract
///   protobuf's own generated code gives -- so this is not a second,
///   competing `.proto` definition (`R-IFACE-1` stays intact). The
///   manifest's own embedded `descriptor_set` bytes, by contrast, parse
///   through real `google::protobuf::FileDescriptorSet` -- that type is
///   compiled into libprotobuf itself (third-party), not generated from
///   any `modules/interfaces/*.proto`.
///
///   **`df.host.*` columns have no protobuf home and are dropped, named,
///   not silently ignored** -- confirmed live against `cm_quantities.cpp`
///   (`modules/df/src/platform/cm/src/host/`): they are plain C++
///   host-diagnostic state (`abiVersion`, `execCount`, per-port
///   `.updated`/`.ageS`, ...), never serialized as a port message.
/// @author Pavan Karimajji

#include <algorithm>
#include <cstring>
#include <fstream>
#include <sstream>

#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>
#include <google/protobuf/descriptor_database.h>
#include <google/protobuf/dynamic_message.h>

#include "simcore/io.hpp"
#include "erg_wire.hpp"

namespace simcore::io::codecs {

namespace {

namespace pb = google::protobuf;

Error MakeError(Kind kind, std::string expected, std::string found, std::string where, std::string hint = "") {
  return Error{kind, std::move(expected), std::move(found), std::move(where), std::move(hint)};
}

// ---- `.erg.info` parsing ---------------------------------------------

enum class ErgType { kDouble, kInt, kBytes };

struct ErgColumn {
  std::string name;
  ErgType type;
  std::size_t byte_width = 0;
  std::size_t byte_offset = 0;
};

// `File.At.N.Type` is `Double` | `Int` | `"<N> Bytes"` (the real
// `bsd_tos_left_straight*.erg.info` fixtures' own literal spelling, column
// 27's `$none$` field). No other type has ever been observed; an unknown
// spelling is a hard parse error naming it, never guessed at a width.
bool ParseErgType(const std::string& text, ErgType* type, std::size_t* width) {
  if (text == "Double") {
    *type = ErgType::kDouble;
    *width = 8;
    return true;
  }
  if (text == "Int") {
    *type = ErgType::kInt;
    *width = 4;
    return true;
  }
  // "<N> Bytes"
  std::istringstream iss(text);
  std::size_t n = 0;
  std::string literal;
  if ((iss >> n >> literal) && literal == "Bytes") {
    *type = ErgType::kBytes;
    *width = n;
    return true;
  }
  return false;
}

// Parses the `File.At.N.Name`/`File.At.N.Type` lines out of a real
// `#INFOFILE1.1` sidecar. Every other line (`Quantity.*`, `Anim.Msg.*`,
// `RandomSeed`, ...) is real CarMaker metadata this codec has no use for
// and skips -- not a claim those lines are meaningless, only that nothing
// here reads them.
Result<std::vector<ErgColumn>> ParseErgInfo(const std::filesystem::path& path) {
  std::ifstream in(path);
  if (!in) {
    return Result<std::vector<ErgColumn>>::Fail(
        MakeError(Kind::Environment, "a readable .erg.info sidecar", "could not open", path.string()));
  }

  std::map<int, std::string> names;
  std::map<int, std::string> types;
  std::string line;
  while (std::getline(in, line)) {
    const auto eq = line.find('=');
    if (eq == std::string::npos) continue;
    std::string key = line.substr(0, eq);
    std::string value = line.substr(eq + 1);
    // Trim trailing/leading whitespace (INFOFILE1.1 pads both sides of '=').
    const auto trim = [](std::string& s) {
      while (!s.empty() && (s.back() == ' ' || s.back() == '\t' || s.back() == '\r')) s.pop_back();
      std::size_t start = 0;
      while (start < s.size() && (s[start] == ' ' || s[start] == '\t')) ++start;
      s = s.substr(start);
    };
    trim(key);
    trim(value);

    static const std::string kPrefix = "File.At.";
    if (key.rfind(kPrefix, 0) != 0) continue;
    const std::string rest = key.substr(kPrefix.size());  // "<N>.Name" or "<N>.Type"
    const auto dot = rest.find('.');
    if (dot == std::string::npos) continue;
    const int index = std::atoi(rest.substr(0, dot).c_str());
    const std::string field = rest.substr(dot + 1);
    if (field == "Name") {
      names[index] = value;
    } else if (field == "Type") {
      types[index] = value;
    }
  }

  if (names.empty()) {
    return Result<std::vector<ErgColumn>>::Fail(MakeError(
        Kind::Environment, "at least one File.At.N.Name declaration", "none found", path.string()));
  }

  std::vector<ErgColumn> columns;
  std::size_t offset = 0;
  for (const auto& [index, name] : names) {
    const auto type_it = types.find(index);
    if (type_it == types.end()) {
      return Result<std::vector<ErgColumn>>::Fail(MakeError(
          Kind::Environment, "a File.At." + std::to_string(index) + ".Type for every .Name",
          "missing", path.string()));
    }
    ErgColumn column;
    column.name = name;
    if (!ParseErgType(type_it->second, &column.type, &column.byte_width)) {
      return Result<std::vector<ErgColumn>>::Fail(MakeError(
          Kind::Environment, "a Double/Int/\"N Bytes\" column type",
          "'" + type_it->second + "' for File.At." + std::to_string(index), path.string()));
    }
    column.byte_offset = offset;
    offset += column.byte_width;
    columns.push_back(std::move(column));
  }
  return Result<std::vector<ErgColumn>>::Ok(std::move(columns));
}

// ---- manifest sidecar parsing (erg_wire, no first-party dependency) --

struct PortSpecLite {
  std::string name;
  std::string proto_type;
};

struct ManifestLite {
  std::string component;
  std::vector<PortSpecLite> outputs;
  std::vector<PortSpecLite> inputs;
  std::string descriptor_set_bytes;
};

PortSpecLite ParsePortSpec(std::string_view bytes) {
  PortSpecLite spec;
  erg_detail::WalkFields(bytes, [&](const erg_detail::WireField& f) {
    if (f.wire_type != 2) return;
    if (f.field_number == 1) {
      spec.name.assign(f.bytes_value);
    } else if (f.field_number == 2) {
      spec.proto_type.assign(f.bytes_value);
    }
  });
  return spec;
}

Result<ManifestLite> ParseManifest(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return Result<ManifestLite>::Fail(MakeError(
        Kind::Environment, "a readable .manifest.pb sidecar beside the .erg file", "could not open",
        path.string(),
        "SM-05a needs a real adas.sil.ComponentManifest sidecar to reconstruct port messages -- "
        "see tests/fixtures/erg/make_erg_fixture.py for how one is produced"));
  }
  std::ostringstream buf;
  buf << in.rdbuf();
  const std::string bytes = buf.str();

  ManifestLite manifest;
  bool ok = erg_detail::WalkFields(bytes, [&](const erg_detail::WireField& f) {
    if (f.wire_type != 2) return;
    switch (f.field_number) {
      case 1:  // component
        manifest.component.assign(f.bytes_value);
        break;
      case 5:  // inputs (repeated PortSpec)
        manifest.inputs.push_back(ParsePortSpec(f.bytes_value));
        break;
      case 6:  // outputs (repeated PortSpec)
        manifest.outputs.push_back(ParsePortSpec(f.bytes_value));
        break;
      case 9:  // descriptor_set
        manifest.descriptor_set_bytes.assign(f.bytes_value);
        break;
      default:
        break;
    }
  });
  if (!ok) {
    return Result<ManifestLite>::Fail(
        MakeError(Kind::Environment, "a well-formed ComponentManifest wire stream", "malformed bytes", path.string()));
  }
  if (manifest.component.empty()) {
    return Result<ManifestLite>::Fail(
        MakeError(Kind::Environment, "a ComponentManifest with a non-empty component field", "empty", path.string()));
  }
  if (manifest.descriptor_set_bytes.empty()) {
    return Result<ManifestLite>::Fail(MakeError(
        Kind::Environment, "a ComponentManifest carrying its own descriptor_set (R-SIM-11)", "empty",
        path.string()));
  }
  return Result<ManifestLite>::Ok(std::move(manifest));
}

// ---- column -> port grouping -------------------------------------------

// One column's resolved destination: either a leaf field inside a
// reconstructed port message, or "drop" (a `<component>.host.*`
// diagnostic column with no protobuf home).
struct ColumnBinding {
  const ErgColumn* column = nullptr;
  std::vector<std::string> field_path;  // e.g. {"left", "observable_fraction"}
};

struct PortGroup {
  std::string port_name;
  std::string proto_type;
  std::vector<ColumnBinding> bindings;
};

// Longest-prefix-match `column_name` against every known port name
// (`bsd.outputs`, `bsd.compState`, ...). A match at `name` means either
// `column_name == name` (a bare-scalar port -- rejected below, no real
// port in this repo is scalar-typed) or `column_name` starts with
// `name + "."`, in which case the remainder is the field path.
std::optional<std::string> LongestPortMatch(
    const std::string& column_name, const std::vector<std::string>& port_names_by_length_desc) {
  for (const std::string& name : port_names_by_length_desc) {
    if (column_name == name) return name;
    if (column_name.size() > name.size() + 1 && column_name.compare(0, name.size(), name) == 0 &&
        column_name[name.size()] == '.') {
      return name;
    }
  }
  return std::nullopt;
}

std::vector<std::string> SplitDotted(const std::string& s) {
  std::vector<std::string> parts;
  std::size_t start = 0;
  while (start <= s.size()) {
    const auto dot = s.find('.', start);
    if (dot == std::string::npos) {
      parts.push_back(s.substr(start));
      break;
    }
    parts.push_back(s.substr(start, dot - start));
    start = dot + 1;
  }
  return parts;
}

// Reads one column's raw bytes out of a row buffer and returns it as a
// `double` (a lossless widening for both `Double`/`Int` -- the proto
// field's own `cpp_type()` decides the final narrowing, not this step).
double ReadColumnAsDouble(const ErgColumn& column, const std::uint8_t* row_base) {
  const std::uint8_t* p = row_base + column.byte_offset;
  if (column.type == ErgType::kDouble) {
    double v;
    std::memcpy(&v, p, sizeof(v));
    return v;
  }
  // kInt: 4-byte little-endian signed int32 (the real fixtures' own type).
  std::int32_t v;
  std::memcpy(&v, p, sizeof(v));
  return static_cast<double>(v);
}

// Sets one leaf field on `message` from a column's raw value, typed off
// the PROTO field's own `cpp_type()` -- never the ERG column's `Double`/
// `Int` tag alone, since e.g. an enum is ERG-`Int` but proto-`CPPTYPE_ENUM`.
Result<bool> SetLeafField(
    pb::Message* message, const pb::FieldDescriptor* field, double raw_value, const std::string& column_name) {
  const pb::Reflection* refl = message->GetReflection();
  switch (field->cpp_type()) {
    case pb::FieldDescriptor::CPPTYPE_DOUBLE:
      refl->SetDouble(message, field, raw_value);
      break;
    case pb::FieldDescriptor::CPPTYPE_FLOAT:
      refl->SetFloat(message, field, static_cast<float>(raw_value));
      break;
    case pb::FieldDescriptor::CPPTYPE_INT32:
      refl->SetInt32(message, field, static_cast<std::int32_t>(raw_value));
      break;
    case pb::FieldDescriptor::CPPTYPE_UINT32:
      refl->SetUInt32(message, field, static_cast<std::uint32_t>(raw_value));
      break;
    case pb::FieldDescriptor::CPPTYPE_INT64:
      refl->SetInt64(message, field, static_cast<std::int64_t>(raw_value));
      break;
    case pb::FieldDescriptor::CPPTYPE_UINT64:
      refl->SetUInt64(message, field, static_cast<std::uint64_t>(raw_value));
      break;
    case pb::FieldDescriptor::CPPTYPE_BOOL:
      refl->SetBool(message, field, raw_value != 0.0);
      break;
    case pb::FieldDescriptor::CPPTYPE_ENUM: {
      const pb::EnumValueDescriptor* value = field->enum_type()->FindValueByNumber(static_cast<int>(raw_value));
      if (value == nullptr) {
        return Result<bool>::Fail(MakeError(
            Kind::Contract, "a value declared in enum " + field->enum_type()->full_name(),
            std::to_string(static_cast<int>(raw_value)), "column '" + column_name + "'"));
      }
      refl->SetEnumValue(message, field, static_cast<int>(raw_value));
      break;
    }
    default:
      return Result<bool>::Fail(MakeError(
          Kind::Contract, "a scalar or enum leaf field", "cpp_type=" + std::to_string(field->cpp_type()),
          "column '" + column_name + "' -> field '" + field->full_name() + "'"));
  }
  return Result<bool>::Ok(true);
}

class ErgReader final : public Reader {
 public:
  Result<bool> Open(const std::filesystem::path& path) override {
    // ---- binary header ----
    std::ifstream in(path, std::ios::binary);
    if (!in) {
      return Result<bool>::Fail(MakeError(Kind::Environment, "a readable .erg file", "could not open", path.string()));
    }
    std::ostringstream buf;
    buf << in.rdbuf();
    data_ = buf.str();

    static constexpr std::size_t kHeaderSize = 16;
    static constexpr char kMagic[8] = {'C', 'M', '-', 'E', 'R', 'G', '\0', '\0'};
    if (data_.size() < kHeaderSize || std::memcmp(data_.data(), kMagic, 8) != 0) {
      return Result<bool>::Fail(MakeError(
          Kind::Environment, "a file beginning with the \"CM-ERG\" magic header", "absent or too short",
          path.string()));
    }
    std::uint16_t version = 0;
    std::memcpy(&version, data_.data() + 8, sizeof(version));
    std::uint32_t declared_row_size = 0;
    std::memcpy(&declared_row_size, data_.data() + 10, sizeof(declared_row_size));
    row_size_ = declared_row_size;

    // ---- .erg.info sidecar ----
    const std::filesystem::path info_path = std::filesystem::path(path).replace_extension(".erg.info");
    auto columns_result = ParseErgInfo(info_path);
    if (!columns_result.ok()) return Result<bool>::Fail(columns_result.error());
    columns_ = std::move(columns_result.value());

    if (columns_.empty() || columns_.front().name != "Time") {
      return Result<bool>::Fail(MakeError(
          Kind::Environment, "column 1 named \"Time\" (the row's own clock)",
          columns_.empty() ? "no columns" : "column 1 = '" + columns_.front().name + "'", info_path.string()));
    }
    const std::size_t computed_row_size = columns_.back().byte_offset + columns_.back().byte_width;
    if (computed_row_size != row_size_) {
      return Result<bool>::Fail(MakeError(
          Kind::Environment,
          ".erg.info's own declared columns to sum to the .erg header's row_size (" + std::to_string(row_size_) + ")",
          std::to_string(computed_row_size) + " bytes from " + std::to_string(columns_.size()) + " columns",
          path.string(),
          "the header and the sidecar disagree about this file's own row shape"));
    }
    row_count_ = (data_.size() - kHeaderSize) / row_size_;
    if (kHeaderSize + row_count_ * row_size_ != data_.size()) {
      return Result<bool>::Fail(MakeError(
          Kind::Environment, "a body length that is an exact multiple of row_size", "a partial trailing row",
          path.string()));
    }

    // ---- manifest sidecar ----
    std::filesystem::path manifest_path = path;
    manifest_path.replace_extension("");
    manifest_path += ".manifest.pb";
    auto manifest_result = ParseManifest(manifest_path);
    if (!manifest_result.ok()) return Result<bool>::Fail(manifest_result.error());
    const ManifestLite manifest = std::move(manifest_result.value());

    // ---- descriptor pool, from the manifest's own real FileDescriptorSet ----
    pb::FileDescriptorSet file_descriptor_set;
    if (!file_descriptor_set.ParseFromString(manifest.descriptor_set_bytes)) {
      return Result<bool>::Fail(MakeError(
          Kind::Environment, "a manifest descriptor_set that parses as a real FileDescriptorSet",
          "failed to parse", manifest_path.string()));
    }
    for (const auto& file_proto : file_descriptor_set.file()) {
      descriptor_db_.Add(file_proto);
    }
    descriptor_pool_ = std::make_unique<pb::DescriptorPool>(&descriptor_db_);
    message_factory_ = std::make_unique<pb::DynamicMessageFactory>(descriptor_pool_.get());

    // ---- column -> port grouping ----
    std::vector<PortSpecLite> all_ports = manifest.outputs;
    all_ports.insert(all_ports.end(), manifest.inputs.begin(), manifest.inputs.end());
    std::vector<std::string> port_names;
    for (const PortSpecLite& p : all_ports) port_names.push_back(p.name);
    std::sort(port_names.begin(), port_names.end(),
              [](const std::string& a, const std::string& b) { return a.size() > b.size(); });

    std::map<std::string, PortGroup> groups;  // port_name -> group, insertion order preserved by outputs-then-inputs
    std::vector<std::string> ordered_port_names;
    const std::string host_prefix = manifest.component + ".host.";

    for (std::size_t i = 1; i < columns_.size(); ++i) {  // skip column 0, Time
      const ErgColumn& column = columns_[i];
      if (column.name == "$none$") continue;  // a declared-but-unused padding column
      if (column.name.rfind(host_prefix, 0) == 0) continue;  // df.host.* diagnostics: dropped, named above

      const auto matched = LongestPortMatch(column.name, port_names);
      if (!matched) {
        return Result<bool>::Fail(MakeError(
            Kind::Environment, "every non-\"" + host_prefix + "*\" column to match a real manifest port name",
            "'" + column.name + "' matches none", path.string()));
      }
      const std::string field_path_str = column.name.substr(matched->size() + 1);
      if (field_path_str.empty()) {
        return Result<bool>::Fail(MakeError(
            Kind::Internal, "a field path after the matched port name", "empty (bare-scalar port match)",
            "column '" + column.name + "'"));
      }

      if (groups.find(*matched) == groups.end()) {
        const auto port_it = std::find_if(
            all_ports.begin(), all_ports.end(), [&](const PortSpecLite& p) { return p.name == *matched; });
        groups[*matched] = PortGroup{*matched, port_it->proto_type, {}};
        ordered_port_names.push_back(*matched);
      }
      groups[*matched].bindings.push_back(ColumnBinding{&column, SplitDotted(field_path_str)});
    }

    for (const std::string& name : ordered_port_names) {
      PortGroup& group = groups[name];
      const pb::Descriptor* descriptor = descriptor_pool_->FindMessageTypeByName(group.proto_type);
      if (descriptor == nullptr) {
        return Result<bool>::Fail(MakeError(
            Kind::Environment, "the manifest's descriptor_set to contain " + group.proto_type,
            "not found", manifest_path.string()));
      }
      resolved_ports_.push_back(ResolvedPort{group, descriptor, message_factory_->GetPrototype(descriptor)});
    }

    // Validate every binding's field path resolves through the real
    // descriptor tree to a settable scalar/enum leaf NOW, once, rather than
    // discovering a bad path per row -- the one thing that genuinely cannot
    // be checked here is an enum column's numeric value being outside its
    // proto's declared range, since that depends on the row's own data
    // (`Pull()` leaves that one field at its proto3 default rather than
    // fabricate a value, per `R-SIM-25`).
    for (const ResolvedPort& port : resolved_ports_) {
      for (const ColumnBinding& binding : port.group.bindings) {
        const pb::Descriptor* current_descriptor = port.descriptor;
        for (std::size_t seg = 0; seg + 1 < binding.field_path.size(); ++seg) {
          const pb::FieldDescriptor* field = current_descriptor->FindFieldByName(binding.field_path[seg]);
          if (field == nullptr || field->cpp_type() != pb::FieldDescriptor::CPPTYPE_MESSAGE || field->is_repeated()) {
            return Result<bool>::Fail(MakeError(
                Kind::Environment, "column '" + binding.column->name + "'s field path to resolve inside " +
                                        port.group.proto_type + " via singular message fields",
                "no such singular message field '" + binding.field_path[seg] + "' at that point in the path",
                path.string()));
          }
          current_descriptor = field->message_type();
        }
        const pb::FieldDescriptor* leaf = current_descriptor->FindFieldByName(binding.field_path.back());
        if (leaf == nullptr) {
          return Result<bool>::Fail(MakeError(
              Kind::Environment, "column '" + binding.column->name + "'s leaf field to exist on " +
                                      current_descriptor->full_name(),
              "no field '" + binding.field_path.back() + "'", path.string()));
        }
        if (leaf->is_repeated() || leaf->cpp_type() == pb::FieldDescriptor::CPPTYPE_MESSAGE ||
            leaf->cpp_type() == pb::FieldDescriptor::CPPTYPE_STRING) {
          return Result<bool>::Fail(MakeError(
              Kind::Environment, "column '" + binding.column->name + "' to address a scalar or enum leaf field",
              "resolved to " + leaf->full_name() + " (cpp_type=" + std::to_string(leaf->cpp_type()) + ")",
              path.string()));
        }
      }
    }

    opened_ = true;
    return Result<bool>::Ok(true);
  }

  std::map<std::string, TopicInfo> Describe() const override {
    std::map<std::string, TopicInfo> result;
    for (const ResolvedPort& port : resolved_ports_) {
      TopicInfo info;
      info.schema_name = port.group.proto_type;
      info.provenance = Provenance::kMeasured;
      pb::FileDescriptorProto file_proto;
      port.descriptor->file()->CopyTo(&file_proto);
      info.schema_bytes.resize(file_proto.ByteSizeLong());
      file_proto.SerializeToArray(info.schema_bytes.data(), static_cast<int>(info.schema_bytes.size()));
      result[port.group.port_name] = std::move(info);
    }
    return result;
  }

  void Seek(std::int64_t log_time_ns) override {
    lookahead_.reset();
    // `Time` is monotonic (never assumed uniformly spaced) -- binary search
    // the first row whose own Time, converted to ns, is >= the target.
    std::size_t lo = 0, hi = row_count_;
    while (lo < hi) {
      const std::size_t mid = lo + (hi - lo) / 2;
      if (RowLogTimeNs(mid) < log_time_ns) {
        lo = mid + 1;
      } else {
        hi = mid;
      }
    }
    row_index_ = lo;
    port_index_ = 0;
  }

  Batch ReadRange(const ReadBounds& bounds) override {
    return detail::AccumulateBatch(bounds, lookahead_, [this]() { return Pull(); });
  }

  void Close() override { opened_ = false; }

  std::optional<std::vector<std::uint8_t>> GetMeta(const std::string&) const override {
    return std::nullopt;  // .erg carries no meta-block concept
  }

 private:
  struct ResolvedPort {
    PortGroup group;
    const pb::Descriptor* descriptor;
    const pb::Message* prototype;
  };

  const std::uint8_t* RowBase(std::size_t row_index) const {
    return reinterpret_cast<const std::uint8_t*>(data_.data()) + 16 + row_index * row_size_;
  }

  std::int64_t RowLogTimeNs(std::size_t row_index) const {
    const double time_s = ReadColumnAsDouble(columns_[0], RowBase(row_index));
    return static_cast<std::int64_t>(time_s * 1e9 + (time_s >= 0 ? 0.5 : -0.5));
  }

  std::optional<RawMessage> Pull() {
    if (!opened_ || row_index_ >= row_count_) return std::nullopt;

    const ResolvedPort& port = resolved_ports_[port_index_];
    std::unique_ptr<pb::Message> message(port.prototype->New());
    const std::uint8_t* row_base = RowBase(row_index_);

    // Every binding's path was already validated once in Open() -- the
    // walk below can only still fail at the leaf, and only for an enum
    // column whose row value is outside its proto's declared range, which
    // genuinely depends on this row's own data and cannot be checked
    // ahead of time. `SetLeafField` reports that case in its own Result;
    // this loop leaves the one affected field at its proto3 default
    // rather than fabricate a value (R-SIM-25) -- every other field in
    // this same message is unaffected.
    for (const ColumnBinding& binding : port.group.bindings) {
      pb::Message* current = message.get();
      const pb::Descriptor* current_descriptor = port.descriptor;
      for (std::size_t seg = 0; seg + 1 < binding.field_path.size(); ++seg) {
        const pb::FieldDescriptor* field = current_descriptor->FindFieldByName(binding.field_path[seg]);
        current = current->GetReflection()->MutableMessage(current, field);
        current_descriptor = field->message_type();
      }
      const pb::FieldDescriptor* leaf = current_descriptor->FindFieldByName(binding.field_path.back());
      const double raw_value = ReadColumnAsDouble(*binding.column, row_base);
      const Result<bool> set_result = SetLeafField(current, leaf, raw_value, binding.column->name);
      (void)set_result;  // failure here means only this one field stays default; see comment above
    }

    RawMessage out;
    out.topic = port.group.port_name;
    out.log_time_ns = RowLogTimeNs(row_index_);
    out.capture_time_ns = std::nullopt;  // R-SIM-14: never defaulted to reception
    out.payload.resize(message->ByteSizeLong());
    message->SerializeToArray(out.payload.data(), static_cast<int>(out.payload.size()));

    ++port_index_;
    if (port_index_ >= resolved_ports_.size()) {
      port_index_ = 0;
      ++row_index_;
    }
    return out;
  }

  std::string data_;
  std::size_t row_size_ = 0;
  std::size_t row_count_ = 0;
  std::vector<ErgColumn> columns_;
  pb::SimpleDescriptorDatabase descriptor_db_;
  std::unique_ptr<pb::DescriptorPool> descriptor_pool_;
  std::unique_ptr<pb::DynamicMessageFactory> message_factory_;
  std::vector<ResolvedPort> resolved_ports_;
  bool opened_ = false;
  std::size_t row_index_ = 0;
  std::size_t port_index_ = 0;
  std::optional<RawMessage> lookahead_;
};

}  // namespace

Result<bool> RegisterErg(CodecRegistry& registry) {
  Capabilities capabilities;
  capabilities.embedded_schemas = false;  // needs the .manifest.pb sidecar
  capabilities.random_access = true;      // fixed row size, Time is monotonic
  capabilities.meta_blocks = false;
  capabilities.arbitrary_topics = false;  // topic vocabulary fixed at Open()
  capabilities.round_trips = false;       // read-only: .erg is CarMaker-native, we never write it
  capabilities.capture_time = false;      // no separate capture clock exists in this format

  return registry.Register(
      ".erg", capabilities, []() -> std::unique_ptr<Reader> { return std::make_unique<ErgReader>(); });
}

}  // namespace simcore::io::codecs
