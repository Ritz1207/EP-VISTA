# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Explicit altitude sweep; never runs as part of a baseline case."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from .models import ProjectCase, ThrusterRecord
from .study import run_case


@dataclass(slots=True)
class AltitudeSweepRow:
    altitude_km: float
    mean_drag_mN: float
    maximum_drag_mN: float
    total_impulse_N_s: float
    propellant_kg: float | None
    limiting_thrust_margin_mN: float | None


def run_altitude_sweep(
    project: ProjectCase,
    candidate: ThrusterRecord,
    minimum_altitude_km: float,
    maximum_altitude_km: float,
    step_km: float,
    progress: Callable[[int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[AltitudeSweepRow]:
    if not 150 <= minimum_altitude_km <= maximum_altitude_km <= 300:
        raise ValueError("高度扫描必须位于150–300 km。")
    if step_km <= 0:
        raise ValueError("高度间隔必须大于0 km。")
    altitudes = np.arange(minimum_altitude_km, maximum_altitude_km + step_km * 0.5, step_km)
    notify = progress or (lambda _value, _message: None)
    cancelled = cancel_check or (lambda: False)
    rows: list[AltitudeSweepRow] = []
    started = perf_counter()

    def duration_text(seconds: float) -> str:
        seconds = max(0, int(round(seconds)))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}小时{minutes:02d}分"
        if minutes:
            return f"{minutes}分{seconds:02d}秒"
        return f"{seconds}秒"

    for index, altitude in enumerate(altitudes):
        if cancelled():
            raise RuntimeError("计算已取消。")
        point_count = len(altitudes)

        def nested_progress(value: int, message: str) -> None:
            point_fraction = min(max(value / 100.0, 0.0), 1.0)
            total_fraction = (index + point_fraction) / max(point_count, 1)
            elapsed = perf_counter() - started
            if total_fraction > 0:
                remaining = elapsed * (1.0 - total_fraction) / total_fraction
                timing = (
                    f"；已用{duration_text(elapsed)}，预计剩余{duration_text(remaining)}"
                )
            else:
                timing = ""
            notify(
                int(round(100 * total_fraction)),
                f"{altitude:g} km（{index + 1}/{point_count}）：{message}{timing}",
            )

        nested_progress(0, "准备计算")
        case = deepcopy(project)
        case.mission.altitude_km = float(altitude)
        case.selected_thruster_ids = [candidate.thruster_id]
        result = run_case(
            case,
            [candidate],
            progress=nested_progress,
            cancel_check=cancelled,
        )
        assessment = result.assessments[0]
        rows.append(
            AltitudeSweepRow(
                altitude_km=float(altitude),
                mean_drag_mN=result.demand.mean_drag_mN,
                maximum_drag_mN=result.demand.maximum_drag_mN,
                total_impulse_N_s=result.demand.total_impulse_N_s,
                propellant_kg=assessment.propellant_kg,
                limiting_thrust_margin_mN=assessment.limiting_thrust_margin_mN,
            )
        )
    notify(100, f"高度扫描完成；总用时{duration_text(perf_counter() - started)}")
    return rows
