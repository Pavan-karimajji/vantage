// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief See frame_bridge.hpp.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "vantage/frame_bridge.hpp"

#include <utility>

#include "simcore/io.hpp"

namespace sim::vantage {

void FrameBridge::AddFrame(const adas::transport::PortFrame& frame) {
  viz::session::PortValue value;
  // The canonical spelling ("/df/aeb.outputs"), exactly what a Session gives a port read from a recording:
  // the player resolves plug-in ports against it (viz's ResolveTickPort), and a frame's own "df.aeb.outputs"
  // would bind nothing -- every layer unavailable, with a clean exit.
  value.name = simcore::io::CanonicalTopic(frame.portName != nullptr ? frame.portName : "");
  value.origin = viz::session::Origin::kSimulated;
  value.valid = true;
  value.updated = true;
  if (frame.data != nullptr) {
    value.payload.assign(frame.data, frame.data + frame.size);
  }
  pending_.push_back(std::move(value));
}

viz::session::Tick FrameBridge::TakeTick(std::uint64_t cycle_index) {
  viz::session::Tick tick;
  tick.index = static_cast<std::size_t>(cycle_index);
  tick.t_ns = static_cast<std::int64_t>(cycle_index);
  for (auto& value : pending_) {
    value.t_ns = tick.t_ns;
  }
  tick.ports = std::move(pending_);
  pending_.clear();
  return tick;
}

}  // namespace sim::vantage
