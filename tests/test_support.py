"""Shared AST helpers: lets tests exercise Kivy app code without importing Kivy.

Termux limitation: Kivy (and its SDL2/native loader) is not installable here, so
the app modules can't be imported directly. These helpers extract individual
functions by (class, method) and exec the raw AST into a caller-supplied
namespace, preserving exact behavior of the code under test.
"""
import ast
import copy
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent


def from_class(path, cls, name, ns):
    """Exec method `cls.name` from file at `path` into `ns` and return it."""
    tree = ast.parse(pathlib.Path(path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    raw = copy.deepcopy(item)
                    raw.decorator_list = []  # strip @mainthread/@sidethread; tests call raw logic
                    exec(compile(ast.Module(body=[raw], type_ignores=[]), path, "exec"), ns)
                    return ns[name]
    raise LookupError(f"{cls}.{name} not found in {path}")
