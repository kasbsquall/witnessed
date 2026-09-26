import io
import sys
sys.path.insert(0, "sample/tabulate")

from tabulate import _read_csv_file

fobject = io.StringIO("a,b,c\n1,2,3\n")
result = _read_csv_file(fobject)
assert len(result) == 2
assert result[0] == ["a", "b", "c"]
