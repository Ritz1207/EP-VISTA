# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Shared-library integrity, legacy migration and explicit project isolation."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ep_vista_core import models
from ep_vista_core.library import (
    default_library_path, fingerprint, merged_library, read_library,
    save_thruster_library, validate_library,
)
from ep_vista_core.models import ProjectCase, ThrusterRecord
from ep_vista_core.paths import project_root


def record(**changes):
    return replace(ThrusterRecord("TEST", "测试推进器", "traditional", "Xe", 40, 2000,
                                 structure_mass_kg=4, structure_mass_source="用户试验"), **changes)


def demo():
    project = ProjectCase.load(project_root() / "examples/battery_mass_demo.ep-vista.json")
    # The checked-in demonstration is user-editable; tests select a stable,
    # known record instead of inheriting its last interactive selection.
    project.library_snapshot = models.default_library_snapshot()
    project.custom_thrusters = []
    project.propulsion_structure = {
        item["thruster_id"]: ThrusterRecord(**item).structure_mass_input()
        for item in project.library_snapshot
    }
    project.selected_thruster_ids = ["Hall_01"]
    return project


def test_unified_defaults():
    records, _ = read_library(default_library_path())
    assert len(records) >= 10  # The user can add records to the shared library.
    hall_01 = next(r for r in records if r.thruster_id == "Hall_01")
    assert (hall_01.thrust_to_power_mN_kW, hall_01.structure_mass_kg) == (58.92, 3)
    assert hall_01.thruster_type == "霍尔"
    assert hall_01.source == "NASA Technical Reports Server"
    assert hall_01.structure_mass_source.startswith("https://www.researchgate.net/")
    assert not (default_library_path().parent / "structure_mass_examples.json").exists()


def test_unicode_roundtrip_and_unknown_vs_zero(tmp_path):
    path = tmp_path / "共享.csv"
    records = [record(notes='逗号,双引号"和换行\n均保留', structure_mass_kg=None),
               record(thruster_id="ZERO", structure_mass_kg=0)]
    token = save_thruster_library(path, records, expected_hash=None)
    actual, read_token = read_library(path)
    assert actual == records
    assert token == read_token == fingerprint(path)
    assert actual[0].structure_mass_kg is None
    assert actual[1].structure_mass_kg == 0


def test_legacy_performance_only_csv(tmp_path):
    path = tmp_path / "legacy.csv"
    path.write_text("thruster_id,name_zh,architecture,propellant,thrust_to_power_mN_kW,isp_s\n"
                    "OLD,旧参数,traditional,Xe,40,2000\n", encoding="utf-8-sig")
    records, _ = read_library(path)
    assert records[0].structure_mass_kg is None
    assert records[0].minimum_power_kW == 0
    assert records[0].thruster_type == "其他"


