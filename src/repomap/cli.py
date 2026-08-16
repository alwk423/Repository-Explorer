from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from typer.core import TyperGroup

from repomap.deps import build_dependency_graph
from repomap.ignore import build_ignore_spec
from repomap.scanner import compute_stats, scan_repo
from repomap.tree import build_tree, render_tree


class RootGroup(TyperGroup):
    """Lets `repomap <path>` and `repomap <subcommand> ...` coexist.

    Click otherwise consumes the first token into the callback's `path`
    argument before it ever considers subcommand names, so `repomap deps x`
    would bind path="deps" and then fail to find a command named "x".
    """

    def parse_args(self, ctx: typer.Context, args: list[str]) -> list[str]:
        if args and args[0] in self.commands:
            path_param = next(p for p in self.params if p.name == "path")
            self.params.remove(path_param)
            try:
                return super().parse_args(ctx, args)
            finally:
                self.params.append(path_param)
        return super().parse_args(ctx, args)


app = typer.Typer(cls=RootGroup, help="Quickly understand the structure of a repository.")
console = Console()


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def run_overview(path: str) -> None:
    root = Path(path).resolve()
    if not root.is_dir():
        console.print(f"[red]Not a directory:[/] {root}")
        raise typer.Exit(code=1)

    ignore_spec = build_ignore_spec(root)
    files = scan_repo(root, ignore_spec)
    stats = compute_stats(files, root)

    console.print(f"\n[bold]{root}[/]\n")
    tree_node = build_tree(root, files)
    console.print(render_tree(tree_node))

    console.print()
    summary = Table(title="Summary")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Files", str(stats.total_files))
    summary.add_row("Directories", str(stats.total_dirs))
    summary.add_row("Total size", _human_size(stats.total_size_bytes))
    console.print(summary)

    console.print()
    lang_table = Table(title="Languages")
    lang_table.add_column("Language")
    lang_table.add_column("Files", justify="right")
    for lang, count in sorted(stats.files_by_language.items(), key=lambda kv: -kv[1]):
        lang_table.add_row(lang, str(count))
    console.print(lang_table)

    console.print()
    cat_table = Table(title="Categories")
    cat_table.add_column("Category")
    cat_table.add_column("Files", justify="right")
    for category, count in sorted(stats.files_by_category.items(), key=lambda kv: -kv[1]):
        cat_table.add_row(category, str(count))
    console.print(cat_table)

    if stats.largest_files:
        console.print()
        largest_table = Table(title="Largest files")
        largest_table.add_column("File")
        largest_table.add_column("Size", justify="right")
        for f in stats.largest_files:
            largest_table.add_row(str(f.path.relative_to(root)), _human_size(f.size_bytes))
        console.print(largest_table)


def _print_deps_detail(graph, target_path: Path, root_path: Path) -> None:
    rel = target_path.relative_to(root_path)
    console.print(f"\n[bold]{rel}[/]\n")

    deps_table = Table(title=f"Dependencies ({len(graph.dependencies[target_path])})")
    deps_table.add_column("File")
    for dep in sorted(graph.dependencies[target_path]):
        deps_table.add_row(str(dep.relative_to(root_path)))
    console.print(deps_table)

    console.print()
    dependents_table = Table(title=f"Dependents ({len(graph.dependents[target_path])})")
    dependents_table.add_column("File")
    for dependent in sorted(graph.dependents[target_path]):
        dependents_table.add_row(str(dependent.relative_to(root_path)))
    console.print(dependents_table)


def _print_deps_summary(graph, root_path: Path) -> None:
    console.print(f"\n[bold]{root_path}[/]\n")

    table = Table(title=f"Python files ({len(graph.dependencies)})")
    table.add_column("File")
    table.add_column("Dependencies", justify="right")
    table.add_column("Dependents", justify="right")

    rows = sorted(
        graph.dependencies,
        key=lambda p: (-len(graph.dependents[p]), p.relative_to(root_path).as_posix()),
    )
    for path in rows:
        table.add_row(
            str(path.relative_to(root_path)),
            str(len(graph.dependencies[path])),
            str(len(graph.dependents[path])),
        )
    console.print(table)


def _render_dependency_tree(graph, root_path: Path) -> Tree:
    tree = Tree(f"[bold]{root_path}[/]")
    for path in sorted(graph.dependencies, key=lambda p: p.relative_to(root_path).as_posix()):
        label = str(path.relative_to(root_path))
        deps = graph.dependencies[path]
        if not deps:
            tree.add(f"[dim]{label}[/]")
            continue
        branch = tree.add(label)
        for dep in sorted(deps, key=lambda p: p.relative_to(root_path).as_posix()):
            branch.add(f"[dim]{dep.relative_to(root_path)}[/]")
    return tree


@app.command("graph")
def graph_command(
    root: str = typer.Option(".", "--root", "-r", help="Repository root to scan."),
) -> None:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        console.print(f"[red]Not a directory:[/] {root_path}")
        raise typer.Exit(code=1)

    ignore_spec = build_ignore_spec(root_path)
    files = scan_repo(root_path, ignore_spec)
    graph = build_dependency_graph(files, root_path)

    if not graph.dependencies:
        console.print(f"[red]No Python files found under:[/] {root_path}")
        raise typer.Exit(code=1)

    console.print()
    console.print(_render_dependency_tree(graph, root_path))


@app.command("deps")
def deps_command(
    target: str = typer.Argument(
        ".", help="Python file to inspect, or a directory for a repo-wide summary."
    ),
    root: str = typer.Option(".", "--root", "-r", help="Repository root to scan."),
) -> None:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        console.print(f"[red]Not a directory:[/] {root_path}")
        raise typer.Exit(code=1)

    target_arg = Path(target)
    target_path = target_arg.resolve() if target_arg.is_absolute() else (root_path / target).resolve()

    ignore_spec = build_ignore_spec(root_path)
    files = scan_repo(root_path, ignore_spec)
    graph = build_dependency_graph(files, root_path)

    if target_path.is_dir():
        if not graph.dependencies:
            console.print(f"[red]No Python files found under:[/] {target_path}")
            raise typer.Exit(code=1)
        _print_deps_summary(graph, root_path)
        return

    if target_path not in graph.dependencies:
        console.print(f"[red]Not a Python file scanned under {root_path}:[/] {target_path}")
        raise typer.Exit(code=1)

    _print_deps_detail(graph, target_path, root_path)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to inspect."),
) -> None:
    if ctx.invoked_subcommand is None:
        run_overview(path)


if __name__ == "__main__":
    app()
