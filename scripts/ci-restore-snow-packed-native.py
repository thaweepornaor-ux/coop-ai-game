#!/usr/bin/env python3
"""Restore one selected packed native from two frozen chunks; execute no archive content."""
import argparse, binascii, hashlib, importlib.util, json, os, stat, struct, sys
from pathlib import Path, PurePosixPath
import unicodedata, urllib.error, urllib.request, zipfile

HELPER_BLOB = "571484eedb1566ab96a23672aada5449f35da618"
RUN = 38752917367
COMMIT = "4973159799789e7548403bc8d27abab0e72c60f3"
CHUNK, MAX_ENTRY, MAX_BLEND, MAX_ENTRIES = 1048576, 67108864, 134217728, 64
BLEND_FILE = "snow-packed-used-textures-candidate.blend"
BLEND_BYTES = 105085368
BLEND_SHA = "fb75dbf2b1141b59d90296951941eb3849d2ddc7afa71326ac97f20bd9c6e0e4"
SNAPSHOT_SHA = "b213ebabbe6027c0c2e59df506d32d7fa15d05f9a0a6807b23100d8bc73fd98a"
CREDITS = {
    "credits/LICENSES.md": [
        1559,
        "21ffbcb7404ceeb59a8038da34ad28df24ee3f390d33f9c16bac04952cbab71c"
    ],
    "credits/rain/ATTRIBUTION.txt": [
        292,
        "41d2a5693de42c5ee60dafaea599dfadd5a34ede8554a4d8a7c98af0cd008f24"
    ],
    "credits/snow/ATTRIBUTION.txt": [
        292,
        "cf280b50c86fc5b1518643f4bb8be5befba91b29bdfeb5311ad3f98b65fddc9d"
    ]
}
PROOF_PINS = {
    "packed-textures-audit.json": [
        61385,
        "fea804a7f728f4870a6af4b56e0ea7f4d4baf194a6baac80ab6049d2a2962049"
    ],
    "packed-reopen-audit.json": [
        10977,
        "79c93c459c2a1428ac44a252fdee7744320a8381dec0f8364ea66e5397e9d3ed"
    ],
    "packed-reopen-expectations.json": [
        70147,
        "ba0d31b175ccbb5bffc3e65db3217b060727bd1a889df78fb69838d43821329a"
    ],
    "packed-transport-manifest.json": [
        627,
        "808536aa936a76f620444af37bb5f5e333712f7c928c9d25a7508b0094bf8c13"
    ],
    "credits/LICENSES.md": [
        1559,
        "21ffbcb7404ceeb59a8038da34ad28df24ee3f390d33f9c16bac04952cbab71c"
    ],
    "credits/rain/ATTRIBUTION.txt": [
        292,
        "41d2a5693de42c5ee60dafaea599dfadd5a34ede8554a4d8a7c98af0cd008f24"
    ],
    "credits/snow/ATTRIBUTION.txt": [
        292,
        "cf280b50c86fc5b1518643f4bb8be5befba91b29bdfeb5311ad3f98b65fddc9d"
    ]
}
PARTS = [
    {
        "artifact_id": 11982293383,
        "name": "avatar-snow-packed-native-part-0",
        "zip_bytes": 67069077,
        "zip_sha256": "8587fdf9631fa47b68b92a87468831fcc5dd703920333cd67f884b4eb2506a36",
        "file": "snow-packed-native.part-000.bin",
        "bytes": 67108864,
        "sha256": "1838e979f3a156715d8925bae95daa5e5a657f366c2a190d769dcbe005cb04d8"
    },
    {
        "artifact_id": 11981908316,
        "name": "avatar-snow-packed-native-part-1",
        "zip_bytes": 37894634,
        "zip_sha256": "302f095d00a4988256926df483ba0e55301aa0831bea035b94612b8d91fc5ba6",
        "file": "snow-packed-native.part-001.bin",
        "bytes": 37976504,
        "sha256": "0b481147d6df0ad39ec62702699210cd8f8c1cf087423928e5378c2ff38bcfba"
    }
]
PROOF = {"artifact_id": 11981269040, "name": "avatar-snow-packed-native-proof",
    "zip_bytes": 34695, "zip_sha256": "75070d63706b6329f2c34b3a4314d48e39a61dbe8ad4de04a047bc7996fb5460"}
