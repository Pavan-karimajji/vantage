// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `SI-05` -- `mutate` (`WP-11`): the six closed override verbs, the five
///   closed fault verbs, the resolved address grammar's application to a
///   real decoded message, and time-window scoping.
///
///   **Ported from `adas_sim/config/{override,fault}.py` and
///   `adas_sim/runspec/address.py`'s `apply_override`/`_descend`/
///   `_resolve_scalar_target`/`_resolve_repeated_target`/
///   `_apply_structural`** (`WP-11`'s own `MOVE`/`DEDUPE` source, read
///   directly rather than reinvented -- same discipline `WP-09`/`WP-10`
///   used). The Python side stays the one place a raw address STRING is
///   parsed (`R-SIM-15`'s closed grammar, `parse_address`); by the time a
///   mutation reaches `simcore` it has already been resolved into
///   `MutationAddress` (`runspec.hpp`, `IMP-0008`'s own flat shape) --
///   nothing in this file parses a string address, matching the design
///   skeleton's own "the address arrives RESOLVED from the spec; nothing
///   here parses."
///
///   **Byte-level application reuses `io/codecs/erg.cpp`'s own
///   `DescriptorPool`/`DynamicMessageFactory`/`google::protobuf::
///   Reflection` technique** (declared in that file's own header comment)
///   rather than inventing a second decode mechanism -- `NR-SIM-8`'s "a
///   third addressing scheme for the same objects is how a tool becomes
///   inconsistent" applies one level down to decode mechanisms too.
///
///   **Honestly out of scope this slice** (`IMP-0107`): refusing a
///   mutation whose `crosses_boundary` flag is set applies to data
///   `SpecMutation` does not yet carry -- `crosses_boundary`/`waiver` are
///   `SI-11`'s coherence classifier's own output (`WP-20`,
///   `graph/waiver.py`, not started; `emit.py` itself still writes
///   `"coherence": {"verdict": "unknown", ...}` for every run today). There
///   is no real flag `Mutator::ApplyTo` could read yet; wiring one now
///   would be a guess about a shape `WP-20` has not designed. `Touches`
///   (`IMP-0105`) and every other `WP-11` item are unaffected -- this is
///   the one line item with no target to build against, named rather than
///   silently dropped.
///
///   **`faults`, unlike `mutations`, have no `RunSpec` array of their own
///   yet** -- `run.faults:` lives only in the pre-`RunSpec` Python
///   `Pipeline` (`adas_sim/config/fault.py`, wired into
///   `Pipeline._apply_stimulus_faults`, never migrated into
///   `emit.py`/`runspec.hpp`, `WP-05`'s own scope boundary). `FaultSpec`
///   below is therefore a `simcore`-only type, its shape read directly off
///   `config/fault.py::Fault` (verb/address/value/window) but expressed
///   with this codebase's own nullable-window-pair idiom
///   (`SpecMutation::window_ns_start`/`window_ns_end`) rather than
///   Python's three-way `from_s`/`to_s`/`after_tick` union, since there is
///   no established "which of two window shapes wins" question here yet
///   -- one shape, matching the sibling type it sits beside.
/// @author Pavan Karimajji

#pragma once

#include <cstdint>
#include <functional>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <google/protobuf/message.h>

#include "simcore/bus.hpp"
#include "simcore/errors.hpp"
#include "simcore/runspec.hpp"

