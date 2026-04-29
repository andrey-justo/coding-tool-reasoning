from dataclasses import dataclass
from typing import List, Optional


@dataclass
class IntentPlanningResult:
    """Output of Stage 1 intent planning.

    This helper structure bridges the natural-language request and the
    `CodeGenPlan` model used by MCP tools.
    """

    nfr_focus: List[str]
    resolved_nfr_ids: List[str]
    high_level_steps: List[str]
    inferred_target_language: Optional[str] = None
