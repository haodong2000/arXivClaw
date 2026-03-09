from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    summary: str
    published_at: datetime
    link: str
    categories: list[str]


@dataclass(slots=True)
class ScoredPaper:
    paper: Paper
    score: float
    relevance: str
    matched_keywords: list[str]
    reasoning: str
