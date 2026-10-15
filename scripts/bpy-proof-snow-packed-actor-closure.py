#!/usr/bin/env python3
"""Read-only closure of declared roots in one frozen packed Snow native derivative.
No original textures, original blend, native pose replay, saves, renders or model upload.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import sys
import traceback
from urllib.parse import urlsplit, urlunsplit

WRAPPER_BLOB = "05f0667f0096416d0368ff4399107db3b73c95f0"
WORKER_BLOB = "e3869adf226c957e8f2467fc23312cf09dd2eaa9"
CONFIG_BLOB = "f0612039b320e8dac77587ec4aecdc2c84618843"
BLEND_SHA = "fb75dbf2b1141b59d90296951941eb3849d2ddc7afa71326ac97f20bd9c6e0e4"
SNAPSHOT_SHA = "b213ebabbe6027c0c2e59df506d32d7fa15d05f9a0a6807b23100d8bc73fd98a"
INPUTS = {
    "snow-packed-used-textures-candidate.blend": (105085368, BLEND_SHA),
    "packed-textures-audit.json": (61385, "fea804a7f728f4870a6af4b56e0ea7f4d4baf194a6baac80ab6049d2a2962049"),
    "packed-reopen-audit.json": (10977, "79c93c459c2a1428ac44a252fdee7744320a8381dec0f8364ea66e5397e9d3ed"),
    "packed-reopen-expectations.json": (70147, "ba0d31b175ccbb5bffc3e65db3217b060727bd1a889df78fb69838d43821329a"),
    "packed-transport-manifest.json": (627, "808536aa936a76f620444af37bb5f5e333712f7c928c9d25a7508b0094bf8c13"),
    "credits/LICENSES.md": (1559, "21ffbcb7404ceeb59a8038da34ad28df24ee3f390d33f9c16bac04952cbab71c"),
    "credits/rain/ATTRIBUTION.txt": (292, "41d2a5693de42c5ee60dafaea599dfadd5a34ede8554a4d8a7c98af0cd008f24"),
    "credits/snow/ATTRIBUTION.txt": (292, "cf280b50c86fc5b1518643f4bb8be5befba91b29bdfeb5311ad3f98b65fddc9d"),
}
JSON_CAP = 1024*1024
ID_CAP = 4096
EDGE_CAP = 32768
NODE_CAP = 4096
PATH_CAP = 32768
ISSUE_CAP = 20
PACK_RUN = 38752917367
INTERNAL_TYPES = ("Mesh", "Armature", "Lattice", "Object", "Material", "Action", "Key",
                  "Collection", "World", "Camera", "Light", "NodeTree", "Scene")

# Additional exact-class source audits (data only; never loaded/executed from archives):
# root shader12 3e463047391ba9d9b67940a28638420878a149fb
# peer Geometry/Function+shader12 00843b400f2069fc04aac48c6e643d01d4244945
# weak provenance/LineStyle 059855e91ee3ad7017230a483399fdceae093700
# Weak eligibility: measured local/no override AND independently supported live dependency closure.
# LineStyle.use_texture is the positive RNA Boolean; no storage-flag inference or render pruning.

# Closed builtin node policy; unlisted types STOP instead of inferring path coverage.
NODE_SOURCE_REVISION = "8bf95cbd38d1456c94e9d751f3804eea4d5b137b"
NODE_POLICY = {
    "NodeFrame": [
        "intern/node_common.cc",
        "528-546",
        "structural"
    ],
    "NodeReroute": [
        "intern/node_common.cc",
        "550-597",
        "structural"
    ],
    "NodeGroupInput": [
        "intern/node_common.cc",
        "876-890",
        "structural"
    ],
    "NodeGroupOutput": [
        "intern/node_common.cc",
        "923-939",
        "structural"
    ],
    "ShaderNodeGroup": [
        "shader/node_shader_tree.cc + intern/node_common.cc",
        "183-184;451-494",
        "node_group_id"
    ],
    "ShaderNodeTexImage": [
        "shader/nodes/node_shader_tex_image.cc",
        "18-49;93-106;281-293",
        "verified_image_id"
    ],
    "ShaderNodeTexEnvironment": [
        "shader/nodes/node_shader_tex_environment.cc",
        "18-49;106-107;190-204",
        "verified_image_id"
    ],
    "ShaderNodeBsdfPrincipled": [
        "shader/nodes/node_shader_bsdf_principled.cc",
        "16-314;701-714",
        "scalar_vector_shader"
    ],
    "ShaderNodeOutputMaterial": [
        "shader/nodes/node_shader_output_material.cc",
        "9-27;81-91",
        "shader_output"
    ],
    "ShaderNodeNormalMap": [
        "shader/nodes/node_shader_normal_map.cc",
        "21-32;58-70;196-210",
        "scalar_vector_shader"
    ],
    "ShaderNodeMath": [
        "shader/nodes/node_shader_math.cc",
        "24-71;364-378",
        "scalar_vector_shader"
    ],
    "ShaderNodeVectorMath": [
        "shader/nodes/node_shader_vector_math.cc",
        "26-77;570-585",
        "scalar_vector_shader"
    ],
    "ShaderNodeMixRGB": [
        "shader/nodes/node_shader_mix_rgb.cc",
        "17-26;161-170",
        "scalar_vector_shader"
    ],
    "ShaderNodeMix": [
        "shader/nodes/node_shader_mix.cc",
        "28-91;617-633",
        "scalar_vector_shader"
    ],
    "ShaderNodeRGB": [
        "shader/nodes/node_shader_rgb.cc",
        "16-20;57-64",
        "scalar_vector_shader"
    ],
    "ShaderNodeValue": [
        "shader/nodes/node_shader_value.cc",
        "16-21;67-75",
        "scalar_vector_shader"
    ],
    "ShaderNodeTexCoord": [
        "shader/nodes/node_shader_tex_coord.cc",
        "14-37;109-119",
        "object_id_coordinates"
    ],
    "ShaderNodeMapping": [
        "shader/nodes/node_shader_mapping.cc",
        "16-32;124-133",
        "scalar_vector_shader"
    ],
    "ShaderNodeBackground": [
        "shader/nodes/node_shader_background.cc",
        "9-18;42-51",
        "shader_output"
    ],
    "ShaderNodeOutputWorld": [
        "shader/nodes/node_shader_output_world.cc",
        "9-17;42-51",
        "shader_output"
    ],
    "ShaderNodeAddShader": [
        "shader/nodes/node_shader_add_shader.cc",
        "9-23;55-70",
        "shader_values"
    ],
    "ShaderNodeAttribute": [
        "shader/nodes/node_shader_attribute.cc",
        "16-22;37-86;102-121",
        "internal_named_attribute"
    ],
    "ShaderNodeBsdfAnisotropic": [
        "shader/nodes/node_shader_bsdf_glossy.cc",
        "12-40;42-57;92-116",
        "shader_values"
    ],
    "ShaderNodeBsdfRefraction": [
        "shader/nodes/node_shader_bsdf_refraction.cc",
        "9-40;69-89",
        "shader_values"
    ],
    "ShaderNodeBsdfTransparent": [
        "shader/nodes/node_shader_bsdf_transparent.cc",
        "11-28;55-73",
        "shader_values"
    ],
    "ShaderNodeEmission": [
        "shader/nodes/node_shader_emission.cc",
        "9-29;49-65",
        "shader_values"
    ],
    "ShaderNodeInvert": [
        "shader/nodes/node_shader_invert.cc",
        "13-34;48-63",
        "shader_values"
    ],
    "ShaderNodeLightPath": [
        "shader/nodes/node_shader_light_path.cc",
        "9-34;55-72",
        "internal_shading_context"
    ],
    "ShaderNodeMixShader": [
        "shader/nodes/node_shader_mix_shader.cc",
        "9-31;62-77",
        "shader_values"
    ],
    "ShaderNodeNewGeometry": [
        "shader/nodes/node_shader_geometry.cc",
        "9-59;88-103",
        "internal_shading_geometry"
    ],
    "ShaderNodeTangent": [
        "shader/nodes/node_shader_tangent.cc",
        "19-22;51-84;98-118",
        "internal_named_uv"
    ],
    "ShaderNodeUVMap": [
        "shader/nodes/node_shader_uvmap.cc",
        "21-24;49-73;89-110",
        "internal_named_uv"
    ],
    "FunctionNodeBooleanMath": [
        "function/nodes/node_fn_boolean_math.cc",
        "23-29;178-205",
        "audited_internal_field_or_value"
    ],
    "FunctionNodeCompare": [
        "function/nodes/node_fn_compare.cc",
        "29-58;736-754",
        "audited_internal_field_or_value"
    ],
    "GeometryNodeInputEdgeSmooth": [
        "geometry/nodes/node_geo_input_edge_smooth.cc",
        "9-18;20-33",
        "audited_internal_field_or_value"
    ],
    "GeometryNodeInputMeshEdgeAngle": [
        "geometry/nodes/node_geo_input_mesh_edge_angle.cc",
        "15-29;217-229",
        "audited_internal_field_or_value"
    ],
    "GeometryNodeInputShadeSmooth": [
        "geometry/nodes/node_geo_input_face_smooth.cc",
        "9-18;20-33",
        "audited_internal_field_or_value"
    ],
    "GeometryNodeSetShadeSmooth": [
        "geometry/nodes/node_geo_set_shade_smooth.cc",
        "18-37;112-131",
        "audited_internal_field_or_value"
    ],
    "ShaderNodeValToRGB": [
        "shader/nodes/node_shader_color_ramp.cc",
        "22-40;159-179",
        "audited_internal_field_or_value"
    ],
    "ShaderNodeRGBCurve": [
        "shader/nodes/node_shader_curves.cc",
        "159-180;299-318",
        "audited_internal_field_or_value"
    ],
    "ShaderNodeSeparateColor": [
        "shader/nodes/node_shader_sepcomb_color.cc",
        "25-65;96-115",
        "audited_internal_field_or_value"
    ],
    "ShaderNodeVectorRotate": [
        "shader/nodes/node_shader_vector_rotate.cc",
        "25-45;265-283",
        "audited_internal_field_or_value"
    ],
    "ShaderNodeVectorTransform": [
        "shader/nodes/node_shader_vector_transform.cc",
        "17-43;201-221",
        "audited_internal_field_or_value"
    ],
    "ShaderNodeMapRange": [
        "shader/nodes/node_shader_map_range.cc",
        "32-49;521-543",
        "audited_internal_field_or_value"
    ]
}

def require(condition, code):
    if not condition:
        raise ValueError("actor_closure_"+code)

def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)+"\n").encode("utf-8")

def sha(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()

def git_blob(path):
    raw = Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def clean(value, limit=192):
    return "".join(c if c.isprintable() else " " for c in str(value))[:limit]

def write_json(path, value):
    raw = encoded(value)
    require(len(raw) <= JSON_CAP, "report_budget")
    Path(path).write_bytes(raw)

def load_module(filename, expected_blob, module_name):
    path = Path(__file__).with_name(filename)
    require(path.is_file() and not path.is_symlink() and git_blob(path) == expected_blob, "module_pin")
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, "module_spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def verify_inputs(root):
    checkpoint = root/"checkpoint"
    manifest_path = root/"restore-manifest.json"
    require(checkpoint.is_dir() and not checkpoint.is_symlink()
            and manifest_path.is_file() and not manifest_path.is_symlink()
            and manifest_path.stat().st_size <= JSON_CAP, "restore_layout")
    require(not manifest_path.stat().st_mode & 0o222, "restore_manifest_readonly")
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get("schema_version") == 1 and manifest.get("ok") is True
            and manifest.get("purpose") == "frozen_packed_actor_closure_input"
            and manifest.get("joined_verified") is True and manifest.get("readonly") is True
            and manifest.get("archive_files_executed") is False, "restore_manifest")
    rows = manifest.get("files")
    require(isinstance(rows, list) and len(rows) == 8, "restore_file_count")
    actual = {}
    for row in rows:
        require(isinstance(row, dict) and row.get("file") in INPUTS
                and row["file"] not in actual, "restore_file_identity")
        actual[row["file"]] = (row.get("bytes"), row.get("sha256"))
    require(actual == INPUTS, "restore_manifest_pins")
    components = manifest.get("components")
    require(isinstance(components, list) and len(components) == 3
            and all(row.get("run_id") == PACK_RUN and row.get("all_archive_crcs_verified") is True
                    for row in components), "restore_component_provenance")
    observed = {}
    for name, (size, checksum) in INPUTS.items():
        path = checkpoint/name
        require(path.is_file() and not path.is_symlink()
                and path.resolve(strict=True).is_relative_to(checkpoint)
                and stat.S_ISREG(path.stat().st_mode) and not path.stat().st_mode & 0o222
                and path.stat().st_size == size and sha(path) == checksum, "frozen_input_pin")
        observed[name] = {"bytes": size, "sha256": checksum, "readonly": True}
    files = {p.relative_to(checkpoint).as_posix() for p in checkpoint.rglob("*") if p.is_file()}
    require(files == set(INPUTS), "checkpoint_inventory")
    return {"files": observed, "restore_manifest_sha256": sha(manifest_path),
            "all_eight_inputs_readonly_and_sha_verified": True}

def prior_proof(checkpoint):
    parent = json.loads((checkpoint/"packed-textures-audit.json").read_text())
    child = json.loads((checkpoint/"packed-reopen-audit.json").read_text())
    transport = json.loads((checkpoint/"packed-transport-manifest.json").read_text())
    require(all(parent.get(key) is True for key in ("candidate_complete", "packed_used_textures_verified",
            "reopen_verified", "all_68_original_hashes_unchanged", "input_files_unchanged",
            "retention_metadata_restored")), "producer_parent_flags")
    require(parent["derivative"]["sha256"] == BLEND_SHA
            and parent["derivative"]["bytes"] == INPUTS["snow-packed-used-textures-candidate.blend"][0]
            and transport["sha256"] == BLEND_SHA and transport["same_job_join_sha256_verified"] is True,
            "producer_blend_identity")
    require(child.get("passed") is True and child.get("snapshot_stable_before_and_after_decode") is True
            and child.get("reference_values_passed_before_and_after_decode") is True
            and child["blend_sha256_before"] == child["blend_sha256_after"] == BLEND_SHA
            and child["retention_policy_readback"]["passed"] is True, "producer_child_flags")
    return {"run_id": PACK_RUN, "packed_native_readback_inherited": True,
            "original_68_and_b223_provenance_inherited_not_rechecked": True}

def build_graph(bpy, config, expected):
    users = bpy.data.user_map()  # Unfiltered reverse map: dependency -> using owner IDs.
    require(isinstance(users, dict), "user_map_schema")
    all_ids = set(users)
    edge_count = 0
    for dependency, owners in users.items():
        require(isinstance(dependency, bpy.types.ID) and isinstance(owners, set), "user_map_entry")
        all_ids.update(owners)
        edge_count += len(owners)
    require(len(all_ids) <= ID_CAP and edge_count <= EDGE_CAP, "graph_budget")
    require(all(isinstance(item, bpy.types.ID) for item in all_ids), "user_map_non_id")
    labels = {}
    for item in all_ids:
        if not item.is_embedded_data:
            labels[item] = item.bl_rna.identifier+":"+item.name_full
    # Private embedded objects are inspected by their actual containing ID route.
    for owner in sorted(labels, key=lambda item: labels[item]):
        for route in ("node_tree", "collection"):
            if route == "collection" and not isinstance(owner, bpy.types.Scene):
                continue
            child = getattr(owner, route, None)
            if isinstance(child, bpy.types.ID) and child.is_embedded_data:
                label = labels[owner]+"::"+route
                if child not in labels or label < labels[child]:
                    labels[child] = label
    require(all(item in labels for item in all_ids)
            and len(set(labels.values())) == len(labels), "graph_stable_id_labels")
    require(all(len(label) <= 256 for label in labels.values()), "id_label_budget")
    dependencies = {item: set() for item in all_ids}
    for dependency, owners in users.items():
        for owner in owners:
            dependencies[owner].add(dependency)
    scene = bpy.context.scene
    rig = bpy.data.objects.get(config["rig_name"])
    require(scene is not None and rig is not None and rig.type == "ARMATURE", "graph_core_roots")
    mesh_roots = [bpy.data.objects.get(name) for name in config["mesh_names"]]
    require(len(mesh_roots) == 17 and all(obj is not None and obj.type == "MESH" for obj in mesh_roots),
            "graph_mesh_roots")
    actions = [bpy.data.actions.get(name) for name in expected["action_names"]]
    require(len(actions) == 59 and all(action is not None for action in actions), "graph_action_roots")
    retained = bpy.data.objects.get("GEO-snow-eye_anim")
    require(retained is not None, "graph_preservation_root")
    roots = set((scene, rig, retained, *mesh_roots, *actions))
    require(roots <= all_ids, "roots_missing_from_user_map")
    queue = sorted(roots, key=lambda item: labels[item])
    parents = {item: None for item in roots}
    reached = set(roots)
    for owner in queue:
        for dependency in sorted(dependencies[owner], key=lambda item: labels[item]):
            if dependency not in reached:
                reached.add(dependency)
                parents[dependency] = owner
                queue.append(dependency)
    # Add actual private embedded IDs for resource inspection, not fake-user count edges.
    inspected = set(reached)
    embedded_parent = {}
    for owner in sorted(reached, key=lambda item: labels[item]):
        for route in ("node_tree", "collection"):
            if route == "collection" and not isinstance(owner, bpy.types.Scene):
                continue
            child = getattr(owner, route, None)
            if isinstance(child, bpy.types.ID) and child.is_embedded_data:
                require(child in labels, "embedded_label_missing")
                inspected.add(child)
                embedded_parent[child] = owner
    require(len(inspected) <= ID_CAP, "inspection_id_budget")
    def chain(item):
        ids = []
        current = item
        seen = set()
        while current is not None and current not in seen:
            seen.add(current)
            ids.append(labels[current])
            current = embedded_parent.get(current, parents.get(current))
        ids.reverse()
        return {"ids": ids if len(ids) <= 32 else ids[:16]+ids[-16:],
                "depth": len(ids), "truncated": len(ids) > 32}
    summary = {"unfiltered_id_count": len(all_ids), "unfiltered_edge_count": edge_count,
               "declared_root_count": len(roots), "declared_roots": sorted(labels[item] for item in roots),
               "reachable_main_id_count": len(reached), "private_embedded_inspection_count": len(inspected-reached),
               "inspected_id_count": len(inspected), "outside_root_scope_count": len(all_ids-reached),
               "reachable_id_identity_sha256": hashlib.sha256(encoded(sorted(labels[item] for item in inspected))).hexdigest(),
               "outside_scope_sample": sorted(labels[item] for item in all_ids-reached)[:20],
               "eye_anim_is_explicit_preservation_root": True,
               "all_59_actions_are_explicit_roots": True, "fake_user_counts_used_as_edges": False}
    resource_dependencies = {owner: set(dependencies.get(owner, set())) for owner in inspected}
    for child, owner in embedded_parent.items():
        resource_dependencies[owner].add(child)
    require(all(target in inspected for targets in resource_dependencies.values() for target in targets),
            "resource_dependency_outside_closure")
    return inspected, labels, chain, summary, resource_dependencies


def id_label(item, labels):
    return labels.get(item, item.bl_rna.identifier+":"+item.name_full) if item is not None else None

def resource_metadata_state(bpy, ids, labels, dependencies):
    """Read metadata only: no weak target path resolution, append, decode or mutation."""
    weak_rows, style_rows = [], []
    for owner in sorted(ids, key=lambda item: labels[item]):
        weak = owner.library_weak_reference
        if weak is not None:
            filepath, id_name = weak.filepath, weak.id_name
            require(isinstance(filepath, str) and len(filepath) <= 4096
                    and isinstance(id_name, str) and len(id_name) <= 1024,
                    "weak_metadata_text_budget")
            weak_rows.append({"owner": labels[owner], "owner_type": owner.bl_rna.identifier,
                "filepath": filepath, "id_name": id_name,
                "local": owner.library is None, "no_override": owner.override_library is None})
        if isinstance(owner, bpy.types.FreestyleLineStyle):
            require(type(owner.use_nodes) is bool and type(owner.use_texture) is bool,
                    "freestyle_boolean_metadata")
            textures = []
            for slot in owner.texture_slots:
                if slot is not None and slot.texture is not None:
                    textures.append(id_label(slot.texture, labels))
            style_rows.append({"owner": labels[owner], "local": owner.library is None,
                "no_override": owner.override_library is None, "use_nodes": owner.use_nodes,
                "use_texture": owner.use_texture, "node_tree": id_label(owner.node_tree, labels),
                "texture_slot_ids": textures,
                "outgoing_ids": sorted(id_label(item, labels)
                                       for item in dependencies.get(owner, set()))})
    return {"weak": weak_rows, "freestyle": style_rows}

def redacted_text(value, limit=512):
    raw = str(value)
    redacted = raw
    if "://" in raw:
        parts = urlsplit(raw)
        redacted = urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))
    return {"text": clean(redacted, limit), "length": len(redacted),
            "truncated": len(redacted) > limit, "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "url_credentials_query_fragment_redacted": redacted != raw}

def bounded_issue_representatives(groups):
    """Fair per-code examples; counts never depend on retained details."""
    details, used = [], 0
    for index in range(3):
        for code in sorted(groups):
            if index >= len(groups[code]):
                continue
            row = groups[code][index]
            size = len(encoded(row))
            if used+size <= 128*1024 and len(details) < 60:
                details.append(row)
                used += size
    return details, used


def audit_resources(bpy, ids, labels, chain, expected, dependencies, metadata):
    issue_count, issue_counts, owner_type_counts = 0, {}, {}
    owners_by_type, bad_owners, issue_groups = {}, set(), {}
    unknown_node_types, unknown_node_details, node_type_counts = {}, [], {}
    output_paths = {}
    checked = {"verified_packed_image_ids": 0, "nodes": 0, "modifiers": 0,
               "registered_nonempty_paths": 0, "registered_output_paths": 0,
               "registered_verified_packed_image_paths": 0, "freestyle_line_styles": 0}
    expected_images = {row["name"] for row in expected["images"]}
    image_paths = {row["name"]: {row["missing_pattern"], *(f["missing_path"] for f in row["files"])}
                   for row in expected["images"]}
    supported_owners = set()
    freestyle_records = []
    def issue(owner, code, location, path=None):
        nonlocal issue_count
        issue_count += 1
        require(issue_count <= 131072, "observation_budget")
        issue_counts[code] = issue_counts.get(code, 0)+1
        typename = owner.bl_rna.identifier
        owner_type_counts[typename] = owner_type_counts.get(typename, 0)+1
        owners_by_type.setdefault(typename, set()).add(owner)
        bad_owners.add(owner)
        rows = issue_groups.setdefault(code, [])
        if len(rows) < 3:
            row = {"owner": labels[owner], "owner_type": typename, "code": code,
                   "location": clean(location, 256), "root_chain": chain(owner)}
            if path is not None:
                row["resource_path"] = redacted_text(path)
            rows.append(row)
    def output(owner, path):
        if isinstance(path, str) and path:
            require(len(path) <= 4096, "path_text_budget")
            output_paths.setdefault(owner, set()).add(path)
            if owner.is_embedded_data:
                containing = labels[owner].split("::", 1)[0]
                for candidate in ids:
                    if labels[candidate] == containing:
                        output_paths.setdefault(candidate, set()).add(path)
    def inspect_paths(owner, item, location, output_fields=()):
        for prop in item.bl_rna.properties:
            if prop.type == "STRING" and prop.subtype in ("FILE_PATH", "DIR_PATH"):
                value = getattr(item, prop.identifier)
                if not value:
                    continue
                require(isinstance(value, str) and len(value) <= 4096, "path_text_budget")
                if prop.identifier in output_fields:
                    output(owner, value)
                else:
                    issue(owner, "unclassified_nonempty_input_path", location+"."+prop.identifier, value)
    def point_cache(owner, cache, location):
        if cache is None:
            return
        flags = [bool(getattr(cache, name, False)) for name in ("is_baked", "use_disk_cache", "use_external")]
        if any(flags) or getattr(cache, "filepath", ""):
            issue(owner, "point_cache_input_unsupported", location, getattr(cache, "filepath", ""))
    internal = tuple(getattr(bpy.types, name) for name in INTERNAL_TYPES)
    inspected_trees = set()
    style_by_name = {row["owner"]: row for row in metadata["freestyle"]}
    for owner in sorted(ids, key=lambda item: labels[item]):
        local = owner.library is None and owner.override_library is None
        if not local:
            issue(owner, "linked_or_override_dependency", "ID.library/override_library",
                  owner.library.filepath if owner.library is not None else None)
        if isinstance(owner, bpy.types.Image):
            if owner.name not in expected_images:
                issue(owner, "extra_reachable_image_not_in_packed_proof", "Image", owner.filepath_raw)
            else:
                checked["verified_packed_image_ids"] += 1
                supported_owners.add(owner)
            continue
        if isinstance(owner, bpy.types.FreestyleLineStyle):
            checked["freestyle_line_styles"] += 1
            supported_owners.add(owner)
            facts = style_by_name[labels[owner]]
            outgoing = dependencies.get(owner, set())
            counts = {}
            for item in outgoing:
                key = item.bl_rna.identifier
                counts[key] = counts.get(key, 0)+1
            for slot in owner.texture_slots:
                if slot is not None and slot.texture is not None and slot.texture not in ids:
                    issue(owner, "freestyle_texture_reference_outside_graph", "FreestyleLineStyle.texture_slots")
            if owner.node_tree is not None and owner.node_tree not in ids:
                issue(owner, "freestyle_node_tree_outside_graph", "FreestyleLineStyle.node_tree")
            freestyle_records.append({**facts, "root_chain": chain(owner),
                "outgoing_dependency_type_counts": dict(sorted(counts.items())),
                "all_dependencies_must_independently_pass": True,
                "disabled_render_or_texture_flags_do_not_prune_dependencies": True})
        elif isinstance(owner, internal):
            supported_owners.add(owner)
        else:
            issue(owner, "unsupported_reachable_id_type", owner.bl_rna.identifier)
            continue
        inspect_paths(owner, owner, owner.bl_rna.identifier)
        if isinstance(owner, bpy.types.Scene):
            inspect_paths(owner, owner.render, "Scene.render", ("filepath",))
            if owner.sequence_editor is not None:
                issue(owner, "sequence_editor_resource_inspection_unsupported", "Scene.sequence_editor")
            if owner.rigidbody_world is not None:
                point_cache(owner, owner.rigidbody_world.point_cache, "Scene.rigidbody_world.point_cache")
        if isinstance(owner, bpy.types.Object):
            if len(owner.particle_systems):
                issue(owner, "particle_system_resources_unsupported", "Object.particle_systems")
            for modifier in owner.modifiers:
                checked["modifiers"] += 1
                require(checked["modifiers"] <= EDGE_CAP, "modifier_budget")
                location = "Object.modifiers["+clean(modifier.name, 96)+"]"
                inspect_paths(owner, modifier, location)
                if getattr(modifier, "cache_file", None) is not None:
                    issue(owner, "modifier_cache_file_unsupported", location)
                point_cache(owner, getattr(modifier, "point_cache", None), location+".point_cache")
                if modifier.type in ("FLUID", "DYNAMIC_PAINT", "OCEAN", "MESH_CACHE", "MESH_SEQUENCE_CACHE"):
                    issue(owner, "modifier_external_resource_family_unsupported", location+"."+modifier.type)
                if modifier.type == "NODES" and len(modifier.bakes):
                    issue(owner, "geometry_nodes_bakes_unsupported", location+".bakes")
        if isinstance(owner, bpy.types.NodeTree) and owner not in inspected_trees:
            inspected_trees.add(owner)
            for node in owner.nodes:
                checked["nodes"] += 1
                require(checked["nodes"] <= NODE_CAP, "node_budget")
                location = "NodeTree.nodes["+clean(node.name, 96)+"]"
                typename = str(node.bl_idname)
                require(len(typename) <= 128 and (len(node_type_counts) < 256 or typename in node_type_counts),
                        "node_type_budget")
                node_type_counts[typename] = node_type_counts.get(typename, 0)+1
                if typename not in NODE_POLICY or node.bl_rna.identifier != typename:
                    unknown_node_types[typename] = unknown_node_types.get(typename, 0)+1
                    if len(unknown_node_details) < ISSUE_CAP:
                        unknown_node_details.append({"node_type": typename, "owner": labels[owner],
                            "location": location, "root_chain": chain(owner)})
                    issue(owner, "unsupported_node_type", location+"."+typename)
                    continue
                if typename in ("ShaderNodeTexImage", "ShaderNodeTexEnvironment"):
                    image = node.image
                    if image is not None and (image not in ids or image.name not in expected_images):
                        issue(owner, "image_node_reference_not_in_verified_packed_closure", location)
                if typename == "ShaderNodeGroup":
                    group = node.node_tree
                    if group is not None and group not in ids:
                        issue(owner, "shader_group_reference_outside_id_graph", location)
                if typename == "ShaderNodeTexCoord":
                    obj = node.object
                    if obj is not None and obj not in ids:
                        issue(owner, "coordinate_object_reference_outside_id_graph", location)
                # Exact audited builtins only. Their values/attributes are metadata; no execute call.
                inspect_paths(owner, node, location)
                for socket in node.inputs:
                    inspect_paths(owner, socket, location+".inputs["+clean(socket.identifier, 96)+"]")
    # Supplementary registered BKE_bpath inputs deliberately skip packed/weak paths.
    mapped = bpy.data.file_path_map(subset=set(ids), include_libraries=True)
    require(isinstance(mapped, dict), "file_path_map_schema")
    for owner, paths in mapped.items():
        require(owner in ids and isinstance(paths, set), "file_path_map_owner")
        for path in sorted(paths):
            if not path:
                continue
            checked["registered_nonempty_paths"] += 1
            require(checked["registered_nonempty_paths"] <= PATH_CAP
                    and isinstance(path, str) and len(path) <= 4096, "registered_path_budget")
            if isinstance(owner, bpy.types.Image) and path in image_paths.get(owner.name, set()):
                checked["registered_verified_packed_image_paths"] += 1
            elif path in output_paths.get(owner, set()):
                checked["registered_output_paths"] += 1
            else:
                issue(owner, "registered_external_input_unclassified", "file_path_map", path)
    # Weak references are append provenance only if the owner's actual live closure is supported.
    # The state includes BOTH readonly fields; id_name is not a filesystem path.
    live_bad_owners = set(bad_owners)
    def live_closure_passed(owner):
        seen, pending = set(), [owner]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            require(len(seen) <= ID_CAP, "live_closure_budget")
            if current not in supported_owners or current in live_bad_owners:
                return False
            pending.extend(dependencies.get(current, set())-seen)
        return True
    weak_records, weak_counts, weak_type_counts = [], {}, {}
    for row in metadata["weak"]:
        owner = next(item for item in ids if labels[item] == row["owner"])
        own_live_passed = live_closure_passed(owner)
        eligible = row["local"] and row["no_override"] and own_live_passed
        classification = "append_origin_metadata" if eligible else "unclassified_owner_resource"
        weak_counts[classification] = weak_counts.get(classification, 0)+1
        typename = row["owner_type"]
        weak_type_counts[typename] = weak_type_counts.get(typename, 0)+1
        if not eligible:
            issue(owner, "weak_owner_resources_unclassified", "ID.library_weak_reference")
        weak_records.append({"owner": row["owner"], "owner_type": typename, "root_chain": chain(owner),
            "local": row["local"], "no_override": row["no_override"],
            "own_live_resource_closure_passed": own_live_passed, "classification": classification,
            "filepath": redacted_text(row["filepath"]), "id_name": redacted_text(row["id_name"], 256),
            "id_name_is_not_filesystem_input": True, "original_target_resolved_or_opened": False,
            "metadata_sha256": hashlib.sha256(encoded(row)).hexdigest()})
    require(len(encoded(weak_records)) <= 512*1024, "weak_record_budget")
    for row in freestyle_records:
        owner = next(item for item in ids if labels[item] == row["owner"])
        row["live_resource_closure_passed"] = live_closure_passed(owner)
    details, detail_bytes = bounded_issue_representatives(issue_groups)
    require(sum(issue_counts.values()) == issue_count and sum(owner_type_counts.values()) == issue_count,
            "issue_aggregate_consistency")
    return {"passed": issue_count == 0, "unsupported_count": issue_count,
            "issue_counts_by_code": dict(sorted(issue_counts.items())),
            "issue_counts_by_owner_type": dict(sorted(owner_type_counts.items())),
            "unique_unsupported_owner_count": len(bad_owners),
            "unique_unsupported_owners_by_type": {key: len(value) for key, value in sorted(owners_by_type.items())},
            "unsupported_details": details, "unsupported_details_omitted": issue_count-len(details),
            "representative_policy": {"per_code": 3, "maximum": 60, "byte_budget": 128*1024,
                                      "actual_bytes": detail_bytes, "full_counts_never_trimmed": True},
            "weak_reference_count": len(weak_records), "weak_classification_counts": dict(sorted(weak_counts.items())),
            "weak_owner_type_counts": dict(sorted(weak_type_counts.items())), "weak_records": weak_records,
            "weak_fields_never_resolved_opened_or_mutated": True,
            "weak_metadata_before_after_hash_required": True,
            "freestyle_records": freestyle_records, "checked": checked,
            "all_node_type_counts": dict(sorted(node_type_counts.items())),
            "unknown_node_type_counts": dict(sorted(unknown_node_types.items())),
            "unknown_node_details": unknown_node_details,
            "node_policy_source_revision": NODE_SOURCE_REVISION, "closed_node_policy": NODE_POLICY,
            "resource_policy": "Exact44auditednodes; verified22packedImages; local append-origin metadata; dependency-checked LineStyle; unknown inputs STOP",
            "id_cap": ID_CAP, "edge_cap": EDGE_CAP, "file_path_map_is_supplementary": True,
            "file_path_map_fixed_skip_packed_and_weak_not_used_as_absence_proof": True,
            "full_scene_portable": False, "whole_file_portable": False}

def failure_record(error, stage):
    code = error.args[0] if isinstance(error, ValueError) and len(error.args) == 1 else None
    if not (isinstance(code, str) and len(code) <= 180
            and code.startswith(("actor_closure_", "packed_native_", "packed_reopen_"))
            and all(c.isascii() and (c.isalnum() or c == "_") for c in code)):
        code = None
    return {"stage": stage, "error_type": type(error).__name__, "error_code": code,
            "frames": [{"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
                       for frame in traceback.extract_tb(error.__traceback__)[-6:]]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.input_root).resolve(strict=True)
    out = Path(args.out).resolve()
    require(not out.is_relative_to(root) and not root.is_relative_to(out), "output_input_overlap")
    out.mkdir(parents=True, exist_ok=True)
    audit_path = out/"packed-actor-closure-audit.json"
    require(not audit_path.exists(), "audit_already_exists")
    audit = {"purpose": "Read-only dependency/resource closure of fixed saved Snow actor/preservation roots",
             "used_actor_external_closure_passed": False, "saved_packed_native_readback_passed": False,
             "full_scene_portable": False, "art_approved": False, "glb_pbr_approved": False,
             "browser_animation_approved": False, "native_pose_replay": False, "models_saved": 0,
             "original_assets_restored": False, "model_payload_reuploaded": False,
             "unsupported_resource_decode_or_relink_requested": False}
    before = None
    source_pins = {}
    stage = "inputs"
    failure = None
    native_passed = False
    resources = None
    try:
        before = verify_inputs(root)
        checkpoint = root/"checkpoint"
        audit["frozen_inputs_before"] = before
        audit["inherited_proof"] = prior_proof(checkpoint)
        for name in INPUTS:
            if name.endswith(".blend"):
                continue
            destination = out/(name if name.startswith("credits/") else "metadata/"+name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checkpoint/name, destination)
        shutil.copyfile(root/"restore-manifest.json", out/"metadata/restore-manifest.json")
        stage = "pinned_modules"
        wrapper = load_module("bpy-pack-snow-used-textures.py", WRAPPER_BLOB, "closure_packed_wrapper")
        worker = load_module("bpy-verify-snow-packed-textures.py", WORKER_BLOB, "closure_packed_worker")
        config_path = Path(__file__).with_name("avatar-render-configs")/"snow-crewneck-prototype.json"
        require(git_blob(config_path) == CONFIG_BLOB, "config_pin")
        config = json.loads(config_path.read_text())
        modules = wrapper.load_modules()
        base, native, natural, face, proof, soft, pair, helper = modules
        source_paths = {Path(__file__).resolve(), Path(wrapper.__file__).resolve(),
                        Path(worker.__file__).resolve(), config_path.resolve(),
                        Path("bpy-proof/bpy-runtime.json").resolve()}
        source_paths.update(Path(module.__file__).resolve() for module in modules)
        source_paths.update(Path(__file__).with_name(name).resolve()
                            for name in ("bpy-proof-snow-bent-elbows.py", "bpy-prototype-snow-crewneck.py"))
        source_pins = {str(path): sha(path) for path in source_paths}
        expected = worker.load_expected(checkpoint/"packed-reopen-expectations.json",
                                       INPUTS["packed-reopen-expectations.json"][1])
        require(expected["snapshot_sha256"] == SNAPSHOT_SHA and expected["blend_sha256"] == BLEND_SHA,
                "frozen_native_expected_identity")
        stage = "runtime"
        import bpy
        bpy.context.preferences.filepaths.use_scripts_auto_execute = False
        wrapper.validate_runtime(bpy)
        stage = "fresh_open"
        opened = bpy.ops.wm.open_mainfile(filepath=str(checkpoint/"snow-packed-used-textures-candidate.blend"),
                                        load_ui=False, use_scripts=False)
        require("FINISHED" in opened and not bpy.context.preferences.filepaths.use_scripts_auto_execute,
                "open_policy")
        wrapper.validate_runtime(bpy)
        rig = bpy.data.objects.get("RIG-Snow")
        require(rig is not None and rig.type == "ARMATURE", "native_rig")
        audit["saved_binding"] = wrapper.binding_state(bpy, rig)
        require(audit["saved_binding"] == expected["saved_binding"] == expected["reference_binding"],
                "saved_idle_zero_binding")
        audit["reference_binding"] = wrapper.bind_reference(bpy, native, rig)
        require(audit["reference_binding"] == expected["reference_binding"], "native_reference_binding")
        audit["retention_before"] = worker.verify_retained_object(bpy, expected["retention_policy"])
        stage = "native_before"
        first = wrapper.capture_state(bpy, modules, rig, expected["action_names"])
        require(first == expected["snapshot"] and wrapper.digest(first) == SNAPSHOT_SHA,
                "native_snapshot_before")
        audit["native_before"] = {"snapshot_sha256": wrapper.digest(first), "driver_status": first["driver_status"]}
        audit["numeric_before"] = wrapper.compare_values(wrapper.numeric_values(bpy, modules, rig),
                                                        expected["reference_values"])
        require(audit["numeric_before"]["passed"] is True, "native_values_before")
        stage = "packed_decode"
        images = wrapper.used_images(bpy, pair)
        packed = wrapper.packed_state(bpy, images, expected["images"], Path(expected["missing_root"]), decode=True)
        require(packed["all_passed"] is True and packed["images"] == 22 and packed["packed_entries"] == 30
                and packed["decoded_file_buffers"] == 18 and packed["decoded_tile_buffers"] == 12,
                "packed_decode_coverage")
        audit["packed_readback"] = packed
        stage = "dependency_graph"
        ids, labels, chain, graph, resource_dependencies = build_graph(bpy, config, expected)
        audit["dependency_graph"] = graph
        require(graph["declared_root_count"] == 79 and graph["unfiltered_id_count"] == 339
                and graph["unfiltered_edge_count"] == 361 and graph["inspected_id_count"] == 256
                and graph["reachable_id_identity_sha256"] == "658cf75b210d7a99735565862f77f895e07cd0c58e6149eddd4d7a2a047fd4a2",
                "fixed_actor_graph_identity")
        stage = "resource_metadata_before"
        resource_metadata_before = resource_metadata_state(bpy, ids, labels, resource_dependencies)
        metadata_hash_before = hashlib.sha256(encoded(resource_metadata_before)).hexdigest()
        audit["resource_metadata_before"] = {"sha256": metadata_hash_before,
            "weak_reference_count": len(resource_metadata_before["weak"]),
            "freestyle_count": len(resource_metadata_before["freestyle"])}
        stage = "resources"
        resources = audit_resources(bpy, ids, labels, chain, expected,
                                    resource_dependencies, resource_metadata_before)
        audit["resource_closure"] = resources
        stage = "native_after"
        final = wrapper.capture_state(bpy, modules, rig, expected["action_names"])
        require(final == first and wrapper.digest(final) == SNAPSHOT_SHA, "native_snapshot_after")
        audit["numeric_after"] = wrapper.compare_values(wrapper.numeric_values(bpy, modules, rig),
                                                       expected["reference_values"])
        require(audit["numeric_after"]["passed"] is True, "native_values_after")
        audit["retention_after"] = worker.verify_retained_object(bpy, expected["retention_policy"])
        require(wrapper.binding_state(bpy, rig) == expected["reference_binding"]
                and not bpy.context.preferences.filepaths.use_scripts_auto_execute, "native_policy_after")
        audit["native_after"] = {"snapshot_sha256": wrapper.digest(final), "driver_status": final["driver_status"]}
        stage = "resource_metadata_after"
        resource_metadata_after = resource_metadata_state(bpy, ids, labels, resource_dependencies)
        audit["resource_metadata_after"] = {"sha256": hashlib.sha256(encoded(resource_metadata_after)).hexdigest(),
            "weak_reference_count": len(resource_metadata_after["weak"]),
            "freestyle_count": len(resource_metadata_after["freestyle"])}
        require(resource_metadata_after == resource_metadata_before
                and audit["resource_metadata_after"]["sha256"] == metadata_hash_before,
                "readonly_resource_metadata_changed")
        audit["resource_metadata_unchanged"] = True
        native_passed = True
    except Exception as error:
        failure = failure_record(error, stage)
        audit["failure"] = failure
    finally:
        try:
            after = verify_inputs(root)
            audit["frozen_inputs_after"] = after
            audit["all_eight_inputs_and_manifest_unchanged"] = before is not None and after == before
            audit["reviewed_code_and_runtime_unchanged"] = bool(source_pins) and all(
                Path(path).is_file() and sha(path) == checksum for path, checksum in source_pins.items())
            hashes_passed = audit["all_eight_inputs_and_manifest_unchanged"] and audit["reviewed_code_and_runtime_unchanged"]
        except Exception as error:
            audit["hash_recheck_failure"] = failure_record(error, "input_hash_recheck")
            hashes_passed = False
        audit["saved_packed_native_readback_passed"] = bool(native_passed and hashes_passed and failure is None)
        audit["used_actor_external_closure_passed"] = bool(native_passed and hashes_passed
            and failure is None and resources is not None and resources["passed"])
        write_json(audit_path, audit)
        summary = {key: audit.get(key) for key in ("purpose", "used_actor_external_closure_passed",
            "saved_packed_native_readback_passed", "failure", "hash_recheck_failure",
            "all_eight_inputs_and_manifest_unchanged", "reviewed_code_and_runtime_unchanged",
            "full_scene_portable", "art_approved", "glb_pbr_approved", "browser_animation_approved",
            "models_saved", "original_assets_restored", "model_payload_reuploaded")}
        if resources is not None:
            summary["resource_closure"] = {key: resources[key] for key in
                ("passed", "unsupported_count", "unsupported_details_omitted", "issue_counts_by_code",
                 "issue_counts_by_owner_type", "weak_reference_count", "weak_classification_counts",
                 "unknown_node_type_counts", "checked")}
        require(len(encoded(summary)) <= 24*1024, "stdout_budget")
        print("SNOW_PACKED_ACTOR_CLOSURE "+encoded(summary).decode("utf-8").strip(), flush=True)
    return 0 if audit["used_actor_external_closure_passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