def test_legacy_csv_infers_known_type_without_rewriting_source(tmp_path):
    path = tmp_path / "legacy.csv"
    path.write_text("thruster_id,name_zh,architecture,propellant,thrust_to_power_mN_kW,isp_s\n"
                    "HET1,HET样机,traditional,Xe,40,2000\n"
                    "ION1,NSTAR离子推力器,traditional,Xe,40,2000\n", encoding="utf-8")
    before = path.read_bytes()
    records, _ = read_library(path)
    assert [item.thruster_type for item in records] == ["霍尔", "离子"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("changes", [
    {"structure_mass_kg": -1}, {"structure_mass_kg": float("nan")},
    {"maximum_power_kW": float("inf")}, {"minimum_power_kW": -1},
    {"minimum_power_kW": 3, "maximum_power_kW": 2}, {"maximum_power_kW": 0},
    {"thruster_id": " TEST "}, {"name_zh": " "}, {"isp_s": -1},
    {"thrust_to_power_mN_kW": 1000}, {"architecture": "abep", "intake_efficiency": None},
])
def test_invalid_record_never_overwrites(tmp_path, changes):
    path = tmp_path / "library.csv"
    token = save_thruster_library(path, [record()])
    with pytest.raises(ValueError):
        save_thruster_library(path, [record(**changes)], expected_hash=token)
    assert fingerprint(path) == token
    assert not list(tmp_path.glob("*.lock"))


@pytest.mark.parametrize("content", [
    "thruster_id,thruster_id\nA,A\n",
    "thruster_id,name_zh,architecture,propellant,thrust_to_power_mN_kW,isp_s,unknown\n",
    "thruster_id,name_zh,architecture,propellant,thrust_to_power_mN_kW,isp_s\nA,A,traditional,Xe,40\n",
    "thruster_id,name_zh,architecture,propellant,thrust_to_power_mN_kW,isp_s\nA,A,traditional,Xe,40,2000,extra\n",
])
def test_invalid_csv_rejected(tmp_path, content):
    path = tmp_path / "invalid.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_library(path)


def test_duplicate_ids_and_merge_confirmation():
    original = record()
    changed = record(structure_mass_kg=8)
    with pytest.raises(ValueError):
        validate_library([original, changed])
    with pytest.raises(ValueError):
        merged_library([original], [changed])
    merged = merged_library([original], [changed], replace_existing=True)
    assert merged[0].structure_mass_kg == 8
    merged[0].structure_mass_kg = 12
    assert original.structure_mass_kg == 4 and changed.structure_mass_kg == 8


def test_stale_write_and_backup(tmp_path):
    path, backups = tmp_path / "library.csv", tmp_path / "backups"
    token = save_thruster_library(path, [record()])
    token2 = save_thruster_library(path, [record(structure_mass_kg=5)],
                                  expected_hash=token, backup_dir=backups)
    assert read_library(next(backups.glob("*.csv")))[0] == [record()]
    with pytest.raises(RuntimeError, match="修改"):
        save_thruster_library(path, [record(structure_mass_kg=6)], expected_hash=token)
    assert fingerprint(path) == token2
    assert not path.with_suffix(".csv.lock").exists()


def test_existing_lock_preserved(tmp_path):
    path = tmp_path / "library.csv"
    token = save_thruster_library(path, [record()])
    lock = path.with_suffix(".csv.lock")
    lock.touch()
    with pytest.raises(RuntimeError, match="写入"):
        save_thruster_library(path, [record(structure_mass_kg=6)])
    assert lock.exists() and fingerprint(path) == token


def test_saved_project_does_not_read_changed_library(tmp_path, monkeypatch):
    project = demo()
    project.library_snapshot = [asdict(record())]
    project.selected_thruster_ids = ["TEST"]
    project.propulsion_structure = {"TEST": record().structure_mass_input()}
    saved = project.save(tmp_path / "project.ep-vista.json")
    monkeypatch.setattr(models, "default_library_snapshot", lambda: pytest.fail("读取了公共库"))
    reopened = ProjectCase.load(saved)
    assert reopened.library_snapshot == project.library_snapshot
    assert reopened.propulsion_structure["TEST"].mass_kg == 4
    assert reopened.schema_version == "2.3"
    reopened.library_snapshot[0]["structure_mass_kg"] = 10
    assert project.library_snapshot[0]["structure_mass_kg"] == 4


def test_legacy_project_preserves_explicit_mass_and_original_file(tmp_path, monkeypatch):
    raw = demo().to_dict()
    raw.pop("library_snapshot")
    raw["schema_version"] = "2.1"
    raw["propulsion_structure"] = {"TEST": {"mass_kg": 7, "source": "本项目", "notes": "含PPU"}}
    path = tmp_path / "old.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(models, "default_library_snapshot", lambda: [asdict(record())])
    project = ProjectCase.load(path)
    assert path.read_bytes() == before
    assert project.propulsion_structure["TEST"].mass_kg == 7
    assert project.library_snapshot[0]["structure_mass_kg"] == 4


def test_old_project_adds_type_in_memory_only_and_saves_as_23(tmp_path):
    raw = demo().to_dict()
    for item in raw["library_snapshot"]:
        item.pop("thruster_type", None)
    raw["schema_version"] = "2.2"
    source = tmp_path / "old-22.json"
    source.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    before = source.read_bytes()
    project = ProjectCase.load(source)
    assert source.read_bytes() == before
    assert project.schema_version == "2.3"
    assert all(item["thruster_type"] == "其他" for item in project.library_snapshot)
    upgraded = project.save(tmp_path / "upgraded.json")
    saved = json.loads(upgraded.read_text(encoding="utf-8"))
    assert saved["schema_version"] == "2.3"
    assert all("thruster_type" in item for item in saved["library_snapshot"])


def test_core_uses_snapshot_and_freezes_explicit_candidates(monkeypatch):
    from ep_vista_core import study
    project = demo()
    project.mission.design_life_hours = 0.02
    project.library_snapshot = [asdict(record(thruster_id="Hall_01", structure_mass_kg=4))]
    monkeypatch.setattr(study, "load_thruster_library", lambda _p: pytest.fail("读取了公共库"))
    result = study.run_case(project)
    assert result.candidate_snapshot[0].thrust_to_power_mN_kW == 40
    assert result.source_snapshot["candidate_parameter_basis"] == "project_snapshot"
    explicit = record(thruster_id="Hall_01", thrust_to_power_mN_kW=42)
    result = study.run_case(project, candidates=[explicit])
    assert result.project.library_snapshot == [asdict(explicit)]
    assert project.library_snapshot[0]["thrust_to_power_mN_kW"] == 40


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_library_panel_persists_across_instances_without_global_write(app, tmp_path):
    from ep_vista_app.library_panel import LibraryPanel
    path = tmp_path / "library.csv"
    save_thruster_library(path, [record()])
    first = LibraryPanel(path=path, backup_dir=tmp_path / "backups")
    assert first.store_record(record(thruster_id="SECOND"))
    second = LibraryPanel(path=path, backup_dir=tmp_path / "backups")
    assert len(second.records) == 2
    second.table.selectRow(1)
    emitted = []
    second.use_requested.connect(emitted.append)
    second.use_records()
    assert emitted[0][0].thruster_id == "SECOND"
    first.close()
    second.close()


def test_library_can_rename_id_and_delete_selected_record(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from ep_vista_app.library_panel import LibraryPanel
    path = tmp_path / "library.csv"
    backups = tmp_path / "backups"
    original = record(thruster_id="OLD", thruster_type="霍尔")
    other = record(thruster_id="KEEP", thruster_type="离子")
    save_thruster_library(path, [original, other])
    panel = LibraryPanel(path=path, backup_dir=backups)
    renamed = replace(original, thruster_id="NEW", thruster_type="MPD")
    assert panel.replace_record("OLD", renamed)
    persisted, _ = read_library(path)
    assert [item.thruster_id for item in persisted] == ["NEW", "KEEP"]
    assert persisted[0].thruster_type == "MPD"
    assert len(list(backups.glob("*.csv"))) == 1
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_kw: QMessageBox.Yes)
    row = next(row for row in range(panel.table.rowCount())
               if panel.table.item(row, 0).text() == "NEW")
    panel.table.selectRow(row)
    panel.delete_records()
    persisted, _ = read_library(path)
    assert [item.thruster_id for item in persisted] == ["KEEP"]
    assert len(list(backups.glob("*.csv"))) == 2
    assert "已删除1条" in panel.status.text()
    panel.close()


def test_library_rename_rejects_duplicate_and_delete_cancel_preserves_file(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from ep_vista_app.library_panel import LibraryPanel
    path = tmp_path / "library.csv"
    save_thruster_library(path, [record(thruster_id="A"), record(thruster_id="B")])
    panel = LibraryPanel(path=path, backup_dir=tmp_path / "backups")
    before = path.read_bytes()
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda _owner, title, body, *_a: warnings.append((title, body)))
    assert not panel.replace_record("A", record(thruster_id="B"))
    assert warnings[0][0] == "ID已存在"
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_kw: QMessageBox.No)
    panel.table.selectRow(0)
    panel.delete_records()
    assert path.read_bytes() == before
    assert not list((tmp_path / "backups").glob("*.csv"))
    panel.close()


