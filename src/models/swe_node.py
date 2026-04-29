from dataclasses import dataclass


@dataclass
class SweNode:
    id: str
    type: str
    name: str
    nfr_category: str
    description: str
