#!/usr/bin/env python3
"""Restore frozen native reference data as read-only bytes; execute no archive content."""
import argparse, binascii, hashlib, importlib.util, json, os, stat, struct, sys
from pathlib import Path, PurePosixPath
import unicodedata, urllib.error, urllib.request, zipfile

HELPER_BLOB = "571484eedb1566ab96a23672aada5449f35da618"
ARTIFACT, RUN = 11955076458, 38696896433
COMMIT = "88cf00944ab8b61ba401b37d955cff5502b73b13"
NAME = "avatar-snow-glb-native48-candidate"
ZIP_BYTES, ZIP_SHA = 31224659, "e6ee96d87d3d05fa6ef857b938226a8e27d44994255f8d59fe8dfa7542edb9ed"
PINNED_FILES = {
    "native_reference.npz": (31443671, "6dca400a201b003e7ed81c8556d06cfa5afde07edad30705e2bf22ee487d9f94"),
    "native_reference.json": (143763, "83471e5eb420f716ef024b04e660ba29ba975f6e13a52835f65498c964fecb9d"),
    "glb-correctives-audit.json": (110470, "3a3e7016883e6998180ece3a24f7efecfc06f50b202890265aa59aa4af372fa7"),
}
CHUNK, MAX_ENTRY, MAX_TOTAL, MAX_ENTRIES = 1048576, 33554432, 33554432, 64
MAPPING = {
    "snow/native_reference.npz": "native_reference.npz",
    "snow/native_reference.json": "native_reference.json",
    "snow/glb-correctives-audit.json": "glb-correctives-audit.json",
    "snow/credits/LICENSES.md": "credits/LICENSES.md",
    "snow/credits/rain/ATTRIBUTION.txt": "credits/rain/ATTRIBUTION.txt",
    "snow/credits/snow/ATTRIBUTION.txt": "credits/snow/ATTRIBUTION.txt",
}
SAFE = frozenset(("posix_required", "missing_token", "invalid_arguments", "unsafe_restore_dir",
    "unsafe_report_path", "trusted_restore_helper_mismatch", "oversized_metadata",
    "frozen_artifact_mismatch", "archive_exceeds_size", "archive_checksum_mismatch",
    "archive_entry_limit_exceeded", "archive_count_bytes_mismatch", "unsafe_zip_entry",
    "duplicate_archive_entry", "file_directory_collision", "missing_or_duplicate_target",
    "unsafe_destination", "entry_exceeds_size", "entry_size_crc_mismatch", "written_entry_mismatch",
    "reference_checksum_mismatch", "restored_inventory_mismatch", "original_not_readonly",
    "manifest_budget_exceeded", "unsafe_redirect", "redirect_limit"))
def load_helper():
    path = Path(__file__).with_name("ci-restore-frozen-avatar-sources.py")
    raw = path.read_bytes()
    digest = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if digest != HELPER_BLOB:
        raise ValueError("trusted_restore_helper_mismatch")
    spec = importlib.util.spec_from_file_location("_reviewed_avatar_restore", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
def hash_crc_bounded(path):
    digest, crc, size = hashlib.sha256(), 0, 0
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(CHUNK), b""):
            size += len(data)
            if size > MAX_ENTRY:
                raise ValueError("entry_exceeds_size")
            digest.update(data)
            crc = binascii.crc32(data, crc)
    return size, digest.hexdigest(), format(crc & 0xffffffff, "08x")

