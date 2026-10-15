#!/usr/bin/env python3
"""Fresh-process verification of one packed-used-textures Snow native derivative.

No original asset lookup, relinking, native clip replay, material baking or render.
The same reviewed wrapper supplies canonical snapshots; this is not independent math.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

MAX_EXPECTED = 1024*1024
MAX_BLEND = 128*1024*1024
MAX_TEXTURE = 32*1024*1024
MAX_REPORT = 1024*1024
MAX_STDOUT = 24*1024
WRAPPER_FILE = "bpy-pack-snow-used-textures.py"
FIELDS = {"schema_version", "wrapper_blob", "worker_blob", "blend_sha256", "blend_bytes",
          "snapshot", "snapshot_sha256", "reference_binding", "saved_binding",
          "action_names", "images", "missing_root", "reference_values", "pre_save_id_inventory", "retention_policy"}


def require(condition, code):
    if not condition:
        raise ValueError("packed_reopen_"+code)


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)+"\n").encode("utf-8")


def checksum(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()


def digest_text(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(c in "0123456789abcdef" for c in value))


def finite_json(value):
    if isinstance(value, float):
        require(math.isfinite(value), "nonfinite_expected")
    elif isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str), "expected_key_type")
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)
    else:
        require(value is None or type(value) in (str, bool, int), "expected_json_type")


def checked_binding(value):
    require(isinstance(value, dict) and set(value) == {
        "action", "slot_identifier", "frame", "subframe"}, "binding_schema")
    require(isinstance(value["action"], str) and 0 < len(value["action"]) <= 256
            and isinstance(value["slot_identifier"], str) and 0 < len(value["slot_identifier"]) <= 256
            and type(value["frame"]) is int and type(value["subframe"]) in (int, float)
            and math.isfinite(value["subframe"]) and 0 <= value["subframe"] < 1, "binding_values")


def checked_retention_policy(policy, snapshot):
    fields = {"object_name", "source_users", "source_use_fake_user", "saved_users",
              "saved_use_fake_user", "driver_identity_sha256", "saved_object_fake_users"}
    require(isinstance(policy, dict) and set(policy) == fields, "retention_policy_schema")
    require(policy["object_name"] == "GEO-snow-eye_anim"
            and type(policy["source_users"]) is int and policy["source_users"] == 0
            and policy["source_use_fake_user"] is False
            and type(policy["saved_users"]) is int and policy["saved_users"] == 1
            and policy["saved_use_fake_user"] is True
            and policy["driver_identity_sha256"] ==
                "d9638f60715ccbe8d885fdf6709cf1e74b229201d0a3c5ee85363c1f13c80040",
            "retention_policy_fixed_values")
    flags = policy["saved_object_fake_users"]
    require(isinstance(flags, dict) and len(flags) == 59
            and all(isinstance(name, str) and 0 < len(name) <= 256
                    and type(flag) is bool for name, flag in flags.items())
            and flags.get("GEO-snow-eye_anim") is True, "retention_saved_flags")
    require(isinstance(snapshot.get("stable_inventory"), dict)
            and isinstance(snapshot["stable_inventory"].get("objects"), list)
            and sorted(flags) == sorted(snapshot["stable_inventory"]["objects"]),
            "retention_expected_object_names")


def verify_retained_object(bpy, policy):
    # Read-only saved-state check. The source-state fields are the parent's guarded declaration.
    target = bpy.data.objects.get("GEO-snow-eye_anim")
    require(target is not None and target.type == "MESH"
            and target.library is None and target.override_library is None,
            "retention_target_local_mesh")
    scenes = sorted(scene.name for scene in bpy.data.scenes
                    if scene.objects.get(target.name) == target)
    collections = sorted(collection.name for collection in target.users_collection)
    require(not scenes and not collections, "retention_target_became_linked")
    require(target.use_fake_user is True and int(target.users) == 1,
            "retention_saved_target_flag_or_users")
    actual_flags = {obj.name: bool(obj.use_fake_user) for obj in bpy.data.objects}
    require(len(actual_flags) == 59 and actual_flags == policy["saved_object_fake_users"],
            "retention_all_object_flags_or_names")
    animation = target.animation_data
    curves = list(animation.drivers) if animation is not None else []
    require(len(curves) == 1, "retention_target_driver_count")
    keys = sorted([curve.data_path, int(curve.array_index), curve.driver.type] for curve in curves)
    identity = hashlib.sha256(encoded(keys)).hexdigest()
    require(identity == policy["driver_identity_sha256"], "retention_target_driver_identity")
    return {"object_name": target.name, "object_type": target.type, "local_no_override": True,
            "users": int(target.users), "use_fake_user": bool(target.use_fake_user),
            "scene_names": scenes, "collection_names": collections, "own_driver_count": len(curves),
            "driver_identity_sha256": identity, "object_count": len(actual_flags),
            "all_saved_object_fake_user_flags_equal": True,
            "saved_object_fake_users_sha256": hashlib.sha256(encoded(actual_flags)).hexdigest(),
            "source_state_is_declared_parent_guard": True, "read_only_saved_state_check": True,
            "passed": True}


def load_expected(path, expected_sha):
    require(digest_text(expected_sha, 64), "expected_sha_argument")
    require(path.is_file() and not path.is_symlink()
            and 0 < path.stat().st_size <= MAX_EXPECTED, "expected_file_budget")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha, "expected_file_hash")
    value = json.loads(raw.decode("utf-8"))
    finite_json(value)
    require(isinstance(value, dict) and set(value) == FIELDS and value["schema_version"] == 3,
            "expected_schema")
    for key in ("wrapper_blob", "worker_blob"):
        require(digest_text(value[key], 40), "expected_source_pin")
    for key in ("blend_sha256", "snapshot_sha256"):
        require(digest_text(value[key], 64), "expected_sha_pin")
    require(type(value["blend_bytes"]) is int and 0 < value["blend_bytes"] <= MAX_BLEND,
            "expected_blend_budget")
    require(isinstance(value["snapshot"], dict) and hashlib.sha256(
        encoded(value["snapshot"])).hexdigest() == value["snapshot_sha256"], "snapshot_hash")
    checked_retention_policy(value["retention_policy"], value["snapshot"])
    for key in ("saved_binding", "reference_binding"):
        checked_binding(value[key])
    require(value["reference_binding"]["action"] == "COOP_SNOW_NATIVE_IDLE_CANDIDATE"
            and value["reference_binding"]["slot_identifier"] == "OBRIG-Snow"
            and value["reference_binding"]["frame"] == 0
            and value["reference_binding"]["subframe"] == 0, "fixed_reference_binding")
    names = value["action_names"]
    require(isinstance(names, list) and names and all(isinstance(n, str) and 0 < len(n) <= 256 for n in names)
            and names == sorted(set(names)), "action_names")
    rows = value["images"]
    require(isinstance(rows, list) and len(rows) == 22
            and all(isinstance(r, dict) and isinstance(r.get("name"), str) for r in rows)
            and len({r["name"] for r in rows}) == 22
            and sum(r.get("source") == "FILE" for r in rows) == 18
            and sum(r.get("source") == "TILED" for r in rows) == 4, "used_image_inventory")
    root = Path(value["missing_root"])
    require(root.is_absolute() and not root.exists(), "missing_root_not_absent")
    total, count, unique = 0, 0, set()
    for row in rows:
        require(set(row) == {"name", "source", "colorspace", "alpha_mode", "tiles",
                             "missing_pattern", "files"}, "image_row_schema")
        require(isinstance(row["tiles"], list) and all(type(t) is int for t in row["tiles"])
                and len(row["tiles"]) == len(set(row["tiles"])), "tile_inventory")
        if row["source"] == "TILED":
            require(sorted(row["tiles"]) == [1001, 1002, 1003], "fixed_udim_tiles")
        require(isinstance(row["files"], list)
                and len(row["files"]) == (3 if row["source"] == "TILED" else 1), "file_count")
        require(all(isinstance(row[k], str) and 0 < len(row[k]) <= 4096
                    for k in ("colorspace", "alpha_mode", "missing_pattern")), "image_row_text")
        pattern = Path(row["missing_pattern"])
        require(pattern.is_absolute() and pattern.is_relative_to(root)
                and not pattern.exists(), "missing_pattern_not_isolated")
        if row["source"] == "TILED":
            require("<UDIM>" in row["missing_pattern"], "missing_pattern_udim_token")
        for file in row["files"]:
            require(isinstance(file, dict) and set(file) == {
                "view", "tile_number", "file", "bytes", "sha256", "size", "channels", "missing_path"},
                "file_row_schema")
            require(type(file["view"]) is int and file["view"] == 0
                    and type(file["tile_number"]) is int
                    and file["tile_number"] in ([1001, 1002, 1003] if row["source"] == "TILED" else [1001]),
                    "fixed_file_view_tile")
            require(isinstance(file["file"], str) and 0 < len(file["file"]) <= 4096
                    and file["file"] not in unique, "source_file_identity")
            unique.add(file["file"])
            require(type(file["bytes"]) is int and 0 < file["bytes"] <= MAX_TEXTURE
                    and digest_text(file["sha256"], 64), "source_file_byte_pin")
            require(isinstance(file["size"], list) and len(file["size"]) == 2
                    and all(type(d) is int and d > 0 for d in file["size"])
                    and type(file["channels"]) is int and file["channels"] > 0, "decoded_descriptor")
            missing = Path(file["missing_path"])
            require(missing.is_absolute() and missing.is_relative_to(root)
                    and not missing.exists(), "source_path_not_missing")
            count += 1
            total += file["bytes"]
    require(count == len(unique) == 30 and total == 97102085, "fixed_file_count_or_bytes")
    require(isinstance(value["reference_values"], dict), "reference_values_schema")
    return value


def checked_regular(path, cap):
    require(path.is_file() and not path.is_symlink()
            and 0 < path.stat().st_size <= cap, "source_file_type_or_budget")


def failure_record(error, stage):
    code = None
    if (isinstance(error, ValueError) and len(error.args) == 1
            and isinstance(error.args[0], str) and len(error.args[0]) <= 180
            and error.args[0].startswith(("packed_reopen_", "packed_native_"))
            and all(c.isascii() and (c.isalnum() or c == "_") for c in error.args[0])):
        code = error.args[0]
    frames, trace = [], error.__traceback__
    while trace is not None:
        frames.append({"file": Path(trace.tb_frame.f_code.co_filename).name[:128],
                       "line": trace.tb_lineno, "function": trace.tb_frame.f_code.co_name[:128]})
        frames = frames[-6:]
        trace = trace.tb_next
    return {"stage": stage, "error_type": type(error).__name__, "error_code": code, "frames": frames}


def observe_driver_aggregate(bpy,soft,helper):
    # Read-only observation; an inspection failure must not replace the strict checks.
    try:
        summary=soft.driver_summary(helper,bpy)
        records=helper.driver_evaluation_status(bpy)
        return {"native_driver_status":summary,
                "autoexec_enabled":bool(bpy.context.preferences.filepaths.use_scripts_auto_execute),
                "native_unmuted":sum(r["native_without_python"] and not r["muted"] for r in records),
                "non_native_unmuted":sum(not r["native_without_python"] and not r["muted"] for r in records),
                "record_count":len(records)}
    except Exception as error:
        return {"inspection_error":{"error_type":type(error).__name__[:64]}}



def observe_id_comparison(bpy,wrapper,expected,aggregate):
    # Parent identities are pinned expected data. Differences are observations, never recovery.
    try:
        before=expected["pre_save_id_inventory"]
        after=wrapper.observe_id_persistence(bpy,aggregate.get("native_driver_status",{}).get("count"))
        if "inspection_error" in before or "inspection_error" in after:
            return {"inspection_unavailable":True,"before":before.get("inspection_error"),
                    "after":after.get("inspection_error")}
        left={row["name"]:row for row in before["objects"]}
        right={row["name"]:row for row in after["objects"]}
        require(len(left)==len(before["objects"]) and len(right)==len(after["objects"]),
                "diagnostic_object_identity_duplicate")
        missing=sorted(set(left)-set(right));extra=sorted(set(right)-set(left))
        old={tuple(row["owner_key"]):row for row in before["driver_owners"]}
        new={tuple(row["owner_key"]):row for row in after["driver_owners"]}
        require(len(old)==len(before["driver_owners"]) and len(new)==len(after["driver_owners"]),
                "diagnostic_owner_identity_duplicate")
        absent=sorted(set(old)-set(new));added=sorted(set(new)-set(old))
        changed=sorted(key for key in set(old)&set(new) if old[key]!=new[key])
        details=([{"kind":"missing_object","before":left[name]} for name in missing]
            +[{"kind":"extra_object","after":right[name]} for name in extra]
            +[{"kind":"missing_driver_owner","before":old[key]} for key in absent]
            +[{"kind":"extra_driver_owner","after":new[key]} for key in added]
            +[{"kind":"changed_driver_owner","before":old[key],"after":new[key]} for key in changed])
        result={"object_count_before":len(left),"object_count_after":len(right),
            "missing_object_count":len(missing),"extra_object_count":len(extra),
            "missing_owner_count":len(absent),"extra_owner_count":len(added),
            "changed_owner_count":len(changed),"details":details[:20],
            "driver_count_before":sum(row["driver_count"] for row in old.values()),
            "driver_count_after":sum(row["driver_count"] for row in new.values()),
            "aggregate_matches_helper_before":before["aggregate_matches_helper"],
            "aggregate_matches_helper_after":after["aggregate_matches_helper"],
            "detail_limit":20,"details_omitted":max(0,len(details)-20),
            "details_truncated":len(details)>20,"diagnostic_byte_budget":16*1024,
            "users_and_fake_users_are_observations_only":True}
        while result["details"] and len(encoded(result))>16*1024:
            result["details"].pop()
            result["details_omitted"]=len(details)-len(result["details"])
            result["details_truncated"]=True
        return result
    except Exception as error:
        return {"inspection_error":{"error_type":type(error).__name__[:64]}}

def main():
    parser = argparse.ArgumentParser()
    for name in ("blend", "expected", "expected-sha", "out"):
        parser.add_argument("--"+name, required=True)
    args = parser.parse_args()
    out = Path(args.out)
    audit_path = out/"packed-reopen-audit.json"
    stage = "arguments"
    expected = before = None
    verification_passed = False
    result = {"worker": "fresh_process_packed_used_textures_v1", "passed": False,
              "packed_used_textures_only": False, "full_scene_portable": False,
              "glb_pbr_approved": False, "overall_art_approved": False,
              "browser_animation_approved": False, "production_glb_approved": False,
              "native_clip_replay": False, "source_relink_performed": False,
              "same_reviewed_snapshot_code": True, "independent_math_reader": False,
              "failure": None}
    try:
        require(sys.version_info[:2] == (3, 11), "python_version")
        require(not audit_path.exists(), "audit_already_exists")
        stage = "expected"
        expected_path, blend_path = Path(args.expected), Path(args.blend)
        expected = load_expected(expected_path, args.expected_sha)
        stage = "source_pins"
        worker_path = Path(__file__)
        wrapper_path = worker_path.with_name(WRAPPER_FILE)
        checked_regular(worker_path, MAX_EXPECTED)
        checked_regular(wrapper_path, MAX_EXPECTED)
        worker_raw, wrapper_raw = worker_path.read_bytes(), wrapper_path.read_bytes()
        require(git_blob(worker_raw) == expected["worker_blob"]
                and git_blob(wrapper_raw) == expected["wrapper_blob"], "worker_or_wrapper_blob")
        checked_regular(blend_path, MAX_BLEND)
        before = checksum(blend_path)
        require(blend_path.stat().st_size == expected["blend_bytes"]
                and before == expected["blend_sha256"], "candidate_blend_identity")
        result.update({"expected_sha256": args.expected_sha, "wrapper_blob": expected["wrapper_blob"],
                       "worker_blob": expected["worker_blob"], "blend_sha256_before": before,
                       "blend_bytes": expected["blend_bytes"],
                       "expected_snapshot_sha256": expected["snapshot_sha256"]})
        # Import only a fixed sibling path after BOTH source blobs are verified.
        stage = "reviewed_wrapper_import"
        spec = importlib.util.spec_from_file_location("_packed_snow_verified_wrapper", wrapper_path)
        require(spec is not None and spec.loader is not None, "wrapper_module_spec")
        wrapper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wrapper)
        stage = "runtime"
        import bpy
        bpy.context.preferences.filepaths.use_scripts_auto_execute = False
        wrapper.validate_runtime(bpy)
        modules = wrapper.load_modules()
        require(isinstance(modules, tuple) and len(modules) == 8, "reviewed_module_inventory")
        base, native, natural, face, proof, soft, pair, helper = modules
        stage = "fresh_open"
        opened = bpy.ops.wm.open_mainfile(filepath=str(blend_path.resolve(strict=True)),
                                        load_ui=False, use_scripts=False)
        require("FINISHED" in opened
                and bpy.context.preferences.filepaths.use_scripts_auto_execute is False,
                "open_or_autoexec_policy")
        wrapper.validate_runtime(bpy)
        result["native_driver_after_open"] = observe_driver_aggregate(bpy, soft, helper)
        result["id_persistence_comparison"] = observe_id_comparison(bpy, wrapper, expected, result["native_driver_after_open"])
        stage = "retention_policy_readback"
        result["retention_policy_readback"] = verify_retained_object(bpy, expected["retention_policy"])
        stage = "fresh_open"
        rig = bpy.data.objects.get("RIG-Snow")
        require(rig is not None and rig.type == "ARMATURE" and rig.data.pose_position == "POSE"
                and rig.name in bpy.context.scene.objects, "saved_native_rig")
        stage = "saved_binding"
        saved = wrapper.binding_state(bpy, rig)
        checked_binding(saved)
        require(saved == expected["saved_binding"], "saved_binding_changed")
        result["saved_binding_verified"] = True
        stage = "reference_binding"
        bound = wrapper.bind_reference(bpy, native, rig)
        require(bound == expected["reference_binding"]
                and wrapper.binding_state(bpy, rig) == expected["reference_binding"],
                "reference_binding_changed")
        result["native_driver_after_reference"] = observe_driver_aggregate(bpy, soft, helper)
        stage = "snapshot_before_decode"
        result["native_guard_context"] = {}
        first = wrapper.capture_state(bpy, modules, rig, expected["action_names"],
                                      diagnostics=result["native_guard_context"])
        first_hash = hashlib.sha256(encoded(first)).hexdigest()
        require(first == expected["snapshot"] and first_hash == expected["snapshot_sha256"],
                "saved_snapshot_changed")
        values_before = wrapper.compare_values(
            wrapper.numeric_values(bpy, modules, rig), expected["reference_values"])
        finite_json(values_before)
        require(isinstance(values_before, dict) and values_before.get("passed") is True,
                "reference_values_before_decode")
        result["reference_values_before_decode"] = values_before
        result["observed_snapshot_sha256_before_decode"] = first_hash
        stage = "packed_entries_and_decode"
        images = wrapper.used_images(bpy, pair)
        require(len(images) == 22 and len({image.name for image in images}) == 22
                and {image.name for image in images} == {row["name"] for row in expected["images"]},
                "saved_used_image_closure_changed")
        packed = wrapper.packed_state(
            bpy, images, expected["images"], Path(expected["missing_root"]), decode=True)
        finite_json(packed)
        require(isinstance(packed, dict) and packed.get("all_passed") is True
                and packed.get("images") == 22 and packed.get("packed_entries") == 30
                and packed.get("packed_bytes") == 97102085
                and packed.get("decoded_file_buffers") == 18
                and packed.get("decoded_tile_buffers") == 12
                and packed.get("external_paths_all_missing") is True
                and len(packed.get("records", [])) == 30, "saved_pack_decode_counts")
        result["packed_verification"] = packed
        stage = "snapshot_after_decode"
        last = wrapper.capture_state(bpy, modules, rig, expected["action_names"])
        last_hash = hashlib.sha256(encoded(last)).hexdigest()
        require(last == expected["snapshot"] and last == first
                and last_hash == expected["snapshot_sha256"], "decode_changed_saved_structure")
        require(wrapper.binding_state(bpy, rig) == expected["reference_binding"],
                "decode_changed_reference_binding")
        values_after = wrapper.compare_values(
            wrapper.numeric_values(bpy, modules, rig), expected["reference_values"])
        finite_json(values_after)
        require(isinstance(values_after, dict) and values_after.get("passed") is True,
                "reference_values_after_decode")
        result["reference_values_after_decode"] = values_after
        result["observed_snapshot_sha256_after_decode"] = last_hash
        require(bpy.context.preferences.filepaths.use_scripts_auto_execute is False,
                "autoexec_changed_after_decode")
        verification_passed = True
    except Exception as error:
        result["failure"] = failure_record(error, stage)
    # Hash-only cleanup also runs when decode/snapshot checks fail; preserve the
    # first error and never turn a failed verification into a successful audit.
    hashes_passed = False
    if before is not None:
        try:
            checked_regular(blend_path, MAX_BLEND)
            after = checksum(blend_path)
            result["blend_sha256_after"] = after
            result["candidate_blend_hash_unchanged"] = (
                after == before and blend_path.stat().st_size == expected["blend_bytes"])
            require(result["candidate_blend_hash_unchanged"], "candidate_blend_changed")
            require(checksum(expected_path) == args.expected_sha
                    and git_blob(worker_path.read_bytes()) == expected["worker_blob"]
                    and git_blob(wrapper_path.read_bytes()) == expected["wrapper_blob"],
                    "expected_or_sources_changed")
            result["expected_and_source_hashes_unchanged"] = True
            hashes_passed = True
        except Exception as error:
            cleanup_failure = failure_record(error, "input_hash_recheck")
            if result["failure"] is None:
                result["failure"] = cleanup_failure
            else:
                result["hash_recheck_failure"] = cleanup_failure
    result["passed"] = bool(verification_passed and hashes_passed and result["failure"] is None)
    result["packed_used_textures_only"] = result["passed"]
    if verification_passed:
        result["snapshot_stable_before_and_after_decode"] = True
        result["reference_values_passed_before_and_after_decode"] = True
    # Fixed flags do not conflate packed transport/decode with scene/PBR/render acceptance.
    payload = encoded(result)
    summary = {key: value for key, value in result.items()
               if key not in ("packed_verification", "native_guard_context", "id_persistence_comparison")}
    if "id_persistence_comparison" in result:
        summary["id_persistence_comparison_in_report"] = True
    if "native_guard_context" in result:
        summary["native_guard_context_in_report"] = True
    if "packed_verification" in result:
        summary["packed_verification"] = {k: v for k, v in result["packed_verification"].items() if k != "records"}
    small = encoded(summary)
    require(len(payload) <= MAX_REPORT and len(small) <= MAX_STDOUT, "report_or_stdout_budget")
    try:
        out.mkdir(parents=True, exist_ok=True)
        with audit_path.open("xb") as file:
            file.write(payload)
    except OSError as error:
        summary["passed"] = False
        summary["packed_used_textures_only"] = False
        summary["audit_write_error_type"] = type(error).__name__
        small = encoded(summary)
        print("SNOW_PACKED_TEXTURES_REOPEN "+small.decode("utf-8").rstrip("\n"), flush=True)
        return 1
    print("SNOW_PACKED_TEXTURES_REOPEN "+small.decode("utf-8").rstrip("\n"), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
