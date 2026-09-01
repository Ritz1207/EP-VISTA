# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""End-to-end EP-VISTA study pipeline."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from .atmosphere import evaluate_nrlmsis2
from .cache import _file_sha256, load_demand_cache, save_demand_cache
from .budgets import evaluate_power, build_mass_breakdowns
from .models import DemandProfile, ProjectCase, ThrusterRecord, TradeStudyResult
from .orbit import propagate_single_revolution, propagate_sso
from .propulsion import (
    evaluate_candidate,
    load_thruster_library,
    conclusion_text,
)
from .weather import fixed_activity_weather, load_historical_weather
from .paths import project_root


ProgressCallback = Callable[[int, str], None]
CancelCheck = Callable[[], bool]


def default_thruster_library_path() -> Path:
    return project_root() / "data" / "thrusters" / "thrusters.csv"


def _weather_for(project: ProjectCase, orbit):
    if project.atmosphere.mode == "historical":
        weather_path = Path(project.atmosphere.weather_file or "")
        if not weather_path.is_absolute():
            weather_path = project_root() / weather_path
        return load_historical_weather(weather_path, orbit.utc)
    return fixed_activity_weather(project.atmosphere.fixed_activity or "", orbit.utc.size)


def _demand_from_orbit(
    project: ProjectCase,
    orbit,
    cancel_check: CancelCheck | None = None,
    atmosphere_progress: Callable[[int, int], None] | None = None,
) -> DemandProfile:
    weather = _weather_for(project, orbit)
    atmosphere = evaluate_nrlmsis2(
        orbit,
        weather,
        project.sampling.batch_rows,
        cancel_check=cancel_check,
        progress=atmosphere_progress,
    )
    solar_area = project.power.resolved_solar_array_area_m2()
    solar_frontal_area = solar_area * orbit.solar_projection_factor
    effective_area = project.spacecraft.body_frontal_area_m2 + solar_frontal_area
    dynamic_pressure = 0.5 * atmosphere.mass_density_kg_m3 * orbit.speed_m_s**2
    drag_mN = 1000.0 * dynamic_pressure * (
        project.spacecraft.drag_coefficient * project.spacecraft.body_frontal_area_m2
        + project.spacecraft.solar_array_drag_coefficient * solar_frontal_area
    )
    total_impulse = float(np.trapezoid(drag_mN * 1e-3, orbit.elapsed_seconds))
    return DemandProfile(
        orbit=orbit,
        atmosphere=atmosphere,
        solar_array_area_m2=solar_area,
        solar_frontal_area_m2=solar_frontal_area,
        effective_frontal_area_m2=effective_area,
        drag_mN=drag_mN,
        total_impulse_N_s=total_impulse,
        intake_area_m2=project.spacecraft.body_frontal_area_m2,
    )


