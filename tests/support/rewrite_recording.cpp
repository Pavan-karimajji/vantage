// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `rewrite_recording` (`IMP-0069`; serves `RCT:SYT-REC-03` `.c3`): reads a recording through the engine's own
///   reader and writes its topics, messages and metadata again through the engine's own writer, in the order an
///   engine run writes them -- `config_bundle` before the first message, `manifest` once, after the last. Two calls
///   with the same input therefore make two writer calls with the same arguments, which an engine run's
///   `process_nonce` stops two engine runs from being.
///   argv: `<in.mcap> <out.mcap>`. Exit 0, or 1 with the refusal on stderr; 2 on a bad argument.
/// @author Pavan Karimajji

#include <iostream>
#include <string>

#include "simcore/io.hpp"

int main(int argc, char** argv) {
  if (argc != 3) {
    std::cerr << "usage: " << argv[0] << " <in.mcap> <out.mcap>\n";
    return 2;
  }
  simcore::io::CodecRegistry& registry = simcore::io::CodecRegistry::Instance();
  const auto registered = simcore::io::codecs::RegisterMcap(registry);
  if (!registered.ok()) {
    std::cerr << registered.error().Format() << "\n";
    return 1;
  }
  auto reader = registry.OpenRead(argv[1]);
  if (!reader.ok() || !reader.value()->Open(argv[1]).ok()) {
    std::cerr << "cannot open '" << argv[1] << "'\n";
    return 1;
  }
  auto writer = registry.OpenWrite(argv[2]);
  if (!writer.ok()) {
    std::cerr << writer.error().Format() << "\n";
    return 1;
  }
  const auto opened = writer.value()->Open(argv[2], reader.value()->Describe());
  if (!opened.ok()) {
    std::cerr << opened.error().Format() << "\n";
    return 1;
  }
  const auto bundle = reader.value()->GetMetaBlock(simcore::io::ToString(simcore::io::MetaKind::kConfigBundle));
  if (bundle.has_value()) writer.value()->WriteMetaBlock(simcore::io::ToString(simcore::io::MetaKind::kConfigBundle), *bundle);

  simcore::io::WriterBase base(*writer.value());
  for (;;) {
    const simcore::io::Batch batch = reader.value()->ReadRange(simcore::io::ReadBounds{});
    for (const simcore::io::RawMessage& message : batch.messages) base.WriteMessage(message);
    if (batch.exhausted) break;
  }
  const auto manifest = reader.value()->GetMetaBlock(simcore::io::ToString(simcore::io::MetaKind::kRunManifest));
  if (manifest.has_value()) writer.value()->WriteMetaBlock(simcore::io::ToString(simcore::io::MetaKind::kRunManifest), *manifest);
  writer.value()->Close();
  reader.value()->Close();
  return 0;
}
