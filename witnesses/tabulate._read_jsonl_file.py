import sys
sys.path.insert(0, "sample/tabulate")

import io
import tabulate as _tabulate_pkg

with open("sample/tabulate/examples/people.jsonl", "r") as fobject:
    result = _tabulate_pkg._read_jsonl_file(fobject)

assert len(result) == 2, f"Expected 2 rows, got {len(result)}"
assert isinstance(result[0], dict), "First element should be a dict"
assert result[0]["name"] == "Alice", f"Expected 'Alice', got {result[0]['name']}"
