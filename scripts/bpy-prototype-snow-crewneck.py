"""Bounded Snow neckline prototype on an immutable, hash-pinned original mesh.
Imports reviewed repository helpers only. No embedded Blender Text is executed.
A prototype image, not the coordinate guards, determines garment art acceptance.
"""
import argparse
import base64
import hashlib
import heapq
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import sys

SOURCE_SHA = "80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
HELPER_BLOB = "a64c4f14e977a6ae720fb57b01ffa9f69d5703f8"
EXPECTED_NECK_INDICES = [930,931,936,937,945,984,1569,1561,1560,1555,1554,1566,1565,1564,1563,1562,1589,1747,1748,1590,1568,1567,1559,1558,1557,1556,983,932,933,934,935,943,944,966,1341,1340,965,938,939,940,941,942]
EXPECTED_VERTICES, EXPECTED_KEYS = 1839, 10

def load_helper():
    path = Path(__file__).with_name("bpy-inspect-avatar-garments.py")
    raw = path.read_bytes()
    sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if sha != HELPER_BLOB:
        raise ValueError("reviewed_inspector_source_changed")
    spec = importlib.util.spec_from_file_location("reviewed_avatar_inspector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guard_manual_correspondence(obj):
    expected = {
        984: (0.0, -0.10321877896785736, 1.344225525856018),
        945: (0.005300186574459076, -0.10182908922433853, 1.3483264446258545),
        1569: (0.005300186574459076, -0.10182908922433853, 1.3483264446258545),
        966: (0.1389947235584259, 0.02442489191889763, 1.4307104349136353),
        1590: (0.1389947235584259, 0.02442489191889763, 1.4307104349136353),
    }
    actual, tolerance = {}, 1e-6
    for index, (absolute_x, y, z) in expected.items():
        point = obj.matrix_world @ obj.data.vertices[index].co
        if max(abs(abs(point.x) - absolute_x), abs(point.y - y), abs(point.z - z)) > tolerance:
            raise ValueError("manual_image_world_anchor_correspondence_mismatch")
        actual[index] = list(point)
    if actual[945][0] * actual[1569][0] >= 0 or actual[966][0] * actual[1590][0] >= 0:
        raise ValueError("manual_symmetric_anchor_pair_mismatch")
    return {"vertices_world": actual, "tolerance_world": tolerance,
            "front_negative_y": actual[984][1] < 0,
            "manual_reference": "Snow front image:984 center V,945/1569 symmetric neighbors,966/1590 high sides"}

def transform_snapshot(rig, objects):
    state = {
        "rig_world": [list(row) for row in rig.matrix_world],
        "object_world": {obj.name: [list(row) for row in obj.matrix_world] for obj in objects},
        "bone_matrix_basis": {b.name: [list(row) for row in b.matrix_basis] for b in rig.pose.bones},
    }
    return {"sha256": hashlib.sha256(json.dumps(state, separators=(",", ":"),
                                              allow_nan=False).encode()).hexdigest(),
            "bone_count": len(rig.pose.bones),
            "garment_and_rig_world": {obj.name: [list(row) for row in obj.matrix_world]
                                     for obj in [rig, *objects]}}

def driver_summary(records):
    return {"total": len(records), "muted": sum(r["muted"] for r in records),
            "active_invalid": sum(not r["muted"] and not r["is_valid"] for r in records),
            "active_native": sum(not r["muted"] and r["native_without_python"] for r in records),
            "invalid_records": [{"id_type": r["id_type"], "name": r["name"],
                                 "path": r["path"], "index": r["index"], "muted": r["muted"]}
                                for r in records if not r["is_valid"]]}


def preserved_signature(obj):
    mesh = obj.data
    payload = {
        "edges": [list(e.vertices) for e in mesh.edges],
        "polygons": [[p.material_index, *p.vertices] for p in mesh.polygons],
        "weights": [[[g.group, float(g.weight)] for g in v.groups] for v in mesh.vertices],
        "vertex_groups": [g.name for g in obj.vertex_groups],
        "uv_layers": [{"name": layer.name, "uv": [list(v.uv) for v in layer.data]}
                      for layer in mesh.uv_layers],
        "materials": [s.material.name if s.material else None for s in obj.material_slots],
    }
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"),
                                      allow_nan=False).encode()).hexdigest()

