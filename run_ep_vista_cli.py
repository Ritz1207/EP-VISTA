# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Run the CLI from a source checkout without installing the project package."""

# Configure local imports/cache identically to the source GUI launcher.
import run_ep_vista_gui  # noqa: F401
from ep_vista_core.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
