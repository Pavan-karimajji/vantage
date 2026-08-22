// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   IMP-0099/0100/0102/0105: `Address` application over a decoded
///   message -- no string parsing (the resolved `MutationAddress`, `path`
///   as field names, one `index`/`all_elements` for the whole address,
///   already arrived that way, `IMP-0008`). Ported from
///   `runspec/address.py::_descend`/`_resolve_scalar_target`/
///   `_resolve_repeated_target`/`_clear_element_in_place`/
///   `_apply_structural`/`apply_override`. `select`/`drop`'s
///   fixed-slots-clears-in-place-never-compacts rule (`IMP-0100`) is the
///   one Python ported unchanged.
///
///   `Mutator` (`SW-0102`/`SW-0105`, decode-once/encode-once/`Touches`)
///   lives in this file too -- it is the one caller of `ApplyAtAddress`
///   in this slice, and splitting it into a fifth file the design's own
///   skeleton (`verbs`/`faults`/`address`/`window`) does not name would
///   be an unrequested file, not a requested simplification.
///
///   Byte-level reflection reuses `io/codecs/erg.cpp`'s own established
///   technique (`DescriptorPool`/`DynamicMessageFactory`/
///   `google::protobuf::Reflection`, that file's own header comment) --
///   not a second decode mechanism.
/// @author Pavan Karimajji

#include "simcore/mutate.hpp"

#include <algorithm>
#include <memory>
#include <set>

#include <google/protobuf/descriptor.h>
#include <google/protobuf/dynamic_message.h>