SAFE = frozenset(("posix_required", "missing_token", "invalid_arguments", "unsafe_restore_dir",
    "unsafe_report_path", "trusted_restore_helper_mismatch", "oversized_metadata",
    "frozen_artifact_mismatch", "archive_exceeds_size", "archive_checksum_mismatch",
    "archive_entry_limit_exceeded", "archive_count_bytes_mismatch", "unsafe_zip_entry",
    "duplicate_archive_entry", "file_directory_collision", "missing_or_duplicate_target",
    "unsafe_destination", "entry_exceeds_size", "entry_size_crc_mismatch", "written_entry_mismatch",
    "reference_checksum_mismatch", "restored_inventory_mismatch", "original_not_readonly",
    "manifest_budget_exceeded", "unsafe_redirect", "redirect_limit", "nonempty_directory",
    "unexpected_part_archive_file", "packed_producer_contract", "packed_worker_contract",
    "packed_expectations_contract", "packed_transport_contract", "joined_blend_mismatch"))
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
def hash_crc_bounded(path, limit=MAX_ENTRY):
    digest, crc, size = hashlib.sha256(), 0, 0
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(CHUNK), b""):
            size += len(data)
            if size > limit:
                raise ValueError("entry_exceeds_size")
            digest.update(data)
            crc = binascii.crc32(data, crc)
    return size, digest.hexdigest(), format(crc & 0xffffffff, "08x")

def checked_archive_name(info, limit):
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
    elif not 0 <= info.file_size <= limit:
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

def require(condition, code):
    if not condition:
        raise ValueError(code)

