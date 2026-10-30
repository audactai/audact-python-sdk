#!/usr/bin/env python3
"""Positive controls for check_dist.py. Run from sdk/python: python scripts/check_dist_test.py."""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

import build  # noqa: F401  (must be installed; a missing module fails the run)

HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent
CHECK = HERE / "check_dist.py"
LEAK_SCAN = (PKG_ROOT / ".." / ".." / "scripts" / "sdk" / "leak-scan.sh").resolve()

_state: dict[str, Path] = {}


def setUpModule() -> None:
    tmp = Path(tempfile.mkdtemp())
    _state["tmp"] = tmp
    src = tmp / "src"
    shutil.copytree(
        PKG_ROOT,
        src,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.egg-info", ".*_cache", "build", "dist",
            "test_parity.py", "test_schema_parity.py",
        ),
    )
    out = tmp / "built"
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(out), str(src)],
        check=True, capture_output=True,
    )
    _state["built"] = out


def tearDownModule() -> None:
    shutil.rmtree(_state["tmp"], ignore_errors=True)


def _rewrite_zip(src: Path, dst: Path, drop=None, add=None, edit=None) -> None:
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if drop and drop(item.filename):
                continue
            data = zin.read(item.filename)
            if edit and edit(item.filename):
                data = edit(item.filename)(data)
            zout.writestr(item, data)
        for name, data in (add or {}).items():
            zout.writestr(name, data)


def _rewrite_tar(src: Path, dst: Path, add: dict[str, bytes]) -> None:
    with tarfile.open(src, "r:gz") as tin, tarfile.open(dst, "w:gz") as tout:
        top = ""
        for m in tin.getmembers():
            top = top or m.name.split("/")[0]
            f = tin.extractfile(m) if m.isfile() else None
            tout.addfile(m, f)
        for name, data in add.items():
            ti = tarfile.TarInfo(f"{top}/{name}")
            ti.size = len(data)
            tout.addfile(ti, io.BytesIO(data))


class CheckDistTest(unittest.TestCase):
    def fresh(self) -> Path:
        d = Path(tempfile.mkdtemp(dir=_state["tmp"]))
        for p in _state["built"].iterdir():
            shutil.copy(p, d / p.name)
        return d

    def run_check(self, d: Path, leak: bool = False) -> tuple[int, str]:
        cmd = [sys.executable, str(CHECK), str(d)]
        if leak:
            cmd += ["--leak-scan", str(LEAK_SCAN)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return r.returncode, r.stdout + r.stderr

    def wheel(self, d: Path) -> Path:
        return next(d.glob("*.whl"))

    def swap_wheel(self, d: Path, **kw) -> None:
        whl = self.wheel(d)
        tmp = d / "new.whl.tmp"
        _rewrite_zip(whl, tmp, **kw)
        tmp.replace(whl)

    def test_1_unmodified_with_leak_scan(self) -> None:
        code, out = self.run_check(self.fresh(), leak=True)
        self.assertEqual(code, 0, out)
        self.assertIn("check_dist: OK", out)

    def test_2_extra_wheel_member(self) -> None:
        d = self.fresh()
        self.swap_wheel(d, add={"tests/test_x.py": b"x = 1\n"})
        code, out = self.run_check(d)
        self.assertEqual(code, 1, out)
        self.assertIn("unexpected file", out)

    def test_3_missing_py_typed(self) -> None:
        d = self.fresh()
        self.swap_wheel(d, drop=lambda n: n == "audact/py.typed")
        code, out = self.run_check(d)
        self.assertEqual(code, 1, out)
        self.assertIn("missing", out)

    def test_4_metadata_version(self) -> None:
        d = self.fresh()

        def edit(n: str):
            if n.endswith(".dist-info/METADATA"):
                return lambda b: b.replace(b"\nVersion: ", b"\nVersion: 9", 1)
            return None

        self.swap_wheel(d, edit=edit)
        code, out = self.run_check(d)
        self.assertEqual(code, 1, out)
        self.assertIn("metadata", out)

    def test_5_sdist_pycache(self) -> None:
        d = self.fresh()
        sd = next(d.glob("*.tar.gz"))
        tmp = d / "new.tmp"
        _rewrite_tar(sd, tmp, {"audact/__pycache__/x.pyc": b"\0"})
        tmp.replace(sd)
        code, out = self.run_check(d)
        self.assertEqual(code, 1, out)
        self.assertIn("unexpected file", out)

    def test_6_planted_secret(self) -> None:
        d = self.fresh()
        secret = ("aud_" + "live_" + "0123456789abcdef" * 2).encode()
        self.swap_wheel(
            d,
            edit=lambda n: (lambda b: b + b"# " + secret + b"\n") if n == "audact/pii.py" else None,
        )
        code, out = self.run_check(d, leak=True)
        self.assertEqual(code, 1, out)
        # Same build without the flag passes: the flag is what catches the planted key.
        code2, out2 = self.run_check(d)
        self.assertEqual(code2, 0, out2)
        self.assertIn("leak scan: skipped (no --leak-scan given)", out2)


if __name__ == "__main__":
    unittest.main()
