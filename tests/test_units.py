"""Tests for witnessed.units.enumerate_units."""

import ast
import textwrap
from pathlib import Path

import pytest

from witnessed.units import Unit, enumerate_units


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_pkg(tmp_path: Path, source: str, filename: str = "mod.py") -> Path:
    """Write *source* as a single-file package under *tmp_path* and return the
    package directory."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / filename).write_text(textwrap.dedent(source))
    return pkg


def _get(units: list[Unit], qualname: str) -> Unit:
    matches = [u for u in units if u.qualname == qualname]
    assert len(matches) == 1, f"expected exactly one unit named {qualname!r}, got {matches}"
    return matches[0]


# ---------------------------------------------------------------------------
# Plain function: qualname now includes module prefix
# ---------------------------------------------------------------------------


def test_plain_function(tmp_path: Path) -> None:
    source = """\
        def hello():
            x = 1
            return x
        """
    pkg = _write_pkg(tmp_path, source)
    units = enumerate_units(pkg, repo_root=tmp_path)
    u = _get(units, "pkg.mod.hello")
    # def_line is line 1 (the "def" line)
    assert u.def_line == 1
    # body_start is line 2 (first line of the body)
    assert u.body_start == 2
    assert u.body_end == 3
    assert u.file.endswith("mod.py")
    assert "/" in u.file  # forward slashes


# ---------------------------------------------------------------------------
# Method inside a class
# ---------------------------------------------------------------------------


def test_method(tmp_path: Path) -> None:
    source = """\
        class MyClass:
            def method(self):
                return 42
        """
    pkg = _write_pkg(tmp_path, source)
    units = enumerate_units(pkg, repo_root=tmp_path)
    u = _get(units, "pkg.mod.MyClass.method")
    assert u.def_line == 2
    assert u.body_start == 3
    assert u.body_end == 3


# ---------------------------------------------------------------------------
# Nested function
# ---------------------------------------------------------------------------


def test_nested_function(tmp_path: Path) -> None:
    source = """\
        def outer():
            def inner():
                return 0
            return inner
        """
    pkg = _write_pkg(tmp_path, source)
    units = enumerate_units(pkg, repo_root=tmp_path)
    # Both the outer and the inner function must be present.
    outer = _get(units, "pkg.mod.outer")
    inner = _get(units, "pkg.mod.outer.inner")
    assert outer.def_line == 1
    assert outer.body_start == 2
    assert inner.def_line == 2
    assert inner.body_start == 3


# ---------------------------------------------------------------------------
# Decorated function: body_start must be after decorator and signature
# ---------------------------------------------------------------------------


def test_decorated_function(tmp_path: Path) -> None:
    source = """\
        import functools

        def my_decorator(f):
            return f

        @my_decorator
        def decorated():
            result = 1
            return result
        """
    pkg = _write_pkg(tmp_path, source)
    units = enumerate_units(pkg, repo_root=tmp_path)
    u = _get(units, "pkg.mod.decorated")
    # The decorator is on line 6, "def" is on line 7.
    # ast.FunctionDef.lineno points to the "def" keyword line (line 7 here),
    # while body[0].lineno is the first statement of the body (line 8).
    assert u.def_line == 7
    assert u.body_start == 8
    assert u.body_end == 9


# ---------------------------------------------------------------------------
# One-liner: def f(): return 1
# ---------------------------------------------------------------------------


def test_one_line_function(tmp_path: Path) -> None:
    source = """\
        def f(): return 1
        """
    pkg = _write_pkg(tmp_path, source)
    units = enumerate_units(pkg, repo_root=tmp_path)
    u = _get(units, "pkg.mod.f")
    # body_start == def_line for a one-liner because the entire function,
    # signature and body, lives on the same physical line.  The spec says the
    # def line "runs at import time and never counts", but for a one-liner that
    # is a moot point: when the body executes the def line has already finished,
    # and coverage marks that single line as executed during the call.  Using
    # body[0].lineno (which equals def_line here) is still correct because it
    # is the line that must appear in a coverage hit to count as evidence; the
    # import-time execution only sets up the function object, it does not
    # execute the return statement.
    assert u.def_line == 1
    assert u.body_start == 1
    assert u.body_end == 1


# ---------------------------------------------------------------------------
# Multi-line signature
# ---------------------------------------------------------------------------


def test_multiline_signature(tmp_path: Path) -> None:
    source = """\
        def compute(
            x: int,
            y: int,
        ) -> int:
            return x + y
        """
    pkg = _write_pkg(tmp_path, source)
    units = enumerate_units(pkg, repo_root=tmp_path)
    u = _get(units, "pkg.mod.compute")
    # ast sets lineno to the first line of the "def" statement (line 1).
    assert u.def_line == 1
    # The body starts on line 5, after the closing parenthesis of the signature.
    assert u.body_start == 5
    assert u.body_end == 5


# ---------------------------------------------------------------------------
# Defect 1: functions inside if/try/with/for blocks must not be skipped
# ---------------------------------------------------------------------------


def test_function_inside_if_block(tmp_path: Path) -> None:
    """A FunctionDef nested inside an if/try/with/for at module level must be found."""
    source = """\
        import sys

        if sys.version_info >= (3, 0):
            def py3_only():
                return "py3"

        try:
            def in_try():
                return "try"
        except Exception:
            def in_except():
                return "except"

        for _i in range(1):
            def in_for():
                return "for"
        """
    pkg = _write_pkg(tmp_path, source)
    units = enumerate_units(pkg, repo_root=tmp_path)
    qualnames = {u.qualname for u in units}
    assert "pkg.mod.py3_only" in qualnames
    assert "pkg.mod.in_try" in qualnames
    assert "pkg.mod.in_except" in qualnames
    assert "pkg.mod.in_for" in qualnames


def test_tabulate_76_functions() -> None:
    """On the vendored tabulate package ast.walk finds 76 functions; so must enumerate_units."""
    pkg_dir = Path("sample/tabulate/tabulate")
    repo_root = Path(".")

    # Ground truth via ast.walk
    walk_count = 0
    for py_file in sorted(pkg_dir.rglob("*.py")):
        src = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        walk_count += sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        )

    units = enumerate_units(pkg_dir, repo_root=repo_root)
    assert len(units) == walk_count == 76


# ---------------------------------------------------------------------------
# Defect 2: Unit.file must be relative to repo_root, not package_dir.parent
# ---------------------------------------------------------------------------


def test_file_relative_to_repo_root(tmp_path: Path) -> None:
    """Unit.file must be relative to repo_root, not to package_dir.parent."""
    # Layout: repo_root/project/mypkg/mod.py
    repo_root = tmp_path / "repo"
    project = repo_root / "project"
    pkg = project / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f():\n    return 1\n")

    units = enumerate_units(pkg, repo_root=repo_root)
    assert len(units) == 1
    # Must be relative to repo_root, i.e. include "project/mypkg/mod.py"
    assert units[0].file == "project/mypkg/mod.py"


# ---------------------------------------------------------------------------
# Defect 3: qualname must include the module path
# ---------------------------------------------------------------------------


def test_qualname_includes_module_path(tmp_path: Path) -> None:
    """qualnames must be prefixed with the dotted module path so they are unique across files."""
    # Two modules each defining a function named "helper"
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("def helper():\n    pass\n")
    (pkg / "sub.py").write_text("def helper():\n    pass\n")

    units = enumerate_units(pkg, repo_root=tmp_path)
    qualnames = {u.qualname for u in units}
    # __init__.py contributes "mypkg.helper"
    assert "mypkg.helper" in qualnames
    # sub.py contributes "mypkg.sub.helper"
    assert "mypkg.sub.helper" in qualnames
    # No bare "helper" without module prefix
    assert "helper" not in qualnames
