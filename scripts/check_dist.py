#!/usr/bin/env python3
"""Check a built wheel and sdist before publishing.

usage: check_dist.py <distdir> [--leak-scan <path>]

Verifies the wheel's exact file set, its metadata, an install smoke test in a fresh
virtualenv, and the sdist's contents. With --leak-scan, both archives are unpacked and the
given scanner is run on the result. Standard library only.
"""

from __future__ import annotations

import argparse
import email.parser
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent
SRC = PKG_ROOT / "audact"
REPO_URL = "https://github.com/audactai/audact-python-sdk"

SMOKE = """
import importlib.resources
import sys

import audact
from audact import AudactAPIError, AudactClient

expected, venv_root = sys.argv[1], sys.argv[2]
assert audact.__version__ == expected, (audact.__version__, expected)
AudactClient(api_key="x")
assert importlib.resources.files("audact").joinpath("py.typed").is_file(), "py.typed missing"
assert audact.__file__ is not None
assert "site-packages" in audact.__file__, audact.__file__
assert audact.__file__.startswith(venv_root), audact.__file__
assert issubclass(AudactAPIError, Exception)
print("smoke ok")
"""

SDIST_FORBIDDEN = re.compile(
    r"(^|/)(__pycache__|\.venv|dist|build)(/|$)|\.pyc$|(^|/)\.env[^/]*$"
)


def source_version() -> str:
    text = (SRC / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__ = "([0-9]+\.[0-9]+\.[0-9]+[^"]*)"$', text, re.M)
    if not m:
        raise SystemExit("check_dist: cannot find __version__ in audact/__init__.py")
    return m.group(1)


def project_name() -> str:
    with open(PKG_ROOT / "pyproject.toml", "rb") as fh:
        return str(tomllib.load(fh)["project"]["name"])


def check_wheel(whl: Path, version: str, name: str, failures: list[str]) -> None:
    dist_info = f"{name}-{version}.dist-info"
    expected = {f"audact/{p.name}" for p in SRC.glob("*.py")}
    expected.add("audact/py.typed")
    expected |= {
        f"{dist_info}/{n}"
        for n in ("METADATA", "WHEEL", "RECORD", "top_level.txt", "licenses/LICENSE")
    }
    with zipfile.ZipFile(whl) as zf:
        names = {n for n in zf.namelist() if not n.endswith("/")}
        for n in sorted(names - expected):
            failures.append(f"unexpected file: {whl.name}: {n}")
        for n in sorted(expected - names):
            failures.append(f"missing: {whl.name}: {n}")
        meta_name = next((n for n in names if n.endswith(".dist-info/METADATA")), None)
        if meta_name is None:
            failures.append("metadata: METADATA not found")
            return
        meta = email.parser.Parser().parsestr(zf.read(meta_name).decode("utf-8"))
    want = {
        "Name": name,
        "Version": version,
        "License-Expression": "MIT",
        "Requires-Python": ">=3.11",
        "Description-Content-Type": "text/markdown",
    }
    for key, val in want.items():
        got = meta.get(key)
        if got != val:
            failures.append(f"metadata: {key} is {got!r}, want {val!r}")
    if not any(REPO_URL in u for u in (meta.get_all("Project-URL") or [])):
        failures.append(f"metadata: no Project-URL contains {REPO_URL}")


def check_sdist(sdist: Path, failures: list[str]) -> None:
    with tarfile.open(sdist, "r:gz") as tf:
        members = [m.name for m in tf.getmembers()]
    rels = [m.split("/", 1)[1] if "/" in m else "" for m in members]
    for m, rel in zip(members, rels, strict=True):
        if not rel:
            continue
        if SDIST_FORBIDDEN.search(rel):
            failures.append(f"unexpected file: {sdist.name}: {m}")
        parts = rel.split("/")
        for i, part in enumerate(parts):
            if part.endswith(".egg-info") and i > 0:
                failures.append(f"unexpected file: {sdist.name}: {m} (nested egg-info)")
                break
    relset = set(rels)
    for req in ("LICENSE", "pyproject.toml", "README.md", "audact/py.typed"):
        if req not in relset:
            failures.append(f"missing: {sdist.name}: {req}")


def install_smoke(whl: Path, version: str, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as cwd:
        venv_dir = Path(tmp) / "venv"
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        py = venv_dir / "bin" / "python"
        r = subprocess.run(
            [str(py), "-m", "pip", "install", "-q", str(whl)],
            capture_output=True, text=True, check=False,
        )
        if r.returncode != 0:
            failures.append(f"install: pip install failed: {r.stderr.strip()}")
            return
        r = subprocess.run(
            [str(py), "-I", "-c", SMOKE, version, str(venv_dir.resolve())],
            cwd=cwd, capture_output=True, text=True, check=False,
        )
        if r.returncode != 0:
            failures.append(f"install: smoke failed: {(r.stderr or r.stdout).strip()}")


def leak_scan(whl: Path, sdist: Path, scanner: str, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(whl) as zf:
            zf.extractall(root / "wheel")
        with tarfile.open(sdist, "r:gz") as tf:
            tf.extractall(root / "sdist", filter="data")
        r = subprocess.run(
            [scanner, str(root)], capture_output=True, text=True, check=False
        )
        if r.returncode != 0:
            out = (r.stdout + r.stderr).strip()
            failures.append(f"leak scan: scanner exited {r.returncode}: {out}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Check a built wheel and sdist.")
    ap.add_argument("distdir", type=Path)
    ap.add_argument("--leak-scan", dest="leak_scan", default=None)
    args = ap.parse_args(argv)

    wheels = sorted(args.distdir.glob("*.whl"))
    sdists = sorted(args.distdir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        print(
            f"check_dist: need exactly one .whl and one .tar.gz in {args.distdir} "
            f"(found {len(wheels)} and {len(sdists)})"
        )
        return 1

    version, name = source_version(), project_name()
    failures: list[str] = []
    check_wheel(wheels[0], version, name, failures)
    check_sdist(sdists[0], failures)
    install_smoke(wheels[0], version, failures)
    if args.leak_scan:
        leak_scan(wheels[0], sdists[0], args.leak_scan, failures)
    else:
        print("leak scan: skipped (no --leak-scan given)")

    for f in failures:
        print(f)
    if failures:
        return 1
    print("check_dist: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
