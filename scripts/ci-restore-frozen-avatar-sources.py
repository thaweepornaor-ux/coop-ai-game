#!/usr/bin/env python3
"""Restore one pinned Actions source artifact for inspection only; execute no archive file."""
import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = "thaweepornaor-ux/coop-ai-game"
ARTIFACT, RUN = 11688851271, 38103066739
COMMIT = "2ab008ad76d7dbfe798f49318b00ae8faf989e48"
ZIP_BYTES = 180865809
ZIP_SHA = "1d6054aad6deccaff326f750ec82bba75bee83c4253e4dcb75da6ce842d503d8"
ARCHIVE_FILES, ARCHIVE_BYTES = 68, 180849901
SOURCE_FILES, SOURCE_BYTES = 60, 179992532
SOURCE_PREFIX = "sources/assets/characters/"
CREDIT_SUFFIXES = (
    "assets/characters/LICENSES.md",
    "assets/characters/rain/ATTRIBUTION.txt",
    "assets/characters/snow/ATTRIBUTION.txt",
)
CHUNK, ENTRY_LIMIT, FILE_LIMIT = 1048576, 256, 25000000
SAFE_CODES = frozenset((
    "posix_required", "missing_token", "invalid_arguments", "unsafe_restore_dir",
    "unsafe_report_path",
    "unsafe_redirect", "redirect_limit", "oversized_metadata",
    "frozen_artifact_mismatch", "archive_exceeds_size", "archive_checksum_mismatch",
    "unsafe_zip_entry", "nonempty_directory", "duplicate_archive_entry",
    "archive_entry_limit_exceeded", "archive_count_bytes_mismatch",
    "source_count_bytes_mismatch", "file_directory_collision",
    "missing_or_duplicate_credit", "unsafe_destination",
    "entry_exceeds_size", "entry_size_crc_mismatch", "written_entry_mismatch",
    "restored_inventory_mismatch", "original_not_readonly", "manifest_budget_exceeded",
))

def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")

def hash_crc(path):
    digest, crc, size = hashlib.sha256(), 0, 0
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(CHUNK), b""):
            size += len(data)
            if size > FILE_LIMIT:
                raise ValueError("entry_exceeds_size")
            digest.update(data)
            crc = binascii.crc32(data, crc)
    return size, digest.hexdigest(), format(crc & 0xffffffff, "08x")

class NoAuthRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.redirects = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirects += 1
        if self.redirects > 5:
            raise ValueError("redirect_limit")
        try:
            url = urllib.parse.urlsplit(newurl)
            valid = (req.get_method() == "GET" and code in (301, 302, 303, 307, 308)
                     and url.scheme == "https" and bool(url.hostname)
                     and url.username is None and url.password is None
                     and url.port in (None, 443)
                     and not any(ord(c) < 32 or ord(c) == 127 for c in newurl))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("unsafe_redirect")
        # Construct a fresh request: never forward Authorization, Cookie or API headers.
        # Signed redirect URLs are used only in memory and never saved or logged.
        return urllib.request.Request(newurl, headers={"Accept": "application/octet-stream"}, method="GET")

