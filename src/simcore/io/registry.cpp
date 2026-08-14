// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `CodecRegistry` (`IMP-0023`, `IMP-0024`). Ports `io/registry.py`'s
///   `register`/`reader_for`/`writer_for` behaviour: extension-keyed
///   lookup, an explicit-override seam, and refusal by capability rather
///   than by a branch on the codec's identity.
/// @author Pavan Karimajji

#include "simcore/io.hpp"

namespace simcore::io {

namespace {

Error MakeError(Kind kind, std::string expected, std::string found, std::string where, std::string hint = "") {
  return Error{kind, std::move(expected), std::move(found), std::move(where), std::move(hint)};
}

}  // namespace

CodecRegistry& CodecRegistry::Instance() {
  static CodecRegistry instance;
  return instance;
}

Result<bool> CodecRegistry::Register(
    const std::string& ext, Capabilities capabilities, ReaderFactory reader_factory,
    WriterFactory writer_factory) {
  // IMP-0023: a second registration of one extension is an Internal error
  // naming both -- not overwritten, not silently ignored.
  if (entries_.count(ext) != 0) {
    return Result<bool>::Fail(MakeError(
        Kind::Internal, "an extension registered at most once", "'" + ext + "' registered a second time",
        "simcore::io::CodecRegistry::Register"));
  }
  // IMP-0024: a codec whose round_trip is true must supply a WriterFactory;
  // one whose round_trip is false is registered write-only.
  if (capabilities.round_trips && writer_factory == nullptr) {
    return Result<bool>::Fail(MakeError(
        Kind::Internal, "a WriterFactory for a round_trips codec", "none supplied",
        "simcore::io::CodecRegistry::Register('" + ext + "')"));
  }
  capabilities.write_only = !capabilities.round_trips && writer_factory != nullptr;
  entries_[ext] = Entry{capabilities, std::move(reader_factory), std::move(writer_factory)};
  return Result<bool>::Ok(true);
}

Result<std::unique_ptr<Reader>> CodecRegistry::OpenRead(const std::filesystem::path& path) const {
  const std::string ext = path.extension().string();
  const auto it = entries_.find(ext);
  if (it == entries_.end()) {
    return Result<std::unique_ptr<Reader>>::Fail(MakeError(
        Kind::Authoring, "a registered extension: " + RegisteredExtensions(), "'" + ext + "'",
        path.string()));
  }
  // R-SIM-14: an export (write-only) is refused as a resim input BY
  // CAPABILITY, never by a naming convention -- the entry exists, it simply
  // has no reader factory.
  if (it->second.reader_factory == nullptr) {
    return Result<std::unique_ptr<Reader>>::Fail(MakeError(
        Kind::Authoring, "a codec with a reader (round_trips capability)",
        "'" + ext + "' is write-only -- refused as a resim input", path.string(),
        "an export is lossy and terminal; use the recording it was exported from"));
  }
  return Result<std::unique_ptr<Reader>>::Ok(it->second.reader_factory());
}

Result<std::unique_ptr<Writer>> CodecRegistry::OpenWrite(const std::filesystem::path& path) const {
  const std::string ext = path.extension().string();
  const auto it = entries_.find(ext);
  if (it == entries_.end()) {
    return Result<std::unique_ptr<Writer>>::Fail(MakeError(
        Kind::Authoring, "a registered extension: " + RegisteredExtensions(), "'" + ext + "'",
        path.string()));
  }
  if (it->second.writer_factory == nullptr) {
    return Result<std::unique_ptr<Writer>>::Fail(MakeError(
        Kind::Authoring, "a codec with a writer", "'" + ext + "' is read-only (no writer registered)",
        path.string()));
  }
  return Result<std::unique_ptr<Writer>>::Ok(it->second.writer_factory());
}

Result<Capabilities> CodecRegistry::CapabilitiesFor(const std::string& ext) const {
  const auto it = entries_.find(ext);
  if (it == entries_.end()) {
    return Result<Capabilities>::Fail(MakeError(
        Kind::Authoring, "a registered extension: " + RegisteredExtensions(), "'" + ext + "'",
        "simcore::io::CodecRegistry::CapabilitiesFor"));
  }
  return Result<Capabilities>::Ok(it->second.capabilities);
}

std::string CodecRegistry::RegisteredExtensions() const {
  std::string out;
  for (const auto& kv : entries_) {
    if (!out.empty()) out += ", ";
    out += kv.first;
  }
  return out;
}

}  // namespace simcore::io
