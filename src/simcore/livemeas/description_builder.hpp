// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   `BuildMeasDescription` (`IMP-0078`, `ARCH §4`): the live measurement's `MeasDescription`, built from
///   the run setup, the loaded component manifests and the recording's topic index. The order of its
///   `ports` is the port index a step's values use.
/// @author Pavan Karimajji

#pragma once

#include <map>
#include <string>

#include "livemeas/meas_description.pb.h"
#include "simcore/io.hpp"
#include "simcore/module_host.hpp"
#include "simcore/runspec.hpp"

namespace simcore::livemeas {

/// Stages (every one, with its mode), ports (every port of a stage that is not `off`, then each
/// `source.<port>` an input is wired to), the descriptor set (every manifest's and every recorded topic's
/// schemas, once per file), config bundles, overrides and the readiness limit.
adas::livemeas::MeasDescription BuildMeasDescription(
    const RunSpec& spec, const std::map<std::string, module_host::Component*>& components,
    const std::map<std::string, io::TopicInfo>& topics);

}  // namespace simcore::livemeas
