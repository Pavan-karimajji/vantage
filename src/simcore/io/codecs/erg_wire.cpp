// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `erg_wire.hpp`'s implementation.
/// @author Pavan Karimajji

#include "erg_wire.hpp"

namespace simcore::io::codecs::erg_detail {

namespace {

// Reads one base-128 varint starting at `data[*pos]`, advancing `*pos`
// past it. Returns false on a truncated varint (no continuation-bit-clear
// byte found within 10 bytes -- the max width of a 64-bit varint).
bool ReadVarint(std::string_view data, std::size_t* pos, std::uint64_t* out) {
  std::uint64_t result = 0;
  for (int shift = 0; shift < 70; shift += 7) {
    if (*pos >= data.size()) return false;
    const std::uint8_t byte = static_cast<std::uint8_t>(data[*pos]);
    ++*pos;
    result |= static_cast<std::uint64_t>(byte & 0x7F) << shift;
    if ((byte & 0x80) == 0) {
      *out = result;
      return true;
    }
  }
  return false;  // more than 10 bytes -- not a valid 64-bit varint
}

}  // namespace

bool WalkFields(std::string_view data, const std::function<void(const WireField&)>& visit) {
  std::size_t pos = 0;
  while (pos < data.size()) {
    std::uint64_t tag = 0;
    if (!ReadVarint(data, &pos, &tag)) return false;

    WireField field;
    field.field_number = static_cast<int>(tag >> 3);
    field.wire_type = static_cast<int>(tag & 0x7);

    switch (field.wire_type) {
      case 0: {  // VARINT
        std::uint64_t value = 0;
        if (!ReadVarint(data, &pos, &value)) return false;
        field.varint_value = value;
        break;
      }
      case 1: {  // I64 (fixed64/double/sfixed64)
        if (pos + 8 > data.size()) return false;
        pos += 8;
        break;
      }
      case 2: {  // LEN (string/bytes/embedded message/packed repeated)
        std::uint64_t length = 0;
        if (!ReadVarint(data, &pos, &length)) return false;
        if (pos + length > data.size()) return false;
        field.bytes_value = data.substr(pos, length);
        pos += length;
        break;
      }
      case 5: {  // I32 (fixed32/float/sfixed32)
        if (pos + 4 > data.size()) return false;
        pos += 4;
        break;
      }
      default:
        // 3/4 (deprecated START_GROUP/END_GROUP) or an unrecognized wire
        // type -- proto3 never emits either; a stream containing one is
        // malformed, not merely unsupported.
        return false;
    }
    visit(field);
  }
  return true;
}

}  // namespace simcore::io::codecs::erg_detail
