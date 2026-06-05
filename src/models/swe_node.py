from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SweNode:
    id: str
    type: str
    name: str
    nfr_category: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_path: str = ""
