"""Parse a Python package and enumerate every function/method definition."""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Unit:
    qualname: str   # e.g. "tabulate._format" or "Class.method"
    file: str       # path relative to repo root, forward slashes
    def_line: int
    body_start: int  # node.body[0].lineno — first line of the body
    body_end: int    # node.end_lineno


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


def enumerate_units(package_dir: Path) -> list[Unit]:
    """Return one Unit per FunctionDef/AsyncFunctionDef found under *package_dir*.

    Paths stored in Unit.file are relative to the repository root (the parent
    of *package_dir*) and use forward slashes.
    """
    repo_root = package_dir.parent
    results: list[Unit] = []

    for py_file in sorted(package_dir.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        rel_file = py_file.relative_to(repo_root).as_posix()
        _collect(tree.body, "", rel_file, results)

    return results
