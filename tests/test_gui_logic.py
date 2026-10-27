"""Behavioral regression tests for main.py command dispatch and model
selection, using runtime-built (non-interned) strings — the same shapes that
Kivy spinners deliver, which exposed the `is <literal>` bugs.
"""
import types
import unittest

from test_support import from_class, REPO

MAIN = str(REPO / "main.py")

CMDS = ["lock", "unlock", "reboot", "powerdown", "sniff", "info"]


class FakeCom:
    def __init__(self):
        self.device = ""
        self.new_sn = ""
        self.calls = []
    def dump(self, d): self.calls.append(("dump", d))
    def changesn(self, s): self.calls.append(("changesn", s))
    def __getattr__(self, n):
        def m(*a): self.calls.append((n,) + a)
        return m


def make_app(state="connected"):
    app = types.SimpleNamespace(
        com=FakeCom(),
        conn=types.SimpleNamespace(state=state),
        msgs=[])
    ns = {"tprint": app.msgs.append}
    fn = from_class(MAIN, "NineRiFt", "executecmd", ns)
    return app, fn


def norm(c):
    return "".join(list(c))


class TestExecutecmdDispatch(unittest.TestCase):
    def test_every_command_dispatches_with_runtime_string(self):
        for c in CMDS:
            with self.subTest(command=c):
                app, executecmd = make_app()
                executecmd(app, norm(c))
                self.assertIn((c,), app.com.calls)
                self.assertIn(c + " execute", app.msgs)

    def test_dump_routes_device(self):
        app, executecmd = make_app()
        app.com.device = "drv"
        executecmd(app, norm("dump"))
        self.assertEqual([("dump", "drv")], app.com.calls)

    def test_dump_without_device_prompts(self):
        app, executecmd = make_app()
        executecmd(app, norm("dump"))
        self.assertEqual([], app.com.calls)
        self.assertIn("set device first", app.msgs)

    def test_changesn_routes_new_sn(self):
        app, executecmd = make_app()
        app.com.new_sn = "ABC123"
        executecmd(app, norm("changesn"))
        self.assertEqual([("changesn", "ABC123")], app.com.calls)

    def test_changesn_without_sn_prompts(self):
        app, executecmd = make_app()
        executecmd(app, norm("changesn"))
        self.assertIn("set NewSN first", app.msgs)

    def test_disconnected_never_dispatches(self):
        app, executecmd = make_app(state="disconnected")
        executecmd(app, norm("lock"))
        self.assertEqual([], app.com.calls)


class TestSelectModel(unittest.TestCase):
    def _run(self, mod):
        app = types.SimpleNamespace(versel=False, hasextbms=False)
        fn = from_class(MAIN, "NineRiFt", "select_model", {})
        values = fn(app, mod)
        return app, values

    def test_esx_extends_bms_support(self):
        app, values = self._run("es" + "x")
        self.assertTrue(app.hasextbms)
        self.assertIn("ExtBMS", values)

    def test_max_no_bms_support(self):
        app, values = self._run("ma" + "x")
        self.assertFalse(app.hasextbms)
        self.assertNotIn("ExtBMS", values)

    def test_m365_requires_version_selector(self):
        app, values = self._run("m36" + "5")
        self.assertTrue(app.versel)

    def test_m365pro_no_version_selector(self):
        app, values = self._run("m365" + "pro")
        self.assertFalse(app.versel)


if __name__ == "__main__":
    unittest.main()