namespace simcore::mutate {

// SW-0097: six, closed. A `switch` over this enum must never carry a
// `default:` (mirrors `bus::Origin`'s own discipline) -- ANL-SW-24 diffs
// this set against the published schema on every build.
enum class Verb { Const, Hold, Offset, Scale, Select, Drop };

std::string ToString(Verb verb);

// The closed-list gate ported from `contracts/override.py::
// parse_override_verb`: a verb outside the six is a load error naming the
// closed set, never a warning.
Result<Verb> ParseVerb(std::string_view raw, const std::string& where);

// SW-0101: five, closed, each derived from `bus::Header`'s own fields --
// a sixth fault would need a ninth header field. Ported from
// `contracts/fault.py::FaultVerb`.
enum class Fault { Drop, Stale, Delay, Invalidate, Corrupt };

std::string ToString(Fault fault);

Result<Fault> ParseFault(std::string_view raw, const std::string& where);

// See this file's own top note: no `RunSpec` array carries this yet, so
// it is constructed directly by whatever caller owns `run.faults:` today
// (a test, or a future `WP-12`/scenario-loader consumer).
struct FaultSpec {
  Fault verb = Fault::Drop;
  MutationAddress address;
  std::optional<double> value;                    // required: corrupt, delay
  std::optional<std::int64_t> window_ns_start;     // both null == always active
  std::optional<std::int64_t> window_ns_end;
};

// IMP-0108: `[from_ns, to_ns)`, `null` meaning open on that side; both
// `null` means always active. Shared by `Mutator` (its own mutation's
// window) and `FaultSpec` -- one window rule, not two.
bool InWindow(std::optional<std::int64_t> start_ns, std::optional<std::int64_t> end_ns, std::int64_t t_sim_ns);

// IMP-0099/0100: what a resolved `MutationAddress` needs to reach real
// bytes -- the port's message `Descriptor` (to navigate `path`/`index`)
// and, for `select`/`drop` only, whether the port is `fixed_slots`
// (`NR-SIM-4`: `nullopt` is a `Contract` error naming the port, never a
// guessed default -- ports `apply_override`'s own `fixed_slots=None`
// branch unchanged).
struct PortInfo {
  const google::protobuf::Descriptor* descriptor = nullptr;
  std::optional<bool> fixed_slots;
};

// verbs.cpp: the four arithmetic verbs' bare-number math -- ported from
// `Override.apply`. `select`/`drop` are structural and never reach this
// function (mirrors the Python docstring's own warning).
Result<double> ApplyArithmetic(Verb verb, double current, double first, double operand);

// address.cpp: applies one verb at one resolved address to an already-
// decoded message, in place. Ported from `apply_override`'s own
// decode-outside/apply-inside split -- this function is the "apply"
// half; `Mutator::ApplyTo` below owns decode/encode (IMP-0102's own
// "decode once ... encode once", the one thing the Python split did not
// do). `first_seen` is `hold`'s cross-call memory, threaded by the
// caller exactly like Python's own `first_seen`/`effective_first`.
Result<bool> ApplyAtAddress(google::protobuf::Message& message, const MutationAddress& address, Verb verb,
                             const std::vector<double>& operands, std::optional<bool> fixed_slots,
                             std::optional<double>& first_seen);

// faults.cpp: one `PortValue`'s faulted form this tick -- ported from
// `apply_fault`. `active_since` is `stale`'s own cross-tick memory
// (mirrors `first_active_t_s`); returns the value unchanged, with
// `active_since` untouched, when the window is not active this tick.
// `corrupt` reuses `ApplyAtAddress`'s own `Verb::Const` path (never a
// second byte-mutation mechanism, `contracts/fault.py`'s own stated
// reason) and therefore needs `message` decoded the same way `Mutator`
// does -- `descriptor`/`factory` are the caller's, same reasoning as
// `Mutator`'s own `PortInfo` resolver.
Result<bus::PortValue> ApplyFault(const bus::PortValue& value, const FaultSpec& fault, std::int64_t t_sim_ns,
                                   std::optional<std::int64_t>& active_since,
                                   const google::protobuf::Descriptor* descriptor,
                                   google::protobuf::MessageFactory* factory);

// SI-05's own entry point: a bounded set of mutations, applied to the
// port values that carry them. `Mutator` owns no `DescriptorPool` of its
// own -- `resolve_port` is the caller's (a test fixture today; `WP-13`'s
// `Runner`, once built, owns the real per-run pool the same way
// `component.cpp::ReadManifest` already does for a single component's
// own manifest) -- so decode is possible without `mutate` inventing a
// second descriptor-pool lifetime.
class Mutator {
 public:
  using PortResolver = std::function<std::optional<PortInfo>(const std::string& stage, const std::string& port)>;

  Mutator(std::vector<SpecMutation> mutations, PortResolver resolve_port);

  // IMP-0102: decode once, apply every mutation touching this value,
  // encode once. A `value` this Mutator does not `Touches()` returns
  // unchanged, undecoded -- `Touches` is the gate `ApplyTo` itself uses,
  // not just a caller convenience (IMP-0105).
  //
  // IMP-0428: `bare_port` is the port name BARE (matching
  // `SpecMutation::address.port`'s own convention and `cycle_loop.cpp`'s
  // own caller-side pre-check) -- `value.port` itself is always
  // fully-qualified `"<stage>.<port>"` (`bus::PortBus::Publish`'s own
  // convention) and is never re-derived from here for the `Touches` gate,
  // which is what let the two disagree before this fix.
  Result<bool> ApplyTo(bus::PortValue& value, const std::string& bare_port, std::int64_t t_sim_ns) const;

  // IMP-0105: built at construction from the spec; `stage` is the
  // producing module (`bus::PortValue::header.producer`), `port` is
  // `bus::PortValue::port` -- the same two fields `ApplyTo` reads off a
  // real value.
  bool Touches(const std::string& stage, const std::string& port) const;

 private:
  std::vector<SpecMutation> mutations_;
  PortResolver resolve_port_;
  // `hold`'s cross-call memory, one entry per (stage, port, mutation
  // index touching it) -- `mutable` because `ApplyTo` is logically const
  // (it mutates the passed `PortValue`, not the `Mutator`'s own
  // configuration) but must remember `first_seen` across ticks.
  mutable std::map<std::string, double> first_seen_;
};

}  // namespace simcore::mutate
