#!/usr/bin/env python3
"""Prove official Blender tooling independently of blocked character source downloads."""
import argparse
import json
from pathlib import Path
import runpy
import subprocess
import urllib.error

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
args = parser.parse_args()
root = Path(args.out).resolve()
root.mkdir(parents=True, exist_ok=False)
archives = root / "archives"
archives.mkdir()
reports = root / "reports"
reports.mkdir()
acquire = runpy.run_path("scripts/ci-acquire-avatar-sources.py")
try:
    binary, provenance = acquire["install_blender"](archives, root / "tools")
    version = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=30)
    if version.returncode != 0 or "Blender 4.5.9" not in version.stdout:
        raise ValueError("BLENDER_VERSION_EXECUTION_FAILED")
    report = {"ok": True, "scope": "Official Blender executable only; no character opened or edited",
              "provenance": provenance, "version": version.stdout.splitlines()[0]}
    (reports / "blender-runtime.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
except Exception as error:
    failure = {"ok": False, "scope": "Blender tooling acquisition",
               "error_type": type(error).__name__, "code": "BLENDER_TOOLING_FAILED"}
    if isinstance(error, urllib.error.HTTPError):
        failure.update(code="HTTP_REQUEST_REJECTED", http_status=int(error.code))
        error.close()
    elif isinstance(error, ValueError):
        failure["code"] = str(error)
    (reports / "blender-failure.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
    print(json.dumps(failure))
    raise SystemExit(1)