def api(suffix, token):
    return urllib.request.Request("https://api.github.com/repos/" + REPO + suffix,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"}, method="GET")

def checked_name(info):
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
    elif not 0 <= info.file_size <= FILE_LIMIT:
        raise ValueError("unsafe_zip_entry")
    return clean

def mkdir_checked(base, relative):
    current = base
    for part in PurePosixPath(relative).parts:
        current = current / part
        if not current.exists():
            current.mkdir(mode=0o700)
        if current.is_symlink() or not current.is_dir():
            raise ValueError("unsafe_destination")
        if not current.resolve().is_relative_to(base):
            raise ValueError("unsafe_destination")
    return current

class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # Do not echo arbitrary command-line argument contents.
        raise ValueError("invalid_arguments")

def restore():
    root, report, stage = None, None, "setup"
    try:
        if os.name != "posix":
            raise ValueError("posix_required")
        token = os.environ.get("GH_TOKEN", "")
        if not token:
            raise ValueError("missing_token")
        parser = SafeParser(add_help=False)
        parser.add_argument("--out", required=True)
        parser.add_argument("--report", required=True)
        args = parser.parse_args()
        candidate = Path(args.out)
        report_candidate = Path(args.report)
        if not candidate.is_absolute() or candidate.is_symlink() or candidate.exists():
            raise ValueError("unsafe_restore_dir")
        if (not report_candidate.is_absolute() or report_candidate.is_symlink()
                or report_candidate.exists()):
            raise ValueError("unsafe_report_path")
        root = candidate.resolve()
        originals = root / "originals"
        if report_candidate.resolve().is_relative_to(root):
            raise ValueError("unsafe_report_path")
        report = report_candidate.resolve()
        report.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.mkdir(parents=True, exist_ok=False, mode=0o700)
        originals.mkdir(mode=0o700)
        redirect_handler = NoAuthRedirect()
        opener = urllib.request.build_opener(redirect_handler)

        stage = "metadata"
        with opener.open(api("/actions/artifacts/" + str(ARTIFACT), token), timeout=90) as response:
            raw = response.read(CHUNK + 1)
        if len(raw) > CHUNK:
            raise ValueError("oversized_metadata")
        meta = json.loads(raw)
        if (meta.get("id") != ARTIFACT or meta.get("name") != "avatar-render-originals"
                or meta.get("expired") is not False or meta.get("size_in_bytes") != ZIP_BYTES
                or meta.get("digest") != "sha256:" + ZIP_SHA
                or meta.get("workflow_run", {}).get("id") != RUN
                or meta.get("workflow_run", {}).get("head_sha") != COMMIT):
            raise ValueError("frozen_artifact_mismatch")

        stage = "download"
        original_zip = root / "original.zip"
        digest, downloaded = hashlib.sha256(), 0
        with opener.open(api("/actions/artifacts/" + str(ARTIFACT) + "/zip", token), timeout=90) as response:
            with original_zip.open("xb") as output:
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
        original_zip.chmod(0o444)

        stage = "zip_directory"
        records = []
        with zipfile.ZipFile(original_zip) as source:
            infos = source.infolist()
            if len(infos) > ENTRY_LIMIT:
                raise ValueError("archive_entry_limit_exceeded")
            paths = [checked_name(info) for info in infos]
            portable = [unicodedata.normalize("NFC", name).casefold() for name in paths]
            if len(paths) != len(set(paths)) or len(portable) != len(set(portable)):
                raise ValueError("duplicate_archive_entry")
            files = [info for info in infos if not info.is_dir()]
            directories = [info.filename for info in infos if info.is_dir()]
            if len(files) != ARCHIVE_FILES or sum(info.file_size for info in files) != ARCHIVE_BYTES:
                raise ValueError("archive_count_bytes_mismatch")
            sources = [info for info in files if info.filename.startswith(SOURCE_PREFIX)]
            if len(sources) != SOURCE_FILES or sum(info.file_size for info in sources) != SOURCE_BYTES:
                raise ValueError("source_count_bytes_mismatch")
            file_names = {info.filename for info in files}
            for name in paths:
                if any(parent.as_posix() in file_names for parent in PurePosixPath(name).parents):
                    raise ValueError("file_directory_collision")
            credits = []
            for suffix in CREDIT_SUFFIXES:
                matching = [info.filename for info in sources
                            if info.filename == suffix or info.filename.endswith("/" + suffix)]
                if len(matching) != 1:
                    raise ValueError("missing_or_duplicate_credit")
                credits.append(matching[0])

            stage = "extract"
            for info in infos:
                relative = info.filename.rstrip("/")
                if info.is_dir():
                    mkdir_checked(originals, relative)
                    continue
                parent = mkdir_checked(originals, PurePosixPath(relative).parent.as_posix())
                target = parent / PurePosixPath(relative).name
                if target.exists() or target.is_symlink() or not target.resolve().is_relative_to(originals):
                    raise ValueError("unsafe_destination")
                checksum, crc, size = hashlib.sha256(), 0, 0
                with source.open(info) as inp, target.open("xb") as output:
                    while True:
                        data = inp.read(CHUNK)
                        if not data:
                            break
                        size += len(data)
                        if size > info.file_size:
                            raise ValueError("entry_exceeds_size")
                        checksum.update(data)
                        crc = binascii.crc32(data, crc)
                        output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                    os.fchmod(output.fileno(), 0o444)
                crc &= 0xffffffff
                if size != info.file_size or crc != info.CRC:
                    raise ValueError("entry_size_crc_mismatch")
                records.append({"path": relative, "bytes": size,
                    "sha256": checksum.hexdigest(), "crc32": format(crc, "08x"),
                    "is_character_source": relative.startswith(SOURCE_PREFIX),
                    "is_credit": relative in credits,
                    "original_zip_compressed_bytes": info.compress_size,
                    "original_zip_method": info.compress_type, "restored_mode": "0444"})

        stage = "verify_restored"
        actual_files = set()
        for target in originals.rglob("*"):
            if target.is_symlink():
                raise ValueError("unsafe_destination")
            if target.is_file():
                actual_files.add(target.relative_to(originals).as_posix())
                mode = target.stat().st_mode
                if not stat.S_ISREG(mode) or mode & 0o333:
                    raise ValueError("original_not_readonly")
        if actual_files != {record["path"] for record in records}:
            raise ValueError("restored_inventory_mismatch")
        for record in records:
            size, checksum, crc = hash_crc(originals / record["path"])
            if (size != record["bytes"] or checksum != record["sha256"] or crc != record["crc32"]):
                raise ValueError("written_entry_mismatch")
        # Source files and original license/credit text are byte-for-byte unchanged.
        for directory in sorted((p for p in originals.rglob("*") if p.is_dir()),
                                key=lambda p: len(p.parts), reverse=True):
            directory.chmod(0o555)
        originals.chmod(0o555)

        stage = "manifest"
        manifest = {"schema_version": 1, "ok": True, "purpose": "Frozen originals for inspection only",
            "repository": REPO, "original_artifact_id": ARTIFACT, "original_run": RUN,
            "original_commit": COMMIT, "original_artifact_name": "avatar-render-originals",
            "original_archive": {"bytes": downloaded, "sha256": ZIP_SHA,
                "github_digest_verified": True, "preserved_file": "original.zip"},
            "archive_entry_count": len(infos), "archive_file_count": ARCHIVE_FILES,
            "archive_file_bytes": ARCHIVE_BYTES, "source_prefix": SOURCE_PREFIX,
            "source_file_count": SOURCE_FILES, "source_bytes": SOURCE_BYTES,
            "original_directories": directories, "credit_paths": sorted(credits),
            "entries": sorted(records, key=lambda record: record["path"]),
            "all_restored_hashes_and_crc_rechecked": True,
            "hash_basis": "Pinned original ZIP SHA256; per-file hashes computed and rechecked after extraction",
            "archive_files_executed": False, "originals_readonly": True,
            "model_or_game_approved": False}
        payload = encoded(manifest)
        if len(payload) > CHUNK:
            raise ValueError("manifest_budget_exceeded")
        manifest_file = root / "restore-manifest.json"
        manifest_file.write_bytes(payload)
        manifest_file.chmod(0o444)
        with report.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), 0o444)
        readme = root / "README.txt"
        readme.write_text("Inspection-only restore of the pinned avatar-render-originals artifact.\n"
            "All 68 original files, including all 60 character source files and credit files, "
            "remain byte-for-byte unchanged under originals/. Files are 0444 and directories 0555.\n"
            "No original file was executed, imported, rendered, converted or approved. "
            "The original ZIP is retained read-only. restore-manifest.json contains provenance, "
            "SHA256 and CRC32 records. These records are anchored by the pinned ZIP checksum; "
            "they are not an independent pre-existing per-file hash list.\n", encoding="utf-8")
        readme.chmod(0o444)
        print("AVATAR_FROZEN_RESTORE " + json.dumps({"ok": True,
            "archive_files": ARCHIVE_FILES, "archive_bytes": ARCHIVE_BYTES,
            "source_files": SOURCE_FILES, "source_bytes": SOURCE_BYTES,
            "original_sha256": ZIP_SHA, "readonly": True, "executed": False,
            "model_or_game_approved": False}), flush=True)
        return 0
    except Exception as error:
        failure = {"ok": False, "stage": stage, "error_type": type(error).__name__}
        if (isinstance(error, ValueError) and len(error.args) == 1
                and isinstance(error.args[0], str) and error.args[0] in SAFE_CODES):
            failure["error_code"] = error.args[0]
        if isinstance(error, urllib.error.HTTPError):
            failure["http_status"] = error.code
        if root is not None and root.is_dir():
            try:
                (root / "restore-failure.json").write_bytes(encoded(failure))
            except OSError:
                pass
        if report is not None:
            try:
                with report.open("xb") as output:
                    output.write(encoded(failure))
            except OSError:
                pass
        # No exception message, body, header, environment, token, request or signed URL is logged.
        print("AVATAR_FROZEN_RESTORE_FAILED " + json.dumps(failure), flush=True)
        return 1

if __name__ == "__main__":
    sys.exit(restore())
