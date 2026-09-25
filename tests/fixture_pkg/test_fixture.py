"""Fixture test suite: calls suite_fn only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mypkg import suite_fn


def test_suite():
    assert suite_fn() == "tested"
