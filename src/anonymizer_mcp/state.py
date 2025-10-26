"""
Lightweight persistence for which input files have already been anonymized.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ProcessingState:
    """
    Tracks files that have successfully gone through anonymization so we can
    skip re-processing unless the user explicitly forces a rescan.
    """

    path: Path
    processed: dict[str, int] = field(default_factory=dict)
    _dirty: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    self.processed = {
                        str(k): int(v) for k, v in payload.get("processed", {}).items() if isinstance(v, int)
                    }
            except Exception:
                # Corrupt state should not crash the server; start fresh.
                self.processed = {}

    def reset(self) -> None:
        self.processed.clear()
        self._dirty = True

    def is_processed(self, file_path: Path) -> bool:
        key = str(file_path)
        recorded = self.processed.get(key)
        if recorded is None:
            return False
        try:
            return recorded == int(file_path.stat().st_mtime_ns)
        except FileNotFoundError:
            return True

    def mark_processed(self, file_path: Path) -> None:
        try:
            mtime_ns = int(file_path.stat().st_mtime_ns)
        except FileNotFoundError:
            mtime_ns = 0
        self.processed[str(file_path)] = mtime_ns
        self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"processed": self.processed}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._dirty = False