def ordered_front_arc(component, side_a, side_b, front):
    adjacent = {}
    for a, b in component["edges"]:
        adjacent.setdefault(a, set()).add(b)
        adjacent.setdefault(b, set()).add(a)
    if any(len(v) != 2 for v in adjacent.values()):
        raise ValueError("neck_boundary_is_not_single_cycle")
    candidates = []
    for following in sorted(adjacent[side_a]):
        path, previous, current = [side_a], side_a, following
        while current != side_b:
            if current in path:
                raise ValueError("neck_arc_did_not_reach_side_anchor")
            path.append(current)
            next_vertices = adjacent[current] - {previous}
            if len(next_vertices) != 1:
                raise ValueError("neck_arc_branch")
            previous, current = current, next(iter(next_vertices))
        path.append(side_b)
        candidates.append(path)
    matches = [path for path in candidates if front in path]
    if len(matches) != 1:
        raise ValueError("front_anchor_does_not_identify_unique_arc")
    return matches[0]

def plan_displacements(obj, component, settings):
    from mathutils import Vector
    coordinates = [obj.matrix_world @ v.co for v in obj.data.vertices]
    guard_manual_correspondence(obj)
    arc = ordered_front_arc(component, 966, 1590, 984)
    if coordinates[984].y >= 0:
        raise ValueError("reviewed_front_anchor_not_negative_y")
    graph = [[] for _ in coordinates]
    for edge in obj.data.edges:
        a, b = edge.vertices
        length = (coordinates[a] - coordinates[b]).length
        if not math.isfinite(length) or length <= 1e-10:
            raise ValueError("zero_or_nonfinite_raw_edge_length")
        graph[a].append((b, length))
        graph[b].append((a, length))
    cumulative = [0.0]
    for a, b in zip(arc, arc[1:]):
        cumulative.append(cumulative[-1] + (coordinates[a] - coordinates[b]).length)
    if cumulative[-1] <= 0:
        raise ValueError("zero_neck_arc_length")
    collar = set(component["vertex_indices"])
    pins = {index: 0.0 for index in collar}
    depth = settings["round_depth_world"]
    cap = settings["max_lift_world"]
    taper = settings["endpoint_taper_fraction"]
    for index, distance in zip(arc, cumulative):
        t = distance / cumulative[-1]
        side_z = coordinates[966].z * (1 - t) + coordinates[1590].z * t
        target_z = side_z - depth * math.sin(math.pi * t) ** 2
        edge_t = min(1.0, min(t, 1 - t) / taper)
        edge_weight = edge_t * edge_t * (3 - 2 * edge_t)
        pins[index] = min(cap, max(0.0, target_z - coordinates[index].z)) * edge_weight
    pins[966] = pins[1590] = 0.0
    if pins[984] <= 0 or max(pins.values()) > cap + 1e-12:
        raise ValueError("prototype_front_lift_not_in_reviewed_bounds")
    radius = settings["geodesic_radius_world"]
    distances = [math.inf] * len(graph)
    queue = []
    for index in collar:
        distances[index] = 0.0
        heapq.heappush(queue, (0.0, index))
    while queue:
        distance, index = heapq.heappop(queue)
        if distance != distances[index] or distance >= radius:
            continue
        for neighbor, length in graph[index]:
            candidate = distance + length
            if candidate <= radius and candidate < distances[neighbor]:
                distances[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor))
    support = {i for i, d in enumerate(distances) if d < radius}
    # Other real garment boundary loops and support perimeter stay fixed.
    for index in settings["_all_boundary_indices"]:
        if index not in collar:
            pins[index] = 0.0
    for index in support:
        if index not in collar and any(n not in support for n, _ in graph[index]):
            pins[index] = 0.0
    unknown = sorted(support - set(pins))
    values = [0.0] * len(graph)
    for index, value in pins.items():
        values[index] = value
    tolerance = settings["solver_tolerance_world"]
    max_change, iteration = math.inf, 0
    for iteration in range(1, settings["solver_max_iterations"] + 1):
        max_change = 0.0
        for index in unknown:
            weighted = [(values[n], 1.0 / length) for n, length in graph[index]]
            value = sum(v * w for v, w in weighted) / sum(w for _, w in weighted)
            max_change = max(max_change, abs(value - values[index]))
            values[index] = value
        if max_change <= tolerance:
            break
    if max_change > tolerance:
        raise ValueError("harmonic_solver_did_not_converge")
    if min(values) < -1e-12 or max(values) > cap + 1e-12:
        raise ValueError("harmonic_displacement_outside_bounds")
    inverse = obj.matrix_world.to_3x3().inverted()
    deltas = [inverse @ Vector((0, 0, value)) for value in values]
    return deltas, {
        "front_arc_indices": arc, "collar_pin_displacements_world_z": [
            {"index": i, "delta": pins[i]} for i in sorted(collar)],
        "affected_vertex_indices": [i for i, v in enumerate(values) if v > 1e-10],
        "support_vertex_count": len(support), "interior_vertex_count": len(unknown),
        "support_radius_world": radius, "max_displacement_world": max(values),
        "solver": "positive inverse-edge-length harmonic interpolation",
        "solver_iterations": iteration, "solver_last_max_change": max_change,
        "solver_tolerance": tolerance, "solver_converged": True,
        "fixed_side_anchors": [966, 1590], "front_anchor": 984,
        "correspondence": "manual front/side anchor correspondence supplied by reviewed source images",
    }

