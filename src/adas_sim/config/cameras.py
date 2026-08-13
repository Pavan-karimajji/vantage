# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`CameraModel` -- intrinsics/extrinsics fields declared now so `S-D4`
(projection) does not have to invent the shape later; declaring costs
nothing and projection itself stays unimplemented until then."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CameraModel:
    camera_id: str
    pose_x_m: float
    pose_y_m: float
    pose_z_m: float
    pose_yaw_deg: float
    pose_pitch_deg: float
    pose_roll_deg: float
    focal_length_x_px: float
    focal_length_y_px: float
    principal_point_x_px: float
    principal_point_y_px: float
    image_width_px: int
    image_height_px: int

    def __repr__(self) -> str:
        return f"<CameraModel {self.camera_id!r} image={self.image_width_px}x{self.image_height_px}>"
