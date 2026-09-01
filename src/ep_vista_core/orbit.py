# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Circular SSO propagation using the same J2 secular model as MATLAB baseline."""

from __future__ import annotations

from datetime import datetime, timezone
import math

import numpy as np

from .models import OrbitSamples


EARTH_MEAN_RADIUS_M = 6_371_000.0
EARTH_MU_M3_S2 = 3.986004418e14
EARTH_J2 = 1.08262668e-3
TROPICAL_YEAR_DAYS = 365.2422


def _unix_seconds(utc_text: str) -> float:
    parsed = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("UTC必须包含时区。")
    return parsed.astimezone(timezone.utc).timestamp()


def orbital_period_seconds(altitude_km: float) -> float:
    radius_m = EARTH_MEAN_RADIUS_M + 1000.0 * altitude_km
    return 2.0 * math.pi * math.sqrt(radius_m**3 / EARTH_MU_M3_S2)


def sso_inclination_deg(altitude_km: float) -> float:
    radius_m = EARTH_MEAN_RADIUS_M + 1000.0 * altitude_km
    mean_motion = math.sqrt(EARTH_MU_M3_S2 / radius_m**3)
    target_rate = math.radians(360.0 / TROPICAL_YEAR_DAYS) / 86400.0
    cosine = -target_rate / (
        1.5 * EARTH_J2 * mean_motion * (EARTH_MEAN_RADIUS_M / radius_m) ** 2
    )
    if abs(cosine) > 1:
        raise ValueError(f"{altitude_km:.3f} km处不存在当前J2近似下的SSO。")
    return math.degrees(math.acos(cosine))


