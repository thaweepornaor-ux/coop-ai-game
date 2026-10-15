"""Two matched real Snow neck crops: only the linked shirt NormalMap strength changes.
Loads hash-pinned repository helpers; never calls prototype main or solves/edits/saves a model.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import sys

SOURCE_SHA = "80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
DERIVATIVE_SHA = "9ee52d1c40d56c4909cc255873dddb08aa9fc627e4ce1bc30af12ea99bacb94c"
DERIVATIVE_BYTES = 8450445
PROTOTYPE_BLOB = "059fad9611e95ece356ff6911a9de879dcb3d363"
HELPER_BLOB = "a64c4f14e977a6ae720fb57b01ffa9f69d5703f8"
CONFIG_BLOB = "f0612039b320e8dac77587ec4aecdc2c84618843"
SEED = 1729

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n").encode()

def write_audit(path,value):
    data=encoded(value)
    if len(data)>1048576:
        raise ValueError("pair_audit_byte_budget_exceeded")
    path.write_bytes(data)

def vector(value):
    result=[float(v) for v in value]
    if not all(math.isfinite(v) for v in result):
        raise ValueError("nonfinite_control_value")
    return result

def load_reviewed_modules():
    path=Path(__file__).with_name("bpy-prototype-snow-crewneck.py")
    if git_blob(path.read_bytes())!=PROTOTYPE_BLOB:
        raise ValueError("reviewed_prototype_hash_mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_snow_prototype",path)
    prototype=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prototype)
    helper=prototype.load_helper()
    if prototype.HELPER_BLOB!=HELPER_BLOB:
        raise ValueError("reviewed_helper_identity_mismatch")
    return prototype,helper

def used_materials(objects):
    result={}
    for obj in objects:
        for slot in obj.material_slots:
            if slot.material:
                result[slot.material.name]=slot.material
    return [result[name] for name in sorted(result)]

def collect_images(materials):
    result,seen={},set()
    def visit(tree):
        if tree is None or tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        for node in tree.nodes:
            if node.type=="SCRIPT":
                raise ValueError("script_shader_not_allowed")
            image=getattr(node,"image",None)
            if image:
                result[image.name]=image
            visit(getattr(node,"node_tree",None))
    for material in materials:
        visit(material.node_tree)
    return [result[name] for name in sorted(result)]

def relink_and_reload(images,texture_root,records,checkpoint):
    texture_root=texture_root.resolve(strict=True)
    for image in images:
        filename=str(image.filepath).replace("\\","/").split("/")[-1]
        record={"image":image.name,"filename":filename,"source":image.source,"files":[],
            "stage":"start","packed_files_before":len(image.packed_files),
            "filepath_inside_original_textures":False,"reload_requested":False,
            "reload_completed":False,"size_acquisition_requested":False,"size_guard_passed":False}
        # Shared audit list is populated BEFORE any reload/guard can raise.
        records.append(record)
        checkpoint()
        if image.source not in ("FILE","TILED"):
            raise ValueError("used_image_requires_verified_external_source")
        if not filename or filename in (".",".."):
            raise ValueError("used_image_filename_missing")
        candidate=texture_root/filename
        if candidate.parent.resolve()!=texture_root:
            raise ValueError("used_image_path_escapes_original_textures")
        filenames=[]
        if image.source=="TILED":
            if "<UDIM>" not in filename:
                raise ValueError("used_tiled_image_missing_udim_token")
            for tile in image.tiles:
                filenames.append(texture_root/filename.replace("<UDIM>",str(tile.number)))
            if not filenames:
                raise ValueError("used_tiled_image_has_no_declared_tiles")
        else:
            filenames=[candidate]
        for path in filenames:
            resolved=path.resolve(strict=True)
            if not resolved.is_relative_to(texture_root) or not resolved.is_file():
                raise ValueError("used_texture_not_inside_verified_originals")
            record["files"].append({"file":resolved.name,"sha256":sha(resolved),
                                    "bytes":resolved.stat().st_size})
        record["filepath_inside_original_textures"]=True
        record["stage"]="before_reload"
        record["has_data_before_reload"]=bool(image.has_data)
        image.filepath=str(candidate)
        record["reload_requested"]=True
        checkpoint()
        image.reload()
        record["reload_completed"]=True
        record["stage"]="after_reload"
        record["has_data_after_reload"]=bool(image.has_data)
        record["source_after_reload"]=image.source
        record["packed_files_after"]=len(image.packed_files)
        checkpoint()
        # Official v4.5.9 RNA: has_data checks loaded buffers; size acquires/releases
        # an image buffer. Access size explicitly before the unchanged readiness test.
        record["size_acquisition_requested"]=True
        checkpoint()
        size=list(image.size)
        record["size"]=size
        record["has_data_after_size_acquisition"]=bool(image.has_data)
        record["stage"]="after_size_acquisition"
        record["size_guard_passed"]=(record["has_data_after_size_acquisition"]
            and len(size)==2 and min(size)>0)
        checkpoint()
        marker={key:record.get(key) for key in (
            "image","filename","source","source_after_reload","stage",
            "filepath_inside_original_textures","packed_files_before","packed_files_after",
            "has_data_before_reload","has_data_after_reload",
            "size_acquisition_requested","size","has_data_after_size_acquisition","size_guard_passed")}
        marker["verified_file_count"]=len(record["files"])
        marker["verified_file_sha256"]=[f["sha256"] for f in record["files"]]
        marker_text=json.dumps(marker,allow_nan=False)
        if len(marker_text.encode())>4096:
            raise ValueError("texture_state_stdout_byte_budget_exceeded")
        print("SNOW_TEXTURE_RELOAD_STATE "+marker_text,flush=True)
        if (not record["has_data_after_size_acquisition"] or len(size)!=2 or min(size)<=0):
            raise ValueError("used_image_reload_has_no_pixel_data")
        record["stage"]="ready"
        checkpoint()
    return records

def find_target(bpy,garment):
    material=bpy.data.materials.get("snow.shirt")
    if material is None or all(slot.material!=material for slot in garment.material_slots):
        raise ValueError("expected_shirt_material_not_assigned")
    targets,seen=[],set()
    def visit(tree,path):
        if tree is None or tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        for node in tree.nodes:
            if node.type=="NORMAL_MAP":
                color=node.inputs.get("Color")
                strength=node.inputs.get("Strength")
                output=node.outputs.get("Normal")
                incoming=[link for link in color.links if link.from_node.type=="TEX_IMAGE"
                          and link.from_socket.name=="Color"] if color else []
                outgoing=[link for link in output.links if link.to_node.type=="BSDF_PRINCIPLED"
                          and link.to_socket.name=="Normal"] if output else []
                exact=[link for link in incoming if link.from_node.image and
                       str(link.from_node.image.filepath).replace("\\","/").split("/")[-1]=="shirt_normal.png"]
                if exact and outgoing:
                    if (strength is None or strength.is_linked or len(exact)!=1 or len(outgoing)!=1
                            or node.space!="TANGENT" or node.uv_map!="UVMap"):
                        raise ValueError("shirt_normalmap_control_route_mismatch")
                    if float(strength.default_value)!=1.0:
                        raise ValueError("frozen_normalmap_strength_not_one")
                    animation=tree.animation_data
                    strength_path=strength.path_from_id("default_value")
                    if animation and any(f.data_path==strength_path and not f.mute for f in animation.drivers):
                        raise ValueError("target_normalmap_strength_has_active_driver")
                    targets.append((tree,node,strength,{
                        "material":material.name,"tree":path,"node":node.name,
                        "type":node.bl_idname,"space":node.space,"uv_map":node.uv_map,
                        "image":exact[0].from_node.image.name,"image_filename":"shirt_normal.png",
                        "from_node":exact[0].from_node.name,"from_socket":"Color",
                        "to_node":outgoing[0].to_node.name,"to_socket":"Normal",
                        "strength_path":strength_path,"strength_unlinked":True}))
            visit(getattr(node,"node_tree",None),path+"/"+node.name)
    visit(material.node_tree,material.name)
    if len(targets)!=1:
        raise ValueError("linked_shirt_normalmap_target_not_unique")
    return targets[0]

def ensure_saved_dependency_closure(bpy,scene,selected):
    pending=list(selected)
    scanned=set()
    linked=[]
    while pending:
        owner=pending.pop()
        if owner.as_pointer() in scanned:
            continue
        scanned.add(owner.as_pointer())
        for modifier in owner.modifiers:
            for field in ("object","target"):
                dependency=getattr(modifier,field,None)
                if not isinstance(dependency,bpy.types.Object):
                    continue
                if dependency.name not in scene.objects:
                    scene.collection.objects.link(dependency)
                    linked.append(dependency.name)
                if dependency.type=="MESH" and dependency not in selected:
                    dependency.hide_render=True
                    pending.append(dependency)
    return sorted(set(linked))

def primitive_default(socket):
    value=getattr(socket,"default_value",None)
    if isinstance(value,(bool,int,float)):
        return value if not isinstance(value,float) or math.isfinite(value) else None
    if value is not None and not isinstance(value,str):
        try:
            result=list(value)
            if len(result)<=4 and all(isinstance(v,(bool,int,float)) and math.isfinite(v) for v in result):
                return result
        except (TypeError,ValueError):
            pass
    return None

def control_snapshot(bpy,scene,objects,materials,target_node,target_socket):
    trees,seen=[],set()
    def visit(tree):
        if tree is None or tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        nodes=[]
        for node in tree.nodes:
            inputs=[]
            for socket in node.inputs:
                excluded=node==target_node and socket==target_socket
                inputs.append({"identifier":socket.identifier,"linked":socket.is_linked,
                               "default":"EXCLUDED_TARGET_STRENGTH" if excluded else primitive_default(socket)})
            entry={"name":node.name,"type":node.bl_idname,"inputs":inputs}
            for field in ("operation","blend_type","data_type","uv_map","space","invert",
                          "interpolation","projection","extension"):
                value=getattr(node,field,None)
                if isinstance(value,(str,int,float,bool)):
                    entry[field]=value
            image=getattr(node,"image",None)
            if image:
                entry["image"]={"name":image.name,"filepath":image.filepath,
                    "colorspace":image.colorspace_settings.name,"alpha_mode":image.alpha_mode}
            child=getattr(node,"node_tree",None)
            if child:
                entry["node_group"]=child.name
                visit(child)
            nodes.append(entry)
        links=sorted((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier)
                     for l in tree.links)
        trees.append({"name":tree.name,"nodes":nodes,"links":links})
    for material in materials:
        visit(material.node_tree)
    visit(scene.world.node_tree if scene.world else None)
    for light_object in scene.objects:
        if light_object.type=="LIGHT":
            visit(light_object.data.node_tree)
    geometry=hashlib.sha256()
    poses=hashlib.sha256()
    for obj in sorted(objects,key=lambda o:o.name):
        geometry.update(obj.name.encode())
        for vertex in obj.data.vertices:
            geometry.update(struct.pack("<3d",*vector(vertex.co)))
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                geometry.update(key.name.encode()+struct.pack("<d",float(key.value)))
    for obj in sorted((o for o in scene.objects if o.type=="ARMATURE"),key=lambda o:o.name):
        poses.update(obj.name.encode())
        for bone in obj.pose.bones:
            poses.update(bone.name.encode())
            for row in bone.matrix:
                poses.update(struct.pack("<4d",*vector(row)))
    camera=scene.camera
    lights=[{"name":o.name,"type":o.data.type,"energy":o.data.energy,"color":vector(o.data.color),
             "size":getattr(o.data,"size",None),"shape":getattr(o.data,"shape",None),
             "matrix":[vector(row) for row in o.matrix_world]}
            for o in sorted(scene.objects,key=lambda o:o.name) if o.type=="LIGHT"]
    state={"camera":{"name":camera.name,"type":camera.data.type,"ortho_scale":camera.data.ortho_scale,
                     "lens":camera.data.lens,"shift":[camera.data.shift_x,camera.data.shift_y],
                     "clip":[camera.data.clip_start,camera.data.clip_end],
                     "dof_use":camera.data.dof.use_dof,"dof_distance":camera.data.dof.focus_distance,
                     "matrix":[vector(row) for row in camera.matrix_world]},
        "scene_objects":[{"name":o.name,"type":o.type,"hide_render":o.hide_render,
                          "matrix":[vector(row) for row in o.matrix_world]}
                         for o in sorted(scene.objects,key=lambda o:o.name)],
        "lights":lights,"world":scene.world.name if scene.world else None,
        "material_slots":{o.name:[s.material.name if s.material else None for s in o.material_slots]
                          for o in objects},
        "node_trees":sorted(trees,key=lambda t:t["name"]),
        "geometry_and_key_values_sha256":geometry.hexdigest(),"pose_matrices_sha256":poses.hexdigest(),
        "render":{"engine":scene.render.engine,"resolution":[scene.render.resolution_x,
                     scene.render.resolution_y,scene.render.resolution_percentage],
                  "samples":scene.cycles.samples,"device":scene.cycles.device,
                  "seed":scene.cycles.seed,"use_animated_seed":scene.cycles.use_animated_seed,
                  "denoising":scene.cycles.use_denoising,
                  "adaptive_sampling":scene.cycles.use_adaptive_sampling,
                  "adaptive_threshold":scene.cycles.adaptive_threshold,
                  "view_transform":scene.view_settings.view_transform,"look":scene.view_settings.look,
                  "exposure":scene.view_settings.exposure,"gamma":scene.view_settings.gamma}}
    return {"sha256":hashlib.sha256(encoded(state)).hexdigest(),
            "geometry_and_key_values_sha256":geometry.hexdigest(),"pose_matrices_sha256":poses.hexdigest(),
            "camera":state["camera"],"render":state["render"],
            "scope":"camera/render/light/world/object transforms/visible material node numeric defaults and links/used images/raw geometry/key values/pose; target strength excluded"}

def evaluated_counts(bpy,objects):
    depsgraph=bpy.context.evaluated_depsgraph_get()
    result=[]
    for obj in objects:
        evaluated=obj.evaluated_get(depsgraph)
        result.append({"object":obj.name,"raw_vertices":len(obj.data.vertices),
                       "raw_polygons":len(obj.data.polygons),
                       "evaluated_vertices":len(evaluated.data.vertices),
                       "evaluated_polygons":len(evaluated.data.polygons),
                       "raw_to_evaluated_mapping":"unproven; counts do not establish correspondence"})
    return result

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
        raise ValueError("pair_output_overlaps_inputs")
    if sha(source)!=SOURCE_SHA or derivative.stat().st_size!=DERIVATIVE_BYTES or sha(derivative)!=DERIVATIVE_SHA:
        raise ValueError("frozen_input_hash_mismatch")
    raw_config=Path(args.config).read_bytes()
    if git_blob(raw_config)!=CONFIG_BLOB:
        raise ValueError("reviewed_config_hash_mismatch")
    config=json.loads(raw_config)
    frozen_audit_path=derivative.with_name("prototype-audit.json")
    if frozen_audit_path.stat().st_size>16777216:
        raise ValueError("frozen_producer_audit_oversized")
    frozen=json.loads(frozen_audit_path.read_text(encoding="utf-8"))
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
    neck=[s for s in camera_config if s["name"]=="neck-crop"]
    front=[s for s in camera_config if s["name"]=="front"]
    if (len(neck)!=1 or len(front)!=1 or neck[0]["resolution"]!=[640,480]
            or neck[0]["azimuth"]!=0 or config["poses"]!={"neutral":[]}):
        raise ValueError("frozen_neck_camera_definition_mismatch")
    destination.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        target=destination/"credits"/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source_root/relative,target)
        credits.append({"file":str(target.relative_to(destination)),"sha256":sha(target),
                        "bytes":target.stat().st_size})
    audit={"purpose":"Matched NormalMap 1/0 neck crops only","source_sha256":SOURCE_SHA,
        "derivative_sha256":DERIVATIVE_SHA,"producer_audit_sha256":sha(frozen_audit_path),
        "prototype_blob":PROTOTYPE_BLOB,"helper_blob":HELPER_BLOB,"config_blob":CONFIG_BLOB,
        "frozen_camera_config_sha256":camera_hash,"camera_definition":neck[0],"credits":credits,
        "renders":[],"controls":[],"source_and_derivative_unchanged":False,
        "normal_strength_restored":False,"geometry_edits_performed":False,"solver_runs":0,
        "models_saved":0,"garment_art_approved":False,"production_glb_approved":False,
        "animation_approved":False,"raw_to_evaluated_mapping":"unproven",
        "limits":["Normal-off does not prove a sole geometric cause or accept the existing raw fold.",
                  "Rendered normals include native modifiers; raw vertex IDs are not evaluated IDs.",
                  "Texture files are restored read-only originals; used-file SHA256 is rechecked.",
                  "The two controls share fixed RNG settings; no old full-body baseline is rerendered."]}
    audit_path=destination/"normalmap-pair-audit.json"
    write_audit(audit_path,audit)
    socket=None
    original_strength=None
    textures=[]
    failure=None
    try:
        prototype,helper=load_reviewed_modules()
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
        audit["linked_missing_modifier_dependencies"]=ensure_saved_dependency_closure(bpy,scene,objects)
        materials=used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
        images=collect_images(materials)
        audit["used_textures"]=textures
        audit["texture_expected_image_count"]=len(images)
        audit["texture_preparation_complete"]=False
        def checkpoint_texture_state():
            audit["texture_attempted_image_count"]=len(textures)
            audit["texture_ready_image_count"]=sum(r.get("size_guard_passed",False) for r in textures)
            write_audit(audit_path,audit)
        relink_and_reload(images,source.parent/"textures",textures,checkpoint_texture_state)
        audit["texture_preparation_complete"]=True
        checkpoint_texture_state()
        tree,node,socket,target=find_target(bpy,bpy.data.objects["GEO-snow-shirt"])
        original_strength=float(socket.default_value)
        audit["normalmap_target"]=target
        scene.cycles.seed=SEED
        scene.cycles.use_animated_seed=False
        height=float(front[0]["ortho_scale"])/1.32
        shot={"name":"neck-crop","target":Vector(neck[0]["target_world"]),
              "scale":float(neck[0]["ortho_scale"]),"angle":0,"resolution":(640,480)}
        center=Vector(front[0]["target_world"])
        camera=scene.camera
        # Reconstruct only the saved producer camera; no bounds are recomputed.
        expected_location=shot["target"]+Vector((0,-height*3.5,height*0.02))
        if (camera.location-expected_location).length>1e-5 or abs(camera.data.ortho_scale-shot["scale"])>1e-6:
            raise ValueError("saved_camera_does_not_match_frozen_neck_definition")
        expected_rotation=(shot["target"]-expected_location).to_track_quat("-Z","Y")
        if camera.rotation_euler.to_quaternion().rotation_difference(expected_rotation).angle>1e-5:
            raise ValueError("saved_camera_rotation_does_not_match_frozen_neck_definition")
        # Canonicalize the same saved camera formula before hashing both controls.
        camera.location=expected_location
        camera.rotation_euler=expected_rotation.to_euler()
        camera.data.ortho_scale=shot["scale"]
        scene.render.resolution_x,scene.render.resolution_y=shot["resolution"]
        scene.render.resolution_percentage=100
        bpy.context.view_layer.update()
        garment=bpy.data.objects["GEO-snow-shirt"]
        geometry_before=helper.garment_geometry_signature(garment)
        baseline_control=control_snapshot(bpy,scene,objects,materials,node,socket)
        audit["control_reference"]=baseline_control
        audit["evaluated_counts_before"]=evaluated_counts(bpy,objects)
        for phase,strength in (("normal-on",1.0),("normal-off",0.0)):
            socket.default_value=strength
            bpy.context.view_layer.update()
            before=control_snapshot(bpy,scene,objects,materials,node,socket)
            if before["sha256"]!=baseline_control["sha256"]:
                raise ValueError("non_target_controls_changed_before_render")
            audit["active_normalmap_strength"]=strength
            prototype.render_phase(helper,bpy,destination,scene,camera,center,height,
                                   [shot],phase,audit,args.emit_preview)
            after=control_snapshot(bpy,scene,objects,materials,node,socket)
            if after["sha256"]!=baseline_control["sha256"]:
                raise ValueError("non_target_controls_changed_after_render")
            record={"phase":phase,"normalmap_strength":strength,
                    "control_hash_before":before["sha256"],"control_hash_after":after["sha256"],
                    "all_hashed_non_target_controls_match":True}
            audit["controls"].append(record)
            print("SNOW_NORMALMAP_CONTROL "+json.dumps(record),flush=True)
        if helper.garment_geometry_signature(garment)!=geometry_before:
            raise ValueError("raw_garment_geometry_changed")
        audit["raw_garment_geometry_unchanged"]=True
        audit["evaluated_counts_after"]=evaluated_counts(bpy,objects)
        if audit["evaluated_counts_before"]!=audit["evaluated_counts_after"]:
            raise ValueError("evaluated_mesh_counts_changed_between_controls")
        audit["pair_completed"]=True
    except Exception as error:
        failure=error
        code=error.args[0] if isinstance(error,ValueError) and len(error.args)==1 and isinstance(error.args[0],str) else None
        if not code or len(code)>100 or not all(c.islower() or c=="_" for c in code):
            code=None
        audit["failure"]={"error_type":type(error).__name__,"error_code":code}
        raise
    finally:
        if socket is not None and original_strength is not None:
            socket.default_value=original_strength
            audit["normal_strength_restored"]=float(socket.default_value)==original_strength
        unchanged=sha(source)==SOURCE_SHA and sha(derivative)==DERIVATIVE_SHA
        audit["source_and_derivative_unchanged"]=unchanged
        texture_unchanged=True
        checked_files=0
        for image in textures:
            for record in image["files"]:
                path=source.parent/"textures"/record["file"]
                matches=sha(path)==record["sha256"]
                texture_unchanged=texture_unchanged and matches
                checked_files+=1
        expected_images=audit.get("texture_expected_image_count")
        ready_images=sum(r.get("size_guard_passed",False) for r in textures)
        recheck_complete=(expected_images is not None and expected_images>0
            and len(textures)==expected_images and ready_images==expected_images
            and audit.get("texture_preparation_complete",False) and checked_files>0)
        audit["texture_hash_recheck"]={"checked_file_count":checked_files,
            "attempted_image_count":len(textures),"ready_image_count":ready_images,
            "expected_image_count":expected_images,"complete":recheck_complete,
            "all_checked_files_unchanged":texture_unchanged if checked_files else None}
        audit["used_texture_hashes_rechecked"]=recheck_complete and texture_unchanged
        write_audit(audit_path,audit)
        marker={"pair_completed":audit.get("pair_completed",False),
            "renders":len(audit["renders"]),"control_phases":[p["phase"] for p in audit["controls"]],
            "control_hash":audit.get("control_reference",{}).get("sha256"),
            "target":audit.get("normalmap_target"),"normal_strength_restored":audit["normal_strength_restored"],
            "source_and_derivative_unchanged":unchanged,
            "used_texture_hashes_rechecked":audit["used_texture_hashes_rechecked"],
            "texture_hash_recheck":audit["texture_hash_recheck"],
            "evaluated_counts":audit.get("evaluated_counts_after",audit.get("evaluated_counts_before")),
            "failure":audit.get("failure"),"models_saved":0,"solver_runs":0,
            "garment_art_approved":False,"production_glb_approved":False,"animation_approved":False}
        if len(encoded(marker))>24000:
            raise ValueError("pair_stdout_byte_budget_exceeded")
        print("SNOW_NORMALMAP_PAIR "+encoded(marker).decode().strip(),flush=True)
        if failure is None and (not unchanged or not audit["used_texture_hashes_rechecked"]
                                or not audit["normal_strength_restored"]):
            raise ValueError("pair_cleanup_or_readonly_input_check_failed")

if __name__=="__main__":
    main()
