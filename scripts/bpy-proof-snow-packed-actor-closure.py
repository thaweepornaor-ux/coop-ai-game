#!/usr/bin/env python3
"""Read-only fixed Snow source-cage surface plan with locked resource/native prerequisites.
No original textures, original blend, native pose replay, saves, renders or model upload.
"""
import argparse
import hashlib
import importlib.util
import json
import math
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

# Narrow inert Text/numeric Palette source audit ef34c680315ea4ee2f6ae931ebadad3bfe0f692f
# Text.is_modified/reload/as_module/run/import are deliberately NEVER called.
# Empty SequenceEditor source audit c173bdf9ce4f74c11d35e3ba596cdd63e47c536f
# No measured next-candidate Text/Palette/editor values or runtime acceptance inferred.
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


def saved_text_buffer_state(text):
    line_count = len(text.lines)
    require(line_count <= 32768, "text_line_budget")
    digest, count = hashlib.sha256(), 0
    for line in text.lines:
        data = line.body.encode("utf-8")
        count += len(data)
        require(count <= 1024*1024, "text_buffer_byte_budget")
        digest.update(len(data).to_bytes(8, "little"))
        digest.update(data)
    return {"line_count": line_count, "utf8_body_bytes": count,
            "saved_buffer_sha256": digest.hexdigest(),
            "hash_format": "saved line bodies UTF8; each prefixed by uint64 little-endian byte length",
            "script_body_logged": False, "text_executed_or_imported": False}


def resource_metadata_state(bpy, ids, labels, dependencies):
    """Read metadata only: no weak target path resolution, append, decode or mutation."""
    weak_rows, style_rows, text_rows, palette_rows, sequence_rows = [], [], [], [], []
    total_text_bytes = 0
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

        if isinstance(owner, bpy.types.Text):
            require(isinstance(owner.filepath, str) and len(owner.filepath) <= 4096
                    and type(owner.is_in_memory) is bool and type(owner.use_module) is bool,
                    "text_metadata_schema")
            saved = saved_text_buffer_state(owner)
            total_text_bytes += saved["utf8_body_bytes"]
            require(total_text_bytes <= 2*1024*1024, "total_text_buffer_budget")
            text_rows.append({"owner": labels[owner], "name": owner.name_full,
                "local": owner.library is None, "no_override": owner.override_library is None,
                "filepath": owner.filepath, "is_in_memory": owner.is_in_memory,
                "use_module": owner.use_module, "use_fake_user": owner.use_fake_user, **saved})
        if isinstance(owner, bpy.types.Palette):
            require(len(owner.colors) <= 4096, "palette_color_budget")
            values = []
            for color in owner.colors:
                value = [float(component) for component in color.color]
                value.extend((float(color.strength), float(color.weight)))
                require(len(value) == 5 and all(math.isfinite(number) for number in value),
                        "palette_numeric_data")
                values.append(value)
            palette_rows.append({"owner": labels[owner], "local": owner.library is None,
                "no_override": owner.override_library is None, "color_count": len(values),
                "numeric_values_finite": True, "numeric_data_sha256": hashlib.sha256(encoded(values)).hexdigest(),
                "use_fake_user": owner.use_fake_user, "colors_edited_or_applied": False})
        if isinstance(owner, bpy.types.Scene):
            editor = owner.sequence_editor
            row = {"owner": labels[owner], "editor_present": editor is not None}
            if editor is not None:
                require(len(editor.strips) <= 4096 and len(editor.meta_stack) <= 4096
                        and isinstance(editor.proxy_dir, str) and len(editor.proxy_dir) <= 4096,
                        "sequence_editor_metadata_budget")
                top = [{"name": strip.name, "type": strip.type} for strip in editor.strips]
                row.update({"top_level_count": len(top), "top_level_identity_sha256": hashlib.sha256(encoded(top)).hexdigest(),
                    "top_level_type_counts": {kind: sum(value["type"] == kind for value in top)
                                             for kind in sorted({value["type"] for value in top})},
                    "top_level_sample": top[:20], "meta_stack_count": len(editor.meta_stack),
                    "active_strip": editor.active_strip.name if editor.active_strip is not None else None,
                    "proxy_dir": editor.proxy_dir,
                    "recursive_empty_proved_from_top_level": len(top) == 0,
                    "recursive_collection_walked": False})
            sequence_rows.append(row)
    return {"schema_version": 2, "weak": weak_rows, "freestyle": style_rows,
            "texts": text_rows, "palettes": palette_rows, "sequencers": sequence_rows}

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
    freestyle_records, text_records, palette_records, sequence_records = [], [], [], []
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
    text_by_name = {row["owner"]: row for row in metadata["texts"]}
    palette_by_name = {row["owner"]: row for row in metadata["palettes"]}
    sequence_by_name = {row["owner"]: row for row in metadata["sequencers"]}
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
        if isinstance(owner, bpy.types.Text):
            facts = text_by_name[labels[owner]]
            accepted = (local and owner.name in {"cloudrig.py", "snow_post_generation.py"}
                        and facts["filepath"] == "" and facts["is_in_memory"] is True)
            text_records.append({**{key: value for key, value in facts.items() if key != "filepath"},
                "filepath": redacted_text(facts["filepath"]), "root_chain": chain(owner),
                "stored_inert_internal_text_data": accepted,
                "saved_module_request_preserved_not_executed": True,
                "script_behavior_or_execution_dependencies_approved": False})
            if accepted:
                supported_owners.add(owner)
            else:
                issue(owner, "unsupported_text_storage_or_identity", "Text.filepath/is_in_memory", facts["filepath"])
            continue
        if isinstance(owner, bpy.types.Palette):
            facts = palette_by_name[labels[owner]]
            palette_records.append({**facts, "root_chain": chain(owner),
                                    "internal_numeric_data_only": local})
            if local:
                supported_owners.add(owner)
            # Generic nested-ID dependencies remain in the unchanged graph.
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
            facts = sequence_by_name[labels[owner]]
            accepted = (not facts["editor_present"] or (
                facts["top_level_count"] == 0 and facts["meta_stack_count"] == 0
                and facts["active_strip"] is None and facts["proxy_dir"] == ""))
            sequence_records.append({**{key: value for key, value in facts.items() if key != "proxy_dir"},
                "proxy_dir": redacted_text(facts.get("proxy_dir", "")),
                "empty_editor_structural_data_only": accepted, "root_chain": chain(owner),
                "editor_created_cleared_or_media_opened": False})
            if not accepted:
                issue(owner, "nonempty_or_unclassified_sequence_editor", "Scene.sequence_editor", facts.get("proxy_dir", ""))
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
            "freestyle_records": freestyle_records, "inert_text_records": text_records,
            "palette_records": palette_records, "sequence_editor_records": sequence_records,
            "text_execution_or_future_script_dependencies_approved": False, "checked": checked,
            "all_node_type_counts": dict(sorted(node_type_counts.items())),
            "unknown_node_type_counts": dict(sorted(unknown_node_types.items())),
            "unknown_node_details": unknown_node_details,
            "node_policy_source_revision": NODE_SOURCE_REVISION, "closed_node_policy": NODE_POLICY,
            "resource_policy": "Exact44nodes; packed22Images; local append metadata; checked LineStyle; exact2inert Text buffers; numeric Palette; strictly empty editor; unknown inputs STOP",
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


