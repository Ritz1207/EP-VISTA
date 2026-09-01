# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Versioned data contracts used by both the calculation core and GUI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np

from .paths import migrate_legacy_weather_path
from .orbit_statistics import ASSESSMENT_BASIS


SCHEMA_VERSION = "2.3"
G0_M_S2 = 9.80665


@dataclass(slots=True)
class MissionConfig:
    start_utc: str
    design_life_hours: float | None
    altitude_km: float
    ltan_hours: float


@dataclass(slots=True)
class SpacecraftConfig:
    # Legacy total mass is retained only as an import reference, never split.
    mass_kg: float | None = None
    body_frontal_area_m2: float = 2.0
    drag_coefficient: float = 2.2
    solar_array_drag_coefficient: float = 2.2
    structure_mass_kg: float | None = None
    payload_mass_kg: float | None = None


@dataclass(slots=True)
class PowerConfig:
    total_power_kW: float
    propulsion_power_kW: float
    solar_array_mode: str = "auto_size"
    solar_array_specific_power_W_m2: float = 300.0
    solar_array_area_m2: float | None = None
    supply_mode: str = "solar"
    solar_array_specific_power_W_kg: float | None = None
    battery_usable_specific_energy_kWh_kg: float | None = None
    battery_max_power_kW: float | None = None

    def resolved_solar_array_area_m2(self) -> float:
        if self.solar_array_mode == "auto_size" and self.supply_mode == "solar":
            return self.total_power_kW * 1000.0 / self.solar_array_specific_power_W_m2
        if self.solar_array_area_m2 is None:
            raise ValueError("固定太阳翼模式必须输入太阳翼面积。")
        return float(self.solar_array_area_m2)


@dataclass(slots=True)
class AtmosphereConfig:
    mode: str = "historical"
    weather_file: str | None = None
    fixed_activity: str | None = None


@dataclass(slots=True)
class SamplingConfig:
    phase_step_deg: float = 5.0
    batch_rows: int = 250_000


@dataclass(slots=True)
class StructureMassInput:
    mass_kg: float | None = None
    source: str = "用户输入"
    notes: str = "不含推进剂；配套部件计入范围由用户确认。"


def default_structure_masses() -> dict[str, StructureMassInput]:
    return {item["thruster_id"]: ThrusterRecord(**item).structure_mass_input()
            for item in default_library_snapshot()
            if item["structure_mass_kg"] is not None or item["structure_mass_source"] or item["structure_mass_notes"]}


def default_library_snapshot() -> list[dict[str, Any]]:
    # Lazy import avoids a data-contract / CSV-reader import cycle.
    from .library import default_library_path, load_thruster_library
    return [asdict(item) for item in load_thruster_library(default_library_path())]


