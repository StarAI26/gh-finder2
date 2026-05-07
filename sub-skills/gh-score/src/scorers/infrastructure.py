"""Infrastructure scorer — org backing + release flow."""

from __future__ import annotations

from base import BaseScorer


class InfrastructureScorer(BaseScorer):
    name = "infrastructure"

    def __init__(self, weight: float = 0, config=None):
        self.weight = weight
        self.config = config

    def compute(self, repo: dict, config) -> float:
        # TODO: owner.type == Organization → +50, releases.has_releases → +50
        return 100.0  # placeholder