namespace simcore::mutate {

namespace {

namespace pb = google::protobuf;

Error MakeError(Kind kind, std::string expected, std::string found, std::string where, std::string hint = "") {
  return Error{kind, std::move(expected), std::move(found), std::move(where), std::move(hint)};
}

// Navigates every segment but the last -- each must name an existing,
// SINGULAR message field (a non-final indexed segment is refused one
// layer up, `IMP-0008`'s own documented limit: the flattened
// `{path[], index}` shape has room for exactly one index, on the final
// segment). Ported from `_descend`, restricted to the shape this codebase
// actually emits.
Result<pb::Message*> DescendToParent(pb::Message& message, const std::vector<std::string>& path, const std::string& where) {
  pb::Message* current = &message;
  for (std::size_t i = 0; i + 1 < path.size(); ++i) {
    const pb::FieldDescriptor* field = current->GetDescriptor()->FindFieldByName(path[i]);
    if (field == nullptr || field->cpp_type() != pb::FieldDescriptor::CPPTYPE_MESSAGE || field->is_repeated()) {
      return Result<pb::Message*>::Fail(MakeError(
          Kind::Contract, "an existing singular message field '" + path[i] + "'",
          field == nullptr ? "no such field" : "not a singular message field", where));
    }
    current = current->GetReflection()->MutableMessage(current, field);
  }
  return Result<pb::Message*>::Ok(current);
}

// `container`/`field`'s value as a bare double, at `index` when the field
// is repeated -- mirrors `_read_scalar`, typed off the PROTO field's own
// `cpp_type()` (same convention `erg.cpp::SetLeafField` uses for writes).
Result<double> GetLeafField(const pb::Message& container, const pb::FieldDescriptor& field, std::optional<int> index,
                             const std::string& where) {
  const pb::Reflection* refl = container.GetReflection();
  const bool repeated = index.has_value();
  switch (field.cpp_type()) {
    case pb::FieldDescriptor::CPPTYPE_DOUBLE:
      return Result<double>::Ok(repeated ? refl->GetRepeatedDouble(container, &field, *index) : refl->GetDouble(container, &field));
    case pb::FieldDescriptor::CPPTYPE_FLOAT:
      return Result<double>::Ok(repeated ? refl->GetRepeatedFloat(container, &field, *index) : refl->GetFloat(container, &field));
    case pb::FieldDescriptor::CPPTYPE_INT32:
      return Result<double>::Ok(repeated ? refl->GetRepeatedInt32(container, &field, *index) : refl->GetInt32(container, &field));
    case pb::FieldDescriptor::CPPTYPE_UINT32:
      return Result<double>::Ok(repeated ? refl->GetRepeatedUInt32(container, &field, *index) : refl->GetUInt32(container, &field));
    case pb::FieldDescriptor::CPPTYPE_INT64:
      return Result<double>::Ok(static_cast<double>(
          repeated ? refl->GetRepeatedInt64(container, &field, *index) : refl->GetInt64(container, &field)));
    case pb::FieldDescriptor::CPPTYPE_UINT64:
      return Result<double>::Ok(static_cast<double>(
          repeated ? refl->GetRepeatedUInt64(container, &field, *index) : refl->GetUInt64(container, &field)));
    case pb::FieldDescriptor::CPPTYPE_BOOL:
      return Result<double>::Ok((repeated ? refl->GetRepeatedBool(container, &field, *index) : refl->GetBool(container, &field)) ? 1.0
                                                                                                                                    : 0.0);
    case pb::FieldDescriptor::CPPTYPE_ENUM:
      return Result<double>::Ok(static_cast<double>(
          repeated ? refl->GetRepeatedEnumValue(container, &field, *index) : refl->GetEnumValue(container, &field)));
    default:
      return Result<double>::Fail(
          MakeError(Kind::Contract, "a scalar or enum leaf field", "field '" + field.full_name() + "'", where));
  }
}

Result<bool> SetLeafField(pb::Message& container, const pb::FieldDescriptor& field, std::optional<int> index, double value,
                           const std::string& where) {
  const pb::Reflection* refl = container.GetReflection();
  const bool repeated = index.has_value();
  switch (field.cpp_type()) {
    case pb::FieldDescriptor::CPPTYPE_DOUBLE:
      repeated ? refl->SetRepeatedDouble(&container, &field, *index, value) : refl->SetDouble(&container, &field, value);
      break;
    case pb::FieldDescriptor::CPPTYPE_FLOAT:
      repeated ? refl->SetRepeatedFloat(&container, &field, *index, static_cast<float>(value))
               : refl->SetFloat(&container, &field, static_cast<float>(value));
      break;
    case pb::FieldDescriptor::CPPTYPE_INT32:
      repeated ? refl->SetRepeatedInt32(&container, &field, *index, static_cast<std::int32_t>(value))
               : refl->SetInt32(&container, &field, static_cast<std::int32_t>(value));
      break;
    case pb::FieldDescriptor::CPPTYPE_UINT32:
      repeated ? refl->SetRepeatedUInt32(&container, &field, *index, static_cast<std::uint32_t>(value))
               : refl->SetUInt32(&container, &field, static_cast<std::uint32_t>(value));
      break;
    case pb::FieldDescriptor::CPPTYPE_INT64:
      repeated ? refl->SetRepeatedInt64(&container, &field, *index, static_cast<std::int64_t>(value))
               : refl->SetInt64(&container, &field, static_cast<std::int64_t>(value));
      break;
    case pb::FieldDescriptor::CPPTYPE_UINT64:
      repeated ? refl->SetRepeatedUInt64(&container, &field, *index, static_cast<std::uint64_t>(value))
               : refl->SetUInt64(&container, &field, static_cast<std::uint64_t>(value));
      break;
    case pb::FieldDescriptor::CPPTYPE_BOOL:
      repeated ? refl->SetRepeatedBool(&container, &field, *index, value != 0.0) : refl->SetBool(&container, &field, value != 0.0);
      break;
    case pb::FieldDescriptor::CPPTYPE_ENUM: {
      const pb::EnumValueDescriptor* enum_value = field.enum_type()->FindValueByNumber(static_cast<int>(value));
      if (enum_value == nullptr) {
        return Result<bool>::Fail(MakeError(Kind::Contract, "a value declared in enum " + field.enum_type()->full_name(),
                                             std::to_string(static_cast<int>(value)), where));
      }
      repeated ? refl->SetRepeatedEnumValue(&container, &field, *index, static_cast<int>(value))
               : refl->SetEnumValue(&container, &field, static_cast<int>(value));
      break;
    }
    default:
      return Result<bool>::Fail(
          MakeError(Kind::Contract, "a scalar or enum leaf field", "field '" + field.full_name() + "'", where));
  }
  return Result<bool>::Ok(true);
}

// A repeated element clears itself IN PLACE (`fixed_slots=true`) -- a
// message element via its own `Clear()`, a scalar/enum element reset to
// its type's proto3 zero value. Ported from `_clear_element_in_place`.
void ClearElementInPlace(pb::Message& container, const pb::FieldDescriptor& field, int index) {
  const pb::Reflection* refl = container.GetReflection();
  if (field.cpp_type() == pb::FieldDescriptor::CPPTYPE_MESSAGE) {
    refl->MutableRepeatedMessage(&container, &field, index)->Clear();
    return;
  }
  if (field.cpp_type() == pb::FieldDescriptor::CPPTYPE_ENUM) {
    refl->SetRepeatedEnumValue(&container, &field, index, field.enum_type()->value(0)->number());
    return;
  }
  (void)SetLeafField(container, field, index, 0.0, "mutate::ClearElementInPlace");
}

// Removes index `i`, preserving order of the survivors (`del container[i]`'s
// own semantics) -- protobuf's reflection API has no direct erase, so this
// left-shifts every later element by one swap then drops the now-duplicate
// tail, the same technique the generated Python container uses internally.
void EraseRepeatedElement(pb::Message& container, const pb::FieldDescriptor& field, int index) {
  const pb::Reflection* refl = container.GetReflection();
  const int length = refl->FieldSize(container, &field);
  for (int i = index; i + 1 < length; ++i) {
    refl->SwapElements(&container, &field, i, i + 1);
  }
  refl->RemoveLast(&container, &field);
}

// Ported from `_apply_structural`: `select` keeps the addressed element(s)
// and removes every other; `drop` removes exactly the addressed one(s).
// `fixed_slots=true` clears in place (never renumbers); `false` compacts,
// highest index first so an earlier delete never renumbers a later target
// still to be processed.
void ApplyStructural(pb::Message& container, const pb::FieldDescriptor& field, Verb verb, std::optional<int> index,
                      bool all_elements, bool fixed_slots) {
  const pb::Reflection* refl = container.GetReflection();
  const int length = refl->FieldSize(container, &field);
  std::vector<int> targets;
  if (verb == Verb::Select) {
    std::set<int> keep;
    if (all_elements) {
      for (int i = 0; i < length; ++i) keep.insert(i);
    } else {
      keep.insert(*index);
    }
    for (int i = 0; i < length; ++i) {
      if (!keep.count(i)) targets.push_back(i);
    }
  } else {  // Verb::Drop
    if (all_elements) {
      for (int i = 0; i < length; ++i) targets.push_back(i);
    } else {
      targets.push_back(*index);
    }
  }

  if (fixed_slots) {
    for (int i : targets) ClearElementInPlace(container, field, i);
    return;
  }
  std::sort(targets.rbegin(), targets.rend());  // highest index first -- an unvisited target must never be renumbered
  for (int i : targets) EraseRepeatedElement(container, field, i);
}

}  // namespace

Result<bool> ApplyAtAddress(pb::Message& message, const MutationAddress& address, Verb verb,
                             const std::vector<double>& operands, std::optional<bool> fixed_slots,
                             std::optional<double>& first_seen) {
  const std::string where = "mutate::ApplyAtAddress address '" + address.port + "." +
                             (address.path.empty() ? std::string("<port>") : address.path.back()) + "'";

  if (verb == Verb::Select || verb == Verb::Drop) {
    if (address.path.empty() || (!address.index.has_value() && !address.all_elements)) {
      return Result<bool>::Fail(MakeError(
          Kind::Authoring, "an indexed repeated field for select/drop, e.g. 'port.repeated[i]' or '[*]'",
          "address carries no index", where,
          "select/drop address one or every element of a repeated field, never a bare field"));
    }
    Result<pb::Message*> parent = DescendToParent(message, address.path, where);
    if (!parent.ok()) return Result<bool>::Fail(parent.error());
    const pb::FieldDescriptor* field = parent.value()->GetDescriptor()->FindFieldByName(address.path.back());
    if (field == nullptr || !field->is_repeated()) {
      return Result<bool>::Fail(MakeError(Kind::Contract, "an existing repeated field '" + address.path.back() + "'",
                                           field == nullptr ? "no such field" : "not repeated", where));
    }
    if (!fixed_slots.has_value()) {
      return Result<bool>::Fail(MakeError(
          Kind::Contract, "the port's manifest to declare fixed_slots for a " + ToString(verb) + " override",
          "fixed_slots absent from the manifest", where,
          "drop/select on a repeated field needs fixed_slots declared true or false -- neither may be guessed (NR-SIM-4)"));
    }
    ApplyStructural(*parent.value(), *field, verb, address.index, address.all_elements, *fixed_slots);
    return Result<bool>::Ok(true);
  }

  // Arithmetic (const/hold/offset/scale).
  if (address.path.empty()) {
    return Result<bool>::Fail(MakeError(Kind::Authoring, "a field path for an arithmetic override (const/hold/offset/scale)",
                                         "address is the whole port", where,
                                         "a whole-message port has no single number to override -- address a field"));
  }
  if (address.all_elements) {
    return Result<bool>::Fail(MakeError(Kind::Authoring, "a single index for an arithmetic override, never '*'",
                                         "address is every element", where,
                                         "'*' means every element -- only select/drop operate on a whole set at once"));
  }
  Result<pb::Message*> parent = DescendToParent(message, address.path, where);
  if (!parent.ok()) return Result<bool>::Fail(parent.error());
  const pb::FieldDescriptor* leaf = parent.value()->GetDescriptor()->FindFieldByName(address.path.back());
  if (leaf == nullptr) {
    return Result<bool>::Fail(MakeError(Kind::Contract, "an existing field '" + address.path.back() + "'", "no such field", where));
  }
  Result<double> current = GetLeafField(*parent.value(), *leaf, address.index, where);
  if (!current.ok()) return Result<bool>::Fail(current.error());

  const double effective_first = first_seen.has_value() ? *first_seen : current.value();
  const double operand = operands.empty() ? 0.0 : operands.front();
  Result<double> new_value = ApplyArithmetic(verb, current.value(), effective_first, operand);
  if (!new_value.ok()) return Result<bool>::Fail(new_value.error());

  Result<bool> set_result = SetLeafField(*parent.value(), *leaf, address.index, new_value.value(), where);
  if (!set_result.ok()) return set_result;
  first_seen = effective_first;
  return Result<bool>::Ok(true);
}

Mutator::Mutator(std::vector<SpecMutation> mutations, PortResolver resolve_port)
    : mutations_(std::move(mutations)), resolve_port_(std::move(resolve_port)) {}

namespace {
std::string TouchKey(const std::string& stage, const std::string& port) { return stage + "." + port; }
}  // namespace

bool Mutator::Touches(const std::string& stage, const std::string& port) const {
  for (const SpecMutation& mutation : mutations_) {
    if (mutation.address.stage == stage && mutation.address.port == port) return true;
  }
  return false;
}

Result<bool> Mutator::ApplyTo(bus::PortValue& value, const std::string& bare_port, std::int64_t t_sim_ns) const {
  const std::string& stage = value.header.producer;
  const std::string& port = bare_port;
  if (!Touches(stage, port)) return Result<bool>::Ok(true);

  std::optional<PortInfo> info = resolve_port_(stage, port);
  if (!info.has_value()) {
    return Result<bool>::Fail(MakeError(Kind::Environment, "a resolvable Descriptor for port '" + port + "'",
                                         "resolve_port returned none", "mutate::Mutator::ApplyTo"));
  }
  if (info->descriptor == nullptr) {
    return Result<bool>::Fail(
        MakeError(Kind::Environment, "a non-null Descriptor", "descriptor == nullptr", "mutate::Mutator::ApplyTo"));
  }

  pb::DynamicMessageFactory factory;
  std::unique_ptr<pb::Message> message(factory.GetPrototype(info->descriptor)->New());
  if (!message->ParseFromArray(value.payload.data(), static_cast<int>(value.payload.size()))) {
    return Result<bool>::Fail(MakeError(Kind::Contract, "payload bytes that parse as " + info->descriptor->full_name(),
                                         "ParseFromArray failed", "mutate::Mutator::ApplyTo"));
  }

  bool applied_any = false;
  for (const SpecMutation& mutation : mutations_) {
    if (mutation.address.stage != stage || mutation.address.port != port) continue;
    if (!InWindow(mutation.window_ns_start, mutation.window_ns_end, t_sim_ns)) continue;

    Result<Verb> verb = ParseVerb(mutation.verb, "mutate::Mutator::ApplyTo verb");
    if (!verb.ok()) return Result<bool>::Fail(verb.error());

    const std::string key = TouchKey(stage, port) + "#" + mutation.verb;
    std::optional<double> first_seen;
    auto it = first_seen_.find(key);
    if (it != first_seen_.end()) first_seen = it->second;

    Result<bool> applied =
        ApplyAtAddress(*message, mutation.address, verb.value(), mutation.operands, info->fixed_slots, first_seen);
    if (!applied.ok()) return applied;
    if (first_seen.has_value()) first_seen_[key] = *first_seen;
    applied_any = true;
  }

  if (!applied_any) return Result<bool>::Ok(true);

  value.payload.resize(message->ByteSizeLong());
  message->SerializeToArray(value.payload.data(), static_cast<int>(value.payload.size()));
  value.origin = bus::Origin::Overridden;  // IMP-0103: travels on the value itself
  return Result<bool>::Ok(true);
}

}  // namespace simcore::mutate
