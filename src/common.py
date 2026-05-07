"""Global config + paths. One source of truth."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    weights: dict = field(default_factory=dict)
    thresholds: dict = field(default_factory=dict)
    paths: dict = field(default_factory=dict)
    scoring: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        cfg_path = Path(path) if path else ROOT / "config" / "scoring.json"
        with open(cfg_path, encoding="utf-8") as f:
            raw = json.load(f)
        return cls(
            weights=raw.get("weights", {}),
            thresholds=raw.get("thresholds", {}),
            paths=raw.get("paths", {}),
            scoring=raw.get("scoring", {}),
        )

    def path(self, name: str) -> Path:
        """Resolve a named path from config, relative to ROOT."""
        p = self.paths.get(name, name)
        return ROOT / p if not Path(p).is_absolute() else Path(p)
