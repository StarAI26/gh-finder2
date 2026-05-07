"""Community scorer — log-scaled stars/forks/watchers."""

from __future__ import annotations
import math

from base import BaseScorer


class CommunityScorer(BaseScorer):
    name = "community"

    def __init__(self, weight: float = 0, config=None):
        self.weight = weight
        self.config = config

    def compute(self, repo: dict, config) -> float:
        m = repo["metrics"]
        t = config.thresholds
        stars = math.log1p(m["stars"]) / math.log1p(t["min_stars_for_scale"]) * 50
        forks = math.log1p(m["forks"]) / math.log1p(t["max_forks_for_scale"]) * 30
        watchers = math.log1p(m["watchers"]) / math.log1p(t["max_watchers_for_scale"]) * 20
        return min(stars + forks + watchers, 100.0)
