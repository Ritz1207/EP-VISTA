# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Ideal continuous power sizing and per-candidate initial mass accounting."""

from .models import ProjectCase


POWER_BOUNDARY = (
    "恒定整星负载、理想连续太阳翼发电；电池按受输出上限约束后的补充功率持续供电至任务结束配置。"
    "配置电量及质量为方案估算，并非已知实物电池容量；供电不足时不视为满足整星需求。"
    "不含食期、充电循环、退化及额外设计余量。比能量为系统级可用值。"
)


def evaluate_power(project: ProjectCase) -> dict:
    power = project.power
    solar_kW = power.resolved_solar_array_area_m2() * power.solar_array_specific_power_W_m2 / 1000
    deficit = max(power.total_power_kW - solar_kW, 0.0)
    if deficit < 1e-12:
        deficit = 0.0
    battery = power.supply_mode == "battery"
    required = deficit if battery else 0.0
    duration = float(project.mission.design_life_hours)
    required_energy = required * duration
    solar_mass = 1000 * solar_kW / power.solar_array_specific_power_W_kg if solar_kW > 0 else 0.0
    battery_max = float(power.battery_max_power_kW or 0) if battery else 0.0
    supplied = min(required, battery_max)
    configured_energy = supplied * duration
    battery_mass = configured_energy / power.battery_usable_specific_energy_kWh_kg if configured_energy > 0 else 0.0
    gap = max(deficit - supplied, 0.0)
    return {
        "battery_sizing_basis": "supply_limited_duration_v1",
        "supply_mode": power.supply_mode,
        "status": "供电功率足够" if gap <= 1e-12 else "供电功率不足",
        "solar_power_kW": solar_kW,
        "total_power_kW": power.total_power_kW,
        "battery_required_power_kW": required,
        "battery_max_power_kW": battery_max,
        "battery_supply_power_kW": supplied,
        "supply_total_power_kW": solar_kW + supplied,
        "power_shortfall_kW": gap,
        "battery_required_energy_kWh": required_energy,
        "battery_configured_energy_kWh": configured_energy,
        "battery_equivalent_full_power_hours": configured_energy / power.total_power_kW,
        "battery_mass_kg": battery_mass,
        "solar_array_mass_kg": solar_mass,
        "notes": POWER_BOUNDARY,
    }


def power_summary_text(power: dict) -> str:
    """User-visible assessment for the desktop result view."""
    text = f"当前供电系统总功率为{power['supply_total_power_kW']:.6g} kW，"
    if power["power_shortfall_kW"] > 1e-12:
        return text + (f"未满足整星{power['total_power_kW']:.6g} kW的功率需求，"
                       f"缺口{power['power_shortfall_kW']:.6g} kW。")
    return text + f"满足整星{power['total_power_kW']:.6g} kW的功率需求。"


def build_mass_breakdowns(project: ProjectCase, power: dict, assessments) -> list[dict]:
    rows = []
    for assessment in assessments:
        entry = project.propulsion_structure[assessment.thruster_id]
        components = {
            "satellite_structure_mass_kg": project.spacecraft.structure_mass_kg,
            "solar_array_mass_kg": power["solar_array_mass_kg"],
            "battery_mass_kg": power["battery_mass_kg"],
            "propulsion_structure_mass_kg": entry.mass_kg,
            "propellant_mass_kg": assessment.propellant_kg,
            "payload_mass_kg": project.spacecraft.payload_mass_kg,
        }
        known = all(value is not None for value in components.values())
        notes = [entry.notes, "质量按输入口径合计；非完整系统质量核验。"]
        if any(value == 0 for key, value in components.items() if key in {
            "satellite_structure_mass_kg", "propulsion_structure_mass_kg", "payload_mass_kg"
        }):
            notes.append("用户明确填写为零的结构/载荷组成：未计入。")
        if assessment.status != "满足任务":
            notes.append("条件性理论估算：该方案尚不能满足任务。")
        rows.append({
            "thruster_id": assessment.thruster_id,
            "name_zh": assessment.name_zh,
            **components,
            "initial_total_mass_kg": sum(components.values()) if known else None,
            "total_impulse_N_s": assessment.required_total_impulse_N_s,
            "mass_source": entry.source,
            "status": assessment.status,
            "notes": " ".join(notes),
        })
    return rows
