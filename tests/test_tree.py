from pathlib import Path

from repomap.ignore import build_ignore_spec
from repomap.scanner import scan_repo
from repomap.tree import build_tree

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_repo"


def test_tree_matches_fixture_layout():
    ignore_spec = build_ignore_spec(FIXTURE_ROOT)
    files = scan_repo(FIXTURE_ROOT, ignore_spec)
    root_node = build_tree(FIXTURE_ROOT, files)

    child_names = {c.name for c in root_node.children}
    assert {"src", "tests", "README.md", "pyproject.toml"} <= child_names
    assert "node_modules" not in child_names
    assert "secret.txt" not in child_names

    src_node = next(c for c in root_node.children if c.name == "src")
    assert {c.name for c in src_node.children} == {"app.py", "utils.py"}