def default_project_library_snapshot(custom_thrusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only fill missing library inputs; never duplicate a project's own record."""
    custom_ids = {item["thruster_id"] for item in custom_thrusters}
    return [item for item in default_library_snapshot() if item["thruster_id"] not in custom_ids]


@dataclass(slots=True)
class ProjectCase:
    name: str
    mission: MissionConfig
    spacecraft: SpacecraftConfig
    power: PowerConfig
    atmosphere: AtmosphereConfig
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    selected_thruster_ids: list[str] = field(default_factory=list)
    custom_thrusters: list[dict[str, Any]] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    propulsion_structure: dict[str, StructureMassInput] = field(default_factory=default_structure_masses)
    library_snapshot: list[dict[str, Any]] | None = None

    def validate(self, candidate_ids: list[str] | None = None) -> None:
        errors: list[str] = []

        def number(value, label, *, zero=False):
            if value is None:
                errors.append(f"请补齐{label}。")
            elif not isinstance(value, (int, float)) or not np.isfinite(value) or (value < 0 if zero else value <= 0):
                errors.append(f"{label}必须为有限{'非负数' if zero else '正数'}。")
        try:
            parsed = datetime.fromisoformat(self.mission.start_utc.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                errors.append("起始UTC必须包含时区，例如2025-03-20T00:00:00Z。")
        except ValueError:
            errors.append("起始UTC格式无效。")
        if self.mission.design_life_hours is None:
            errors.append("任务设计寿命为必填项。")
        elif self.mission.design_life_hours <= 0:
            errors.append("任务设计寿命必须大于0小时。")
        elif not np.isfinite(self.mission.design_life_hours):
            errors.append("任务设计寿命必须为有限值。")
        if not 150 <= self.mission.altitude_km <= 300:
            errors.append("V1仅支持150–300 km太阳同步圆轨道。")
        if not 0 <= self.mission.ltan_hours < 24:
            errors.append("LTAN必须位于0–24小时范围内。")
        number(self.spacecraft.structure_mass_kg, "卫星结构质量 (kg)", zero=True)
        number(self.spacecraft.payload_mass_kg, "其他载荷质量 (kg)", zero=True)
        for candidate_id in candidate_ids if candidate_ids is not None else self.selected_thruster_ids:
            item = self.propulsion_structure.get(candidate_id, StructureMassInput())
            number(item.mass_kg, f"候选方案{candidate_id}的结构质量 (kg)", zero=True)
        number(self.spacecraft.body_frontal_area_m2, "本体迎风面积 (m²)")
        number(self.spacecraft.drag_coefficient, "本体阻力系数")
        number(self.spacecraft.solar_array_drag_coefficient, "太阳翼阻力系数")
        number(self.power.total_power_kW, "整星功率 (kW)")
        number(self.power.propulsion_power_kW, "电推进可用功率 (kW)")
        if self.spacecraft.body_frontal_area_m2 <= 0:
            errors.append("本体迎风面积必须大于0 m²。")
        if self.spacecraft.drag_coefficient <= 0:
            errors.append("阻力系数必须大于0。")
        if self.power.total_power_kW <= 0 or self.power.propulsion_power_kW <= 0:
            errors.append("整星功率和电推进可用功率必须大于0 kW。")
        if self.power.propulsion_power_kW > self.power.total_power_kW:
            errors.append("电推进可用功率不能大于整星功率。")
        if self.power.solar_array_specific_power_W_m2 <= 0:
            errors.append("太阳翼比功率必须大于0 W/m²。")
        number(self.power.solar_array_specific_power_W_m2, "太阳翼单位面积功率 (W/m²)")
        if self.power.supply_mode not in {"solar", "battery"}:
            errors.append("供电方式必须为solar或battery。")
        if self.power.supply_mode == "battery" and self.power.solar_array_mode != "fixed_hardware":
            errors.append("电池供电方式必须使用固定硬件太阳翼面积。")
        if self.power.solar_array_mode not in {"auto_size", "fixed_hardware"}:
            errors.append("太阳翼模式必须为auto_size或fixed_hardware。")
        if self.power.solar_array_mode == "fixed_hardware":
            number(self.power.solar_array_area_m2, "固定太阳翼面积 (m²)", zero=self.power.supply_mode == "battery")
        try:
            area = self.power.resolved_solar_array_area_m2()
            if area > 0:
                number(self.power.solar_array_specific_power_W_kg, "太阳翼系统比功率 (W/kg)")
            if self.power.supply_mode == "battery":
                for value, label, zero in (
                    (self.power.battery_usable_specific_energy_kWh_kg, "电池系统级可用比能量 (kWh/kg)", False),
                    (self.power.battery_max_power_kW, "电池持续输出功率上限 (kW)", True),
                ):
                    deficit = self.power.total_power_kW - area * self.power.solar_array_specific_power_W_m2 / 1000
                    if deficit > 1e-12 or value is not None:
                        number(value, label, zero=zero)
        except (ValueError, ZeroDivisionError, TypeError):
            pass  # Invalid geometry is reported above.
        if self.atmosphere.mode not in {"historical", "fixed_activity"}:
            errors.append("空间天气模式必须为historical或fixed_activity。")
        if self.atmosphere.mode == "historical" and not self.atmosphere.weather_file:
            errors.append("历史空间天气模式必须指定CSV文件。")
        if self.atmosphere.mode == "fixed_activity" and self.atmosphere.fixed_activity not in {
            "low", "nominal", "high"
        }:
            errors.append("固定活动情景必须为low、nominal或high。")
        if not 0 < self.sampling.phase_step_deg <= 30:
            errors.append("轨道位置步长必须位于0–30°。")
        if errors:
            raise ValueError("\n".join(errors))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        if self.library_snapshot is None:
            self.library_snapshot = default_project_library_snapshot(self.custom_thrusters)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProjectCase":
        from .library import validate_library
        raw_custom = value.get("custom_thrusters", [])
        if not isinstance(raw_custom, list):
            raise ValueError("项目自定义方案必须是列表。")
        custom_thrusters = [asdict(ThrusterRecord(**item)) for item in raw_custom]
        if custom_thrusters:
            validate_library([ThrusterRecord(**item) for item in custom_thrusters])
        snapshot = value.get("library_snapshot")
        if snapshot is None:
            # Legacy projects had IDs only: freeze today's library in memory.
            # Reading does not rewrite their original files.
            snapshot = default_project_library_snapshot(custom_thrusters)
        else:
            if not isinstance(snapshot, list):
                raise ValueError("项目型号库快照必须是列表。")
            if snapshot:
                records = [ThrusterRecord(**item) for item in snapshot]
                validate_library(records)
                snapshot = [asdict(item) for item in records]
        return cls(
            name=value["name"],
            mission=MissionConfig(**value["mission"]),
            spacecraft=SpacecraftConfig(**value["spacecraft"]),
            power=PowerConfig(**value["power"]),
            atmosphere=AtmosphereConfig(**{
                **value["atmosphere"],
                "weather_file": migrate_legacy_weather_path(value["atmosphere"].get("weather_file")),
            }),
            sampling=SamplingConfig(**value.get("sampling", {})),
            selected_thruster_ids=list(value.get("selected_thruster_ids", [])),
            custom_thrusters=custom_thrusters,
            # Retired ranking settings in old project JSON are intentionally ignored.
            schema_version=SCHEMA_VERSION,
            propulsion_structure={key: StructureMassInput(**item) for key, item in value["propulsion_structure"].items()}
            if "propulsion_structure" in value else {
                item["thruster_id"]: ThrusterRecord(**item).structure_mass_input()
                for item in snapshot
                if item.get("structure_mass_kg") is not None
                or item.get("structure_mass_source") or item.get("structure_mass_notes")
            },
            library_snapshot=deepcopy(snapshot),
        )

    @classmethod
    def load(cls, path: str | Path) -> "ProjectCase":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(slots=True)
class ThrusterRecord:
    thruster_id: str
    name_zh: str
    architecture: str
    propellant: str
    thrust_to_power_mN_kW: float
    isp_s: float
    thruster_type: str = "其他"
    minimum_power_kW: float = 0.0
    maximum_power_kW: float | None = None
    intake_efficiency: float | None = None
    power_basis: str = "engineering design input"
    data_type: str = "engineering_design_case"
    metric_coincidence: str = "same_design_point"
    source: str = ""
    locator: str = ""
    verification_status: str = "pending_human_verification"
    notes: str = ""
    structure_mass_kg: float | None = None
    structure_mass_source: str = "用户输入"
    structure_mass_notes: str = "不含推进剂；配套部件计入范围由用户确认。"

    def structure_mass_input(self) -> StructureMassInput:
        return StructureMassInput(self.structure_mass_kg, self.structure_mass_source,
                                  self.structure_mass_notes)

    @property
    def implied_efficiency(self) -> float:
        thrust_per_power_N_W = self.thrust_to_power_mN_kW * 1e-6
        return thrust_per_power_N_W * self.isp_s * G0_M_S2 / 2.0

    def validate(self) -> None:
        if not self.thruster_type.strip():
            raise ValueError(f"{self.name_zh}的推进器类型不能为空。")
        if self.thruster_type != self.thruster_type.strip():
            raise ValueError(f"{self.name_zh}的推进器类型首尾不能包含空白。")
        if self.architecture not in {"traditional", "abep"}:
            raise ValueError(f"{self.name_zh}的推进方式无效。")
        if self.thrust_to_power_mN_kW <= 0 or self.isp_s <= 0:
            raise ValueError(f"{self.name_zh}的推功比和比冲必须大于0。")
        if not 0 < self.implied_efficiency <= 1:
            raise ValueError(
                f"{self.name_zh}由推功比和比冲计算的效率为"
                f"{self.implied_efficiency:.3f}，参数不一致。"
            )
        if self.architecture == "abep" and (
            self.intake_efficiency is None or not 0 < self.intake_efficiency <= 1
        ):
            raise ValueError(f"{self.name_zh}必须提供0–1范围内的集气效率。")


@dataclass(slots=True)
class OrbitSamples:
    elapsed_seconds: np.ndarray
    utc: np.ndarray
    phase_deg: np.ndarray
    phase_unwrapped_deg: np.ndarray
    altitude_km: np.ndarray
    inclination_deg: float
    nodal_rate_deg_day: float
    latitude_deg: np.ndarray
    longitude_deg: np.ndarray
    raan_deg: np.ndarray
    current_ltan_hours: np.ndarray
    beta_deg: np.ndarray
    speed_m_s: np.ndarray
    solar_projection_factor: np.ndarray


@dataclass(slots=True)
class AtmosphereSamples:
    mass_density_kg_m3: np.ndarray
    n_N2_m3: np.ndarray
    n_O2_m3: np.ndarray
    n_O_m3: np.ndarray
    n_He_m3: np.ndarray
    n_H_m3: np.ndarray
    n_Ar_m3: np.ndarray
    n_N_m3: np.ndarray
    n_anomalous_O_m3: np.ndarray
    temperature_K: np.ndarray


@dataclass(slots=True)
class DemandProfile:
    orbit: OrbitSamples
    atmosphere: AtmosphereSamples
    solar_array_area_m2: float
    solar_frontal_area_m2: np.ndarray
    effective_frontal_area_m2: np.ndarray
    drag_mN: np.ndarray
    total_impulse_N_s: float
    intake_area_m2: float

    @property
    def mean_drag_mN(self) -> float:
        duration_s = float(self.orbit.elapsed_seconds[-1] - self.orbit.elapsed_seconds[0])
        if duration_s <= 0:
            return float(np.mean(self.drag_mN))
        return float(np.trapezoid(self.drag_mN, self.orbit.elapsed_seconds) / duration_s)

    @property
    def maximum_drag_mN(self) -> float:
        return float(np.max(self.drag_mN))


@dataclass(slots=True)
class CandidateAssessment:
    thruster_id: str
    name_zh: str
    architecture: str
    status: str
    reason: str
    operating_power_kW: float | None
    required_power_kW: float | None
    available_thrust_mN: float | None
    limiting_thrust_margin_mN: float | None
    propellant_kg: float | None
    required_total_impulse_N_s: float
    implied_efficiency: float | None
    verification_status: str
    propulsion_status: str | None = None
    assessment_basis: str = ASSESSMENT_BASIS
    maximum_orbit_mean_drag_mN: float | None = None
    minimum_orbit_mean_thrust_margin_mN: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TradeStudyResult:
    project: ProjectCase
    demand: DemandProfile
    single_revolution: DemandProfile
    assessments: list[CandidateAssessment]
    conclusion: str
    generated_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    power_assessment: dict[str, Any] = field(default_factory=dict)
    mass_breakdowns: list[dict[str, Any]] = field(default_factory=list)
    candidate_snapshot: list[ThrusterRecord] = field(default_factory=list)
    source_snapshot: dict[str, Any] = field(default_factory=dict)

    def summary_dict(self) -> dict[str, Any]:
        orbit = self.demand.orbit
        density = self.demand.atmosphere.mass_density_kg_m3
        return {
            "schema_version": self.project.schema_version,
            "generated_at_utc": self.generated_at_utc,
            "project_name": self.project.name,
            "start_utc": self.project.mission.start_utc,
            "design_life_hours": self.project.mission.design_life_hours,
            "altitude_km": self.project.mission.altitude_km,
            "ltan_hours": self.project.mission.ltan_hours,
            "sso_inclination_deg": orbit.inclination_deg,
            "orbital_period_min": float(360.0 / (orbit.phase_unwrapped_deg[1] / orbit.elapsed_seconds[1]) / 60.0)
            if len(orbit.elapsed_seconds) > 1
            else None,
            "density_min_kg_m3": float(np.min(density)),
            "density_mean_kg_m3": float(
                np.trapezoid(density, orbit.elapsed_seconds)
                / (orbit.elapsed_seconds[-1] - orbit.elapsed_seconds[0])
            )
            if orbit.elapsed_seconds[-1] > orbit.elapsed_seconds[0]
            else float(np.mean(density)),
            "density_max_kg_m3": float(np.max(density)),
            "mean_drag_mN": self.demand.mean_drag_mN,
            "maximum_drag_mN": self.demand.maximum_drag_mN,
            "total_impulse_N_s": self.demand.total_impulse_N_s,
            "solar_array_area_m2": self.demand.solar_array_area_m2,
            "conclusion": self.conclusion,
            "assessment_basis": ASSESSMENT_BASIS,
            "assessments": [item.to_dict() for item in self.assessments],
            "power_assessment": self.power_assessment,
            "mass_breakdowns": self.mass_breakdowns,
        }
