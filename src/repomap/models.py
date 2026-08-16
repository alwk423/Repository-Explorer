from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

Category = str  # "source" | "test" | "config" | "docs" | "other"


@dataclass
class FileInfo:
    path: Path
    size_bytes: int
    language: str | None
    category: Category


@dataclass
class RepoStats:
    total_files: int = 0
    total_dirs: int = 0
    total_size_bytes: int = 0
    files_by_language: dict[str, int] = field(default_factory=dict)
    files_by_category: dict[str, int] = field(default_factory=dict)
    largest_files: list[FileInfo] = field(default_factory=list)


@dataclass
class TreeNode:
    name: str
    path: Path
    is_dir: bool
    children: list["TreeNode"] = field(default_factory=list)
