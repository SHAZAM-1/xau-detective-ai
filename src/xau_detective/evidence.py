"""Auditable evidence ledger for deterministic analysis."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Direction


@dataclass
class EvidenceLedger:
    direction: Direction
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    research_supporting: list[str] = field(default_factory=list)
    research_contradicting: list[str] = field(default_factory=list)
    research_warnings: list[str] = field(default_factory=list)

    def add_support(self, item: str) -> None:
        self.supporting.append(item)

    def add_contradiction(self, item: str) -> None:
        self.contradicting.append(item)

    def add_warning(self, item: str) -> None:
        self.warnings.append(item)

    def add_research_support(self, item: str) -> None:
        self.research_supporting.append(item)

    def add_research_contradiction(self, item: str) -> None:
        self.research_contradicting.append(item)

    def add_research_warning(self, item: str) -> None:
        self.research_warnings.append(item)

    @property
    def independent_evidence_count(self) -> int:
        return len(set(self.supporting))

    @property
    def has_conflict(self) -> bool:
        return bool(self.contradicting)