# Source-cage planning, not evaluated geometry, PBR mapping, or renderer approval.
SURFACE_MODIFIER_FIELDS = {
    "ARMATURE": [
        "object",
        "use_bone_envelopes",
        "use_vertex_groups",
        "use_deform_preserve_volume",
        "use_multi_modifier",
        "vertex_group",
        "invert_vertex_group"
    ],
    "SUBSURF": [
        "subdivision_type",
        "levels",
        "render_levels",
        "show_only_control_edges",
        "use_creases",
        "use_custom_normals",
        "use_limit_surface",
        "uv_smooth",
        "quality",
        "boundary_smooth"
    ],
    "MASK": [
        "mode",
        "armature",
        "vertex_group",
        "invert_vertex_group",
        "use_smooth",
        "threshold"
    ],
    "SMOOTH": [
        "use_x",
        "use_y",
        "use_z",
        "factor",
        "iterations",
        "vertex_group",
        "invert_vertex_group"
    ],
    "CORRECTIVE_SMOOTH": [
        "factor",
        "iterations",
        "scale",
        "rest_source",
        "smooth_type",
        "invert_vertex_group",
        "vertex_group",
        "is_bind",
        "use_only_smooth",
        "use_pin_boundary"
    ],
    "LATTICE": [
        "object",
        "vertex_group",
        "invert_vertex_group",
        "strength"
    ],
    "SOLIDIFY": [
        "solidify_mode",
        "thickness",
        "thickness_clamp",
        "use_thickness_angle_clamp",
        "thickness_vertex_group",
        "offset",
        "edge_crease_inner",
        "edge_crease_outer",
        "edge_crease_rim",
        "material_offset",
        "material_offset_rim",
        "vertex_group",
        "shell_vertex_group",
        "rim_vertex_group",
        "use_rim",
        "use_even_offset",
        "use_quality_normals",
        "invert_vertex_group",
        "use_flat_faces",
        "use_flip_normals",
        "use_rim_only",
        "nonmanifold_thickness_mode",
        "nonmanifold_boundary_mode",
        "nonmanifold_merge_threshold",
        "bevel_convex"
    ],
    "SHRINKWRAP": [
        "wrap_method",
        "wrap_mode",
        "cull_face",
        "target",
        "auxiliary_target",
        "vertex_group",
        "offset",
        "project_limit",
        "use_project_x",
        "use_project_y",
        "use_project_z",
        "subsurf_levels",
        "use_negative_direction",
        "use_positive_direction",
        "use_invert_cull",
        "invert_vertex_group"
    ],
    "WEIGHTED_NORMAL": [
        "weight",
        "mode",
        "thresh",
        "keep_sharp",
        "vertex_group",
        "invert_vertex_group",
        "use_face_influence"
    ],
    "NORMAL_EDIT": [
        "mode",
        "mix_mode",
        "mix_factor",
        "mix_limit",
        "no_polynors_fix",
        "vertex_group",
        "invert_vertex_group",
        "target",
        "use_direction_parallel"
    ],
    "MIRROR": [
        "use_axis",
        "use_bisect_axis",
        "use_bisect_flip_axis",
        "use_clip",
        "use_mirror_vertex_groups",
        "use_mirror_merge",
        "use_mirror_u",
        "use_mirror_v",
        "use_mirror_udim",
        "mirror_offset_u",
        "mirror_offset_v",
        "offset_u",
        "offset_v",
        "merge_threshold",
        "bisect_threshold",
        "mirror_object"
    ],
    "CAST": [
        "cast_type",
        "object",
        "invert_vertex_group",
        "use_x",
        "use_y",
        "use_z",
        "use_radius_as_size",
        "use_transform",
        "factor",
        "radius",
        "size",
        "vertex_group"
    ],
    "MESH_DEFORM": [
        "object",
        "is_bound",
        "invert_vertex_group",
        "vertex_group",
        "precision",
        "use_dynamic_bind"
    ],
    "SURFACE_DEFORM": [
        "target",
        "falloff",
        "is_bound",
        "vertex_group",
        "invert_vertex_group",
        "use_sparse_bind",
        "strength"
    ]
}
SURFACE_MATERIAL_FIELDS = ("use_nodes", "diffuse_color", "specular_color", "specular_intensity",
    "roughness", "metallic", "surface_render_method", "displacement_method", "alpha_threshold",
    "use_transparency_overlap", "use_backface_culling", "use_backface_culling_shadow",
    "use_backface_culling_lightprobe_volume", "use_transparent_shadow", "thickness_mode",
    "use_thickness_from_shadow", "volume_intersection_method", "max_vertex_displacement", "pass_index")

def surface_value(bpy, value, labels, depth=0):
    require(depth <= 8, "surface_value_depth")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        require(-(2**63) <= value < 2**63, "surface_integer_range")
        return value
    if isinstance(value, float):
        require(math.isfinite(value), "surface_nonfinite_numeric")
        return value
    if isinstance(value, str):
        require(len(value) <= 4096, "surface_string_budget")
        return value
    if isinstance(value, bpy.types.ID):
        require(value in labels and value.library is None and value.override_library is None,
                "surface_id_outside_supported_closure")
        return {"id": labels[value]}
    if isinstance(value, (set, frozenset)):
        require(len(value) <= 64 and all(isinstance(v, str) for v in value), "surface_enum_set")
        return sorted(surface_value(bpy, v, labels, depth+1) for v in value)
    kind = type(value).__name__
    if isinstance(value, (list, tuple)) or kind in ("bpy_prop_array", "Vector", "Color", "Euler",
            "Quaternion", "Matrix", "IDPropertyArray"):
        require(len(value) <= 64, "surface_array_budget")
        return [surface_value(bpy, v, labels, depth+1) for v in value]
    if kind == "IDPropertyGroup" or isinstance(value, dict):
        keys = sorted(value.keys())
        require(len(keys) <= 256 and all(isinstance(k, str) for k in keys), "surface_idproperty_keys")
        return {surface_value(bpy, k, labels, depth+1):
                surface_value(bpy, value[k], labels, depth+1) for k in keys}
    raise ValueError("surface_value_type_unsupported:"+kind[:96])

def surface_fields(bpy, value, fields, labels):
    return {name: surface_value(bpy, getattr(value, name), labels) for name in fields}

def surface_stream_digest(rows):
    digest, count = hashlib.sha256(), 0
    for row in rows:
        data = encoded(row)
        digest.update(len(data).to_bytes(8, "little"))
        digest.update(data)
        count += 1
    return {"count": count, "sha256": digest.hexdigest(),
            "format": "ordered canonical JSON rows; uint64LE length then UTF8 JSON bytes"}

def surface_modifier(bpy, modifier, labels, groups):
    row = {"name": modifier.name, "type": modifier.type,
           "flags": surface_fields(bpy, modifier,
               ("show_viewport", "show_render", "show_in_editmode", "show_on_cage"), labels)}
    if modifier.type == "NODES":
        require(modifier.node_group is not None, "surface_geometry_group_missing")
        groups.add(modifier.node_group)
        row["settings"] = surface_fields(bpy, modifier,
            ("node_group", "bake_directory", "bake_target"), labels)
        require(len(modifier.bakes) == 0, "surface_geometry_bakes_unsupported")
        row["bake_count"] = 0
        # Registered NodesModifier settings IDProperty map; never execute or update the node group.
        row["instance_settings"] = surface_value(bpy,
            {key: modifier[key] for key in sorted(modifier.keys())}, labels)
        row["source_parameter_capture_supported"] = True
        return row
    if modifier.type == "DATA_TRANSFER":
        row["settings"] = {"object": surface_value(bpy, modifier.object, labels)}
        row["source_parameter_capture_supported"] = False
        row["unsupported_reason"] = "Dynamic layer enum labels may evaluate source meshes and use active-object context; selectors not read."
        row["unread_selector_fields"] = ["layers_vgroup_select_src", "layers_vcol_vert_select_src",
            "layers_vcol_loop_select_src", "layers_uv_select_src", "layers_vgroup_select_dst",
            "layers_vcol_vert_select_dst", "layers_vcol_loop_select_dst", "layers_uv_select_dst"]
        row["other_settings_not_captured"] = True
        return row
    if modifier.type not in SURFACE_MODIFIER_FIELDS:
        row["source_parameter_capture_supported"] = False
        row["unsupported_reason"] = "Modifier type has no complete source-backed public-parameter serializer."
        return row
    row["settings"] = surface_fields(bpy, modifier, SURFACE_MODIFIER_FIELDS[modifier.type], labels)
    row["source_parameter_capture_supported"] = True
    return row

