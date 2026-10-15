#!/usr/bin/env python3
"""One offline CUBICSPLINE candidate from frozen authored GLB keys only.

No bpy or native NPZ evaluation. The independent reader evaluates the resulting
file against native references in a separate CI process.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import numpy as np

MAX_GLB = 32*1024*1024
MAX_JSON = 1024*1024
CLIPS = ("idle", "wave", "celebrate")
PINNED = {
    "source.glb": (15845580, "4a91efd3b9e69e0549180b0b1c348ef35effc0b13ab561909ee5b8ebb1215f90"),
    "native_reference.npz": (15870464, "d21f2d557cf3261604e0dee37399fe65323516092ab8ece4ef1babe3d2dbe2be"),
    "native_reference.json": (79868, "ca8aa6a0785ad894619cedd673fc35cdd12298fa2cea579ee6db7d2ac5226df1"),
    "source-writer-audit.json": (31022, "1878e544b4e5c263a0cdfbf9f9c786effe3dfe5bb1766fd1b401a72073f1347e"),
    "source-reader-audit.json": (121100, "946bf478b943609170e458983f215e90dc250b4cd2769bb3468076b19f68d150"),
}
CREDITS = ("LICENSES.md", "rain/ATTRIBUTION.txt", "snow/ATTRIBUTION.txt")
WIDTH = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}
OUTPUT_NAME = "snow-armature-cubic-prototype.glb"


def require(ok, code):
    if not ok:
        raise ValueError("snow_cubic_" + code)


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def finite(data):
    require(np.isfinite(data).all(), "nonfinite")
    return data


def frozen_files(root):
    result = {}
    for name, (size, checksum) in PINNED.items():
        path = root/name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == size,
                "input_file_size_or_type")
        require(digest(path) == checksum, "input_checksum")
        require(path.stat().st_mode & 0o222 == 0, "input_not_readonly")
        result[name] = {"bytes": size, "sha256": checksum}
    for name in CREDITS:
        path = root/"credits"/name
        require(path.is_file() and not path.is_symlink()
                and 0 < path.stat().st_size <= 65536
                and path.stat().st_mode & 0o222 == 0, "credits_missing_or_unbounded")
        result["credits/"+name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    return result


def read_json(path):
    require(path.stat().st_size <= MAX_JSON, "json_budget")
    return json.loads(path.read_text("utf-8"))


def read_glb(path):
    raw = path.read_bytes()
    require(20 <= len(raw) <= MAX_GLB, "input_glb_budget")
    require(struct.unpack_from("<III", raw, 0) == (0x46546c67, 2, len(raw)), "glb_header")
    cursor, chunks = 12, []
    while cursor < len(raw):
        require(cursor+8 <= len(raw), "glb_chunk_header")
        length, kind = struct.unpack_from("<II", raw, cursor)
        cursor += 8
        require(length % 4 == 0 and cursor+length <= len(raw), "glb_chunk_bounds")
        chunks.append((kind, raw[cursor:cursor+length]))
        cursor += length
    require(len(chunks) == 2 and chunks[0][0] == 0x4e4f534a and chunks[1][0] == 0x004e4942,
            "glb_two_chunks")
    doc = json.loads(chunks[0][1].decode("utf-8"))
    buffers = doc.get("buffers", [])
    require(len(buffers) == 1 and "uri" not in buffers[0], "glb_internal_buffer")
    length = buffers[0]["byteLength"]
    require(type(length) is int and 0 < length <= len(chunks[1][1])
            and len(chunks[1][1])-length <= 3, "glb_buffer_length")
    require(doc.get("asset", {}).get("extras", {}).get("coop_corrective_contract") == "coop-armature-correctives-v1",
            "glb_contract")
    return doc, chunks[1][1][:length]


def values(doc, binary, index, expected):
    require(type(index) is int and 0 <= index < len(doc["accessors"]), "accessor_index")
    accessor = doc["accessors"][index]
    require(accessor.get("componentType") == 5126 and accessor.get("type") == expected
            and not accessor.get("normalized", False) and "sparse" not in accessor,
            "animation_accessor_type")
    vi = accessor["bufferView"]
    require(type(vi) is int and 0 <= vi < len(doc["bufferViews"]), "view_index")
    view = doc["bufferViews"][vi]
    require(view.get("buffer") == 0 and "byteStride" not in view, "animation_view_layout")
    count, width = accessor["count"], WIDTH[expected]
    require(type(count) is int and 0 < count <= 100000, "animation_count")
    relative = accessor.get("byteOffset", 0)
    start, size = view.get("byteOffset", 0)+relative, count*width*4
    require(type(relative) is int and relative >= 0 and start % 4 == 0
            and relative+size <= view["byteLength"] and start+size <= len(binary),
            "animation_accessor_bounds")
    return finite(np.frombuffer(binary, dtype="<f4", count=count*width,
                                offset=start).reshape(count, width).copy())


def plan_streams(doc, binary):
    animations = doc.get("animations", [])
    require(len(animations) == 3 and {a.get("name") for a in animations} == set(CLIPS),
            "three_semantic_clips")
    nodes, meshes = doc["nodes"], doc["meshes"]
    plans = []
    for ai, animation in enumerate(animations):
        samplers = animation.get("samplers", [])
        require(0 < len(samplers) < 2000, "sampler_budget")
        usages = {}
        for channel in animation.get("channels", []):
            si = channel["sampler"]
            require(type(si) is int and 0 <= si < len(samplers), "sampler_index")
            target, path = channel["target"], channel["target"]["path"]
            node = target["node"]
            require(type(node) is int and 0 <= node < len(nodes)
                    and path in ("translation", "rotation", "scale", "weights"), "channel_target")
            width = 4 if path == "rotation" else 3
            expected = "VEC4" if path == "rotation" else "VEC3"
            if path == "weights":
                require("mesh" in nodes[node], "weights_node_mesh")
                primitives = meshes[nodes[node]["mesh"]]["primitives"]
                widths = {len(p.get("targets", [])) for p in primitives}
                require(widths == {147}, "morph_target_count")
                width, expected = 147, "SCALAR"
            usage = (path, width, expected)
            require(si not in usages or usages[si] == usage, "ambiguous_sampler_path")
            usages[si] = usage
        require(set(usages) == set(range(len(samplers))), "unused_sampler")
        for si, sampler in enumerate(samplers):
            require(sampler.get("interpolation", "LINEAR") == "LINEAR", "source_not_linear")
            path, width, expected = usages[si]
            times = values(doc, binary, sampler["input"], "SCALAR")[:, 0].astype(np.float64)
            require(len(times) == 49 and np.all(np.diff(times) > 0)
                    and np.allclose(times, np.arange(49)/24, atol=1e-7, rtol=0), "times49")
            raw_values = values(doc, binary, sampler["output"], expected)
            require(raw_values.size == 49*width, "source_output_cardinality")
            key = raw_values.reshape(49, width)
            if path == "rotation":
                norms = np.linalg.norm(key.astype(np.float64), axis=1)
                require(np.all(np.abs(norms-1) < 1e-4)
                        and np.all(np.sum(key[1:].astype(np.float64)*key[:-1], axis=1) >= 0),
                        "source_quaternion_unit_hemisphere")
            plans.append({"animation": ai, "sampler": si, "path": path,
                          "type": expected, "width": width, "times": times, "keys": key,
                          "bytes": 49*3*width*4})
    return plans


def rewrite(root, out, audit):
    source_writer = read_json(root/"source-writer-audit.json")
    source_reader = read_json(root/"source-reader-audit.json")["summary"]
    require(source_writer["writer_completed"] is True
            and source_writer["readonly_cleanup_passed"] is True
            and source_writer["input_preservation_passed"] is True
            and source_writer["native_reference_hash_recheck"] is True,
            "source_writer_checkpoint")
    require(source_reader["authored_passed"] is True
            and source_reader["fractional_passed"] is False
            and source_reader["passed"] is False
            and source_reader["writer_checkpoint_passed"] is True
            and source_reader["reference_npz_unchanged_during_readback"] is True,
            "source_expected_fractional_failure")
    audit["source_checkpoint_passed"] = True
    audit["native_provenance"] = {"reference_capture_run": 38688634504,
        "reference_authored_rows": 147, "reference_fractional_rows": 12,
        "native_playback_this_job": False, "blender_loaded_this_job": False,
        "preservation_inherited_from_run": 38691954362}
    doc, original_binary = read_glb(root/"source.glb")
    plans = plan_streams(doc, original_binary)
    new_doc = copy.deepcopy(doc)
    cursor = len(original_binary)
    for plan in plans:
        cursor = (cursor+3)//4*4
        view_index, accessor_index = len(new_doc["bufferViews"]), len(new_doc["accessors"])
        new_doc["bufferViews"].append({"buffer": 0, "byteOffset": cursor, "byteLength": plan["bytes"]})
        new_doc["accessors"].append({"bufferView": view_index, "byteOffset": 0,
            "componentType": 5126, "count": 49*3*(147 if plan["path"] == "weights" else 1),
            "type": plan["type"]})
        sampler = new_doc["animations"][plan["animation"]]["samplers"][plan["sampler"]]
        sampler["output"], sampler["interpolation"] = accessor_index, "CUBICSPLINE"
        plan["offset"] = cursor
        cursor += plan["bytes"]
    new_doc["buffers"][0]["byteLength"] = cursor
    new_doc["asset"]["extras"]["cubic_candidate"] = {
        "source_glb_sha256": PINNED["source.glb"][1],
        "tangent_policy": "per-clip seconds FD: centered secant interior, one-sided endpoints; unused endpoint zero",
        "keys_unchanged": True, "fractional_validation_targets_used_for_tangents": False,
        "production_approved": False}
    json_raw = encoded(new_doc)
    json_padded = json_raw+b" "*((-len(json_raw)) % 4)
    total = 12+8+len(json_padded)+8+(cursor+3)//4*4
    audit["preflight"] = {"original_binary_bytes": len(original_binary),
        "new_binary_bytes": cursor, "new_glb_bytes": total, "glb_cap_bytes": MAX_GLB,
        "output_archive_combined_payload_may_exceed_input_archive_32MiB_cap": True,
        "performed_before_tangent_output_allocation": True}
    require(total <= MAX_GLB, "output_glb_preflight_cap")
    # Allocation follows the exact total-byte preflight. Fractional targets are never read here.
    output_binary = bytearray(cursor)
    output_binary[:len(original_binary)] = original_binary
    max_tangent, minimum_morph_tangent, counts = 0.0, 0.0, {}
    for plan in plans:
        t, k = plan["times"], plan["keys"].astype(np.float64)
        derivative = np.empty_like(k)
        derivative[1:-1] = (k[2:]-k[:-2])/(t[2:]-t[:-2])[:, None]
        derivative[0] = (k[1]-k[0])/(t[1]-t[0])
        derivative[-1] = (k[-1]-k[-2])/(t[-1]-t[-2])
        finite(derivative)
        group = np.empty((49, 3, plan["width"]), dtype="<f4")
        group[:, 0, :] = derivative
        group[:, 1, :] = plan["keys"]
        group[:, 2, :] = derivative
        group[0, 0, :], group[-1, 2, :] = 0.0, 0.0
        finite(group)
        require(np.array_equal(group[:, 1, :], plan["keys"]), "stored_value_keys_changed")
        max_tangent = max(max_tangent, float(np.max(np.abs(group[:, (0, 2), :]))))
        if plan["path"] == "weights":
            minimum_morph_tangent = min(minimum_morph_tangent, float(np.min(group[:, (0, 2), :])))
        counts[plan["path"]] = counts.get(plan["path"], 0)+1
        payload = group.tobytes(order="C")
        require(len(payload) == plan["bytes"], "output_stream_byte_count")
        output_binary[plan["offset"]:plan["offset"]+len(payload)] = payload
    binary_padded = bytes(output_binary)+b"\0"*((-len(output_binary)) % 4)
    result = (struct.pack("<III", 0x46546c67, 2, total)
              + struct.pack("<II", len(json_padded), 0x4e4f534a)+json_padded
              + struct.pack("<II", len(binary_padded), 0x004e4942)+binary_padded)
    require(len(result) == total and len(result) <= MAX_GLB, "serialized_glb_size")
    target = out/OUTPUT_NAME
    target.write_bytes(result)
    audit["glb_written"] = {"file": OUTPUT_NAME, "bytes": target.stat().st_size, "sha256": digest(target)}
    audit["tangent_policy"] = {
        "source": "49 existing serialized value keys within each clip, actual serialized seconds",
        "interior": "(v[i+1]-v[i-1])/(t[i+1]-t[i-1])",
        "first": "(v[1]-v[0])/(t[1]-t[0])",
        "last": "(v[48]-v[47])/(t[48]-t[47])",
        "first_in_and_last_out": 0, "quantized_to_float32": True,
        "component_quaternion_cubic_normalized_by_reader": True,
        "quaternion_value_keys_not_sign_changed": True,
        "morph_weights_not_normalized_or_clamped": True,
        "native_fractional_validation_values_used": False,
        "per_path_sampler_counts": counts, "total_sampler_streams": len(plans),
        "maximum_absolute_stored_tangent": max_tangent,
        "minimum_stored_morph_tangent": minimum_morph_tangent}
    for name in ("native_reference.npz", "native_reference.json"):
        shutil.copyfile(root/name, out/name)
        require(digest(out/name) == PINNED[name][1], "copied_reference_checksum")
    for name in CREDITS:
        target = out/"credits"/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root/"credits"/name, target)
        require(digest(target) == digest(root/"credits"/name), "copied_credit_checksum")
    audit["native_reference"] = {"npz_bytes": PINNED["native_reference.npz"][0],
        "npz_sha256": PINNED["native_reference.npz"][1],
        "metadata_bytes": PINNED["native_reference.json"][0],
        "metadata_sha256": PINNED["native_reference.json"][1],
        "inherited_from_run": 38688634504, "recaptured": False}
    audit["native_reference_hash_recheck"] = True
    audit["writer_completed"] = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root, out = Path(args.input_root).resolve(), Path(args.out).resolve()
    require(root.is_dir() and not root.is_symlink() and root != out
            and root not in out.parents and out not in root.parents, "directories")
    require(not out.exists(), "output_already_exists")
    out.mkdir(parents=True)
    audit = {"purpose": "one offline cubic interpolation candidate; authored keys only",
        "writer_completed": False, "source_checkpoint_passed": False,
        "readonly_cleanup_passed": False, "native_reference_hash_recheck": False,
        "glb_written": None, "error": None, "renders": 0, "models_saved": 0,
        "native_playback_this_job": False, "source_geometry_edits": 0,
        "overall_art_approved": False, "production_glb_approved": False,
        "browser_animation_approved": False,
        "limits": ["BODY+SHIRT ARMATURE-stage POSITION pilot only.",
                   "Existing all-set weights and 147 targets unchanged; game adapter incompatible.",
                   "No PBR, normals, UV export, final modifiers, full avatar or browser proof.",
                   "Approximate TRS and native references are inherited, not recaptured.",
                   "Only twelve existing fractional validation times will be checked independently."]}
    before = None
    try:
        before = frozen_files(root)
        audit["input_files"] = before
        # Credits remain available even if a later GLB rewrite guard fails.
        for name in CREDITS:
            target = out/"credits"/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root/"credits"/name, target)
        rewrite(root, out, audit)
    except Exception as error:
        frames, tb = [], error.__traceback__
        while tb is not None:
            frames.append({"file": Path(tb.tb_frame.f_code.co_filename).name,
                           "line": tb.tb_lineno, "function": tb.tb_frame.f_code.co_name})
            frames, tb = frames[-6:], tb.tb_next
        code = error.args[0] if isinstance(error, ValueError) and len(error.args) == 1 else None
        audit["error"] = {"type": type(error).__name__, "code": code if isinstance(code, str)
                          and code.startswith("snow_cubic_") and len(code) < 160 else None,
                          "frames": frames}
    finally:
        try:
            audit["input_files_unchanged"] = before is not None and frozen_files(root) == before
            audit["readonly_cleanup_passed"] = audit["input_files_unchanged"]
        except Exception:
            audit["input_files_unchanged"] = False
        full = encoded(audit)
        require(len(full) <= MAX_JSON, "audit_budget")
        (out/"glb-correctives-audit.json").write_bytes(full)
        small = {k: audit.get(k) for k in ("writer_completed", "error", "glb_written", "preflight",
            "tangent_policy", "input_files_unchanged", "native_reference_hash_recheck",
            "native_playback_this_job", "overall_art_approved", "production_glb_approved")}
        require(len(encoded(small)) <= 24576, "summary_budget")
        print("SNOW_GLB_CUBIC_WRITER " + encoded(small).decode(), flush=True)
    return 0 if audit["writer_completed"] and audit["readonly_cleanup_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
