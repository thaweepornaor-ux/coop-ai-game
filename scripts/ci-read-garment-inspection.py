"""Read frozen garment JSON only; no bpy, blend loading, rendering or mesh edits."""
import argparse, binascii, hashlib, json, math, os, re, stat, sys, zipfile
from pathlib import Path, PurePosixPath
import urllib.error, urllib.parse, urllib.request
REPO = "thaweepornaor-ux/coop-ai-game"
ARTIFACT, RUN = 11694845616, 38119494514
COMMIT = "9b01ca16f4eb991893e2cbc0a5060152ea70b1ff"
ZIP_BYTES, ZIP_SHA = 5230501, "e97dc38c711429d231c6fff514fb905f84b40006c953dd8b3023ed8fcae62ce9"
CHUNK, ENTRY_MAX, TOTAL_MAX, JSON_MAX = 1048576, 16777216, 67108864, 8388608
OUTPUT_MAX = 300000
SAFE_CODES = frozenset(("invalid_arguments", "missing_token", "unsafe_output", "unsafe_redirect",
    "redirect_limit", "metadata_size", "frozen_artifact_mismatch", "download_header",
    "download_size", "download_checksum", "unsafe_zip_path", "zip_limits", "duplicate_zip_path",
    "zip_collision", "missing_unique_report", "entry_crc_size", "invalid_json", "report_schema",
    "source_hash_mismatch", "output_budget"))
class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid_arguments")

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

def require(ok):
    if not ok:
        raise ValueError("report_schema")
def integer(value):
    require(type(value) is int and 0 <= value <= 10000000)
    return value
def flag(value):
    require(type(value) is bool)
    return value
def number(value):
    require(type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1e12)
    return value
def vector(value):
    require(isinstance(value, list) and len(value) == 3)
    return [number(x) for x in value]
def bounds(value):
    return {k: vector(value[k]) for k in ("minimum", "maximum")}
def digest(value):
    require(isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value) is not None)
    return value
def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("invalid_json")
        result[key] = value
    return result
def forbidden_constant(value):
    raise ValueError("invalid_json")
def summarize(model, topology, proof):
    require(topology["model"] == model and proof["model"] == model)
    source_hash = digest(topology["source_sha256"])
    if source_hash != digest(proof["source_sha256"]):
        raise ValueError("source_hash_mismatch")
    before, after = topology["geometry_signature_before"], topology["geometry_signature_after"]
    components = topology["boundary_components"]
    require(isinstance(components, list) and len(components) <= 256)
    boundary = []
    for c in components:
        require(c["kind"] in ("closed_loop", "open_chain", "branched_component"))
        require(len(c["vertices"]) <= 10000 and len(c["edges"]) <= 10000)
        edges = []
        for edge in c["edges"]:
            require(isinstance(edge, list) and len(edge) == 2)
            edges.append([integer(x) for x in edge])
        boundary.append({"component_id": integer(c["component_id"]), "kind": c["kind"],
            "ordered": flag(c["ordered"]), "closed": flag(c["closed"]),
            "vertex_indices": [integer(x) for x in c["vertex_indices"]],
            "edge_indices": [integer(x) for x in c["edge_indices"]], "edges": edges,
            "vertices": [{"index": integer(v["index"]), "degree": integer(v["degree"]),
                         "local": vector(v["local"]), "world_at_inspection": vector(v["world_at_inspection"])}
                        for v in c["vertices"]],
            "local_bounds": bounds(c["local_bounds"]),
            "local_edge_length": number(c["local_edge_length"]), "anatomical_label": None})
    policy = proof["driver_and_animation_policy"]
    evaluated = proof["driver_evaluation_status_after_render"]
    require(isinstance(policy, list) and len(policy) <= 10000
            and isinstance(evaluated, list) and len(evaluated) <= 100000)
    pc = {"driver_count": 0, "native_retained": 0, "complex_muted": 0,
          "complex_active": 0, "originally_muted": 0}
    for block in policy:
        for driver in block["drivers"]:
            native, muted = flag(driver["native_without_python"]), flag(driver["muted_after_policy"])
            pc["driver_count"] += 1
            pc["native_retained"] += int(native and not muted)
            pc["complex_muted"] += int(not native and muted)
            pc["complex_active"] += int(not native and not muted)
            pc["originally_muted"] += int(flag(driver["originally_muted"]))
    categories = ("objects", "meshes", "armatures", "shape_keys", "materials",
                  "node_groups", "scenes", "worlds", "curves")
    id_types = set(categories) | {x + ".node_tree" for x in categories}
    driver_types = ("SCRIPTED", "AVERAGE", "SUM", "MIN", "MAX")
    counts = {"driver_count": len(evaluated), "active": 0, "muted": 0,
              "invalid": 0, "active_invalid": 0, "active_native": 0, "active_complex": 0}
    examples = []
    for ordinal, driver in enumerate(evaluated):
        muted, valid = flag(driver["muted"]), flag(driver["is_valid"])
        native = flag(driver["native_without_python"])
        counts["active"] += int(not muted)
        counts["muted"] += int(muted)
        counts["invalid"] += int(not valid)
        counts["active_invalid"] += int(not muted and not valid)
        counts["active_native"] += int(not muted and native)
        counts["active_complex"] += int(not muted and not native)
        if not muted and not valid and len(examples) < 20:
            examples.append({"record_index": ordinal,
                "id_type": driver["id_type"] if driver["id_type"] in id_types else "other",
                "driver_type": driver["type"] if driver["type"] in driver_types else "other",
                "array_index": integer(driver["index"]), "native_without_python": native,
                "muted": muted, "is_valid": valid})
    require(len(before["shape_keys"]) <= 256)
    return {"model": model, "source_sha256": source_hash,
        "raw_counts": {k: integer(topology[k]) for k in (
            "vertex_count", "edge_count", "polygon_count", "shape_key_count",
            "boundary_edge_count", "closed_loop_count")},
        "boundary_components": boundary,
        "loose_edge_indices": [integer(x) for x in topology["loose_edge_indices"]],
        "nonmanifold_edge_indices": [integer(x) for x in topology["nonmanifold_edge_indices"]],
        "evaluated_bounds_for_camera_framing": bounds(topology["evaluated_bounds_for_camera_framing"]),
        "geometry": {"topology_sha256": digest(before["topology_sha256"]),
            "vertex_coordinate_sha256": digest(before["vertex_coordinate_sha256"]),
            "shape_keys": [{"key_index": i, "point_count": integer(k["point_count"]),
                            "coordinate_sha256": digest(k["coordinate_sha256"])}
                           for i, k in enumerate(before["shape_keys"])],
            "before_after_signatures_match": before == after,
            "raw_coordinates_unchanged": flag(topology["raw_mesh_and_shape_key_coordinates_unchanged"])},
        "driver_policy_counts": pc, "driver_evaluation_counts": counts,
        "active_invalid_examples": examples,
        "active_invalid_examples_truncated": counts["active_invalid"] > len(examples),
        "native_driver_policy_experiment": flag(proof["native_driver_policy_experiment"]),
        "driver_policy_visually_accepted": flag(proof["driver_policy_visually_accepted"]),
        "garment_geometry_unchanged": flag(proof["garment_geometry_unchanged"]),
        "garment_edits_performed": flag(proof["garment_edits_performed"]),
        "source_hash_rechecked": flag(proof["source_hash_rechecked"]),
        "automatic_python_execution": flag(proof["policy"]["automatic_python_execution"]),
        "embedded_text_executed": flag(proof["policy"]["embedded_text_executed"])}
