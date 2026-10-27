"""Regression tests for duplicate firmware downloads in FWGet.Gimme.

`Gimme()` used to call `getFile()` twice unconditionally. The `getboth`
toggle makes the *second* call target the plain `.bin` instead of
`.bin.enc` — meaningful only for m365 + DRV, which needs both files.
For every other combination both calls fetch the identical URL, and the
toggle never reset afterwards, so a later DRV fetch behaved differently
depending on session history.

Tests drive the real FWGet class with `requests` monkeypatched so no
network is touched: fwget is importable on Termux (no Kivy needed).
"""
import hashlib
import os
import sys
import tempfile
import types
import unittest

import fwget

PAYLOAD = b"NINERIFT-TEST-FIRMWARE"
MD5 = hashlib.md5(PAYLOAD).hexdigest()


class FakeResponse:
    def __init__(self, status_code=200, content=b"", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


class FakeRequests:
    """Serves in-memory firmware files; records every call for assertions."""

    def __init__(self):
        self.calls = []

    def head(self, url, *a, **kw):
        self.calls.append(("head", url))
        return FakeResponse(200)

    def get(self, url, *a, **kw):
        self.calls.append(("get", url))
        if url.endswith(".md5"):
            return FakeResponse(200, content=MD5.encode(), text=MD5)
        return FakeResponse(200, content=PAYLOAD)

    def file_urls(self):
        return [u for op, u in self.calls if op == "get" and not u.endswith(".md5")]


class TestGimmeDownloadCount(unittest.TestCase):
    def setUp(self):
        self._real_requests = fwget.requests
        self.addCleanup(setattr, fwget, "requests", self._real_requests)

    def make_fwget(self):
        req = FakeRequests()
        fwget.requests = req
        cache = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(cache, ignore_errors=True))
        fw = fwget.FWGet(cache)
        fw.dirname = "testrepo"
        fw.repoURL = "http://fake/"
        return req, fw

    def test_m365_drv_downloads_both_enc_and_plain(self):
        # intended historical behavior: DRV targets fetch .bin.enc AND .bin
        self.req, self.fw = self.make_fwget()
        self.fw.setModel("m365")
        self.fw.Gimme("DRV", "1.0")
        names = sorted(u.rsplit("/", 1)[1] for u in self.req.file_urls())
        self.assertEqual(names, ["DRV1.0.bin", "DRV1.0.bin.enc"])

    def test_m365_ble_downloads_once(self):
        self.req, self.fw = self.make_fwget()
        self.fw.setModel("m365")
        self.fw.Gimme("BLE", "1.0")
        names = sorted(u.rsplit("/", 1)[1] for u in self.req.file_urls())
        self.assertEqual(["BLE1.0.bin"], names)

    def test_m365_bms_downloads_once(self):
        self.req, self.fw = self.make_fwget()
        self.fw.setModel("m365")
        self.fw.Gimme("BMS", "1.0")
        names = sorted(u.rsplit("/", 1)[1] for u in self.req.file_urls())
        self.assertEqual(["BMS1.0.bin"], names)

    def test_other_models_download_once(self):
        for model in ("esx", "max"):
            with self.subTest(model=model):
                self.req, self.fw = self.make_fwget()
                fwget.requests = self.req
                self.fw.setModel(model)
                self.fw.Gimme("DRV", "1.0")
                names = sorted(u.rsplit("/", 1)[1] for u in self.req.file_urls())
                self.assertEqual(["DRV1.0.bin.enc"], names)

    def test_repeated_drv_downloads_both_each_time(self):
        # behavior must not depend on session history (getboth leak)
        self.req, self.fw = self.make_fwget()
        self.fw.setModel("m365")
        self.fw.Gimme("DRV", "1.0")
        self.req.calls.clear()
        self.fw.Gimme("DRV", "2.0")
        names = sorted(u.rsplit("/", 1)[1] for u in self.req.file_urls())
        self.assertEqual(names, ["DRV2.0.bin", "DRV2.0.bin.enc"])

    def test_getboth_flag_reset_after_gimme(self):
        self.req, self.fw = self.make_fwget()
        self.fw.setModel("m365")
        self.fw.Gimme("DRV", "1.0")
        self.assertFalse(self.fw.getboth)


if __name__ == "__main__":
    unittest.main()
