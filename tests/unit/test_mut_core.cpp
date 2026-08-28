// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `UT-MUT-01`..`UT-MUT-10` (`WP-11`, `SI-05`): the six closed override
///   verbs, the five closed fault verbs, resolved-address application and
///   time-window scoping -- against a small, self-contained synthetic
///   message type (built programmatically via `FileDescriptorProto`, no
///   `.proto` fixture file and no `AdasInterfaces` dependency needed --
///   `simcore` itself requires nothing first-party, and this test honours
///   that even though `tests/` is outside that grep).
///
///   The synthetic type is a `DynamicMessage` (no generated C++ class), so
///   this file reads/writes it the same way `mutate/address.cpp` itself
///   does -- through `google::protobuf::Reflection` -- rather than
///   generated accessors, via a handful of small helpers below.
///
///   `UT-MUT-11` (`WP-11a`, `SW-0424`): added 2026-08-22, closing the
///   `IMP-0428` defect (`ApplyTo`'s own internal `Touches` re-check
///   comparing a bare `SpecMutation::address.port` against
///   `bus::PortBus::Publish`'s always-fully-qualified `value.port`). Unlike
///   `UT-MUT-01`..`UT-MUT-10` above, this one routes a real
///   `runner::Runner` cycle over a real `bus::PortBus` and the real
///   `echo_stub` component (`F-STUB`) -- a hand-built `PortValue` with a
///   deliberately bare `.port` (this file's own `MakeValue` helper, used by
///   every other test here) is exactly the shape that let the defect hide.
/// @author Pavan Karimajji

#include <gtest/gtest.h>

#include <cstdlib>
#include <filesystem>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include <google/protobuf/descriptor.h>
#include <google/protobuf/descriptor.pb.h>
#include <google/protobuf/dynamic_message.h>

#include "simcore/mutate.hpp"
#include "simcore/runner.hpp"

namespace simcore::mutate {
namespace {

namespace pb = google::protobuf;

// ---- Reflection helpers (mirrors what mutate/address.cpp itself does) ----

const pb::FieldDescriptor* Field(const pb::Message& m, const std::string& name) {
  const pb::FieldDescriptor* f = m.GetDescriptor()->FindFieldByName(name);
  EXPECT_NE(f, nullptr) << "no field '" << name << "' on " << m.GetDescriptor()->full_name();
  return f;
}

double GetDouble(const pb::Message& m, const std::string& field) { return m.GetReflection()->GetDouble(m, Field(m, field)); }
void SetDouble(pb::Message& m, const std::string& field, double v) { m.GetReflection()->SetDouble(&m, Field(m, field), v); }
void AddDouble(pb::Message& m, const std::string& field, double v) { m.GetReflection()->AddDouble(&m, Field(m, field), v); }
double GetRepeatedDouble(const pb::Message& m, const std::string& field, int i) {
  return m.GetReflection()->GetRepeatedDouble(m, Field(m, field), i);
}
int RepeatedSize(const pb::Message& m, const std::string& field) { return m.GetReflection()->FieldSize(m, Field(m, field)); }
pb::Message* AddMessage(pb::Message& m, const std::string& field) { return m.GetReflection()->AddMessage(&m, Field(m, field)); }
const pb::Message& GetRepeatedMessage(const pb::Message& m, const std::string& field, int i) {
  return m.GetReflection()->GetRepeatedMessage(m, Field(m, field), i);
}
// A synthetic `mutate_test.TestPort`:
//   double x = 1; double y = 2;
//   TestElement single_child = 3;         // singular message (path navigation)
//   repeated TestElement items = 4;       // repeated message (select/drop)
//   repeated double numbers = 5;          // repeated scalar (select/drop)
//   Status status = 6;                    // enum
// `TestElement { double value = 1; }`.
class MutateFixture : public ::testing::Test {
 protected:
  void SetUp() override {
    pb::FileDescriptorProto fd;
    fd.set_name("mutate_test.proto");
    fd.set_package("mutate_test");
    fd.set_syntax("proto3");

    pb::EnumDescriptorProto* status_enum = fd.add_enum_type();
    status_enum->set_name("Status");
    pb::EnumValueDescriptorProto* ok_value = status_enum->add_value();
    ok_value->set_name("OK");
    ok_value->set_number(0);
    pb::EnumValueDescriptorProto* bad_value = status_enum->add_value();
    bad_value->set_name("BAD");
    bad_value->set_number(1);

    pb::DescriptorProto* element = fd.add_message_type();
    element->set_name("TestElement");
    AddField(element, "value", 1, pb::FieldDescriptorProto::TYPE_DOUBLE, false);

    pb::DescriptorProto* port = fd.add_message_type();
    port->set_name("TestPort");
    AddField(port, "x", 1, pb::FieldDescriptorProto::TYPE_DOUBLE, false);
    AddField(port, "y", 2, pb::FieldDescriptorProto::TYPE_DOUBLE, false);
    AddMessageField(port, "single_child", 3, ".mutate_test.TestElement", false);
    AddMessageField(port, "items", 4, ".mutate_test.TestElement", true);
    AddField(port, "numbers", 5, pb::FieldDescriptorProto::TYPE_DOUBLE, true);
    AddEnumField(port, "status", 6, ".mutate_test.Status");

    file_ = pool_.BuildFile(fd);
    ASSERT_NE(file_, nullptr);
    port_descriptor_ = file_->FindMessageTypeByName("TestPort");
    ASSERT_NE(port_descriptor_, nullptr);
    element_descriptor_ = file_->FindMessageTypeByName("TestElement");
    factory_ = std::make_unique<pb::DynamicMessageFactory>(&pool_);
  }

