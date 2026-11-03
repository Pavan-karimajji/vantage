// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `recording_dump` (`VNT-WP-09a-R1`; serves `RCT:SYT-REC-04` `.c3`): opens one recording with Vantage's
///   own C++ reader (`include/simcore/io.hpp`, the `.mcap` codec) and prints what the reader returns, one JSON
///   line each, all text as lowercase hex so any byte survives:
///     `{"kind":"topic","topic":"/A/out","schema_name":"adas.lab.LabSample","origin":"simulated","schema_hex":"..."}`
///     `{"kind":"block","block":"manifest","key":"yaml","hex":"..."}`     (`manifest`, `config_bundle`)
///     `{"kind":"message","topic":"/A/out","log_time_ns":20000000,"hex":"..."}`   (file order)
///   Topics come back in the reader's canonical spelling (`/A/out`), as everywhere above `io`.
///   argv: `<recording.mcap>`. Exit 0, or 1 with the reader's refusal on stderr.
/// @author Pavan Karimajji

#include <cstdint>
#include <iostream>
#include <string>

#include "simcore/io.hpp"

namespace {

std::string Hex(const std::string& text) {
  static const char kDigits[] = "0123456789abcdef";
  std::string out;
  out.reserve(text.size() * 2);
  for (const unsigned char c : text) {
    out.push_back(kDigits[c >> 4]);
    out.push_back(kDigits[c & 0x0f]);
  }
  return out;
}

std::string Hex(const std::vector<std::uint8_t>& bytes) { return Hex(std::string(bytes.begin(), bytes.end())); }

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "usage: " << argv[0] << " <recording.mcap>\n";
    return 2;
  }
  simcore::io::CodecRegistry& registry = simcore::io::CodecRegistry::Instance();
  const auto registered = simcore::io::codecs::RegisterMcap(registry);
  if (!registered.ok()) {
    std::cerr << registered.error().Format() << "\n";
    return 1;
  }
  auto reader = registry.OpenRead(argv[1]);
  if (!reader.ok()) {
    std::cerr << reader.error().Format() << "\n";
    return 1;
  }
  const auto opened = reader.value()->Open(argv[1]);
  if (!opened.ok()) {
    std::cerr << opened.error().Format() << "\n";
    return 1;
  }

  for (const auto& [topic, info] : reader.value()->Describe()) {
    std::cout << "{\"kind\":\"topic\",\"topic\":\"" << topic << "\",\"schema_name\":\"" << info.schema_name
              << "\",\"origin\":\"" << simcore::io::ToString(info.provenance) << "\",\"schema_hex\":\""
              << Hex(info.schema_bytes) << "\"}\n";
  }
  for (const char* block : {"manifest", "config_bundle"}) {
    const auto entries = reader.value()->GetMetaBlock(block);
    if (!entries.has_value()) continue;
    for (const auto& [key, text] : *entries) {
      std::cout << "{\"kind\":\"block\",\"block\":\"" << block << "\",\"key_hex\":\"" << Hex(key) << "\",\"hex\":\""
                << Hex(text) << "\"}\n";
    }
  }
  for (;;) {
    const simcore::io::Batch batch = reader.value()->ReadRange(simcore::io::ReadBounds{});
    for (const simcore::io::RawMessage& message : batch.messages) {
      std::cout << "{\"kind\":\"message\",\"topic\":\"" << message.topic << "\",\"log_time_ns\":" << message.log_time_ns
                << ",\"hex\":\"" << Hex(message.payload) << "\"}\n";
    }
    if (batch.exhausted) break;
  }
  reader.value()->Close();
  return 0;
}
