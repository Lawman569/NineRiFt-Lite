"""Regression lint: forbid identity comparisons (`is`/`is not`) with string
literals in app modules.

Why: identity relies on CPython string interning, which is an implementation
detail. Spinner/UI passes runtime-built strings, so `mod is 'esx'` silently
fails for non-interned strings.
"""
import ast
import pathlib
import unittest

APP_MODULES = ["main.py", "nbclient.py", "nbcmd.py", "utils.py",
               "fwupd.py", "fwget.py", "mocklink.py"]
REPO = pathlib.Path(__file__).resolve().parent.parent


def string_identity_comparisons():
    bad = []
    for mod in APP_MODULES:
        path = REPO / mod
        src = path.read_text()
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.Compare):
                continue
            for op, comp in zip(node.ops, node.comparators):
                if not isinstance(op, (ast.Is, ast.IsNot)):
                    continue
                literals = []
                if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                    literals.append(repr(comp.value))
                elif isinstance(comp, ast.Tuple):
                    literals += [repr(e.value) for e in comp.elts
                                 if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                if literals:
                    bad.append(f"{mod}:{node.lineno} {' or '.join(sorted(set(literals)))}")
    return bad


class TestNoStringIdentityComparison(unittest.TestCase):
    def test_app_modules_use_vs_is_for_strings(self):
        bad = string_identity_comparisons()
        self.assertEqual([], bad,
                         "identity comparison with str literal (fragile, "
                         "relies on interning) at:\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
