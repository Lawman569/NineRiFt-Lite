"""Regression tests for the firmware-flash progress bar.

KV binds per-frame updates via::

    ProgressBar:
        value: app.fwupd.progress
        max: app.fwupd.maxprog

so FWUpd.progress/maxprog must be Kivy properties (declared at class level);
plain attributes bound once in __init__ never emit change events, so the bar
would freeze at 0 forever. Tests enforce that wiring structurally, plus a
behavioral guard on update_progress.

Termux limitation: Kivy itself can't be imported here, so property-ness is
verified via AST inspection of the source instead of instantiation.
"""
import ast
import copy
import pathlib
import types
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
FWUPD = str(REPO / "fwupd.py")
MAIN = str(REPO / "main.py")
KV = str(REPO / "ninerift.kv")


def from_class(path, cls, name, ns):
    """Exec raw method logic (decorators stripped) without importing Kivy."""
    tree = ast.parse(pathlib.Path(path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    raw = copy.deepcopy(item)
                    raw.decorator_list = []
                    exec(compile(ast.Module(body=[raw], type_ignores=[]), path, "exec"), ns)
                    return ns[name]
    raise LookupError(f"{cls}.{name} not found in {path}")


def is_numeric_property_call(decl):
    for node in ast.walk(decl):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            if name == "NumericProperty":
                return True
    return False


class TestFWUpdProgressProperties(unittest.TestCase):
    def test_progress_and_maxprog_are_kivy_properties(self):
        tree = ast.parse(pathlib.Path(FWUPD).read_text())
        bound = set()
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name != "FWUpd":
                continue
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and is_numeric_property_call(stmt):
                    bound |= {t.id if isinstance(t, ast.Name) else t.attr for t in stmt.targets}
        self.assertIn("progress", bound)
        self.assertIn("maxprog", bound)

    def test_update_progress_sets_values(self):
        fn = from_class(FWUPD, "FWUpd", "update_progress", {})
        fw = types.SimpleNamespace(progress=0, maxprog=100)
        fn(fw, 7, 130)
        self.assertEqual((7, 130), (fw.progress, fw.maxprog))


class TestProgressbarWireup(unittest.TestCase):
    def test_kv_binds_to_fwupd(self):
        kv = pathlib.Path(KV).read_text()
        self.assertIn("value: app.fwupd.progress", kv)
        self.assertIn("max: app.fwupd.maxprog", kv)

    def test_main_py_has_no_undefined_flashscreen_reference(self):
        # `FlashScreen` exists only as a KV rule; referencing it from Python
        # is an interpreter NameError waiting to happen.
        self.assertNotIn("FlashScreen", pathlib.Path(MAIN).read_text())


if __name__ == "__main__":
    unittest.main()