def restore_component(helper, opener, token, root, destination, component, mapping, pins,
                      extract, member_limit, total_limit, exact_inventory):
    artifact = component["artifact_id"]
    with opener.open(helper.api("/actions/artifacts/"+str(artifact), token), timeout=90) as response:
        raw = response.read(CHUNK+1)
    require(len(raw) <= CHUNK, "oversized_metadata")
    meta = json.loads(raw)
    require(meta.get("id") == artifact and meta.get("name") == component["name"]
        and meta.get("expired") is False and meta.get("size_in_bytes") == component["zip_bytes"]
        and meta.get("digest") == "sha256:"+component["zip_sha256"]
        and meta.get("workflow_run", {}).get("id") == RUN
        and meta.get("workflow_run", {}).get("head_sha") == COMMIT, "frozen_artifact_mismatch")
    archive, downloaded, digest = root/("artifact-"+str(artifact)+".zip"), 0, hashlib.sha256()
    with opener.open(helper.api("/actions/artifacts/"+str(artifact)+"/zip", token), timeout=90) as response:
        with archive.open("xb") as output:
            while True:
                data = response.read(CHUNK)
                if not data:
                    break
                downloaded += len(data)
                require(downloaded <= component["zip_bytes"], "archive_exceeds_size")
                digest.update(data)
                output.write(data)
            output.flush()
            os.fsync(output.fileno())
    require(downloaded == component["zip_bytes"] and digest.hexdigest() == component["zip_sha256"],
            "archive_checksum_mismatch")
    archive.chmod(0o444)
    records, selected = [], {}
    with zipfile.ZipFile(archive) as source:
        infos = source.infolist()
        require(1 <= len(infos) <= MAX_ENTRIES, "archive_entry_limit_exceeded")
        paths = [checked_archive_name(info, member_limit) for info in infos]
        portable = [unicodedata.normalize("NFC", name).casefold() for name in paths]
        require(len(paths) == len(set(paths)) and len(portable) == len(set(portable)),
                "duplicate_archive_entry")
        files = [info for info in infos if not info.is_dir()]
        require(sum(info.file_size for info in files) <= total_limit, "archive_count_bytes_mismatch")
        names = {info.filename for info in files}
        for info in infos:
            no_zip64(info)
            require(info.is_dir() or info.file_size/max(1, info.compress_size) <= 4096,
                    "unsafe_zip_entry")
            require(not any(p.as_posix() in names for p in PurePosixPath(info.filename).parents),
                    "file_directory_collision")
        for suffix, canonical in mapping.items():
            matches = [info for info in files if info.filename == suffix
                       or info.filename.endswith("/"+suffix)]
            require(len(matches) == 1, "missing_or_duplicate_target")
            selected[matches[0].filename] = canonical
        require(len(selected) == len(mapping) and len(set(selected.values())) == len(mapping),
                "missing_or_duplicate_target")
        if exact_inventory:
            require(len(files) == len(mapping), "unexpected_part_archive_file")
        for info in files:
            canonical = selected.get(info.filename)
            target = None
            if canonical in extract:
                parent = helper.mkdir_checked(destination, PurePosixPath(canonical).parent.as_posix())
                target = parent/PurePosixPath(canonical).name
                require(not target.exists() and not target.is_symlink()
                    and target.resolve().is_relative_to(destination), "unsafe_destination")
            checksum, crc, size = hashlib.sha256(), 0, 0
            output = target.open("xb") if target else None
            try:
                with source.open(info) as inp:
                    while True:
                        data = inp.read(CHUNK)
                        if not data:
                            break
                        size += len(data)
                        require(size <= info.file_size and size <= member_limit, "entry_exceeds_size")
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
            require(size == info.file_size and crc == info.CRC, "entry_size_crc_mismatch")
            digest = checksum.hexdigest()
            if canonical is not None:
                require([size, digest] == list(pins[canonical]), "reference_checksum_mismatch")
            if target:
                require(hash_crc_bounded(target, member_limit) == (size, digest, format(crc, "08x")),
                        "written_entry_mismatch")
            records.append({"archive_path": info.filename, "canonical_path": canonical,
                "bytes": size, "sha256": digest, "crc32": format(crc, "08x"),
                "restored": target is not None})
    return {"artifact_id": artifact, "artifact_name": component["name"], "run_id": RUN,
        "commit": COMMIT, "archive_bytes": component["zip_bytes"],
        "archive_sha256": component["zip_sha256"], "all_archive_crcs_verified": True,
        "all_restored_hashes_rechecked": True, "entries": records}

def read_json(path):
    require(path.stat().st_size <= CHUNK, "oversized_metadata")
    return json.loads(path.read_bytes())

