// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `WriteReproducer` (`IMP-0139`, `WP-15`) -- on a module crash,
///   writes a self-contained package: the run spec (copied verbatim), the
///   input capture at the failing cycle (one file per port), the module
///   identity line and captured stderr. Hooks into `WP-14`'s own crash
///   detection (`module_host::RunIsolatedStage`'s `IsolatedOutcome::
///   kCrashed`, wired at the `simengine/main.cpp` restart-supervisor call
///   site) rather than building a second one -- this file only ever WRITES
///   the package; it never decides what counts as a crash.
///
///   `SW-0140`: every filesystem call below goes through the
///   `std::error_code` overload. No overload here can throw, so this
///   function's own `noexcept` is not a promise resting on "nothing
///   happens to throw today" -- it is structurally true from the calls
///   made.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <fstream>

namespace simcore::diagnostics {

namespace {

Result<bool> WriteBytes(const std::filesystem::path& path, const void* data, std::size_t size,
                         const std::string& what) {
  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  if (!out) {
    return Result<bool>::Fail(Error{Kind::Environment, "a writable reproducer file", "open failed", path.string(),
                                    "check " + what + "'s output directory is writable"});
  }
  if (size > 0) out.write(static_cast<const char*>(data), static_cast<std::streamsize>(size));
  if (!out) {
    return Result<bool>::Fail(Error{Kind::Environment, "a fully-written reproducer file", "write failed",
                                    path.string(), "check disk space for " + what});
  }
  return Result<bool>::Ok(true);
}

Result<bool> WriteText(const std::filesystem::path& path, const std::string& text, const std::string& what) {
  return WriteBytes(path, text.data(), text.size(), what);
}

Result<bool> CopyRunSpec(const std::filesystem::path& source, const std::filesystem::path& dest) {
  std::error_code ec;
  std::filesystem::copy_file(source, dest, std::filesystem::copy_options::overwrite_existing, ec);
  if (ec) {
    return Result<bool>::Fail(Error{Kind::Environment, "a readable run spec to copy into the reproducer",
                                    ec.message(), source.string(), "check the run spec still exists and is readable"});
  }
  return Result<bool>::Ok(true);
}

}  // namespace

Result<ReproducerResult> WriteReproducer(const std::filesystem::path& output_dir,
                                          const ReproducerInput& input) noexcept {
  std::error_code ec;
  const std::filesystem::path package_dir =
      output_dir / ("cycle_" + std::to_string(input.failing_cycle));

  std::filesystem::create_directories(package_dir, ec);
  if (ec) {
    return Result<ReproducerResult>::Fail(Error{Kind::Environment, "a creatable reproducer output directory",
                                                ec.message(), package_dir.string(),
                                                "check the output directory is writable and has free space"});
  }

  ReproducerResult result;
  result.package_dir = package_dir;

  if (!input.run_spec_path.empty()) {
    const std::filesystem::path dest = package_dir / "run_spec.json";
    const Result<bool> copied = CopyRunSpec(input.run_spec_path, dest);
    if (!copied.ok()) return Result<ReproducerResult>::Fail(copied.error());
    result.files_written.push_back(dest.string());
  }

  const std::filesystem::path capture_dir = package_dir / "input_capture";
  if (!input.input_capture.empty()) {
    std::filesystem::create_directories(capture_dir, ec);
    if (ec) {
      return Result<ReproducerResult>::Fail(Error{Kind::Environment, "a creatable input_capture/ directory",
                                                  ec.message(), capture_dir.string(),
                                                  "check the output directory is writable"});
    }
    for (const auto& [qualified_port, bytes] : input.input_capture) {
      const std::filesystem::path dest = capture_dir / (qualified_port + ".bin");
      const Result<bool> written = WriteBytes(dest, bytes.data(), bytes.size(), qualified_port);
      if (!written.ok()) return Result<ReproducerResult>::Fail(written.error());
      result.files_written.push_back(dest.string());
    }
  }

  const std::filesystem::path identity_path = package_dir / "module_identity.txt";
  const Result<bool> identity_written = WriteText(identity_path, input.module_identity, "module_identity.txt");
  if (!identity_written.ok()) return Result<ReproducerResult>::Fail(identity_written.error());
  result.files_written.push_back(identity_path.string());

  const std::filesystem::path stderr_path = package_dir / "stderr.txt";
  const Result<bool> stderr_written = WriteText(stderr_path, input.captured_stderr, "stderr.txt");
  if (!stderr_written.ok()) return Result<ReproducerResult>::Fail(stderr_written.error());
  result.files_written.push_back(stderr_path.string());

  return Result<ReproducerResult>::Ok(std::move(result));
}

}  // namespace simcore::diagnostics
