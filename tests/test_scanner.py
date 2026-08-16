from pathlib import Path

from repomap.ignore import build_ignore_spec
from repomap.scanner import compute_stats, scan_repo

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_repo"


def _scan():
    ignore_spec = build_ignore_spec(FIXTURE_ROOT)
    return scan_repo(FIXTURE_ROOT, ignore_spec)


def test_ignored_paths_never_appear():
    files = _scan()
    rel_paths = {f.path.relative_to(FIXTURE_ROOT).as_posix() for f in files}
    assert not any("node_modules" in p for p in rel_paths)
    assert "secret.txt" not in rel_paths


def test_language_and_category_classification():
    files = _scan()
    by_rel = {f.path.relative_to(FIXTURE_ROOT).as_posix(): f for f in files}

    app = by_rel["src/app.py"]
    assert app.language == "Python"
    assert app.category == "source"

    test_file = by_rel["tests/test_app.py"]
    assert test_file.category == "test"

    readme = by_rel["README.md"]
    assert readme.category == "docs"

    config = by_rel["pyproject.toml"]
    assert config.category == "config"


def test_compute_stats():
    files = _scan()
    stats = compute_stats(files, FIXTURE_ROOT)
    assert stats.total_files == len(files)
    assert stats.files_by_category.get("source") == 2
    assert stats.files_by_category.get("test") == 1
