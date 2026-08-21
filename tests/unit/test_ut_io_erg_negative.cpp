// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   Regression coverage for three real defects found live in code review
///   (2026-08-21, all independently confirmed by reading `erg.cpp` before
///   fixing): a bare-scalar port match crashing `Open()` via an
///   out-of-range `substr()` rather than returning the `Result::Fail` the
///   code around it clearly intended; an all-diagnostic `.erg` (every real
///   column matches nothing but `<component>.host.*`) leaving
///   `resolved_ports_` empty and `Pull()` indexing it anyway; and a
///   `"N Bytes"`-typed column bound to a real scalar leaf field silently
///   mis-reading the wrong byte count instead of being refused at load
///   time. Each case here is a small, synthetic `.erg`/`.erg.info` pair
///   (real reconstruction correctness is `UT-IO-28`/`UT-IO-29`'s own job,
///   against the real fixture — these three are error-path-only, and a
///   synthetic file is the honest way to reach an error path a real
///   capture never happens to exercise) plus the REAL manifest sidecar,
///   copied unmodified, since only the `.erg`/`.info` shape needs to
///   change to reach each case.
/// @author Pavan Karimajji

#include <cstring>
#include <fstream>

#include <gtest/gtest.h>

#include "simcore/io.hpp"

namespace simcore::io {
namespace {

std::filesystem::path RealManifestPath() {
  // tests/unit/test_ut_io_erg_negative.cpp -> ../fixtures/erg
  return std::filesystem::path(__FILE__).parent_path() / ".." / "fixtures" / "erg" /
         "bsd_tos_left_straight_1row.manifest.pb";
}

void WriteFile(const std::filesystem::path& path, const std::string& bytes) {
  std::ofstream out(path, std::ios::binary);
  out.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
}

void CopyManifestSidecar(const std::filesystem::path& erg_stem) {
  std::ifstream in(RealManifestPath(), std::ios::binary);
  std::ostringstream buf;
  buf << in.rdbuf();
  std::filesystem::path manifest_path = erg_stem;
  manifest_path += ".manifest.pb";
  WriteFile(manifest_path, buf.str());
}

// Builds a minimal, synthetic .erg (header + exactly one row) and its
// .erg.info sidecar, given the second column's own name/type/value --
// column 1 is always "Time"=0.0 (Double). Real manifest sidecar copied
// alongside, real PortSpec names ("bsd.compState") reused deliberately,
// since these tests exercise erg.cpp's own grouping/validation logic
// against those real, stable names -- not the reconstruction itself.
std::filesystem::path BuildOneColumnFixture(
    const std::string& name, const std::string& stem, const std::string& info_type,
    std::size_t byte_width, const std::string& raw_value_bytes) {
  const std::filesystem::path dir = std::filesystem::temp_directory_path();
  const std::filesystem::path erg_stem = dir / stem;
  std::filesystem::path erg_path = erg_stem;
  erg_path += ".erg";
  std::filesystem::path info_path = erg_stem;
  info_path += ".erg.info";

  const std::uint32_t row_size = static_cast<std::uint32_t>(8 + byte_width);
  std::string header = std::string("CM-ERG", 6) + std::string(2, '\0');
  std::uint16_t version = 1;
  header.append(reinterpret_cast<const char*>(&version), sizeof(version));
  header.append(reinterpret_cast<const char*>(&row_size), sizeof(row_size));
  header.append(2, '\0');

  double time_s = 0.0;
  std::string row;
  row.append(reinterpret_cast<const char*>(&time_s), sizeof(time_s));
  row.append(raw_value_bytes);
  EXPECT_EQ(row.size(), row_size) << "test bug: raw_value_bytes width must match byte_width";

  WriteFile(erg_path, header + row);

  std::ostringstream info;
  info << "#INFOFILE1.1 (UTF-8) - Do not remove this line!\n\n";
  info << "File.Format = erg\nFile.ByteOrder = LittleEndian\n\n";
  info << "File.At.1.Name = Time\nFile.At.1.Type = Double\n\n";
  info << "File.At.2.Name = " << name << "\nFile.At.2.Type = " << info_type << "\n";
  WriteFile(info_path, info.str());

  CopyManifestSidecar(erg_stem);
  return erg_path;
}

TEST(ErgNegative, BareScalarPortMatchIsARefusalNotACrash) {
  // "bsd.compState" (no ".state" suffix) exactly equals a real manifest
  // port name -- LongestPortMatch's own exact-match branch returns it,
  // and the code immediately after must refuse cleanly, not throw.
  const std::int32_t value = 1;
  const auto path = BuildOneColumnFixture(
      "bsd.compState", "ut_io_erg_neg_01", "Int", 4,
      std::string(reinterpret_cast<const char*>(&value), sizeof(value)));

  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterErg(registry).ok());
  auto reader_result = registry.OpenRead(path);
  ASSERT_TRUE(reader_result.ok());
  const std::unique_ptr<Reader>& reader = reader_result.value();

  const Result<bool> opened = reader->Open(path);  // must not throw std::out_of_range
  EXPECT_FALSE(opened.ok());
  EXPECT_NE(opened.error().found.find("bare-scalar"), std::string::npos) << opened.error().Format();
}

TEST(ErgNegative, AllDiagnosticColumnsLeaveNoPortsAndReadRangeIsSafelyEmpty) {
  // "df.host.execCount" matches the <component>.host.* diagnostic prefix
  // and is dropped -- zero real ports resolve, but the file still has one
  // real row. Pull() must not index an empty resolved_ports_.
  const std::int32_t value = 7;
  const auto path = BuildOneColumnFixture(
      "df.host.execCount", "ut_io_erg_neg_02", "Int", 4,
      std::string(reinterpret_cast<const char*>(&value), sizeof(value)));

  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterErg(registry).ok());
  auto reader_result = registry.OpenRead(path);
  ASSERT_TRUE(reader_result.ok());
  const std::unique_ptr<Reader>& reader = reader_result.value();

  ASSERT_TRUE(reader->Open(path).ok());
  EXPECT_TRUE(reader->Describe().empty());

  ReadBounds bounds;
  bounds.max_messages = 100;
  const Batch batch = reader->ReadRange(bounds);  // must not read resolved_ports_[0] on an empty vector
  EXPECT_TRUE(batch.messages.empty());
  EXPECT_TRUE(batch.exhausted);
}

TEST(ErgNegative, BytesColumnBoundToAScalarLeafIsRefusedAtOpen) {
  // "bsd.compState.state" is a real Int leaf (CompState.state, an enum) --
  // declaring it "5 Bytes" instead must be refused at Open(), not read as
  // 4 raw bytes regardless of the declared width (over/under-reading
  // adjacent row memory).
  const std::string five_bytes("\x01\x00\x00\x00\x00", 5);  // explicit length -- a literal's implicit
                                                              // const char* ctor stops at the embedded '\0'
  const auto path = BuildOneColumnFixture("bsd.compState.state", "ut_io_erg_neg_03", "5 Bytes", 5, five_bytes);

  CodecRegistry registry;
  ASSERT_TRUE(codecs::RegisterErg(registry).ok());
  auto reader_result = registry.OpenRead(path);
  ASSERT_TRUE(reader_result.ok());
  const std::unique_ptr<Reader>& reader = reader_result.value();

  const Result<bool> opened = reader->Open(path);
  EXPECT_FALSE(opened.ok());
  EXPECT_NE(opened.error().found.find("not a scalar"), std::string::npos) << opened.error().Format();
}

}  // namespace
}  // namespace simcore::io
