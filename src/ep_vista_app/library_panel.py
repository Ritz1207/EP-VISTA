# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Cross-project library editor; project snapshots change only on explicit load."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ep_vista_core.library import (
    default_library_path, fingerprint, merged_library, read_library, save_thruster_library,
)
from ep_vista_core.models import ThrusterRecord
from ep_vista_core.paths import project_root

from .dialogs import ThrusterDialog


ARCHITECTURE_LABELS = {"traditional": "传统供质", "abep": "吸气式 ABEP"}


class LibraryPanel(QWidget):
    use_requested = Signal(object)

    def __init__(self, parent=None, *, path=None, backup_dir=None):
        super().__init__(parent)
        self.path = Path(path) if path is not None else default_library_path()
        self.backup_dir = Path(backup_dir) if backup_dir is not None else project_root() / "workspace/library_backups"
        self.records, self.version = read_library(self.path)
        layout = QVBoxLayout(self)
        self.hint = QLabel(
            "“新增记录”用于建立型号；“编辑记录”用于修改选中型号的ID、类型、性能、默认质量和来源。\n"
            "“删除选中记录”用于从型号库删除所选型号；保存前会确认并自动备份，已有项目不变。\n"
            "“导入CSV”用于合并外部型号数据；“导出CSV”用于保存完整型号库；“刷新”用于重读已保存的型号库。\n"
            "“载入本项目”用于将选中型号加入候选推进方案，同ID时确认覆盖；仅编辑型号库不会更新项目参数。"
        )
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索ID、名称或性能来源")
        self.search.textChanged.connect(self.refresh_table)
        layout.addWidget(self.search)
        actions = QHBoxLayout()
        for text, handler in (
            ("新增记录", self.add_record), ("编辑记录", self.edit_record),
            ("删除选中记录", self.delete_records),
            ("导入CSV", self.import_library), ("导出CSV", self.export_library),
            ("刷新", self.reload_library), ("载入本项目", self.use_records),
        ):
            button = QPushButton(text)
            if text != "载入本项目":
                button.setObjectName("secondary")
            button.clicked.connect(handler)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.table = QTableWidget(0, 13)
        self.table.setObjectName("evidenceTable")
        self.table.setHorizontalHeaderLabels([
            "ID", "设备/方案", "推进器类型", "推进方式", "推功比 (mN/kW)", "比冲 Isp (s)",
            "默认质量 (kg)", "功率范围 (kW)", "性能来源", "质量来源",
            "质量计入范围", "来源位置", "核验状态",
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalHeader().setDefaultSectionSize(36)
        for column, width in enumerate((115, 215, 105, 115, 155, 90, 135, 130, 240, 200, 350, 200, 245)):
            self.table.setColumnWidth(column, width)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self.edit_record())
        layout.addWidget(self.table)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh_table()

    def refresh_table(self, *_args):
        query = self.search.text().strip().casefold()
        records = [r for r in self.records if r.thruster_id != "ENG_ABEP20"
                   and (not query or query in
                        f"{r.thruster_id} {r.name_zh} {r.thruster_type} {r.source}".casefold())]
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            maximum = "不限" if record.maximum_power_kW is None else f"{record.maximum_power_kW:g}"
            values = [
                record.thruster_id, record.name_zh, record.thruster_type,
                ARCHITECTURE_LABELS.get(record.architecture, record.architecture),
                f"{record.thrust_to_power_mN_kW:g}", f"{record.isp_s:g}",
                "未知" if record.structure_mass_kg is None else f"{record.structure_mass_kg:g}",
                f"{record.minimum_power_kW:g}–{maximum}", record.source,
                record.structure_mass_source, record.structure_mass_notes,
                record.locator, record.verification_status,
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                cell.setData(Qt.UserRole, record.thruster_id)
                self.table.setItem(row, column, cell)
        self.status.setText(f"显示{len(records)}条；型号库：{self.path}\n"
                            "未知质量留空，0表示明确未计入。保存时自动备份；导出包含完整型号库。")

    def selected_records(self):
        ids = {self.table.item(index.row(), 0).data(Qt.UserRole)
               for index in self.table.selectionModel().selectedRows()}
        return [deepcopy(record) for record in self.records if record.thruster_id in ids]

    def _persist(self, records, *, dialog_parent=None):
        try:
            version = save_thruster_library(self.path, records, expected_hash=self.version,
                                           backup_dir=self.backup_dir)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(dialog_parent if dialog_parent is not None else self, "型号库未保存", str(exc))
            return False
        self.records, self.version = deepcopy(records), version
        self.refresh_table()
        self.status.setText("已保存到跨项目型号库。当前项目未自动更新；需要时请选中并载入。")
        return True

    def store_record(self, record, *, dialog_parent=None):
        owner = dialog_parent if dialog_parent is not None else self
        existing = next((r for r in self.records if r.thruster_id == record.thruster_id), None)
        if existing is not None and existing != record:
            if QMessageBox.question(owner, "覆盖同ID型号库记录",
                f"{record.thruster_id}已经存在。是否覆盖其性能、默认质量和来源？\n"
                "当前磁盘版本会备份，已有项目快照不会自动改变。") != QMessageBox.Yes:
                return False
        try:
            records = merged_library(self.records, [record], replace_existing=True)
        except ValueError as exc:
            QMessageBox.warning(owner, "记录无效", str(exc))
            return False
        return self._persist(records, dialog_parent=owner)

    def add_record(self):
        dialog = ThrusterDialog(self, id_editable=True,
                                unavailable_ids={record.thruster_id for record in self.records})
        dialog.setWindowTitle("新增跨项目型号库记录")
        if dialog.exec() and dialog.record:
            self.store_record(dialog.record)

    def edit_record(self):
        selected = self.selected_records()
        if len(selected) != 1:
            QMessageBox.information(self, "选择记录", "请选中一条型号库记录。")
            return
        record = selected[0]
        dialog = ThrusterDialog(
            self, existing=record, preserve_id=True,
            structure_mass=record.structure_mass_input(), id_editable=True,
            unavailable_ids={item.thruster_id for item in self.records
                             if item.thruster_id != record.thruster_id},
        )
        dialog.setWindowTitle("编辑跨项目型号库记录")
        if dialog.exec() and dialog.record:
            self.replace_record(record.thruster_id, dialog.record)

    def replace_record(self, original_id, record):
        if not any(item.thruster_id == original_id for item in self.records):
            QMessageBox.warning(self, "记录已变化", "原型号已不存在；请刷新型号库后重试。")
            return False
        if record.thruster_id != original_id and any(
            item.thruster_id == record.thruster_id for item in self.records
        ):
            QMessageBox.warning(self, "ID已存在", f"型号库中已存在ID：{record.thruster_id}。")
            return False
        records = [deepcopy(record) if item.thruster_id == original_id else deepcopy(item)
                   for item in self.records]
        return self._persist(records)

    def delete_records(self):
        selected = self.selected_records()
        if not selected:
            QMessageBox.information(self, "选择记录", "请选中要从型号库删除的记录。")
            return
        ids = [record.thruster_id for record in selected]
        remaining = [deepcopy(record) for record in self.records
                     if record.thruster_id not in set(ids)]
        if not remaining:
            QMessageBox.warning(self, "无法删除", "型号库至少需要保留一条记录。")
            return
        if QMessageBox.question(
            self,
            "删除型号库记录",
            f"将从型号库删除{len(ids)}条记录：{'、'.join(ids)}\n"
            "保存前会自动备份当前型号库；已有项目快照不会改变。是否继续？",
        ) != QMessageBox.Yes:
            return
        if self._persist(remaining):
            self.status.setText(
                f"已删除{len(ids)}条型号库记录：{'、'.join(ids)}。已有项目未改变。"
            )

    def import_library(self):
        filename, _ = QFileDialog.getOpenFileName(self, "导入推进器型号库", "", "CSV (*.csv)")
        if not filename:
            return
        try:
            incoming, _ = read_library(filename)
            old = {r.thruster_id: r for r in self.records}
            conflicts = [r.thruster_id for r in incoming if r.thruster_id in old and old[r.thruster_id] != r]
            unknown = sum(r.structure_mass_kg is None for r in incoming)
            details = (f"读取{len(incoming)}条，默认质量未知{unknown}条。\n"
                       f"同ID不同内容{len(conflicts)}条：" + "、".join(conflicts[:10]) +
                       "\n确认后合并到型号库；同ID冲突会覆盖性能和默认质量，已有项目不变。")
            if QMessageBox.question(self, "确认导入范围", details) != QMessageBox.Yes:
                return
            self._persist(merged_library(self.records, incoming, replace_existing=True))
        except (OSError, ValueError, UnicodeError) as exc:
            QMessageBox.warning(self, "无法导入", str(exc))

    def export_library(self):
        filename, _ = QFileDialog.getSaveFileName(self, "导出完整推进器型号库",
                                                 "thrusters.csv", "CSV (*.csv)")
        if not filename:
            return
        path = Path(filename)
        if path.resolve() == self.path.resolve():
            QMessageBox.warning(self, "请选择其他位置", "导出不能覆盖当前工作型号库。")
            return
        try:
            save_thruster_library(path, self.records, expected_hash=fingerprint(path))
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "无法导出", str(exc))
            return
        self.status.setText(f"已导出{len(self.records)}条记录：{path}；分享前请核对资料来源与权限。")

    def reload_library(self):
        try:
            records, version = read_library(self.path)
        except (OSError, ValueError, UnicodeError) as exc:
            QMessageBox.warning(self, "无法刷新", str(exc))
            return
        self.records, self.version = records, version
        self.refresh_table()

    def use_records(self):
        records = self.selected_records()
        if not records:
            QMessageBox.information(self, "选择记录", "请选择一条或多条型号库记录。")
            return
        self.use_requested.emit(records)