def test_library_dialog_id_type_and_propulsion_method_are_distinct(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from ep_vista_app.dialogs import ThrusterDialog
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda _owner, title, body, *_a: warnings.append((title, body)))
    dialog = ThrusterDialog(existing=record(thruster_id="OLD", thruster_type="霍尔"),
                            preserve_id=True, id_editable=True, unavailable_ids={"TAKEN"})
    try:
        assert dialog.id_edit.isEnabled()
        assert dialog.id_edit.text() == "OLD"
        assert dialog.thruster_type_combo.currentText() == "霍尔"
        assert dialog.architecture_combo.currentText() == "传统供质"
        assert not dialog.other_thruster_type_edit.isEnabled()
        dialog.thruster_type_combo.setCurrentIndex(dialog.thruster_type_combo.findData("其他"))
        assert dialog.other_thruster_type_edit.isEnabled()
        dialog.other_thruster_type_edit.setText("MPD")
        dialog.architecture_combo.setCurrentIndex(dialog.architecture_combo.findData("abep"))
        dialog.id_edit.setText("NEW")
        dialog._accept()
        assert dialog.record.thruster_id == "NEW"
        assert dialog.record.thruster_type == "MPD"
        assert dialog.record.architecture == "abep"
        assert dialog.record.intake_efficiency is not None
    finally:
        dialog.close()
    duplicate = ThrusterDialog(id_editable=True, unavailable_ids={"TAKEN"})
    try:
        duplicate.id_edit.setText("TAKEN")
        duplicate._accept()
        assert duplicate.record is None
        assert warnings[-1][0] == "ID已存在"
    finally:
        duplicate.close()


def test_gui_library_access_and_explicit_load_isolation(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from ep_vista_app.main_window import MainWindow
    window = MainWindow()
    try:
        window.open_library()
        assert window.library_window.isVisible()
        assert window.library_panel.window() is window.library_window
        assert not window.results_window.isVisible()
        assert window.result is None
        original = demo()
        window._apply_project(original)
        library_before = deepcopy(window.library_panel.records)
        incoming = record(thruster_id="Hall_01", structure_mass_kg=8)
        monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_kw: QMessageBox.Yes)
        window._use_library_records([incoming])
        saved = window._collect_project()
        assert next(r for r in saved.library_snapshot if r["thruster_id"] == "Hall_01")["structure_mass_kg"] == 8
        assert saved.propulsion_structure["Hall_01"].mass_kg == 8
        assert window.library_panel.records == library_before
        window._apply_project(original)
        assert next(r for r in window.library if r.thruster_id == "Hall_01").thrust_to_power_mN_kW == 58.92
    finally:
        window.close()
        app.processEvents()


def test_open_project_dialog_starts_in_examples(app, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from ep_vista_app.main_window import MainWindow

    captured = {}

    def fake_open(_parent, title, directory, file_filter):
        captured.update(title=title, directory=directory, file_filter=file_filter)
        return "", ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_open)
    window = MainWindow()
    try:
        window.open_project()
        assert captured["title"] == "打开EP-VISTA项目"
        assert Path(captured["directory"]).resolve() == (project_root() / "examples").resolve()
        assert captured["file_filter"] == "EP-VISTA项目 (*.json)"
    finally:
        window.close()
        app.processEvents()


