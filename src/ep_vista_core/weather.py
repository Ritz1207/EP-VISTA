# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Offline space-weather loading and exact three-hour matching."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np


AP_COLUMNS = (
    "ap_daily",
    "ap_current_3h",
    "ap_3h_prior",
    "ap_6h_prior",
    "ap_9h_prior",
    "ap_mean_12_33h",
    "ap_mean_36_57h",
)

FIXED_ACTIVITY = {
    "low": (70.0, 70.0, 4.0),
    "nominal": (150.0, 150.0, 15.0),
    "high": (220.0, 220.0, 50.0),
}


@dataclass(slots=True)
class WeatherInputs:
    f107_daily: np.ndarray
    f107_81day: np.ndarray
    ap7: np.ndarray
    warning_count: int
    source_label: str


def _parse_utc(text: str) -> int:
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return int(parsed.astimezone(timezone.utc).timestamp())


def historical_weather_coverage(path: str | Path) -> tuple[datetime, datetime]:
    """Return first covered UTC and the exclusive end of the final 3 h bin."""
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("空间天气CSV没有数据。")
    if "utc" not in rows[0]:
        raise ValueError("空间天气CSV缺少utc列。")
    first = datetime.fromtimestamp(_parse_utc(rows[0]["utc"]), timezone.utc)
    last = datetime.fromtimestamp(_parse_utc(rows[-1]["utc"]), timezone.utc)
    if last < first:
        raise ValueError("空间天气CSV的UTC顺序无效。")
    return first, last + timedelta(hours=3)


def historical_task_start_window(
    path: str | Path,
    design_life_hours: float,
) -> tuple[datetime, datetime]:
    """Return first allowed start and exclusive latest start for a task."""
    first, coverage_end_exclusive = historical_weather_coverage(path)
    return first, coverage_end_exclusive - timedelta(hours=design_life_hours)


def validate_historical_task_window(
    path: str | Path,
    start_utc: str,
    design_life_hours: float,
) -> None:
    start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    if start.tzinfo is None:
        raise ValueError("起始UTC必须包含时区。")
    start = start.astimezone(timezone.utc)
    first, latest_start_exclusive = historical_task_start_window(
        path,
        design_life_hours,
    )
    if latest_start_exclusive <= first:
        raise ValueError("任务设计寿命不短于历史空间天气文件的有效覆盖时长。")
    if start < first or start >= latest_start_exclusive:
        latest_inclusive = latest_start_exclusive - timedelta(seconds=1)
        raise ValueError(
            "当前历史CSV与任务设计寿命允许的起始UTC范围为"
            f"{first.isoformat().replace('+00:00', 'Z')}至"
            f"{latest_inclusive.isoformat().replace('+00:00', 'Z')}。"
        )


def load_historical_weather(path: str | Path, sample_utc: np.ndarray) -> WeatherInputs:
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("空间天气CSV没有数据。")
    required = {
        "utc",
        "f107_previous_day_sfu",
        "f107_centered_81day_sfu",
        "interpolated_or_predicted",
        *AP_COLUMNS,
    }
    missing = required.difference(rows[0])
    if missing:
        raise ValueError(f"空间天气CSV缺少列：{', '.join(sorted(missing))}")
    source_unix = np.asarray([_parse_utc(row["utc"]) for row in rows], dtype=np.int64)
    if source_unix.size > 1 and not np.all(np.diff(source_unix) == 10800):
        raise ValueError("空间天气CSV必须是严格连续的3小时序列。")
    sample_unix = sample_utc.astype("datetime64[s]").astype(np.int64)
    bins = sample_unix - np.mod(sample_unix, 10800)
    locations = ((bins - source_unix[0]) // 10800).astype(np.int64)
    valid = (locations >= 0) & (locations < source_unix.size)
    if np.any(valid):
        valid[valid] &= source_unix[locations[valid]] == bins[valid]
    if not np.all(valid):
        missing_unix = int(bins[np.flatnonzero(~valid)[0]])
        missing_utc = datetime.fromtimestamp(missing_unix, timezone.utc).isoformat()
        raise ValueError(f"历史空间天气未覆盖{missing_utc}。请导入覆盖完整任务的CSV。")
    f107 = np.asarray([float(row["f107_previous_day_sfu"]) for row in rows])
    f107a = np.asarray([float(row["f107_centered_81day_sfu"]) for row in rows])
    ap_source = np.asarray([[float(row[name]) for name in AP_COLUMNS] for row in rows])
    warnings = np.asarray([int(float(row["interpolated_or_predicted"])) for row in rows])
    unique_locations = np.unique(locations)
    return WeatherInputs(
        f107_daily=f107[locations],
        f107_81day=f107a[locations],
        ap7=ap_source[locations, :],
        warning_count=int(np.sum(warnings[unique_locations] != 0)),
        source_label=str(source_path),
    )


def fixed_activity_weather(activity: str, count: int) -> WeatherInputs:
    if activity not in FIXED_ACTIVITY:
        raise ValueError("固定活动情景必须为low、nominal或high。")
    f107, f107a, ap = FIXED_ACTIVITY[activity]
    return WeatherInputs(
        f107_daily=np.full(count, f107),
        f107_81day=np.full(count, f107a),
        ap7=np.full((count, 7), ap),
        warning_count=0,
        source_label=f"fixed_activity:{activity}",
    )
