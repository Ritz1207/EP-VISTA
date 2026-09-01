# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Main desktop workflow: inputs, demand, candidates and sensitivity."""

from __future__ import annotations

from dataclasses import asdict
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import shutil
from threading import Event
import traceback

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
    QStyleOptionViewItem,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ep_vista_core.budgets import power_summary_text
from ep_vista_core.models import (
    AtmosphereConfig,
    MissionConfig,
    PowerConfig,
    ProjectCase,
    SamplingConfig,
    SpacecraftConfig,
    StructureMassInput,
    ThrusterRecord,
)
from ep_vista_core.plots import (
    mission_drag_thrust_figure,
    single_revolution_area_figure,
    single_revolution_drag_figure,
)
from ep_vista_core.propulsion import load_thruster_library
from ep_vista_core.sensitivity import run_altitude_sweep
from ep_vista_core.study import default_thruster_library_path, project_root, run_case
from ep_vista_core.weather import (
    historical_task_start_window,
    validate_historical_task_window,
)

from .dialogs import ThrusterDialog
from .library_panel import LibraryPanel
from .window_chrome import GlassMainWindow


STYLE = """
QWidget { background:transparent; color:#25334D; font-family:'Microsoft YaHei'; font-size:10pt; }
QMainWindow, QDialog { background:#EEF2FB; }
QMainWindow#glassWindow { background:transparent; }
QLabel#brandTitle { color:#293F83; font-size:19pt; font-weight:700; }
QLabel#brandMark { color:#4F55E7; font-size:27pt; font-weight:800; padding:0 12px 0 0; }
QFrame#glassToolbar { background:rgba(255,255,255,155); border:1px solid rgba(255,255,255,245); border-radius:14px; }
QGroupBox { background:rgba(255,255,255,168); border:1px solid rgba(255,255,255,240); border-radius:17px; margin-top:14px; padding:12px; padding-top:16px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:16px; padding:0 7px; color:#293F70; }
QLineEdit, QDoubleSpinBox, QComboBox { background:rgba(255,255,255,192); border:1px solid #D6DDF0; border-radius:9px; padding:7px 9px; min-height:20px; selection-background-color:#DCE5FF; selection-color:#233657; }
QLineEdit:hover, QDoubleSpinBox:hover, QComboBox:hover { border-color:#B1BBE5; }
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus { background:rgba(255,255,255,240); border:1px solid #787DE8; }
QLineEdit:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    background:rgba(227,232,244,155); color:#929CB0; border-color:#DFE4EF;
}
QLabel:disabled { color:#929CB0; }
QComboBox QAbstractItemView { background:#FCFDFF; color:#25334D; border:1px solid #D2D9EF; selection-background-color:#E6EAFE; selection-color:#364AB5; }
QComboBox::drop-down { border:0; width:25px; }
QComboBox::down-arrow, QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow { image:none; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { border:0; background:transparent; width:24px; }
QPushButton { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3768EF,stop:1 #8A61E8); color:white; border:1px solid rgba(255,255,255,170); border-radius:10px; padding:9px 16px; font-weight:600; }
QPushButton:hover { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4C79F2,stop:1 #9B76ED); }
QPushButton:pressed { background:#5056D6; }
QPushButton:focus { border:2px solid #ADB8F4; padding:8px 15px; }
QPushButton:disabled { background:#D9DFED; color:#8691A7; border-color:#E9EDF6; }
QPushButton#secondary { background:rgba(255,255,255,175); color:#40528A; border:1px solid rgba(255,255,255,250); }
QPushButton#secondary:hover { background:rgba(238,240,255,235); border-color:#C3CCF1; }
QPushButton#secondary:disabled { background:rgba(232,237,247,180); color:#929CB0; border-color:#E6EAF3; }
QTabWidget::pane { border:1px solid rgba(255,255,255,240); border-radius:14px; background:rgba(255,255,255,145); top:0; }
QTabBar::tab { background:rgba(246,248,255,140); color:#64718D; border:1px solid rgba(255,255,255,190); border-top-left-radius:11px; border-top-right-radius:11px; padding:10px 15px; margin-right:4px; }
QTabBar::tab:hover { background:rgba(255,255,255,210); color:#4B59B4; }
QTabBar::tab:selected { background:rgba(255,255,255,235); color:#4555D4; border-bottom:2px solid #7776E8; font-weight:600; }
QTableWidget { background:rgba(255,255,255,188); alternate-background-color:rgba(235,240,253,135); border:1px solid rgba(255,255,255,240); border-radius:10px; gridline-color:#E2E7F2; selection-background-color:#E3E9FF; selection-color:#263A72; }
QTableWidget::item { padding:5px; }
QTableWidget::item:selected { background:#E3E9FF; color:#263A72; }
QHeaderView::section { background:rgba(233,239,253,225); color:#40517B; padding:8px; border:none; border-bottom:1px solid #DDE4F3; font-weight:600; }
QTableCornerButton::section { background:#EDF1FB; border:0; }
QProgressBar { border:1px solid rgba(255,255,255,240); border-radius:8px; background:rgba(218,225,244,145); text-align:center; color:#263861; min-height:20px; }
QProgressBar::chunk { border-radius:7px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #A8C5FF,stop:1 #C6B5F2); }
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical { background:rgba(232,237,249,130); width:11px; margin:2px; border-radius:5px; }
QScrollBar:horizontal { background:rgba(232,237,249,130); height:11px; margin:2px; border-radius:5px; }
QScrollBar::handle { background:#B9C6E2; border-radius:4px; min-height:30px; min-width:30px; }
QScrollBar::handle:hover { background:#909EC7; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; width:0; }
QScrollBar::add-page, QScrollBar::sub-page { background:transparent; }
QToolTip { background:#FCFDFF; color:#293C60; border:1px solid #CDD8ED; padding:7px; }
"""


