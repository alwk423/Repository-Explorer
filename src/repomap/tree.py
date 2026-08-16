from __future__ import annotations

from pathlib import Path

from rich.tree import Tree

from repomap.models import FileInfo, TreeNode


def build_tree(root: Path, files: list[FileInfo]) -> TreeNode:
    root_node = TreeNode(name=root.name or str(root), path=root, is_dir=True)
    # Cache of already-built directory nodes, keyed by path, so shared parent
    # directories aren't recreated when multiple files live under them.
    dir_nodes: dict[Path, TreeNode] = {root: root_node}

    def get_dir_node(dir_path: Path) -> TreeNode:
        if dir_path in dir_nodes:
            return dir_nodes[dir_path]
        # Recurse up first so missing ancestor directories get created too,
        # then link this node onto its (now-guaranteed-to-exist) parent.
        parent_node = get_dir_node(dir_path.parent)
        node = TreeNode(name=dir_path.name, path=dir_path, is_dir=True)
        parent_node.children.append(node)
        dir_nodes[dir_path] = node
        return node

    # Sorted only for deterministic build order; _sort_children below is what
    # actually fixes the final display order.
    for f in sorted(files, key=lambda f: f.path.as_posix()):
        parent_node = get_dir_node(f.path.parent)
        parent_node.children.append(TreeNode(name=f.path.name, path=f.path, is_dir=False))

    _sort_children(root_node)
    return root_node


def _sort_children(node: TreeNode) -> None:
    # (not is_dir, name.lower()) sorts directories before files, and
    # alphabetically (case-insensitive) within each group.
    node.children.sort(key=lambda c: (not c.is_dir, c.name.lower()))
    for child in node.children:
        if child.is_dir:
            _sort_children(child)


def render_tree(node: TreeNode) -> Tree:
    label = f"[bold blue]{node.name}/[/]" if node.is_dir else node.name
    tree = Tree(label)
    _add_children(tree, node)
    return tree


def _add_children(tree: Tree, node: TreeNode) -> None:
    for child in node.children:
        if child.is_dir:
            label = f"[bold blue]{child.name}/[/]"
            # tree.add returns the new branch, so nested children attach here
            # rather than back at the root.
            branch = tree.add(label)
            _add_children(branch, child)
        else:
            tree.add(f"[dim]{child.name}[/]")
