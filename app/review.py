from __future__ import annotations

from itertools import count
from typing import List

from app.schemas import CategoryResult, ReviewCase
from app.taxonomy import DecisionAction


class ReviewQueue:
    def __init__(self) -> None:
        self._counter = count(1)
        self._cases: List[ReviewCase] = []

    def create_case(
        self,
        tenant_id: str,
        submitted_text: str,
        action: DecisionAction,
        category_scores: List[CategoryResult],
    ) -> ReviewCase:
        priority = self._priority_from_scores(category_scores)
        case = ReviewCase(
            case_id=f"case-{next(self._counter):05d}",
            tenant_id=tenant_id,
            submitted_text=submitted_text,
            action=action,
            priority=priority,
            category_scores=category_scores,
            notes=["Auto-created from synchronous moderation decision."],
        )
        self._cases.append(case)
        self._cases.sort(key=lambda item: item.priority, reverse=True)
        return case

    def list_cases(self) -> List[ReviewCase]:
        return list(self._cases)

    @staticmethod
    def _priority_from_scores(category_scores: List[CategoryResult]) -> int:
        highest = max((score.score for score in category_scores), default=0.0)
        if highest >= 0.9:
            return 100
        if highest >= 0.75:
            return 80
        if highest >= 0.55:
            return 60
        return 40
