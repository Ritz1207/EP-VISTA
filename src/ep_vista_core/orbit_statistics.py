# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Shared, time-weighted revolution statistics for judgments and plots.

Linear interpolation inserts exact revolution boundaries. The final partial
revolution is included over its actual duration, never silently discarded.
"""

from dataclasses import dataclass

import numpy as np


ASSESSMENT_BASIS = "per_orbit_time_mean_strict_gt_v1"
ASSESSMENT_NOTE = (
    "按每圈平均补偿判断：每圈平均实际可用推力须大于对应平均阻力；"
    "末尾不足一圈按实际时段计入。允许圈内瞬时推力不足，不保证瞬时定高；"
    "未模拟高度波动，供电与设备工作范围仍需满足。"
)


@dataclass(frozen=True)
class OrbitStatistics:
    time: np.ndarray
    mean: np.ndarray
    minimum: np.ndarray
    maximum: np.ndarray


class OrbitReducer:
    """Prepare O(N) interval reductions once for any same-orbit force series."""

    def __init__(self, time, phase_unwrapped_deg):
        self.original_time = np.asarray(time, dtype=float)
        phase = np.asarray(phase_unwrapped_deg, dtype=float)
        if (self.original_time.ndim != 1 or phase.shape != self.original_time.shape
                or phase.size < 2 or not np.all(np.isfinite(phase))
                or not np.all(np.isfinite(self.original_time))
                or np.any(np.diff(self.original_time) <= 0) or np.any(np.diff(phase) <= 0)):
            raise ValueError("逐圈统计需要至少两个UTC与轨道相位严格递增的有限采样点。")
        crossings = np.arange(np.floor(phase[0] / 360) + 1, np.ceil(phase[-1] / 360)) * 360
        crossings = crossings[(crossings > phase[0] + 1e-9) & (crossings < phase[-1] - 1e-9)]
        self.edges = np.r_[self.original_time[0], np.interp(crossings, phase, self.original_time), self.original_time[-1]]
        self.time = np.unique(np.r_[self.original_time, self.edges])
        self.indices = np.searchsorted(self.time, self.edges)
        self.duration = np.diff(self.edges)

    def reduce(self, values) -> OrbitStatistics:
        values = np.asarray(values, dtype=float)
        if values.shape != self.original_time.shape or not np.all(np.isfinite(values)):
            raise ValueError("逐圈统计数值必须有限且与轨道采样维度一致。")
        augmented = np.interp(self.time, self.original_time, values)
        areas = (augmented[:-1] + augmented[1:]) * 0.5 * np.diff(self.time)
        integral = np.add.reduceat(areas, self.indices[:-1])
        # Include both bounding values in each min/max; adjacent circles share
        # a boundary, not any finite-duration interval.
        minimum = np.minimum(np.minimum.reduceat(augmented[:-1], self.indices[:-1]), augmented[self.indices[1:]])
        maximum = np.maximum(np.maximum.reduceat(augmented[:-1], self.indices[:-1]), augmented[self.indices[1:]])
        return OrbitStatistics((self.edges[:-1] + self.edges[1:]) * 0.5,
                               integral / self.duration, minimum, maximum)