def test_dialog_combines_mass_sources_and_preserves_propellant(app):
    from ep_vista_app.dialogs import ThrusterDialog
    item = record()
    dialog = ThrusterDialog(existing=item, preserve_id=True, structure_mass=item.structure_mass_input())
    dialog.source_edit.setText("试验记录A")
    dialog.mass_source_edit.setText("称重记录B")
    dialog.structure_mass_edit.setText("6.5")
    dialog._accept()
    assert dialog.record.propellant == "Xe"
    assert dialog.record.structure_mass_kg == 6.5
    assert dialog.record.source == "试验记录A"
    assert dialog.record.structure_mass_source == "称重记录B"
    dialog.close()


def test_result_keeps_unselected_project_records():
    from ep_vista_core.study import run_case
    project = demo()
    project.mission.design_life_hours = 0.02
    result = run_case(project)
    assert len(result.project.library_snapshot) == len(project.library_snapshot)
    result.project.selected_thruster_ids = ["Hall_01", "Ion_01"]
    rerun = run_case(result.project)
    assert {r.thruster_id for r in rerun.candidate_snapshot} == {"Hall_01", "Ion_01"}


def test_changed_mass_does_not_inherit_old_source_automatically(app):
    from ep_vista_app.dialogs import ThrusterDialog
    item = record()
    dialog = ThrusterDialog(existing=item, preserve_id=True, structure_mass=item.structure_mass_input())
    dialog.structure_mass_edit.setText("8")
    dialog._accept()
    assert dialog.record.structure_mass_source == "用户输入"
    dialog.close()


def test_gui_csv_import_cancel_confirm_and_export(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from ep_vista_app.library_panel import LibraryPanel
    path, incoming, exported = [tmp_path / f"{name}.csv" for name in ("library", "incoming", "export")]
    original = save_thruster_library(path, [record()])
    save_thruster_library(incoming, [record(structure_mass_kg=8), record(thruster_id="SECOND")])
    panel = LibraryPanel(path=path, backup_dir=tmp_path / "backups")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_kw: (str(incoming), "CSV"))
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_kw: QMessageBox.No)
    panel.import_library()
    assert fingerprint(path) == original
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_kw: QMessageBox.Yes)
    panel.import_library()
    assert panel.records[0].structure_mass_kg == 8 and len(panel.records) == 2
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_kw: (str(exported), "CSV"))
    panel.export_library()
    assert read_library(exported)[0] == panel.records
    panel.close()


def test_library_controls_belong_to_candidate_section_and_window_is_separate(app):
    from PySide6.QtWidgets import QPushButton, QTabWidget
    from ep_vista_app.main_window import MainWindow
    window = MainWindow()
    try:
        assert window.candidates_group.isAncestorOf(window.library_button)
        assert window.candidates_group.isAncestorOf(window.collect_library_button)
        actions = window.candidates_group.layout().itemAt(0).layout()
        assert actions.itemAt(0).widget() is window.library_button
        assert actions.itemAt(1).widget() is window.collect_library_button
        assert window.library_button.text() == "推进器型号库"
        assert not window.collect_library_button.isEnabled()
        window.library_button.click()
        assert window.library_window.isVisible()
        assert window.library_window.windowTitle() == "EP-VISTA — 推进器型号库"
        assert not window.library_window.findChildren(QTabWidget)
        buttons = [b.text() for b in window.library_panel.findChildren(QPushButton)]
        assert "收录本项目方案" not in buttons
        assert buttons == ["新增记录", "编辑记录", "删除选中记录", "导入CSV", "导出CSV", "刷新", "载入本项目"]
        assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
            "任务全程推阻关系", "绕地一周", "高度扫描", "结论"]
        for label in buttons:
            assert f"“{label}”用于" in window.library_panel.hint.text()
        assert not window.results_window.isVisible()
        window.library_window.close()
        assert not window.library_window.isVisible()
        window.library_button.click()
        assert window.library_window.isVisible()
    finally:
        window.close()
        assert not window.library_window.isVisible()
        app.processEvents()


def test_empty_project_stays_empty_until_explicit_load_and_roundtrips(app, tmp_path):
    from ep_vista_app.main_window import MainWindow
    window = MainWindow()
    try:
        token = fingerprint(default_library_path())
        assert window.candidate_table.rowCount() == 0
        assert window.library == []
        assert window.structure_inputs == {}
        empty = window._collect_project(validate=False)
        path = empty.save(tmp_path / "empty.ep-vista.json")
        window._apply_project(ProjectCase.load(path))
        assert window.candidate_table.rowCount() == 0
        window.open_library()
        assert window.candidate_table.rowCount() == 0
        window.library_panel.table.selectRow(0)
        window.library_panel.use_records()
        assert window.candidate_table.rowCount() == 1
        assert window._selected_ids() == ["Hall_01"]
        assert window.empty_candidates_label.isHidden()
        loaded = window._collect_project(validate=False)
        assert len(loaded.library_snapshot) == 1
        loaded.selected_thruster_ids = []  # Unchecked is not removed from project.
        loaded.save(path)
        window._load_template()
        assert window.candidate_table.rowCount() == 0
        window._apply_project(ProjectCase.load(path))
        assert window.candidate_table.rowCount() == 1
        assert window._selected_ids() == []
        assert fingerprint(default_library_path()) == token
    finally:
        window.close()
        app.processEvents()


