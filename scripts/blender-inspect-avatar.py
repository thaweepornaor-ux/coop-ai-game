"""Run explicitly in Blender 4.5.9. Read raw datablocks; no evaluated geometry or frame changes."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import bpy

def counts(items):
    return dict(sorted(Counter(items).items()))

def driver_count(block):
    data = getattr(block, "animation_data", None)
    return len(data.drivers) if data else 0

def material_info(material):
    result = {"name": material.name, "use_nodes": material.use_nodes,
              "diffuse_color": list(material.diffuse_color), "drivers": driver_count(material)}
    if material.use_nodes and material.node_tree:
        tree = material.node_tree
        result["node_types"] = counts(n.bl_idname for n in tree.nodes)
        result["node_tree_drivers"] = driver_count(tree)
        result["principled"] = []
        for node in tree.nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            values = {}
            for key in ("Base Color", "Metallic", "Roughness", "Alpha"):
                socket = node.inputs.get(key)
                if socket is not None:
                    value = socket.default_value
                    values[key] = {"linked": socket.is_linked,
                                   "default": value if isinstance(value, (int, float)) else list(value)}
            result["principled"].append(values)
    return result

def object_info(obj):
    result = {"name": obj.name, "type": obj.type,
              "parent": obj.parent.name if obj.parent else None,
              "parent_type": obj.parent_type, "hide_render": obj.hide_render,
              "hide_viewport": obj.hide_viewport,
              "drivers": driver_count(obj),
              "constraints": counts(c.type for c in obj.constraints)}
    if obj.type == "MESH":
        mesh = obj.data
        keys = mesh.shape_keys
        result.update({
            "raw_vertices": len(mesh.vertices), "raw_edges": len(mesh.edges),
            "raw_polygons": len(mesh.polygons), "uv_layers": list(mesh.uv_layers.keys()),
            "materials": [s.material.name if s.material else None for s in obj.material_slots],
            "vertex_group_count": len(obj.vertex_groups),
            "shape_keys": [{"name": k.name, "relative_key": k.relative_key.name if k.relative_key else None,
                            "value": k.value} for k in keys.key_blocks] if keys else [],
            "shape_key_drivers": driver_count(keys) if keys else 0,
            "modifiers": [],
        })
        for modifier in obj.modifiers:
            entry = {"name": modifier.name, "type": modifier.type,
                     "viewport": modifier.show_viewport, "render": modifier.show_render}
            if modifier.type == "ARMATURE":
                entry.update({"armature": modifier.object.name if modifier.object else None,
                              "preserve_volume": modifier.use_deform_preserve_volume})
            elif modifier.type == "SUBSURF":
                entry.update({"levels": modifier.levels, "render_levels": modifier.render_levels})
            elif modifier.type == "MASK":
                entry.update({"mode": modifier.mode, "vertex_group": modifier.vertex_group,
                              "invert": modifier.invert_vertex_group})
            elif modifier.type == "SOLIDIFY":
                entry["thickness"] = modifier.thickness
            result["modifiers"].append(entry)
    elif obj.type == "ARMATURE":
        result.update({
            "bone_count": len(obj.data.bones),
            "deform_bone_count": sum(b.use_deform for b in obj.data.bones),
            "bbone_segmented_count": sum(b.bbone_segments > 1 for b in obj.data.bones),
            "bones": [{"name": b.name, "parent": b.parent.name if b.parent else None,
                       "deform": b.use_deform, "bbone_segments": b.bbone_segments}
                      for b in obj.data.bones],
            "pose_constraints": counts(c.type for bone in obj.pose.bones for c in bone.constraints),
        })
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    report = {
        "blender_version": bpy.app.version_string,
        "blend_file": Path(bpy.data.filepath).name,
        "evidence": "Raw original datablock inventory; not rendered/exported/avatar acceptance.",
        "limits": [
            "No embedded Text blocks are executed by this inspector.",
            "No frame_set, evaluated objects, dependency-graph updates or render calls.",
            "Automatic Python execution is disabled by CLI; safe simple-expression drivers are not globally disabled.",
            "Mesh counts are before modifier evaluation; no wardrobe separability is inferred from names.",
        ],
        "objects_by_type": counts(o.type for o in bpy.data.objects),
        "objects": [object_info(o) for o in bpy.data.objects],
        "materials": [material_info(m) for m in bpy.data.materials],
        "images": [{"name": i.name, "source": i.source,
                    "filename": Path(i.filepath).name, "packed": bool(i.packed_files),
                    "colorspace": i.colorspace_settings.name,
                    "udim_tiles": [t.number for t in i.tiles] if i.source == "TILED" else []}
                   for i in bpy.data.images],
        "actions": [{"name": a.name, "slots": len(a.slots), "layers": len(a.layers)}
                    for a in bpy.data.actions],
        "collections": [{"name": c.name, "hide_render": c.hide_render,
                         "hide_viewport": c.hide_viewport,
                         "object_names": [o.name for o in c.objects]} for c in bpy.data.collections],
        "embedded_text_names": [t.name for t in bpy.data.texts],
        "libraries": [Path(l.filepath).name for l in bpy.data.libraries],
        "scenes": [{"name": s.name, "object_names": [o.name for o in s.objects]}
                   for s in bpy.data.scenes],
    }
    Path(args.out).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"ok": True, "blend_file": report["blend_file"],
                     "objects_by_type": report["objects_by_type"],
                     "material_count": len(report["materials"]),
                     "image_count": len(report["images"]), "action_count": len(report["actions"])}))

main()
