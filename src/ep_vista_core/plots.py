# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Matplotlib figures used by the desktop result views."""

from __future__ import annotations

import numpy as np
import matplotlib as mpl
from matplotlib.figure import Figure

from .models import TradeStudyResult, ThrusterRecord
from .propulsion import available_thrust_profile
from .orbit_statistics import OrbitReducer


INK = "#172033"
BLUE = "#2457C5"
GOLD = "#D79B16"
ORANGE = "#E66B2E"
OLIVE = "#738B2E"
PINK = "#C45C8C"
GREEN = "#2E8B57"
GREEN_BAND = "#9BC7AA"
GRID = "#D9DEE8"
NEUTRAL = "#6B7280"
PALETTE = [BLUE, GOLD, ORANGE, OLIVE, PINK]

# Keep Chinese labels readable in desktop plots.
mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False


def _figure(width: float = 8.0, height: float = 4.8) -> Figure:
    fig = Figure(figsize=(width, height), dpi=110, facecolor="white")
    return fig


def _style_axis(ax) -> None:
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.75)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(NEUTRAL)
    ax.spines["bottom"].set_color(NEUTRAL)
    ax.tick_params(colors=INK, labelsize=9)


def _format_ltan(hours: float) -> str:
    total_minutes = int(round(hours * 60.0)) % (24 * 60)
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _candidate_label(name: str) -> str:
    if "（推功比" in name:
        return (
            name.replace("（推功比", "\n推功比 ")
            .replace("，比冲", "；比冲 ")
            .removesuffix("）")
        )
    return name


def mission_drag_thrust_figure(
    result: TradeStudyResult,
    candidates: list[ThrusterRecord],
) -> Figure:
    """Full-mission drag history and selected candidates' available thrust."""
    fig = _figure(9.4, 5.5)
    ax = fig.add_subplot(111)
    time_hours = result.demand.orbit.elapsed_seconds / 3600.0
    reducer = OrbitReducer(time_hours, result.demand.orbit.phase_unwrapped_deg)
    drag_stats = reducer.reduce(result.demand.drag_mN)
    orbit_time = drag_stats.time
    ax.fill_between(
        orbit_time,
        drag_stats.minimum,
        drag_stats.maximum,
        color=GREEN_BAND,
        alpha=0.38,
        linewidth=0,
        label="整星阻力范围",
        zorder=2,
    )
    ax.plot(
        orbit_time,
        drag_stats.mean,
        color=GREEN,
        linestyle="--",
        linewidth=1.65,
        label="整星平均阻力",
        marker="o" if orbit_time.size == 1 else None,
        zorder=3,
    )

    selected = set(result.project.selected_thruster_ids)
    shown = [item for item in candidates if not selected or item.thruster_id in selected]
    for index, candidate in enumerate(shown):
        try:
            candidate.validate()
        except ValueError:
            continue
        color = PALETTE[index % len(PALETTE)]
        available, _power_ceiling, _ = available_thrust_profile(
            result.demand,
            candidate,
            result.project.power.propulsion_power_kW,
        )
        label = candidate.name_zh
        if candidate.architecture == "traditional":
            ax.axhline(
                float(available[0]),
                color=color,
                linestyle="-",
                linewidth=1.6,
                label=label,
            )
        else:
            thrust_stats = reducer.reduce(available)
            ax.fill_between(
                thrust_stats.time,
                thrust_stats.minimum,
                thrust_stats.maximum,
                color=color,
                alpha=0.16,
                linewidth=0,
                label=f"{label}推力范围",
                zorder=2,
            )
            ax.plot(
                thrust_stats.time,
                thrust_stats.mean,
                color=color,
                linestyle="-",
                linewidth=1.55,
                label=f"{label}平均推力",
                marker="o" if orbit_time.size == 1 else None,
            )

    ax.set_xlim(float(time_hours[0]), float(time_hours[-1]))
    ax.set_ylim(bottom=0)
    ax.set_xlabel("任务时间 (h)")
    ax.set_ylabel("阻力与推力 (mN)")
    handles, labels = ax.get_legend_handles_labels()
    legend_columns = min(4, max(1, len(labels)))
    legend_rows = (len(labels) + legend_columns - 1) // legend_columns
    # Each ABEP candidate adds both a line and a band entry. Reserve enough
    # header space without shrinking the force plot as the legend grows.
    fig.set_figheight(5.5 + 0.22 * max(0, legend_rows - 3))
    plot_top = min(0.64, 0.81 - (0.2 * legend_rows + 0.15) / fig.get_figheight())
    fig.legend(
        handles,
        labels,
        frameon=False,
        fontsize=6.8,
        ncol=legend_columns,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.81),
        columnspacing=1.4,
        handlelength=2.5,
    )
    _style_axis(ax)
    fig.suptitle(
        "任务期间逐圈整星阻力与候选推进方案可用推力",
        color=INK,
        fontsize=10.5,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.91,
        f"{result.project.mission.altitude_km:g} km SSO，LTAN {_format_ltan(result.project.mission.ltan_hours)}；"
        f"起始UTC {result.project.mission.start_utc}；任务时长{result.project.mission.design_life_hours:g} h",
        ha="center",
        fontsize=7.8,
        color=NEUTRAL,
    )
    fig.text(
        0.5,
        0.865,
        "所谓平均是指：按圈时间平均，末尾不足一圈按实际时段计入",
        ha="center",
        fontsize=7.8,
        color=NEUTRAL,
    )
    fig.subplots_adjust(left=0.085, right=0.985, bottom=0.12, top=plot_top)
    return fig


