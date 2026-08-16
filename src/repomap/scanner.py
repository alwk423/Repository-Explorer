from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from repomap.ignore import IgnoreSpec
from repomap.models import FileInfo, RepoStats

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".swift": "Swift",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".sh": "Shell",
    ".bash": "Shell",
}

CONFIG_FILENAMES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    "tox.ini",
    ".gitignore",
    ".editorconfig",
}
CONFIG_EXTENSIONS = {".cfg", ".ini", ".yaml", ".yml", ".toml"}

DOC_FILENAME_PREFIXES = ("README", "LICENSE", "CHANGELOG", "CONTRIBUTING")

TEST_FILENAME_PATTERNS = ("test_*.py", "*_test.py", "*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts")
TEST_DIR_NAMES = {"test", "tests"}


def detect_language(path: Path) -> str | None:
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower())


def classify_category(path: Path, root: Path) -> str:
    # Checks are ordered by priority: first match wins (e.g. a test file under
    # docs/ is still "test", not "docs").
    rel_parts = path.relative_to(root).parts
    name = path.name

    if any(part in TEST_DIR_NAMES for part in rel_parts[:-1]):
        return "test"
    if any(fnmatch.fnmatch(name, pattern) for pattern in TEST_FILENAME_PATTERNS):
        return "test"

    if name in CONFIG_FILENAMES or path.suffix.lower() in CONFIG_EXTENSIONS:
        return "config"
    if any(part.lower() == ".github" for part in rel_parts[:-1]):
        return "config"

    if name.startswith(DOC_FILENAME_PREFIXES) or path.suffix.lower() in {".md", ".rst"}:
        return "docs"
    if any(part.lower() == "docs" for part in rel_parts[:-1]):
        return "docs"

    if detect_language(path) is not None:
        return "source"

    return "other"


def scan_repo(root: Path, ignore_spec: IgnoreSpec) -> list[FileInfo]:
    root = root.resolve()
    files: list[FileInfo] = []

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)

        # Mutating dirnames in place (not reassigning) tells os.walk not to
        # descend into these subdirectories at all.
        dirnames[:] = [
            d for d in dirnames if not ignore_spec.is_ignored(current_dir / d)
        ]

        for filename in filenames:
            file_path = current_dir / filename
            if ignore_spec.is_ignored(file_path):
                continue
            try:
                size = file_path.stat().st_size
            except OSError:
                # Broken symlink, permission denied, or deleted mid-walk — skip it.
                continue
            files.append(
                FileInfo(
                    path=file_path,
                    size_bytes=size,
                    language=detect_language(file_path),
                    category=classify_category(file_path, root),
                )
            )

    return files


def compute_stats(files: list[FileInfo], root: Path, top_n: int = 5) -> RepoStats:
    stats = RepoStats()
    dirs: set[Path] = set()

    for f in files:
        stats.total_files += 1
        stats.total_size_bytes += f.size_bytes

        lang_key = f.language or "Other"
        stats.files_by_language[lang_key] = stats.files_by_language.get(lang_key, 0) + 1
        stats.files_by_category[f.category] = stats.files_by_category.get(f.category, 0) + 1

        # Walk up to root, recording each ancestor directory; stop early once
        # we hit a directory already recorded, since its ancestors must be too.
        parent = f.path.parent
        while parent != root and parent not in dirs:
            dirs.add(parent)
            if parent.parent == parent:
                # Reached the filesystem root (e.g. "/") without hitting `root`.
                break
            parent = parent.parent

    stats.total_dirs = len(dirs)
    stats.largest_files = sorted(files, key=lambda f: f.size_bytes, reverse=True)[:top_n]

    return stats
