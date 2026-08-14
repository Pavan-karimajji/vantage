// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `LazyPayload<T>`'s decode counter (`IMP-0027`). The template itself
///   lives in `io.hpp` (a template member cannot be defined once in a .cpp
///   for every `T`); this is the one non-templated seam it calls through,
///   so `DecodeCount()` answers for every payload type with one counter,
///   never one per `T`.
/// @author Pavan Karimajji

#include <atomic>

#include "simcore/io.hpp"

namespace simcore::io {

namespace {
std::atomic<std::size_t> g_decode_count{0};
}  // namespace

void BumpDecodeCount_() { g_decode_count.fetch_add(1, std::memory_order_relaxed); }

std::size_t DecodeCount() { return g_decode_count.load(std::memory_order_relaxed); }

void ResetDecodeCount() { g_decode_count.store(0, std::memory_order_relaxed); }

}  // namespace simcore::io
