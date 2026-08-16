# repomap

A local CLI tool that scans a repository and helps you quickly understand its
structure.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install ".[dev]"
```

Note: use a regular install (`pip install .`), not `-e`. On some machines
(macOS + Python 3.14 in particular), the `.pth` file that editable installs
use to point Python at `src/` ends up with the filesystem's hidden flag set,
and Python 3.14's `site.py` silently skips hidden `.pth` files — so `repomap`
fails with `ModuleNotFoundError: No module named 'repomap'` even though the
install "succeeded". A regular install copies the package files directly and
isn't affected. The trade-off: re-run `pip install .` after editing the
source to pick up changes — or during active development, skip installing
altogether and run `PYTHONPATH=src python -m repomap.cli .` instead, which
always uses the latest code.

## Usage

```bash
repomap .            # overview: directory tree + stats for the current repo
repomap /path/to/repo
```

Ignores `.git`, `node_modules`, virtualenvs, build artifacts, and anything
matched by the target repo's `.gitignore`.

## What it shows

- **Directory tree** — the repo's structure, directories before files,
  alphabetically sorted.
- **Summary** — total file count, directory count, and size.
- **Languages** — file count by detected language (Python, JavaScript,
  Go, Rust, and more).
- **Categories** — file count by role: source, test, config, docs, other.
- **Largest files** — the biggest files in the repo, for spotting bloat.

## Run tests

```bash
pytest
```