def surface_mesh(bpy, obj, rig, labels, materials, groups):
    mesh = obj.data
    require(obj.type == "MESH" and obj.mode == "OBJECT" and not mesh.is_editmode,
            "surface_source_mesh_mode")
    require(obj in labels and mesh in labels, "surface_mesh_identity")
    require(mesh.library is None and mesh.override_library is None, "surface_linked_mesh")
    require(len(obj.material_slots) <= 64 and len(mesh.uv_layers) <= 16
            and len(obj.modifiers) <= 64 and len(mesh.attributes) <= 128,
            "surface_mesh_collection_budget")
    row = {"object": labels[obj], "data": labels[mesh], "source_cage_only": True,
           "final_evaluated_surface_approved": False, "mode": obj.mode,
           "vertices": len(mesh.vertices), "edges": len(mesh.edges), "loops": len(mesh.loops),
           "polygons": len(mesh.polygons), "shape_key_blocks": len(mesh.shape_keys.key_blocks)
                 if mesh.shape_keys else 0,
           "matrix_world": surface_value(bpy, obj.matrix_world, labels),
           "hide_viewport": bool(obj.hide_viewport), "hide_render": bool(obj.hide_render),
           "data_materials": [surface_value(bpy, material, labels) for material in mesh.materials]}
    for material in mesh.materials:
        if material is not None:
            materials.add(material)
    slots = []
    for index, slot in enumerate(obj.material_slots):
        require(slot.slot_index == index and slot.link in ("OBJECT", "DATA"),
                "surface_material_slot_identity")
        material = slot.material
        if material is not None:
            materials.add(material)
        slots.append({"index": index, "link": slot.link, "name": slot.name,
                      "resolved_material": surface_value(bpy, material, labels)})
    row["material_slots"] = slots
    counts = {}
    bad = []
    for polygon in mesh.polygons:
        index = int(polygon.material_index)
        counts[str(index)] = counts.get(str(index), 0)+1
        if index < 0 or index >= max(1, len(slots)):
            bad.append(int(polygon.index))
    row["polygon_material_index_counts"] = counts
    row["unassigned_index_zero_faces_without_slots"] = counts.get("0",0) if not slots else 0
    row["out_of_range_material_indices"] = {"count": len(bad), "first20_polygon_indices": bad[:20]}
    require(not bad, "surface_polygon_material_index_out_of_range")
    row["source_positions"] = surface_stream_digest(
        surface_value(bpy, vertex.co, labels) for vertex in mesh.vertices)
    row["source_topology"] = surface_stream_digest(
        [int(p.index), list(p.vertices), int(p.loop_start), int(p.loop_total),
         int(p.material_index), bool(p.use_smooth)] for p in mesh.polygons)
    row["source_edges"] = surface_stream_digest(list(e.vertices) for e in mesh.edges)
    group_names = {group.index: group.name for group in obj.vertex_groups}
    deform = {bone.name for bone in rig.data.bones if bone.use_deform}
    maximum, zero, positive = 0, 0, 0
    def weight_rows():
        nonlocal maximum, zero, positive
        for vertex in mesh.vertices:
            memberships = []
            eligible = 0
            for group in vertex.groups:
                require(group.group in group_names and math.isfinite(group.weight)
                        and group.weight >= 0, "surface_raw_weight_membership")
                name = group_names[group.group]
                memberships.append([int(group.group), name, float(group.weight)])
                if group.weight > 0 and name in deform:
                    eligible += 1
            maximum = max(maximum, eligible)
            zero += int(eligible == 0)
            positive += int(eligible > 0)
            yield [int(vertex.index), memberships]
    weight_digest = surface_stream_digest(weight_rows())
    row["source_vertex_groups"] = [{"index":g.index, "name":g.name} for g in obj.vertex_groups]
    row["source_weights"] = {"memberships":weight_digest,
        "max_positive_use_deform_bone_groups":maximum,
        "vertices_without_positive_use_deform_group":zero,
        "vertices_with_positive_use_deform_group":positive,
        "scope":"raw source memberships only; not new pre-Armature or evaluated weight proof",
        "weights_changed_or_truncated":False}
    uv_rows = []
    for index, layer in enumerate(mesh.uv_layers):
        require(len(layer.uv) == len(mesh.loops), "surface_uv_corner_count")
        low, high, cells = [None,None], [None,None], {}
        def uv_values():
            for item in layer.uv:
                uv = surface_value(bpy, item.vector, labels)
                require(len(uv) == 2, "surface_uv_dimension")
                for axis in range(2):
                    low[axis] = uv[axis] if low[axis] is None else min(low[axis],uv[axis])
                    high[axis] = uv[axis] if high[axis] is None else max(high[axis],uv[axis])
                cell = (math.floor(uv[0]), math.floor(uv[1]))
                require(abs(cell[0]) <= 1000000 and abs(cell[1]) <= 1000000,
                        "surface_uv_cell_range")
                cells[cell] = cells.get(cell,0)+1
                require(len(cells) <= 4096, "surface_uv_cell_budget")
                yield uv
        checksum = surface_stream_digest(uv_values())
        uv_rows.append({"index":index,"name":layer.name,"active":bool(layer.active),
            "active_render":bool(layer.active_render),"active_clone":bool(layer.active_clone),
            "coordinates":checksum,"minimum":low,"maximum":high,
            "raw_floor_cell_counts":[{"u":cell[0],"v":cell[1],"corners":count}
                                    for cell,count in sorted(cells.items())],
            "sampled_image_tile_coverage_approved":False})
    row["uv_layers"] = uv_rows
    row["active_uv_layer_index"] = int(mesh.uv_layers.active_index)
    row["active_uv_layer_name"] = mesh.uv_layers.active.name if mesh.uv_layers.active else None
    # Named shader-attribute dependencies need a descriptor; no assumption that a name is a UV map.
    row["attribute_descriptors"] = [{"name":attribute.name,"type":attribute.data_type,
                                   "domain":attribute.domain,"length":len(attribute.data)}
                                  for attribute in mesh.attributes]
    row["attribute_values_captured_except_uv"] = False
    row["modifiers"] = [surface_modifier(bpy, modifier, labels, groups) for modifier in obj.modifiers]
    return row

