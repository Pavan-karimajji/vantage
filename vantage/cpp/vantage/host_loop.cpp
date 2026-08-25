// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief See host_loop.hpp.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "vantage/host_loop.hpp"

#include "simcore/abi/simcore.h"
#include "simcore/transport.hpp"
#include "vantage/frame_bridge.hpp"

namespace sim::vantage {

HostLoopResult RunEmbedded(const std::string& run_spec_path, const std::string& config_path,
                           std::int64_t exec_timeout_ms, viz::session::PushSource& sink) {
  HostLoopResult result;

  char create_err[512] = {0};
  SimExitCode create_exit = kSimExitOk;
  SimEngine* engine = simEngineCreate(run_spec_path.c_str(), config_path.empty() ? nullptr : config_path.c_str(),
                                       exec_timeout_ms, create_err, sizeof(create_err), &create_exit);
  if (engine == nullptr) {
    result.ok = false;
    result.error = create_err;
    return result;
  }

  simcore::transport::InProcessTransport transport(/*depth=*/8);
  // `InProcessTransport` multiply-inherits `ITransport` AND
  // `TransportPublisher` -- convert to the correct base HERE, while the
  // compiler still has both types, BEFORE erasing to `void*`
  // (`simcore.h`'s own documented gotcha; `test_it11_embed_host.cpp`'s
  // `UT-ABI-04` found this live as a real defect).
  simcore::transport::TransportPublisher* publisher = &transport;
  simEngineAttachTransport(engine, publisher);

  std::uint32_t engine_version = 0;
  if (transport.attach(simcore::transport::InProcessTransport::kProtocolVersion, &engine_version) !=
      adas::transport::AttachResult::kOk) {
    result.ok = false;
    result.error = "vantage: in-process transport attach refused (version mismatch or engine unavailable)";
    simEngineDestroy(engine);
    return result;
  }

  FrameBridge bridge;
  for (;;) {
    char step_err[512] = {0};
    std::int32_t keep_going = 0;
    const SimExitCode step_exit = simEngineStepOnce(engine, step_err, sizeof(step_err), &keep_going);
    if (step_exit != kSimExitOk) {
      result.ok = false;
      result.error = step_err;
      break;
    }
    if (keep_going == 0) break;  // exhausted -- no cycle was actually stepped this call

    adas::transport::PortFrame frame{};
    while (transport.tryReceive(&frame)) {
      bridge.AddFrame(frame);
    }
    sink.DeliverTick(bridge.TakeTick(static_cast<std::uint64_t>(result.cycles_stepped)));
    ++result.cycles_stepped;
  }

  simEngineDestroy(engine);
  return result;
}

}  // namespace sim::vantage
