// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief `UT-EDG-08`/`09` (`IMP-0139`/`0140`, `WP-15`): `WriteReproducer`
///   writes a real package (spec copy, input snapshot, module identity,
///   stderr) on the happy path, and never raises -- an unwritable output
///   directory is a reported `Result::Fail`, never a thrown exception --
///   which is `diagnostics.hpp`'s blanket `SW-0140` property, exercised
///   here at this one I/O-touching symbol.
/// @author Pavan Karimajji

#include "simcore/diagnostics.hpp"

#include <fstream>

#include <gtest/gtest.h>

namespace simcore::diagnostics {
namespace {

std::filesystem::path UniqueTempDir(const std::string& name) {
  const std::filesystem::path dir = std::filesystem::temp_directory_path() / name;
  std::filesystem::remove_all(dir);
  return dir;
}

TEST(UtEdg08Reproducer, WritesARealPackageWithEveryDeclaredPiece) {
  const std::filesystem::path spec_path = std::filesystem::temp_directory_path() / "ut_edg_08_spec.json";
  {
    std::ofstream spec_out(spec_path, std::ios::trunc);
    spec_out << R"({"schema": "adas.sim.runspec/1.0"})";
  }

  ReproducerInput input;
  input.run_spec_path = spec_path;
  input.failing_cycle = 42;
  input.input_capture["a.in"] = {0x01, 0x02, 0x03};
  input.module_identity = "component=echo_stub build_id=test";
  input.captured_stderr = "segfault at 0xdeadbeef\n";

  const std::filesystem::path output_dir = UniqueTempDir("ut_edg_08_out");
  const Result<ReproducerResult> result = WriteReproducer(output_dir, input);
  ASSERT_TRUE(result.ok()) << result.error().Format();

  const ReproducerResult& package = result.value();
  EXPECT_TRUE(std::filesystem::exists(package.package_dir / "run_spec.json"));
  EXPECT_TRUE(std::filesystem::exists(package.package_dir / "input_capture" / "a.in.bin"));
  EXPECT_TRUE(std::filesystem::exists(package.package_dir / "module_identity.txt"));
  EXPECT_TRUE(std::filesystem::exists(package.package_dir / "stderr.txt"));
  EXPECT_EQ(package.files_written.size(), 4u);

  std::ifstream stderr_in(package.package_dir / "stderr.txt");
  std::ostringstream buf;
  buf << stderr_in.rdbuf();
  EXPECT_EQ(buf.str(), input.captured_stderr);

  std::ifstream snapshot_in(package.package_dir / "input_capture" / "a.in.bin", std::ios::binary);
  std::vector<std::uint8_t> bytes((std::istreambuf_iterator<char>(snapshot_in)), std::istreambuf_iterator<char>());
  EXPECT_EQ(bytes, input.input_capture["a.in"]);

  std::filesystem::remove_all(output_dir);
  std::filesystem::remove(spec_path);
}

// UT-EDG-09: an unwritable output directory is a reported failure, never a
// crash -- exercised by pointing `output_dir` at a path that already
// exists as a REGULAR FILE, so `create_directories` cannot possibly
// succeed there (a real, portable way to force the failure without
// depending on filesystem permission semantics that differ across CI
// images).
TEST(UtEdg09DiagnosticsNeverRaise, AnUnwritableOutputDirectoryIsAReportedFailureNotAnException) {
  const std::filesystem::path blocking_file = std::filesystem::temp_directory_path() / "ut_edg_09_blocking_file";
  {
    std::ofstream touch(blocking_file, std::ios::trunc);
    touch << "not a directory";
  }

  ReproducerInput input;
  input.module_identity = "unused";
  input.captured_stderr = "unused";

  Result<ReproducerResult> result = Result<ReproducerResult>::Fail(Error{});
  EXPECT_NO_THROW({
    // `blocking_file` itself is not a directory and cannot become one --
    // create_directories(blocking_file / "cycle_0") must fail.
    result = WriteReproducer(blocking_file, input);
  });
  EXPECT_FALSE(result.ok());
  EXPECT_EQ(result.error().kind, Kind::Environment);

  std::filesystem::remove(blocking_file);
}

TEST(UtEdg09DiagnosticsNeverRaise, AMissingRunSpecPathIsAReportedFailureNotAnException) {
  ReproducerInput input;
  input.run_spec_path = "/definitely/does/not/exist/spec.json";
  input.module_identity = "unused";

  const std::filesystem::path output_dir = UniqueTempDir("ut_edg_09_missing_spec");
  Result<ReproducerResult> result = Result<ReproducerResult>::Fail(Error{});
  EXPECT_NO_THROW({ result = WriteReproducer(output_dir, input); });
  EXPECT_FALSE(result.ok());
  EXPECT_EQ(result.error().kind, Kind::Environment);

  std::filesystem::remove_all(output_dir);
}

}  // namespace
}  // namespace simcore::diagnostics
