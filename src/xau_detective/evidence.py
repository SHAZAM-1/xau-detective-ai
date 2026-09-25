"""Evidence ledger: separates supporting evidence from contradictions."""
from __future__ import annotations

from dataclasses import dataclass, field
from .models import Direction


@dataclass
class EvidenceLedger:
    direction: Direction
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_support(self, item: str) -> None:
        self.supporting.append(item)

    def add_contradiction(self, item: str) -> None:
        self.contradicting.append(item)

    def add_warning(self, item: str) -> None:
        self.warnings.append(item)

    @property
    def independent_evidence_count(self) -> int:
        return len(set(self.supporting))

    @property
    def has_conflict(self) -> bool:
        return bool(self.contradicting)