def source_surface_report(bpy, config, rig, labels, context):
    objects = [bpy.data.objects.get(name) for name in config["mesh_names"]]
    require(len(objects) == 17 and all(obj is not None for obj in objects), "surface_exact17_objects")
    counts = {"objects":len(objects), "vertices":sum(len(obj.data.vertices) for obj in objects),
              "loops":sum(len(obj.data.loops) for obj in objects),
              "polygons":sum(len(obj.data.polygons) for obj in objects),
              "modifiers":sum(len(obj.modifiers) for obj in objects)}
    context["preflight_counts"] = counts
    modifier_types = {}
    for obj in objects:
        for modifier in obj.modifiers:
            modifier_types[modifier.type] = modifier_types.get(modifier.type,0)+1
    context["all_modifier_type_counts"] = dict(sorted(modifier_types.items()))
    require(counts["vertices"] <= 1000000 and counts["loops"] <= 4000000
            and counts["polygons"] <= 1000000 and counts["modifiers"] <= 1024,
            "surface_aggregate_preflight")
    meshes, materials, groups = [], set(), set()
    for obj in objects:
        context["active_object"] = obj.name
        meshes.append(surface_mesh(bpy,obj,rig,labels,materials,groups))
    require(len(materials) <= 128, "surface_material_budget")
    material_rows, roots = [], set(groups)
    for material in sorted(materials,key=lambda item:labels[item]):
        context["active_material"] = material.name
        require(material.library is None and material.override_library is None,
                "surface_material_linked_or_override")
        material_rows.append({"id":labels[material],
            "settings":surface_fields(bpy,material,SURFACE_MATERIAL_FIELDS,labels),
            "node_tree":surface_value(bpy,material.node_tree,labels)})
        if material.node_tree is not None:
            roots.add(material.node_tree)
    trees = surface_node_trees(bpy,roots,labels)
    unsupported = [{"object":mesh["object"], "modifier_index":index, "modifier_name":modifier["name"],
                    "type":modifier["type"], "reason":modifier["unsupported_reason"]}
                   for mesh in meshes for index,modifier in enumerate(mesh["modifiers"])
                   if modifier.get("source_parameter_capture_supported") is not True]
    unsupported_types = {}
    for item in unsupported:
        unsupported_types[item["type"]] = unsupported_types.get(item["type"],0)+1
    result = {"schema_version":1, "scope":"exact17 configured SOURCE-CAGE meshes and source-slot materials",
        "source_counts":counts, "native_render_engine":bpy.context.scene.render.engine, "meshes":meshes, "materials":material_rows, "node_trees":trees,
        "source_exposed_parameter_capture_complete":not unsupported,
        "unsupported_modifier_count":len(unsupported), "unsupported_modifier_type_counts":unsupported_types,
        "unsupported_modifiers":unsupported, "unsupported_selector_or_type_never_read":True,
        "derived_render_caches_captured":False, "all_node_storage_bytes_captured":False,
        "named_attribute_numeric_data_or_behavior_approved":False,
        "source_cage_equals_final_surface":False,
        "final_evaluated_material_assignments_complete":False,
        "pbr_semantic_mapping_approved":False,"material_visual_approved":False,
        "production_glb_approved":False,"browser_approved":False,
        "renders_or_bakes":0,"models_saved":0,"model_payload_reuploaded":False,
        "source_or_native_controls_changed":False}
    require(len(encoded(result)) <= 650*1024, "surface_report_byte_budget")
    return result