def apply_identical_deltas(obj, deltas, tolerance):
    from mathutils import Vector
    mesh = obj.data
    original_vertices = [v.co.copy() for v in mesh.vertices]
    keys = mesh.shape_keys.key_blocks
    original_keys = {k.name: [p.co.copy() for p in k.data] for k in keys}
    # Assign from snapshots, never +=: avoids double displacement if storage aliases.
    for vertex, original, delta in zip(mesh.vertices, original_vertices, deltas):
        vertex.co = original + delta
    for key in keys:
        for point, original, delta in zip(key.data, original_keys[key.name], deltas):
            point.co = original + delta
    mesh.update()
    basis = keys[0]
    residuals = []
    for key in keys:
        error = max(((point.co - basis.data[i].co) -
                     (original_keys[key.name][i] - original_keys[basis.name][i])).length
                    for i, point in enumerate(key.data))
        residuals.append({"key": key.name, "relative_to": basis.name,
                          "max_pair_offset_residual_local": error})
    assignment_error = max((v.co - (original_vertices[i] + deltas[i])).length
                           for i, v in enumerate(mesh.vertices))
    if max([r["max_pair_offset_residual_local"] for r in residuals] +
           [assignment_error]) > tolerance:
        raise ValueError("shape_key_identical_delta_residual_exceeded")
    return {"pair_key_delta_residuals": residuals,
            "max_raw_coordinate_assignment_error_local": assignment_error,
            "tolerance_local": tolerance}

def triangle_quality(obj, before, triangles):
    matrix = obj.matrix_world
    flipped, minimum_ratio, maximum_ratio = [], math.inf, 0.0
    for number, (a, b, c) in enumerate(triangles):
        p = [matrix @ before[i] for i in (a, b, c)]
        q = [matrix @ obj.data.vertices[i].co for i in (a, b, c)]
        old = (p[1] - p[0]).cross(p[2] - p[0])
        new = (q[1] - q[0]).cross(q[2] - q[0])
        if old.length <= 1e-12:
            continue
        ratio = new.length / old.length
        minimum_ratio, maximum_ratio = min(minimum_ratio, ratio), max(maximum_ratio, ratio)
        if new.length <= 1e-12 or old.dot(new) <= 0:
            flipped.append(number)
    report = {"checked_triangles": len(triangles), "flipped_or_collapsed_triangle_indices": flipped,
              "minimum_area_ratio": minimum_ratio, "maximum_area_ratio": maximum_ratio}
    if flipped:
        raise ValueError("prototype_has_flipped_or_collapsed_raw_triangles")
    return report

