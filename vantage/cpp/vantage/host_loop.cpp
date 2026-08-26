// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief See host_loop.hpp.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "vantage/host_loop.hpp"

#include <utility>

#include "simcore/abi/simcore.h"

namespace sim::vantage {

simcore::Result<EmbeddedEngine> EmbeddedEngine::Create(const std::string& run_spec_path,
                                                        const std::string& config_path,
                                                        std::int64_t exec_timeout_ms) {
  char create_err[512] = {0};
  SimExitCode create_exit = kSimExitOk;
  SimEngine* raw_engine = simEngineCreate(run_spec_path.c_str(),
                                          config_path.empty() ? nullptr : config_path.c_str(), exec_timeout_ms,
                                          create_err, sizeof(create_err), &create_exit);
  if (raw_engine == nullptr) {
    return simcore::Result<EmbeddedEngine>::Fail(
        simcore::Error{simcore::Kind::Environment, "a constructed SimEngine", create_err,
                       "sim::vantage::EmbeddedEngine::Create"});
  }

  auto transport = std::make_unique<simcore::transport::InProcessTransport>(/*depth=*/8);
  // `InProcessTransport` multiply-inherits `ITransport` AND
  // `TransportPublisher` -- convert to the correct base HERE, while the
  // compiler still has both types, BEFORE erasing to `void*` (`simcore.h`'s
  // own documented gotcha; `test_it11_embed_host.cpp`'s `UT-ABI-04` found
  // this live as a real defect).
  simcore::transport::TransportPublisher* publisher = transport.get();
  simEngineAttachTransport(raw_engine, publisher);

  std::uint32_t engine_version = 0;
  if (transport->attach(simcore::transport::InProcessTransport::kProtocolVersion, &engine_version) !=
      adas::transport::AttachResult::kOk) {
    simEngineDestroy(raw_engine);
    return simcore::Result<EmbeddedEngine>::Fail(simcore::Error{
        simcore::Kind::Internal, "an in-process transport attach accepted", "refused (version mismatch or engine unavailable)",
        "sim::vantage::EmbeddedEngine::Create"});
  }

  EmbeddedEngine engine;
  engine.engine_ = raw_engine;
  engine.transport_ = std::move(transport);
  return simcore::Result<EmbeddedEngine>::Ok(std::move(engine));
}

EmbeddedEngine::~EmbeddedEngine() { simEngineDestroy(engine_); }

EmbeddedEngine::EmbeddedEngine(EmbeddedEngine&& other) noexcept
    : engine_(other.engine_),
      transport_(std::move(other.transport_)),
      bridge_(std::move(other.bridge_)),
      ok_(other.ok_),
      exhausted_(other.exhausted_),
      error_(std::move(other.error_)),
      cycles_stepped_(other.cycles_stepped_) {
  other.engine_ = nullptr;
}

EmbeddedEngine& EmbeddedEngine::operator=(EmbeddedEngine&& other) noexcept {
  if (this != &other) {
    simEngineDestroy(engine_);
    engine_ = other.engine_;
    transport_ = std::move(other.transport_);
    bridge_ = std::move(other.bridge_);
    ok_ = other.ok_;
    exhausted_ = other.exhausted_;
    error_ = std::move(other.error_);
    cycles_stepped_ = other.cycles_stepped_;
    other.engine_ = nullptr;
  }
  return *this;
}

bool EmbeddedEngine::StepOnce(viz::session::PushSource& sink) {
  if (!ok_ || exhausted_) {
    return false;  // a prior step already failed or exhausted the run -- no-op, never re-entered
  }

  char step_err[512] = {0};
  std::int32_t keep_going = 0;
  const SimExitCode step_exit = simEngineStepOnce(engine_, step_err, sizeof(step_err), &keep_going);
  if (step_exit != kSimExitOk) {
    ok_ = false;
    error_ = step_err;
    return false;
  }
  if (keep_going == 0) {
    exhausted_ = true;  // no cycle was actually stepped this call -- ok_ stays true (SW-0148's own "expected, not an error")
    return false;
  }

  adas::transport::PortFrame frame{};
  while (transport_->tryReceive(&frame)) {
    bridge_.AddFrame(frame);
  }
  sink.DeliverTick(bridge_.TakeTick(static_cast<std::uint64_t>(cycles_stepped_)));
  ++cycles_stepped_;
  return true;
}

HostLoopResult RunEmbedded(const std::string& run_spec_path, const std::string& config_path,
                           std::int64_t exec_timeout_ms, viz::session::PushSource& sink) {
  HostLoopResult result;

  simcore::Result<EmbeddedEngine> created = EmbeddedEngine::Create(run_spec_path, config_path, exec_timeout_ms);
  if (!created.ok()) {
    result.ok = false;
    result.error = created.error().found;
    return result;
  }
  // `std::move(created).value()` (the `&&`-qualified `Result<T>::value()`
  // overload) is not portable across every `adas-sim` package this repo
  // might resolve against -- `viz::session::Session`-moving call sites
  // elsewhere in this codebase (e.g. `modules/viz/tests/unit/
  // test_session.cpp`) already work around an older cached package lacking
  // it via the identical `const_cast` idiom below, so this stays
  // buildable regardless of which `errors.hpp` a given build resolves.
  EmbeddedEngine engine = std::move(const_cast<EmbeddedEngine&>(created.value()));

  while (engine.StepOnce(sink)) {
  }

  result.ok = engine.ok();
  result.error = engine.error();
  result.cycles_stepped = engine.cycles_stepped();
  return result;
}

}  // namespace sim::vantage
