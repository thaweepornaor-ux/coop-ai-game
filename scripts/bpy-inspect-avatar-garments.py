"""Inspect real Rain/Snow garments and render under Blender-native driver evaluation.
Raw boundary indices are topology evidence, never guessed anatomical edit selections.
No garment changes, embedded Text execution, clips or GLB export are performed.
"""
import argparse
import base64
import hashlib
import json
import math
import struct
from pathlib import Path
import sys

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")

def json_property(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return [json_property(item) for item in value]
    except TypeError:
        return str(type(value).__name__)

def disable_animation_and_scripts(bpy):
    """Keep Blender-native driver logic; mute expressions requiring full Python."""
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    records = []
    visited = set()
    def prepare(block, category):
        if block is None or block.as_pointer() in visited:
            return
        visited.add(block.as_pointer())
        animation = getattr(block, "animation_data", None)
        if animation:
            drivers = []
            for curve in animation.drivers:
                driver = curve.driver
                native = (driver.type != "SCRIPTED" or driver.is_simple_expression)
                originally_muted = curve.mute
                if not native:
                    curve.mute = True
                drivers.append({
                    "path": curve.data_path, "index": curve.array_index,
                    "type": driver.type, "expression": driver.expression,
                    "native_without_python": native,
                    "originally_muted": originally_muted,
                    "muted_after_policy": curve.mute,
                })
            action_name = animation.action.name if animation.action else None
            nla_count = len(animation.nla_tracks)
            # Preserve driver dependencies such as native IK/FK influence math.
            # Detach time-based source clips; the proof uses explicit poses only.
            animation.action = None
            for track in list(animation.nla_tracks):
                animation.nla_tracks.remove(track)
            records.append({
                "id_type": category, "name": block.name, "drivers": drivers,
                "detached_action": action_name, "removed_nla_tracks": nla_count,
                "native_drivers_retained": sum(
                    d["native_without_python"] and not d["muted_after_policy"]
                    for d in drivers),
                "complex_python_drivers_muted": sum(
                    not d["native_without_python"] for d in drivers),
            })
        prepare(getattr(block, "node_tree", None), category + ".node_tree")
    for category in ("objects", "meshes", "armatures", "shape_keys", "materials",
                     "node_groups", "scenes", "worlds", "curves"):
        for block in getattr(bpy.data, category):
            prepare(block, category)
    return records

def resolve_images(bpy, source_dir):
    report = []
    for image in bpy.data.images:
        if image.source not in ("FILE", "TILED"):
            continue
        filename = Path(image.filepath.replace("\\", "/")).name
        if image.packed_files:
            report.append({"name": image.name, "filename": filename, "packed": True})
            continue
        candidate = Path(bpy.path.abspath(image.filepath))
        if not candidate.is_file() and image.source != "TILED":
            candidate = source_dir / "textures" / filename
        if image.source == "TILED":
            # Preserve the UDIM token; validate every declared original tile.
            if "<UDIM>" not in filename:
                raise RuntimeError("tiled_image_missing_udim_token:" + image.name)
            candidate = source_dir / "textures" / filename
            missing = [t.number for t in image.tiles
                       if not Path(str(candidate).replace("<UDIM>", str(t.number))).is_file()]
            if missing:
                raise RuntimeError("missing_original_udim_tiles:" + image.name)
        elif not candidate.is_file():
            # Missing images used by custom rig UI are reported, never fetched.
            report.append({"name": image.name, "filename": filename,
                           "packed": False, "file_present": False})
            continue
        image.filepath = str(candidate.resolve())
        report.append({"name": image.name, "filename": filename,
                       "packed": False, "file_present": True,
                       "source": image.source,
                       "tiles": [t.number for t in image.tiles] if image.source == "TILED" else []})
    return report

def rig_info(rig):
    return {
        "name": rig.name, "bone_count": len(rig.data.bones),
        "bones": [{
            "name": b.name, "parent": b.parent.name if b.parent else None,
            "deform": b.use_deform,
            "head_local": list(b.head_local), "tail_local": list(b.tail_local),
            "matrix_local": [list(row) for row in b.matrix_local],
            "bbone_segments": b.bbone_segments,
            "pose_constraints": [{
                "name": c.name, "type": c.type, "influence": c.influence,
                "target": getattr(getattr(c, "target", None), "name", None),
                "subtarget": getattr(c, "subtarget", None),
                "mute": c.mute,
            } for c in rig.pose.bones[b.name].constraints],
            "custom_properties": {
                str(k): json_property(v)
                for k, v in rig.pose.bones[b.name].items() if k != "_RNA_UI"
            },
        } for b in rig.data.bones],
    }

def apply_pose(rig, specification):
    from mathutils import Quaternion, Vector
    applied = []
    for item in specification:
        name = item.get("bone")
        if not isinstance(name, str) or name not in rig.pose.bones:
            raise ValueError("pose_requires_existing_source_bone")
        bone = rig.pose.bones[name]
        if "axis" in item and "degrees" in item:
            axis = item["axis"]
            degrees = item["degrees"]
            if (not isinstance(axis, list) or len(axis) != 3
                    or any(type(x) not in (float, int) or not math.isfinite(x) for x in axis)
                    or type(degrees) not in (float, int) or not math.isfinite(degrees)
                    or abs(degrees) > 180):
                raise ValueError("invalid_reviewed_pose_rotation")
            direction = Vector(axis)
            if direction.length < 0.001:
                raise ValueError("zero_pose_axis")
            rotation = Quaternion(direction.normalized(), math.radians(degrees))
        elif "quaternion_wxyz" in item:
            value = item["quaternion_wxyz"]
            if (not isinstance(value, list) or len(value) != 4
                    or any(type(x) not in (float, int) or not math.isfinite(x) for x in value)):
                raise ValueError("invalid_pose_quaternion")
            rotation = Quaternion(value)
            if rotation.magnitude < 0.001:
                raise ValueError("zero_pose_quaternion")
            rotation.normalize()
        else:
            raise ValueError("pose_rotation_required")
        bone.rotation_mode = "QUATERNION"
        bone.rotation_quaternion = rotation
        for key, value in item.get("properties", {}).items():
            if key not in bone or type(value) not in (int, float, bool):
                raise ValueError("pose_property_must_exist_and_be_numeric")
            bone[key] = value
        applied.append({"bone": name, "rotation_quaternion_wxyz": list(rotation),
                        "properties": item.get("properties", {})})
    return applied


GARMENT_NAMES = {"rain": "GEO-rain-top", "snow": "GEO-snow-shirt"}

def coordinate(value):
    result = [float(v) for v in value]
    if len(result) != 3 or not all(math.isfinite(v) for v in result):
        raise ValueError("nonfinite_garment_coordinate")
    return result

def coordinate_digest(values):
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<3d", *coordinate(value)))
    return digest.hexdigest()

def garment_geometry_signature(obj):
    """Hash coordinates/topology only; driver values and render state are separate."""
    mesh = obj.data
    topology = {"edges": [list(e.vertices) for e in mesh.edges],
                "polygons": [list(p.vertices) for p in mesh.polygons]}
    blocks = mesh.shape_keys.key_blocks if mesh.shape_keys else ()
    return {
        "vertex_count": len(mesh.vertices), "edge_count": len(mesh.edges),
        "polygon_count": len(mesh.polygons),
        "topology_sha256": hashlib.sha256(
            json.dumps(topology, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
        "vertex_coordinate_sha256": coordinate_digest(v.co for v in mesh.vertices),
        "shape_keys": [{"name": k.name, "point_count": len(k.data),
                        "coordinate_sha256": coordinate_digest(p.co for p in k.data)}
                       for k in blocks],
    }

def garment_render_state(obj):
    keys = obj.data.shape_keys
    return {
        "matrix_world": [[float(v) for v in row] for row in obj.matrix_world],
        "shape_keys": [{
            "name": k.name, "value": float(k.value), "mute": k.mute,
            "relative_key": k.relative_key.name if k.relative_key else None,
            "slider_min": float(k.slider_min), "slider_max": float(k.slider_max),
        } for k in keys.key_blocks] if keys else [],
        "shape_key_use_relative": keys.use_relative if keys else None,
        "vertex_group_names": [g.name for g in obj.vertex_groups],
        "modifiers": [{
            "name": m.name, "type": m.type,
            "show_viewport": m.show_viewport, "show_render": m.show_render,
            "object": getattr(getattr(m, "object", None), "name", None),
            "target": getattr(getattr(m, "target", None), "name", None),
            "is_bound": getattr(m, "is_bound", None),
        } for m in obj.modifiers],
        "materials": [s.material.name if s.material else None for s in obj.material_slots],
    }

def inspect_garment_boundaries(obj):
    mesh = obj.data
    edge_lookup = {tuple(sorted(e.vertices)): e.index for e in mesh.edges}
    incidence = {edge: 0 for edge in edge_lookup}
    for polygon in mesh.polygons:
        for key in polygon.edge_keys:
            edge = tuple(sorted(key))
            if edge not in incidence:
                raise ValueError("polygon_edge_not_in_raw_mesh")
            incidence[edge] += 1
    boundaries = {edge: edge_lookup[edge] for edge, n in incidence.items() if n == 1}
    adjacent = {}
    for a, b in boundaries:
        adjacent.setdefault(a, set()).add(b)
        adjacent.setdefault(b, set()).add(a)
    unseen, components = set(adjacent), []
    while unseen:
        pending, vertices = [min(unseen)], set()
        while pending:
            vertex = pending.pop()
            if vertex in vertices:
                continue
            vertices.add(vertex)
            pending.extend(adjacent[vertex] - vertices)
        unseen -= vertices
        edges = sorted((a, b) for a, b in boundaries if a in vertices and b in vertices)
        degree = {v: len(adjacent[v]) for v in vertices}
        closed = all(n == 2 for n in degree.values()) and len(edges) == len(vertices)
        endpoints = sorted(v for v, n in degree.items() if n == 1)
        chain = len(endpoints) == 2 and all(n in (1, 2) for n in degree.values())
        ordered = []
        if closed or chain:
            current, previous = min(vertices) if closed else endpoints[0], None
            while True:
                ordered.append(current)
                choices = sorted(v for v in adjacent[current] if v != previous)
                if not choices:
                    break
                following = choices[0]
                if closed and following == ordered[0]:
                    break
                if following in ordered:
                    raise ValueError("boundary_traversal_repeated_vertex")
                previous, current = current, following
            if set(ordered) != vertices:
                raise ValueError("boundary_traversal_incomplete")
        indices = ordered if ordered else sorted(vertices)
        points = [mesh.vertices[v].co for v in indices]
        world = [obj.matrix_world @ p for p in points]
        length = sum((mesh.vertices[a].co - mesh.vertices[b].co).length for a, b in edges)
        components.append({
            "component_id": len(components),
            "kind": "closed_loop" if closed else ("open_chain" if chain else "branched_component"),
            "ordered": bool(ordered), "closed": closed,
            "vertex_indices": indices, "edge_indices": [boundaries[e] for e in edges],
            "edges": [list(e) for e in edges],
            "vertices": [{"index": v, "degree": degree[v],
                          "local": coordinate(p), "world_at_inspection": coordinate(w)}
                         for v, p, w in zip(indices, points, world)],
            "local_bounds": {"minimum": [min(p[i] for p in points) for i in range(3)],
                             "maximum": [max(p[i] for p in points) for i in range(3)]},
            "local_edge_length": float(length), "anatomical_label": None,
        })
    return {
        "object": obj.name, "mesh": mesh.name,
        "object_matrix_world_at_inspection": [[float(v) for v in row] for row in obj.matrix_world],
        "vertex_count": len(mesh.vertices), "edge_count": len(mesh.edges),
        "polygon_count": len(mesh.polygons),
        "shape_key_count": len(mesh.shape_keys.key_blocks) if mesh.shape_keys else 0,
        "boundary_edge_count": len(boundaries), "boundary_components": components,
        "closed_loop_count": sum(c["closed"] for c in components),
        "loose_edge_indices": [edge_lookup[e] for e, n in incidence.items() if n == 0],
        "nonmanifold_edge_indices": [edge_lookup[e] for e, n in incidence.items() if n > 2],
        "limits": [
            "Raw mesh boundaries; modifiers can change visible openings.",
            "Indices never map automatically to evaluated mesh vertices.",
            "No loop is accepted as a neckline, shoulder or hem edit selection.",
        ],
    }

def driver_evaluation_status(bpy):
    records, visited = [], set()
    def inspect(block, category):
        if block is None or block.as_pointer() in visited:
            return
        visited.add(block.as_pointer())
        animation = getattr(block, "animation_data", None)
        if animation:
            for curve in animation.drivers:
                driver = curve.driver
                records.append({
                    "id_type": category, "name": block.name,
                    "path": curve.data_path, "index": curve.array_index,
                    "type": driver.type, "muted": curve.mute, "is_valid": driver.is_valid,
                    "native_without_python":
                        driver.type != "SCRIPTED" or driver.is_simple_expression,
                    "targets": [{"variable": variable.name, "variable_type": variable.type,
                                 "id": getattr(target.id, "name", None),
                                 "data_path": target.data_path,
                                 "bone_target": target.bone_target}
                                for variable in driver.variables for target in variable.targets],
                })
        inspect(getattr(block, "node_tree", None), category + ".node_tree")
    for category in ("objects", "meshes", "armatures", "shape_keys", "materials",
                     "node_groups", "scenes", "worlds", "curves"):
        for block in getattr(bpy.data, category):
            inspect(block, category)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--model", choices=("rain", "snow"), required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--emit-preview", action="store_true")
    parser.add_argument("--save-working", action="store_true")
    args = parser.parse_args()
    import bpy
    from mathutils import Matrix, Vector
    if sys.version_info[:2] != (3, 11) or tuple(bpy.app.version) != (4, 5, 9):
        raise RuntimeError("requires_python_3_11_and_bpy_4_5_9")
    source = Path(args.blend).resolve(strict=True)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = Path(args.out).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if config.get("model") != args.model:
        raise ValueError("config_model_mismatch")
    mesh_names = config.get("mesh_names")
    rig_name = config.get("rig_name")
    poses = config.get("poses")
    if (not isinstance(mesh_names, list) or not mesh_names
            or len(set(mesh_names)) != len(mesh_names)
            or not isinstance(rig_name, str)
            or not isinstance(poses, dict) or "neutral" not in poses):
        raise ValueError("reviewed_mesh_rig_and_pose_config_required")
    if poses != {"neutral": []}:
        raise ValueError("inspection_requires_unmodified_neutral_config")
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    removed_animation = disable_animation_and_scripts(bpy)
    rig = bpy.data.objects.get(rig_name)
    if not rig or rig.type != "ARMATURE":
        raise ValueError("reviewed_original_armature_not_found")
    selected_meshes = []
    for name in mesh_names:
        obj = bpy.data.objects.get(name)
        if not obj or obj.type != "MESH" or not obj.data.vertices:
            raise ValueError("reviewed_original_mesh_not_found:" + str(name))
        selected_meshes.append(obj)
    garment = bpy.data.objects.get(GARMENT_NAMES[args.model])
    if not garment or garment not in selected_meshes or garment.type != "MESH":
        raise ValueError("reviewed_garment_mesh_missing")
    geometry_before = garment_geometry_signature(garment)
    topology = inspect_garment_boundaries(garment)
    topology["geometry_signature_before"] = geometry_before
    topology["render_state_before_evaluation"] = garment_render_state(garment)
    topology["source_filename"] = source.name
    topology["source_sha256"] = source_hash
    topology["model"] = args.model
    write_json(destination / "garment-topology.json", topology)
    # The source inventory must explicitly name geometry. No source widgets or
    # primitive substitute characters are selected by guessing name prefixes.
    image_report = resolve_images(bpy, source.parent)
    used_image_names = set()
    visited_trees = set()
    def collect_used_images(tree):
        if tree is None or tree.as_pointer() in visited_trees:
            return
        visited_trees.add(tree.as_pointer())
        for node in tree.nodes:
            if node.type == "SCRIPT":
                raise RuntimeError("script_shader_is_not_allowed_in_source_proof")
            image = getattr(node, "image", None)
            if image:
                used_image_names.add(image.name)
            collect_used_images(getattr(node, "node_tree", None))
    for obj in selected_meshes:
        for slot in obj.material_slots:
            if slot.material:
                collect_used_images(slot.material.node_tree)
    missing_used = [entry["name"] for entry in image_report
                    if entry.get("file_present") is False and entry["name"] in used_image_names]
    if missing_used:
        raise RuntimeError("missing_original_material_images:" + ",".join(missing_used))
    audit = {
        "model": args.model, "blender_version": bpy.app.version_string,
        "source_filename": source.name, "source_sha256": source_hash,
        "selected_meshes": [{"name": o.name, "raw_vertices": len(o.data.vertices),
                             "materials": [s.material.name if s.material else None
                                           for s in o.material_slots]}
                            for o in selected_meshes],
        "rig": rig_info(rig), "images": image_report,
        "driver_and_animation_policy": removed_animation,
        "policy": {"embedded_text_executed": False, "automatic_python_execution": False,
                   "source_modified_on_disk": False, "uses_original_character_meshes": True},
        "renders": [], "checkpoint": "native-driver garment topology inspection",
        "garment_topology_file": "garment-topology.json",
        "limits": [
            "Native constraints/simple drivers retained; complex Python drivers muted; Actions/NLA detached.",
            "A rendered pose is visual evidence, not production GLB or animation acceptance.",
            "No 20-face variations or independent wardrobe geometry is asserted.",
            "No shape, neckline or garment modifications are silently performed by this baseline proof.",
        ],
    }
    write_json(destination / "render-proof.json", audit)
    scene = bpy.context.scene
    if scene is None:
        raise RuntimeError("source_has_no_active_scene")
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
    audit["linked_hidden_modifier_dependencies"] = sorted(set(linked_dependencies))
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.05
    scene.render.resolution_x = 640
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0.0
    world = bpy.data.worlds.new("AVATAR_PROOF_WORLD")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.10, 0.14, 0.17, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.45
    scene.world = world
    original_pose = {b.name: b.matrix_basis.copy() for b in rig.pose.bones}
    neutral_applied = apply_pose(rig, poses["neutral"])
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in selected_meshes:
        evaluated = obj.evaluated_get(depsgraph)
        points.extend(evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box)
    minimum = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    maximum = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    height = maximum.z - minimum.z
    if not math.isfinite(height) or height <= 0:
        raise RuntimeError("invalid_original_geometry_bounds")
    center = (minimum + maximum) * 0.5
    camera_data = bpy.data.cameras.new("AVATAR_PROOF_CAMERA")
    camera = bpy.data.objects.new("AVATAR_PROOF_CAMERA", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((height * 1.10, -height * 3.5, height * 0.13))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = height * 1.32
    camera.data.lens = 65
    camera.data.clip_end = max(100, height * 20)
    scene.camera = camera
    def light(name, offset, energy, size, color):
        data = bpy.data.lights.new(name, "AREA")
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = center + Vector(tuple(height * x for x in offset))
        obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()
        data.energy = energy * height * height
        data.shape = "DISK"
        data.size = size * height
        data.color = color
    light("KEY_SOFT", (-1.8, -2.6, 2.0), 320, 2.5, (1.0, 0.91, 0.82))
    light("FILL_SOFT", (2.1, -1.2, 0.9), 145, 2.5, (0.80, 0.89, 1.0))
    light("RIM_SOFT", (1.0, 1.9, 1.8), 240, 2.0, (0.86, 1.0, 0.97))
    # A neutral floor is the only new mesh; the character stays the real source.
    floor_mesh = bpy.data.meshes.new("AVATAR_PROOF_FLOOR")
    width = height * 10
    z = minimum.z - height * 0.008
    floor_mesh.from_pydata([
        (center.x - width, center.y - width, z),
        (center.x + width, center.y - width, z),
        (center.x + width, center.y + width, z),
        (center.x - width, center.y + width, z),
    ], [], [(0, 1, 2, 3)])
    floor_mesh.update()
    floor = bpy.data.objects.new("AVATAR_PROOF_FLOOR", floor_mesh)
    scene.collection.objects.link(floor)
    material = bpy.data.materials.new("AVATAR_PROOF_FLOOR")
    material.diffuse_color = (0.20, 0.27, 0.30, 1)
    material.use_nodes = True
    principal = material.node_tree.nodes.get("Principled BSDF")
    principal.inputs["Base Color"].default_value = (0.20, 0.27, 0.30, 1)
    principal.inputs["Roughness"].default_value = 0.82
    floor.data.materials.append(material)
    # These crops are actual new Blender renders. Their frames use evaluated
    # garment bounds; they are never anatomical mesh/edit selections.
    garment_evaluated = garment.evaluated_get(bpy.context.evaluated_depsgraph_get())
    garment_points = [garment_evaluated.matrix_world @ Vector(c)
                      for c in garment_evaluated.bound_box]
    garment_min = Vector(tuple(min(p[i] for p in garment_points) for i in range(3)))
    garment_max = Vector(tuple(max(p[i] for p in garment_points) for i in range(3)))
    garment_center = (garment_min + garment_max) * 0.5
    garment_height = garment_max.z - garment_min.z
    garment_width = garment_max.x - garment_min.x
    if garment_height <= 0 or garment_width <= 0:
        raise ValueError("invalid_evaluated_garment_bounds")
    topology["evaluated_bounds_for_camera_framing"] = {
        "minimum": coordinate(garment_min), "maximum": coordinate(garment_max),
        "method": "evaluated_object_bound_box",
        "raw_boundary_indices_not_mapped_to_evaluated_vertices": True,
    }
    def crop(name, zfraction, vertical_fraction, width_fraction, angle):
        target = garment_center.copy()
        target.z = garment_min.z + garment_height * zfraction
        vertical = garment_height * vertical_fraction
        horizontal = garment_width * width_fraction
        # Landscape ortho scale is horizontal; account for image aspect.
        scale = max(horizontal * 1.18, vertical * (640 / 480) * 1.18)
        return {"name": name, "kind": "crop", "target": target,
                "scale": scale, "angle": angle, "resolution": (640, 480),
                "framing": "garment evaluated bounds heuristic; label is camera region only"}
    shots = [
        {"name": "front", "kind": "full", "target": center,
         "scale": height * 1.32, "angle": 0, "resolution": (640, 800)},
        {"name": "threequarter", "kind": "full", "target": center,
         "scale": height * 1.32, "angle": 45, "resolution": (640, 800)},
        crop("neck-crop", 0.96, 0.45, 0.40, 0),
        crop("shoulder-crop", 0.83, 0.56, 1.05, 45),
        crop("hem-crop", 0.10, 0.35, 1.00, 0),
    ]
    for shot in shots:
        target = shot["target"]
        angle = math.radians(shot["angle"])
        camera.location = target + Vector((
            math.sin(angle) * height * 3.5,
            -math.cos(angle) * height * 3.5,
            height * (0.08 if shot["kind"] == "full" else 0.015)))
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = shot["scale"]
        scene.render.resolution_x, scene.render.resolution_y = shot["resolution"]
        scene.render.resolution_percentage = 100
        bpy.context.view_layer.update()
        path = destination / (args.model + "-" + shot["name"] + ".png")
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True, scene=scene.name)
        if not path.is_file():
            raise RuntimeError("render_output_missing")
        result = {"pose": "neutral", "view": shot["name"], "kind": shot["kind"],
                  "file": path.name, "png_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "bytes": path.stat().st_size, "resolution": list(shot["resolution"]),
                  "camera_target_world": coordinate(target), "camera_azimuth_degrees": shot["angle"],
                  "camera_ortho_scale": shot["scale"], "applied_source_bones": neutral_applied,
                  "framing": shot.get("framing", "whole original character")}
        audit["renders"].append(result)
        write_json(destination / "render-proof.json", audit)
        print("AVATAR_ACTUAL_RENDER " + json.dumps(result), flush=True)
        if args.emit_preview:
            image = bpy.data.images.load(str(path), check_existing=False)
            image.scale(320, 400) if shot["kind"] == "full" else image.scale(256, 192)
            preview = destination / (args.model + "-" + shot["name"] + "-preview.jpg")
            # PNG is already color managed; image.save avoids a second AgX.
            image.file_format = "JPEG"
            image.filepath_raw = str(preview)
            image.save()
            while preview.stat().st_size > 65536 and image.size[0] > 128:
                image.scale(max(128, int(image.size[0] * 0.8)),
                            max(96, int(image.size[1] * 0.8)))
                image.save()
            if preview.stat().st_size > 65536:
                raise ValueError("preview_byte_budget_exceeded")
            preview_dimensions = list(image.size)
            bpy.data.images.remove(image)
            print("AVATAR_ACTUAL_JPEG " + json.dumps({
                "model": args.model, "pose": "neutral", "view": shot["name"],
                "mime_type": "image/jpeg", "dimensions": preview_dimensions,
                "bytes": preview.stat().st_size,
                "base64": base64.b64encode(preview.read_bytes()).decode("ascii"),
            }), flush=True)
    geometry_after = garment_geometry_signature(garment)
    if geometry_after != geometry_before:
        raise RuntimeError("inspection_changed_raw_garment_geometry")
    topology["geometry_signature_after"] = geometry_after
    topology["raw_mesh_and_shape_key_coordinates_unchanged"] = True
    topology["render_state_after_evaluation"] = garment_render_state(garment)
    audit["driver_evaluation_status_after_render"] = driver_evaluation_status(bpy)
    audit["native_driver_policy_experiment"] = True
    audit["driver_policy_visually_accepted"] = False
    audit["garment_geometry_unchanged"] = True
    audit["garment_edits_performed"] = False
    write_json(destination / "garment-topology.json", topology)
    if args.save_working:
        working = destination / (args.model + "-proof-working.blend")
        bpy.ops.wm.save_as_mainfile(filepath=str(working), check_existing=False)
        audit["working_derivative"] = working.name
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError("immutable_source_changed")
    audit["source_hash_rechecked"] = True
    topology["source_hash_rechecked"] = True
    write_json(destination / "garment-topology.json", topology)
    write_json(destination / "render-proof.json", audit)
    print("AVATAR_SOURCE_PROOF_COMPLETE " + json.dumps({
        "model": args.model, "views": [r["view"] for r in audit["renders"]],
        "garment": garment.name, "raw_boundary_components": len(topology["boundary_components"]),
        "closed_boundary_loops": topology["closed_loop_count"],
        "garment_geometry_unchanged": True, "garment_edits_performed": False,
        "original_source_unchanged": True, "production_glb_approved": False,
    }), flush=True)

if __name__ == "__main__":
    main()
