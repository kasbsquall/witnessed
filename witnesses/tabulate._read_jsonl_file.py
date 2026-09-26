import sys
sys.path.insert(0, "sample/tabulate")

from tabulate import _read_jsonl_file

import io
fobject = io.StringIO('{"id": 1, "name": "Alice"}\n{"id": 2, "name": "Bob"}\n')
result = _read_jsonl_file(fobject)

assert len(result) == 2
assert result[0]["name"] == "Alice"
