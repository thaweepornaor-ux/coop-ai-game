"""Frozen Snow soft-cloth material candidate; two new views, no geometry/solver edits.
Imports reviewed repository modules only. Original blends/textures remain unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

PAIR_BLOB = "d04197931cf9b705612d4d99d53e79be643e491e"
SOURCE_SHA = "80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
DERIVATIVE_SHA = "9ee52d1c40d56c4909cc255873dddb08aa9fc627e4ce1bc30af12ea99bacb94c"
DERIVATIVE_BYTES = 8450445
PROTOTYPE_BLOB = "059fad9611e95ece356ff6911a9de879dcb3d363"
HELPER_BLOB = "a64c4f14e977a6ae720fb57b01ffa9f69d5703f8"
CONFIG_BLOB = "f0612039b320e8dac77587ec4aecdc2c84618843"
SEED = 1729
COLOR = (0.18, 0.35, 0.45, 1.0)
MATERIAL_NAME = "snow.shirt.soft-cloth.prototype"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n").encode()

def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def write_audit(path,value):
    raw=encoded(value)
    if len(raw)>1048576:
        raise ValueError("soft_cloth_audit_byte_budget_exceeded")
    path.write_bytes(raw)

def load_reviewed():
    path=Path(__file__).with_name("bpy-render-snow-normalmap-pair.py")
    if git_blob(path.read_bytes())!=PAIR_BLOB:
        raise ValueError("reviewed_pair_hash_mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_snow_material_pair",path)
    pair=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pair)
    prototype,helper=pair.load_reviewed_modules()
    if (pair.PROTOTYPE_BLOB!=PROTOTYPE_BLOB or pair.HELPER_BLOB!=HELPER_BLOB
            or pair.CONFIG_BLOB!=CONFIG_BLOB or pair.SEED!=SEED):
        raise ValueError("reviewed_module_identity_mismatch")
    return pair,prototype,helper

def plain_property(value):
    if isinstance(value,(str,bool,int)):
        return value
    if isinstance(value,float):
        if not math.isfinite(value):
            raise ValueError("nonfinite_preservation_value")
        return value
    if value is None:
        return None
    if hasattr(value,"name") and hasattr(value,"id_data"):
        return {"id_name":value.name,"id_type":type(value).__name__}
    try:
        values=list(value)
        if len(values)<=32 and all(isinstance(v,(bool,int,float)) for v in values):
            if not all(not isinstance(v,float) or math.isfinite(v) for v in values):
                raise ValueError("nonfinite_preservation_value")
            return values
    except TypeError:
        pass
    return None

def modifier_signature(modifier):
    result={}
    for prop in modifier.bl_rna.properties:
        name=prop.identifier
        if name=="rna_type" or prop.is_readonly:
            continue
        try:
            value=plain_property(getattr(modifier,name))
        except (AttributeError,RuntimeError):
            continue
        if value is not None:
            result[name]=value
    if hasattr(modifier,"is_bound"):
        result["is_bound"]=bool(modifier.is_bound)
    return result

def data_preservation(bpy,helper,garment):
    records=[]
    for obj in sorted((o for o in bpy.data.objects if o.type=="MESH"),key=lambda o:o.name):
        mesh=obj.data
        state=helper.garment_render_state(obj)
        state.pop("materials",None)
        slots=[]
        for index,slot in enumerate(obj.material_slots):
            if obj==garment and index==0:
                slots.append({"slot":0,"intentional_object_material_override":True})
            else:
                slots.append({"slot":index,"link":slot.link,
                              "material":slot.material.name if slot.material else None})
        extra={"state":state,"data_materials":[m.name if m else None for m in mesh.materials],
            "object_material_slots":slots,
            "polygon_material_indices":[p.material_index for p in mesh.polygons],
            "weights":[[[g.group,float(g.weight)] for g in v.groups] for v in mesh.vertices],
            "uv":[{"name":layer.name,"values":[list(v.uv) for v in layer.data]}
                  for layer in mesh.uv_layers],
            "modifiers":[modifier_signature(m) for m in obj.modifiers]}
        records.append({"object":obj.name,"data":mesh.name,
            "geometry_and_all_key_coordinates":helper.garment_geometry_signature(obj),
            "keys_values_weights_uv_slots_modifiers_sha256":digest(extra)})
    return {"sha256":digest(records),"mesh_object_count":len(records),
            "shirt":helper.garment_geometry_signature(garment),
            "scope":"all loaded mesh positions/key coordinates and values/weights/UV/topology/data material slots/modifiers/transforms; only shirt object slot0 link+material intentionally excluded"}

def shader_signature(pair,material):
    nodes=[]
    if material.node_tree:
        for node in material.node_tree.nodes:
            nodes.append({"name":node.name,"type":node.bl_idname,
                "inputs":[{"socket":s.identifier,"linked":s.is_linked,
                           "default":pair.primitive_default(s)} for s in node.inputs]})
        links=sorted([l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier]
                     for l in material.node_tree.links)
    else:
        links=[]
    return {"material":material.name,"use_nodes":material.use_nodes,
        "diffuse_color":list(material.diffuse_color),"nodes":sorted(nodes,key=lambda n:n["name"]),
        "links":links}

def driver_summary(helper,bpy):
    records=helper.driver_evaluation_status(bpy)
    return {"count":len(records),"active_invalid":sum(not r["muted"] and not r["is_valid"] for r in records),
        "muted":sum(r["muted"] for r in records),
        "status_sha256":digest([{"owner":r["name"],"id_type":r["id_type"],"path":r["path"],
            "index":r["index"],"type":r["type"],"muted":r["muted"],"is_valid":r["is_valid"],
            "native":r["native_without_python"],"targets":r["targets"]} for r in records])}

def verify_override(bpy,garment,data_material_baseline,new_material,principled,output):
    if (garment.material_slots[0].link!="OBJECT"
            or garment.material_slots[0].material!=new_material
            or garment.data.materials[0]!=data_material_baseline
            or len(new_material.node_tree.nodes)!=2
            or len(new_material.node_tree.links)!=1
            or principled.inputs["Normal"].is_linked
            or principled.inputs["Base Color"].is_linked
            or principled.inputs["Roughness"].is_linked
            or principled.inputs["Metallic"].is_linked
            or abs(float(principled.inputs["Roughness"].default_value)-0.8)>1e-6
            or float(principled.inputs["Metallic"].default_value)!=0.0
            or float(principled.inputs["Alpha"].default_value)!=1.0
            or max(abs(a-b) for a,b in zip(principled.inputs["Base Color"].default_value,COLOR))>1e-6):
        raise ValueError("plain_target_material_override_mismatch")
    link=next(iter(new_material.node_tree.links))
    if (link.from_node!=principled or link.from_socket!=principled.outputs["BSDF"]
            or link.to_node!=output or link.to_socket!=output.inputs["Surface"]):
        raise ValueError("plain_target_shader_route_mismatch")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-root",required=True)
    parser.add_argument("--derivative-blend",required=True)
    parser.add_argument("--config",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--emit-preview",action="store_true")
    args=parser.parse_args()
    source_root=Path(args.source_root).resolve(strict=True)
    source=source_root/"snow/original/Snow/snow_v4.2.blend"
    derivative=Path(args.derivative_blend).resolve(strict=True)
    destination=Path(args.out).resolve()
    if (destination.is_relative_to(source_root) or destination.is_relative_to(derivative.parent)
            or source.is_relative_to(destination) or derivative.is_relative_to(destination)):
        raise ValueError("soft_cloth_output_overlaps_inputs")
    if sha(source)!=SOURCE_SHA or derivative.stat().st_size!=DERIVATIVE_BYTES or sha(derivative)!=DERIVATIVE_SHA:
        raise ValueError("frozen_input_hash_mismatch")
    raw_config=Path(args.config).read_bytes()
    if git_blob(raw_config)!=CONFIG_BLOB:
        raise ValueError("reviewed_config_hash_mismatch")
    config=json.loads(raw_config)
    if config["poses"]!={"neutral":[]}:
        raise ValueError("reviewed_neutral_pose_mismatch")
    producer_path=derivative.with_name("prototype-audit.json")
    if producer_path.stat().st_size>16777216:
        raise ValueError("frozen_producer_audit_oversized")
    frozen=json.loads(producer_path.read_text(encoding="utf-8"))
    if (frozen["source_sha256"]!=SOURCE_SHA or frozen["helper_git_blob_sha1"]!=HELPER_BLOB
            or frozen["derivative"]["sha256"]!=DERIVATIVE_SHA
            or frozen["derivative"]["bytes"]!=DERIVATIVE_BYTES
            or frozen["baseline_reference"]["actual_run"]!=38122307127
            or frozen["after_views_rendered"]!=3):
        raise ValueError("frozen_producer_audit_identity_mismatch")
    camera_config=frozen["camera_config"]
    camera_hash=hashlib.sha256(json.dumps(camera_config,sort_keys=True,allow_nan=False).encode()).hexdigest()
    if frozen["baseline_reference"]["camera_config_sha256"]!=camera_hash:
        raise ValueError("frozen_camera_config_hash_mismatch")
    definitions={}
    for name in ("front","neck-crop"):
        matches=[s for s in camera_config if s["name"]==name]
        if len(matches)!=1 or matches[0]["azimuth"]!=0:
            raise ValueError("frozen_candidate_camera_definition_mismatch")
        definitions[name]=matches[0]
    if definitions["neck-crop"]["resolution"]!=[640,480]:
        raise ValueError("frozen_neck_resolution_mismatch")
    destination.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        target=destination/"credits"/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source_root/relative,target)
        credits.append({"file":str(target.relative_to(destination)),"sha256":sha(target),
                        "bytes":target.stat().st_size})
    audit={"purpose":"Two new frozen-camera soft-cloth material candidate views only",
        "source_sha256":SOURCE_SHA,"input_derivative_sha256":DERIVATIVE_SHA,
        "input_derivative_bytes":DERIVATIVE_BYTES,"producer_audit_sha256":sha(producer_path),
        "pair_blob":PAIR_BLOB,"prototype_blob":PROTOTYPE_BLOB,"helper_blob":HELPER_BLOB,
        "config_blob":CONFIG_BLOB,"frozen_camera_config_sha256":camera_hash,
        "camera_definitions":definitions,"credits":credits,"renders":[],"controls":[],
        "used_textures":[],"texture_preparation_complete":False,
        "solver_runs":0,"geometry_edits_performed":False,"models_saved":0,
        "derivative_saved":False,"source_and_derivative_unchanged":False,
        "garment_art_approved":False,"production_glb_approved":False,"animation_approved":False,
        "native_driver_policy_visually_accepted":False,
        "raw_to_evaluated_mapping":"unproven; counts do not establish correspondence",
        "limits":["Plain material intentionally removes original shirt diffuse/normal/roughness graph details.",
            "This candidate does not establish the remaining dark band's cause or repair collar geometry.",
            "No existing baseline is rerendered; these are two new candidate views only.",
            "Other character parts retain external textures at restored CI paths; derivative is not portable or a production GLB.",
            "No rig/pose/animation or full wardrobe/preset acceptance is implied."]}
    audit_path=destination/"soft-cloth-audit.json"
    write_audit(audit_path,audit)
    textures=audit["used_textures"]
    failure=None
    def recheck_inputs_and_textures():
        unchanged=(sha(source)==SOURCE_SHA and sha(derivative)==DERIVATIVE_SHA
                   and sha(producer_path)==audit["producer_audit_sha256"])
        audit["source_and_derivative_unchanged"]=unchanged
        checked=0
        matches=True
        for image in textures:
            for record in image["files"]:
                match=sha(source.parent/"textures"/record["file"])==record["sha256"]
                checked+=1
                matches=matches and match
        expected=audit.get("texture_expected_image_count")
        ready=sum(r.get("size_guard_passed",False) for r in textures)
        complete=(expected==25 and len(textures)==expected and ready==expected
                  and audit.get("texture_preparation_complete",False) and checked==33)
        audit["texture_hash_recheck"]={"checked_file_count":checked,"expected_file_count":33,
            "attempted_image_count":len(textures),"expected_image_count":expected,
            "ready_image_count":ready,"complete":complete,
            "all_checked_files_unchanged":matches if checked else None}
        audit["used_texture_hashes_rechecked"]=complete and matches
        return unchanged and complete and matches
    try:
        pair,prototype,helper=load_reviewed()
        import bpy
        from mathutils import Vector
        if sys.version_info[:2]!=(3,11) or tuple(bpy.app.version)!=(4,5,9):
            raise ValueError("requires_verified_python_3_11_bpy_4_5_9")
        bpy.context.preferences.filepaths.use_scripts_auto_execute=False
        bpy.ops.wm.open_mainfile(filepath=str(derivative),load_ui=False,use_scripts=False)
        policy=helper.disable_animation_and_scripts(bpy)
        audit["native_policy"]={"autoexec":False,"embedded_text_executed":False,
            "native_retained":sum(p["native_drivers_retained"] for p in policy),
            "complex_python_muted":sum(p["complex_python_drivers_muted"] for p in policy)}
        del policy
        objects=[]
        for name in config["mesh_names"]:
            obj=bpy.data.objects.get(name)
            if obj is None or obj.type!="MESH":
                raise ValueError("frozen_scene_character_mesh_missing")
            objects.append(obj)
        scene=bpy.context.scene
        if scene is None or scene.camera is None or scene.render.engine!="CYCLES":
            raise ValueError("frozen_proof_scene_or_camera_missing")
        if any(obj.name not in scene.objects for obj in objects):
            raise ValueError("frozen_character_visibility_membership_mismatch")
        audit["linked_missing_modifier_dependencies"]=pair.ensure_saved_dependency_closure(bpy,scene,objects)
        materials=pair.used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
        images=pair.collect_images(materials)
        audit["texture_expected_image_count"]=len(images)
        def texture_checkpoint():
            audit["texture_attempted_image_count"]=len(textures)
            audit["texture_ready_image_count"]=sum(r.get("size_guard_passed",False) for r in textures)
            write_audit(audit_path,audit)
        pair.relink_and_reload(images,source.parent/"textures",textures,texture_checkpoint)
        audit["texture_preparation_complete"]=True
        if not recheck_inputs_and_textures():
            raise ValueError("frozen_used_texture_count_or_hash_mismatch")
        garment=bpy.data.objects.get("GEO-snow-shirt")
        if (garment not in objects or len(garment.data.vertices)!=1839
                or not garment.data.shape_keys or len(garment.data.shape_keys.key_blocks)!=10
                or not garment.material_slots or not garment.data.materials):
            raise ValueError("frozen_shirt_geometry_or_slot_guard_failed")
        old_material=bpy.data.materials.get("snow.shirt")
        data_material_baseline=garment.data.materials[0]
        slot_zero_polygons=sum(p.material_index==0 for p in garment.data.polygons)
        predicates={"expected_material_exists":old_material is not None,
            "effective_slot_zero_is_expected":old_material is not None
                and garment.material_slots[0].material==old_material,
            "slot_zero_polygons_present":slot_zero_polygons>0,
            "data_slot_zero_is_expected_diagnostic_only":old_material is not None
                and data_material_baseline==old_material}
        audit["target_binding_guard"]={"required_predicates":[
                "expected_material_exists","effective_slot_zero_is_expected","slot_zero_polygons_present"],
            "predicates":predicates,"data_slot_zero_must_equal_expected":False,
            "layout":{"object":garment.name,"object_slot_count":len(garment.material_slots),
                "data_slot_count":len(garment.data.materials),
                "object_slots":[{"index":i,"link":slot.link,
                    "effective_material":slot.material.name if slot.material else None}
                    for i,slot in enumerate(garment.material_slots)],
                "data_materials":[m.name if m else None for m in garment.data.materials],
                "slot_zero_polygon_count":slot_zero_polygons,
                "expected_material":old_material.name if old_material else None,
                "captured_data_material_baseline":data_material_baseline.name if data_material_baseline else None}}
        # Persist every original compound predicate before a material guard can raise.
        write_audit(audit_path,audit)
        if not all(predicates[name] for name in audit["target_binding_guard"]["required_predicates"]):
            raise ValueError("frozen_shirt_slot_zero_material_mismatch")
        if bpy.data.materials.get(MATERIAL_NAME) is not None:
            raise ValueError("candidate_material_name_already_exists")
        old_tree,old_node,old_socket,old_route=pair.find_target(bpy,garment)
        audit["original_target_normal_route"]=old_route
        audit["target_binding_before"]={"object":garment.name,"slot":0,
            "link":garment.material_slots[0].link,"object_material":old_material.name,
            "data_material":data_material_baseline.name if data_material_baseline else None,
            "mesh_data_users":garment.data.users,"material_users":old_material.users,
            "slot_zero_polygon_count":sum(p.material_index==0 for p in garment.data.polygons)}
        scene.cycles.seed=SEED
        scene.cycles.use_animated_seed=False
        height=float(definitions["front"]["ortho_scale"])/1.32
        center=Vector(definitions["front"]["target_world"])
        shots=[{"name":name,"target":Vector(definitions[name]["target_world"]),
                "scale":float(definitions[name]["ortho_scale"]),"angle":0,
                "resolution":tuple(definitions[name]["resolution"])} for name in ("front","neck-crop")]
        camera=scene.camera
        def configure_shot(shot):
            camera.location=shot["target"]+Vector((0,-height*3.5,height*0.02))
            camera.rotation_euler=(shot["target"]-camera.location).to_track_quat("-Z","Y").to_euler()
            camera.data.ortho_scale=shot["scale"]
            scene.render.resolution_x,scene.render.resolution_y=shot["resolution"]
            scene.render.resolution_percentage=100
            bpy.context.view_layer.update()
        expected_location=shots[1]["target"]+Vector((0,-height*3.5,height*0.02))
        expected_rotation=(shots[1]["target"]-expected_location).to_track_quat("-Z","Y")
        if ((camera.location-expected_location).length>1e-5
                or abs(camera.data.ortho_scale-shots[1]["scale"])>1e-6
                or camera.rotation_euler.to_quaternion().rotation_difference(expected_rotation).angle>1e-5):
            raise ValueError("saved_neck_camera_does_not_match_frozen_definition")
        configure_shot(shots[1])
        before_data=data_preservation(bpy,helper,garment)
        before_original_controls=pair.control_snapshot(bpy,scene,[],materials,None,None)
        before_drivers=driver_summary(helper,bpy)
        audit["preservation_before"]=before_data
        audit["original_material_scene_controls_before"]=before_original_controls
        audit["driver_summary_before"]=before_drivers
        audit["original_target_shader_signature"]=shader_signature(pair,old_material)
        audit["evaluated_counts_before"]=pair.evaluated_counts(bpy,objects)
        write_audit(audit_path,audit)
        new_material=bpy.data.materials.new(MATERIAL_NAME)
        new_material.use_nodes=True
        new_material.diffuse_color=COLOR
        new_material.node_tree.nodes.clear()
        principled=new_material.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        output=new_material.node_tree.nodes.new("ShaderNodeOutputMaterial")
        principled.inputs["Base Color"].default_value=COLOR
        principled.inputs["Roughness"].default_value=0.8
        principled.inputs["Metallic"].default_value=0.0
        principled.inputs["Alpha"].default_value=1.0
        new_material.node_tree.links.new(principled.outputs["BSDF"],output.inputs["Surface"])
        garment.material_slots[0].link="OBJECT"
        garment.material_slots[0].material=new_material
        verify_override(bpy,garment,data_material_baseline,new_material,principled,output)
        audit["target_binding_after"]={"object":garment.name,"slot":0,"link":"OBJECT",
            "object_material":new_material.name,"data_material":garment.data.materials[0].name if garment.data.materials[0] else None}
        audit["new_target_shader_signature"]=shader_signature(pair,new_material)
        audit["intentional_changes"]={"new_material":new_material.name,"object_slot_override_only":True,
            "base_color_scene_linear_rgba":list(COLOR),"roughness":0.8,"metallic":0,
            "alpha":1,"normal_unlinked":True,"nodes":["ShaderNodeBsdfPrincipled","ShaderNodeOutputMaterial"],
            "links":["Principled BSDF.BSDF -> Material Output.Surface"],
            "old_shirt_graph_removed_from_render_intentionally":True,
            "no_bitmap_editing_no_attribute_no_bake":True}
        if data_preservation(bpy,helper,garment)!=before_data:
            raise ValueError("source_mesh_keys_weights_uv_topology_or_modifiers_changed")
        if pair.control_snapshot(bpy,scene,[],materials,None,None)["sha256"]!=before_original_controls["sha256"]:
            raise ValueError("original_materials_rig_scene_or_camera_changed")
        write_audit(audit_path,audit)
        candidate_materials=pair.used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
        new_shader_hash=digest(audit["new_target_shader_signature"])
        for shot in shots:
            configure_shot(shot)
            before=pair.control_snapshot(bpy,scene,objects,candidate_materials,None,None)
            prototype.render_phase(helper,bpy,destination,scene,camera,center,height,
                [shot],"soft-cloth",audit,args.emit_preview)
            after=pair.control_snapshot(bpy,scene,objects,candidate_materials,None,None)
            if before["sha256"]!=after["sha256"]:
                raise ValueError("candidate_controls_changed_during_render")
            verify_override(bpy,garment,data_material_baseline,new_material,principled,output)
            if digest(shader_signature(pair,new_material))!=new_shader_hash:
                raise ValueError("candidate_target_shader_changed_during_render")
            record={"view":shot["name"],"before_sha256":before["sha256"],
                "after_sha256":after["sha256"],"matched_frozen_camera":True,
                "fixed_seed":SEED,"use_animated_seed":False}
            audit["controls"].append(record)
            write_audit(audit_path,audit)
            print("SNOW_SOFT_CLOTH_CONTROL "+encoded(record).decode().strip(),flush=True)
        configure_shot(shots[1])
        after_data=data_preservation(bpy,helper,garment)
        after_controls=pair.control_snapshot(bpy,scene,[],materials,None,None)
        after_drivers=driver_summary(helper,bpy)
        audit["preservation_after"]=after_data
        audit["original_material_scene_controls_after"]=after_controls
        audit["driver_summary_after"]=after_drivers
        audit["evaluated_counts_after"]=pair.evaluated_counts(bpy,objects)
        audit["preservation_passed"]=(before_data==after_data
            and before_original_controls["sha256"]==after_controls["sha256"]
            and before_drivers==after_drivers
            and audit["evaluated_counts_before"]==audit["evaluated_counts_after"])
        if not audit["preservation_passed"]:
            raise ValueError("soft_cloth_preservation_guard_failed")
        if len(audit["renders"])!=2 or [r["view"] for r in audit["renders"]]!=["front","neck-crop"]:
            raise ValueError("candidate_render_count_or_views_mismatch")
        if not recheck_inputs_and_textures():
            raise ValueError("immutable_inputs_or_used_textures_changed_before_save")
        write_audit(audit_path,audit)
        working=destination/"snow-soft-cloth-prototype.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(working),check_existing=False)
        audit["models_saved"]=1
        audit["derivative_saved"]=True
        audit["derivative"]={"file":working.name,"bytes":working.stat().st_size,
            "sha256":sha(working),"textures_packed":False,
            "external_texture_paths_portable":False,
            "requires_original_character_texture_relink":True}
        audit["candidate_completed"]=True
    except Exception as error:
        failure=error
        code=error.args[0] if isinstance(error,ValueError) and len(error.args)==1 and isinstance(error.args[0],str) else None
        if not code or len(code)>100 or not all(c.islower() or c=="_" for c in code):
            code=None
        audit["failure"]={"error_type":type(error).__name__,"error_code":code}
        raise
    finally:
        read_only_ok=recheck_inputs_and_textures()
        write_audit(audit_path,audit)
        marker={"candidate_completed":audit.get("candidate_completed",False),
            "renders":len(audit["renders"]),"views":[r["view"] for r in audit["renders"]],
            "models_saved":audit["models_saved"],"derivative_saved":audit["derivative_saved"],
            "derivative":audit.get("derivative"),"intentional_changes":audit.get("intentional_changes"),
            "target_binding_guard":audit.get("target_binding_guard"),
            "target_binding_before":audit.get("target_binding_before"),
            "target_binding_after":audit.get("target_binding_after"),
            "preservation_passed":audit.get("preservation_passed",False),
            "shirt_geometry":audit.get("preservation_after",audit.get("preservation_before",{})).get("shirt"),
            "per_view_control_hashes":audit["controls"],"native_policy":audit.get("native_policy"),
            "driver_before":audit.get("driver_summary_before"),"driver_after":audit.get("driver_summary_after"),
            "source_and_derivative_unchanged":audit["source_and_derivative_unchanged"],
            "texture_hash_recheck":audit["texture_hash_recheck"],"failure":audit.get("failure"),
            "source_sha256":SOURCE_SHA,"input_derivative_sha256":DERIVATIVE_SHA,
            "solver_runs":0,"geometry_edits_performed":False,"garment_art_approved":False,
            "production_glb_approved":False,"animation_approved":False,
            "external_textures_portable":False,"raw_to_evaluated_mapping":"unproven"}
        if len(encoded(marker))>24000:
            raise ValueError("soft_cloth_stdout_byte_budget_exceeded")
        print("SNOW_SOFT_CLOTH_PROTOTYPE "+encoded(marker).decode().strip(),flush=True)
        if failure is None and not read_only_ok:
            raise ValueError("soft_cloth_final_readonly_check_failed")

if __name__=="__main__":
    main()
