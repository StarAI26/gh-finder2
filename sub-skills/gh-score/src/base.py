"""Base scorer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseScorer(ABC):
    """Subclass this and set `name` + `weight` to be auto-discovered."""

    name: str
    weight: float = 0

    @abstractmethod
    def compute(self, repo: dict, config) -> float:
        """Return a 0-100 score for this dimension."""
        raise NotImplementedError
