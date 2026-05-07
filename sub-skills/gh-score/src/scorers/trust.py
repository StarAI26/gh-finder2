"""Trust scorer — Code Search API mentions."""

from __future__ import annotations
import math

from base import BaseScorer


class TrustScorer(BaseScorer):
    name = "trust"

    def __init__(self, weight: float = 0, config=None):
        self.weight = weight
        self.config = config

    def compute(self, repo: dict, config) -> float:
        # TODO: call Code Search API, count mentions, log-scale to 0-100
        return 100.0  # placeholder