def test_collect_from_candidate_toolbar_without_opening_library(app, tmp_path):
    from ep_vista_app.main_window import MainWindow
    window = MainWindow()
    try:
        path = tmp_path / "library.csv"
        save_thruster_library(path, [record(thruster_id="OTHER")])
        panel = window.library_panel
        panel.path, panel.backup_dir = path, tmp_path / "backups"
        panel.reload_library()
        window._use_library_records([record()])
        window.candidate_table.item(0, 5).setText("8.5")
        window.candidate_table.setCurrentCell(0, 1)
        assert window.collect_library_button.isEnabled()
        window.collect_library_button.click()
        stored = next(r for r in read_library(path)[0] if r.thruster_id == "TEST")
        assert stored.structure_mass_kg == 8.5
        assert "已将" in window.progress_label.text()
        assert not window.library_window.isVisible()
        assert not window.results_window.isVisible()
    finally:
        window.close()
        app.processEvents()


def test_collect_overwrite_confirmation_is_owned_by_input_window(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from ep_vista_app.main_window import MainWindow
    window = MainWindow()
    try:
        path = tmp_path / "library.csv"
        token = save_thruster_library(path, [record()])
        panel = window.library_panel
        panel.path, panel.backup_dir = path, tmp_path / "backups"
        panel.reload_library()
        window._use_library_records([record(structure_mass_kg=9)])
        window.candidate_table.setCurrentCell(0, 1)
        owners = []
        def decline(owner, *_args):
            owners.append(owner)
            return QMessageBox.No
        monkeypatch.setattr(QMessageBox, "question", decline)
        window.collect_library_button.click()
        assert owners == [window]
        assert fingerprint(path) == token
        assert not window.library_window.isVisible()
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("origin", ["custom", "library"])
def test_remove_candidate_cleans_project_and_roundtrips(app, tmp_path, monkeypatch, origin):
    from PySide6.QtWidgets import QMessageBox
    from ep_vista_app.main_window import MainWindow
    window = MainWindow()
    try:
        token = fingerprint(default_library_path())
        item = record()
        if origin == "custom":
            window.custom_thrusters = [item]
            window.structure_inputs[item.thruster_id] = item.structure_mass_input()
            window._refresh_candidate_table({item.thruster_id})
        else:
            window._use_library_records([item])
        window.candidate_table.setCurrentCell(0, 1)
        window.candidate_table.item(0, 5).setText("bad mass")
        assert item.thruster_id in window._mass_invalid
        assert window.remove_candidate_button.isEnabled()
        revision = window._input_revision
        monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.Yes)
        window.remove_candidate_button.click()
        assert window.candidate_table.rowCount() == 0
        assert not window.remove_candidate_button.isEnabled()
        assert not window.collect_library_button.isEnabled()
        assert window.structure_inputs == {} and window._mass_invalid == {}
        assert window._selected_ids() == []
        assert window._input_revision > revision
        project = window._collect_project(validate=False)
        saved = project.save(tmp_path / "removed.ep-vista.json")
        window._apply_project(ProjectCase.load(saved))
        assert window.candidate_table.rowCount() == 0
        assert window.library == [] and window.custom_thrusters == []
        with pytest.raises(ValueError, match="至少选择"):
            window._collect_project()
        assert fingerprint(default_library_path()) == token
    finally:
        window.close()
        app.processEvents()


def test_remove_cancel_preserves_project(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from ep_vista_app.main_window import MainWindow
    window = MainWindow()
    try:
        window._use_library_records([record(), record(thruster_id="SECOND")])
        window.candidate_table.setCurrentCell(0, 1)
        before = window._collect_project(validate=False).to_dict()
        revision = window._input_revision
        monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.No)
        window.remove_candidate_button.click()
        assert window._collect_project(validate=False).to_dict() == before
        assert window._input_revision == revision
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("row", [0, 1])
def test_remove_only_selected_occurrence_of_duplicate_id(app, monkeypatch, row):
    from PySide6.QtWidgets import QMessageBox
    from ep_vista_app.main_window import MainWindow
    window = MainWindow()
    try:
        window.custom_thrusters = [record(name_zh="本项目参数", thrust_to_power_mN_kW=41)]
        window.library = [record(name_zh="型号库参数")]
        window.structure_inputs["TEST"] = record(structure_mass_kg=7).structure_mass_input()
        window._refresh_candidate_table({"TEST"})
        assert window.candidate_table.item(0, 1).text().startswith("【自定义】")
        assert window.candidate_table.item(1, 1).text() == "型号库参数"
        with pytest.raises(ValueError, match="重复ID"):
            window._collect_project()
        window.candidate_table.setCurrentCell(row, 1)
        monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.Yes)
        window.remove_candidate_button.click()
        assert len(window._all_candidates()) == 1
        assert window._all_candidates()[0].name_zh == ("型号库参数" if row == 0 else "本项目参数")
        assert window.structure_inputs["TEST"].mass_kg == 7
        assert window._selected_ids() == ["TEST"]
    finally:
        window.close()
        app.processEvents()


