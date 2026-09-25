import sys
sys.path.insert(0, "sample/tabulate")

import tabulate as _tabulate_module

with open("sample/tabulate/examples/people.csv", newline="") as f:
    result = _tabulate_module._read_csv_file(f)

assert len(result) > 0, "Expected non-empty result"
assert result[0][0] == "id", f"Expected first header to be 'id', got {result[0][0]!r}"