# Prepared source-only insertion block; Blender 4.5.9 / 8bf95cbd38d1456c94e9d751f3804eea4d5b137b.
# Primary policy 791607b112df7fb8e94b98a708efbec42955462b.
# Requires existing require, encoded, hashlib, math, redacted_text and
# surface_value(bpy, value, labels, depth=0). Does not import bpy or execute nodes.
# Public source configuration only; hidden GPU/curve caches are not read/rebuilt.
SURFACE_NODE_FIELDS = {"NodeFrame": {"text": "ID", "shrink": "bool", "label_size": "int"}, "NodeReroute": {"socket_idname": "str"}, "NodeGroupInput": {}, "NodeGroupOutput": {"is_active_output": "bool"}, "ShaderNodeGroup": {"node_tree": "ID"}, "ShaderNodeTexImage": {"image": "ID", "projection": "enum", "interpolation": "enum", "projection_blend": "float", "extension": "enum", "image_user": "ImageUser", "texture_mapping": "TexMapping", "color_mapping": "ColorMapping"}, "ShaderNodeTexEnvironment": {"image": "ID", "projection": "enum", "interpolation": "enum", "image_user": "ImageUser", "texture_mapping": "TexMapping", "color_mapping": "ColorMapping"}, "ShaderNodeBsdfPrincipled": {"distribution": "enum", "subsurface_method": "enum"}, "ShaderNodeOutputMaterial": {"is_active_output": "bool", "target": "enum"}, "ShaderNodeNormalMap": {"space": "enum", "uv_map": "str"}, "ShaderNodeMath": {"operation": "enum", "use_clamp": "bool"}, "ShaderNodeVectorMath": {"operation": "enum"}, "ShaderNodeMixRGB": {"blend_type": "enum", "use_alpha": "bool", "use_clamp": "bool"}, "ShaderNodeMix": {"data_type": "enum", "factor_mode": "enum", "blend_type": "enum", "clamp_factor": "bool", "clamp_result": "bool"}, "ShaderNodeRGB": {}, "ShaderNodeValue": {}, "ShaderNodeTexCoord": {"object": "ID", "from_instancer": "bool"}, "ShaderNodeMapping": {"vector_type": "enum"}, "ShaderNodeBackground": {}, "ShaderNodeOutputWorld": {"is_active_output": "bool", "target": "enum"}, "ShaderNodeAddShader": {}, "ShaderNodeAttribute": {"attribute_type": "enum", "attribute_name": "str"}, "ShaderNodeBsdfAnisotropic": {"distribution": "enum"}, "ShaderNodeBsdfRefraction": {"distribution": "enum"}, "ShaderNodeBsdfTransparent": {}, "ShaderNodeEmission": {}, "ShaderNodeInvert": {}, "ShaderNodeLightPath": {}, "ShaderNodeMixShader": {}, "ShaderNodeNewGeometry": {}, "ShaderNodeTangent": {"direction_type": "enum", "axis": "enum", "uv_map": "str"}, "ShaderNodeUVMap": {"from_instancer": "bool", "uv_map": "str"}, "FunctionNodeBooleanMath": {"operation": "enum"}, "FunctionNodeCompare": {"operation": "enum", "data_type": "enum", "mode": "enum"}, "GeometryNodeInputEdgeSmooth": {}, "GeometryNodeInputMeshEdgeAngle": {}, "GeometryNodeInputShadeSmooth": {}, "GeometryNodeSetShadeSmooth": {"domain": "enum"}, "ShaderNodeValToRGB": {"color_ramp": "ColorRamp"}, "ShaderNodeRGBCurve": {"mapping": "CurveMapping"}, "ShaderNodeSeparateColor": {"mode": "enum"}, "ShaderNodeVectorRotate": {"rotation_type": "enum", "invert": "bool"}, "ShaderNodeVectorTransform": {"vector_type": "enum", "convert_from": "enum", "convert_to": "enum"}, "ShaderNodeMapRange": {"clamp": "bool", "interpolation_type": "enum", "data_type": "enum"}}
SURFACE_SOCKET_FORMS = {"NodeSocketFloat": ["float", "NodeTreeInterfaceSocketFloat", "SOCK_FLOAT", "PROP_NONE"], "NodeSocketFloatUnsigned": ["float", "NodeTreeInterfaceSocketFloatUnsigned", "SOCK_FLOAT", "PROP_UNSIGNED"], "NodeSocketFloatPercentage": ["float", "NodeTreeInterfaceSocketFloatPercentage", "SOCK_FLOAT", "PROP_PERCENTAGE"], "NodeSocketFloatFactor": ["float", "NodeTreeInterfaceSocketFloatFactor", "SOCK_FLOAT", "PROP_FACTOR"], "NodeSocketFloatAngle": ["float", "NodeTreeInterfaceSocketFloatAngle", "SOCK_FLOAT", "PROP_ANGLE"], "NodeSocketFloatTime": ["float", "NodeTreeInterfaceSocketFloatTime", "SOCK_FLOAT", "PROP_TIME"], "NodeSocketFloatTimeAbsolute": ["float", "NodeTreeInterfaceSocketFloatTimeAbsolute", "SOCK_FLOAT", "PROP_TIME_ABSOLUTE"], "NodeSocketFloatDistance": ["float", "NodeTreeInterfaceSocketFloatDistance", "SOCK_FLOAT", "PROP_DISTANCE"], "NodeSocketFloatWavelength": ["float", "NodeTreeInterfaceSocketFloatWavelength", "SOCK_FLOAT", "PROP_WAVELENGTH"], "NodeSocketFloatColorTemperature": ["float", "NodeTreeInterfaceSocketFloatColorTemperature", "SOCK_FLOAT", "PROP_COLOR_TEMPERATURE"], "NodeSocketFloatFrequency": ["float", "NodeTreeInterfaceSocketFloatFrequency", "SOCK_FLOAT", "PROP_FREQUENCY"], "NodeSocketInt": ["int", "NodeTreeInterfaceSocketInt", "SOCK_INT", "PROP_NONE"], "NodeSocketIntUnsigned": ["int", "NodeTreeInterfaceSocketIntUnsigned", "SOCK_INT", "PROP_UNSIGNED"], "NodeSocketIntPercentage": ["int", "NodeTreeInterfaceSocketIntPercentage", "SOCK_INT", "PROP_PERCENTAGE"], "NodeSocketIntFactor": ["int", "NodeTreeInterfaceSocketIntFactor", "SOCK_INT", "PROP_FACTOR"], "NodeSocketBool": ["bool", "NodeTreeInterfaceSocketBool", "SOCK_BOOLEAN", "PROP_NONE"], "NodeSocketRotation": ["v3", "NodeTreeInterfaceSocketRotation", "SOCK_ROTATION", "PROP_NONE"], "NodeSocketMatrix": ["none", "NodeTreeInterfaceSocketMatrix", "SOCK_MATRIX", "PROP_NONE"], "NodeSocketVector": ["v3", "NodeTreeInterfaceSocketVector", "SOCK_VECTOR", "PROP_NONE"], "NodeSocketVectorFactor": ["v3", "NodeTreeInterfaceSocketVectorFactor", "SOCK_VECTOR", "PROP_FACTOR"], "NodeSocketVectorPercentage": ["v3", "NodeTreeInterfaceSocketVectorPercentage", "SOCK_VECTOR", "PROP_PERCENTAGE"], "NodeSocketVectorTranslation": ["v3", "NodeTreeInterfaceSocketVectorTranslation", "SOCK_VECTOR", "PROP_TRANSLATION"], "NodeSocketVectorDirection": ["v3", "NodeTreeInterfaceSocketVectorDirection", "SOCK_VECTOR", "PROP_DIRECTION"], "NodeSocketVectorVelocity": ["v3", "NodeTreeInterfaceSocketVectorVelocity", "SOCK_VECTOR", "PROP_VELOCITY"], "NodeSocketVectorAcceleration": ["v3", "NodeTreeInterfaceSocketVectorAcceleration", "SOCK_VECTOR", "PROP_ACCELERATION"], "NodeSocketVectorEuler": ["v3", "NodeTreeInterfaceSocketVectorEuler", "SOCK_VECTOR", "PROP_EULER"], "NodeSocketVectorXYZ": ["v3", "NodeTreeInterfaceSocketVectorXYZ", "SOCK_VECTOR", "PROP_XYZ"], "NodeSocketVector2D": ["v2", "NodeTreeInterfaceSocketVector2D", "SOCK_VECTOR", "PROP_NONE"], "NodeSocketVectorFactor2D": ["v2", "NodeTreeInterfaceSocketVectorFactor2D", "SOCK_VECTOR", "PROP_FACTOR"], "NodeSocketVectorPercentage2D": ["v2", "NodeTreeInterfaceSocketVectorPercentage2D", "SOCK_VECTOR", "PROP_PERCENTAGE"], "NodeSocketVectorTranslation2D": ["v2", "NodeTreeInterfaceSocketVectorTranslation2D", "SOCK_VECTOR", "PROP_TRANSLATION"], "NodeSocketVectorDirection2D": ["v2", "NodeTreeInterfaceSocketVectorDirection2D", "SOCK_VECTOR", "PROP_DIRECTION"], "NodeSocketVectorVelocity2D": ["v2", "NodeTreeInterfaceSocketVectorVelocity2D", "SOCK_VECTOR", "PROP_VELOCITY"], "NodeSocketVectorAcceleration2D": ["v2", "NodeTreeInterfaceSocketVectorAcceleration2D", "SOCK_VECTOR", "PROP_ACCELERATION"], "NodeSocketVectorEuler2D": ["v2", "NodeTreeInterfaceSocketVectorEuler2D", "SOCK_VECTOR", "PROP_EULER"], "NodeSocketVectorXYZ2D": ["v2", "NodeTreeInterfaceSocketVectorXYZ2D", "SOCK_VECTOR", "PROP_XYZ"], "NodeSocketVector4D": ["v4", "NodeTreeInterfaceSocketVector4D", "SOCK_VECTOR", "PROP_NONE"], "NodeSocketVectorFactor4D": ["v4", "NodeTreeInterfaceSocketVectorFactor4D", "SOCK_VECTOR", "PROP_FACTOR"], "NodeSocketVectorPercentage4D": ["v4", "NodeTreeInterfaceSocketVectorPercentage4D", "SOCK_VECTOR", "PROP_PERCENTAGE"], "NodeSocketVectorTranslation4D": ["v4", "NodeTreeInterfaceSocketVectorTranslation4D", "SOCK_VECTOR", "PROP_TRANSLATION"], "NodeSocketVectorDirection4D": ["v4", "NodeTreeInterfaceSocketVectorDirection4D", "SOCK_VECTOR", "PROP_DIRECTION"], "NodeSocketVectorVelocity4D": ["v4", "NodeTreeInterfaceSocketVectorVelocity4D", "SOCK_VECTOR", "PROP_VELOCITY"], "NodeSocketVectorAcceleration4D": ["v4", "NodeTreeInterfaceSocketVectorAcceleration4D", "SOCK_VECTOR", "PROP_ACCELERATION"], "NodeSocketVectorEuler4D": ["v4", "NodeTreeInterfaceSocketVectorEuler4D", "SOCK_VECTOR", "PROP_EULER"], "NodeSocketVectorXYZ4D": ["v4", "NodeTreeInterfaceSocketVectorXYZ4D", "SOCK_VECTOR", "PROP_XYZ"], "NodeSocketColor": ["v4", "NodeTreeInterfaceSocketColor", "SOCK_RGBA", "PROP_NONE"], "NodeSocketString": ["str", "NodeTreeInterfaceSocketString", "SOCK_STRING", "PROP_NONE"], "NodeSocketStringFilePath": ["str", "NodeTreeInterfaceSocketStringFilePath", "SOCK_STRING", "PROP_FILEPATH"], "NodeSocketShader": ["none", "NodeTreeInterfaceSocketShader", "SOCK_SHADER", "PROP_NONE"], "NodeSocketObject": ["ID", "NodeTreeInterfaceSocketObject", "SOCK_OBJECT", "PROP_NONE"], "NodeSocketImage": ["ID", "NodeTreeInterfaceSocketImage", "SOCK_IMAGE", "PROP_NONE"], "NodeSocketGeometry": ["none", "NodeTreeInterfaceSocketGeometry", "SOCK_GEOMETRY", "PROP_NONE"], "NodeSocketCollection": ["ID", "NodeTreeInterfaceSocketCollection", "SOCK_COLLECTION", "PROP_NONE"], "NodeSocketTexture": ["ID", "NodeTreeInterfaceSocketTexture", "SOCK_TEXTURE", "PROP_NONE"], "NodeSocketMaterial": ["ID", "NodeTreeInterfaceSocketMaterial", "SOCK_MATERIAL", "PROP_NONE"], "NodeSocketVirtual": ["none", None, "SOCK_CUSTOM", "PROP_NONE"]}
SURFACE_NESTED_FIELDS = {"ImageUser": {"use_auto_refresh": "bool", "frame_current": "int", "use_cyclic": "bool", "frame_duration": "int", "frame_offset": "int", "frame_start": "int", "multilayer_layer": "int", "multilayer_pass": "int", "multilayer_view": "int", "tile": "int"}, "TexMapping": {"vector_type": "enum", "translation": "v3", "rotation": "v3", "scale": "v3", "min": "v3", "max": "v3", "use_min": "bool", "use_max": "bool", "mapping_x": "enum", "mapping_y": "enum", "mapping_z": "enum", "mapping": "enum"}, "ColorMapping": {"use_color_ramp": "bool", "color_ramp": "ColorRamp", "brightness": "float", "contrast": "float", "saturation": "float", "blend_type": "enum", "blend_color": "v3", "blend_factor": "float"}}
SURFACE_GRAPH_CAPS = {"trees": 128, "nodes": 4096, "sockets": 32768,
                      "links": 32768, "interface_items": 8192, "images": 64}