def test_remove_keeps_other_check_states_and_existing_result(app, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox
    from ep_vista_app.main_window import MainWindow
    from ep_vista_core.study import run_case
    window = MainWindow()
    try:
        project = demo()
        project.mission.design_life_hours = 0.02
        result = run_case(project)
        window.result = result
        snapshot = deepcopy(result.project.to_dict())
        window._use_library_records([record(), record(thruster_id="SECOND"), record(thruster_id="THIRD")])
        window.candidate_table.item(1, 0).setCheckState(Qt.Unchecked)
        window.candidate_table.setCurrentCell(0, 1)
        monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.Yes)
        window.remove_candidate_button.click()
        assert [r.thruster_id for r in window._all_candidates()] == ["SECOND", "THIRD"]
        assert window._selected_ids() == ["THIRD"]
        assert result.project.to_dict() == snapshot
        assert "输入已修改" in window.snapshot_label.text()
        assert window.candidate_table.currentRow() == 0
    finally:
        window.close()
        app.processEvents()


def test_legacy_project_does_not_duplicate_collected_custom_record(tmp_path, monkeypatch):
    from ep_vista_core.study import run_case
    raw = demo().to_dict()
    raw.pop("library_snapshot")
    raw["schema_version"] = "2.1"
    custom = record(thruster_id="Hall_01", thrust_to_power_mN_kW=40)
    raw["custom_thrusters"] = [asdict(custom)]
    raw["mission"]["design_life_hours"] = 0.02
    # A newer library value must not replace the project's earlier input.
    monkeypatch.setattr(models, "default_library_snapshot", lambda: [asdict(replace(custom, thrust_to_power_mN_kW=45))])
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    token = fingerprint(path)
    project = ProjectCase.load(path)
    assert project.library_snapshot == []
    assert project.custom_thrusters == [asdict(custom)]
    result = run_case(project)
    assert len(result.candidate_snapshot) == 1
    assert result.candidate_snapshot[0].thrust_to_power_mN_kW == 40
    assert fingerprint(path) == token


def test_lazy_save_and_run_exclude_custom_ids_from_default_library(tmp_path, monkeypatch):
    from ep_vista_core import study
    project = demo()
    project.mission.design_life_hours = 0.02
    custom = record(thruster_id="Hall_01")
    project.custom_thrusters = [asdict(custom)]
    project.library_snapshot = None
    public = replace(custom, thrust_to_power_mN_kW=45)
    monkeypatch.setattr(models, "default_library_snapshot", lambda: [asdict(public)])
    monkeypatch.setattr(study, "load_thruster_library", lambda _path: [public])
    result = study.run_case(project)
    assert len(result.candidate_snapshot) == 1
    assert result.candidate_snapshot[0].thrust_to_power_mN_kW == 40
    assert project.library_snapshot is None
    project.save(tmp_path / "saved.json")
    assert project.library_snapshot == []


def test_explicit_conflicting_snapshot_is_not_silently_discarded():
    from ep_vista_core.study import run_case
    raw = demo().to_dict()
    raw["library_snapshot"] = [asdict(record(thruster_id="Hall_01"))]
    raw["custom_thrusters"] = [asdict(record(thruster_id="Hall_01", thrust_to_power_mN_kW=41))]
    project = ProjectCase.from_dict(raw)
    assert len(project.library_snapshot) == len(project.custom_thrusters) == 1
    with pytest.raises(ValueError, match="重复"):
        run_case(project)


