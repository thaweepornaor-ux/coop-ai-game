"""Acquire only pinned, licensed original source files; never execute mirror code."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "mnanimat/software_mnanimat3d"
COMMIT = "d95dff4711bab14cd93aac7f2cb4368d872d1c33"
CREDITS = {
    "assets/characters/LICENSES.md",
    "assets/characters/rain/ATTRIBUTION.txt",
    "assets/characters/snow/ATTRIBUTION.txt",
}
MODELS = {
    "rain": "assets/characters/rain/original/Rain v3.3/rain_v3.2.blend",
    "snow": "assets/characters/snow/original/Snow/snow_v4.2.blend",
}
PREFIXES = (
    "assets/characters/rain/original/Rain v3.3/",
    "assets/characters/snow/original/Snow/",
)

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")

def validate_manifest(value):
    if value.get("repository") != REPOSITORY or value.get("commit") != COMMIT:
        raise ValueError("unapproved_manifest_pin")
    files = value.get("files")
    if not isinstance(files, list) or len(files) != 60:
        raise ValueError("unexpected_file_count")
    seen = set()
    total = 0
    for entry in files:
        name = entry.get("path")
        if not isinstance(name, str):
            raise ValueError("invalid_path_type")
        parts = PurePosixPath(name).parts
        if (not parts or name.startswith("/") or "\\" in name or ":" in name
                or any(p in ("", ".", "..") for p in parts)
                or PurePosixPath(name).as_posix() != name or name in seen):
            raise ValueError("unsafe_or_duplicate_path")
        if name not in CREDITS and not (
                name.startswith(PREFIXES) and name.endswith((".blend", ".png"))):
            raise ValueError("unapproved_source_file")
        size = entry.get("bytes")
        if type(size) is not int or not 0 < size <= 128 * 1024 * 1024:
            raise ValueError("invalid_source_size")
        if not re.fullmatch(r"[0-9a-f]{40}", entry.get("git_blob_sha1", "")):
            raise ValueError("invalid_blob_pin")
        seen.add(name)
        total += size
    if (total != 179992532 or value.get("total_bytes") != total
            or value.get("total_files") != len(files)
            or not CREDITS.issubset(seen) or not set(MODELS.values()).issubset(seen)):
        raise ValueError("manifest_totals_or_required_files_mismatch")
    return files

def acquire(entry, source_root):
    relative = entry["path"]
    target = source_root.joinpath(*PurePosixPath(relative).parts)
    if not target.resolve().is_relative_to(source_root.resolve()):
        raise ValueError("target_outside_source_root")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError("target_already_exists")
    partial = target.with_name(target.name + ".part")
    expected = entry["bytes"]
    blob_hash = hashlib.sha1()
    blob_hash.update(b"blob " + str(expected).encode("ascii") + b"\0")
    sha256 = hashlib.sha256()
    size = 0
    url = ("https://raw.githubusercontent.com/" + REPOSITORY + "/" + COMMIT + "/"
           + urllib.parse.quote(relative, safe="/"))
    try:
        # Public, immutable source URL only: no tokens, identity changes or retries.
        with urllib.request.urlopen(url, timeout=90) as response, partial.open("xb") as handle:
            if response.status != 200:
                raise ValueError("unexpected_http_status")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > expected:
                    raise ValueError("source_exceeds_declared_size")
                blob_hash.update(chunk)
                sha256.update(chunk)
                handle.write(chunk)
        if size != expected or blob_hash.hexdigest() != entry["git_blob_sha1"]:
            raise ValueError("source_size_or_git_blob_hash_mismatch")
        partial.rename(target)
    finally:
        if partial.exists():
            partial.unlink()
    return {
        "path": relative, "bytes": size,
        "git_blob_sha1": blob_hash.hexdigest(), "sha256": sha256.hexdigest(),
    }

def bounded_child_text(value):
    # Child reads public original assets only. Strip URLs and terminal controls.
    value = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value or "")
    value = re.sub(r"(?:https?|ftp|file)://[^\s\"'<>]+", "<URL_REMOVED>", value)
    value = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", value)
    lines = value.splitlines()
    text = "\n".join(lines[-30:])
    return text[-8000:]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--manifest", default=str(
        Path(__file__).with_name("avatar-source-mirror-manifest.json")))
    parser.add_argument("--wrapper", default=str(
        Path(__file__).with_name("bpy-inspect-avatar-source.py")))
    parser.add_argument("--inspector", default=str(
        Path(__file__).with_name("blender-inspect-avatar.py")))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    reports = out / "reports"
    reports.mkdir()
    sources = out / "sources"
    sources.mkdir()
    report_path = reports / "acquisition.json"
    report = {
        "ok": False, "repository": REPOSITORY, "commit": COMMIT,
        "stage": "manifest", "accepted_files": [], "inspections": [],
        "note": "Pinned original mirror files only; no adapted GLBs or mirror scripts executed.",
    }
    write_json(report_path, report)
    try:
        manifest_text = Path(args.manifest).read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        entries = validate_manifest(manifest)
        (out / "pinned-source-manifest.json").write_text(manifest_text, encoding="utf-8")
        for entry in entries:
            report["stage"] = "source_file"
            report["declared_file"] = entry["path"]
            write_json(report_path, report)
            accepted = acquire(entry, sources)
            report["accepted_files"].append(accepted)
            write_json(report_path, report)
        report["download_complete"] = True
        report.pop("declared_file", None)
        write_json(report_path, report)
        if not args.download_only:
            for model_id, blend_path in MODELS.items():
                report["stage"] = model_id + ".raw_library_inventory"
                write_json(report_path, report)
                destination = reports / (model_id + "-raw-inventory.json")
                result = subprocess.run(
                    [args.python, str(Path(args.wrapper).resolve()),
                     "--blend", str(sources.joinpath(*PurePosixPath(blend_path).parts)),
                     "--out", str(destination),
                     "--inspector", str(Path(args.inspector).resolve())],
                    capture_output=True, text=True, timeout=300, check=False,
                )
                # Child only reads public files and metadata. Keep its diagnostic evidence.
                (reports / (model_id + "-inspector-stdout.txt")).write_text(
                    result.stdout, encoding="utf-8")
                (reports / (model_id + "-inspector-stderr.txt")).write_text(
                    result.stderr, encoding="utf-8")
                if result.returncode != 0 or not destination.is_file():
                    report["child_exit_code"] = result.returncode
                    report["child_diagnostic"] = {
                        "stdout_tail": bounded_child_text(result.stdout),
                        "stderr_tail": bounded_child_text(result.stderr),
                    }
                    write_json(report_path, report)
                    print(json.dumps({"CHILD_INSPECTION_FAILED": {
                        "stage": report["stage"],
                        "child_returncode": result.returncode,
                        **report["child_diagnostic"],
                    }}, ensure_ascii=True), flush=True)
                    raise RuntimeError("raw_inventory_process_failed")
                inventory = json.loads(destination.read_text(encoding="utf-8"))
                summary = {
                    "model": model_id,
                    "blender_version": inventory["blender_version"],
                    "load_mode": inventory["source_loading"]["mode"],
                    "objects_by_type": inventory["objects_by_type"],
                    "materials": len(inventory["materials"]),
                    "images": len(inventory["images"]),
                    "actions": len(inventory["actions"]),
                    "armatures": [{
                        "name": o["name"], "bones": o["bone_count"],
                        "deform_bones": o["deform_bone_count"],
                    } for o in inventory["objects"] if o["type"] == "ARMATURE"],
                }
                report["inspections"].append(summary)
                write_json(report_path, report)
                print(json.dumps({"RAW_SOURCE_INVENTORY": summary}), flush=True)
        report.update({"ok": True, "stage": "complete", "total_files": len(entries),
                       "total_bytes": sum(e["bytes"] for e in entries),
                       "license_and_credits_preserved": True})
        write_json(report_path, report)
        print(json.dumps({"SOURCE_ACQUISITION_COMPLETE": {
            "files": len(entries), "bytes": report["total_bytes"],
            "original_sources_only": True, "rendered": False,
        }}), flush=True)
        return 0
    except Exception as error:
        failure = {"error_type": type(error).__name__}
        if isinstance(error, urllib.error.HTTPError):
            failure["http_status"] = error.code
        if isinstance(error, subprocess.TimeoutExpired):
            failure["timeout_seconds"] = 300
        # Never serialize exception messages, redirect URLs, response headers or bodies.
        report["failure"] = failure
        write_json(report_path, report)
        print(json.dumps({"SOURCE_ACQUISITION_FAILED": {
            "stage": report["stage"], "declared_file": report.get("declared_file"),
            "child_returncode": report.get("child_exit_code"),
            "download_complete": report.get("download_complete", False),
            **failure,
        }}), flush=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
