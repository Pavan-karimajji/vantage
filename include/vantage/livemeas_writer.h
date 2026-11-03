// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VANTAGE
/// @file
/// @brief
///   The live measurement writer's plain-C API (`IMP-0071`, `RCT:IMP-0034`..`0037`): the three
///   calls every engine makes and nothing else (`ARCH §10.1`). No C++ and no protobuf type
///   crosses this header, so an engine written in C needs neither. No call throws, aborts or
///   waits: every problem is a result code.
///
///   A step's `values` array may hold a port index more than once: that is how a stage run twice
///   in one engine step arrives, its runs in run order (`D30`). The description is passed as the
///   serialized bytes of `adas.livemeas.MeasDescription`; a value's `port` is an index into its
///   `ports`.
/// @author Pavan Karimajji

#ifndef VANTAGE_LIVEMEAS_WRITER_H
#define VANTAGE_LIVEMEAS_WRITER_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/// What every call returns. Closed list.
typedef enum LiveMeasResult {
  kLiveMeasOk = 0,
  /// `liveMeasOpen`: a live measurement of that name has a writer that is alive.
  kLiveMeasNameHeld = 1,
  /// A null pointer, a zero count, a slot too small for its header or not a multiple of 8, an
  /// outcome outside 1..4: nothing was done.
  kLiveMeasBadArgument = 2,
  /// `liveMeasOpen`: a segment could not be created, mapped or replaced.
  kLiveMeasOpenFailed = 3,
  /// An exception was caught inside the call; the writer is left as it was.
  kLiveMeasInternalError = 4
} LiveMeasResult;

/// The opaque writer of one engine run.
typedef struct LiveMeasHandle LiveMeasHandle;

/// Ring geometry: values from the run setup, never defaulted. Each size is a multiple of 8.
typedef struct LiveMeasGeometry {
  uint32_t cycle_slot_count;
  uint32_t cycle_slot_size;
  uint32_t bulk_slot_count;
  uint32_t bulk_slot_size;
} LiveMeasGeometry;

/// One port value of a step. `origin` is the number of `MeasPortValue.Origin`; `bulk` non-zero
/// sends the payload to `MeasBulk` and the value carries a reference.
typedef struct LiveMeasValue {
  uint32_t port;
  const uint8_t* payload;
  uint32_t length;
  uint32_t origin;
  uint64_t age_ns;
  int32_t bulk;
} LiveMeasValue;

/// One badge of a step. `kind` is the number of `MeasBadge.Kind`; `subject` a C string.
typedef struct LiveMeasBadge {
  uint32_t kind;
  const char* subject;
  uint64_t count;
} LiveMeasBadge;

/// Creates the data and bulk segments of `name`, writes `MeasStatus` and the description, then
/// sets `status` running. A name whose writer is alive: `kLiveMeasNameHeld`. A name whose writer
/// is dead is replaced.
LiveMeasResult liveMeasOpen(const char* name, const LiveMeasGeometry* geometry, const uint8_t* description,
                            uint32_t description_length, LiveMeasHandle** out_handle);

/// Writes one `MeasCycle`: values in the order given, badges after them. A bulk value goes to
/// `MeasBulk` first. A payload that does not fit is marked omitted; a step that still does not
/// fit is not written and `droppedCycles` rises. `heartbeat` rises on every call.
LiveMeasResult liveMeasStep(LiveMeasHandle* handle, uint64_t step, int64_t sim_time_ns, const LiveMeasValue* values,
                            uint32_t value_count, const LiveMeasBadge* badges, uint32_t badge_count);

/// Sets `outcome` (the number of `MeasStatus.outcome`: 1 pass, 2 fail, 3 crash, 4 timeout), then
/// `status` finished, removes the name and frees the handle. Readers already attached keep
/// reading. On `kLiveMeasBadArgument` the handle is still open.
LiveMeasResult liveMeasClose(LiveMeasHandle* handle, uint32_t outcome);

#ifdef __cplusplus
}  // extern "C"
#endif

#endif  // VANTAGE_LIVEMEAS_WRITER_H
