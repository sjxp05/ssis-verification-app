from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ConstantValues = dict[str, float | int | None]


# API
@dataclass
class UploadedFile:
    path: Path
    name: str
    size: int

    @classmethod
    def from_path(cls, path: str | Path) -> UploadedFile:
        p = Path(path)
        size = p.stat().st_size if p.exists() else 0
        return cls(path=p, name=p.name, size=size)
    
    @property
    def size_text(self) -> str:
        s = self.size
        if s < 1024:
            return f"{s} B"
        if s < 1024 ** 2:
            return f"{s / 1024:.1f} KB"
        return f"{s / 1024 ** 2:.1f} MB"