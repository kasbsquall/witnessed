# Fixture package used by tests/test_observe.py.
# Three functions: test calls suite_fn, usage calls used_fn, nobody calls untouched.


def suite_fn():
    """Called only by the test suite."""
    return "tested"


def used_fn():
    """Called only by the usage script."""
    return "used"


def untouched():
    """Never called by any baseline."""
    return "untouched"
