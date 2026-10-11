"""Targeted actual-bpy Rain spine trace. No render, source save or expression fix."""
import argparse, contextlib, ctypes, hashlib, importlib.util, json, math, os, re, stat, sys
from pathlib import Path
OWNER, TARGET, OWNER_BONE = "RIG-rain", "STR-Spine4", "DEF-Spine3"
PATH = 'pose.bones["DEF-Spine3"].bbone_easeout'
SOURCE_SHA = "831ab6d837c679040285862b15dc9ee5180b018442a88aeaf92aaa7509b80258"
HELPER_BLOB = "a64c4f14e977a6ae720fb57b01ffa9f69d5703f8"
CONFIG_BLOB = "e0621512cddb82c3bd174cba655e70862587a39a"
SAFE = frozenset(("invalid_arguments", "source_checksum", "readonly_source_required",
    "trusted_helper_mismatch", "config_mismatch", "runtime_mismatch", "owner_missing",
    "driver_missing", "driver_identity_mismatch", "mesh_missing", "scene_missing",
    "missing_credit", "nonfinite_value", "report_budget"))
class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid_arguments")
def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1048576), b""):
            digest.update(data)
    return digest.hexdigest()
def blob_sha(data):
    return hashlib.sha1(("blob " + str(len(data)) + "\0").encode() + data).hexdigest()
def text(value):
    if value is None:
        return None
    value = re.sub(r"[\x00-\x1f\x7f]", " ", str(value))
    value = re.sub(r"https?://[^\s\"'<>]+", "[redacted URL]", value, flags=re.I)
    value = re.sub(r"\b(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]+", "[redacted credential]", value)
    value = re.sub(r"\bBearer\s+[^\s\"'<>]+", "Bearer [redacted]", value, flags=re.I)
    return value[:256]