def surface_count(counts, kind, amount=1):
    counts[kind] += amount
    require(counts[kind] <= SURFACE_GRAPH_CAPS[kind], "surface_"+kind+"_budget")

def surface_typed(bpy, value, kind, labels, depth=0):
    require(depth <= 8, "surface_nested_depth")
    if kind == "ID":
        require(value is None or isinstance(value, bpy.types.ID), "surface_id_type")
        if value is not None:
            require(value in labels and value.library is None
                    and value.override_library is None, "surface_id_scope")
        return surface_value(bpy, value, labels, depth)
    if kind == "bool":
        require(type(value) is bool, "surface_bool_type")
        return value
    if kind == "int":
        require(type(value) is int and -(1 << 63) <= value < (1 << 63), "surface_int_type")
        return value
    if kind == "float":
        require(type(value) in (int, float) and math.isfinite(value), "surface_float_type")
        return float(value)
    if kind in ("str", "enum"):
        require(type(value) is str and len(value) <= (128 if kind == "enum" else 4096),
                "surface_string_type_or_budget")
        if kind == "enum":
            require(bool(value) and all(char.isascii() for char in value), "surface_enum_identifier")
        return value
    if kind in ("v2", "v3", "v4"):
        size = int(kind[1:])
        require(not isinstance(value, (str, bytes, dict)) and len(value) == size,
                "surface_vector_shape")
        return [surface_typed(bpy, component, "float", labels, depth+1) for component in value]
    if kind == "ColorRamp":
        require(value is not None and value.bl_rna.identifier == "ColorRamp",
                "surface_color_ramp_type")
        require(1 <= len(value.elements) <= 32, "surface_color_ramp_budget")
        out = surface_node_fields(bpy, value, {"interpolation": "enum", "hue_interpolation": "enum",
                             "color_mode": "enum"}, labels, depth+1)
        out["elements"] = [surface_node_fields(bpy, item, {"position": "float", "color": "v4",
                            "alpha": "float"}, labels, depth+1) for item in value.elements]
        return out
    if kind == "CurveMapping":
        require(value is not None and value.bl_rna.identifier == "CurveMapping",
                "surface_curve_mapping_type")
        out = surface_node_fields(bpy, value, {"tone": "enum", "use_clip": "bool",
            "clip_min_x": "float", "clip_min_y": "float", "clip_max_x": "float",
            "clip_max_y": "float", "extend": "enum", "black_level": "v3",
            "white_level": "v3"}, labels, depth+1)
        require(len(value.curves) <= 4, "surface_curve_count")
        out["curves"] = []
        total_points = 0
        for curve in value.curves:
            total_points += len(curve.points)
            require(total_points <= 4096, "surface_curve_point_budget")
            out["curves"].append({"points": [surface_node_fields(bpy, point,
                {"location": "v2", "handle_type": "enum", "select": "bool"},
                labels, depth+1) for point in curve.points]})
        return out
    if kind in SURFACE_NESTED_FIELDS:
        require(value is not None and value.bl_rna.identifier == kind,
                "surface_nested_rna_type")
        return surface_node_fields(bpy, value, SURFACE_NESTED_FIELDS[kind], labels, depth+1)
    require(False, "surface_unhandled_typed_value")

def surface_node_fields(bpy, item, fields, labels, depth=0):
    # Only explicit names; never walk/get all RNA properties.
    return {name: surface_typed(bpy, getattr(item, name), kind, labels, depth+1)
            for name, kind in fields.items()}

def surface_id_properties(bpy, item, labels):
    require(len(item.keys()) <= 256, "surface_id_property_count")
    return surface_value(bpy, {key: item[key] for key in sorted(item.keys())}, labels)

def surface_socket_default(bpy, socket, socket_id, labels, image_ids):
    require(socket_id in SURFACE_SOCKET_FORMS, "surface_unsupported_socket_form")
    kind, _, _, subtype = SURFACE_SOCKET_FORMS[socket_id]
    if kind == "none":
        require(not hasattr(socket, "default_value"), "surface_unhandled_socket_default")
        return {"kind": "no_RNA_default_value"}
    value = socket.default_value
    if subtype == "PROP_FILEPATH":
        require(value == "", "surface_nonempty_socket_filepath")
    if kind == "ID" and isinstance(value, bpy.types.Image):
        image_ids.add(value)
    return {"kind": kind, "value": surface_typed(bpy, value, kind, labels)}

def surface_socket(bpy, socket, index, direction, node_index, labels, image_ids):
    socket_id = socket.bl_idname
    require(socket_id in SURFACE_SOCKET_FORMS
            and socket.bl_rna.identifier == socket_id, "surface_socket_rna_identity")
    out = surface_node_fields(bpy, socket, {"name": "str", "identifier": "str", "type": "enum",
        "is_output": "bool", "enabled": "bool", "hide": "bool", "hide_value": "bool",
        "is_unavailable": "bool", "is_multi_input": "bool", "is_linked": "bool",
        "link_limit": "int"}, labels)
    require(out["is_output"] == (direction == "outputs"), "surface_socket_direction")
    out.update({"index": index, "node_index": node_index, "direction": direction,
                "socket_rna": socket_id,
                "default": surface_socket_default(bpy, socket, socket_id, labels, image_ids)})
    return out

