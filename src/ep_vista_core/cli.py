# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Command-line entry point for reproducible batch use."""

from __future__ import annotations

import argparse
from pathlib import Path

from .models import ProjectCase
from .propulsion import load_thruster_library
from .study import default_thruster_library_path, run_case


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ep-vista", description="Electric Propulsion for VLEO Integrated System Trade Analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="运行EP-VISTA项目并在终端显示结论")
    run_parser.add_argument("project", type=Path)
    validate_parser = subparsers.add_parser("validate", help="仅验证EP-VISTA项目输入")
    validate_parser.add_argument("project", type=Path)
    subparsers.add_parser("list-thrusters", help="列出推进器型号库")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "list-thrusters":
        for item in load_thruster_library(default_thruster_library_path()):
            print(f"{item.thruster_id:12s} {item.name_zh} [{item.verification_status}]")
        return 0
    project = ProjectCase.load(args.project)
    project.validate()
    if args.command == "validate":
        print("输入验证通过。")
        return 0
    result = run_case(project, progress=lambda value, message: print(f"[{value:3d}%] {message}"))
    print(result.conclusion)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