def proof_contract(checkpoint):
    producer = read_json(checkpoint/"packed-textures-audit.json")
    worker = read_json(checkpoint/"packed-reopen-audit.json")
    expected = read_json(checkpoint/"packed-reopen-expectations.json")
    transport = read_json(checkpoint/"packed-transport-manifest.json")
    require(all(producer.get(key) is True for key in (
        "candidate_complete", "packed_used_textures_verified", "reopen_verified",
        "final_snapshot_preserved", "retention_metadata_restored",
        "all_68_original_hashes_unchanged", "input_files_unchanged"))
        and producer.get("derivative") == {"file": BLEND_FILE, "bytes": BLEND_BYTES, "sha256": BLEND_SHA},
        "packed_producer_contract")
    require(all(worker.get(key) is True for key in (
        "passed", "packed_used_textures_only", "saved_binding_verified",
        "snapshot_stable_before_and_after_decode", "reference_values_passed_before_and_after_decode",
        "candidate_blend_hash_unchanged", "expected_and_source_hashes_unchanged"))
        and worker.get("failure") is None and worker.get("blend_bytes") == BLEND_BYTES
        and worker.get("blend_sha256_before") == worker.get("blend_sha256_after") == BLEND_SHA
        and worker.get("expected_sha256") == PROOF_PINS["packed-reopen-expectations.json"][1]
        and worker.get("observed_snapshot_sha256_before_decode") == SNAPSHOT_SHA
        and worker.get("observed_snapshot_sha256_after_decode") == SNAPSHOT_SHA,
        "packed_worker_contract")
    packed = worker.get("packed_verification", {})
    require(all(packed.get(k) == v for k, v in {
        "all_passed": True, "external_paths_all_missing": True, "images": 22, "packed_entries": 30,
        "packed_bytes": 97102085, "decoded_file_buffers": 18, "decoded_tile_buffers": 12}.items())
        and worker.get("retention_policy_readback", {}).get("passed") is True,
        "packed_worker_contract")
    for phase in ("native_driver_after_open", "native_driver_after_reference"):
        driver = worker.get(phase, {})
        require(driver.get("record_count") == driver.get("native_unmuted") == 1291
            and driver.get("non_native_unmuted") == 0
            and driver.get("native_driver_status", {}).get("count") == 1291
            and driver.get("native_driver_status", {}).get("active_invalid") == 0
            and driver.get("native_driver_status", {}).get("muted") == 0, "packed_worker_contract")
    canonical = (json.dumps(expected.get("snapshot"), sort_keys=True,
        ensure_ascii=False, allow_nan=False)+"\n").encode("utf-8")
    policy = expected.get("retention_policy", {})
    require(expected.get("schema_version") == 3
        and expected.get("blend_sha256") == BLEND_SHA and expected.get("blend_bytes") == BLEND_BYTES
        and expected.get("snapshot_sha256") == hashlib.sha256(canonical).hexdigest() == SNAPSHOT_SHA
        and expected.get("snapshot") == producer.get("reference_snapshot")
        and expected.get("wrapper_blob") == "05f0667f0096416d0368ff4399107db3b73c95f0"
        and expected.get("worker_blob") == "e3869adf226c957e8f2467fc23312cf09dd2eaa9"
        and policy == producer.get("retention_policy")
        and policy.get("object_name") == "GEO-snow-eye_anim"
        and policy.get("driver_identity_sha256") == "d9638f60715ccbe8d885fdf6709cf1e74b229201d0a3c5ee85363c1f13c80040"
        and policy.get("source_users") == 0 and policy.get("source_use_fake_user") is False
        and policy.get("saved_users") == 1 and policy.get("saved_use_fake_user") is True
        and len(policy.get("saved_object_fake_users", {})) == 59, "packed_expectations_contract")
    expected_parts = [{"bytes": part["bytes"], "file": part["file"], "index": index,
        "sha256": part["sha256"]} for index, part in enumerate(PARTS)]
    require(transport == {"schema_version": 1, "bytes": BLEND_BYTES, "candidate_file": BLEND_FILE,
        "sha256": BLEND_SHA, "part_size_cap": MAX_ENTRY, "parts": expected_parts,
        "same_job_join_sha256_verified": True, "part_files_are_binary_chunks_not_standalone_blend": True},
        "packed_transport_contract")