  static void AddField(pb::DescriptorProto* msg, const std::string& name, int number,
                        pb::FieldDescriptorProto::Type type, bool repeated) {
    pb::FieldDescriptorProto* f = msg->add_field();
    f->set_name(name);
    f->set_number(number);
    f->set_type(type);
    f->set_label(repeated ? pb::FieldDescriptorProto::LABEL_REPEATED : pb::FieldDescriptorProto::LABEL_OPTIONAL);
  }

  static void AddMessageField(pb::DescriptorProto* msg, const std::string& name, int number,
                               const std::string& type_name, bool repeated) {
    pb::FieldDescriptorProto* f = msg->add_field();
    f->set_name(name);
    f->set_number(number);
    f->set_type(pb::FieldDescriptorProto::TYPE_MESSAGE);
    f->set_type_name(type_name);
    f->set_label(repeated ? pb::FieldDescriptorProto::LABEL_REPEATED : pb::FieldDescriptorProto::LABEL_OPTIONAL);
  }

  static void AddEnumField(pb::DescriptorProto* msg, const std::string& name, int number,
                            const std::string& type_name) {
    pb::FieldDescriptorProto* f = msg->add_field();
    f->set_name(name);
    f->set_number(number);
    f->set_type(pb::FieldDescriptorProto::TYPE_ENUM);
    f->set_type_name(type_name);
    f->set_label(pb::FieldDescriptorProto::LABEL_OPTIONAL);
  }

  std::unique_ptr<pb::Message> NewPort() const {
    return std::unique_ptr<pb::Message>(factory_->GetPrototype(port_descriptor_)->New());
  }

  std::vector<std::uint8_t> Encode(const pb::Message& message) const {
    std::vector<std::uint8_t> bytes(message.ByteSizeLong());
    message.SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
    return bytes;
  }

  std::unique_ptr<pb::Message> Decode(const std::vector<std::uint8_t>& payload) const {
    auto message = NewPort();
    EXPECT_TRUE(message->ParseFromArray(payload.data(), static_cast<int>(payload.size())));
    return message;
  }

  bus::PortValue MakeValue(const std::string& stage, const std::string& port, const pb::Message& message) const {
    bus::PortValue value;
    value.port = port;
    value.header.producer = stage;
    value.payload = Encode(message);
    return value;
  }

  Mutator::PortResolver Resolver(std::optional<bool> fixed_slots = std::nullopt) const {
    const pb::Descriptor* descriptor = port_descriptor_;
    return [descriptor, fixed_slots](const std::string&, const std::string&) -> std::optional<PortInfo> {
      return PortInfo{descriptor, fixed_slots};
    };
  }

