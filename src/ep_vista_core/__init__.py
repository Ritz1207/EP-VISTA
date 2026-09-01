# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Electric Propulsion for VLEO Integrated System Trade Analysis calculation core."""

__version__ = "1.0"
PUBLIC_VERSION = "V1.0"

from .models import ProjectCase, ThrusterRecord, TradeStudyResult
from .study import run_case
from .propulsion import evaluate_candidate

__all__ = [
    "__version__",
    "PUBLIC_VERSION",
    "ProjectCase",
    "ThrusterRecord",
    "TradeStudyResult",
    "run_case",
    "evaluate_candidate",
]
