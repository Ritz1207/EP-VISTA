# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Candidate validation and task assessment, with no candidate ranking."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .models import CandidateAssessment, DemandProfile, G0_M_S2, ThrusterRecord
from .orbit_statistics import OrbitReducer, ASSESSMENT_NOTE
from .library import load_thruster_library as _load_unified_library


def load_thruster_library(path: str | Path) -> list[ThrusterRecord]:
    return _load_unified_library(path)


def available_thrust_profile(
    demand: DemandProfile,
    candidate: ThrusterRecord,
    propulsion_power_kW: float,
) -> tuple[np.ndarray, float, float]:
    """Return available thrust history, power-only ceiling and operating power."""
    operating_power = propulsion_power_kW
    if candidate.maximum_power_kW is not None:
        operating_power = min(operating_power, candidate.maximum_power_kW)
    power_thrust_mN = operating_power * candidate.thrust_to_power_mN_kW
    if operating_power + 1e-12 < candidate.minimum_power_kW:
        return np.zeros_like(demand.drag_mN), power_thrust_mN, operating_power
    if candidate.architecture == "traditional":
        return (
            np.full_like(demand.drag_mN, power_thrust_mN),
            power_thrust_mN,
            operating_power,
        )
    intake_efficiency = float(candidate.intake_efficiency)
    captured_mass_flow = (
        intake_efficiency
        * demand.atmosphere.mass_density_kg_m3
        * demand.orbit.speed_m_s
        * demand.intake_area_m2
    )
    intake_thrust_mN = captured_mass_flow * candidate.isp_s * G0_M_S2 * 1000.0
    return (
        np.minimum(power_thrust_mN, intake_thrust_mN),
        power_thrust_mN,
        operating_power,
    )


def evaluate_candidate(
    demand: DemandProfile,
    candidate: ThrusterRecord,
    propulsion_power_kW: float,
) -> CandidateAssessment:
    try:
        candidate.validate()
    except ValueError as exc:
        return CandidateAssessment(
            thruster_id=candidate.thruster_id,
            name_zh=candidate.name_zh,
            architecture=candidate.architecture,
            status="数据有误，未参与比较",
            reason=str(exc),
            operating_power_kW=None,
            required_power_kW=None,
            available_thrust_mN=None,
            limiting_thrust_margin_mN=None,
            propellant_kg=None,
            required_total_impulse_N_s=demand.total_impulse_N_s,
            implied_efficiency=None,
            verification_status=candidate.verification_status,
        )

    available_series, power_thrust_mN, operating_power = available_thrust_profile(
        demand,
        candidate,
        propulsion_power_kW,
    )
    reducer = OrbitReducer(demand.orbit.elapsed_seconds, demand.orbit.phase_unwrapped_deg)
    mean_drag = reducer.reduce(demand.drag_mN).mean
    mean_thrust = reducer.reduce(available_series).mean
    max_mean_drag = float(np.max(mean_drag))
    required_power = max_mean_drag / candidate.thrust_to_power_mN_kW
    mean_margin = float(np.min(mean_thrust - mean_drag))
    drag = np.maximum(demand.drag_mN, np.finfo(float).tiny)

    if operating_power + 1e-12 < candidate.minimum_power_kW:
        status = "推力不足"
        reason = (
            f"可用电推进功率{propulsion_power_kW:.3g} kW低于该方案的"
            f"最小工作功率{candidate.minimum_power_kW:.3g} kW。"
        )
    elif candidate.architecture == "traditional":
        status = "满足任务" if mean_margin > 0 else "推力不足"
        reason = (
            "每圈可用推力均大于该圈平均整星阻力，满足平均补偿判据。"
            if status == "满足任务"
            else f"各圈平均阻力的最大值为{max_mean_drag:.3g} mN，可用推力{power_thrust_mN:.3g} mN未超过该值。"
        )
    else:
        if mean_margin > 0:
            status = "满足任务"
            reason = "每圈平均实际可用推力均大于对应平均整星阻力，满足平均补偿判据。"
        elif np.any((mean_thrust <= mean_drag) & (power_thrust_mN > mean_drag)):
            status = "进气量不足"
            reason = "至少一圈功率推力足够，但经进气限制后的平均实际推力未超过该圈平均阻力。"
        else:
            status = "推力不足"
            reason = f"功率推力上限{power_thrust_mN:.3g} mN未超过各圈平均阻力最大值{max_mean_drag:.3g} mN；仍需同时核对进气能力。"

    limiting_margin = float(np.min(available_series - drag))
    propellant = (
        demand.total_impulse_N_s / (candidate.isp_s * G0_M_S2)
        if candidate.architecture == "traditional"
        else 0.0
    )
    return CandidateAssessment(
        thruster_id=candidate.thruster_id,
        name_zh=candidate.name_zh,
        architecture=candidate.architecture,
        status=status,
        reason=reason,
        operating_power_kW=float(operating_power),
        required_power_kW=float(required_power),
        available_thrust_mN=float(np.min(available_series)),
        limiting_thrust_margin_mN=limiting_margin,
        propellant_kg=float(propellant),
        required_total_impulse_N_s=demand.total_impulse_N_s,
        implied_efficiency=candidate.implied_efficiency,
        verification_status=candidate.verification_status,
        maximum_orbit_mean_drag_mN=max_mean_drag,
        minimum_orbit_mean_thrust_margin_mN=mean_margin,
    )


def conclusion_text(assessments: list[CandidateAssessment]) -> str:
    """Summarize task checks without ranking or recommending candidates."""
    if not assessments:
        return "尚无候选方案可供判断。"
    total = len(assessments)
    passed = sum(item.status == "满足任务" for item in assessments)
    text = (
        f"共比较{total}个候选方案，其中{passed}个满足每圈平均补偿及供电等任务判据。"
        "各方案按候选列表顺序展示。" + ASSESSMENT_NOTE
    )
    if any(item.verification_status != "human_verified" for item in assessments):
        text += "部分方案的性能证据尚未人工核验。"
    text += "设备寿命能力仍需单独核验。"
    return text
