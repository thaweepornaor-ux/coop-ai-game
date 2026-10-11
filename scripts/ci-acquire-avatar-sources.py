#!/usr/bin/env python3
"""Acquire official avatar sources in a fresh CI directory and inspect raw Blender data."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile

MIB = 1024 * 1024
MODELS = {
    "Snow": {
        "url": "https://studio.blender.org/download-source/files/ba/0f/ba0fe6d810333b1d73c1c359e4dc03cb-6.zip",
        "page": "https://studio.blender.org/characters/snow/v4/",
        "credit": "Snow Rig (CC) Blender Foundation | studio.blender.org",
    },
    "Rain": {
        "url": "https://studio.blender.org/download-source/files/ee/a7/eea73e55dba1cea31c09848df6a794b2-4.zip",
        "page": "https://studio.blender.org/characters/rain/v3/",
        "credit": "Rain Rig (CC) Blender Foundation | studio.blender.org",
    },
}
BLENDER_NAME = "blender-4.5.9-linux-x64.tar.xz"
BLENDER_BASE = "https://download.blender.org/release/Blender4.5/"
STAGE_CONTEXT = {"asset": "none", "stage": "startup"}
REPORTS_DIR = None

def set_stage(asset, stage):
    STAGE_CONTEXT.update(asset=asset, stage=stage)
    print("ASSET_STAGE " + json.dumps(STAGE_CONTEXT), flush=True)

def download(url, target, limit, asset):
    set_stage(asset, "download")
    digest, size = hashlib.sha256(), 0
    with urllib.request.urlopen(url, timeout=120) as response, target.open("xb") as output:
        while True:
            block = response.read(MIB)
            if not block:
                break
            size += len(block)
            if size > limit:
                raise ValueError("DOWNLOAD_LIMIT")
            digest.update(block)
            output.write(block)
    return {"bytes": size, "sha256": digest.hexdigest()}

def safe_zip(archive, destination):
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        if len(entries) > 4096 or sum(i.file_size for i in entries) > 1024 * MIB:
            raise ValueError("ZIP_LIMIT")
        seen = set()
        for entry in entries:
            name = entry.filename
            parts = PurePosixPath(name)
            if ("\\" in name or ":" in name or parts.is_absolute()
                    or ".." in parts.parts or not parts.parts):
                raise ValueError("ZIP_PATH")
            if name in seen or entry.flag_bits & 1:
                raise ValueError("ZIP_DUPLICATE_OR_ENCRYPTED")
            seen.add(name)
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError("ZIP_SPECIAL_FILE")
            (destination / name).resolve().relative_to(destination.resolve())
        if package.testzip() is not None:
            raise ValueError("ZIP_CRC")
        destination.mkdir()
        for entry in entries:
            target = destination / entry.filename
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with package.open(entry) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, MIB)
    files = sorted(p for p in destination.rglob("*") if p.is_file())
    return {
        "zip_crc": "pass",
        "blend_files": [str(p.relative_to(destination)) for p in files if p.suffix.lower() == ".blend"],
        "python_files": [str(p.relative_to(destination)) for p in files if p.suffix.lower() == ".py"],
        "license_files": [str(p.relative_to(destination)) for p in files
                          if re.search(r"license|licence|copyright|readme", p.name, re.I)],
        "file_count": len(files),
    }

def install_blender(archives, tools):
    checksum_file = archives / "blender-4.5.9.sha256"
    download(BLENDER_BASE + checksum_file.name, checksum_file, 64 * 1024, "Blender.checksum")
    set_stage("Blender.checksum", "parse-official-checksum")
    expected = []
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*") == BLENDER_NAME:
            if re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
                expected.append(fields[0].lower())
    if len(expected) != 1:
        raise ValueError("OFFICIAL_SHA256_ENTRY")
    archive = archives / BLENDER_NAME
    actual = download(BLENDER_BASE + BLENDER_NAME, archive, 512 * MIB, "Blender.binary")
    set_stage("Blender.binary", "verify-sha256")
    if actual["sha256"] != expected[0]:
        raise ValueError("BLENDER_SHA256")
    tools.mkdir()
    set_stage("Blender.binary", "validate-extract-tar")
    with tarfile.open(archive, "r:xz") as package:
        members = package.getmembers()
        if len(members) > 20000 or sum(m.size for m in members) > 3072 * MIB:
            raise ValueError("TAR_LIMIT")
        package.extractall(tools, filter="data")
    binaries = [p for p in tools.glob("*/blender") if p.is_file()]
    if len(binaries) != 1:
        raise ValueError("BLENDER_BINARY")
    return binaries[0], {**actual, "official_sha256": expected[0], "verified": True}

def main():
    global REPORTS_DIR
    if sys.version_info < (3, 12):
        raise ValueError("PYTHON_3_12_REQUIRED")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--inspector", required=True)
    args = parser.parse_args()
    root = Path(args.out).resolve()
    inspector = Path(args.inspector).resolve()
    if not inspector.is_file():
        raise ValueError("INSPECTOR_MISSING")
    root.mkdir(parents=True, exist_ok=False)
    archives = root / "archives"
    sources = root / "sources"
    reports = root / "reports"
    for path in (archives, sources, reports):
        path.mkdir()
    REPORTS_DIR = reports
    manifest = {"stage": "original-source-inspection", "models": {}}
    for name, metadata in MODELS.items():
        archive = archives / (name.lower() + ".zip")
        package = download(metadata["url"], archive, 200 * MIB, name + ".archive")
        set_stage(name + ".archive", "validate-crc-extract-zip")
        inventory = safe_zip(archive, sources / name)
        if not inventory["blend_files"] or len(inventory["blend_files"]) > 8:
            raise ValueError("BLEND_COUNT")
        manifest["models"][name] = {
            **metadata, **package, **inventory,
            "license": "CC-BY; retain archive notices and confirm their version",
            "hash_origin": "computed project pin; not an official Blender-published model checksum",
        }
    blender, blender_info = install_blender(archives, root / "tools")
    manifest["blender"] = blender_info
    manifest["blender"]["binary"] = str(blender.relative_to(root))
    (reports / "source-inventory.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for name, model in manifest["models"].items():
        for number, relative in enumerate(model["blend_files"]):
            set_stage(name + ".blend-" + str(number), "inspect-raw-datablocks")
            blend = sources / name / relative
            output = reports / (name.lower() + "-" + str(number) + ".json")
            command = [
                str(blender), "--factory-startup", "--background", "--disable-autoexec",
                "--disable-depsgraph-on-file-load", "--python-exit-code", "1",
                str(blend), "--python", str(inspector), "--", "--out", str(output),
            ]
            run = subprocess.run(command, capture_output=True, text=True, timeout=180)
            output.with_suffix(".log").write_text(run.stdout + run.stderr, encoding="utf-8")
            if run.returncode or not output.is_file():
                raise ValueError("BLENDER_INSPECTION_FAILED_" + name)
            report = json.loads(output.read_text(encoding="utf-8"))
            print("INSPECT_SUMMARY " + json.dumps({
                "model": name, "blend_file": relative, "blender": report["blender_version"],
                "objects_by_type": report["objects_by_type"],
                "materials": len(report["materials"]), "images": len(report["images"]),
                "actions": len(report["actions"]),
                "shape_key_blocks": sum(len(o.get("shape_keys", [])) for o in report["objects"]),
                "rigs": [{"name": o["name"], "bones": o["bone_count"],
                          "deform_bones": o["deform_bone_count"], "bbones": o["bbone_segmented_count"]}
                         for o in report["objects"] if o["type"] == "ARMATURE"],
            }))
    print(json.dumps({"ok": True, "reports": str(reports), "models": {
        name: {"bytes": model["bytes"], "sha256": model["sha256"],
               "blend_files": model["blend_files"], "license_files": model["license_files"]}
        for name, model in manifest["models"].items()}}))

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        failure = {"ok": False, **STAGE_CONTEXT, "error_type": type(error).__name__,
                   "code": "ACQUISITION_OR_INSPECTION_FAILED"}
        if isinstance(error, urllib.error.HTTPError):
            failure.update(code="HTTP_REQUEST_REJECTED", http_status=int(error.code))
            error.close()
        elif isinstance(error, ValueError) and re.fullmatch(r"[A-Za-z0-9_]{1,80}", str(error)):
            failure["code"] = str(error)
        print(json.dumps(failure), flush=True)
        if REPORTS_DIR is not None:
            try:
                (REPORTS_DIR / "acquisition-failure.json").write_text(
                    json.dumps(failure, indent=2), encoding="utf-8")
            except OSError:
                pass
        raise SystemExit(1)