def _sun_ra_dec(unix_seconds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    julian_date = unix_seconds / 86400.0 + 2440587.5
    centuries = (julian_date - 2451545.0) / 36525.0
    mean_longitude = np.mod(
        280.46646 + 36000.76983 * centuries + 0.0003032 * centuries**2, 360.0
    )
    mean_anomaly = np.mod(
        357.52911 + 35999.05029 * centuries - 0.0001537 * centuries**2, 360.0
    )
    anomaly_rad = np.deg2rad(mean_anomaly)
    equation_center = (
        (1.914602 - 0.004817 * centuries - 0.000014 * centuries**2)
        * np.sin(anomaly_rad)
        + (0.019993 - 0.000101 * centuries) * np.sin(2.0 * anomaly_rad)
        + 0.000289 * np.sin(3.0 * anomaly_rad)
    )
    true_longitude = mean_longitude + equation_center
    omega = 125.04 - 1934.136 * centuries
    apparent_longitude = true_longitude - 0.00569 - 0.00478 * np.sin(np.deg2rad(omega))
    obliquity = 23.439291 - 0.0130042 * centuries + 0.00256 * np.cos(np.deg2rad(omega))
    apparent_rad = np.deg2rad(apparent_longitude)
    obliquity_rad = np.deg2rad(obliquity)
    right_ascension = np.mod(
        np.rad2deg(
            np.arctan2(np.cos(obliquity_rad) * np.sin(apparent_rad), np.cos(apparent_rad))
        ),
        360.0,
    )
    declination = np.rad2deg(
        np.arcsin(np.sin(obliquity_rad) * np.sin(apparent_rad))
    )
    return right_ascension, declination


def _gmst_deg(unix_seconds: np.ndarray) -> np.ndarray:
    julian_date = unix_seconds / 86400.0 + 2440587.5
    centuries = (julian_date - 2451545.0) / 36525.0
    return np.mod(
        280.46061837
        + 360.98564736629 * (julian_date - 2451545.0)
        + 0.000387933 * centuries**2
        - centuries**3 / 38710000.0,
        360.0,
    )


def propagate_sso(
    *,
    start_utc: str,
    altitude_km: float,
    ltan_hours: float,
    duration_hours: float,
    phase_step_deg: float,
) -> OrbitSamples:
    """Propagate continuously; the final requested time is always included."""
    if duration_hours < 0:
        raise ValueError("传播时间不能为负。")
    radius_m = EARTH_MEAN_RADIUS_M + 1000.0 * altitude_km
    mean_motion = math.sqrt(EARTH_MU_M3_S2 / radius_m**3)
    target_rate = math.radians(360.0 / TROPICAL_YEAR_DAYS) / 86400.0
    inclination = sso_inclination_deg(altitude_km)
    phase_step_seconds = math.radians(phase_step_deg) / mean_motion
    duration_seconds = duration_hours * 3600.0
    if duration_seconds == 0:
        elapsed = np.array([0.0])
    else:
        count = int(math.floor(duration_seconds / phase_step_seconds))
        elapsed = np.arange(count + 1, dtype=float) * phase_step_seconds
        if elapsed[-1] < duration_seconds - 1e-9:
            elapsed = np.append(elapsed, duration_seconds)
        else:
            elapsed[-1] = duration_seconds

    epoch_unix = _unix_seconds(start_utc)
    unix = epoch_unix + elapsed
    utc = np.rint(unix).astype("int64").astype("datetime64[s]")
    phase_unwrapped = np.rad2deg(mean_motion * elapsed)
    phase = np.mod(phase_unwrapped, 360.0)

    sun_ra0, _ = _sun_ra_dec(np.array([epoch_unix]))
    raan0 = np.mod(sun_ra0[0] + 15.0 * (ltan_hours - 12.0), 360.0)
    raan_unwrapped = raan0 + np.rad2deg(target_rate * elapsed)
    raan = np.mod(raan_unwrapped, 360.0)
    sun_ra, sun_dec = _sun_ra_dec(unix)
    sun_ra_rad = np.deg2rad(sun_ra)
    sun_dec_rad = np.deg2rad(sun_dec)
    sun = np.column_stack(
        (
            np.cos(sun_dec_rad) * np.cos(sun_ra_rad),
            np.cos(sun_dec_rad) * np.sin(sun_ra_rad),
            np.sin(sun_dec_rad),
        )
    )

    u = np.deg2rad(phase)
    omega = np.deg2rad(raan_unwrapped)
    inc = math.radians(inclination)
    x = radius_m * (np.cos(omega) * np.cos(u) - np.sin(omega) * np.sin(u) * math.cos(inc))
    y = radius_m * (np.sin(omega) * np.cos(u) + np.cos(omega) * np.sin(u) * math.cos(inc))
    z = radius_m * np.sin(u) * math.sin(inc)
    vx = radius_m * mean_motion * (
        -np.cos(omega) * np.sin(u) - np.sin(omega) * np.cos(u) * math.cos(inc)
    )
    vy = radius_m * mean_motion * (
        -np.sin(omega) * np.sin(u) + np.cos(omega) * np.cos(u) * math.cos(inc)
    )
    vz = radius_m * mean_motion * np.cos(u) * math.sin(inc)
    speed = np.sqrt(vx**2 + vy**2 + vz**2)

    gmst = np.deg2rad(_gmst_deg(unix))
    x_ecef = np.cos(gmst) * x + np.sin(gmst) * y
    y_ecef = -np.sin(gmst) * x + np.cos(gmst) * y
    latitude = np.rad2deg(np.arcsin(z / radius_m))
    longitude = np.mod(np.rad2deg(np.arctan2(y_ecef, x_ecef)) + 180.0, 360.0) - 180.0
    normal = np.column_stack(
        (
            math.sin(inc) * np.sin(omega),
            -math.sin(inc) * np.cos(omega),
            np.full(elapsed.size, math.cos(inc)),
        )
    )
    beta = np.rad2deg(np.arcsin(np.clip(np.sum(normal * sun, axis=1), -1.0, 1.0)))
    projection = np.abs(np.sum(np.column_stack((vx, vy, vz)) * sun, axis=1) / speed)
    current_ltan = np.mod(12.0 + (raan_unwrapped - sun_ra) / 15.0, 24.0)

    return OrbitSamples(
        elapsed_seconds=elapsed,
        utc=utc,
        phase_deg=phase,
        phase_unwrapped_deg=phase_unwrapped,
        altitude_km=np.full(elapsed.size, altitude_km),
        inclination_deg=inclination,
        nodal_rate_deg_day=math.degrees(target_rate) * 86400.0,
        latitude_deg=latitude,
        longitude_deg=longitude,
        raan_deg=raan,
        current_ltan_hours=current_ltan,
        beta_deg=beta,
        speed_m_s=speed,
        solar_projection_factor=projection,
    )


def propagate_single_revolution(
    *, start_utc: str, altitude_km: float, ltan_hours: float, phase_step_deg: float
) -> OrbitSamples:
    return propagate_sso(
        start_utc=start_utc,
        altitude_km=altitude_km,
        ltan_hours=ltan_hours,
        duration_hours=orbital_period_seconds(altitude_km) / 3600.0,
        phase_step_deg=phase_step_deg,
    )
