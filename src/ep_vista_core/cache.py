# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Local, clearable cache for orbit-atmosphere-drag results."""

from __future__ import annotations

from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import pickle

from .models import DemandProfile, ProjectCase


CACHE_FORMAT = "ep-vista-demand-v3"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def demand_cache_key(project: ProjectCase, root: Path) -> str:
    sampling = asdict(project.sampling)
    # Batch size controls responsiveness and memory use, not physical sampling.
    # Excluding it allows GUI progress tuning to reuse the same numerical cache.
    sampling.pop("batch_rows", None)
    payload = {
        "format": CACHE_FORMAT,
        "mission": asdict(project.mission),
        "geometry": {
            "body_frontal_area_m2": project.spacecraft.body_frontal_area_m2,
            "drag_coefficient": project.spacecraft.drag_coefficient,
            "solar_array_drag_coefficient": project.spacecraft.solar_array_drag_coefficient,
            "solar_array_area_m2": project.power.resolved_solar_array_area_m2(),
        },
        "atmosphere": asdict(project.atmosphere),
        "sampling": sampling,
    }
    if project.atmosphere.weather_file:
        weather = Path(project.atmosphere.weather_file)
        if not weather.is_absolute():
            weather = root / weather
        payload["weather_sha256"] = _file_sha256(weather)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_demand_cache(
    project: ProjectCase, root: Path
) -> tuple[DemandProfile, DemandProfile] | None:
    key = demand_cache_key(project, root)
    path = root / "workspace" / "cache" / "orbit_atmosphere" / f"{key}.pkl.gz"
    if not path.is_file():
        return None
    try:
        with gzip.open(path, "rb") as stream:
            format_name, mission, single = pickle.load(stream)
        if format_name != CACHE_FORMAT:
            return None
        return mission, single
    except (OSError, EOFError, pickle.PickleError, AttributeError, ValueError):
        path.unlink(missing_ok=True)
        return None


def save_demand_cache(
    project: ProjectCase,
    root: Path,
    mission: DemandProfile,
    single: DemandProfile,
) -> Path:
    key = demand_cache_key(project, root)
    directory = root / "workspace" / "cache" / "orbit_atmosphere"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}.pkl.gz"
    temporary = directory / f"{key}.tmp"
    with gzip.open(temporary, "wb", compresslevel=3) as stream:
        pickle.dump((CACHE_FORMAT, mission, single), stream, protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(path)
    return path
