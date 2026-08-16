from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from repomap.models import FileInfo


@dataclass
class ImportRef:
    module: str | None  # dotted module path; None for "from . import x"
    level: int  # 0 for absolute, >0 for relative ("." = 1, ".." = 2, ...)
    names: tuple[str, ...] = ()  # imported names, for "from X import a, b"


@dataclass
class DependencyGraph:
    dependencies: dict[Path, set[Path]] = field(default_factory=dict)
    dependents: dict[Path, set[Path]] = field(default_factory=dict)


def parse_imports(path: Path) -> list[ImportRef]:
    try:
        # Static parse only — never execute the file's code.
        tree = ast.parse(path.read_text(errors="ignore"), filename=str(path))
    except SyntaxError:
        # A single unparsable file shouldn't abort the whole scan.
        return []

    imports: list[ImportRef] = []
    # ast.walk recurses into every node, so imports nested inside functions,
    # classes, or conditionals are found too, not just top-level statements.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # "import a.b, c" - each name is its own module path and always absolute.
            for alias in node.names:
                imports.append(ImportRef(module=alias.name, level=0))
        elif isinstance(node, ast.ImportFrom):
            # "from a.b import c, d" - c and d share one module/level, so a
            # single ImportRef carries the module/level once with both names.
            names = tuple(alias.name for alias in node.names)
            imports.append(ImportRef(module=node.module, level=node.level, names=names))
    return imports


def _package_root(file_dir: Path, root: Path) -> Path:
    # A directory with __init__.py is a package, so its dotted name is
    # relative to its parent, not to itself. Keep climbing past packages
    # until we reach the directory one level above the top of the package
    # chain - that's what would need to be on sys.path for absolute imports
    # (e.g. "import mypkg.sub.mod") to resolve.
    current = file_dir
    while current != root and (current / "__init__.py").is_file():
        current = current.parent
    return current


def build_module_index(python_files: set[Path], root: Path) -> dict[str, Path]:
    # Maps dotted module names (e.g. "mypkg.sub.mod") to file paths, so
    # resolve_import can look up an absolute import directly instead of
    # re-deriving it from the filesystem on every call.
    index: dict[str, Path] = {}
    for file_path in python_files:
        import_root = _package_root(file_path.parent, root)
        parts = list(file_path.relative_to(import_root).parts)
        if parts[-1] == "__init__.py":
            # __init__.py names the package/subpackage itself, not a
            # submodule called "__init__" - drop the filename entirely.
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][: -len(".py")]
        if not parts:
            # A top-level __init__.py sitting at root has nothing left
            # after dropping it - no dotted name to index.
            continue
        index[".".join(parts)] = file_path
    return index


def _match_module_path(mod_dir: Path, python_files: set[Path]) -> Path | None:
    # mod_dir is an extension-less filesystem guess (from splitting a
    # dotted/relative import into path segments) - it's ambiguous whether it
    # names a module file or a package directory, so try both.
    as_module = mod_dir.with_suffix(".py")
    if as_module in python_files:
        return as_module
    as_package = mod_dir / "__init__.py"
    if as_package in python_files:
        return as_package
    return None


def resolve_import(
    ref: ImportRef,           # the parsed import statement to resolve
    importer: Path,           # the file the import statement was found in (anchors relative imports)
    python_files: set[Path],  # every known Python file in the scan, for existence checks
    module_index: dict[str, Path],  # dotted module name -> file path, for absolute imports
) -> set[Path]:
    # Two independent resolution mechanisms, chosen by ref.level:
    #  - relative (level > 0): build a real Path from the importer's
    #    location and check it against python_files directly.
    #  - absolute (level == 0): look up the dotted name in module_index,
    #    a dict already precomputed from every file's dotted name.
    # Both just ask "does a known file match this import?" - they never
    # compare against each other.
    resolved: set[Path] = set()

    if ref.level > 0:
        # Relative import: dots don't map to a dotted name, so resolve by
        # walking the filesystem instead. level's dot count -> how many
        # parents to climb from the importer's own directory.
        base_dir = importer.parent
        for _ in range(ref.level - 1):
            base_dir = base_dir.parent
        if ref.module:
            # "from .sub import a[, b]" - module named, so it alone is the
            # target; names are ignored (a submodule under sub won't match).
            found = _match_module_path(base_dir.joinpath(*ref.module.split(".")), python_files)
            if found:
                resolved.add(found)
        else:
            # "from . import a[, b]" - no module named, so base_dir is
            # the target and each name is checked individually against it
            # (non-file names, e.g. attributes, just won't match).
            for name in ref.names:
                found = _match_module_path(base_dir / name, python_files)
                if found:
                    resolved.add(found)
        return resolved

    if ref.module is None:
        # Shouldn't occur when level == 0 (only "from . import x" omits
        # the module, and that always has level >= 1), but guard anyway.
        return resolved

    if not ref.names:
        # Plain "import a.b" or "import a.b as c" — the whole dotted path
        # must itself be a module; look it up directly.
        found = module_index.get(ref.module)
        if found:
            resolved.add(found)
        return resolved

    for name in ref.names:
        # "from a.b import c, d" — each name is ambiguous: c could be a
        # submodule (a.b.c) or just an attribute defined inside a.b (e.g.
        # "from os.path import join"). Try the submodule reading first,
        # then fall back to treating a.b itself as the dependency.
        found = module_index.get(f"{ref.module}.{name}") or module_index.get(ref.module)
        if found:
            resolved.add(found)
    return resolved


def build_dependency_graph(files: list[FileInfo], root: Path) -> DependencyGraph:
    python_files = {f.path for f in files if f.language == "Python"}
    # Built once upfront - shared across every file's resolve_import calls below.
    module_index = build_module_index(python_files, root)

    graph = DependencyGraph()
    # Pre-seed every file with an empty set so files with no imports/importers
    # still appear in the graph, and callers never hit a missing dict key.
    for path in python_files:
        graph.dependencies[path] = set()
        graph.dependents[path] = set()

    for path in python_files:                              # every Python file
        for ref in parse_imports(path):                    # every import statement in it
            for target in resolve_import(ref, path, python_files, module_index):  # every file it resolves to
                if target == path:
                    # Guards against relative-import edge cases resolving back
                    # to the importing file itself - not a meaningful edge.
                    continue
                # Record both directions at once so "what does X import" and
                # "what imports X" are both O(1) lookups later, with no
                # separate graph-inversion step needed.
                graph.dependencies[path].add(target)
                graph.dependents[target].add(path)

    return graph
