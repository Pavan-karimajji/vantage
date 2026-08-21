// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   IMP-0101/0104: the five closed fault verbs, each derived from
///   `bus::Header`'s own fields. Ported from `contracts/fault.py::
///   apply_fault` -- `drop`/`stale`/`invalidate` are metadata flips,
///   `delay` shifts `t_capture_ns` and refuses when it is unknown rather
///   than fabricating one (`R-SIM-14`'s two-clock rule paying off,
///   `IMP-0104`), and `corrupt` reuses `ApplyAtAddress`'s own `Verb::Const`
///   path -- never a second byte-mutation mechanism (`contracts/fault.py`'s
///   own stated reason).
///
///   **`header.status`'s validity convention, decided here because
///   `bus.hpp` declares the field but no consumer gives it one yet**
///   (`test_ut_bus_header.cpp`'s own `status = 0` fixture is the only
///   precedent in the codebase, matching this domain's usual
///   zero-is-OK status-byte convention): `0` means valid, any nonzero
///   means invalid. `drop`/`invalidate` set it to `1` -- a real sentinel
///   named here, not a guess about a value nobody chose (`NR-SIM-4`
///   governs `age_ns()`'s own `unknown`; this is the narrower question of
///   which nonzero value means "invalid," which the ported Python side
///   never had to answer because its own `PortValue.valid` is a bare
///   bool).
/// @author Pavan Karimajji

#include "simcore/mutate.hpp"

#include <memory>

#include <google/protobuf/dynamic_message.h>

namespace simcore::mutate {

namespace {

namespace pb = google::protobuf;

Error MakeError(Kind kind, std::string expected, std::string found, std::string where, std::string hint = "") {
  return Error{kind, std::move(expected), std::move(found), std::move(where), std::move(hint)};
}

constexpr std::uint32_t kStatusInvalid = 1;

}  // namespace

Result<bus::PortValue> ApplyFault(const bus::PortValue& value, const FaultSpec& fault, std::int64_t t_sim_ns,
                                   std::optional<std::int64_t>& active_since, const pb::Descriptor* descriptor,
                                   pb::MessageFactory* factory) {
  if (!InWindow(fault.window_ns_start, fault.window_ns_end, t_sim_ns)) {
    return Result<bus::PortValue>::Ok(value);  // unchanged; active_since untouched
  }
  if (!active_since.has_value()) active_since = t_sim_ns;

  bus::PortValue result = value;
  result.origin = bus::Origin::Overridden;

  switch (fault.verb) {
    case Fault::Drop:
      // "the port does not arrive" -- no bytes, no decoded value either.
      result.payload.clear();
      result.updated = false;
      result.header.status = kStatusInvalid;
      break;

    case Fault::Stale:
      result.updated = false;
      result.hold_ns = t_sim_ns - *active_since;
      break;

    case Fault::Invalidate:
      // The payload survives -- only the metadata lies (a sensor
      // reporting its own fault, SS9.2). `updated` is left as-is.
      result.header.status = kStatusInvalid;
      break;

    case Fault::Delay: {
      if (!fault.value.has_value()) {
        return Result<bus::PortValue>::Fail(MakeError(Kind::Authoring, "a numeric value: for verb 'delay'",
                                                        "value absent", "mutate::ApplyFault"));
      }
      if (!result.header.t_capture_ns.has_value()) {
        return Result<bus::PortValue>::Fail(MakeError(
            Kind::Contract, "a known t_capture_ns to shift", "t_capture_ns is unknown", "mutate::ApplyFault",
            "delay shifts capture time and refuses rather than fabricating one it was never told (R-SIM-14)"));
      }
      const auto shift_ns = static_cast<std::int64_t>(*fault.value * 1e9);
      result.header.t_capture_ns = result.header.t_capture_ns.value() - shift_ns;
      break;
    }

    case Fault::Corrupt: {
      if (!fault.value.has_value()) {
        return Result<bus::PortValue>::Fail(MakeError(Kind::Authoring, "a numeric value: for verb 'corrupt'",
                                                        "value absent", "mutate::ApplyFault"));
      }
      if (descriptor == nullptr) {
        return Result<bus::PortValue>::Fail(MakeError(Kind::Environment, "a non-null Descriptor for corrupt",
                                                        "descriptor == nullptr", "mutate::ApplyFault"));
      }
      pb::MessageFactory* effective_factory = factory != nullptr ? factory : pb::MessageFactory::generated_factory();
      std::unique_ptr<pb::Message> message(effective_factory->GetPrototype(descriptor)->New());
      if (!message->ParseFromArray(result.payload.data(), static_cast<int>(result.payload.size()))) {
        return Result<bus::PortValue>::Fail(
            MakeError(Kind::Contract, "payload bytes that parse as " + descriptor->full_name(), "ParseFromArray failed",
                       "mutate::ApplyFault"));
      }
      std::optional<double> unused_first_seen;  // corrupt reuses CONST, which never reads `first`
      Result<bool> applied = ApplyAtAddress(*message, fault.address, Verb::Const, {*fault.value}, std::nullopt, unused_first_seen);
      if (!applied.ok()) return Result<bus::PortValue>::Fail(applied.error());
      result.payload.resize(message->ByteSizeLong());
      message->SerializeToArray(result.payload.data(), static_cast<int>(result.payload.size()));
      break;
    }
  }

  return Result<bus::PortValue>::Ok(std::move(result));
}

}  // namespace simcore::mutate