def main():
    root, report, stage = None, None, "setup"
    try:
        require(os.name == "posix", "posix_required")
        helper = load_helper()
        parser = helper.SafeParser(add_help=False)
        parser.add_argument("--out", required=True)
        parser.add_argument("--report", required=True)
        args = parser.parse_args()
        candidate, report_candidate = Path(args.out), Path(args.report)
        require(candidate.is_absolute() and not candidate.exists() and not candidate.is_symlink(),
                "unsafe_restore_dir")
        require(report_candidate.is_absolute() and not report_candidate.exists()
                and not report_candidate.is_symlink(), "unsafe_report_path")
        root, report = candidate.resolve(), report_candidate.resolve()
        require(not report.is_relative_to(root), "unsafe_report_path")
        token = os.environ.get("GH_TOKEN", "")
        require(bool(token), "missing_token")
        root.mkdir(parents=True, exist_ok=False, mode=0o700)
        checkpoint, part_root = root/"checkpoint", root/"parts"
        checkpoint.mkdir(mode=0o700)
        part_root.mkdir(mode=0o700)
        report.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        opener = urllib.request.build_opener(helper.NoAuthRedirect())
        components = []
        for index, part in enumerate(PARTS):
            stage = "restore_part_"+str(index)
            mapping = {"parts/"+part["file"]: part["file"]}
            mapping.update({"snow/"+name: name for name in CREDITS})
            pins = {part["file"]: [part["bytes"], part["sha256"]], **CREDITS}
            components.append(restore_component(helper, opener, token, root, part_root, part,
                mapping, pins, {part["file"]}, MAX_ENTRY, 72*1024*1024, True))
        stage = "restore_proof"
        components.append(restore_component(helper, opener, token, root, checkpoint, PROOF,
            {"snow/"+name: name for name in PROOF_PINS}, PROOF_PINS, set(PROOF_PINS),
            CHUNK, 4*CHUNK, False))
        del token
        stage = "proof_contract"
        proof_contract(checkpoint)
        stage = "join_verified_parts"
        joined, count, digest = checkpoint/BLEND_FILE, 0, hashlib.sha256()
        with joined.open("xb") as output:
            for part in PARTS:
                path = part_root/part["file"]
                require(hash_crc_bounded(path)[:2] == (part["bytes"], part["sha256"]),
                        "reference_checksum_mismatch")
                with path.open("rb") as inp:
                    for data in iter(lambda: inp.read(CHUNK), b""):
                        count += len(data)
                        require(count <= MAX_BLEND and count <= BLEND_BYTES, "entry_exceeds_size")
                        digest.update(data)
                        output.write(data)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), 0o444)
        require(count == BLEND_BYTES and digest.hexdigest() == BLEND_SHA
            and hash_crc_bounded(joined, MAX_BLEND)[:2] == (BLEND_BYTES, BLEND_SHA),
            "joined_blend_mismatch")
        stage = "verify_readonly_inventory"
        pinned = {BLEND_FILE: [BLEND_BYTES, BLEND_SHA], **PROOF_PINS}
        actual, file_rows = set(), []
        for path in checkpoint.rglob("*"):
            require(not path.is_symlink(), "unsafe_destination")
            if path.is_file():
                name = path.relative_to(checkpoint).as_posix()
                actual.add(name)
                require(stat.S_ISREG(path.stat().st_mode) and not path.stat().st_mode & 0o333,
                        "original_not_readonly")
                require(name in pinned, "restored_inventory_mismatch")
                size, digest, crc = hash_crc_bounded(path, MAX_BLEND if name == BLEND_FILE else CHUNK)
                require([size, digest] == pinned[name], "written_entry_mismatch")
                file_rows.append({"file": name, "bytes": size, "sha256": digest})
        require(actual == set(pinned), "restored_inventory_mismatch")
        manifest = {"schema_version": 1, "ok": True, "purpose": "frozen_packed_actor_closure_input",
            "joined_verified": True, "readonly": True, "archive_files_executed": False,
            "files": sorted(file_rows, key=lambda row: row["file"]), "components": components,
            "original_source_preservation_is_inherited": True,
            "full_scene_portable": False, "whole_file_portable": False,
            "production_glb_approved": False, "model_art_or_game_approved": False}
        payload = encoded(manifest)
        require(len(payload) <= CHUNK, "manifest_budget_exceeded")
        manifest_file = root/"restore-manifest.json"
        manifest_file.write_bytes(payload)
        manifest_file.chmod(0o444)
        for directory in sorted((p for p in root.rglob("*") if p.is_dir()),
                                key=lambda p: len(p.parts), reverse=True):
            directory.chmod(0o555)
        root.chmod(0o555)
        with report.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), 0o444)
        print("SNOW_PACKED_NATIVE_RESTORED "+json.dumps({"ok": True,
            "artifacts": [component["artifact_id"] for component in components],
            "joined_bytes": BLEND_BYTES, "joined_sha256": BLEND_SHA,
            "all_archive_crcs_verified": True, "selected_readonly_files": len(file_rows),
            "executed": False, "portability_approved": False}), flush=True)
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
        print("SNOW_PACKED_NATIVE_RESTORE_FAILED "+json.dumps(failure), flush=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
