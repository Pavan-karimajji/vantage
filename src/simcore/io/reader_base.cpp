// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `detail::AccumulateBatch` (`IMP-0025`, `IMP-0026`) -- the shared
///   three-axis batching loop every codec's `Reader::ReadRange` delegates
///   to. Replaces **both** `io/base.py`'s message list/regrouped dict and
///   `sil_host/src/recording_reader.cpp`'s whole-file
///   `std::vector<RecordingTick>` (`SW-0025`'s own `Now.`) -- neither is
///   ported, both are replaced by this one streaming implementation.
/// @author Pavan Karimajji

#include "simcore/io.hpp"

namespace simcore::io::detail {

Batch AccumulateBatch(
    const ReadBounds& bounds, std::optional<RawMessage>& lookahead,
    const std::function<std::optional<RawMessage>()>& pull) {
  Batch batch;
  std::int64_t span_start_ns = 0;
  bool have_span_start = false;
  std::size_t bytes_so_far = 0;

  const auto next_message = [&]() -> std::optional<RawMessage> {
    if (lookahead.has_value()) {
      std::optional<RawMessage> msg = std::move(lookahead);
      lookahead.reset();
      return msg;
    }
    return pull();
  };

  while (true) {
    std::optional<RawMessage> msg = next_message();
    if (!msg.has_value()) {
      batch.end_reason = BatchEndReason::kEndOfStream;
      batch.exhausted = true;
      return batch;
    }

    const std::size_t msg_bytes = msg->payload.size();

    // IMP-0026: a message exceeding max_bytes alone is emitted alone, so
    // the bound cannot deadlock -- both byte and span checks below only
    // fire once the batch already holds ≥1 message.
    if (bounds.max_bytes != 0 && !batch.messages.empty() && bytes_so_far + msg_bytes > bounds.max_bytes) {
      lookahead = std::move(msg);
      batch.end_reason = BatchEndReason::kBytes;
      return batch;
    }
    if (bounds.max_span_ns != 0 && have_span_start &&
        msg->log_time_ns - span_start_ns > bounds.max_span_ns) {
      lookahead = std::move(msg);
      batch.end_reason = BatchEndReason::kSpan;
      return batch;
    }

    if (!have_span_start) {
      span_start_ns = msg->log_time_ns;
      have_span_start = true;
    }
    bytes_so_far += msg_bytes;
    batch.messages.push_back(std::move(*msg));

    if (bounds.max_messages != 0 && batch.messages.size() >= bounds.max_messages) {
      batch.end_reason = BatchEndReason::kCount;
      return batch;
    }
  }
}

}  // namespace simcore::io::detail
