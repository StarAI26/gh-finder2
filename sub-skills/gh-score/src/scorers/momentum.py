"""Momentum scorer — push recency tiers."""

from __future__ import annotations

from base import BaseScorer


class MomentumScorer(BaseScorer):
    name = "momentum"

    def __init__(self, weight: float = 0, config=None):
        self.weight = weight
        self.config = config

    def compute(self, repo: dict, config) -> float:
        days = repo["activity"]["days_since_last_push"]
        if days is None:
            return 0.0
        if days <= 30:
            return 100.0
        if days <= 90:
            return 70.0
        if days <= 180:
            return 40.0
        return 10.0
