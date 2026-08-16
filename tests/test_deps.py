from pathlib import Path

from repomap.deps import build_dependency_graph
from repomap.ignore import build_ignore_spec
from repomap.scanner import scan_repo

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "deps_repo"


def _graph():
    ignore_spec = build_ignore_spec(FIXTURE_ROOT)
    files = scan_repo(FIXTURE_ROOT, ignore_spec)
    return build_dependency_graph(files, FIXTURE_ROOT)


def _rel(paths):
    return {p.relative_to(FIXTURE_ROOT).as_posix() for p in paths}


def test_absolute_and_relative_imports_resolve_to_same_target():
    graph = _graph()
    app = FIXTURE_ROOT / "mypkg" / "app.py"
    assert _rel(graph.dependencies[app]) == {"mypkg/utils.py"}


def test_dotted_relative_import_resolves_across_packages():
    graph = _graph()
    extra = FIXTURE_ROOT / "mypkg" / "sub" / "extra.py"
    assert _rel(graph.dependencies[extra]) == {"mypkg/utils.py"}


def test_stdlib_import_is_not_a_dependency():
    graph = _graph()
    app = FIXTURE_ROOT / "mypkg" / "app.py"
    assert not any(dep.name == "os.py" for dep in graph.dependencies[app])


def test_dependents_are_the_reverse_of_dependencies():
    graph = _graph()
    utils = FIXTURE_ROOT / "mypkg" / "utils.py"
    assert _rel(graph.dependents[utils]) == {"mypkg/app.py", "mypkg/sub/extra.py"}


def test_leaf_module_has_no_dependencies():
    graph = _graph()
    utils = FIXTURE_ROOT / "mypkg" / "utils.py"
    assert graph.dependencies[utils] == set()
