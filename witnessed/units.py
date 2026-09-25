"""Parse a Python package and enumerate every function/method definition."""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Unit:
    qualname: str   # e.g. "tabulate._is_file" or "tabulate.SomeClass.method"
    file: str       # path relative to repo root, forward slashes
    def_line: int
    body_start: int  # node.body[0].lineno: first line of the body
    body_end: int    # node.end_lineno


def _stmt_sublists(node: ast.stmt) -> list[list[ast.stmt]]:
    """Return every statement list nested inside *node* (not the node itself)."""
    sub: list[list[ast.stmt]] = []
    # if / elif / else
    if isinstance(node, ast.If):
        sub.append(node.body)
        if node.orelse:
            sub.append(node.orelse)
    # for / while with optional else
    elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        sub.append(node.body)
        if node.orelse:
            sub.append(node.orelse)
    # with / async with
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        sub.append(node.body)
    # try (Python 3.11+: TryStar)
    elif isinstance(node, ast.Try):
        sub.append(node.body)
        for handler in node.handlers:
            sub.append(handler.body)
        if node.orelse:
            sub.append(node.orelse)
        if node.finalbody:
            sub.append(node.finalbody)
    elif hasattr(ast, "TryStar") and isinstance(node, ast.TryStar):  # type: ignore[attr-defined]
        sub.append(node.body)
        for handler in node.handlers:
            sub.append(handler.body)
        if node.orelse:
            sub.append(node.orelse)
        if node.finalbody:
            sub.append(node.finalbody)
    return sub


def _collect(
    nodes: list[ast.stmt],
    prefix: str,
    rel_file: str,
    results: list[Unit],
) -> None:
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualname = f"{prefix}{node.name}" if prefix else node.name
            results.append(
                Unit(
                    qualname=qualname,
                    file=rel_file,
                    def_line=node.lineno,
                    body_start=node.body[0].lineno,
                    body_end=node.end_lineno,
                )
            )
            # Recurse into the function body for nested functions.
            _collect(node.body, f"{qualname}.", rel_file, results)
        elif isinstance(node, ast.ClassDef):
            class_prefix = f"{prefix}{node.name}." if prefix else f"{node.name}."
            _collect(node.body, class_prefix, rel_file, results)
        else:
            # Walk every statement sub-block so functions inside if/try/with/for
            # blocks are not missed.
            for sublist in _stmt_sublists(node):
                _collect(sublist, prefix, rel_file, results)


def _module_prefix(py_file: Path, package_dir: Path) -> str:
    """Return the dotted module prefix for *py_file* relative to *package_dir*.

    For ``package/sub/mod.py`` the prefix is ``package.sub.mod.``.
    For ``package/__init__.py`` the prefix is ``package.``.
    """
    rel = py_file.relative_to(package_dir.parent).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) + "." if parts else ""


def units_from_source(source: str, rel_file: str, package_dir_rel: str) -> list[Unit]:
    """Parse *source* text and return units as if it lived at *rel_file*.

    *rel_file* is the file path relative to the repo root (forward slashes).
    *package_dir_rel* is the package directory path relative to the repo root
    (forward slashes), used to compute the module prefix.

    The module prefix is computed the same way as ``_module_prefix``: by
    treating *rel_file* as relative to the parent of *package_dir_rel*.
    """
    try:
        tree = ast.parse(source, filename=rel_file)
    except SyntaxError:
        return []

    # Reconstruct Path objects so we can reuse _module_prefix logic.
    # We use PurePosixPath arithmetic on string parts to stay cross-platform.
    rel_parts = rel_file.replace("\\", "/").split("/")
    pkg_parts = package_dir_rel.replace("\\", "/").rstrip("/").split("/")

    # The module prefix is derived from rel_file relative to package_dir.parent.
    # package_dir.parent has one fewer component than package_dir.
    pkg_parent_parts = pkg_parts[:-1]  # e.g. ["sample", "tabulate"]

    # Strip the pkg_parent prefix from rel_parts.
    if rel_parts[: len(pkg_parent_parts)] == pkg_parent_parts:
        suffix_parts = rel_parts[len(pkg_parent_parts) :]
    else:
        suffix_parts = rel_parts

    # Remove .py extension from the final component.
    if suffix_parts:
        last = suffix_parts[-1]
        if last.endswith(".py"):
            last = last[:-3]
        suffix_parts = suffix_parts[:-1] + [last]
        if suffix_parts[-1] == "__init__":
            suffix_parts = suffix_parts[:-1]

    mod_prefix = ".".join(suffix_parts) + "." if suffix_parts else ""

    results: list[Unit] = []
    _collect(tree.body, mod_prefix, rel_file, results)
    return results


def enumerate_units(package_dir: Path, repo_root: Path | None = None) -> list[Unit]:
    """Return one Unit per FunctionDef/AsyncFunctionDef found under *package_dir*.

    *repo_root* is the repository root used to compute ``Unit.file``.  It
    defaults to the current working directory.  Paths stored in ``Unit.file``
    use forward slashes.
    """
    if repo_root is None:
        repo_root = Path.cwd()
    repo_root = repo_root.resolve()
    package_dir = package_dir.resolve()

    results: list[Unit] = []

    for py_file in sorted(package_dir.rglob("*.py")):
        rel_file = py_file.relative_to(repo_root).as_posix()
        pkg_dir_rel = package_dir.relative_to(repo_root).as_posix()
        source = py_file.read_text(encoding="utf-8")
        results.extend(units_from_source(source, rel_file, pkg_dir_rel))

    return results
