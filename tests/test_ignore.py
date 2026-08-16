from pathlib import Path

from repomap.ignore import build_ignore_spec

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_repo"


def test_default_patterns_ignore_node_modules():
    spec = build_ignore_spec(FIXTURE_ROOT)
    assert spec.is_ignored(FIXTURE_ROOT / "node_modules")


def test_gitignore_patterns_are_respected():
    spec = build_ignore_spec(FIXTURE_ROOT)
    assert spec.is_ignored(FIXTURE_ROOT / "secret.txt")


def test_source_files_are_not_ignored():
    spec = build_ignore_spec(FIXTURE_ROOT)
    assert not spec.is_ignored(FIXTURE_ROOT / "src" / "app.py")