def surface_interface(bpy, tree, labels, counts, image_ids):
    interface = tree.interface
    require(interface.bl_rna.identifier == "NodeTreeInterface", "surface_interface_type")
    require(len(interface.items_tree) <= 4096, "surface_tree_interface_budget")
    items = list(interface.items_tree)
    surface_count(counts, "interface_items", len(items))
    indices = {item: index for index, item in enumerate(items)}
    require(len(indices) == len(items), "surface_interface_item_identity")
    implicit_roots = {item.parent for item in items
                      if item.parent is not None and item.parent not in indices}
    require(len(implicit_roots) <= 1, "surface_interface_implicit_root_count")
    implicit = next(iter(implicit_roots)) if implicit_roots else None
    def panel_fields(panel):
        require(panel.bl_rna.identifier == "NodeTreeInterfacePanel"
                and panel.item_type == "PANEL", "surface_interface_panel_type")
        out = surface_node_fields(bpy, panel, {"name": "str", "description": "str",
            "default_closed": "bool", "persistent_uid": "int"}, labels)
        require(len(panel.interface_items) <= 4096
                and all(child in indices for child in panel.interface_items),
                "surface_interface_panel_children")
        out["children"] = [indices[child] for child in panel.interface_items]
        return out
    root_record = None
    if implicit is not None:
        require(implicit.parent is None, "surface_interface_root_parent")
        root_record = panel_fields(implicit)
    rows = []
    for index, item in enumerate(items):
        parent = item.parent
        require(parent is None or parent in indices or parent == implicit,
                "surface_interface_parent")
        row = {"collection_index": index, "index": surface_typed(bpy, item.index, "int", labels),
               "position": surface_typed(bpy, item.position, "int", labels),
               "parent": "ROOT" if parent == implicit and parent is not None else
                         (indices[parent] if parent is not None else None),
               "item_type": surface_typed(bpy, item.item_type, "enum", labels)}
        if item.item_type == "PANEL":
            row.update(panel_fields(item))
        elif item.item_type == "SOCKET":
            socket_id = item.bl_socket_idname
            require(socket_id in SURFACE_SOCKET_FORMS and socket_id != "NodeSocketVirtual",
                    "surface_unsupported_interface_socket")
            kind, rna_interface, family, _ = SURFACE_SOCKET_FORMS[socket_id]
            require(item.bl_rna.identifier == rna_interface, "surface_interface_socket_rna")
            row.update(surface_node_fields(bpy, item, {"name": "str", "identifier": "str",
                "description": "str", "socket_type": "enum", "in_out": "enum",
                "hide_value": "bool", "hide_in_modifier": "bool", "force_non_field": "bool",
                "is_inspect_output": "bool", "is_panel_toggle": "bool", "layer_selection_field": "bool",
                "menu_expanded": "bool", "attribute_domain": "enum", "default_attribute_name": "str",
                "structure_type": "enum", "default_input": "enum", "bl_socket_idname": "str"}, labels))
            row["default"] = surface_socket_default(bpy, item, socket_id, labels, image_ids)
            if family in ("SOCK_FLOAT", "SOCK_INT", "SOCK_VECTOR"):
                row["subtype"] = surface_typed(bpy, item.subtype, "enum", labels)
                number_type = "int" if family == "SOCK_INT" else "float"
                row["min_value"] = surface_typed(bpy, item.min_value, number_type, labels)
                row["max_value"] = surface_typed(bpy, item.max_value, number_type, labels)
                if family == "SOCK_VECTOR":
                    row["dimensions"] = surface_typed(bpy, item.dimensions, "int", labels)
                    require(row["dimensions"] == int(kind[1:]), "surface_interface_vector_dimensions")
            elif family == "SOCK_STRING":
                row["subtype"] = surface_typed(bpy, item.subtype, "enum", labels)
            row["id_properties"] = surface_id_properties(bpy, item, labels)
        else:
            require(False, "surface_unsupported_interface_item")
        rows.append(row)
    keys = [(row["in_out"], row["identifier"]) for row in rows if row["item_type"] == "SOCKET"]
    require(len(keys) == len(set(keys)), "surface_duplicate_interface_identifier")
    return {"items": rows, "implicit_root_panel": root_record,
            "empty_root_panel_unexposed": not items,
            "interface_container_id_properties_supported": False}

def surface_image_metadata(bpy, image, labels):
    require(image in labels and image.library is None and image.override_library is None
            and image.source in ("FILE", "TILED"), "surface_image_scope")
    out = {"id": surface_typed(bpy, image, "ID", labels)}
    out.update(surface_node_fields(bpy, image, {"source": "enum", "type": "enum", "alpha_mode": "enum",
        "use_view_as_render": "bool", "use_deinterlace": "bool", "use_multiview": "bool",
        "is_multiview": "bool", "is_stereo_3d": "bool", "views_format": "enum",
        "use_half_precision": "bool"}, labels))
    require(not out["use_multiview"] and not out["is_multiview"] and not out["is_stereo_3d"],
            "surface_multiview_or_stereo_unsupported")
    out["colorspace"] = surface_node_fields(bpy, image.colorspace_settings,
                                      {"name": "enum", "is_data": "bool"}, labels)
    out["filepath"] = redacted_text(image.filepath_raw)
    require(len(image.tiles) <= 256 and len(image.packed_files) <= 256, "surface_image_mapping_budget")
    out["tiles"] = [surface_node_fields(bpy, tile, {"number": "int", "label": "str"}, labels)
                    for tile in image.tiles]
    out["packed_mapping"] = []
    for packed in image.packed_files:
        require(type(packed.view) is int and packed.view == 0
                and type(packed.tile_number) is int, "surface_packed_view_unsupported")
        out["packed_mapping"].append({"view": packed.view, "tile_number": packed.tile_number,
                                     "filepath": redacted_text(packed.filepath)})
    require(len({row["number"] for row in out["tiles"]}) == len(out["tiles"]),
            "surface_duplicate_image_tile")
    out["dimensions_channels_and_bytes_from_separate_packed_proof"] = True
    out["pixels_or_new_decode_requested"] = False
    return out

