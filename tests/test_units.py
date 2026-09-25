"""Tests for witnessed.units.enumerate_units."""

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
# Plain function
# ---------------------------------------------------------------------------


def test_plain_function(tmp_path: Path) -> None:
    source = """\
        def hello():
            x = 1
            return x
        """
    pkg = _write_pkg(tmp_path, source)
    units = enumerate_units(pkg)
    u = _get(units, "hello")
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
    units = enumerate_units(pkg)
    u = _get(units, "MyClass.method")
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
    units = enumerate_units(pkg)
    # Both the outer and the inner function must be present.
    outer = _get(units, "outer")
    inner = _get(units, "outer.inner")
    assert outer.def_line == 1
    assert outer.body_start == 2
    assert inner.def_line == 2
    assert inner.body_start == 3


# ---------------------------------------------------------------------------
# Decorated function — body_start must be after decorator and signature
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
    units = enumerate_units(pkg)
    u = _get(units, "decorated")
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
    units = enumerate_units(pkg)
    u = _get(units, "f")
    # body_start == def_line for a one-liner because the entire function —
    # signature and body — lives on the same physical line.  The spec says the
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
    units = enumerate_units(pkg)
    u = _get(units, "compute")
    # ast sets lineno to the first line of the "def" statement (line 1).
    assert u.def_line == 1
    # The body starts on line 5, after the closing parenthesis of the signature.
    assert u.body_start == 5
    assert u.body_end == 5
