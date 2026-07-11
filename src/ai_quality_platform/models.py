from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Finding:
    id: str
    severity: str
    category: str
    file: str
    line_start: int
    line_end: int
    title: str
    description: str
    recommendation: str
    blocking: bool
    confidence: float


@dataclass(slots=True)
class ReviewResult:
    reviewer: str
    verdict: str
    summary: str
    findings: list[Finding] = field(default_factory=list)
    tested: list[str] = field(default_factory=list)
    not_tested: list[str] = field(default_factory=list)
    usage_tokens: int = 0
    estimated_cost_jpy: float = 0.0