def validate_material_images(helper, bpy, selected_meshes, source):
    report = helper.resolve_images(bpy, source.parent)
    used, visited = set(), set()
    def visit(tree):
        if tree is None or tree.as_pointer() in visited:
            return
        visited.add(tree.as_pointer())
        for node in tree.nodes:
            if node.type == "SCRIPT":
                raise ValueError("script_shader_not_allowed")
            image = getattr(node, "image", None)
            if image:
                used.add(image.name)
            visit(getattr(node, "node_tree", None))
    for obj in selected_meshes:
        for slot in obj.material_slots:
            if slot.material:
                visit(slot.material.node_tree)
    if any(item.get("file_present") is False and item["name"] in used for item in report):
        raise ValueError("required_original_material_image_missing")
    return report

def prepare_scene(helper, bpy, selected_meshes, rig, config, audit):
    from mathutils import Vector
    apply_pose, poses = helper.apply_pose, config["poses"]
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

    return scene, camera, center, height

def render_phase(helper, bpy, destination, scene, camera, center, height,
                 shots, phase, audit, emit_preview):
    from mathutils import Vector
    for shot in shots:
        target, angle = shot["target"], math.radians(shot["angle"])
        camera.location = target + Vector((math.sin(angle) * height * 3.5,
            -math.cos(angle) * height * 3.5, height * 0.02))
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = shot["scale"]
        scene.render.resolution_x, scene.render.resolution_y = shot["resolution"]
        scene.render.resolution_percentage = 100
        bpy.context.view_layer.update()
        path = destination / ("snow-" + phase + "-" + shot["name"] + ".png")
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True, scene=scene.name)
        record = {"model": "snow", "phase": phase, "pose": "neutral",
                  "view": shot["name"], "file": path.name, "bytes": path.stat().st_size,
                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "resolution": list(shot["resolution"]), "camera_azimuth": shot["angle"],
                  "camera_target_world": list(target), "camera_ortho_scale": shot["scale"],
                  "same_camera_before_after": True}
        audit["renders"].append(record)
        helper.write_json(destination / "prototype-audit.json", audit)
        print("AVATAR_ACTUAL_RENDER " + json.dumps(record), flush=True)
        if emit_preview:
            image = bpy.data.images.load(str(path), check_existing=False)
            image.scale(256, 192) if shot["name"] == "neck-crop" else image.scale(320, 400)
            preview = path.with_name(path.stem + "-preview.jpg")
            image.file_format, image.filepath_raw = "JPEG", str(preview)
            image.save()
            while preview.stat().st_size > 65536 and image.size[0] > 128:
                image.scale(max(128, int(image.size[0] * 0.8)),
                            max(96, int(image.size[1] * 0.8)))
                image.save()
            if preview.stat().st_size > 65536:
                raise ValueError("preview_byte_budget_exceeded")
            dimensions = list(image.size)
            bpy.data.images.remove(image)
            print("AVATAR_ACTUAL_JPEG " + json.dumps({
                "model": "snow", "phase": phase, "pose": "neutral", "view": shot["name"],
                "mime_type": "image/jpeg", "dimensions": dimensions,
                "bytes": preview.stat().st_size,
                "base64": base64.b64encode(preview.read_bytes()).decode("ascii")}), flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default=str(
        Path(__file__).with_name("avatar-render-configs") / "snow-crewneck-prototype.json"))
    parser.add_argument("--emit-preview", action="store_true")
    args = parser.parse_args()
    import bpy
    from mathutils import Vector
    if sys.version_info[:2] != (3, 11) or tuple(bpy.app.version) != (4, 5, 9):
        raise ValueError("requires_verified_python_3_11_bpy_4_5_9")
    helper = load_helper()
    source = Path(args.blend).resolve(strict=True)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if original_hash != SOURCE_SHA:
        raise ValueError("frozen_original_snow_source_hash_mismatch")
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    settings = config["prototype"]
    if (config["model"] != "snow" or config["rig_name"] != "RIG-Snow"
            or config["poses"] != {"neutral": []}
            or settings["source_sha256"] != SOURCE_SHA
            or settings["vertex_count"] != EXPECTED_VERTICES
            or settings["shape_key_count"] != EXPECTED_KEYS
            or settings["neck_boundary_indices"] != EXPECTED_NECK_INDICES):
        raise ValueError("reviewed_prototype_config_mismatch")
    expected_settings = {"round_depth_world": 0.03, "max_lift_world": 0.065,
        "endpoint_taper_fraction": 0.18, "geodesic_radius_world": 0.075,
        "solver_max_iterations": 2500, "solver_tolerance_world": 1e-7,
        "shape_key_residual_tolerance_local": 1e-6}
    if any(settings.get(k) != value for k, value in expected_settings.items()):
        raise ValueError("reviewed_prototype_bounds_changed")
    destination = Path(args.out).resolve()
    if destination.is_relative_to(source.parents[3]) or source.is_relative_to(destination):
        raise ValueError("prototype_output_overlaps_original_source")
    destination.mkdir(parents=True, exist_ok=False)
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    policy = helper.disable_animation_and_scripts(bpy)
    rig = bpy.data.objects.get("RIG-Snow")
    if not rig or rig.type != "ARMATURE":
        raise ValueError("reviewed_snow_rig_missing")
    selected_meshes = []
    for name in config["mesh_names"]:
        obj = bpy.data.objects.get(name)
        if not obj or obj.type != "MESH":
            raise ValueError("reviewed_source_mesh_missing")
        selected_meshes.append(obj)
    garment = bpy.data.objects.get("GEO-snow-shirt")
    if (garment not in selected_meshes or len(garment.data.vertices) != EXPECTED_VERTICES
            or garment.data.shape_keys is None
            or len(garment.data.shape_keys.key_blocks) != EXPECTED_KEYS
            or any(len(k.data) != EXPECTED_VERTICES for k in garment.data.shape_keys.key_blocks)):
        raise ValueError("frozen_shirt_vertex_or_shape_key_count_mismatch")
    topology = helper.inspect_garment_boundaries(garment)
    matching = [c for c in topology["boundary_components"]
                if c["closed"] and set(c["vertex_indices"]) == set(EXPECTED_NECK_INDICES)]
    if len(matching) != 1:
        raise ValueError("exact_reviewed_neck_loop_not_found")
    component = matching[0]
    settings["_all_boundary_indices"] = sorted({
        index for c in topology["boundary_components"] for index in c["vertex_indices"]})
    correspondence = guard_manual_correspondence(garment)
    geometry_before = helper.garment_geometry_signature(garment)
    preserved_before = preserved_signature(garment)
    audit = {"model": "snow", "purpose": "Crewneck geometry prototype, not production acceptance",
        "source_filename": source.name, "source_sha256": original_hash,
        "helper_git_blob_sha1": HELPER_BLOB, "blender_version": bpy.app.version_string,
        "source_write_operations_performed": False, "automatic_python_execution": False,
        "embedded_text_executed": False, "driver_and_animation_policy": policy,
        "garment": garment.name, "geometry_before": geometry_before,
        "topology_before": topology, "render_state_before": helper.garment_render_state(garment),
        "manual_correspondence_guard": correspondence,
        "preserved_weights_uv_material_topology_sha256_before": preserved_before,
        "renders": [], "production_glb_approved": False, "animation_approved": False,
        "garment_art_approved": False, "native_driver_policy_visually_accepted": False,
        "limits": ["Only the exact manually matched neckline and geodesic nearby vertices move.",
                   "All original shape-key offsets are preserved; no new sleeve geometry exists.",
                   "Neutral CPU renders do not prove joint animation, GLB or eleven controls.",
                   "Original textures remain external; restore the source texture tree for reuse."]}
    audit["images"] = validate_material_images(helper, bpy, selected_meshes, source)
    scene, camera, center, height = prepare_scene(helper, bpy, selected_meshes, rig, config, audit)
    neck_world = [garment.matrix_world @ garment.data.vertices[i].co for i in EXPECTED_NECK_INDICES]
    neck_min = Vector(tuple(min(p[i] for p in neck_world) for i in range(3)))
    neck_max = Vector(tuple(max(p[i] for p in neck_world) for i in range(3)))
    neck_center = (neck_min + neck_max) * 0.5
    neck_center.z += 0.025
    shots = [
        {"name": "front", "target": center, "scale": height * 1.32,
         "angle": 0, "resolution": (640, 800)},
        {"name": "threequarter", "target": center, "scale": height * 1.32,
         "angle": 45, "resolution": (640, 800)},
        {"name": "neck-crop", "target": neck_center,
         "scale": max((neck_max.x - neck_min.x) * 1.5, 0.30),
         "angle": 0, "resolution": (640, 480)},
    ]
    audit["neck_world_bounds_before"] = {"minimum": list(neck_min), "maximum": list(neck_max)}
    audit["driver_status_before_render"] = helper.driver_evaluation_status(bpy)
    audit["driver_summary_before"] = driver_summary(audit["driver_status_before_render"])
    transform_before = transform_snapshot(rig, selected_meshes)
    audit["transform_snapshot_before"] = transform_before
    helper.write_json(destination / "prototype-audit.json", audit)
    render_phase(helper, bpy, destination, scene, camera, center, height, shots,
                 "before", audit, args.emit_preview)
    original_vertices = [v.co.copy() for v in garment.data.vertices]
    garment.data.calc_loop_triangles()
    triangles = [tuple(t.vertices) for t in garment.data.loop_triangles]
    deltas, plan = plan_displacements(garment, component, settings)
    audit["displacement_plan"] = plan
    audit["delta_application"] = apply_identical_deltas(
        garment, deltas, settings["shape_key_residual_tolerance_local"])
    audit["raw_triangle_quality_after"] = triangle_quality(garment, original_vertices, triangles)
    preserved_after = preserved_signature(garment)
    if preserved_after != preserved_before:
        raise ValueError("weights_uv_materials_or_topology_changed")
    audit["preserved_weights_uv_material_topology_sha256_after"] = preserved_after
    audit["geometry_after"] = helper.garment_geometry_signature(garment)
    audit["render_state_after"] = helper.garment_render_state(garment)
    audit["neck_world_vertices_after"] = [{"index": i, "world": list(
        garment.matrix_world @ garment.data.vertices[i].co)} for i in EXPECTED_NECK_INDICES]
    bpy.context.view_layer.update()
    render_phase(helper, bpy, destination, scene, camera, center, height, shots,
                 "after", audit, args.emit_preview)
    audit["driver_status_after_render"] = helper.driver_evaluation_status(bpy)
    audit["driver_summary_after"] = driver_summary(audit["driver_status_after_render"])
    transform_after = transform_snapshot(rig, selected_meshes)
    audit["transform_snapshot_after"] = transform_after
    audit["rig_and_selected_object_transforms_preserved"] = transform_before == transform_after
    working = destination / "snow-crewneck-prototype.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(working), check_existing=False)
    audit["derivative"] = {"file": working.name, "bytes": working.stat().st_size,
        "sha256": hashlib.sha256(working.read_bytes()).hexdigest(), "textures_packed": False}
    credits_root = source.parents[3]
    credit_records = []
    for relative in ("LICENSES.md", "rain/ATTRIBUTION.txt", "snow/ATTRIBUTION.txt"):
        credit_source = credits_root / relative
        output = destination / "credits" / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(credit_source, output)
        credit_records.append({"path": str(output.relative_to(destination)),
            "bytes": output.stat().st_size, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
    audit["credits"] = credit_records
    if hashlib.sha256(source.read_bytes()).hexdigest() != original_hash:
        raise ValueError("immutable_original_source_changed")
    audit["source_hash_rechecked"] = True
    audit["weights_uv_materials_topology_preserved"] = True
    helper.write_json(destination / "prototype-audit.json", audit)
    print("SNOW_CREWNECK_PROTOTYPE_COMPLETE " + json.dumps({
        "source_sha256": original_hash, "source_unchanged": True,
        "neck_indices": len(EXPECTED_NECK_INDICES), "vertex_count": EXPECTED_VERTICES,
        "shape_keys": EXPECTED_KEYS, "affected_vertices": len(plan["affected_vertex_indices"]),
        "maximum_lift_world": plan["max_displacement_world"],
        "renders": len(audit["renders"]), "garment_art_approved": False,
        "production_glb_approved": False, "animation_approved": False}), flush=True)

if __name__ == "__main__":
    main()
