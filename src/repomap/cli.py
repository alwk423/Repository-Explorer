from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from repomap.ignore import build_ignore_spec
from repomap.scanner import compute_stats, scan_repo
from repomap.tree import build_tree, render_tree

app = typer.Typer(help="Quickly understand the structure of a repository.")
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


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to inspect."),
) -> None:
    if ctx.invoked_subcommand is None:
        run_overview(path)


if __name__ == "__main__":
    app()