def single_revolution_area_figure(result: TradeStudyResult) -> Figure:
    profile = result.single_revolution
    fig = _figure()
    ax = fig.add_subplot(111)
    ax.plot(profile.orbit.phase_unwrapped_deg, profile.solar_frontal_area_m2, color=BLUE, linewidth=2)
    ax.set_xlabel("轨道位置 (°)")
    ax.set_ylabel("太阳翼迎风面积 (m²)")
    ax.set_xlim(0, 360)
    _style_axis(ax)
    fig.suptitle("卫星绕地一周内的太阳翼迎风面积变化", color=INK, fontsize=11, fontweight="bold")
    ax.set_title(
        f"固定起始UTC {result.project.mission.start_utc}；总太阳翼面积 {profile.solar_array_area_m2:.2f} m²",
        fontsize=8,
        color=NEUTRAL,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    return fig


def single_revolution_drag_figure(result: TradeStudyResult) -> Figure:
    profile = result.single_revolution
    fig = _figure()
    ax = fig.add_subplot(111)
    ax.plot(profile.orbit.phase_unwrapped_deg, profile.drag_mN, color=BLUE, linewidth=2)
    ax.axhline(profile.mean_drag_mN, color=GOLD, linestyle="--", linewidth=1.5, label=f"平均 {profile.mean_drag_mN:.2f} mN")
    ax.scatter([profile.orbit.phase_unwrapped_deg[np.argmax(profile.drag_mN)]], [profile.maximum_drag_mN], color=ORANGE, s=36, zorder=3, label=f"最大 {profile.maximum_drag_mN:.2f} mN")
    ax.set_xlabel("轨道位置 (°)")
    ax.set_ylabel("阻力 (mN)")
    ax.set_xlim(0, 360)
    ax.legend(frameon=False, loc="best")
    _style_axis(ax)
    fig.suptitle("卫星绕地一周内的阻力变化", color=INK, fontsize=11, fontweight="bold")
    ax.set_title(
        f"{result.project.mission.altitude_km:g} km SSO，LTAN {_format_ltan(result.project.mission.ltan_hours)}；不是高度扫描",
        fontsize=8,
        color=NEUTRAL,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    return fig
