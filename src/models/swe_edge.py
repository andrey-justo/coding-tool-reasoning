from dataclasses import dataclass


@dataclass
class SweEdge:
    source_id: str
    relation: str
    target_id: str
    description: str
