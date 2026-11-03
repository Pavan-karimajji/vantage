// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief `vantage-inspect` (`WP-16`, `IMP-0091`): the verbs `attach`, `dump` and `check` over a live measurement
///   that is named on the command line. Exit codes are `InspectExit`; every non-zero end names its cause.
///
///   vantage-inspect attach <name>
///   vantage-inspect dump <name> [--description] [--follow]
///   vantage-inspect check <name> [--recording <file.mcap>]
/// @author Pavan Karimajji

#include <iostream>
#include <string>

#include "inspector.hpp"

namespace {

using namespace vantage::inspector;

int Usage(const std::string& cause) {
  std::cerr << "vantage-inspect: " << cause << "\n"
            << "usage: vantage-inspect attach <name>\n"
            << "       vantage-inspect dump <name> [--description] [--follow]\n"
            << "       vantage-inspect check <name> [--recording <file.mcap>]\n";
  return kInspectUsage;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 3) return Usage(argc < 2 ? "no verb given" : "no live measurement name given");
  const std::string verb = argv[1];
  const std::string name = argv[2];
  if (verb != "attach" && verb != "dump" && verb != "check") return Usage("unknown verb '" + verb + "'");

  DumpOptions dump;
  CheckOptions check;
  for (int i = 3; i < argc; ++i) {
    const std::string arg = argv[i];
    if (verb == "dump" && arg == "--description") {
      dump.description = true;
    } else if (verb == "dump" && arg == "--follow") {
      dump.follow = true;
    } else if (verb == "check" && arg == "--recording" && i + 1 < argc) {
      check.recording = argv[++i];
    } else {
      return Usage("unknown argument '" + arg + "' for " + verb);
    }
  }

  if (verb == "attach") return runAttach(name, std::cout, std::cerr);

  AttachReport report = attachReadOnly(name);
  if (report.outcome != AttachOutcome::kOk) {
    std::cerr << "vantage-inspect: " << report.cause << "\n";
    return kInspectCannotAttach;
  }
  return verb == "dump" ? runDump(*report.attached, dump, std::cout, std::cerr)
                        : runCheck(*report.attached, check, std::cout, std::cerr);
}
