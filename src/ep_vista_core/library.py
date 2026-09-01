# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Unified, cross-project thruster library with validated atomic CSV writes."""
from __future__ import annotations

from copy import deepcopy
import csv
from dataclasses import asdict, fields
from datetime import datetime
import hashlib
import io
import math
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from .models import ThrusterRecord
from .paths import project_root

REQUIRED = {"thruster_id", "name_zh", "architecture", "propellant",
            "thrust_to_power_mN_kW", "isp_s"}
NUMERIC = {"thrust_to_power_mN_kW", "isp_s", "minimum_power_kW",
           "maximum_power_kW", "intake_efficiency", "structure_mass_kg"}
_UNSET = object()


def infer_legacy_thruster_type(thruster_id: str, name: str) -> str:
    """Best-effort display migration for CSVs created before this field existed."""
    text = f"{thruster_id} {name}".casefold()
    if any(token.casefold() in text for token in ("HET", "TAL", "BHT", "PPS", "Hall")):
        return "霍尔"
    if any(token.casefold() in text for token in
           ("NEXT", "NSTAR", "离子推力器", "ion thruster", "gridded ion", "QinetiQ T5", "IT（")):
        return "离子"
    return "其他"


def default_library_path() -> Path:
    return project_root() / "data/thrusters/thrusters.csv"


def fingerprint(path: str | Path) -> str | None:
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def validate_library(records: list[ThrusterRecord]) -> None:
    if not records:
        raise ValueError("型号库至少需要一条记录。")
    ids = set()
    for record in records:
        if not record.thruster_id.strip() or not record.name_zh.strip():
            raise ValueError("型号库ID和名称不能为空。")
        if record.thruster_id != record.thruster_id.strip():
            raise ValueError("型号库ID首尾不能包含空白。")
        if record.thruster_id in ids:
            raise ValueError(f"型号库ID重复：{record.thruster_id}")
        ids.add(record.thruster_id)
        record.validate()
        for key in NUMERIC:
            value = getattr(record, key)
            if value is not None and (isinstance(value, bool) or not math.isfinite(value)):
                raise ValueError(f"{record.thruster_id}的{key}必须是有限数值。")
        if record.minimum_power_kW < 0:
            raise ValueError("最小功率不能为负数。")
        if record.maximum_power_kW is not None and (
            record.maximum_power_kW <= 0 or record.maximum_power_kW < record.minimum_power_kW
        ):
            raise ValueError("最大功率须为正数且不小于最小功率；不限时留空。")
        if record.structure_mass_kg is not None and record.structure_mass_kg < 0:
            raise ValueError("默认结构质量不能为负数；未知时留空。")


def read_library(path: str | Path) -> tuple[list[ThrusterRecord], str]:
    raw = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    columns = reader.fieldnames or []
    known = {field.name for field in fields(ThrusterRecord)}
    if len(columns) != len(set(columns)):
        raise ValueError("CSV存在重复列名。")
    missing = REQUIRED - set(columns)
    extra = set(columns) - known
    if missing or extra:
        raise ValueError(f"型号库列名不匹配；缺少：{sorted(missing)}；未知：{sorted(extra)}")
    legacy_type_column = "thruster_type" not in columns
    records = []
    for number, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"第{number}行的列数与表头不一致。")
        values = {}
        for key, value in row.items():
            if key in NUMERIC:
                if value.strip():
                    try:
                        values[key] = float(value)
                    except ValueError as exc:
                        raise ValueError(f"第{number}行的{key}不是数字。") from exc
                elif key == "minimum_power_kW":
                    values[key] = 0.0
                elif key in REQUIRED:
                    raise ValueError(f"第{number}行缺少{key}。")
                else:
                    values[key] = None
            else:
                values[key] = value
        if legacy_type_column:
            values["thruster_type"] = infer_legacy_thruster_type(
                values["thruster_id"], values["name_zh"]
            )
        records.append(ThrusterRecord(**values))
    validate_library(records)
    return records, hashlib.sha256(raw).hexdigest()


def load_thruster_library(path: str | Path) -> list[ThrusterRecord]:
    return read_library(path)[0]


def merged_library(current: list[ThrusterRecord], incoming: list[ThrusterRecord],
                   *, replace_existing: bool = False) -> list[ThrusterRecord]:
    validate_library(current)
    validate_library(incoming)
    result = {record.thruster_id: deepcopy(record) for record in current}
    for record in incoming:
        if record.thruster_id in result and result[record.thruster_id] != record and not replace_existing:
            raise ValueError(f"同ID记录已存在：{record.thruster_id}；未执行覆盖。")
        result[record.thruster_id] = deepcopy(record)
    return list(result.values())


def save_thruster_library(path: str | Path, records: list[ThrusterRecord], *,
                         expected_hash=_UNSET, backup_dir: str | Path | None = None) -> str:
    """Compare against the read version, then atomically replace one complete CSV."""
    validate_library(records)
    path = Path(path)
    if path.is_symlink():
        raise ValueError("不能覆盖符号链接形式的型号库。")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("型号库正在被其他写入操作使用；请稍后刷新重试。") from exc
    temporary = None
    try:
        os.close(lock_fd)
        actual = fingerprint(path)
        if expected_hash is not _UNSET and actual != expected_hash:
            raise RuntimeError("型号库已被其他窗口或程序修改；本次未保存，请刷新后重试。")
        if actual is not None and backup_dir is not None:
            destination = Path(backup_dir)
            destination.mkdir(parents=True, exist_ok=True)
            name = f"{path.stem}_{datetime.now():%Y%m%d-%H%M%S}_{uuid.uuid4().hex[:8]}.csv"
            shutil.copy2(path, destination / name)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="",
                                         dir=path.parent, prefix=path.name + ".", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=[field.name for field in fields(ThrusterRecord)])
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))
            stream.flush()
            os.fsync(stream.fileno())
        if fingerprint(path) != actual:
            raise RuntimeError("写入前检测到型号库发生变化；本次未覆盖，请刷新重试。")
        temporary.replace(path)
        return fingerprint(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)
