// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `WriterBase::WriteMessage`/`Flush` (`IMP-0040`, `IMP-0041`). Every
///   message is forwarded to the wrapped `Writer` the instant it arrives --
///   this class accumulates only COUNTERS since the last flush, never the
///   messages themselves, which is what keeps peak writer memory bounded by
///   one batch (SW-0041's Accept) rather than a run's whole output.
/// @author Pavan Karimajji

#include "simcore/io.hpp"

namespace simcore::io {

WriterBase::WriterBase(Writer& writer, ReadBounds flush_bounds)
    : writer_(writer), flush_bounds_(flush_bounds) {}

void WriterBase::WriteMessage(const RawMessage& message) {
  // Forwarded immediately -- never staged in a container keyed by topic
  // (SW-0040: "no map iteration reaches the file"), so the sequence the
  // wrapped `Writer` sees is exactly the caller's own call order.
  writer_.Write(message);

  if (!have_span_start_) {
    span_start_ns_ = message.log_time_ns;
    have_span_start_ = true;
  }
  pending_messages_ += 1;
  pending_bytes_ += message.payload.size();
  const std::int64_t span_ns = message.log_time_ns - span_start_ns_;

  const bool count_due = flush_bounds_.max_messages != 0 && pending_messages_ >= flush_bounds_.max_messages;
  const bool bytes_due = flush_bounds_.max_bytes != 0 && pending_bytes_ >= flush_bounds_.max_bytes;
  const bool span_due = flush_bounds_.max_span_ns != 0 && span_ns >= flush_bounds_.max_span_ns;

  if (count_due || bytes_due || span_due) {
    Flush();
  }
}

void WriterBase::Flush() {
  writer_.Flush();
  pending_messages_ = 0;
  pending_bytes_ = 0;
  have_span_start_ = false;
}

}  // namespace simcore::io
