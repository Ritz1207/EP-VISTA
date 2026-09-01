"""V1.0 public metadata, baseline data and repository hygiene stay frozen."""

import csv
import json
from pathlib import Path
import re
import tomllib


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".cff", ".csv", ".json", ".md", ".py", ".toml", ".txt", ".yml"}


def public_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in {".git", "__pycache__", "workspace", "copyright_application"}
               for part in path.parts):
            continue
        yield path


def test_public_text_has_no_retired_identity_or_private_absolute_path():
    forbidden = (
        "Ritz1207" + chr(64) + "163.com",
        "D:" + "/Data/",
        "D:" + "\\Data\\",
        "C:" + "/" + "Users/",
        "C:" + "\\" + "Users\\",
        "/" + "Users/",
        "/" + "home/",
    )
    findings = []
    for path in public_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in forbidden:
            if marker in text:
                findings.append(f"{path.relative_to(ROOT)}: {marker}")
    assert findings == []


def test_v1_public_metadata_is_consistent_and_registration_is_excluded():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert project["version"] == "1.0"
    assert project["authors"] == [{"name": "Ritz"}]
    assert project["urls"] == {
        "Repository": "https://github.com/Ritz1207/EP-VISTA",
        "Issues": "https://github.com/Ritz1207/EP-VISTA/issues",
    }
    for value in (
        "超低轨道电推进系统方案权衡分析平台",
        "Electric Propulsion for VLEO Integrated System Trade Analysis",
        "EP-VISTA",
        "V1.0",
        "Ritz",
    ):
        assert value in readme + citation
    assert re.search(r'^version: "V1\.0"$', citation, re.MULTILINE)
    assert 'date-released: "2026-09-01"' in citation
    assert 'repository-code: "https://github.com/Ritz1207/EP-VISTA"' in citation
    assert "doi:" not in citation
    assert not (ROOT / "SOFTWARE_REGISTRATION.md").exists()
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/workspace/" in ignore
    assert "/copyright_application/" in ignore


def test_public_text_has_no_legal_identity():
    legal_identities = ("任" + "姿颖", "Ren" + "Ziying")
    findings = []
    for path in public_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for identity in legal_identities:
            if identity in text:
                findings.append(f"{path.relative_to(ROOT)}: {identity}")
    assert findings == []


def test_public_positioning_uses_platform_and_explains_sso_inputs():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "方案权衡工具" not in readme + citation
    assert "用于研究与方案分析的工具" not in readme
    assert "方案权衡分析平台" in readme
    assert "方案权衡的平台" in citation
    for term in ("轨道高度", "自动计算", "LTAN", "初始升交点赤经"):
        assert term in readme


def test_v1_thruster_csv_is_the_public_baseline_and_examples_are_scoped():
    with (ROOT / "data/thrusters/thrusters.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_ids = {
        "ENG_ABEP20",
        "Hall_01",
        "Hall_02",
        "Ion_01",
        "Customized_01",
        "Customized_02",
        "Customized_03",
        "Hall_03",
        "Hall_04",
        "Ion_02",
    }
    assert {row["thruster_id"] for row in rows} == expected_ids
    assert len(rows) == 10

    blank = json.loads((ROOT / "examples/new_project_template.ep-vista.json").read_text(encoding="utf-8"))
    assert blank["selected_thruster_ids"] == []
    assert blank["custom_thrusters"] == []
    assert blank["library_snapshot"] == []
    assert blank["propulsion_structure"] == {}

    demo = json.loads((ROOT / "examples/battery_mass_demo.ep-vista.json").read_text(encoding="utf-8"))
    assert set(demo["selected_thruster_ids"]) <= expected_ids
    assert demo["schema_version"] == "2.3"
    assert demo["mission"]["design_life_hours"] == 100.0
