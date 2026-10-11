"""Inspect raw source IDs in a fresh official bpy process, without activating a source scene."""
import argparse
import json
from pathlib import Path
import runpy
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--inspector", required=True)
    args = parser.parse_args()
    import bpy
    if sys.version_info[:2] != (3, 11) or tuple(bpy.app.version) != (4, 5, 9):
        raise RuntimeError("requires_python_3_11_and_bpy_4_5_9")
    source = Path(args.blend).resolve(strict=True)
    inspector = Path(args.inspector).resolve(strict=True)
    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    if bpy.context.preferences.filepaths.use_scripts_auto_execute:
        raise RuntimeError("automatic_scripts_must_be_disabled")
    if len(bpy.data.objects):
        raise RuntimeError("factory_context_not_empty")
    # bpy as a module has no CLI --disable-depsgraph-on-file-load switch.
    # A raw library load avoids open_mainfile and never activates source scenes.
    # Scripts remain disabled in preferences; no Text content is read or executed.
    id_categories = ("objects", "collections", "meshes", "armatures", "materials",
                     "images", "actions", "node_groups", "curves", "fonts")
    source_table = {}
    with bpy.data.libraries.load(str(source), link=False) as (data_from, data_to):
        for category in id_categories:
            if hasattr(data_from, category) and hasattr(data_to, category):
                names = list(getattr(data_from, category))
                source_table[category] = names
                setattr(data_to, category, names)
        source_table["scenes"] = list(data_from.scenes)
        source_table["embedded_text_names"] = list(data_from.texts)
        # Do not request source scenes, worlds, workspace/UI data or Text blocks.
    active_objects = list(bpy.context.scene.objects)
    if active_objects:
        raise RuntimeError("source_objects_must_remain_unlinked_from_active_scene")
    argv_before = sys.argv
    try:
        sys.argv = [str(inspector), "--", "--out", str(output)]
        runpy.run_path(str(inspector), run_name="__main__")
    finally:
        sys.argv = argv_before
    report = json.loads(output.read_text(encoding="utf-8"))
    report["blend_file"] = source.name
    report["source_loading"] = {
        "mode": "raw_unlinked_library_ids",
        "source_filename": source.name,
        "python_version": sys.version.split()[0],
        "use_scripts_auto_execute": False,
        "open_mainfile_called": False,
        "source_scene_activated": False,
        "active_scene_object_count": len(active_objects),
        "text_blocks_requested": False,
        "source_id_table": source_table,
    }
    report["embedded_text_names"] = source_table["embedded_text_names"]
    report["loaded_text_names"] = [text.name for text in bpy.data.texts]
    report["factory_scenes"] = report.pop("scenes", [])
    report["source_scene_names"] = source_table["scenes"]
    report["evidence"] = (
        "Raw original library ID inventory; source scenes were not activated. "
        "Not rendered, evaluated, exported or accepted as a production avatar."
    )
    report["limits"] = [
        "Automatic Python execution disabled before library load; no embedded Text is executed.",
        "No frame_set, evaluated_get, explicit dependency-graph update or render call.",
        "Source objects and collections are imported as unlinked IDs, not activated in a source scene.",
        "Simple-expression drivers are retained as raw metadata; this is not a sandbox guarantee.",
        "Source scene membership/UI state is not imported; source scene/Text names are from the library table.",
        "Mesh counts precede modifier evaluation; clothing separability, animation and face variation remain unproven.",
    ]
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({"RAW_LIBRARY_POLICY": {
        "blender_version": report["blender_version"],
        "automatic_python_execution": False,
        "source_scene_activated": False, "rendered": False,
    }}), flush=True)

if __name__ == "__main__":
    main()