def run_case(
    project: ProjectCase,
    candidates: list[ThrusterRecord] | None = None,
    progress: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> TradeStudyResult:
    project = deepcopy(project)
    if candidates is None:
        candidates = ([ThrusterRecord(**item) for item in project.library_snapshot]
                      if project.library_snapshot is not None
                      else load_thruster_library(default_thruster_library_path()))
        if project.library_snapshot is None:
            custom_ids = {item["thruster_id"] for item in project.custom_thrusters}
            candidates = [item for item in candidates if item.thruster_id not in custom_ids]
            project.library_snapshot = [asdict(item) for item in candidates]
        candidates.extend(ThrusterRecord(**item) for item in project.custom_thrusters)
    candidates = deepcopy(candidates)
    if project.selected_thruster_ids:
        selected = set(project.selected_thruster_ids)
        candidates = [item for item in candidates if item.thruster_id in selected]
        missing = selected - {item.thruster_id for item in candidates}
        if missing:
            raise ValueError(f"未找到候选方案：{', '.join(sorted(missing))}")
    if not candidates:
        raise ValueError("请至少选择一个候选推进方案。")
    ids = [item.thruster_id for item in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("本项目存在重复推进器ID，请先消除型号库与自定义方案的冲突。")
    # Freeze exact inputs, including explicit arguments, without dropping the
    # project's unselected records (users can select them in a later run).
    frozen = {item["thruster_id"]: item for item in (project.library_snapshot or [])}
    custom = {item["thruster_id"]: item for item in project.custom_thrusters}
    for item in candidates:
        if item.thruster_id in custom:
            custom[item.thruster_id] = asdict(item)
        else:
            frozen[item.thruster_id] = asdict(item)
    project.library_snapshot = list(frozen.values())
    project.custom_thrusters = list(custom.values())
    project.validate([item.thruster_id for item in candidates])
    power_assessment = evaluate_power(project)
    weather_path = None
    if project.atmosphere.mode == "historical":
        weather_path = Path(project.atmosphere.weather_file)
        if not weather_path.is_absolute():
            weather_path = project_root() / weather_path
    library_path = default_thruster_library_path()
    source_snapshot = {
        "weather_file": str(weather_path) if weather_path is not None else None,
        "weather_sha256": _file_sha256(weather_path) if weather_path is not None else None,
        "thruster_library": str(library_path),
        "thruster_library_sha256": _file_sha256(library_path) if library_path.is_file() else None,
        "candidate_parameter_basis": "project_snapshot",
        "thruster_library_role": "current reference only; actual inputs are in candidate_snapshot",
    }
    notify = progress or (lambda _value, _message: None)
    cancelled = cancel_check or (lambda: False)
    if cancelled():
        raise RuntimeError("计算已取消。")
    duration = float(project.mission.design_life_hours)
    cached = load_demand_cache(project, project_root())
    if cached is None:
        notify(5, "生成连续SSO轨道")
        mission_orbit = propagate_sso(
            start_utc=project.mission.start_utc,
            altitude_km=project.mission.altitude_km,
            ltan_hours=project.mission.ltan_hours,
            duration_hours=duration,
            phase_step_deg=project.sampling.phase_step_deg,
        )
        if cancelled():
            raise RuntimeError("计算已取消。")
        notify(20, "匹配空间天气并计算NRLMSIS 2.0")

        def mission_atmosphere_progress(completed: int, total: int) -> None:
            fraction = completed / max(total, 1)
            notify(
                20 + int(round(43 * fraction)),
                f"NRLMSIS 2.0：{completed:,}/{total:,}个任务采样点",
            )

        demand = _demand_from_orbit(
            project,
            mission_orbit,
            cancelled,
            atmosphere_progress=mission_atmosphere_progress,
        )
        notify(65, "计算绕地一周内的阻力变化")
        single_orbit = propagate_single_revolution(
            start_utc=project.mission.start_utc,
            altitude_km=project.mission.altitude_km,
            ltan_hours=project.mission.ltan_hours,
            phase_step_deg=project.sampling.phase_step_deg,
        )
        def revolution_atmosphere_progress(completed: int, total: int) -> None:
            fraction = completed / max(total, 1)
            notify(
                65 + int(round(7 * fraction)),
                f"起始时刻绕地一周：{completed:,}/{total:,}个采样点",
            )

        single_demand = _demand_from_orbit(
            project,
            single_orbit,
            cancelled,
            atmosphere_progress=revolution_atmosphere_progress,
        )
        if cancelled():
            raise RuntimeError("计算已取消。")
        if weather_path is not None and _file_sha256(weather_path) != source_snapshot["weather_sha256"]:
            raise RuntimeError("计算期间空间天气文件已修改，请重新运行以保持数据一致。")
        notify(73, "保存轨道与大气缓存")
        save_demand_cache(project, project_root(), demand, single_demand)
    else:
        notify(73, "使用已缓存的轨道、大气和阻力结果")
        demand, single_demand = cached
    if cancelled():
        raise RuntimeError("计算已取消。")
    if weather_path is not None and _file_sha256(weather_path) != source_snapshot["weather_sha256"]:
        raise RuntimeError("计算期间空间天气文件已修改，请重新运行以保持数据一致。")
    notify(78, "比较推进方案")
    assessments = [
        evaluate_candidate(
            demand,
            candidate,
            project.power.propulsion_power_kW,
        )
        for candidate in candidates
    ]
    if power_assessment["status"] == "供电功率不足":
        assessments = [replace(
            item,
            propulsion_status=item.status,
            status="供电功率不足" if item.status != "数据有误，未参与比较" else item.status,
            reason=f"供电缺口{power_assessment['power_shortfall_kW']:.3g} kW；以下仅为指定功率下的理论推进结果。" + item.reason,
        ) for item in assessments]
    mass_breakdowns = build_mass_breakdowns(project, power_assessment, assessments)
    notify(95, "汇总任务判断")
    conclusion = conclusion_text(assessments)
    notify(100, "计算完成")
    return TradeStudyResult(
        project=project,
        demand=demand,
        single_revolution=single_demand,
        assessments=assessments,
        conclusion=conclusion,
        power_assessment=power_assessment,
        mass_breakdowns=mass_breakdowns,
        candidate_snapshot=candidates,
        source_snapshot=source_snapshot,
    )