class GlassSurface(QWidget):
    """App-local soft backdrop, without blurring text or reading the desktop."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0, QColor("#EDF5FF"))
        base.setColorAt(0.50, QColor("#F5F6FD"))
        base.setColorAt(1, QColor("#EEEAFB"))
        painter.fillRect(self.rect(), base)
        for x, y, size, color in (
            (0.05, 0.15, 0.70, QColor(139, 184, 253, 90)),
            (0.93, 0.18, 0.52, QColor(182, 152, 241, 75)),
            (0.65, 1.02, 0.62, QColor(166, 188, 244, 70)),
        ):
            halo = QRadialGradient(QPointF(w * x, h * y), max(w, h) * size)
            halo.setColorAt(0, color)
            halo.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillRect(self.rect(), halo)
        # Restrained orbit-like highlights sit behind the glass, never on data.
        painter.setPen(QPen(QColor(255, 255, 255, 115), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(w * 0.48, -h * 0.63, w * 0.92, h * 0.89))
        painter.drawEllipse(QRectF(-w * 0.48, h * 0.63, w * 1.08, h * 0.67))
        painter.end()


def _glass_shadow(widget: QWidget) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(24)
    effect.setOffset(0, 5)
    effect.setColor(QColor(75, 90, 153, 24))
    widget.setGraphicsEffect(effect)


def _paint_chevron(painter: QPainter, rect, enabled: bool, up: bool = False) -> None:
    center = QRectF(rect).center()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#647697" if enabled else "#A9B2C5"), 1.4))
    path = QPainterPath()
    direction = -1 if up else 1
    path.moveTo(center.x() - 3.5, center.y() - direction * 1.5)
    path.lineTo(center.x(), center.y() + direction * 1.5)
    path.lineTo(center.x() + 3.5, center.y() - direction * 1.5)
    painter.drawPath(path)


class GlassComboBox(QComboBox):
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        rect = self.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxArrow, self)
        painter = QPainter(self)
        _paint_chevron(painter, rect, self.isEnabled())
        painter.end()


class MetricCardGroup(QWidget):
    """Five related metrics: one row when wide, a readable 3+2 when narrow."""

    def __init__(self, specs):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.labels = {}
        self.cards = []
        self.columns = 0
        for key, caption_text in specs:
            card = QFrame()
            card.setObjectName("metricCard")
            card.setStyleSheet("QFrame#metricCard{background:rgba(255,255,255,170);border:1px solid white;border-radius:16px;padding:10px}")
            _glass_shadow(card)
            box = QVBoxLayout(card)
            value = QLabel("—")
            value.setMinimumWidth(0)
            value.setStyleSheet("color:#4E58B8;border:none;font-size:20pt;font-weight:700")
            value.setWordWrap(True)
            caption = QLabel(caption_text)
            caption.setStyleSheet("color:#6B7280;border:none")
            caption.setWordWrap(True)
            box.addWidget(value)
            box.addWidget(caption)
            self.labels[key] = value
            self.cards.append(card)
        self._reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self):
        # Hysteresis avoids scrollbar-induced oscillation at the breakpoint.
        threshold = 1080 if self.columns == 5 else 1120
        columns = 5 if self.width() >= threshold else 3
        if columns == self.columns:
            return
        self.columns = columns
        for card in self.cards:
            self.grid.removeWidget(card)
        for column in range(5):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)
        self.updateGeometry()


class GlassDoubleSpinBox(QDoubleSpinBox):
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        painter = QPainter(self)
        for control, up in ((QStyle.SC_SpinBoxUp, True), (QStyle.SC_SpinBoxDown, False)):
            rect = self.style().subControlRect(QStyle.CC_SpinBox, option, control, self)
            _paint_chevron(painter, rect, self.isEnabled(), up)
        painter.end()


class GlassCheckDelegate(QStyledItemDelegate):
    """Keep normal Qt checkbox hit-testing and keyboard handling, paint only."""

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        checked = index.data(Qt.CheckStateRole)
        if checked is None:
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style() if opt.widget else QApplication.style()
        rect = style.subElementRect(QStyle.SE_ItemViewItemCheckIndicator, opt, opt.widget)
        painter.save()
        painter.fillRect(rect, QColor("#F6F8FF"))
        painter.setRenderHint(QPainter.Antialiasing)
        active = checked == Qt.Checked.value
        painter.setPen(QPen(QColor("#6866DE" if active else "#B7C3DD"), 1))
        painter.setBrush(QColor("#6866DE" if active else "#FFFFFF"))
        box = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(box, 3, 3)
        if active:
            path = QPainterPath()
            path.moveTo(box.left() + box.width() * 0.22, box.center().y())
            path.lineTo(box.left() + box.width() * 0.43, box.top() + box.height() * 0.72)
            path.lineTo(box.left() + box.width() * 0.80, box.top() + box.height() * 0.28)
            painter.setPen(QPen(QColor("white"), 1.6))
            painter.drawPath(path)
        painter.restore()


class StudyWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)
    cancelled = Signal()

    def __init__(self, project: ProjectCase, candidates: list[ThrusterRecord]) -> None:
        super().__init__()
        self.project = project
        self.candidates = candidates
        self.cancel_event = Event()

    def request_cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            result = run_case(
                self.project,
                self.candidates,
                progress=lambda value, message: self.progress.emit(value, message),
                cancel_check=self.cancel_event.is_set,
            )
            self.finished.emit(result)
        except RuntimeError as exc:
            if str(exc) == "计算已取消。":
                self.cancelled.emit()
            else:
                self.failed.emit(traceback.format_exc())
        except Exception:
            self.failed.emit(traceback.format_exc())


class SensitivityWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)
    cancelled = Signal()

    def __init__(self, project, candidate, minimum, maximum, step) -> None:
        super().__init__()
        self.args = (project, candidate, minimum, maximum, step)
        self.cancel_event = Event()

    def request_cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(
                run_altitude_sweep(
                    *self.args,
                    progress=lambda value, message: self.progress.emit(value, message),
                    cancel_check=self.cancel_event.is_set,
                )
            )
        except RuntimeError as exc:
            if str(exc) == "计算已取消。":
                self.cancelled.emit()
            else:
                self.failed.emit(traceback.format_exc())
        except Exception:
            self.failed.emit(traceback.format_exc())


class HoverCanvas(FigureCanvas):
    def __init__(self, figure, result=None) -> None:
        super().__init__(figure)
        self.result = result
        self.annotation = None
        if result is not None and figure.axes:
            ax = figure.axes[0]
            self.annotation = ax.annotate(
                "", xy=(0, 0), xytext=(14, 14), textcoords="offset points",
                bbox={"boxstyle": "round", "fc": "white", "ec": "#8A96A8", "alpha": 0.96},
                fontsize=8,
            )
            self.annotation.set_visible(False)
            self.mpl_connect("motion_notify_event", self._hover)

    def _hover(self, event) -> None:
        if self.result is None or self.annotation is None or event.inaxes is None or event.xdata is None:
            return
        profile = self.result.single_revolution
        index = int(abs(profile.orbit.phase_unwrapped_deg - event.xdata).argmin())
        self.annotation.xy = (profile.orbit.phase_unwrapped_deg[index], profile.drag_mN[index])
        utc = str(profile.orbit.utc[index]) + "Z"
        self.annotation.set_text(
            f"UTC {utc}\n纬度 {profile.orbit.latitude_deg[index]:.2f}°  经度 {profile.orbit.longitude_deg[index]:.2f}°\n"
            f"密度 {profile.atmosphere.mass_density_kg_m3[index]:.3e} kg/m³\n"
            f"太阳翼迎风面积 {profile.solar_frontal_area_m2[index]:.2f} m²\n阻力 {profile.drag_mN[index]:.2f} mN"
        )
        self.annotation.set_visible(True)
        self.draw_idle()


class MissionTimeWindow(QWidget):
    """Keep plot furniture fixed while a scrollbar moves the visible time span."""

    def __init__(self, figure) -> None:
        super().__init__()
        self.figure = figure
        self.canvas = FigureCanvas(figure)
        self.canvas.setMinimumHeight(max(420, round(figure.get_figheight() * figure.dpi)))
        self.axis = figure.axes[0]
        self.full_start, self.full_end = map(float, self.axis.get_xlim())
        full_span = max(0.0, self.full_end - self.full_start)
        self.window_span = min(full_span, max(168.0, full_span * 0.1))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas, 1)
        controls = QHBoxLayout()
        self.range_label = QLabel("")
        self.range_label.setStyleSheet("color:#6B7280")
        self.scrollbar = QScrollBar(Qt.Horizontal)
        self.scrollbar.setRange(0, 1000)
        self.scrollbar.setPageStep(100)
        self.scrollbar.valueChanged.connect(self._update_window)
        controls.addWidget(QLabel("任务时间窗口"))
        controls.addWidget(self.scrollbar, 1)
        controls.addWidget(self.range_label)
        layout.addLayout(controls)

        if full_span <= self.window_span or full_span <= 0:
            self.scrollbar.setEnabled(False)
        self._update_window(0)

    def _update_window(self, value: int) -> None:
        movable_span = max(0.0, self.full_end - self.full_start - self.window_span)
        start = self.full_start + movable_span * value / max(1, self.scrollbar.maximum())
        end = min(self.full_end, start + self.window_span)
        self.axis.set_xlim(start, end)
        self.range_label.setText(f"{start:g}–{end:g} h")
        self.canvas.draw_idle()


class ResultsWindow(GlassMainWindow):
    """A non-modal, independently resizable window; closing only hides it."""

    def closeEvent(self, event) -> None:
        self.hide()
        event.ignore()


class MainWindow(GlassMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # Fusion keeps native indicators (checks/arrows) legible underneath the
        # light stylesheet, including offscreen and high-DPI Qt rendering.
        app = QApplication.instance()
        if app is not None and app.style().objectName().lower() != "fusion":
            app.setStyle("Fusion")
        self.setWindowTitle("EP-VISTA — 项目设置")
        self.resize(1250, 940)
        self.setStyleSheet(STYLE)
        self.library: list[ThrusterRecord] = []
        self.custom_thrusters: list[ThrusterRecord] = []
        self.result = None
        self.structure_inputs: dict[str, StructureMassInput] = {}
        self._mass_invalid = {}
        self._applying = True
        self._input_revision = 0
        self._running_revision = 0
        self._closing = False
        self._legacy_mass_kg = None
        self._sampling = SamplingConfig()
        self._solar_mode_before_battery = "auto_size"
        self.worker_thread: QThread | None = None
        self.study_worker: StudyWorker | None = None
        self.sensitivity_worker: SensitivityWorker | None = None
        self._fixed_solar_area_value = 33.333
        self._last_solar_mode: str | None = None
        self._active_scan_accuracy_label = ""
        self._active_scan_phase_step_deg = 5.0
        self._build_ui()
        self._connect_dirty_signals()
        self._load_template()
        self._applying = False

    def _build_ui(self) -> None:
        root = GlassSurface()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        brand_row = QHBoxLayout()
        mark = QLabel("EP-VISTA · V1.0")
        mark.setObjectName("brandMark")
        brand_row.addWidget(mark)
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel("项目设置")
        title.setObjectName("brandTitle")
        title_box.addWidget(title)
        brand_row.addLayout(title_box, 1)
        layout.addLayout(brand_row)
        toolbar = QFrame()
        toolbar.setObjectName("glassToolbar")
        header = QHBoxLayout(toolbar)
        header.setContentsMargins(12, 8, 12, 8)
        hint = QLabel(
            "超低轨道电推进系统方案权衡分析平台\n"
            "Electric Propulsion for VLEO Integrated System Trade Analysis"
        )
        hint.setStyleSheet("color:#5E6F93;font-size:9pt")
        hint.setWordWrap(True)
        header.addWidget(hint, 1)
        for text, handler in (("打开项目", self.open_project), ("保存项目", self.save_project)):
            button = QPushButton(text)
            button.setObjectName("secondary")
            button.clicked.connect(handler)
            header.addWidget(button)
        cache_button = QPushButton("清理缓存")
        cache_button.setObjectName("secondary")
        cache_button.clicked.connect(self.clear_cache)
        header.addWidget(cache_button)
        self.view_results_button = QPushButton("查看结果")
        self.view_results_button.setEnabled(False)
        self.view_results_button.clicked.connect(self.show_results)
        header.addWidget(self.view_results_button)
        layout.addWidget(toolbar)
        _glass_shadow(toolbar)

        self.input_panel = self._build_input_panel()
        layout.addWidget(self.input_panel, 1)
        action_layout = QHBoxLayout()
        action_layout.addWidget(self.run_button)
        action_layout.addWidget(self.cancel_button)
        action_layout.addWidget(self.progress, 1)
        layout.addLayout(action_layout)
        layout.addWidget(self.progress_label)
        self.footer_label = self._footer_notice()
        layout.addWidget(self.footer_label)
        self.set_content_widget(root)
        self.results_window = ResultsWindow(self, Qt.Window)
        self.results_window.setWindowTitle("EP-VISTA — 分析结果")
        self.results_window.resize(1400, 900)
        self.results_window.setStyleSheet(STYLE)
        results_root = GlassSurface()
        results_layout = QVBoxLayout(results_root)
        results_layout.setContentsMargins(16, 12, 16, 12)
        results_layout.setSpacing(10)
        results_toolbar = QFrame()
        results_toolbar.setObjectName("glassToolbar")
        result_toolbar = QHBoxLayout(results_toolbar)
        result_toolbar.setContentsMargins(14, 8, 14, 8)
        results_mark = QLabel("EP-VISTA · V1.0")
        results_mark.setObjectName("brandMark")
        result_toolbar.addWidget(results_mark)
        self.snapshot_label = QLabel("等待计算结果")
        self.snapshot_label.setWordWrap(True)
        self.snapshot_label.setStyleSheet("color:#5B6A87;font-size:9pt")
        result_toolbar.addWidget(self.snapshot_label, 1)
        results_layout.addWidget(results_toolbar)
        _glass_shadow(results_toolbar)
        self.tabs = QTabWidget()
        self.overview_tab = self._build_overview_tab()
        self.orbit_tab = QTabWidget()
        self.mission_tab = QScrollArea()
        self.mission_tab.setWidgetResizable(True)
        self.sensitivity_tab = self._build_sensitivity_tab()
        self.tabs.addTab(self.mission_tab, "任务全程推阻关系")
        self.tabs.addTab(self.orbit_tab, "绕地一周")
        self.tabs.addTab(self._scroll_page(self.sensitivity_tab, 820), "高度扫描")
        self.conclusion_scroll = self._scroll_page(self.overview_tab, 820)
        self.tabs.addTab(self.conclusion_scroll, "结论")
        results_layout.addWidget(self.tabs, 1)
        self.results_footer_label = self._footer_notice()
        results_layout.addWidget(self.results_footer_label)
        self.results_window.set_content_widget(results_root)
        self._build_library_window()
        for group in self.input_panel.findChildren(QGroupBox):
            _glass_shadow(group)
        for table in (self.candidate_table, self.result_table):
            table.setAlternatingRowColors(True)
            table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
            table.verticalHeader().setDefaultSectionSize(36)

    @staticmethod
    def _footer_notice() -> QLabel:
        label = QLabel(
            "Copyright © 2026 Ritz · "
            "分析结果仅供参考，请结合模型假设与数据适用范围核验。"
        )
        label.setObjectName("footerNotice")
        label.setTextFormat(Qt.PlainText)
        label.setStyleSheet("color:#6D7890;font-size:8pt;font-weight:normal")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _scroll_page(widget: QWidget, minimum_width: int) -> QScrollArea:
        widget.setMinimumWidth(minimum_width)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def _build_input_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        panel = QWidget()
        panel.setMinimumWidth(1020)
        layout = QGridLayout(panel)
        layout.setContentsMargins(10, 4, 10, 12)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(12)
        layout.setAlignment(Qt.AlignTop)
        mission = QGroupBox("任务与SSO轨道")
        form = QFormLayout(mission)
        self.name_edit = QLineEdit()
        self.start_edit = QLineEdit()
        self.start_edit.setPlaceholderText("例如 2025-03-20T00:00:00Z")
        self.life_edit = QLineEdit()
        self.life_edit.setPlaceholderText("必填，不设置默认值")
        self.weather_coverage_label = QLabel("")
        self.weather_coverage_label.setWordWrap(True)
        self.weather_coverage_label.setStyleSheet("color:#6B7280;font-size:9pt")
        life_box = QVBoxLayout()
        life_box.setContentsMargins(0, 0, 0, 0)
        life_box.setSpacing(3)
        life_box.addWidget(self.life_edit)
        life_box.addWidget(self.weather_coverage_label)
        self.altitude_spin = self._spin(150, 300, 225, 1, 5)
        self.ltan_combo = GlassComboBox()
        self.ltan_combo.setEditable(True)
        self.ltan_combo.addItems(["10:30", "06:00"])
        form.addRow("项目名称", self.name_edit)
        form.addRow("起始UTC", self.start_edit)
        form.addRow("任务设计寿命 (h)", life_box)
        form.addRow("轨道高度 (km)", self.altitude_spin)
        form.addRow("LTAN", self.ltan_combo)
        self.structure_mass_edit = QLineEdit()
        self.payload_mass_edit = QLineEdit()
        for edit in (self.structure_mass_edit, self.payload_mass_edit):
            edit.setPlaceholderText("待填写；0表示未计入")
        form.addRow("卫星结构质量 (kg)", self.structure_mass_edit)
        payload_box = QVBoxLayout()
        payload_box.setContentsMargins(0, 0, 0, 0)
        payload_box.setSpacing(3)
        payload_box.addWidget(self.payload_mass_edit)
        self.payload_mass_note = QLabel(
            "指除卫星本体结构、太阳翼、电池系统、推进单元结构和推进剂以外的其余质量"
            "（例如仪器设备、姿轨控系统、星务/数据处理、线缆等）。"
        )
        self.payload_mass_note.setWordWrap(True)
        self.payload_mass_note.setStyleSheet("color:#6B7280;font-size:9pt")
        payload_box.addWidget(self.payload_mass_note)
        form.addRow("其他载荷质量 (kg)", payload_box)
        self.legacy_mass_label = QLabel("")
        self.legacy_mass_label.setWordWrap(True)
        form.addRow(self.legacy_mass_label)
        layout.addWidget(mission, 0, 0)

        spacecraft = QGroupBox("卫星迎风面积与供电")
        form = QFormLayout(spacecraft)
        self.body_area_spin = self._spin(0.01, 1000, 2, 2, 0.5)
        self.cd_spin = self._spin(0.1, 10, 2.2, 2, 0.1)
        self.total_power_spin = self._spin(0.01, 1000, 10, 2, 1)
        self.ep_power_spin = self._spin(0.01, 1000, 5, 2, 1)
        self.solar_mode_combo = GlassComboBox()
        self.solar_mode_combo.addItem("自动尺寸", "auto_size")
        self.solar_mode_combo.addItem("固定硬件", "fixed_hardware")
        self.specific_power_spin = self._spin(1, 5000, 300, 1, 10)
        self.solar_area_spin = self._spin(0, 10000, 33.333, 3, 1)
        self.supply_combo = GlassComboBox()
        self.supply_combo.addItem("太阳翼", "solar")
        self.supply_combo.addItem("电池（允许太阳翼补充供电）", "battery")
        self.solar_mass_power_edit = QLineEdit()
        self.solar_mass_power_edit.setPlaceholderText("待填写；不同于W/m²")
        self.battery_energy_edit = QLineEdit()
        self.battery_energy_edit.setPlaceholderText("系统级可用值；待填写")
        self.battery_power_edit = QLineEdit()
        self.battery_power_edit.setPlaceholderText("待填写")
        form.addRow("本体迎风面积 (m²)", self.body_area_spin)
        form.addRow("阻力系数 Cd", self.cd_spin)
        form.addRow("整星功率 (kW)", self.total_power_spin)
        form.addRow("电推进可用功率 (kW)", self.ep_power_spin)
        form.addRow("供电方式", self.supply_combo)
        form.addRow("太阳翼输入方式", self.solar_mode_combo)
        form.addRow("太阳翼单位面积功率 (W/m²)", self.specific_power_spin)
        form.addRow("太阳翼面积 (m²)", self.solar_area_spin)
        form.addRow("太阳翼系统比功率 (W/kg)", self.solar_mass_power_edit)
        form.addRow("电池可用比能量 (kWh/kg)", self.battery_energy_edit)
        form.addRow("电池持续输出功率上限 (kW)", self.battery_power_edit)
        self.battery_labels = [form.labelForField(self.battery_energy_edit), form.labelForField(self.battery_power_edit)]
        self.solar_mass_power_label = form.labelForField(self.solar_mass_power_edit)
        self.solar_area_label = form.labelForField(self.solar_area_spin)
        self.solar_mode_combo.currentIndexChanged.connect(self._update_solar_mode)
        self.total_power_spin.valueChanged.connect(self._update_auto_solar_area)
        self.specific_power_spin.valueChanged.connect(self._update_auto_solar_area)
        self.supply_combo.currentIndexChanged.connect(self._update_supply_mode)
        self.solar_area_spin.valueChanged.connect(self._update_mass_field_modes)
        layout.addWidget(spacecraft, 0, 1, 2, 1)

        atmosphere = QGroupBox("空间天气")
        self.atmosphere_group = atmosphere
        form = QFormLayout(atmosphere)
        self.weather_mode_combo = GlassComboBox()
        self.weather_mode_combo.addItem("历史数据CSV", "historical")
        self.weather_mode_combo.addItem("固定活动情景（敏感性）", "fixed_activity")
        self.weather_path_edit = QLineEdit()
        self.weather_browse_button = QPushButton("选择CSV")
        self.weather_browse_button.setObjectName("secondary")
        self.weather_browse_button.clicked.connect(self.choose_weather)
        weather_row = QHBoxLayout()
        weather_row.addWidget(self.weather_path_edit, 1)
        weather_row.addWidget(self.weather_browse_button)
        self.activity_combo = GlassComboBox()
        self.activity_combo.addItem("低活动", "low")
        self.activity_combo.addItem("中活动", "nominal")
        self.activity_combo.addItem("高活动", "high")
        form.addRow("模式", self.weather_mode_combo)
        form.addRow("历史CSV", weather_row)
        form.addRow("固定活动", self.activity_combo)
        self.weather_path_label = form.labelForField(weather_row)
        self.activity_label = form.labelForField(self.activity_combo)
        self.weather_mode_combo.currentIndexChanged.connect(self._update_weather_mode)
        self.weather_path_edit.textChanged.connect(self._update_weather_coverage_hint)
        self.life_edit.textChanged.connect(self._update_weather_coverage_hint)
        layout.addWidget(atmosphere, 1, 0)

        candidates = QGroupBox("候选推进方案")
        self.candidates_group = candidates
        candidate_layout = QVBoxLayout(candidates)
        library_actions = QHBoxLayout()
        self.library_button = QPushButton("推进器型号库")
        self.library_button.setObjectName("secondary")
        self.library_button.setToolTip("打开推进器型号库，用于选择型号并载入本项目。")
        self.library_button.clicked.connect(self.open_library)
        library_actions.addWidget(self.library_button)
        self.collect_library_button = QPushButton("收录本项目方案")
        self.collect_library_button.setObjectName("secondary")
        self.collect_library_button.setToolTip("将候选表当前选中行的性能、结构质量和来源保存到型号库，供其他项目使用。")
        self.collect_library_button.setEnabled(False)
        self.collect_library_button.clicked.connect(self._store_candidate_in_library)
        library_actions.addWidget(self.collect_library_button)
        library_actions.addStretch(1)
        candidate_layout.addLayout(library_actions)
        self.empty_candidates_label = QLabel(
            "当前项目暂无候选方案。点击“推进器型号库”选择并载入，或点击“添加自定义方案”。"
        )
        self.empty_candidates_label.setWordWrap(True)
        candidate_layout.addWidget(self.empty_candidates_label)
        self.custom_candidate_label = QLabel("自定义方案：0个；新增后固定显示在列表顶部。")
        self.custom_candidate_label.setStyleSheet("color:#4B5563")
        self.custom_candidate_label.setWordWrap(True)
        candidate_layout.addWidget(self.custom_candidate_label)
        self.candidate_table = QTableWidget(0, 6)
        self.candidate_table.setItemDelegateForColumn(0, GlassCheckDelegate(self.candidate_table))
        self.candidate_table.setHorizontalHeaderLabels(
            ["选", "方案", "推功比\n(mN/kW)", "比冲 Isp\n(s)", "集气效率", "结构质量\n(kg)"]
        )
        self.candidate_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.candidate_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.candidate_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.candidate_table.cellDoubleClicked.connect(
            self._candidate_double_clicked
        )
        self.candidate_table.itemChanged.connect(self._candidate_item_changed)
        self.candidate_table.currentCellChanged.connect(
            self._update_candidate_actions
        )
        self.candidate_table.setMinimumHeight(250)
        self.candidate_table.setColumnWidth(0, 40)
        for column in (2, 3, 4, 5):
            self.candidate_table.setColumnWidth(column, 130)
        candidate_layout.addWidget(self.candidate_table)
        candidate_buttons = QHBoxLayout()
        add_button = QPushButton("添加自定义方案")
        add_button.setObjectName("secondary")
        add_button.clicked.connect(self.add_custom_thruster)
        candidate_buttons.addWidget(add_button)
        edit_button = QPushButton("编辑/复制选中方案")
        edit_button.setObjectName("secondary")
        edit_button.clicked.connect(self.edit_candidate)
        candidate_buttons.addWidget(edit_button)
        self.remove_candidate_button = QPushButton("移除选中方案")
        self.remove_candidate_button.setObjectName("secondary")
        self.remove_candidate_button.setToolTip("仅从本项目移除当前选中行；不会删除推进器型号库记录。")
        self.remove_candidate_button.setEnabled(False)
        self.remove_candidate_button.clicked.connect(self.remove_candidate)
        candidate_buttons.addWidget(self.remove_candidate_button)
        candidate_layout.addLayout(candidate_buttons)
        layout.addWidget(candidates, 2, 0, 1, 2)

        self.run_button = QPushButton("运行完整任务分析")
        self.run_button.clicked.connect(self.run_study)
        self.cancel_button = QPushButton("取消计算")
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_study)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress_label = QLabel("等待输入")
        self.progress_label.setWordWrap(True)
        self.progress_label.setStyleSheet("color:#6B7280")
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(2, 1)
        scroll.setWidget(panel)
        # Leave room for the fixed header/run controls on a 1080p display at
        # 200% scaling; the form itself remains accessible through scrolling.
        scroll.setMinimumHeight(220)
        return scroll

    def _build_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)

        self.orbit_group = QGroupBox("轨道与大气")
        orbit_layout = QVBoxLayout(self.orbit_group)
        self.orbit_cards = MetricCardGroup((
            ("inclination", "SSO倾角"), ("period", "轨道周期"),
            ("density", "任务期间密度范围 (kg/m³)"),
            ("mean_drag", "平均阻力"), ("max_drag", "最大阻力"),
        ))
        self.card_labels = self.orbit_cards.labels
        orbit_layout.addWidget(self.orbit_cards)
        layout.addWidget(self.orbit_group)

        self.power_group = QGroupBox("任务需求与供电")
        power_layout = QVBoxLayout(self.power_group)
        self.power_cards = MetricCardGroup((
            ("impulse", "总冲量"), ("solar_power", "太阳翼供电功率"),
            ("solar_area", "太阳翼面积"), ("battery_power", "电池补充供电功率"),
            ("battery_energy", "电池配置电量"),
        ))
        self.power_card_labels = self.power_cards.labels
        power_layout.addWidget(self.power_cards)
        self.battery_configuration_note = QLabel(
            "电池两项为功率配平的补充供电配置：根据整星用电、太阳翼发电及电池输出上限计算，"
            "电量＝受限补充功率×任务时长。并非电池额定功率或已有容量；太阳翼供电足够时，两项为0。"
        )
        self.battery_configuration_note.setWordWrap(True)
        self.battery_configuration_note.setStyleSheet("color:#61708B;font-size:9pt")
        power_layout.addWidget(self.battery_configuration_note)
        self.power_summary_label = QLabel("供电判断将在计算后显示。")
        self.power_summary_label.setWordWrap(True)
        self.power_summary_label.setStyleSheet("color:#61708B;font-size:9pt")
        power_layout.addWidget(self.power_summary_label)
        layout.addWidget(self.power_group)

        heading = QLabel("候选方案汇总")
        heading.setStyleSheet("color:#344C83;font-size:12pt;font-weight:600")
        layout.addWidget(heading)
        self.summary_columns = (
            ("name_zh", "方案"), ("status", "判断"),
            ("required_power_kW", "推进系统最低功率 (kW)"),
            ("satellite_structure_mass_kg", "卫星结构质量 (kg)"),
            ("solar_array_mass_kg", "太阳翼质量 (kg)"),
            ("battery_mass_kg", "电池质量 (kg)"),
            ("propulsion_structure_mass_kg", "推进单元结构质量 (kg)"),
            ("propellant_mass_kg", "推进剂质量 (kg)"),
            ("payload_mass_kg", "其他载荷质量 (kg)"),
            ("initial_total_mass_kg", "整星总质量 (kg)"),
        )
        self.result_table = QTableWidget(0, len(self.summary_columns))
        self.result_table.setHorizontalHeaderLabels([label for _, label in self.summary_columns])
        for key, explanation in {
            "required_power_kW": "各圈时间平均阻力的最大值除以推功比得到的理论功率阈值；严格大于判据要求实际功率超过阈值。还需检查设备工作范围、供电和ABEP进气限制，不是设备自身的最低工作功率。",
            "battery_mass_kg": "按受输出上限约束后的电池供电功率×任务时长配置电量，再除以系统可用比能量估算质量；不含食期、充电循环、退化和额外余量。供电不足时，这不是满足整星需求所需的电池质量。",
            "initial_total_mass_kg": "六项质量之和，包含本任务所需的全部携带推进剂；口径仍为任务初始质量，不是任务末期质量。",
            "status": "按每圈平均实际可用推力大于该圈平均整星阻力判断；末尾不足一圈按实际时段计入。允许瞬时推力不足，未模拟高度波动。悬停判断单元格可查看具体限制。",
        }.items():
            column = next(i for i, (field, _) in enumerate(self.summary_columns) if field == key)
            self.result_table.horizontalHeaderItem(column).setToolTip(explanation)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setWordWrap(False)
        self.result_table.verticalHeader().hide()
        self.result_table.setMinimumHeight(140)
        layout.addWidget(self.result_table)
        self.mass_note = QLabel("整星总质量为六项质量之和，包含任务所需携带推进剂；电池质量按配置电量估算。判断说明可悬停查看。")
        self.mass_note.setWordWrap(True)
        self.mass_note.setStyleSheet("color:#61708B;font-size:9pt")
        layout.addWidget(self.mass_note)
        return widget

    def _build_sensitivity_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        self.scan_controls = QWidget()
        self.scan_controls.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls_layout = QVBoxLayout(self.scan_controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        note = QLabel(
            "在此页面设置SSO轨道高度范围并运行高度扫描。"
            "采样密度是卫星每绕地一周计算多少次；采样越密，计算越慢。快速预览仅用于初步查看。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("background:rgba(249,244,228,210);color:#715D30;border:1px solid white;border-radius:10px;padding:10px")
        controls_layout.addWidget(note)
        controls = QHBoxLayout()
        self.scan_min = self._spin(150, 300, 180, 1, 5)
        self.scan_max = self._spin(150, 300, 250, 1, 5)
        self.scan_step = self._spin(0.5, 50, 10, 1, 5)
        self.scan_candidate = GlassComboBox()
        self.scan_accuracy = GlassComboBox()
        self.scan_accuracy.addItem("快速预览（每圈约18点）", 20.0)
        self.scan_accuracy.addItem("详细计算（每圈约72点）", 5.0)
        self.scan_accuracy.setToolTip(
            "每圈约18点：相邻计算位置相隔20°；每圈约72点：相隔5°。\n"
            "这里的角度不是SSO倾角。详细计算的采样点数约为快速预览的4倍；最终结果仍需按用途检查采样收敛。"
        )
        for label, widget_control in (("最低高度 (km)", self.scan_min), ("最高高度 (km)", self.scan_max), ("高度间隔 (km)", self.scan_step)):
            controls.addWidget(QLabel(label))
            controls.addWidget(widget_control)
        controls.addStretch(1)
        controls_layout.addLayout(controls)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("推进方案"))
        controls.addWidget(self.scan_candidate, 1)
        controls.addWidget(QLabel("采样密度"))
        controls.addWidget(self.scan_accuracy)
        self.scan_button = QPushButton("运行高度扫描")
        self.scan_button.setEnabled(False)
        self.scan_button.clicked.connect(self.run_sensitivity)
        controls.addWidget(self.scan_button)
        controls_layout.addLayout(controls)
        self.scan_progress = QProgressBar()
        self.scan_progress.setValue(0)
        self.scan_progress_label = QLabel("等待运行高度扫描")
        self.scan_progress_label.setWordWrap(True)
        self.scan_progress_label.setStyleSheet("color:#6B7280")
        controls_layout.addWidget(self.scan_progress)
        controls_layout.addWidget(self.scan_progress_label)
        layout.addWidget(self.scan_controls)
        self.sensitivity_chart_region = QWidget()
        self.sensitivity_chart_region.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sensitivity_chart_host = QVBoxLayout(self.sensitivity_chart_region)
        self.sensitivity_chart_host.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.sensitivity_chart_region, 1)
        self._reset_scan_result()
        return widget

    def _reset_scan_result(self):
        while self.sensitivity_chart_host.count():
            item = self.sensitivity_chart_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.sensitivity_chart_host.setAlignment(Qt.AlignTop)
        self.scan_placeholder = QLabel("等待运行高度扫描")
        self.scan_placeholder.setStyleSheet(
            "background:rgba(255,255,255,150);border:1px solid white;"
            "border-radius:14px;padding:22px;color:#72809A;"
        )
        self.scan_placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.sensitivity_chart_host.addWidget(self.scan_placeholder)
        self.scan_progress.hide()
        self.scan_progress_label.hide()
        self.scan_progress.setValue(0)

    def _build_library_window(self) -> None:
        self.library_window = ResultsWindow(self, Qt.Window)
        self.library_window.setWindowTitle("EP-VISTA — 推进器型号库")
        self.library_window.resize(1400, 800)
        self.library_window.setStyleSheet(STYLE)
        root = GlassSurface()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 12)
        title = QLabel("推进器型号库")
        title.setObjectName("brandTitle")
        layout.addWidget(title)
        self.library_panel = LibraryPanel(self.library_window)
        self.library_panel.use_requested.connect(self._use_library_records)
        layout.addWidget(self.library_panel, 1)
        self.library_footer_label = self._footer_notice()
        layout.addWidget(self.library_footer_label)
        self.library_window.set_content_widget(root)

    def _use_library_records(self, records: list[ThrusterRecord]) -> None:
        current_ids = {item.thruster_id for item in self._all_candidates()}
        conflicts = [item.thruster_id for item in records if item.thruster_id in current_ids]
        if conflicts and QMessageBox.question(
            self, "更新本项目方案",
            "将用型号库参数和默认质量覆盖本项目同ID方案：" + "、".join(conflicts)
            + "\n已算出的结果仍保留旧输入快照；更新后需要重新计算。是否继续？",
        ) != QMessageBox.Yes:
            return
        selected = set(self._selected_ids())
        by_id = {item.thruster_id: item for item in self.library}
        incoming_ids = {item.thruster_id for item in records}
        self.custom_thrusters = [item for item in self.custom_thrusters if item.thruster_id not in incoming_ids]
        for record in records:
            by_id[record.thruster_id] = deepcopy(record)
            self.structure_inputs[record.thruster_id] = record.structure_mass_input()
            self._mass_invalid.pop(record.thruster_id, None)
            selected.add(record.thruster_id)
        self.library = list(by_id.values())
        self._refresh_candidate_table(selected)
        self._mark_dirty()
        self.library_panel.status.setText("已载入本项目；请核对质量计入范围，保存项目并重新计算。")

    def _store_candidate_in_library(self) -> None:
        focused = QApplication.focusWidget()
        if focused is not None:
            focused.clearFocus()
        row = self.candidate_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "选择方案", "请先在本项目候选表选中要收录的方案。")
            return
        candidate_id = self.candidate_table.item(row, 0).data(Qt.UserRole)
        if candidate_id in self._mass_invalid:
            QMessageBox.warning(self, "质量有误", "请先修正该方案的结构质量。")
            return
        record = deepcopy(self._all_candidates()[row])
        mass = self.structure_inputs.get(candidate_id, StructureMassInput())
        record.structure_mass_kg = mass.mass_kg
        record.structure_mass_source = mass.source
        record.structure_mass_notes = mass.notes
        if self.library_panel.store_record(record, dialog_parent=self):
            self.progress_label.setText(f"已将“{record.name_zh}”收录到推进器型号库；其他项目可从型号库载入。")

    @staticmethod
    def _spin(minimum, maximum, value, decimals, step):
        widget = GlassDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setValue(value)
        widget.setSingleStep(step)
        return widget

    def _load_template(self) -> None:
        path = project_root() / "examples" / "new_project_template.ep-vista.json"
        self._apply_project(ProjectCase.load(path))

    def _visible_library(self) -> list[ThrusterRecord]:
        # Retain the legacy raw record for imported studies, but retire it from
        # both UI entry points so it cannot reappear in the evidence tab.
        return [item for item in self.library if item.thruster_id != "ENG_ABEP20"]

    def _all_candidates(self) -> list[ThrusterRecord]:
        return [*self.custom_thrusters, *self._visible_library()]

    def _update_candidate_actions(self, *_args) -> None:
        enabled = 0 <= self.candidate_table.currentRow() < self.candidate_table.rowCount()
        self.collect_library_button.setEnabled(enabled)
        self.remove_candidate_button.setEnabled(enabled)

    def remove_candidate(self) -> None:
        focused = QApplication.focusWidget()
        if focused is not None:
            focused.clearFocus()
        row = self.candidate_table.currentRow()
        candidates = self._all_candidates()
        if not 0 <= row < len(candidates):
            return
        record = candidates[row]
        if QMessageBox.question(
            self, "从本项目移除方案",
            f"确定移除当前选中行“{record.name_zh}”（{record.thruster_id}）吗？\n"
            "仅移除本项目中的方案，不删除型号库记录。未收录的自定义方案请先另行保存。\n"
            "请保存项目以保留此更改；已有计算结果保留旧快照，需重新计算。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        selected = set(self._selected_ids())
        # Remove the selected occurrence, not every record sharing its ID.
        # This also lets users repair explicit old snapshots with ID conflicts.
        if row < len(self.custom_thrusters):
            del self.custom_thrusters[row]
        else:
            visible_indices = [index for index, item in enumerate(self.library)
                               if item.thruster_id != "ENG_ABEP20"]
            del self.library[visible_indices[row - len(self.custom_thrusters)]]
        remaining_ids = {item.thruster_id for item in self._all_candidates()}
        if record.thruster_id not in remaining_ids:
            self.structure_inputs.pop(record.thruster_id, None)
            self._mass_invalid.pop(record.thruster_id, None)
        self._refresh_candidate_table(selected & remaining_ids)
        if self.candidate_table.rowCount():
            self.candidate_table.setCurrentCell(min(row, self.candidate_table.rowCount() - 1), 1)
        self._update_candidate_actions()
        self._mark_dirty()
        self.progress_label.setText(f"已从本项目移除“{record.name_zh}”；型号库未改动，请保存项目。")

    def _refresh_candidate_table(self, selected: set[str] | None = None) -> None:
        if selected is None:
            selected = set(self._selected_ids())
        candidates = self._all_candidates()
        self.empty_candidates_label.setVisible(not candidates)
        self.custom_candidate_label.setText(
            f"自定义方案：{len(self.custom_thrusters)}个；新增后固定显示在列表顶部。"
        )
        self.candidate_table.blockSignals(True)
        self.candidate_table.setRowCount(len(candidates))
        for row, item in enumerate(candidates):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(Qt.Checked if item.thruster_id in selected else Qt.Unchecked)
            check.setData(Qt.UserRole, item.thruster_id)
            self.candidate_table.setItem(row, 0, check)
            is_custom = row < len(self.custom_thrusters)
            display_name = f"【自定义】{item.name_zh}" if is_custom else item.name_zh
            name_cell = QTableWidgetItem(display_name)
            if is_custom:
                name_cell.setBackground(QColor("#EDF3FF"))
                name_cell.setToolTip(
                    f"用户自定义方案\n推功比：{item.thrust_to_power_mN_kW:g} mN/kW\n"
                    f"比冲：{item.isp_s:g} s"
                )
            self.candidate_table.setItem(row, 1, name_cell)
            self.candidate_table.setItem(row, 2, QTableWidgetItem(f"{item.thrust_to_power_mN_kW:g}"))
            self.candidate_table.setItem(row, 3, QTableWidgetItem(f"{item.isp_s:g}"))
            if item.architecture == "abep":
                efficiency_cell = QTableWidgetItem(f"{float(item.intake_efficiency):g}")
                efficiency_cell.setToolTip("吸气式电推进的有效集气效率")
            else:
                efficiency_cell = QTableWidgetItem("—")
                efficiency_cell.setFlags(Qt.NoItemFlags)
                efficiency_cell.setBackground(QColor("#ECEFF4"))
                efficiency_cell.setForeground(QColor("#929BAA"))
                efficiency_cell.setToolTip("传统供质推进方式不使用集气效率")
            self.candidate_table.setItem(row, 4, efficiency_cell)
            for column in (1, 2, 3, 4):
                cell = self.candidate_table.item(row, column)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            mass = self.structure_inputs.get(item.thruster_id, StructureMassInput())
            text = self._mass_invalid.get(item.thruster_id, "" if mass.mass_kg is None else f"{mass.mass_kg:g}")
            cell = QTableWidgetItem(text)
            cell.setToolTip(f"{mass.source}\n{mass.notes}\n空白为未知；0表示未计入。")
            if item.thruster_id in self._mass_invalid:
                cell.setBackground(QColor("#FFE4E4"))
            self.candidate_table.setItem(row, 5, cell)
        self.candidate_table.blockSignals(False)
        self._update_candidate_actions()

    def _candidate_double_clicked(self, row: int, column: int) -> None:
        if column not in (0, 5):
            self.edit_candidate(row)

    def _candidate_item_changed(self, cell: QTableWidgetItem) -> None:
        self._mark_dirty()
        if cell.column() != 5:
            return
        candidate_id = self.candidate_table.item(cell.row(), 0).data(Qt.UserRole)
        try:
            value = self._optional_number(cell.text(), "结构质量 (kg)")
        except ValueError as exc:
            self._mass_invalid[candidate_id] = cell.text()
            self.progress_label.setText(str(exc))
            self.candidate_table.blockSignals(True)
            cell.setBackground(QColor("#FFE4E4"))
            self.candidate_table.blockSignals(False)
            return
        self._mass_invalid.pop(candidate_id, None)
        old = self.structure_inputs.get(candidate_id, StructureMassInput())
        # This marker describes the current input, not the edit history.
        notes = old.notes.replace(" 未计入。", "")
        self.structure_inputs[candidate_id] = StructureMassInput(
            value, "用户输入", notes + (" 未计入。" if value == 0 else "")
        )
        self.candidate_table.blockSignals(True)
        cell.setBackground(QColor("white"))
        cell.setToolTip(f"用户输入\n{self.structure_inputs[candidate_id].notes}")
        self.candidate_table.blockSignals(False)

    @staticmethod
    def _optional_number(text: str, label: str) -> float | None:
        if not text.strip():
            return None
        try:
            value = float(text)
            if not np.isfinite(value) or value < 0:
                raise ValueError
            return value
        except ValueError:
            raise ValueError(f"{label}必须为有限非负数，或留空。") from None

    def _connect_dirty_signals(self) -> None:
        for edit in self.input_panel.findChildren(QLineEdit):
            edit.textChanged.connect(self._mark_dirty)
        for control in self.input_panel.findChildren(QDoubleSpinBox):
            control.valueChanged.connect(self._mark_dirty)
        for control in self.input_panel.findChildren(QComboBox):
            control.currentTextChanged.connect(self._mark_dirty)

    def _mark_dirty(self, *_args) -> None:
        if self._applying:
            return
        self._input_revision += 1
        if self.result is not None:
            self.snapshot_label.setText("输入已修改，当前结果来自上次计算；高度扫描仍使用该次输入快照。")

    def open_library(self) -> None:
        if self.library_window.isMinimized():
            self.library_window.showNormal()
        self.library_window.show()
        self.library_window.raise_()
        self.library_window.activateWindow()

    def show_results(self) -> None:
        if self.results_window.isMinimized():
            self.results_window.showNormal()
        self.results_window.show()
        self.results_window.raise_()

    def _selected_ids(self) -> list[str]:
        return [
            self.candidate_table.item(row, 0).data(Qt.UserRole)
            for row in range(self.candidate_table.rowCount())
            if self.candidate_table.item(row, 0).checkState() == Qt.Checked
        ]

    @staticmethod
    def _parse_ltan(text: str) -> float:
        stripped = text.strip()
        if ":" in stripped:
            hours, minutes = stripped.split(":", 1)
            return float(hours) + float(minutes) / 60.0
        return float(stripped)

    def _collect_project(self, validate: bool = True) -> ProjectCase:
        focused = QApplication.focusWidget()
        if focused is not None:
            focused.clearFocus()  # Commit any active table editor before snapshot/save.
        if self._mass_invalid:
            raise ValueError("请修正结构质量：" + ", ".join(self._mass_invalid))
        life_text = self.life_edit.text().strip()
        life = float(life_text) if life_text else None
        custom = [asdict(item) for item in self.custom_thrusters]
        project = ProjectCase(
            name=self.name_edit.text().strip() or "EP-VISTA项目",
            mission=MissionConfig(
                start_utc=self.start_edit.text().strip(), design_life_hours=life,
                altitude_km=self.altitude_spin.value(), ltan_hours=self._parse_ltan(self.ltan_combo.currentText()),
            ),
            spacecraft=SpacecraftConfig(
                mass_kg=self._legacy_mass_kg,
                structure_mass_kg=self._optional_number(self.structure_mass_edit.text(), "卫星结构质量"),
                payload_mass_kg=self._optional_number(self.payload_mass_edit.text(), "其他载荷质量"),
                body_frontal_area_m2=self.body_area_spin.value(),
                drag_coefficient=self.cd_spin.value(), solar_array_drag_coefficient=self.cd_spin.value(),
            ),
            power=PowerConfig(
                total_power_kW=self.total_power_spin.value(), propulsion_power_kW=self.ep_power_spin.value(),
                solar_array_mode=self.solar_mode_combo.currentData(),
                solar_array_specific_power_W_m2=self.specific_power_spin.value(),
                solar_array_area_m2=self.solar_area_spin.value() if self.solar_mode_combo.currentData() == "fixed_hardware" else None,
                supply_mode=self.supply_combo.currentData(),
                solar_array_specific_power_W_kg=self._optional_number(self.solar_mass_power_edit.text(), "太阳翼系统比功率"),
                battery_usable_specific_energy_kWh_kg=self._optional_number(self.battery_energy_edit.text(), "电池比能量"),
                battery_max_power_kW=self._optional_number(self.battery_power_edit.text(), "电池功率上限"),
            ),
            atmosphere=AtmosphereConfig(
                mode=self.weather_mode_combo.currentData(),
                weather_file=self.weather_path_edit.text().strip() if self.weather_mode_combo.currentData() == "historical" else None,
                fixed_activity=self.activity_combo.currentData() if self.weather_mode_combo.currentData() == "fixed_activity" else None,
            ),
            sampling=deepcopy(self._sampling), selected_thruster_ids=self._selected_ids(),
            custom_thrusters=custom,
            propulsion_structure=deepcopy(self.structure_inputs),
            library_snapshot=[asdict(item) for item in self.library],
        )
        if not validate:
            return project
        if not project.selected_thruster_ids:
            raise ValueError("请至少选择一个候选推进方案；可从型号库载入或添加自定义方案。")
        chosen_ids = [item.thruster_id for item in self._all_candidates()
                      if item.thruster_id in project.selected_thruster_ids]
        if len(chosen_ids) != len(set(chosen_ids)):
            raise ValueError("选中的候选方案存在重复ID，请用“移除选中方案”删除多余行后再计算。")
        project.validate()
        if project.atmosphere.mode == "historical":
            weather_path = self._resolved_weather_path(project.atmosphere.weather_file or "")
            validate_historical_task_window(
                weather_path,
                project.mission.start_utc,
                float(project.mission.design_life_hours),
            )
        return project

    def _apply_project(self, project: ProjectCase) -> None:
        self._applying = True
        self.library = ([ThrusterRecord(**item) for item in project.library_snapshot]
                        if project.library_snapshot is not None
                        else [item for item in load_thruster_library(default_thruster_library_path())
                              if item.thruster_id not in {entry["thruster_id"] for entry in project.custom_thrusters}])
        self._legacy_mass_kg = project.spacecraft.mass_kg
        self._sampling = deepcopy(project.sampling)
        self.structure_inputs = deepcopy(project.propulsion_structure)
        self._mass_invalid.clear()
        self.name_edit.setText(project.name)
        self.start_edit.setText(project.mission.start_utc)
        self.life_edit.setText("" if project.mission.design_life_hours is None else f"{project.mission.design_life_hours:g}")
        self.altitude_spin.setValue(project.mission.altitude_km)
        hours = int(project.mission.ltan_hours)
        minutes = round((project.mission.ltan_hours - hours) * 60)
        self.ltan_combo.setCurrentText(f"{hours:02d}:{minutes:02d}")
        self.structure_mass_edit.setText("" if project.spacecraft.structure_mass_kg is None else f"{project.spacecraft.structure_mass_kg:g}")
        self.payload_mass_edit.setText("" if project.spacecraft.payload_mass_kg is None else f"{project.spacecraft.payload_mass_kg:g}")
        self.legacy_mass_label.setText(
            f"旧项目整星质量{self._legacy_mass_kg:g} kg仅作参考，不自动拆分；请补齐新质量参数。"
            if self._legacy_mass_kg is not None else ""
        )
        self.legacy_mass_label.setVisible(self._legacy_mass_kg is not None)
        self.supply_combo.setCurrentIndex(0 if project.power.supply_mode == "solar" else 1)
        self.body_area_spin.setValue(project.spacecraft.body_frontal_area_m2)
        self.cd_spin.setValue(project.spacecraft.drag_coefficient)
        self.total_power_spin.setValue(project.power.total_power_kW)
        self.ep_power_spin.setValue(project.power.propulsion_power_kW)
        self.solar_mode_combo.setCurrentIndex(0 if project.power.solar_array_mode == "auto_size" else 1)
        if project.power.supply_mode == "solar":
            self._solar_mode_before_battery = project.power.solar_array_mode
        self.specific_power_spin.setValue(project.power.solar_array_specific_power_W_m2)
        if project.power.solar_array_area_m2 is not None:
            self._fixed_solar_area_value = project.power.solar_array_area_m2
            self.solar_area_spin.setValue(project.power.solar_array_area_m2)
        for edit, value in (
            (self.solar_mass_power_edit, project.power.solar_array_specific_power_W_kg),
            (self.battery_energy_edit, project.power.battery_usable_specific_energy_kWh_kg),
            (self.battery_power_edit, project.power.battery_max_power_kW),
        ):
            edit.setText("" if value is None else f"{value:g}")
        self.weather_mode_combo.setCurrentIndex(0 if project.atmosphere.mode == "historical" else 1)
        self.weather_path_edit.setText(project.atmosphere.weather_file or "")
        activity_index = {"low": 0, "nominal": 1, "high": 2}.get(project.atmosphere.fixed_activity, 1)
        self.activity_combo.setCurrentIndex(activity_index)
        self.custom_thrusters = [ThrusterRecord(**item) for item in project.custom_thrusters]
        self._refresh_candidate_table(set(project.selected_thruster_ids))
        self._update_supply_mode()
        self._update_weather_mode()
        self._applying = False
        self._mark_dirty()

    def _update_supply_mode(self, *_args) -> None:
        battery = self.supply_combo.currentData() == "battery"
        if battery:
            if self.solar_mode_combo.isEnabled():
                self._solar_mode_before_battery = self.solar_mode_combo.currentData()
            self.solar_mode_combo.setCurrentIndex(1)
        elif not self.solar_mode_combo.isEnabled():
            self.solar_mode_combo.setCurrentIndex(self.solar_mode_combo.findData(self._solar_mode_before_battery))
        self.solar_mode_combo.setEnabled(not battery)
        for widget in (self.battery_energy_edit, self.battery_power_edit, *self.battery_labels):
            widget.setEnabled(battery)
        self._update_solar_mode()
        self._update_mass_field_modes()

    def _update_mass_field_modes(self, *_args) -> None:
        has_solar = self.solar_area_spin.value() > 0 or self.solar_mode_combo.currentData() == "auto_size"
        self.solar_mass_power_edit.setEnabled(has_solar)
        self.solar_mass_power_label.setEnabled(has_solar)

    def _update_solar_mode(self) -> None:
        mode = self.solar_mode_combo.currentData()
        fixed_hardware = mode == "fixed_hardware"
        if self._last_solar_mode == "fixed_hardware" and self.solar_area_spin.isEnabled():
            self._fixed_solar_area_value = self.solar_area_spin.value()
        if fixed_hardware and self._last_solar_mode != "fixed_hardware":
            self.solar_area_spin.setValue(self._fixed_solar_area_value)
        self.solar_area_spin.setEnabled(fixed_hardware)
        self.solar_area_label.setEnabled(fixed_hardware)
        self._last_solar_mode = mode
        if not fixed_hardware:
            self._update_auto_solar_area()

    def _update_auto_solar_area(self, *_args) -> None:
        if self.solar_mode_combo.currentData() != "auto_size":
            return
        specific_power = self.specific_power_spin.value()
        if specific_power > 0:
            self.solar_area_spin.setValue(
                self.total_power_spin.value() * 1000.0 / specific_power
            )

    def _update_weather_mode(self) -> None:
        historical = self.weather_mode_combo.currentData() == "historical"
        self.weather_path_edit.setEnabled(historical)
        self.weather_browse_button.setEnabled(historical)
        self.weather_path_label.setEnabled(historical)
        self.activity_combo.setEnabled(not historical)
        self.activity_label.setEnabled(not historical)
        self._update_weather_coverage_hint()

    @staticmethod
    def _resolved_weather_path(path_text: str) -> Path:
        path = Path(path_text)
        return path if path.is_absolute() else project_root() / path

    def _update_weather_coverage_hint(self, *_args) -> None:
        if self.weather_mode_combo.currentData() != "historical":
            self.weather_coverage_label.setText(
                "固定活动情景不受CSV覆盖范围限制；起始UTC仍用于计算太阳位置、轨道面和季节效应。"
            )
            return
        path_text = self.weather_path_edit.text().strip()
        life_text = self.life_edit.text().strip()
        if not path_text:
            self.weather_coverage_label.setText("选择历史CSV后显示允许的起始UTC范围。")
            return
        try:
            life = float(life_text)
            if life <= 0:
                raise ValueError
        except ValueError:
            self.weather_coverage_label.setText(
                "输入任务设计寿命后，程序将联合CSV覆盖范围计算允许的起始UTC。"
            )
            return
        try:
            first, latest_exclusive = historical_task_start_window(
                self._resolved_weather_path(path_text),
                life,
            )
            if latest_exclusive <= first:
                self.weather_coverage_label.setText(
                    "当前任务设计寿命不短于该CSV的有效覆盖时长，不能使用这份历史数据。"
                )
                return
            latest = latest_exclusive - timedelta(seconds=1)
            first_text = first.isoformat().replace("+00:00", "Z")
            latest_text = latest.isoformat().replace("+00:00", "Z")
            self.weather_coverage_label.setText(
                f"按当前设计寿命，起始UTC允许范围：{first_text} 至 {latest_text}。"
            )
        except (OSError, ValueError) as exc:
            self.weather_coverage_label.setText(f"无法读取历史数据范围：{exc}")

    def choose_weather(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择空间天气CSV", str(project_root() / "data" / "space_weather"), "CSV (*.csv)")
        if path:
            try:
                relative = Path(path).resolve().relative_to(project_root())
                self.weather_path_edit.setText(relative.as_posix())
            except ValueError:
                self.weather_path_edit.setText(path)

    def add_custom_thruster(self) -> None:
        dialog = ThrusterDialog(self)
        if dialog.exec() and dialog.record:
            self.custom_thrusters.append(dialog.record)
            self.structure_inputs[dialog.record.thruster_id] = deepcopy(dialog.structure_mass)
            self._mark_dirty()
            selected = set(self._selected_ids()) | {dialog.record.thruster_id}
            self._refresh_candidate_table(selected)
            for row in range(self.candidate_table.rowCount()):
                if self.candidate_table.item(row, 0).data(Qt.UserRole) == dialog.record.thruster_id:
                    self.candidate_table.selectRow(row)
                    self.candidate_table.scrollToItem(
                        self.candidate_table.item(row, 1),
                        QAbstractItemView.PositionAtCenter,
                    )
                    break

    def edit_candidate(self, row: int | None = None) -> None:
        if row is None or isinstance(row, bool):
            row = self.candidate_table.currentRow()
        if row < 0 or row >= self.candidate_table.rowCount():
            QMessageBox.information(self, "选择推进方案", "请先选中一个候选推进方案。")
            return
        candidate_id = self.candidate_table.item(row, 0).data(Qt.UserRole)
        existing = self._all_candidates()[row]
        preserve_id = row < len(self.custom_thrusters)
        dialog = ThrusterDialog(
            self, existing=existing, preserve_id=preserve_id,
            structure_mass=self.structure_inputs.get(candidate_id, StructureMassInput()),
        )
        if not dialog.exec() or dialog.record is None:
            return
        selected = set(self._selected_ids())
        if preserve_id:
            self.custom_thrusters[row] = dialog.record
        else:
            self.custom_thrusters.append(dialog.record)
            selected.add(dialog.record.thruster_id)
        self.structure_inputs[dialog.record.thruster_id] = deepcopy(dialog.structure_mass)
        self._mass_invalid.pop(dialog.record.thruster_id, None)
        self._mark_dirty()
        self._refresh_candidate_table(selected)
        for target_row in range(self.candidate_table.rowCount()):
            if (
                self.candidate_table.item(target_row, 0).data(Qt.UserRole)
                == dialog.record.thruster_id
            ):
                self.candidate_table.selectRow(target_row)
                self.candidate_table.scrollToItem(
                    self.candidate_table.item(target_row, 1),
                    QAbstractItemView.PositionAtCenter,
                )
                break

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "打开EP-VISTA项目", str(project_root() / "examples"), "EP-VISTA项目 (*.json)")
        if path:
            try:
                self._apply_project(ProjectCase.load(path))
            except Exception as exc:
                QMessageBox.critical(self, "无法打开项目", str(exc))

    def save_project(self) -> None:
        try:
            project = self._collect_project(validate=False)
        except Exception as exc:
            QMessageBox.warning(self, "输入有误", str(exc))
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存EP-VISTA项目", str(project_root() / "workspace" / "projects" / "project.ep-vista.json"), "EP-VISTA项目 (*.json)")
        if path:
            project.save(path)

    def clear_cache(self) -> None:
        if self.worker_thread is not None:
            QMessageBox.information(self, "计算进行中", "请先取消或等待当前计算完成后再清理缓存。")
            return
        cache = (project_root() / "workspace" / "cache").resolve()
        if QMessageBox.question(
            self,
            "清理缓存",
            f"仅删除EP-VISTA计算缓存：\n{cache}\n\n项目和已有结果文件不会删除。",
        ) != QMessageBox.Yes:
            return
        shutil.rmtree(cache, ignore_errors=True)
        cache.mkdir(parents=True, exist_ok=True)
        QMessageBox.information(self, "清理完成", "EP-VISTA计算缓存已清理。")

    def run_study(self) -> None:
        if self.worker_thread is not None:
            return
        try:
            project = self._collect_project()
        except Exception as exc:
            QMessageBox.warning(self, "输入有误", str(exc))
            return
        selected = set(project.selected_thruster_ids)
        candidates = [item for item in self._all_candidates() if item.thruster_id in selected]
        self._running_revision = self._input_revision
        self.run_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.worker_thread = QThread(self)
        worker = StudyWorker(deepcopy(project), deepcopy(candidates))
        self.study_worker = worker
        worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_result)
        worker.failed.connect(self._on_failure)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self.worker_thread.quit)
        worker.failed.connect(self.worker_thread.quit)
        worker.cancelled.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(worker.deleteLater)
        self.worker_thread.finished.connect(self._thread_finished)
        self.worker_thread.start()

    @Slot(int, str)
    def _on_progress(self, value, message) -> None:
        self.progress.setValue(value)
        self.progress_label.setText(message)

    @Slot(object)
    def _on_result(self, result) -> None:
        self.result = result
        self.cancel_button.setEnabled(False)
        self.progress.setValue(100)
        self.progress_label.setText("计算完成")
        self._show_result(result)
        self.view_results_button.setEnabled(True)
        if self._input_revision == self._running_revision:
            self.snapshot_label.setText(f"本次输入快照：{result.project.name}；生成于{result.generated_at_utc}")
        else:
            self.snapshot_label.setText("输入已修改，当前结果来自上次计算；高度扫描使用该次输入快照。")
        if not self._closing:
            self.show_results()

    @Slot(str)
    def _on_failure(self, detail) -> None:
        self.cancel_button.setEnabled(False)
        self.scan_accuracy.setEnabled(True)
        self.progress_label.setText("计算失败")
        if self.sensitivity_worker is not None:
            self.scan_progress_label.setText("高度扫描失败")
        if not self._closing:
            QMessageBox.critical(self, "计算失败", detail)

    def cancel_study(self) -> None:
        if self.study_worker is not None:
            self.study_worker.request_cancel()
        if self.sensitivity_worker is not None:
            self.sensitivity_worker.request_cancel()
        self.cancel_button.setEnabled(False)
        self.progress_label.setText("正在取消；当前NRLMSIS批次结束后停止")

    @Slot()
    def _on_cancelled(self) -> None:
        self.cancel_button.setEnabled(False)
        self.progress_label.setText("计算已取消")
        self.scan_accuracy.setEnabled(True)
        if self.sensitivity_worker is not None:
            self.scan_progress_label.setText("高度扫描已取消")

    @Slot()
    def _thread_finished(self) -> None:
        thread = self.worker_thread
        # finished() precedes deferred QObject/thread-local destruction. Keep
        # Python worker wrappers alive until native cleanup has really ended.
        if thread is not None and not thread.wait(0):
            QTimer.singleShot(10, self._thread_finished)
            return
        self.worker_thread = None
        self.study_worker = None
        self.sensitivity_worker = None
        if thread is not None:
            thread.deleteLater()
        self.run_button.setEnabled(True)
        self.scan_button.setEnabled(self.result is not None)
        self.scan_accuracy.setEnabled(True)
        if self._closing:
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event) -> None:
        if self.worker_thread is not None:
            if not self._closing and QMessageBox.question(
                self, "结束计算并退出", "当前仍在计算。是否取消计算，并在当前批次安全结束后退出？"
            ) != QMessageBox.Yes:
                event.ignore()
                return
            self._closing = True
            self.cancel_study()
            event.ignore()
            return
        self.results_window.hide()
        self.library_window.hide()
        event.accept()

    def _show_result(self, result) -> None:
        self._reset_scan_result()
        summary = result.summary_dict()
        self.card_labels["inclination"].setText(f"{result.demand.orbit.inclination_deg:.3f}°")
        period = summary["orbital_period_min"]
        self.card_labels["period"].setText("未确定" if period is None else f"{period:.2f} min")
        density_min, density_max = summary["density_min_kg_m3"], summary["density_max_kg_m3"]
        self.card_labels["density"].setText(f"{density_min:.3e}\n～ {density_max:.3e}")
        self.card_labels["density"].setToolTip(
            f"任务期间全部离散采样点的最小密度至最大密度：{density_min:.8e} ～ {density_max:.8e} kg/m³。"
        )
        self.card_labels["mean_drag"].setText(f"{result.demand.mean_drag_mN:.2f} mN")
        self.card_labels["max_drag"].setText(f"{result.demand.maximum_drag_mN:.2f} mN")
        self._show_power_and_candidates(result)

        candidates = result.candidate_snapshot
        self.scan_candidate.clear()
        for candidate in candidates:
            self.scan_candidate.addItem(candidate.name_zh, candidate.thruster_id)
        self._replace_plot_tabs(self.orbit_tab, [
            ("迎风面积", single_revolution_area_figure(result), None),
            ("阻力", single_revolution_drag_figure(result), result),
        ])
        mission_window = MissionTimeWindow(mission_drag_thrust_figure(result, candidates))
        old_mission_window = self.mission_tab.takeWidget()
        if old_mission_window is not None:
            old_mission_window.deleteLater()
        self.mission_tab.setWidget(mission_window)
        self.tabs.setCurrentWidget(self.mission_tab)

    def _show_power_and_candidates(self, result) -> None:
        power = result.power_assessment
        for key, value, unit in (
            ("impulse", result.demand.total_impulse_N_s, "N·s"),
            ("solar_power", power["solar_power_kW"], "kW"),
            ("solar_area", result.demand.solar_array_area_m2, "m²"),
            ("battery_power", power["battery_supply_power_kW"], "kW"),
            ("battery_energy", power["battery_configured_energy_kWh"], "kWh"),
        ):
            self.power_card_labels[key].setText(f"{value:,.4g} {unit}")
            self.power_card_labels[key].setToolTip(f"{value:.9g} {unit}")
        self.power_card_labels["battery_power"].setToolTip(
            f"受输出上限约束后的电池供电功率：{power['battery_supply_power_kW']:.9g} kW，"
            f"取所需补充功率{power['battery_required_power_kW']:.9g} kW与电池持续输出上限"
            f"{power['battery_max_power_kW']:.9g} kW的较小值。"
        )
        self.power_card_labels["battery_energy"].setToolTip(
            f"配置电量{power['battery_configured_energy_kWh']:.9g} kWh = 电池供电功率"
            f"{power['battery_supply_power_kW']:.9g} kW × 任务时长{result.project.mission.design_life_hours:g} h。"
            "这是按任务持续供电配置的电量，不是已知实物电池容量。"
        )
        self.power_summary_label.setText(power_summary_text(power))
        self.power_summary_label.setToolTip(power["notes"])
        self.power_summary_label.setStyleSheet(
            f"color:{'#B45309' if power['power_shortfall_kW'] > 1e-12 else '#61708B'};font-size:9pt"
        )

        # Join by candidate ID, never by the incidental order of mass rows.
        masses = {row["thruster_id"]: row for row in result.mass_breakdowns}
        self.result_table.setRowCount(len(result.assessments))
        for row, item in enumerate(result.assessments):
            mass = masses.get(item.thruster_id, {})
            values = {
                **mass, "name_zh": item.name_zh, "status": item.status,
                "required_power_kW": item.required_power_kW,
                "propellant_mass_kg": item.propellant_kg,
            }
            for column, (key, _) in enumerate(self.summary_columns):
                value = values.get(key)
                text = "未确定" if value is None else f"{value:.6g}" if isinstance(value, (int, float)) else str(value)
                cell = QTableWidgetItem(text)
                cell.setData(Qt.UserRole, value)
                cell.setToolTip(text if value is None or isinstance(value, str) else f"{value:.12g}")
                if key == "status":
                    cell.setToolTip(item.reason)
                    cell.setForeground(QColor("#2457C5" if item.status == "满足任务" else "#B45309"))
                self.result_table.setItem(row, column, cell)
        self.result_table.resizeColumnsToContents()
        self.result_table.setColumnWidth(0, 235)
        self._fit_summary_table(self.result_table)

    @staticmethod
    def _fit_summary_table(table):
        # Keep each section compact; large candidate lists scroll inside tables.
        rows_height = sum(table.rowHeight(row) for row in range(table.rowCount()))
        height = table.horizontalHeader().height() + rows_height + table.horizontalScrollBar().sizeHint().height() + 6
        table.setFixedHeight(min(360, max(140, height)))

    @staticmethod
    def _replace_plot_tabs(tabs: QTabWidget, items) -> None:
        while tabs.count():
            old = tabs.widget(0)
            tabs.removeTab(0)
            old.deleteLater()
        for title, content, hover_result in items:
            if isinstance(content, QWidget):
                canvas = content
            else:
                canvas = HoverCanvas(content, hover_result)
                canvas.setMinimumHeight(460)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(canvas)
            tabs.addTab(scroll, title)

    def run_sensitivity(self) -> None:
        if self.worker_thread is not None or self.result is None:
            return
        try:
            project = deepcopy(self.result.project)
            project.sampling.phase_step_deg = float(self.scan_accuracy.currentData())
            # Smaller batches provide several visible updates during each long
            # NRLMSIS calculation without changing the numerical result.
            project.sampling.batch_rows = min(project.sampling.batch_rows, 50_000)
            candidate_id = self.scan_candidate.currentData()
            candidate = next(item for item in self.result.candidate_snapshot if item.thruster_id == candidate_id)
        except Exception as exc:
            QMessageBox.warning(self, "输入有误", str(exc))
            return
        self.scan_button.setEnabled(False)
        self.scan_accuracy.setEnabled(False)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.scan_progress.setValue(0)
        self.scan_progress.show()
        self.scan_progress_label.show()
        self.scan_progress_label.setText("正在准备高度扫描")
        self._active_scan_accuracy_label = self.scan_accuracy.currentText()
        self._active_scan_phase_step_deg = project.sampling.phase_step_deg
        self.worker_thread = QThread(self)
        worker = SensitivityWorker(project, candidate, self.scan_min.value(), self.scan_max.value(), self.scan_step.value())
        self.sensitivity_worker = worker
        worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(worker.run)
        worker.finished.connect(self._show_sensitivity)
        worker.failed.connect(self._on_failure)
        worker.progress.connect(self._on_sensitivity_progress)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self.worker_thread.quit)
        worker.failed.connect(self.worker_thread.quit)
        worker.cancelled.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(worker.deleteLater)
        self.worker_thread.finished.connect(self._thread_finished)
        self.worker_thread.start()

    @Slot(int, str)
    def _on_sensitivity_progress(self, value: int, message: str) -> None:
        self._on_progress(value, message)
        self.scan_progress.setValue(value)
        self.scan_progress_label.setText(message)

    @Slot(object)
    def _show_sensitivity(self, rows) -> None:
        from matplotlib.figure import Figure

        self.scan_accuracy.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.scan_progress.setValue(100)
        self.scan_progress.show()
        self.scan_progress_label.show()
        self.scan_progress_label.setText(
            f"高度扫描完成：{self._active_scan_accuracy_label}"
        )
        while self.sensitivity_chart_host.count():
            item = self.sensitivity_chart_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.sensitivity_chart_host.setAlignment(Qt.Alignment())
        figure = Figure(figsize=(12, 4.6), dpi=105, facecolor="white")
        ax1, ax2, ax3 = figure.subplots(1, 3)
        altitude = [row.altitude_km for row in rows]
        ax1.plot(altitude, [row.mean_drag_mN for row in rows], "-o", color="#2457C5", label="平均阻力")
        ax1.plot(altitude, [row.maximum_drag_mN for row in rows], "--s", color="#D79B16", label="最大阻力")
        ax1.set_ylabel("阻力 (mN)")
        ax1.set_xlabel("SSO轨道高度 (km)")
        ax1.legend(frameon=False)
        ax1.grid(True, color="#D9DEE8")
        propellant = [row.propellant_kg for row in rows]
        if all(value is not None for value in propellant):
            ax2.plot(altitude, propellant, "-o", color="#D79B16")
            ax2.set_ylabel("推进剂 (kg)")
        else:
            ax2.text(0.5, 0.5, "该方案不携带推进剂", ha="center", va="center", transform=ax2.transAxes)
            ax2.set_ylabel("推进剂")
        ax2.set_xlabel("SSO轨道高度 (km)")
        ax2.grid(True, color="#D9DEE8")
        ax3.plot(
            altitude,
            [row.limiting_thrust_margin_mN or 0 for row in rows],
            "-o",
            color="#2457C5",
        )
        ax3.axhline(0, color="#172033", linestyle="--")
        ax3.set_xlabel("SSO轨道高度 (km)")
        ax3.set_ylabel("极限推力余量 (mN)")
        ax3.grid(True, color="#D9DEE8")
        precision_note = (
            "快速预览，不作为最终精确结果"
            if self._active_scan_phase_step_deg > 5.0
            else "详细计算"
        )
        figure.suptitle(
            "不同SSO轨道高度的任务结果\n"
            f"{precision_note}；每圈约{360 / self._active_scan_phase_step_deg:g}个采样点",
            fontsize=10.5,
            fontweight="bold",
        )
        figure.tight_layout(rect=(0, 0, 1, 0.86))
        canvas = FigureCanvas(figure)
        canvas.setMinimumSize(1100, 410)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(canvas)
        self.sensitivity_chart_host.addWidget(scroll)
