#!/usr/bin/env python3
"""Verify the official bpy wheel before a bounded module-only runtime proof."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

NAME = "bpy-4.5.9-cp311-cp311-manylinux_2_28_x86_64.whl"
SHA256 = "0bca32fe0658388f5ef669631220d7147fc2544bb0103a0042603519552b6b6a"
BYTES = 373033590
parser = argparse.ArgumentParser()
parser.add_argument("--wheel-dir", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
if sys.version_info[:2] != (3, 11):
    raise SystemExit("PYTHON_3_11_REQUIRED")
out = Path(args.out).resolve()
out.mkdir(parents=True, exist_ok=False)
try:
    wheel = Path(args.wheel_dir).resolve() / NAME
    if not wheel.is_file() or wheel.stat().st_size != BYTES:
        raise ValueError("OFFICIAL_WHEEL_SIZE")
    digest = hashlib.sha256()
    with wheel.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != SHA256:
        raise ValueError("OFFICIAL_WHEEL_SHA256")
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], check=True)
    import bpy
    if tuple(bpy.app.version) != (4, 5, 9):
        raise ValueError("BPY_VERSION")
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    report = {
        "ok": True, "scope": "Blender module-only runtime; no original character loaded or edited",
        "wheel_sha256": SHA256, "wheel_bytes": BYTES, "blender_version": bpy.app.version_string,
        "cycles_built": bool(bpy.app.build_options.cycles),
        "autoexec_enabled": bpy.context.preferences.filepaths.use_scripts_auto_execute,
        "limits": ["Published Python dependencies are not installed in this first bounded import probe",
                   "No render, clothing, animation or exported GLB is approved by this probe"],
    }
    (out / "bpy-runtime.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("BPY_RUNTIME " + json.dumps(report), flush=True)
except Exception as error:
    failure = {"ok": False, "scope": "Verified official bpy module",
               "error_type": type(error).__name__, "code": "BPY_RUNTIME_FAILED"}
    if isinstance(error, ModuleNotFoundError):
        failure.update(code="MODULE_MISSING", module=error.name)
    elif isinstance(error, ValueError):
        failure["code"] = str(error)
    (out / "bpy-failure.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
    print("BPY_RUNTIME " + json.dumps(failure), flush=True)
    raise SystemExit(1)