def num(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("nonfinite_value")
    return value
def vector(value):
    return [num(x) for x in value]
def matrix(value):
    return [vector(row) for row in value]
@contextlib.contextmanager
def quiet_native():
    # Do not leak unrelated Blender diagnostics/all driver expressions into stdout/artifacts.
    libc = ctypes.CDLL(None)
    libc.fflush(None)
    sys.stdout.flush()
    sys.stderr.flush()
    saved = (os.dup(1), os.dup(2))
    try:
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
            yield
    finally:
        libc.fflush(None)
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        os.close(saved[0])
        os.close(saved[1])
def link_dependencies(bpy, selected_meshes):
    scene = bpy.context.scene
    if scene is None:
        raise ValueError("scene_missing")
    scene.name = "AVATAR_SOURCE_PROOF"
    # Reuse the active scene so the bpy module does not require a UI window.
    # Unlink scene contents without deleting any original dependency datablocks.
    for collection in list(scene.collection.children):
        scene.collection.children.unlink(collection)
    for obj in list(scene.collection.objects):
        scene.collection.objects.unlink(obj)
    for obj in selected_meshes:
        scene.collection.objects.link(obj)
        obj.hide_render = False
        obj.hide_viewport = False
    # Link original transform/rig dependencies, never source widget geometry.
    for obj in list(bpy.data.objects):
        if obj.type in ("ARMATURE", "EMPTY", "LATTICE") and obj.name not in scene.objects:
            scene.collection.objects.link(obj)
    # Keep mesh modifier dependencies in the scene but never render helper geometry.
    pending = list(selected_meshes)
    linked_dependencies = []
    scanned = set()
    while pending:
        owner = pending.pop()
        if owner.as_pointer() in scanned:
            continue
        scanned.add(owner.as_pointer())
        for modifier in owner.modifiers:
            for attribute in ("object", "target"):
                dependency = getattr(modifier, attribute, None)
                if not isinstance(dependency, bpy.types.Object):
                    continue
                if dependency.name not in scene.objects:
                    scene.collection.objects.link(dependency)
                if dependency.type == "MESH" and dependency not in selected_meshes:
                    dependency.hide_render = True
                    linked_dependencies.append(dependency.name)
                    pending.append(dependency)
    return {"linked_object_count": len(scene.objects),
            "hidden_modifier_dependency_count": len(set(linked_dependencies))}
def bone(rig, name):
    data = rig.data.bones.get(name) if rig and rig.type == "ARMATURE" else None
    pose = rig.pose.bones.get(name) if rig and rig.type == "ARMATURE" else None
    result = {"data_bone_exists": data is not None, "pose_bone_exists": pose is not None}
    if pose:
        result.update({"scale": vector(pose.scale), "matrix_basis": matrix(pose.matrix_basis),
                       "pose_matrix": matrix(pose.matrix), "world_matrix": matrix(rig.matrix_world @ pose.matrix)})
        if name == OWNER_BONE:
            result.update({"bbone_easeout": num(pose.bbone_easeout),
                           "bbone_segments": int(data.bbone_segments) if data else None})
    return result
def snapshot(rig, curve, variable):
    target = variable.targets[0]
    identity = target.id
    expression = curve.driver.expression
    return {"driver": {"owner": OWNER, "path": PATH, "array_index": int(curve.array_index),
        "type": curve.driver.type, "is_valid": bool(curve.driver.is_valid), "mute": bool(curve.mute),
        "native_without_python": bool(curve.driver.is_simple_expression),
        "expression": text(expression), "expression_truncated": len(expression) > 256,
        "expression_sha256": hashlib.sha256(expression.encode()).hexdigest()},
        "variable": {"name": "scale", "type": variable.type, "target_id": text(identity.name) if identity else None,
            "target_id_exists": identity is not None, "target_id_is_owner": bool(identity == rig) if identity else False,
            "bone_target": text(target.bone_target), "transform_type": text(target.transform_type),
            "transform_space": text(target.transform_space), "rotation_mode": text(target.rotation_mode)},
        "target_bone": bone(identity, TARGET), "owner_bone": bone(rig, OWNER_BONE)}
def credits(source, out):
    if source.parents[2].name != "rain" or source.parents[1].name != "original":
        raise ValueError("missing_credit")
    root = source.parents[3]
    result = []
    for path in (Path("LICENSES.md"), Path("rain/ATTRIBUTION.txt")):
        original, destination = root / path, out / "credits" / path
        if original.is_symlink() or not original.is_file() or not 0 < original.stat().st_size <= 1048576:
            raise ValueError("missing_credit")
        data = original.read_bytes()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(0o444)
        if destination.read_bytes() != data:
            raise ValueError("missing_credit")
        result.append({"file": "credits/" + path.as_posix(), "bytes": len(data),
                       "sha256": hashlib.sha256(data).hexdigest(), "byte_identical": True})
    return result
def main():
    out, stage = None, "setup"
    try:
        parser = Parser(add_help=False)
        for arg in ("--blend", "--config", "--out"):
            parser.add_argument(arg, required=True)
        args = parser.parse_args()
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=False)
        source = Path(args.blend).resolve(strict=True)
        if not stat.S_ISREG(source.stat().st_mode) or source.stat().st_mode & 0o333:
            raise ValueError("readonly_source_required")
        if sha(source) != SOURCE_SHA:
            raise ValueError("source_checksum")
        credit_records = credits(source, out)
        helper = Path(__file__).resolve().with_name("bpy-inspect-avatar-garments.py")
        if blob_sha(helper.read_bytes()) != HELPER_BLOB:
            raise ValueError("trusted_helper_mismatch")
        config_bytes = Path(args.config).read_bytes()
        if blob_sha(config_bytes) != CONFIG_BLOB:
            raise ValueError("config_mismatch")
        config = json.loads(config_bytes)
        if config["model"] != "rain" or config["rig_name"] != OWNER or config["poses"] != {"neutral": []}:
            raise ValueError("config_mismatch")
        stage = "bpy_trace"
        with quiet_native():
            spec = importlib.util.spec_from_file_location("_trusted_rain_inspector", helper)
            trusted = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(trusted)  # Pinned repository module, never source archive code.
            import bpy
            if sys.version_info[:2] != (3, 11) or tuple(bpy.app.version) != (4, 5, 9):
                raise ValueError("runtime_mismatch")
            bpy.context.preferences.filepaths.use_scripts_auto_execute = False
            bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
            rig = bpy.data.objects.get(OWNER)
            if not rig or rig.type != "ARMATURE":
                raise ValueError("owner_missing")
            matches = [c for c in rig.animation_data.drivers if c.data_path == PATH and c.array_index == 0] if rig.animation_data else []
            if len(matches) != 1:
                raise ValueError("driver_missing")
            curve = matches[0]
            variable = curve.driver.variables.get("scale")
            if (curve.driver.type != "SCRIPTED" or not curve.driver.is_simple_expression or curve.mute
                or variable is None or variable.type != "TRANSFORMS" or len(variable.targets) != 1
                or variable.targets[0].bone_target != TARGET):
                raise ValueError("driver_identity_mismatch")
            original_expression, original_mute = curve.driver.expression, bool(curve.mute)
            policy = trusted.disable_animation_and_scripts(bpy)
            if curve.mute or not curve.driver.is_simple_expression:
                raise ValueError("driver_identity_mismatch")
            selected_meshes = []
            for name in config["mesh_names"]:
                obj = bpy.data.objects.get(name)
                if not obj or obj.type != "MESH" or not obj.data.vertices:
                    raise ValueError("mesh_missing")
                selected_meshes.append(obj)
            trusted.resolve_images(bpy, source.parent)
            linkage = link_dependencies(bpy, selected_meshes)
            trusted.apply_pose(rig, config["poses"]["neutral"])
            before = snapshot(rig, curve, variable)
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            depsgraph.update()
            after = snapshot(rig, curve, variable)
            evaluated_rig = rig.evaluated_get(depsgraph)
            evaluated_target = variable.targets[0].id.evaluated_get(depsgraph) if variable.targets[0].id else None
            evaluated = {"target_bone": bone(evaluated_target, TARGET),
                         "owner_bone": bone(evaluated_rig, OWNER_BONE)}
            policy_counts = {"blocks": len(policy), "drivers": sum(len(p["drivers"]) for p in policy),
                "native_retained": sum(p["native_drivers_retained"] for p in policy),
                "complex_python_muted": sum(p["complex_python_drivers_muted"] for p in policy)}
            expression_unchanged = curve.driver.expression == original_expression
            mute_unchanged = bool(curve.mute) == original_mute
            autoexec_disabled = not bpy.context.preferences.filepaths.use_scripts_auto_execute
        stage = "source_recheck_and_report"
        if sha(source) != SOURCE_SHA:
            raise ValueError("source_checksum")
        report = {"schema_version": 1, "ok": True, "source_sha256": SOURCE_SHA,
            "trusted_inspector_blob": HELPER_BLOB, "reviewed_config_blob": CONFIG_BLOB,
            "before_explicit_update_under_policy": before, "after_explicit_update_under_policy": after,
            "evaluated_after_update": evaluated, "policy_counts": policy_counts, "dependency_linkage": linkage,
            "credits": credit_records, "expression_unchanged": expression_unchanged, "mute_unchanged": mute_unchanged,
            "explicit_bone_value_assignments": False, "automatic_python_execution_disabled": autoexec_disabled,
            "source_hash_rechecked": True, "source_modified_on_disk": False, "source_saved": False,
            "renders_performed": False, "cause_established": False, "production_glb_approved": False}
        payload = json.dumps(report, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        marker = b"AVATAR_RAIN_SPINE_TRACE "
        if len(marker) + len(payload) + 1 > 24576:
            raise ValueError("report_budget")
        (out / "rain-spine-trace.json").write_bytes(payload + b"\n")
        print(marker.decode() + payload.decode(), flush=True)
        return 0
    except Exception as error:
        failure = {"ok": False, "stage": stage, "error_type": type(error).__name__}
        frames, node = [], error.__traceback__
        while node is not None:
            code = node.tb_frame.f_code
            frames.append({"file": text(Path(code.co_filename).name)[:128],
                           "line": int(node.tb_lineno), "function": text(code.co_name)[:128]})
            frames = frames[-6:]
            node = node.tb_next
        failure["frames"] = frames
        if isinstance(error, ValueError) and len(error.args) == 1 and isinstance(error.args[0], str) and error.args[0] in SAFE:
            failure["error_code"] = error.args[0]
        if out is not None and out.is_dir():
            try:
                (out / "rain-spine-trace-failure.json").write_text(json.dumps(failure) + "\n", encoding="utf-8")
            except OSError:
                pass
        print("AVATAR_RAIN_SPINE_TRACE_FAILED " + json.dumps(failure), flush=True)
        return 1
if __name__ == "__main__":
    sys.exit(main())