def test_source_terminology_has_no_obsolete_project_or_library_labels():
    import ast
    for path in (project_root() / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "资料库" not in node.value, (path.name, node.lineno)
                if "工程" in node.value:
                    assert node.value == "工程模型：推功比 + 比冲", (path.name, node.lineno)
                assert "推力/功率比" not in node.value, (path.name, node.lineno)


def test_project_button_dialog_and_parameter_labels_are_consistent(app, monkeypatch):
    from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton
    from ep_vista_app.dialogs import ThrusterDialog
    from ep_vista_app.main_window import MainWindow
    window = MainWindow()
    try:
        assert window.windowTitle() == "EP-VISTA — 项目设置"
        assert window.name_edit.text() == "新建EP-VISTA项目"
        assert window.collect_library_button.text() == "收录本项目方案"
        assert "载入本项目" in [button.text() for button in window.library_panel.findChildren(QPushButton)]
        assert window.candidate_table.horizontalHeaderItem(2).text().splitlines()[0] == "推功比"
        assert window.library_panel.table.horizontalHeaderItem(2).text() == "推进器类型"
        assert window.library_panel.table.horizontalHeaderItem(3).text() == "推进方式"
        assert window.library_panel.table.horizontalHeaderItem(5).text() == "比冲 Isp (s)"
        assert any("任务设计寿命" in label.text() for label in window.findChildren(QLabel))
        dialog = ThrusterDialog(window)
        assert dialog.mode_combo.itemText(0) == "工程模型：推功比 + 比冲"
        dialog.close()
        window._use_library_records([record()])
        window.candidate_table.setCurrentCell(0, 1)
        messages = []
        def decline(_owner, title, body, *_args):
            messages.append((title, body))
            return QMessageBox.No
        monkeypatch.setattr(QMessageBox, "question", decline)
        window.remove_candidate_button.click()
        assert messages[0][0] == "从本项目移除方案"
        assert "请保存项目" in messages[0][1]
        assert "工程" not in messages[0][1]
        assert window.candidate_table.rowCount() == 1
    finally:
        window.close()
        app.processEvents()


def test_report_module_and_gui_entry_are_removed(app):
    import importlib.util
    from PySide6.QtWidgets import QPushButton
    from ep_vista_app.main_window import MainWindow
    from ep_vista_core import plots
    assert not (project_root() / "src/ep_vista_core/export.py").exists()
    assert importlib.util.find_spec("ep_vista_core.export") is None
    assert not hasattr(plots, "all_baseline_figures")
    assert not hasattr(plots, "orbit_geometry_figure")
    window = MainWindow()
    try:
        assert not hasattr(window, "export_current")
        assert not hasattr(window, "export_button")
        assert not any(button.text() == "导出报告" for button in window.findChildren(QPushButton))
        assert "导出CSV" in [button.text() for button in window.library_panel.findChildren(QPushButton)]
    finally:
        window.close()
        app.processEvents()


def test_result_and_plot_tabs_still_work_without_report_export(app):
    from PySide6.QtWidgets import QTabWidget
    from ep_vista_app.main_window import MainWindow, MissionTimeWindow
    from ep_vista_core.study import run_case
    project = demo()
    project.mission.design_life_hours = 0.02
    result = run_case(project)
    window = MainWindow()
    try:
        window._on_result(result)
        assert window.view_results_button.isEnabled()
        assert window.results_window.isVisible()
        assert window.result_table.rowCount() == len(result.assessments)
        assert window.tabs.currentWidget() is window.mission_tab
        assert isinstance(window.mission_tab.widget(), MissionTimeWindow)
        assert not window.mission_tab.findChildren(QTabWidget)
        assert window.orbit_tab.count() == 2
        window._mark_dirty()
        assert "高度扫描" in window.snapshot_label.text()
        assert "导出" not in window.snapshot_label.text()
    finally:
        window.close()
        app.processEvents()


def test_cli_run_prints_conclusion_without_creating_reports(tmp_path, capsys):
    from ep_vista_core.cli import main
    project = demo()
    project.mission.design_life_hours = 0.02
    path = project.save(tmp_path / "short.ep-vista.json")
    output_dir = project_root() / "workspace/exports"
    before = set(output_dir.rglob("*")) if output_dir.exists() else set()
    assert main(["run", str(path)]) == 0
    output = capsys.readouterr().out
    assert "[100%]" in output
    assert "结果已保存" not in output
    assert set(tmp_path.iterdir()) == {path}
    assert (set(output_dir.rglob("*")) if output_dir.exists() else set()) == before


def test_cli_rejects_retired_report_output_option(capsys):
    from ep_vista_core.cli import build_parser
    parser = build_parser()
    assert "导出结果" not in parser.format_help()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["run", "example.json", "--output", "reports"])
    assert exc.value.code == 2
    assert "--output" in capsys.readouterr().err


def mission_plot_case(abep_count=1):
    """Synthetic force samples: two full revolutions and a final half orbit."""
    from types import SimpleNamespace
    import numpy as np
    candidates = [record(thruster_id="TRAD", name_zh="传统方案")]
    for index in range(abep_count):
        name = "ABEP（自定义）" if index == 0 else f"ABEP（自定义{index + 1}）"
        candidates.append(record(thruster_id=f"ABEP{index}", name_zh=name,
                                 architecture="abep", propellant="air", intake_efficiency=0.6))
    phase = np.arange(0.0, 901.0, 45.0)
    project = demo()
    project.mission.design_life_hours = 3.75
    project.power.propulsion_power_kW = 1.0
    project.selected_thruster_ids = [item.thruster_id for item in candidates]
    demand = SimpleNamespace(
        orbit=SimpleNamespace(elapsed_seconds=phase * 15.0, phase_unwrapped_deg=phase,
                              speed_m_s=np.full(phase.shape, 7800.0)),
        atmosphere=SimpleNamespace(mass_density_kg_m3=(3 + 2 * np.cos(np.deg2rad(phase))) * 1e-10),
        drag_mN=20 + 10 * np.sin(np.deg2rad(phase)), intake_area_m2=1.0,
    )
    return SimpleNamespace(project=project, demand=demand), candidates