def surface_node_trees(bpy, roots, labels):
    """Return bounded raw source graph metadata; caller hashes this again after inspection.
    roots: actual Material.node_tree / modifier.node_group IDs; no strings or archive input code.
    Requires old strict native+packed+resource closure gates independently; this is not PBR proof.
    """
    counts = {key: 0 for key in SURFACE_GRAPH_CAPS}
    image_ids, records, visiting = set(), {}, set()
    require(isinstance(roots, (list, tuple, set)) and len(roots) <= 128, "surface_tree_root_budget")
    root_ids = set(roots)
    require(all(isinstance(tree, bpy.types.NodeTree) and tree in labels for tree in root_ids),
            "surface_tree_root_type")
    def visit(tree, depth):
        require(depth <= 32, "surface_group_depth")
        require(tree not in visiting, "surface_recursive_node_group")
        if tree in records:
            return
        require(tree in labels and tree.library is None and tree.override_library is None
                and tree.bl_idname in ("ShaderNodeTree", "GeometryNodeTree"),
                "surface_tree_scope")
        visiting.add(tree)
        surface_count(counts, "trees")
        require(len(tree.nodes) <= 4096 and len(tree.links) <= 32768, "surface_tree_budget")
        nodes = list(tree.nodes)
        indices = {node: index for index, node in enumerate(nodes)}
        require(len(indices) == len(nodes) and len({node.name for node in nodes}) == len(nodes),
                "surface_node_identity")
        sockets = {}
        rows = []
        children = set()
        interface = surface_interface(bpy, tree, labels, counts, image_ids)
        for index, node in enumerate(nodes):
            surface_count(counts, "nodes")
            node_type = node.bl_idname
            require(node_type in SURFACE_NODE_FIELDS and node.bl_rna.identifier == node_type,
                    "surface_unsupported_node")
            require(node.parent is None or (node.parent in indices
                    and node.parent.bl_idname == "NodeFrame"), "surface_node_parent_scope")
            row = surface_node_fields(bpy, node, {"name": "str", "label": "str",
                                            "mute": "bool", "type": "str"}, labels)
            row.update({"index": index, "node_type": node_type,
                "parent_index": indices[node.parent] if node.parent is not None else None,
                "parameters": surface_node_fields(bpy, node, SURFACE_NODE_FIELDS[node_type], labels),
                "id_properties": surface_id_properties(bpy, node, labels)})
            for direction in ("inputs", "outputs"):
                collection = getattr(node, direction)
                require(len(collection) <= 512, "surface_node_socket_budget")
                row[direction] = []
                for socket_index, socket in enumerate(collection):
                    surface_count(counts, "sockets")
                    require(socket not in sockets, "surface_duplicate_socket")
                    item = surface_socket(bpy, socket, socket_index, direction, index, labels, image_ids)
                    row[direction].append(item)
                    sockets[socket] = {"node_index": index, "direction": direction,
                                      "index": socket_index, "identifier": item["identifier"]}
            if node_type in ("ShaderNodeTexImage", "ShaderNodeTexEnvironment") and node.image is not None:
                image_ids.add(node.image)
            if node_type == "ShaderNodeGroup" and node.node_tree is not None:
                children.add(node.node_tree)
            rows.append(row)
        def endpoint(socket):
            require(socket is not None and socket in sockets, "surface_link_socket_scope")
            return dict(sockets[socket])
        def link_row(link, order, internal_owner=None):
            surface_count(counts, "links")
            source, target = endpoint(link.from_socket), endpoint(link.to_socket)
            if internal_owner is None:
                require(source["direction"] == "outputs" and target["direction"] == "inputs"
                        and link.from_node in indices and link.to_node in indices
                        and indices[link.from_node] == source["node_index"]
                        and indices[link.to_node] == target["node_index"], "surface_external_link_owner")
            else:
                # Internal mute links are input-to-output, not external-link orientation.
                require(source["node_index"] == target["node_index"] == internal_owner,
                        "surface_internal_link_owner")
            return {"collection_index": order, "from": source, "to": target,
                **surface_node_fields(bpy, link, {"is_valid": "bool", "is_muted": "bool",
                     "is_hidden": "bool", "multi_input_sort_id": "int"}, labels)}
        links = [link_row(link, order) for order, link in enumerate(tree.links)]
        for node, row in zip(nodes, rows):
            require(len(node.internal_links) <= 512, "surface_internal_link_budget")
            row["internal_links"] = [link_row(link, order, row["index"])
                                     for order, link in enumerate(node.internal_links)]
        def group_bindings(row, group_interface, directions):
            interface_keys = {(item["in_out"], item["identifier"]): item["collection_index"]
                for item in group_interface["items"] if item["item_type"] == "SOCKET"}
            bindings = []
            for direction, interface_direction in directions:
                for socket in row[direction]:
                    if socket["socket_rna"] == "NodeSocketVirtual":
                        bindings.append({"socket_direction": direction, "socket_index": socket["index"],
                                         "virtual_extension_sentinel": True})
                    else:
                        key = (interface_direction, socket["identifier"])
                        require(key in interface_keys, "surface_group_socket_interface_binding")
                        bindings.append({"socket_direction": direction, "socket_index": socket["index"],
                            "identifier": socket["identifier"], "interface_item_index": interface_keys[key]})
            return bindings
        for child in sorted(children, key=lambda item: labels[item] if item in labels else ""):
            visit(child, depth+1)
        for node, row in zip(nodes, rows):
            if row["node_type"] == "ShaderNodeGroup" and node.node_tree is not None:
                row["group_instance_bindings"] = group_bindings(row, records[node.node_tree]["interface"],
                                                               (("inputs", "INPUT"), ("outputs", "OUTPUT")))
            elif row["node_type"] == "NodeGroupInput":
                row["group_interface_bindings"] = group_bindings(row, interface, (("outputs", "INPUT"),))
            elif row["node_type"] == "NodeGroupOutput":
                row["group_interface_bindings"] = group_bindings(row, interface, (("inputs", "OUTPUT"),))
        require(tree.nodes.active is None or tree.nodes.active in indices, "surface_active_node")
        records[tree] = {"id": surface_typed(bpy, tree, "ID", labels),
            "tree_type": tree.bl_idname, "nodes": rows, "links": links, "interface": interface,
            "active_node_index": indices[tree.nodes.active] if tree.nodes.active is not None else None,
            "id_properties": surface_id_properties(bpy, tree, labels)}
        visiting.remove(tree)
    for tree in sorted(root_ids, key=lambda item: labels[item]):
        visit(tree, 0)
    surface_count(counts, "images", len(image_ids))
    result = {"roots": [surface_typed(bpy, tree, "ID", labels)
                         for tree in sorted(root_ids, key=lambda item: labels[item])],
        "trees": [records[tree] for tree in sorted(records, key=lambda item: labels[item])],
        "images": [surface_image_metadata(bpy, image, labels)
                    for image in sorted(image_ids, key=lambda item: labels[item])],
        "counts": counts, "public_source_configuration_only": True,
        "hidden_gpu_and_curve_caches_uninspected_not_recomputed": True,
        "all_socket_collections_and_defaults_retained": True,
        "actual_node_evaluation_shader_compile_or_pixels_requested": False,
        "pbr_export_or_visual_equivalence_proved": False}
    require(len(encoded(result)) <= 512*1024, "surface_node_graph_json_budget")
    return result


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
    audit = {"purpose": "Read-only exact17 Snow SOURCE-CAGE material/UV/modifier planning with locked actor resource prerequisites",
             "source_surface_report_passed": False,
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
    surface_report = None
    surface_failure = None
    surface_context = {}
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
        if resources["passed"]:
            try:
                stage = "source_surface_before"
                surface_report = source_surface_report(bpy, config, rig, labels, surface_context)
                audit["source_surface_plan"] = surface_report
                audit["source_surface_before_sha256"] = hashlib.sha256(encoded(surface_report)).hexdigest()
            except Exception as error:
                surface_failure = failure_record(error, stage)
                audit["source_surface_failure"] = surface_failure
                audit["source_surface_failure_context"] = dict(surface_context)
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
        if surface_report is not None and surface_failure is None:
            try:
                stage = "source_surface_after"
                surface_after = source_surface_report(bpy, config, rig, labels, surface_context)
                audit["source_surface_after_sha256"] = hashlib.sha256(encoded(surface_after)).hexdigest()
                require(surface_after == surface_report
                        and audit["source_surface_after_sha256"] == audit["source_surface_before_sha256"],
                        "source_surface_readonly_metadata_changed")
                audit["source_surface_metadata_unchanged"] = True
            except Exception as error:
                surface_failure = failure_record(error, stage)
                audit["source_surface_failure"] = surface_failure
                audit["source_surface_failure_context"] = dict(surface_context)
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
        audit["source_surface_report_passed"] = bool(audit["used_actor_external_closure_passed"]
            and surface_report is not None and surface_failure is None
            and surface_report.get("source_exposed_parameter_capture_complete") is True
            and audit.get("source_surface_metadata_unchanged") is True)
        write_json(audit_path, audit)
        summary = {key: audit.get(key) for key in ("purpose", "source_surface_report_passed", "source_surface_failure", "used_actor_external_closure_passed",
            "saved_packed_native_readback_passed", "failure", "hash_recheck_failure",
            "all_eight_inputs_and_manifest_unchanged", "reviewed_code_and_runtime_unchanged",
            "full_scene_portable", "art_approved", "glb_pbr_approved", "browser_animation_approved",
            "models_saved", "original_assets_restored", "model_payload_reuploaded")}
        if resources is not None:
            summary["resource_closure"] = {key: resources[key] for key in
                ("passed", "unsupported_count", "unsupported_details_omitted", "issue_counts_by_code",
                 "issue_counts_by_owner_type", "weak_reference_count", "weak_classification_counts",
                 "unknown_node_type_counts", "checked")}
        if surface_report is not None:
            summary["source_surface_plan"] = {key:surface_report[key] for key in
                ("scope","source_counts","source_exposed_parameter_capture_complete",
                 "unsupported_modifier_count","unsupported_modifier_type_counts",
                 "final_evaluated_material_assignments_complete","pbr_semantic_mapping_approved")}
        require(len(encoded(summary)) <= 24*1024, "stdout_budget")
        print("SNOW_PACKED_ACTOR_CLOSURE "+encoded(summary).decode("utf-8").strip(), flush=True)
    return 0 if audit["source_surface_report_passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