def checked_archive_name(info):
    name = info.filename
    clean = name[:-1] if info.is_dir() else name
    path = PurePosixPath(clean)
    kind = stat.S_IFMT(info.external_attr >> 16)
    if (not clean or info.orig_filename != name or len(name) > 1024
            or clean.startswith("/") or "\\" in name or ":" in name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or path.as_posix() != clean or ".." in path.parts
            or len(path.parts) > 16 or info.flag_bits & 1
            or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
            or (info.is_dir() and kind == stat.S_IFREG)
            or (not info.is_dir() and kind == stat.S_IFDIR)
            or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
        raise ValueError("unsafe_zip_entry")
    if info.is_dir():
        if info.file_size != 0:
            raise ValueError("nonempty_directory")
    elif not 0 <= info.file_size <= MAX_ENTRY:
        raise ValueError("unsafe_zip_entry")
    return clean

def no_zip64(info):
    if info.extract_version >= 45:
        raise ValueError("unsafe_zip_entry")
    data, cursor = info.extra, 0
    while cursor < len(data):
        if cursor + 4 > len(data):
            raise ValueError("unsafe_zip_entry")
        kind, length = struct.unpack_from("<HH", data, cursor)
        cursor += 4
        if cursor + length > len(data) or kind == 1:
            raise ValueError("unsafe_zip_entry")
        cursor += length
def main():
    root, report, stage = None, None, "setup"
    try:
        if os.name != "posix":
            raise ValueError("posix_required")
        helper = load_helper()
        parser = helper.SafeParser(add_help=False)
        parser.add_argument("--out", required=True)
        parser.add_argument("--report", required=True)
        args = parser.parse_args()
        candidate, report_candidate = Path(args.out), Path(args.report)
        if not candidate.is_absolute() or candidate.exists() or candidate.is_symlink():
            raise ValueError("unsafe_restore_dir")
        if (not report_candidate.is_absolute() or report_candidate.exists()
                or report_candidate.is_symlink()):
            raise ValueError("unsafe_report_path")
        root, report = candidate.resolve(), report_candidate.resolve()
        if report.is_relative_to(root):
            raise ValueError("unsafe_report_path")
        token = os.environ.get("GH_TOKEN", "")
        if not token:
            raise ValueError("missing_token")
        root.mkdir(parents=True, exist_ok=False, mode=0o700)
        checkpoint = root / "checkpoint"
        checkpoint.mkdir(mode=0o700)
        report.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        opener = urllib.request.build_opener(helper.NoAuthRedirect())
        stage = "metadata"
        with opener.open(helper.api("/actions/artifacts/" + str(ARTIFACT), token), timeout=90) as response:
            raw = response.read(CHUNK + 1)
        if len(raw) > CHUNK:
            raise ValueError("oversized_metadata")
        meta = json.loads(raw)
        if (meta.get("id") != ARTIFACT or meta.get("name") != NAME
                or meta.get("expired") is not False or meta.get("size_in_bytes") != ZIP_BYTES
                or meta.get("digest") != "sha256:" + ZIP_SHA
                or meta.get("workflow_run", {}).get("id") != RUN
                or meta.get("workflow_run", {}).get("head_sha") != COMMIT):
            raise ValueError("frozen_artifact_mismatch")
        stage = "download"
        archive, downloaded, digest = root / "prototype.zip", 0, hashlib.sha256()
        with opener.open(helper.api("/actions/artifacts/" + str(ARTIFACT) + "/zip", token), timeout=90) as response:
            with archive.open("xb") as output:
                while True:
                    data = response.read(CHUNK)
                    if not data:
                        break
                    downloaded += len(data)
                    if downloaded > ZIP_BYTES:
                        raise ValueError("archive_exceeds_size")
                    digest.update(data)
                    output.write(data)
                output.flush()
                os.fsync(output.fileno())
        del token
        if downloaded != ZIP_BYTES or digest.hexdigest() != ZIP_SHA:
            raise ValueError("archive_checksum_mismatch")
        archive.chmod(0o444)
        stage = "zip_directory"
        records, selected = [], {}
        with zipfile.ZipFile(archive) as source:
            infos = source.infolist()
            if not 1 <= len(infos) <= MAX_ENTRIES:
                raise ValueError("archive_entry_limit_exceeded")
            paths = [checked_archive_name(info) for info in infos]
            portable = [unicodedata.normalize("NFC", name).casefold() for name in paths]
            if len(paths) != len(set(paths)) or len(portable) != len(set(portable)):
                raise ValueError("duplicate_archive_entry")
            files = [info for info in infos if not info.is_dir()]
            if sum(info.file_size for info in files) > MAX_TOTAL:
                raise ValueError("archive_count_bytes_mismatch")
            names = {info.filename for info in files}
            for info in infos:
                no_zip64(info)
                if (info.file_size > MAX_ENTRY or (not info.is_dir()
                        and info.file_size / max(1, info.compress_size) > 4096)):
                    raise ValueError("unsafe_zip_entry")
                if any(p.as_posix() in names for p in PurePosixPath(info.filename).parents):
                    raise ValueError("file_directory_collision")
            for suffix, canonical in MAPPING.items():
                matches = [info for info in files if info.filename == suffix
                           or info.filename.endswith("/" + suffix)]
                if len(matches) != 1:
                    raise ValueError("missing_or_duplicate_target")
                selected[matches[0].filename] = canonical
            if len(selected) != len(MAPPING):
                raise ValueError("missing_or_duplicate_target")
            stage = "verify_all_entries_and_extract_selected"
            for info in files:
                canonical = selected.get(info.filename)
                target = None
                if canonical:
                    parent = helper.mkdir_checked(checkpoint, PurePosixPath(canonical).parent.as_posix())
                    target = parent / PurePosixPath(canonical).name
                    if target.exists() or target.is_symlink() or not target.resolve().is_relative_to(checkpoint):
                        raise ValueError("unsafe_destination")
                checksum, crc, size = hashlib.sha256(), 0, 0
                output = target.open("xb") if target else None
                try:
                    with source.open(info) as inp:
                        while True:
                            data = inp.read(CHUNK)
                            if not data:
                                break
                            size += len(data)
                            if size > info.file_size or size > MAX_ENTRY:
                                raise ValueError("entry_exceeds_size")
                            checksum.update(data)
                            crc = binascii.crc32(data, crc)
                            if output:
                                output.write(data)
                    if output:
                        output.flush()
                        os.fsync(output.fileno())
                        os.fchmod(output.fileno(), 0o444)
                finally:
                    if output:
                        output.close()
                crc &= 0xffffffff
                if size != info.file_size or crc != info.CRC:
                    raise ValueError("entry_size_crc_mismatch")
                entry = {"archive_path": info.filename, "canonical_path": canonical,
                    "bytes": size, "sha256": checksum.hexdigest(), "crc32": format(crc, "08x"),
                    "restored": target is not None}
                if target:
                    check_size, check_hash, check_crc = hash_crc_bounded(target)
                    if (check_size, check_hash, check_crc) != (size, checksum.hexdigest(), format(crc, "08x")):
                        raise ValueError("written_entry_mismatch")
                if canonical in PINNED_FILES:
                    if (size, checksum.hexdigest()) != PINNED_FILES[canonical]:
                        raise ValueError("reference_checksum_mismatch")
                records.append(entry)
        stage = "verify_readonly_inventory"
        actual = set()
        for path in checkpoint.rglob("*"):
            if path.is_symlink():
                raise ValueError("unsafe_destination")
            if path.is_file():
                actual.add(path.relative_to(checkpoint).as_posix())
                if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_mode & 0o333:
                    raise ValueError("original_not_readonly")
        if actual != set(MAPPING.values()):
            raise ValueError("restored_inventory_mismatch")
        manifest = {"schema_version": 1, "ok": True, "purpose": "Frozen native reference and failed-TRS checkpoint data for one cached export",
            "artifact_id": ARTIFACT, "run_id": RUN, "commit": COMMIT, "artifact_name": NAME,
            "archive_bytes": ZIP_BYTES, "archive_sha256": ZIP_SHA,
            "pinned_reference_files": {name: {"bytes": size, "sha256": digest} for name, (size, digest) in PINNED_FILES.items()},
            "archive_file_count": len(records), "restored_file_count": len(selected),
            "all_archive_crcs_verified": True, "all_restored_hashes_rechecked": True,
            "readonly": True, "archive_files_executed": False,
            "model_art_or_game_approved": False, "entries": records}
        payload = encoded(manifest)
        if len(payload) > CHUNK:
            raise ValueError("manifest_budget_exceeded")
        manifest_file = root / "restore-manifest.json"
        manifest_file.write_bytes(payload)
        manifest_file.chmod(0o444)
        for directory in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p:len(p.parts), reverse=True):
            directory.chmod(0o555)
        root.chmod(0o555)
        with report.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), 0o444)
        print("SNOW_FROZEN_NATIVE315_REFERENCE_RESTORED " + json.dumps({
            "ok": True, "artifact": ARTIFACT, "zip_bytes": ZIP_BYTES, "zip_sha256": ZIP_SHA,
            "archive_files_crc_checked": len(records), "selected_readonly_files": len(selected),
            "native_reference_npz_sha256": PINNED_FILES["native_reference.npz"][1], "executed": False, "model_approved": False}), flush=True)
        return 0
    except Exception as error:
        failure = {"ok": False, "stage": stage, "error_type": type(error).__name__}
        if (isinstance(error, ValueError) and len(error.args) == 1
                and isinstance(error.args[0], str) and error.args[0] in SAFE):
            failure["error_code"] = error.args[0]
        if isinstance(error, urllib.error.HTTPError):
            failure["http_status"] = error.code
        frames, node = [], error.__traceback__
        while node is not None:
            frames.append({"file": Path(node.tb_frame.f_code.co_filename).name[:128],
                           "line": node.tb_lineno, "function": node.tb_frame.f_code.co_name[:128]})
            frames = frames[-6:]
            node = node.tb_next
        failure["frames"] = frames
        if report is not None and not report.exists():
            try:
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_bytes(encoded(failure))
            except OSError:
                pass
        print("SNOW_FROZEN_NATIVE315_REFERENCE_RESTORE_FAILED " + json.dumps(failure), flush=True)
        return 1
if __name__ == "__main__":
    sys.exit(main())
