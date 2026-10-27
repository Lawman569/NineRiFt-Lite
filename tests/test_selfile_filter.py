"""Regression test for firmware file filter selection (selfile_filter).

Extracted via AST so the suite runs without Kivy (Termux limitation).
Covered filter matrix: m365 (DRV version-aware, others plain .bin),
m365pro (DRV encrypted, others plain), esx/max (always encrypted).

Guards the historical bug: `if mod is 'esx' or 'max':` evaluated always-true
and clobbered every model's filter to '*.bin.enc', making plain .bin M365
firmware unselectable.
"""
import ast
import pathlib
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
MAIN = str(REPO / "main.py")


def from_class(path, cls, name, ns):
    for node in ast.walk(ast.parse(pathlib.Path(path).read_text())):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    exec(compile(ast.Module(body=[item], type_ignores=[]), path, "exec"), ns)
                    return ns[name]
    raise LookupError(f"{cls}.{name} not found")


CASES = [
    ("m365", "<141", "BLE", ["*.bin", "!.md5"]),
    ("m365", ">=141", "DRV", ["*.bin.enc", "!.md5"]),
    ("m365", "<141", "DRV", ["*.bin", "!.md5"]),
    ("m365pro", "?", "DRV", ["*.bin.enc", "!.md5"]),
    ("m365pro", "?", "BMS", ["*.bin", "!.md5"]),
    ("esx", "?", "BLE", ["*.bin.enc", "!.md5"]),
    ("max", "?", "DRV", ["*.bin.enc", "!.md5"]),
]


class TestSelfileFilter(unittest.TestCase):
    def test_filter_matrix(self):
        fn = from_class(MAIN, "NineRiFt", "selfile_filter", {})
        for mod, vers, dev, expected in CASES:
            with self.subTest(mod=mod, vers=vers, dev=dev):
                self.assertEqual(expected, fn(None, mod, vers, dev))


if __name__ == "__main__":
    unittest.main()
