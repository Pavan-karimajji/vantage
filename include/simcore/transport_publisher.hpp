// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   The engine-side producer half of `SI-25` `transport` (`UT-TRN-*`,
///   `WP-27`) -- deliberately not part of `adas::transport::ITransport`
///   (`modules/interfaces`), whose four methods are the player/consumer
///   side only (`R-IFACE-1`: the shared contract is what both ends agree
///   on, and only the player ever calls `attach`/`tryReceive`/
///   `engineAlive`/`lastTickReceived`). `InProcessTransport::Publish` and
///   `SharedMemoryTransport::Publish` already share this exact signature;
///   this interface is what lets `Runner` (`runner.hpp`) hold one of
///   either without knowing which (`SetTransportPublisher`, the same
///   nullable-pointer, non-perturbing shape `SetCheckpoint`/
///   `SetByteCounter` already use -- absent, the run behaves exactly as
///   before, `SW-0352`).
/// @author Pavan Karimajji

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace simcore::transport {

class TransportPublisher {
 public:
  virtual ~TransportPublisher() = default;
  virtual void Publish(uint64_t tickIndex, const std::string& portName, const uint8_t* data, std::size_t size) = 0;
};

}  // namespace simcore::transport
