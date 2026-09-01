# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""NRLMSIS 2.0 evaluation through pymsis 0.12.0."""

from __future__ import annotations

from collections.abc import Callable
import numpy as np
import pymsis

from .models import AtmosphereSamples, OrbitSamples
from .weather import WeatherInputs


EXPECTED_PYMSIS_VERSION = "0.12.0"


def evaluate_nrlmsis2(
    orbit: OrbitSamples,
    weather: WeatherInputs,
    batch_rows: int = 250_000,
    cancel_check: Callable[[], bool] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> AtmosphereSamples:
    if pymsis.__version__ != EXPECTED_PYMSIS_VERSION:
        raise RuntimeError(
            f"EP-VISTA要求pymsis {EXPECTED_PYMSIS_VERSION}，当前为{pymsis.__version__}。"
        )
    count = orbit.utc.size
    if weather.ap7.shape != (count, 7):
        raise ValueError("空间天气数据行数与轨道样本数不一致。")
    output = np.empty((count, 11), dtype=float)
    report = progress or (lambda _completed, _total: None)
    report(0, count)
    for start in range(0, count, batch_rows):
        if cancel_check is not None and cancel_check():
            raise RuntimeError("计算已取消。")
        stop = min(start + batch_rows, count)
        block = pymsis.calculate(
            orbit.utc[start:stop],
            orbit.longitude_deg[start:stop],
            orbit.latitude_deg[start:stop],
            orbit.altitude_km[start:stop],
            f107s=weather.f107_daily[start:stop],
            f107as=weather.f107_81day[start:stop],
            aps=weather.ap7[start:stop, :],
            version=2.0,
            geomagnetic_activity=-1,
        )
        output[start:stop, :] = np.asarray(block, dtype=float).reshape((-1, 11))
        report(stop, count)
    if cancel_check is not None and cancel_check():
        raise RuntimeError("计算已取消。")
    # pymsis keeps an NO output slot shared with NRLMSIS 2.1, but NRLMSIS 2.0
    # does not provide NO and therefore returns NaN in column 9. EP-VISTA does not
    # expose that unsupported quantity as a computed species.
    supported = output[:, [0, 1, 2, 3, 4, 5, 6, 7, 8, 10]]
    if not np.all(np.isfinite(supported)):
        raise ValueError("NRLMSIS 2.0支持的输出量包含非有限值。")
    if np.any(output[:, 0] <= 0) or np.any(output[:, 1:9] < 0) or np.any(output[:, 10] <= 0):
        raise ValueError("NRLMSIS 2.0输出不满足密度、组分和温度的物理范围。")
    return AtmosphereSamples(
        mass_density_kg_m3=output[:, 0],
        n_N2_m3=output[:, 1],
        n_O2_m3=output[:, 2],
        n_O_m3=output[:, 3],
        n_He_m3=output[:, 4],
        n_H_m3=output[:, 5],
        n_Ar_m3=output[:, 6],
        n_N_m3=output[:, 7],
        n_anomalous_O_m3=output[:, 8],
        temperature_K=output[:, 10],
    )