def main():
    root, stage = None, "setup"
    try:
        parser = SafeParser(add_help=False)
        parser.add_argument("--out", required=True)
        args = parser.parse_args()
        token = os.environ.get("GH_TOKEN", "")
        if not token:
            raise ValueError("missing_token")
        candidate = Path(args.out)
        if not candidate.is_absolute() or candidate.exists() or candidate.is_symlink():
            raise ValueError("unsafe_output")
        root = candidate.resolve()
        root.mkdir(parents=True, exist_ok=False)
        opener = urllib.request.build_opener(NoAuthRedirect())
        stage = "metadata"
        with opener.open(api("/actions/artifacts/" + str(ARTIFACT), token), timeout=20) as response:
            raw = response.read(CHUNK + 1)
        if len(raw) > CHUNK:
            raise ValueError("metadata_size")
        meta = json.loads(raw, object_pairs_hook=unique_object, parse_constant=forbidden_constant)
        if (meta.get("id") != ARTIFACT or meta.get("name") != "avatar-garment-topology-proof"
            or meta.get("expired") is not False or meta.get("size_in_bytes") != ZIP_BYTES
            or meta.get("digest") != "sha256:" + ZIP_SHA
            or meta.get("workflow_run", {}).get("id") != RUN
            or meta.get("workflow_run", {}).get("head_sha") != COMMIT):
            raise ValueError("frozen_artifact_mismatch")
        stage = "download"
        archive = root / "frozen-inspection.zip"
        checksum, count = hashlib.sha256(), 0
        with opener.open(api("/actions/artifacts/" + str(ARTIFACT) + "/zip", token), timeout=20) as response:
            length = response.headers.get("Content-Length")
            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if (response.status != 200 or (length is not None and length != str(ZIP_BYTES))
                or content_type not in ("application/zip", "application/octet-stream", "application/x-zip-compressed")):
                raise ValueError("download_header")
            with archive.open("xb") as output:
                while True:
                    data = response.read(CHUNK)
                    if not data:
                        break
                    count += len(data)
                    if count > ZIP_BYTES:
                        raise ValueError("download_size")
                    checksum.update(data)
                    output.write(data)
        del token
        if count != ZIP_BYTES or checksum.hexdigest() != ZIP_SHA:
            raise ValueError("download_checksum")
        archive.chmod(0o444)
        stage = "zip_inventory"
        wanted = {m + "/" + f: None for m in ("rain", "snow")
                  for f in ("garment-topology.json", "render-proof.json")}
        loaded, entry_hashes = {}, {}
        with zipfile.ZipFile(archive) as source:
            infos = source.infolist()
            if len(infos) > 256 or sum(i.file_size for i in infos) > TOTAL_MAX:
                raise ValueError("zip_limits")
            names, files = set(), set()
            for info in infos:
                name = info.filename.rstrip("/") if info.is_dir() else info.filename
                path = PurePosixPath(name)
                kind = stat.S_IFMT(info.external_attr >> 16)
                if (not name or info.orig_filename != info.filename or len(name) > 1024
                    or name.startswith("/") or "\\" in name or ":" in name
                    or path.as_posix() != name or ".." in path.parts
                    or any(ord(c) < 32 or ord(c) == 127 for c in name)
                    or info.flag_bits & 1 or kind not in (0, stat.S_IFDIR, stat.S_IFREG)
                    or (info.is_dir() and (info.file_size != 0 or kind == stat.S_IFREG))
                    or (not info.is_dir() and kind == stat.S_IFDIR)
                    or not 0 <= info.file_size <= ENTRY_MAX
                    or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ValueError("unsafe_zip_path")
                if name in names:
                    raise ValueError("duplicate_zip_path")
                names.add(name)
                if not info.is_dir():
                    files.add(name)
                    for suffix in wanted:
                        if name == suffix or name.endswith("/" + suffix):
                            if wanted[suffix] is not None:
                                raise ValueError("missing_unique_report")
                            wanted[suffix] = info
            if any(p.as_posix() in files for name in names for p in PurePosixPath(name).parents):
                raise ValueError("zip_collision")
            if any(info is None for info in wanted.values()):
                raise ValueError("missing_unique_report")
            selected = {info.filename: suffix for suffix, info in wanted.items()}
            stage = "crc_and_json"
            for info in infos:
                suffix = selected.get(info.filename)
                if suffix and info.file_size > JSON_MAX:
                    raise ValueError("zip_limits")
                size, crc, sha, pieces = 0, 0, hashlib.sha256(), []
                with source.open(info) as stream:
                    while True:
                        data = stream.read(CHUNK)
                        if not data:
                            break
                        size += len(data)
                        if size > info.file_size:
                            raise ValueError("entry_crc_size")
                        crc = binascii.crc32(data, crc)
                        if suffix:
                            sha.update(data)
                            pieces.append(data)
                if size != info.file_size or crc & 0xffffffff != info.CRC:
                    raise ValueError("entry_crc_size")
                if suffix:
                    loaded[suffix] = json.loads(b"".join(pieces),
                        object_pairs_hook=unique_object, parse_constant=forbidden_constant)
                    entry_hashes[suffix] = {"bytes": size, "sha256": sha.hexdigest(),
                                            "crc32": format(crc & 0xffffffff, "08x")}
        stage = "summarize"
        report = {"schema_version": 1, "ok": True, "purpose": "Read frozen inspection JSON only",
            "provenance": {"repository": REPO, "artifact_id": ARTIFACT, "run_id": RUN,
                           "head_sha": COMMIT, "zip_bytes": ZIP_BYTES, "zip_sha256": ZIP_SHA},
            "inventory": {"entry_count": len(infos), "file_count": len(files),
                          "uncompressed_bytes": sum(i.file_size for i in infos),
                          "all_entries_crc_verified": True, "unique_suffix_selection": True,
                          "selected_json": entry_hashes},
            "models": [summarize(m, loaded[m + "/garment-topology.json"],
                                loaded[m + "/render-proof.json"]) for m in ("rain", "snow")],
            "bpy_imported": False, "blend_loaded": False, "renders_performed": False,
            "geometry_edited": False, "production_glb_approved": False,
            "raw_boundaries_are_anatomical_edit_selections": False}
        payload = json.dumps(report, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        marker = b"AVATAR_GARMENT_INSPECTION_READ "
        if len(marker) + len(payload) + 1 > OUTPUT_MAX:
            raise ValueError("output_budget")
        (root / "garment-inspection-read.json").write_bytes(payload + b"\n")
        print(marker.decode() + payload.decode(), flush=True)
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
                (root / "probe-failure.json").write_text(json.dumps(failure) + "\n", encoding="utf-8")
            except OSError:
                pass
        # Never print raw errors, original JSON, expressions, names, paths, targets, headers or URLs.
        print("AVATAR_GARMENT_INSPECTION_READ_FAILED " + json.dumps(failure), flush=True)
        return 1
if __name__ == "__main__":
    sys.exit(main())
