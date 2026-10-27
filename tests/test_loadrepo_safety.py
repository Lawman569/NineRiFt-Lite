"""Security regression tests for FWGet.loadRepo.

History: loadRepo() parsed repository JSON with eval(file.read()) in both
code paths (fresh download and offline cache fallback) — arbitrary code
from a compromised/hostile repository host executed as Python (RCE).

Post-fix contract:
  * payload parsing is strict JSON (json.loads), never eval
  * the decoded document is validated against the expected repo shape
    before any instance state mutation
  * malformed/foreign payload => return False, state untouched, no crash

These tests deliberately avoid executing malicious payloads; the
execution-safety proof is structural (AST lint: no eval/exec anywhere in
fwget.py), mirroring tests/test_string_clscmp.py.

fwget imports cleanly on Termux (no Kivy), so these drive the real class
with a monkeypatched `requests` - no network touched.
"""
import ast
import json
import pathlib
import shutil
import tempfile
import unittest

import fwget

VALID_JSON = json.dumps({
    "repo": {
        "infos": {
            "name": "test-repo",
            "dirname": "testrepo",
            "files_URL": "http://files.fake/",
        },
        "files": {"DRV": ["1.0"], "BMS": ["2.0"], "BLE": ["3.0"]},
    }
})

# valid under Python's eval (single quotes), invalid JSON — eval would
# happily load it; json.loads must refuse.
PYTHON_LITERAL = (
    "{'repo': {'infos': {'name': 'py-literal', 'dirname': 'pydir',"
    " 'files_URL': 'http://files.fake/eval-does-not-belong-here/'},"
    " 'files': {'DRV': [], 'BMS': [], 'BLE': []}}}"
)

# JSON with the shape silently wrong: loadRepo must refuse instead of
# crashing (pre-fix it raised KeyError mid-way, after mutating(dirname))
MISSING_FILES_JSON = json.dumps({
    "repo": {"infos": {"name": "broken", "dirname": "nope"}, "files_URL": "http://files.fake/"}
})
REPO_URL = "http://repo.fake/fw/repo.json"


class FakeResponse:
    def __init__(self, status_code=200, content=b"", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


class FakeRequests:
    def __init__(self, served=b"", offline=False):
        self.served = self._ensure_bytes(served)
        self.offline = offline
        self._real = fwget.requests

    @staticmethod
    def _ensure_bytes(b):
        return b.encode() if isinstance(b, str) else b

    def head(self, url, *a, **kw):
        return FakeResponse(500 if self.offline else 200)

    def get(self, url, *a, **kw):
        if self.offline:
            raise fwget.requests.ConnectionError("offline")
        return FakeResponse(200, content=self.served)


def make_fwget(served, offline=False):
    """Real FWGet with requests monkeypatched; returns (fw, fake)."""
    fake = FakeRequests(served, offline)
    fwget.requests = fake
    cache = tempfile.mkdtemp()
    fw = fwget.FWGet(cache)
    fw.repoURL = REPO_URL
    return fw, fake, cache


class TestLoadRepoSafety(unittest.TestCase):
    def setUp(self):
        self._real_requests = fwget.requests

    def tearDown(self):
        fwget.requests = self._real_requests
        if getattr(self, "cache", None):
            shutil.rmtree(self.cache, ignore_errors=True)

    def _fresh(self, served=b"", offline=False):
        self.req = FakeRequests(served, offline)
        fwget.requests = self.req
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)
        self.fw = fwget.FWGet(self.cache)
        return self.fw

    def test_valid_repo_payload_fully_loads(self):
        fw = self._fresh(VALID_JSON)
        result = fw.loadRepo(REPO_URL)
        self.assertTrue(result[0])
        self.assertEqual(fw.dirname, "testrepo")
        self.assertEqual(fw.repoURL, "http://files.fake/")
        self.assertEqual([fw.DRV, fw.BMS, fw.BLE], [["1.0"], ["2.0"], ["3.0"]])

    def test_python_literal_payload_rejected(self):
        fw = self._fresh(PYTHON_LITERAL)
        self.assertFalse(fw.loadRepo(REPO_URL))
        self.assertEqual(fw.dirname, "null")
        self.assertEqual(fw.repoURL, REPO_URL)
        self.assertEqual([fw.DRV, fw.BMS, fw.BLE], [[], [], []])

    def test_json_missing_required_keys_rejected(self):
        fw = self._fresh(MISSING_FILES_JSON)
        self.assertFalse(fw.loadRepo(REPO_URL))
        self.assertEqual(fw.dirname, "null")
        self.assertEqual([fw.DRV, fw.BMS, fw.BLE], [[], [], []])

    def test_cache_fallback_with_invalid_json_rejected(self):
        fw = self._fresh(offline=True)
        hashed = __import__("hashlib").md5(REPO_URL.encode()).hexdigest()
        with open(self.cache + hashed + ".json", "w") as f:
            f.write(PYTHON_LITERAL)
        self.assertFalse(fw.loadRepo(REPO_URL))
        self.assertEqual(fw.dirname, "null")

    def test_no_eval_or_exec_in_fwget_module(self):
        tree = ast.parse(pathlib.Path(fwget.__file__).read_text())
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id in ("eval", "exec"):
                    bad.append(f"line {node.lineno}: {fn.id}(...)")
        self.assertEqual([], bad)
