// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `IMP-0082`/`IMP-0393` (`WP-10`): `module_host`'s own thin window onto
///   the generic SIL ABI. The ABI itself is declared exactly once, in
///   `modules/interfaces` (R-IFACE-1) -- this header never redeclares
///   `AdasPort`/`AdasPortSet`/`adasExec` etc., it only pulls them into
///   `simcore::module_host` so a caller never needs to know the struct
///   lives in a first-party dependency rather than this module. `KEEP`
///   because the real content (`adas/adas_sil_abi.h`) already existed and
///   is untouched; `EXTEND` because this alias layer is new.
/// @author Pavan Karimajji

#pragma once

#include "adas/adas_sil_abi.h"

namespace simcore::module_host {

using ::AdasPort;
using ::AdasPortSet;

inline constexpr int32_t kAbiVersion = ADAS_SIL_ABI_VERSION;

}  // namespace simcore::module_host
