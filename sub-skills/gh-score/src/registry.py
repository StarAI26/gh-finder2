"""Auto-discover scorer classes from scorers/ directory."""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import BaseScorer


def load_scorers(config, scorers_dir: Path | None = None) -> dict:
    """Import every .py in scorers/, instantiate scorer classes with config weights."""
    if scorers_dir is None:
        scorers_dir = Path(__file__).parent / "scorers"

    scorers: dict = {}

    for finder, mod_name, _ in pkgutil.iter_modules([str(scorers_dir)]):
        if mod_name.startswith("_"):
            continue
        mod = importlib.import_module(f"scorers.{mod_name}")
        for attr in dir(mod):
            cls = getattr(mod, attr)
            if (
                isinstance(cls, type)
                and issubclass(cls, BaseScorer)
                and cls is not BaseScorer
                and hasattr(cls, "name")
            ):
                weight = config.weights.get(cls.name, 0)
                scorers[cls.name] = cls(weight=weight, config=config)

    return scorers
