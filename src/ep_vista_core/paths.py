# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Relocatable project paths and narrowly scoped legacy-project migration."""

from pathlib import Path, PureWindowsPath


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def migrate_legacy_weather_path(value: str | None) -> str | None:
    """Resolve old in-project weather paths without changing external user data.

    Kept only to read existing EPT project JSON; new projects use relative paths.
    Migration is in memory, never an overwrite of the imported project file.
    """
    if not value:
        return value
    old_roots = (
        PureWindowsPath(project_root().parent / "EPT"),
    )
    path = PureWindowsPath(value)
    for old_root in old_roots:
        try:
            relative = path.relative_to(old_root)
        except ValueError:
            continue
        if ".." in relative.parts:
            return value
        if project_root().joinpath(*relative.parts).is_file():
            return relative.as_posix()
    return value
