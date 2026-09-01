# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Small dialogs kept separate from the main engineering workflow."""

from __future__ import annotations

import uuid
import math
from copy import deepcopy

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ep_vista_core.models import ThrusterRecord, StructureMassInput


class ThrusterDialog(QDialog):
    def __init__(
        self,
        parent=None,
        existing: ThrusterRecord | None = None,
        preserve_id: bool = False,
        structure_mass: StructureMassInput | None = None,
        id_editable: bool = False,
        unavailable_ids: set[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.existing = existing
        self.preserve_id = preserve_id
        self.unavailable_ids = set(unavailable_ids or ())
        self.structure_mass = deepcopy(structure_mass or StructureMassInput())
        if preserve_id:
            title = "编辑自定义推进方案"
        elif existing is not None:
            title = "复制为自定义推进方案"
        else:
            title = "添加自定义推进方案"
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)
        suggested_id = (
            existing.thruster_id
            if existing is not None and preserve_id
            else f"USER_{uuid.uuid4().hex[:8].upper()}"
        )
        self.id_edit = QLineEdit(suggested_id)
        self.id_edit.setEnabled(id_editable)
        self.id_edit.setToolTip(
            "型号库中可修改；ID用于识别记录，不能与已有型号重复。"
            if id_editable else "当前场景保持ID不变。"
        )
        self.name_edit = QLineEdit("自定义推进方案")
        self.thruster_type_combo = QComboBox()
        self.thruster_type_combo.addItem("霍尔", "霍尔")
        self.thruster_type_combo.addItem("离子", "离子")
        self.thruster_type_combo.addItem("其他", "其他")
        self.other_thruster_type_edit = QLineEdit()
        self.other_thruster_type_edit.setPlaceholderText("可输入具体类型，例如MPD；留空则保存为“其他”")
        self.architecture_combo = QComboBox()
        self.architecture_combo.addItem("传统供质", "traditional")
        self.architecture_combo.addItem("吸气式 ABEP", "abep")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("工程模型：推功比 + 比冲", "engineering")
        self.mode_combo.addItem("设备工作点：功率 + 推力 + 比冲", "device_point")
        self.thrust_power = self._spin(0.01, 500, 45, 2)
        self.power = self._spin(0.001, 100, 1, 3)
        self.thrust = self._spin(0.001, 10000, 45, 3)
        self.isp = self._spin(1, 20000, 3000, 0)
        self.minimum_power = self._spin(0, 100, 0, 3)
        self.maximum_power = self._spin(0, 100, 0, 3)
        self.intake_efficiency = self._spin(0.001, 1, 0.4, 3)
        self.structure_mass_edit = QLineEdit(
            "" if self.structure_mass.mass_kg is None else str(self.structure_mass.mass_kg)
        )
        self.structure_mass_edit.setPlaceholderText("未知可留空；0表示未计入")
        self.structure_mass_edit.setToolTip(f"{self.structure_mass.source}\n{self.structure_mass.notes}")
        form.addRow("型号ID", self.id_edit)
        form.addRow("方案名称", self.name_edit)
        form.addRow("推进器类型", self.thruster_type_combo)
        form.addRow("其他类型", self.other_thruster_type_edit)
        form.addRow("推进方式", self.architecture_combo)
        form.addRow("输入方式", self.mode_combo)
        form.addRow("推功比 (mN/kW)", self.thrust_power)
        form.addRow("设备功率 (kW)", self.power)
        form.addRow("设备推力 (mN)", self.thrust)
        form.addRow("比冲 Isp (s)", self.isp)
        form.addRow("最小工作功率 (kW)", self.minimum_power)
        form.addRow("最大工作功率 (kW，0表示未限定)", self.maximum_power)
        form.addRow("集气效率（仅ABEP）", self.intake_efficiency)
        form.addRow("结构质量 (kg)", self.structure_mass_edit)
        self.source_edit = QLineEdit(existing.source if existing else "用户输入")
        self.locator_edit = QLineEdit(existing.locator if existing else "")
        self.notes_edit = QLineEdit(existing.notes if existing else "")
        self.mass_source_edit = QLineEdit(self.structure_mass.source)
        self.mass_notes_edit = QLineEdit(self.structure_mass.notes)
        form.addRow("性能来源", self.source_edit)
        form.addRow("来源位置 / 链接", self.locator_edit)
        form.addRow("性能备注", self.notes_edit)
        form.addRow("质量来源", self.mass_source_edit)
        form.addRow("质量计入范围", self.mass_notes_edit)
        self.thrust_power_label = form.labelForField(self.thrust_power)
        self.power_label = form.labelForField(self.power)
        self.thrust_label = form.labelForField(self.thrust)
        self.minimum_power_label = form.labelForField(self.minimum_power)
        self.maximum_power_label = form.labelForField(self.maximum_power)
        self.intake_efficiency_label = form.labelForField(self.intake_efficiency)
        self.other_thruster_type_label = form.labelForField(self.other_thruster_type_edit)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_host)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(640, 640)
        self.mode_combo.currentIndexChanged.connect(self._update_mode)
        self.architecture_combo.currentIndexChanged.connect(self._update_mode)
        self.thruster_type_combo.currentIndexChanged.connect(self._update_mode)
        if existing is not None:
            self._load_existing(existing)
        self._update_mode()
        self.record: ThrusterRecord | None = None

    def _load_existing(self, record: ThrusterRecord) -> None:
        name = record.name_zh
        if not self.preserve_id:
            name = f"{name}（自定义）"
        self.name_edit.setText(name)
        type_index = self.thruster_type_combo.findData(record.thruster_type)
        if type_index >= 0:
            self.thruster_type_combo.setCurrentIndex(type_index)
        else:
            self.thruster_type_combo.setCurrentIndex(self.thruster_type_combo.findData("其他"))
            self.other_thruster_type_edit.setText(record.thruster_type)
        architecture_index = self.architecture_combo.findData(record.architecture)
        if architecture_index >= 0:
            self.architecture_combo.setCurrentIndex(architecture_index)
        self.mode_combo.setCurrentIndex(0)
        self.thrust_power.setValue(record.thrust_to_power_mN_kW)
        representative_power = (
            record.minimum_power_kW
            if record.minimum_power_kW > 0
            else min(record.maximum_power_kW or 1.0, 100.0)
        )
        self.power.setValue(representative_power)
        self.thrust.setValue(representative_power * record.thrust_to_power_mN_kW)
        self.isp.setValue(record.isp_s)
        self.minimum_power.setValue(record.minimum_power_kW)
        self.maximum_power.setValue(record.maximum_power_kW or 0.0)
        if record.intake_efficiency is not None:
            self.intake_efficiency.setValue(record.intake_efficiency)

    @staticmethod
    def _spin(minimum: float, maximum: float, value: float, decimals: int) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setValue(value)
        widget.setSingleStep(0.1 if decimals else 100)
        return widget

    def _update_mode(self) -> None:
        engineering = self.mode_combo.currentData() == "engineering"
        self._set_field_enabled(self.thrust_power, self.thrust_power_label, engineering)
        self._set_field_enabled(self.minimum_power, self.minimum_power_label, engineering)
        self._set_field_enabled(self.maximum_power, self.maximum_power_label, engineering)
        self._set_field_enabled(self.power, self.power_label, not engineering)
        self._set_field_enabled(self.thrust, self.thrust_label, not engineering)
        abep = self.architecture_combo.currentData() == "abep"
        self._set_field_enabled(
            self.intake_efficiency,
            self.intake_efficiency_label,
            abep,
        )
        other_type = self.thruster_type_combo.currentData() == "其他"
        self._set_field_enabled(
            self.other_thruster_type_edit,
            self.other_thruster_type_label,
            other_type,
        )

    @staticmethod
    def _set_field_enabled(widget, label, enabled: bool) -> None:
        widget.setEnabled(enabled)
        label.setEnabled(enabled)

    def _accept(self) -> None:
        thruster_id = self.id_edit.text().strip()
        if not thruster_id or thruster_id != self.id_edit.text():
            QMessageBox.warning(self, "输入有误", "型号ID不能为空，且首尾不能包含空白。")
            return
        if thruster_id in self.unavailable_ids:
            QMessageBox.warning(self, "ID已存在", f"型号库中已存在ID：{thruster_id}。请输入其他ID。")
            return
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "输入有误", "请输入方案名称。")
            return
        try:
            text = self.structure_mass_edit.text().strip()
            mass = float(text) if text else None
            if mass is not None and (not math.isfinite(mass) or mass < 0):
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "输入有误", "结构质量必须为有限非负数，或留空。")
            return
        architecture = self.architecture_combo.currentData()
        thruster_type = self.thruster_type_combo.currentData()
        if thruster_type == "其他":
            thruster_type = self.other_thruster_type_edit.text().strip() or "其他"
        if self.mode_combo.currentData() == "engineering":
            thrust_to_power = self.thrust_power.value()
            minimum_power = self.minimum_power.value()
            maximum_power = self.maximum_power.value() or None
        else:
            power = self.power.value()
            thrust_to_power = self.thrust.value() / power
            minimum_power = power
            maximum_power = power
        record = ThrusterRecord(
            thruster_id=thruster_id,
            name_zh=self.name_edit.text().strip(),
            architecture=architecture,
            propellant=(self.existing.propellant
                        if self.existing is not None and self.existing.architecture == architecture
                        else "air" if architecture == "abep" else "user_defined"),
            thrust_to_power_mN_kW=thrust_to_power,
            isp_s=self.isp.value(),
            thruster_type=thruster_type,
            minimum_power_kW=minimum_power,
            maximum_power_kW=maximum_power,
            intake_efficiency=self.intake_efficiency.value() if architecture == "abep" else None,
            power_basis="user input",
            data_type="user_input",
            metric_coincidence="same_user_input_point",
            source=self.source_edit.text().strip() or "用户输入",
            locator=self.locator_edit.text().strip(),
            verification_status="user_input",
            notes=self.notes_edit.text().strip() or "效率由推功比和比冲推导，不作为独立输入。",
        )
        try:
            record.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "参数不一致", str(exc))
            return
        self.record = record
        notes = self.mass_notes_edit.text().strip().replace(" 未计入。", "")
        mass_source = self.mass_source_edit.text().strip() or "用户输入"
        if mass != self.structure_mass.mass_kg and mass_source == self.structure_mass.source:
            mass_source = "用户输入"
        self.structure_mass = StructureMassInput(
            mass, mass_source,
            notes + (" 未计入。" if mass == 0 else ""),
        )
        self.record.structure_mass_kg = mass
        self.record.structure_mass_source = self.structure_mass.source
        self.record.structure_mass_notes = self.structure_mass.notes
        self.accept()