  pb::DescriptorPool pool_;
  const pb::FileDescriptor* file_ = nullptr;
  const pb::Descriptor* port_descriptor_ = nullptr;
  const pb::Descriptor* element_descriptor_ = nullptr;
  std::unique_ptr<pb::DynamicMessageFactory> factory_;
};

MutationAddress AddressAt(const std::string& stage, const std::string& port, std::vector<std::string> path,
                           std::optional<int> index = std::nullopt, bool all_elements = false) {
  MutationAddress address;
  address.stage = stage;
  address.port = port;
  address.path = std::move(path);
  address.index = index;
  address.all_elements = all_elements;
  return address;
}

SpecMutation MakeMutation(const std::string& verb, MutationAddress address, std::vector<double> operands = {}) {
  SpecMutation mutation;
  mutation.verb = verb;
  mutation.address = std::move(address);
  mutation.operands = std::move(operands);
  return mutation;
}

// ---- UT-MUT-01: each of the six verbs; then name a seventh ----------

TEST(UtMut01ClosedVerbs, EachOfTheSixParsesAndRoundTripsItsOwnName) {
  for (const std::string& name : {"const", "hold", "offset", "scale", "select", "drop"}) {
    Result<Verb> verb = ParseVerb(name, "test");
    ASSERT_TRUE(verb.ok());
    EXPECT_EQ(ToString(verb.value()), name);
  }
}

TEST(UtMut01ClosedVerbs, ASeventhVerbNameIsAuthoringErrorNamingTheClosedSet) {
  Result<Verb> verb = ParseVerb("interpolate", "test");
  ASSERT_FALSE(verb.ok());
  EXPECT_EQ(verb.error().kind, Kind::Authoring);
  EXPECT_NE(verb.error().expected.find("const"), std::string::npos);
}

// ---- UT-MUT-02: every verb applied to a repeated field never allocates ----

TEST_F(MutateFixture, UtMut02ArithmeticOnARepeatedElementNeverChangesElementCount) {
  auto port = NewPort();
  AddDouble(*port, "numbers", 1.0);
  AddDouble(*port, "numbers", 2.0);
  AddDouble(*port, "numbers", 3.0);
  std::optional<double> first_seen;
  const MutationAddress address = AddressAt("s", "p", {"numbers"}, 1);
  Result<bool> applied = ApplyAtAddress(*port, address, Verb::Offset, {10.0}, std::nullopt, first_seen);
  ASSERT_TRUE(applied.ok());
  EXPECT_EQ(RepeatedSize(*port, "numbers"), 3);
  EXPECT_DOUBLE_EQ(GetRepeatedDouble(*port, "numbers", 1), 12.0);
}

TEST_F(MutateFixture, UtMut02SelectDropOnFixedSlotsNeverChangesElementCount) {
  auto port = NewPort();
  AddDouble(*port, "numbers", 1.0);
  AddDouble(*port, "numbers", 2.0);
  AddDouble(*port, "numbers", 3.0);
  std::optional<double> first_seen;
  const MutationAddress address = AddressAt("s", "p", {"numbers"}, 1);
  Result<bool> applied = ApplyAtAddress(*port, address, Verb::Drop, {}, /*fixed_slots=*/true, first_seen);
  ASSERT_TRUE(applied.ok());
  EXPECT_EQ(RepeatedSize(*port, "numbers"), 3);  // cleared in place, never compacted
  EXPECT_DOUBLE_EQ(GetRepeatedDouble(*port, "numbers", 1), 0.0);
}

// ---- UT-MUT-03: port, field path, [i], [*] ---------------------------

TEST_F(MutateFixture, UtMut03WholePortAddressIsRefusedForArithmetic) {
  auto port = NewPort();
  std::optional<double> first_seen;
  const MutationAddress address = AddressAt("s", "p", {});
  Result<bool> applied = ApplyAtAddress(*port, address, Verb::Const, {5.0}, std::nullopt, first_seen);
  ASSERT_FALSE(applied.ok());
  EXPECT_EQ(applied.error().kind, Kind::Authoring);
}

TEST_F(MutateFixture, UtMut03FieldPathAddressesALeaf) {
  auto port = NewPort();
  SetDouble(*port, "x", 1.0);
  std::optional<double> first_seen;
  Result<bool> applied = ApplyAtAddress(*port, AddressAt("s", "p", {"x"}), Verb::Const, {9.0}, std::nullopt, first_seen);
  ASSERT_TRUE(applied.ok());
  EXPECT_DOUBLE_EQ(GetDouble(*port, "x"), 9.0);
}

TEST_F(MutateFixture, UtMut03IndexedElementAddressesOneRepeatedEntry) {
  auto port = NewPort();
  AddDouble(*port, "numbers", 1.0);
  AddDouble(*port, "numbers", 2.0);
  std::optional<double> first_seen;
  Result<bool> applied =
      ApplyAtAddress(*port, AddressAt("s", "p", {"numbers"}, 0), Verb::Const, {7.0}, std::nullopt, first_seen);
  ASSERT_TRUE(applied.ok());
  EXPECT_DOUBLE_EQ(GetRepeatedDouble(*port, "numbers", 0), 7.0);
  EXPECT_DOUBLE_EQ(GetRepeatedDouble(*port, "numbers", 1), 2.0);
}

TEST_F(MutateFixture, UtMut03WildcardSelectsEveryElement) {
  auto port = NewPort();
  AddDouble(*port, "numbers", 1.0);
  AddDouble(*port, "numbers", 2.0);
  AddDouble(*port, "numbers", 3.0);
  std::optional<double> first_seen;
  Result<bool> applied = ApplyAtAddress(*port, AddressAt("s", "p", {"numbers"}, std::nullopt, /*all_elements=*/true),
                                         Verb::Drop, {}, /*fixed_slots=*/false, first_seen);
  ASSERT_TRUE(applied.ok());
  EXPECT_EQ(RepeatedSize(*port, "numbers"), 0);
}

TEST_F(MutateFixture, UtMut03WildcardIsRefusedForArithmetic) {
  auto port = NewPort();
  AddDouble(*port, "numbers", 1.0);
  std::optional<double> first_seen;
  Result<bool> applied = ApplyAtAddress(*port, AddressAt("s", "p", {"numbers"}, std::nullopt, true), Verb::Scale, {2.0},
                                         std::nullopt, first_seen);
  ASSERT_FALSE(applied.ok());
  EXPECT_EQ(applied.error().kind, Kind::Authoring);
}

// A predicate-shaped address is closed BY CONSTRUCTION here: `MutationAddress`
// has no field that could carry one (`std::optional<int> index` or
// `all_elements`, nothing else) -- the grammar is refused in Python's
// `parse_address` (`R-SIM-15`) before a mutation ever reaches this struct;
// there is no string for this module to reject a second time.

// ---- UT-MUT-04: drop an element of a fixed_slots port; read every index ----

TEST_F(MutateFixture, UtMut04DropOnFixedSlotsPortClearsInPlaceAndReadsEveryIndexAfterwards) {
  auto port = NewPort();
  for (int i = 0; i < 4; ++i) SetDouble(*AddMessage(*port, "items"), "value", i + 1.0);
  std::optional<double> first_seen;
  Result<bool> applied =
      ApplyAtAddress(*port, AddressAt("s", "p", {"items"}, 1), Verb::Drop, {}, /*fixed_slots=*/true, first_seen);
  ASSERT_TRUE(applied.ok());
  ASSERT_EQ(RepeatedSize(*port, "items"), 4);
  EXPECT_DOUBLE_EQ(GetDouble(GetRepeatedMessage(*port, "items", 0), "value"), 1.0);
  EXPECT_DOUBLE_EQ(GetDouble(GetRepeatedMessage(*port, "items", 1), "value"), 0.0);  // cleared, not shifted
  EXPECT_DOUBLE_EQ(GetDouble(GetRepeatedMessage(*port, "items", 2), "value"), 3.0);
  EXPECT_DOUBLE_EQ(GetDouble(GetRepeatedMessage(*port, "items", 3), "value"), 4.0);
}

TEST_F(MutateFixture, UtMut04SelectDropWithNoFixedSlotsDeclaredIsRefusedNeverGuessed) {
  auto port = NewPort();
  AddDouble(*port, "numbers", 1.0);
  std::optional<double> first_seen;
  Result<bool> applied =
      ApplyAtAddress(*port, AddressAt("s", "p", {"numbers"}, 0), Verb::Drop, {}, std::nullopt, first_seen);
  ASSERT_FALSE(applied.ok());
  EXPECT_EQ(applied.error().kind, Kind::Contract);
}

// ---- UT-MUT-05: each of the five faults; read the header field acted on ----

TEST_F(MutateFixture, UtMut05DropClearsPayloadAndMarksNotUpdated) {
  auto port = NewPort();
  SetDouble(*port, "x", 1.0);
  bus::PortValue value = MakeValue("s", "p", *port);
  FaultSpec fault{Fault::Drop, AddressAt("s", "p", {})};
  std::optional<std::int64_t> active_since;
  Result<bus::PortValue> result = ApplyFault(value, fault, /*t_sim_ns=*/0, active_since, nullptr, nullptr);
  ASSERT_TRUE(result.ok());
  EXPECT_TRUE(result.value().payload.empty());
  EXPECT_FALSE(result.value().updated);
  ASSERT_TRUE(result.value().header.status.has_value());
  EXPECT_NE(result.value().header.status.value(), 0u);
}

TEST_F(MutateFixture, UtMut05StaleGrowsHoldAgeAcrossTicksFromFirstActiveTick) {
  auto port = NewPort();
  bus::PortValue value = MakeValue("s", "p", *port);
  FaultSpec fault{Fault::Stale, AddressAt("s", "p", {})};
  std::optional<std::int64_t> active_since;
  Result<bus::PortValue> first = ApplyFault(value, fault, 1'000, active_since, nullptr, nullptr);
  ASSERT_TRUE(first.ok());
  ASSERT_TRUE(first.value().hold_ns.has_value());
  EXPECT_EQ(first.value().hold_ns.value(), 0);
  Result<bus::PortValue> second = ApplyFault(value, fault, 1'500, active_since, nullptr, nullptr);
  ASSERT_TRUE(second.ok());
  EXPECT_EQ(second.value().hold_ns.value(), 500);
}

TEST_F(MutateFixture, UtMut05InvalidateKeepsPayloadFlipsStatus) {
  auto port = NewPort();
  SetDouble(*port, "x", 3.0);
  bus::PortValue value = MakeValue("s", "p", *port);
  value.header.status = std::uint32_t{0};
  FaultSpec fault{Fault::Invalidate, AddressAt("s", "p", {})};
  std::optional<std::int64_t> active_since;
  Result<bus::PortValue> result = ApplyFault(value, fault, 0, active_since, nullptr, nullptr);
  ASSERT_TRUE(result.ok());
  EXPECT_FALSE(result.value().payload.empty());
  EXPECT_NE(result.value().header.status.value(), 0u);
}

TEST_F(MutateFixture, UtMut05DelayShiftsAKnownCaptureStampAndRefusesAnUnknownOne) {
  auto port = NewPort();
  bus::PortValue value = MakeValue("s", "p", *port);
  value.header.t_capture_ns = std::int64_t{5'000'000'000};
  FaultSpec fault{Fault::Delay, AddressAt("s", "p", {}), /*value=*/0.5};
  std::optional<std::int64_t> active_since;
  Result<bus::PortValue> shifted = ApplyFault(value, fault, 0, active_since, nullptr, nullptr);
  ASSERT_TRUE(shifted.ok());
  EXPECT_EQ(shifted.value().header.t_capture_ns.value(), 4'500'000'000);

  bus::PortValue unknown_capture = MakeValue("s", "p", *port);  // t_capture_ns left unknown
  Result<bus::PortValue> refused = ApplyFault(unknown_capture, fault, 0, active_since, nullptr, nullptr);
  ASSERT_FALSE(refused.ok());
  EXPECT_EQ(refused.error().kind, Kind::Contract);
}

TEST_F(MutateFixture, UtMut05CorruptReusesConstOverrideByteMutation) {
  auto port = NewPort();
  SetDouble(*port, "x", 1.0);
  bus::PortValue value = MakeValue("s", "p", *port);
  FaultSpec fault{Fault::Corrupt, AddressAt("s", "p", {"x"}), /*value=*/42.0};
  std::optional<std::int64_t> active_since;
  Result<bus::PortValue> result = ApplyFault(value, fault, 0, active_since, port_descriptor_, factory_.get());
  ASSERT_TRUE(result.ok());
  auto decoded = Decode(result.value().payload);
  EXPECT_DOUBLE_EQ(GetDouble(*decoded, "x"), 42.0);
}

// ---- UT-MUT-06: three verbs to one value; decode once, encode once --------

TEST_F(MutateFixture, UtMut06ThreeMutationsOnOneValueAllApplyInASingleDecodeEncodePass) {
  auto port = NewPort();
  SetDouble(*port, "x", 1.0);
  SetDouble(*port, "y", 2.0);
  AddDouble(*port, "numbers", 3.0);
  bus::PortValue value = MakeValue("df", "outputs", *port);

  std::vector<SpecMutation> mutations{
      MakeMutation("const", AddressAt("df", "outputs", {"x"}), {100.0}),
      MakeMutation("offset", AddressAt("df", "outputs", {"y"}), {1.0}),
      MakeMutation("scale", AddressAt("df", "outputs", {"numbers"}, 0), {10.0}),
  };
  // `ApplyTo`'s own body decodes once before this loop and encodes once
  // after it (address.cpp) -- there is no per-verb decode/encode call to
  // instrument from outside; this test proves the observable consequence:
  // all three mutations really did land on the one message this call
  // decoded, not three independent partial re-encodes.
  Mutator mutator(mutations, Resolver());
  Result<bool> applied = mutator.ApplyTo(value, value.port, /*t_sim_ns=*/0);
  ASSERT_TRUE(applied.ok());

  auto decoded = Decode(value.payload);
  EXPECT_DOUBLE_EQ(GetDouble(*decoded, "x"), 100.0);
  EXPECT_DOUBLE_EQ(GetDouble(*decoded, "y"), 3.0);
  EXPECT_DOUBLE_EQ(GetRepeatedDouble(*decoded, "numbers", 0), 30.0);
}

// ---- UT-MUT-07: origin travels on the value itself -------------------

TEST_F(MutateFixture, UtMut07OverriddenPortCarriesOverriddenOriginOnTheValue) {
  auto port = NewPort();
  bus::PortValue value = MakeValue("df", "outputs", *port);
  value.origin = bus::Origin::Measured;
  std::vector<SpecMutation> mutations{MakeMutation("const", AddressAt("df", "outputs", {"x"}), {1.0})};
  Mutator mutator(mutations, Resolver());
  ASSERT_TRUE(mutator.ApplyTo(value, value.port, 0).ok());
  EXPECT_EQ(value.origin, bus::Origin::Overridden);
}

// ---- UT-MUT-08: delay -- see UtMut05DelayShiftsAKnownCaptureStamp... above --

// ---- UT-MUT-09: Touches; a port outside it never reaches ApplyTo ----------

TEST_F(MutateFixture, UtMut09TouchesReflectsExactlyTheMutationsSpecAddresses) {
  std::vector<SpecMutation> mutations{MakeMutation("const", AddressAt("df", "outputs", {"x"}), {1.0})};
  Mutator mutator(mutations, Resolver());
  EXPECT_TRUE(mutator.Touches("df", "outputs"));
  EXPECT_FALSE(mutator.Touches("df", "other_port"));
  EXPECT_FALSE(mutator.Touches("other_stage", "outputs"));
}

TEST_F(MutateFixture, UtMut09APortOutsideTouchesIsReturnedUndecodedUnchanged) {
  auto port = NewPort();
  SetDouble(*port, "x", 1.0);
  bus::PortValue value = MakeValue("df", "unrelated_port", *port);
  const std::vector<std::uint8_t> original_payload = value.payload;
  std::vector<SpecMutation> mutations{MakeMutation("const", AddressAt("df", "outputs", {"x"}), {999.0})};
  // A resolver that would fail the test if it were ever called -- proves
  // ApplyTo's Touches() gate runs before any decode attempt.
  Mutator::PortResolver failing_resolver = [](const std::string&, const std::string&) -> std::optional<PortInfo> {
    ADD_FAILURE() << "resolve_port called for a port outside Touches()";
    return std::nullopt;
  };
  Mutator mutator(mutations, failing_resolver);
  Result<bool> applied = mutator.ApplyTo(value, value.port, 0);
  ASSERT_TRUE(applied.ok());
  EXPECT_EQ(value.payload, original_payload);
}

// ---- UT-MUT-10: window scoping ----------------------------------------

TEST(UtMut10Window, InsideOutsideAndOpenBoundaries) {
  EXPECT_TRUE(InWindow(std::nullopt, std::nullopt, 12345));
  EXPECT_TRUE(InWindow(1000, 2000, 1500));
  EXPECT_FALSE(InWindow(1000, 2000, 500));
  EXPECT_FALSE(InWindow(1000, 2000, 2000));  // half-open: [start, end)
  EXPECT_TRUE(InWindow(1000, std::nullopt, 5'000'000));
  EXPECT_FALSE(InWindow(std::nullopt, 2000, 2000));
}

TEST_F(MutateFixture, UtMut10FaultOutsideItsWindowLeavesTheValueUnchanged) {
  auto port = NewPort();
  SetDouble(*port, "x", 1.0);
  bus::PortValue value = MakeValue("s", "p", *port);
  const std::vector<std::uint8_t> original_payload = value.payload;
  FaultSpec fault{Fault::Drop, AddressAt("s", "p", {}), std::nullopt, /*window_ns_start=*/1'000'000'000};
  std::optional<std::int64_t> active_since;
  Result<bus::PortValue> before_window = ApplyFault(value, fault, /*t_sim_ns=*/0, active_since, nullptr, nullptr);
  ASSERT_TRUE(before_window.ok());
  EXPECT_EQ(before_window.value().payload, original_payload);
  EXPECT_FALSE(active_since.has_value());

  Result<bus::PortValue> inside_window = ApplyFault(value, fault, /*t_sim_ns=*/2'000'000'000, active_since, nullptr, nullptr);
  ASSERT_TRUE(inside_window.ok());
  EXPECT_TRUE(inside_window.value().payload.empty());
  ASSERT_TRUE(active_since.has_value());
}

// ---- UT-MUT-11: a declared override applies through a real Runner cycle --
// with a real PortBus (WP-11a, SW-0424, IMP-0428). See this file's own top
// note: unlike every test above, this one never hand-builds a PortValue --
// the override must survive bus::PortBus::Publish's own fully-qualified
// `value.port` convention, which is exactly what hid IMP-0428 before now.

class EnvGuard {
 public:
  EnvGuard(const char* name, const std::string& value) : name_(name) {
#if defined(_WIN32)
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
  }
  ~EnvGuard() {
#if defined(_WIN32)
    _putenv_s(name_, "");
#else
    unsetenv(name_);
#endif
  }

 private:
  const char* name_;
};

std::filesystem::path EchoStubPath() {
#if defined(_WIN32)
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "echo_stub.dll";
#else
  return std::filesystem::path(ADAS_SIM_TEST_FIXTURE_DIR) / "libecho_stub.so";
#endif
}

// A minimal in-test `io::Reader`, one recorded message on `/meas/objects` --
// mirrors `test_ut_run_core.cpp::VectorReader`, kept local rather than
// shared since neither file treats its own fixture scaffolding as reusable
// infrastructure (that file's own top note).
class Ut11Reader final : public io::Reader {
 public:
  Ut11Reader(std::vector<io::RawMessage> messages, std::map<std::string, io::TopicInfo> topics)
      : messages_(std::move(messages)), topics_(std::move(topics)) {}

  Result<bool> Open(const std::filesystem::path&) override { return Result<bool>::Ok(true); }
  std::map<std::string, io::TopicInfo> Describe() const override { return topics_; }
  void Seek(std::int64_t) override {}

  io::Batch ReadRange(const io::ReadBounds& bounds) override {
    return io::detail::AccumulateBatch(bounds, lookahead_, [this]() -> std::optional<io::RawMessage> {
      if (index_ >= messages_.size()) return std::nullopt;
      return messages_[index_++];
    });
  }

  void Close() override {}
  std::optional<std::vector<std::uint8_t>> GetMeta(const std::string&) const override { return std::nullopt; }

 private:
  std::vector<io::RawMessage> messages_;
  std::map<std::string, io::TopicInfo> topics_;
  std::optional<io::RawMessage> lookahead_;
  std::size_t index_ = 0;
};

class CapturingWriter final : public io::Writer {
 public:
  Result<bool> Open(const std::filesystem::path&, const std::map<std::string, io::TopicInfo>&) override {
    return Result<bool>::Ok(true);
  }
  void Write(const io::RawMessage& message) override { written.push_back(message); }
  void WriteMeta(const std::string&, const std::vector<std::uint8_t>&) override {}
  void Close() override {}

  std::vector<io::RawMessage> written;
};

TEST_F(MutateFixture, UtMut11ADeclaredOverrideAppliesThroughARealRunnerCycleWithARealPortBus) {
  EnvGuard name_guard("ADAS_SIL_TEST_STUB_NAME", "run_stub_ut_mut_11");
  EnvGuard port_guard("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "");  // sut produces no output -- irrelevant to this case

  auto loaded = module_host::Component::Load(EchoStubPath());
  ASSERT_TRUE(loaded.ok()) << loaded.error().Format();
  module_host::Component component = std::move(loaded).value();
  ASSERT_TRUE(component.Init().ok());

  // The recording's own bytes -- x=7.0 -- which the declared override below
  // must NOT be the value observed on read-back.
  auto recorded_port = NewPort();
  SetDouble(*recorded_port, "x", 7.0);

  SpecPort objects_port;
  objects_port.name = "objects";
  objects_port.kind = "data";
  objects_port.proto_type = "mutate_test.TestPort";
  objects_port.record = "full";
  objects_port.sampling = "latest";
  objects_port.on_missing = "hold";

  SpecPort meas_port = objects_port;
  meas_port.dir = "pro";
  SpecStage meas;
  meas.name = "meas";
  meas.mode = "measured";
  meas.ports = {meas_port};

  SpecPort sut_port = objects_port;
  sut_port.dir = "req";
  SpecInput from_meas;
  from_meas.port = "objects";
  from_meas.producer = "meas";
  from_meas.producer_port = "objects";
  SpecStage sut;
  sut.name = "sut";
  sut.mode = "simulate";
  sut.ports = {sut_port};
  sut.inputs = {from_meas};

  RunSpec spec;
  spec.run_id = "ut-mut-11";
  spec.grid_step_ns = 10'000'000;
  spec.stages = {meas, sut};
  spec.order = {"meas", "sut"};

  // The declared override: `meas.objects.x := 42.0` -- the same address
  // shape a real Resolved Run Spec's `mutations[]` carries.
  std::vector<SpecMutation> mutations{MakeMutation("const", AddressAt("meas", "objects", {"x"}), {42.0})};
  // ...and carried ON the spec, which is where a real run declares them
  // (`simcore.cpp` builds its `Mutator` from `spec.mutations`). The recorder
  // reads the same field to decide that this port needs a post-mutation
  // topic of its own (`R-SIM-15`), so leaving the spec empty here made the
  // engine and the Mutator disagree about whether an override exists.
  spec.mutations = mutations;
  Mutator mutator(mutations, Resolver());

  const std::string topic = runner::PortNameToTopic("meas.objects");
  io::TopicInfo topic_info;
  topic_info.schema_name = "mutate_test.TestPort";
  topic_info.provenance = io::Provenance::kMeasured;

  io::RawMessage recorded_message;
  recorded_message.topic = topic;
  recorded_message.log_time_ns = 0;
  recorded_message.payload = Encode(*recorded_port);

  Ut11Reader reader({recorded_message}, {{topic, topic_info}});
  scheduler::Scheduler sched(spec);
  bus::PortBus bus;
  CapturingWriter sink;
  io::WriterBase writer_base(sink);

  auto constructed = runner::Runner::Construct(spec, sched, bus, reader, {{"sut", &component}}, &writer_base, &mutator);
  ASSERT_TRUE(constructed.ok()) << constructed.error().Format();
  runner::Runner run = std::move(constructed).value();
  Result<bool> step = run.StepOnce();
  ASSERT_TRUE(step.ok()) << step.error().Format();

  // The exact bytes delivered to `sut`'s own `objects` req port this cycle,
  // post-mutation -- read back from what the writer actually received, the
  // same technique `UtAbi02Resolver.ADeclaredOverrideIsApplied` uses through
  // the C ABI.
  const std::string delivered_topic = runner::PortNameToTopic("sut.objects");
  const io::RawMessage* delivered = nullptr;
  for (const auto& message : sink.written) {
    if (message.topic == delivered_topic) delivered = &message;
  }
  ASSERT_NE(delivered, nullptr) << "no delivered req message written for sut.objects";
  auto decoded = Decode(delivered->payload);
  EXPECT_DOUBLE_EQ(GetDouble(*decoded, "x"), 42.0);
}

}  // namespace
}  // namespace simcore::mutate
