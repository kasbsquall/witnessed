"""Fixture usage script: calls used_fn only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mypkg import used_fn

if __name__ == "__main__":
    result = used_fn()
    print(result)
