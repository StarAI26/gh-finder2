"""Quality scorer — license, archived, issue hygiene, fork, README presence."""

from __future__ import annotations

from base import BaseScorer


class QualityScorer(BaseScorer):
    name = "quality"

    def __init__(self, weight: float = 0, config=None):
        self.weight = weight
        self.config = config

    def compute(self, repo: dict, config) -> float:
        # TODO: license (best license gets 40, no license=0)
        # TODO: archived (is_archived → -30)
        # TODO: issue hygiene (open_issues/stars ratio, 0-20)
        # TODO: fork (is_fork → -20, original is usually better)
        # TODO: README length (len(readme) < 500 → -15, project not serious)
        return 100.0  # placeholder
