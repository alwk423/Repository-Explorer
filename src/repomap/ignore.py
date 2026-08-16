from __future__ import annotations

from pathlib import Path

import pathspec

DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    "node_modules/",
    "__pycache__/",
    ".venv/",
    "venv/",
    ".mypy_cache/",
    ".pytest_cache/",
    "dist/",
    "build/",
    "*.egg-info/",
    ".idea/",
    ".vscode/",
]


class IgnoreSpec:
    def __init__(self, spec: pathspec.PathSpec, root: Path):
        self._spec = spec
        self._root = root

    def is_ignored(self, path: Path) -> bool:
        rel = path.relative_to(self._root)
        rel_str = rel.as_posix()
        if path.is_dir():
            # Directory-only patterns like "build/" only match with a trailing slash.
            rel_str += "/"
        return self._spec.match_file(rel_str)


def build_ignore_spec(root: Path) -> IgnoreSpec:
    patterns = list(DEFAULT_IGNORE_PATTERNS)
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        # Only the root .gitignore is honored; nested .gitignore files are not merged in.
        patterns.extend(gitignore.read_text(errors="ignore").splitlines())
    spec = pathspec.PathSpec.from_lines("gitignore", patterns)
    return IgnoreSpec(spec, root)
