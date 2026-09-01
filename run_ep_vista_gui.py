# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Source-tree launcher for the EP-VISTA desktop application."""

import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(PROJECT_ROOT / "workspace" / "cache" / "matplotlib"),
)


if __name__ == "__main__":
    from ep_vista_app.main import main

    raise SystemExit(main())