def test_abep_legend_identifies_mean_and_range_without_changing_statistics():
    import numpy as np
    from ep_vista_core.orbit_statistics import OrbitReducer
    from ep_vista_core.plots import mission_drag_thrust_figure
    from ep_vista_core.propulsion import available_thrust_profile
    result, candidates = mission_plot_case(abep_count=2)
    figure = mission_drag_thrust_figure(result, candidates)
    try:
        axis = figure.axes[0]
        expected_labels = ["整星阻力范围", "整星平均阻力", "传统方案"]
        reducer = OrbitReducer(result.demand.orbit.elapsed_seconds / 3600,
                               result.demand.orbit.phase_unwrapped_deg)
        for candidate in candidates[1:]:
            range_label = f"{candidate.name_zh}推力范围"
            mean_label = f"{candidate.name_zh}平均推力"
            expected_labels.extend([range_label, mean_label])
            values, _, _ = available_thrust_profile(result.demand, candidate, 1.0)
            stats = reducer.reduce(values)
            assert len(stats.mean) == 3  # The final partial revolution is retained.
            curve = next(line for line in axis.lines if line.get_label() == mean_label)
            band = next(item for item in axis.collections if item.get_label() == range_label)
            np.testing.assert_allclose(curve.get_xdata(), stats.time)
            np.testing.assert_allclose(curve.get_ydata(), stats.mean)
            assert band.get_alpha() == 0.16
            for time, lower, upper in zip(stats.time, stats.minimum, stats.maximum):
                vertices = band.get_paths()[0].vertices
                values_at_time = vertices[np.isclose(vertices[:, 0], time), 1]
                assert values_at_time.min() == pytest.approx(lower)
                assert values_at_time.max() == pytest.approx(upper)
        assert [text.get_text() for text in figure.legends[0].get_texts()] == expected_labels
        assert not any("ABEP" in label and "阻力" in label for label in expected_labels)
    finally:
        figure.clear()


@pytest.mark.parametrize("abep_count", [0, 1, 4, 12])
def test_mission_plot_explanation_is_separate_and_header_does_not_overlap(abep_count):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from ep_vista_core.plots import mission_drag_thrust_figure
    result, candidates = mission_plot_case(abep_count)
    figure = mission_drag_thrust_figure(result, candidates)
    try:
        texts = [text.get_text() for text in figure.texts]
        explanation = "所谓平均是指：按圈时间平均，末尾不足一圈按实际时段计入"
        assert texts.count(explanation) == 1
        assert not any("含太阳翼" in text for text in texts)
        assert "起始UTC" in texts[1] and explanation not in texts[1]
        canvas = FigureCanvasAgg(figure)
        canvas.draw()
        renderer = canvas.get_renderer()
        boxes = [text.get_window_extent(renderer) for text in figure.texts]
        assert boxes[0].y0 > boxes[1].y1
        assert boxes[1].y0 > boxes[2].y1
        legend = figure.legends[0].get_window_extent(renderer)
        assert boxes[2].y0 > legend.y1
        assert legend.y0 > figure.axes[0].get_window_extent(renderer).y1
        assert legend.x0 >= 0 and legend.x1 <= figure.bbox.width
    finally:
        figure.clear()


def test_footer_notice_is_identical_subtle_and_outside_scrolling_content(app):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea
    from ep_vista_app.main_window import MainWindow
    expected = ("Copyright © 2026 Ritz · "
                "分析结果仅供参考，请结合模型假设与数据适用范围核验。")
    window = MainWindow()
    try:
        window.show()
        window.results_window.show()
        window.library_window.show()
        app.processEvents()
        for owner, label in ((window, window.footer_label),
                             (window.results_window, window.results_footer_label),
                             (window.library_window, window.library_footer_label)):
            assert label.window() is owner
            assert label.text() == expected
            assert label.textFormat() == Qt.PlainText
            assert label.isVisible() and label.wordWrap()
            assert label.font().pointSizeF() == pytest.approx(8)
            assert not label.font().bold()
            assert label.focusPolicy() == Qt.NoFocus
            parent = label.parentWidget()
            assert parent.layout().itemAt(parent.layout().count() - 1).widget() is label
            assert not isinstance(parent, QScrollArea)
            assert label.height() >= label.heightForWidth(label.width())
    finally:
        window.close()
        app.processEvents()


def test_flat_mission_page_replaces_old_plot_and_keeps_time_navigation(app):
    from PySide6.QtWidgets import QTabWidget
    from ep_vista_app.main_window import MainWindow, MissionTimeWindow
    from ep_vista_core.study import run_case
    project = demo()
    project.mission.design_life_hours = 0.02
    result = run_case(project)
    window = MainWindow()
    try:
        window._on_result(result)
        old = window.mission_tab.widget()
        window._on_result(result)
        assert window.mission_tab.widget() is not old
        assert len(window.mission_tab.findChildren(MissionTimeWindow)) == 1
        assert not window.mission_tab.findChildren(QTabWidget)
        assert window.tabs.tabText(0) == "任务全程推阻关系"
        assert window.tabs.currentWidget() is window.mission_tab
        assert not window.mission_tab.widget().scrollbar.isEnabled()
        assert window.orbit_tab.count() == 2
        # No physical calculation is required to check a long timeline.
        timeline = window.mission_tab.widget()
        timeline.full_end = 1000
        timeline.window_span = 168
        timeline.scrollbar.setEnabled(True)
        timeline.scrollbar.setValue(1000)
        assert timeline.axis.get_xlim() == pytest.approx((832, 1000))
        assert timeline.range_label.text() == "832–1000 h"
    finally:
        window.close()
        app.processEvents()
