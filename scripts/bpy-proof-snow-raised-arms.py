"""Read-only frozen Snow raised-arm pose proof: two posed renders, no blend save.
Only four verified arm controls change. Face controls are inventoried, never posed.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

SOFT_BLOB="405a46b744084975adbe23f59d494cdc29d5e0a1"
PAIR_BLOB="d04197931cf9b705612d4d99d53e79be643e491e"
PROTOTYPE_BLOB="059fad9611e95ece356ff6911a9de879dcb3d363"
HELPER_BLOB="a64c4f14e977a6ae720fb57b01ffa9f69d5703f8"
CONFIG_BLOB="f0612039b320e8dac77587ec4aecdc2c84618843"
SOURCE_SHA="80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
INPUT_SHA="02e4f1300a90426dcfc83621020df40af898a3671d2fc970b9e2d9a39788031d"
INPUT_BYTES=8468919
SEED=1729
FACES=("MSTR-Eyebrow.L","MSTR-Eyebrow.R","MSTR-Eyebrow_Z.L","MSTR-Eyebrow_Z.R",
       "OuterLip_Corner.L","OuterLip_Corner.R","MSTR-Mouth","TGT-Eyes")
ARMS=("IK-Wrist.L","IK-Wrist.R","POLE-UpperArm.L","POLE-UpperArm.R")
MODES={"XYZ","XZY","YXZ","YZX","ZXY","ZYX","QUATERNION"}
TOL=0.0001

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n").encode()

def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def write_audit(path,value):
    raw=encoded(value)
    if len(raw)>1048576:
        raise ValueError("raised_arm_audit_byte_budget_exceeded")
    path.write_bytes(raw)

def plain(value,depth=0):
    if depth>8:
        raise ValueError("custom_property_nesting_exceeded")
    if isinstance(value,(str,bool,int)) or value is None:
        return value
    if isinstance(value,float):
        if not math.isfinite(value):
            raise ValueError("nonfinite_runtime_value")
        return value
    if hasattr(value,"keys"):
        return {str(k):plain(value[k],depth+1) for k in value.keys()}
    try:
        return [plain(v,depth+1) for v in value]
    except TypeError:
        raise ValueError("unsupported_custom_property_value")

def matrix(value):
    return [[float(v) for v in row] for row in value]

def matrix_error(a,b):
    return max(abs(float(a[i][j])-float(b[i][j])) for i in range(4) for j in range(4))

def load_reviewed():
    path=Path(__file__).with_name("bpy-prototype-snow-soft-cloth.py")
    if git_blob(path.read_bytes())!=SOFT_BLOB:
        raise ValueError("reviewed_soft_cloth_hash_mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_snow_soft_cloth",path)
    soft=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(soft)
    pair,prototype,helper=soft.load_reviewed()
    if (soft.PAIR_BLOB!=PAIR_BLOB or soft.PROTOTYPE_BLOB!=PROTOTYPE_BLOB
            or soft.HELPER_BLOB!=HELPER_BLOB or soft.CONFIG_BLOB!=CONFIG_BLOB):
        raise ValueError("reviewed_import_chain_mismatch")
    return soft,pair,helper

def properties(bone):
    return {key:plain(bone[key]) for key in bone.keys()}

def channels(bone):
    return {"location":list(bone.location),"rotation_mode":bone.rotation_mode,
        "rotation_euler":list(bone.rotation_euler),
        "rotation_quaternion":list(bone.rotation_quaternion),"scale":list(bone.scale),
        "lock_location":list(bone.lock_location),"lock_rotation":list(bone.lock_rotation),
        "lock_rotation_w":bone.lock_rotation_w,"lock_rotations_4d":bone.lock_rotations_4d,
        "lock_scale":list(bone.lock_scale)}

def control_record(rig,bone):
    ranges={}
    for name in ("location","rotation_euler","rotation_quaternion","scale"):
        prop=bone.bl_rna.properties[name]
        ranges[name]={"hard_min":float(prop.hard_min),"hard_max":float(prop.hard_max)}
    custom=[]
    for key in bone.keys():
        try:
            ui=plain(bone.id_properties_ui(key).as_dict())
        except (TypeError,ValueError,RuntimeError):
            ui={"available":False}
        custom.append({"name":key,"value":plain(bone[key]),"ui":ui})
    return {"name":bone.name,"parent":bone.parent.name if bone.parent else None,
        "head_world":list(rig.matrix_world@bone.head),
        "matrix_armature":matrix(bone.matrix),"matrix_world":matrix(rig.matrix_world@bone.matrix),
        "channels":channels(bone),"rna_transform_ranges":ranges,
        "bone_hidden":bone.bone.hide,"hide_select":bone.bone.hide_select,
        "constraints":[{"name":c.name,"type":c.type,"mute":c.mute,"influence":float(c.influence),
            "target":getattr(getattr(c,"target",None),"name",None),
            "subtarget":getattr(c,"subtarget",None)} for c in bone.constraints],
        "custom_properties":custom}

def key_values(bpy):
    records=[]
    seen=set()
    for obj in sorted((o for o in bpy.data.objects if o.type=="MESH"),key=lambda o:o.name):
        keys=obj.data.shape_keys
        if keys is None or keys.as_pointer() in seen:
            continue
        seen.add(keys.as_pointer())
        for key in keys.key_blocks:
            prop=key.bl_rna.properties["value"]
            value=float(key.value)
            low,high=float(prop.hard_min),float(prop.hard_max)
            if not all(math.isfinite(v) for v in (value,low,high)) or not low<=value<=high:
                raise ValueError("native_shape_key_value_outside_finite_rna_hard_range")
            records.append({"data":keys.name,"key":key.name,"value":value,
                "hard_min":low,"hard_max":high,"slider_min":float(key.slider_min),
                "slider_max":float(key.slider_max)})
    return records

def raw_preservation(bpy,helper,soft):
    records=[]
    for obj in sorted((o for o in bpy.data.objects if o.type=="MESH"),key=lambda o:o.name):
        mesh=obj.data
        state=helper.garment_render_state(obj)
        for key in state["shape_keys"]:
            key.pop("value",None)
        payload={"state_excluding_native_key_values":state,
            "object_material_slots":[{"link":slot.link,"material":slot.material.name if slot.material else None}
                                     for slot in obj.material_slots],
            "data_materials":[m.name if m else None for m in mesh.materials],
            "polygon_material_indices":[p.material_index for p in mesh.polygons],
            "weights":[[[g.group,float(g.weight)] for g in v.groups] for v in mesh.vertices],
            "uv":[{"name":layer.name,"values":[list(v.uv) for v in layer.data]} for layer in mesh.uv_layers],
            "modifiers":[soft.modifier_signature(m) for m in obj.modifiers]}
        records.append({"object":obj.name,"data":mesh.name,
            "geometry_and_key_data":helper.garment_geometry_signature(obj),
            "other_preserved_data_sha256":digest(payload)})
    return {"sha256":digest(records),"mesh_objects":len(records),
        "scope":"all raw mesh coordinates/all key DATA/UV/weights/topology/modifiers/ALL material slots and links; native key VALUES excluded"}

def material_graph_hash(bpy,pair):
    trees,seen=[],set()
    def visit(tree):
        if tree is None or tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        nodes=[]
        for node in tree.nodes:
            if node.type=="SCRIPT":
                raise ValueError("script_shader_not_allowed")
            data={"name":node.name,"type":node.bl_idname,
                "inputs":[{"id":s.identifier,"linked":s.is_linked,"value":pair.primitive_default(s)}
                          for s in node.inputs]}
            for key in ("operation","blend_type","data_type","uv_map","space","invert",
                        "interpolation","projection","extension"):
                value=getattr(node,key,None)
                if isinstance(value,(str,bool,int,float)):
                    data[key]=value
            image=getattr(node,"image",None)
            if image:
                data["image"]={"name":image.name,"filepath":image.filepath,
                    "colorspace":image.colorspace_settings.name,"alpha_mode":image.alpha_mode}
            child=getattr(node,"node_tree",None)
            if child:
                data["group"]=child.name
                visit(child)
            nodes.append(data)
        trees.append({"name":tree.name,"nodes":sorted(nodes,key=lambda v:v["name"]),
            "links":sorted([l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier]
                           for l in tree.links)})
    materials=[]
    for material in bpy.data.materials:
        materials.append({"name":material.name,"use_nodes":material.use_nodes,
                          "diffuse_color":list(material.diffuse_color)})
        visit(material.node_tree)
    for world in bpy.data.worlds:
        visit(world.node_tree)
    for light in bpy.data.lights:
        visit(light.node_tree)
    return digest({"materials":sorted(materials,key=lambda v:v["name"]),
                   "node_trees":sorted(trees,key=lambda v:v["name"])})

def rest_rig_hash(rig):
    return digest({"object_matrix":matrix(rig.matrix_world),"pose_position":rig.data.pose_position,
        "bones":[{"name":b.name,"parent":b.parent.name if b.parent else None,
            "matrix_local":matrix(b.matrix_local),"head":list(b.head_local),
            "tail":list(b.tail_local),"deform":b.use_deform} for b in rig.data.bones]})

def evaluated_snapshot(bpy,objects):
    dg=bpy.context.evaluated_depsgraph_get()
    result={}
    for obj in objects:
        evaluated=obj.evaluated_get(dg)
        mesh=evaluated.data
        topology=digest({"vertices":len(mesh.vertices),"edges":[list(e.vertices) for e in mesh.edges],
                         "polygons":[list(p.vertices) for p in mesh.polygons]})
        coords=[evaluated.matrix_world@v.co for v in mesh.vertices]
        if any(not all(math.isfinite(x) for x in co) for co in coords):
            raise ValueError("nonfinite_evaluated_coordinate")
        result[obj.name]={"vertices":len(mesh.vertices),"polygons":len(mesh.polygons),
            "topology_sha256":topology,"world_coordinates_sha256":digest([list(co) for co in coords]),
            "coords":coords}
    return result

def evaluated_report(snapshot):
    return {name:{k:v for k,v in data.items() if k!="coords"} for name,data in snapshot.items()}

def deformation(before,after):
    reports={}
    for name in before:
        a,b=before[name],after[name]
        comparable=(a["topology_sha256"]==b["topology_sha256"] and a["vertices"]==b["vertices"])
        record={"evaluated_topology_comparable":comparable,"mapping_scope":"two viewport-evaluated snapshots only; no raw/render mapping"}
        if comparable:
            deltas=[(x-y).length for x,y in zip(a["coords"],b["coords"])]
            record.update({"changed_vertices":sum(d>1e-6 for d in deltas),
                "maximum_world_displacement":max(deltas,default=0),
                "samples":[{"index":i,"before":list(a["coords"][i]),"after":list(b["coords"][i]),"distance":deltas[i]}
                           for i in sorted(range(len(deltas)),key=lambda i:deltas[i],reverse=True)[:4]]})
        reports[name]=record
    return reports

def make_channel_plan(rig,bone,target_world):
    from mathutils import Matrix
    if bone.rotation_mode not in MODES:
        raise ValueError("unsupported_control_rotation_mode")
    if any(not c.mute and c.influence!=0 for c in bone.constraints):
        raise ValueError("arm_control_has_active_constraint")
    paths={bone.path_from_id(field) for field in ("location","rotation_euler","rotation_quaternion","rotation_axis_angle","scale")}
    if rig.animation_data and any(not f.mute and f.data_path in paths for f in rig.animation_data.drivers):
        raise ValueError("arm_control_transform_has_active_driver")
    kw={}
    if bone.parent:
        kw={"parent_matrix":bone.parent.matrix.copy(),"parent_matrix_local":bone.parent.bone.matrix_local.copy()}
    basis=bone.bone.convert_local_to_pose(rig.matrix_world.inverted()@target_world,
        bone.bone.matrix_local,invert=True,**kw)
    location,rotation,scale=basis.decompose()
    if matrix_error(basis,Matrix.LocRotScale(location,rotation,scale))>1e-5:
        raise ValueError("unsupported_sheared_control_basis")
    old=channels(bone)
    for key,values,locks in (("location",location,bone.lock_location),("scale",scale,bone.lock_scale)):
        if any(locked and abs(float(values[i])-old[key][i])>1e-5 for i,locked in enumerate(locks)):
            raise ValueError("requested_pose_changes_locked_control_channel")
    if bone.rotation_mode=="QUATERNION":
        original=bone.rotation_quaternion.copy()
        if rotation.dot(original)<0:
            rotation.negate()
        rotation_values=list(rotation)
        if bone.lock_rotations_4d:
            locks=[bone.lock_rotation_w,*bone.lock_rotation]
            if any(lock and abs(rotation_values[i]-old["rotation_quaternion"][i])>1e-5 for i,lock in enumerate(locks)):
                raise ValueError("requested_pose_changes_locked_quaternion_channel")
        else:
            locks=None
            if any(bone.lock_rotation) and original.rotation_difference(rotation).angle>1e-5:
                raise ValueError("unsupported_locked_quaternion_rotation")
    else:
        rotation_values=list(rotation.to_euler(bone.rotation_mode,bone.rotation_euler))
        locks=list(bone.lock_rotation)
        if any(lock and abs(rotation_values[i]-old["rotation_euler"][i])>1e-5 for i,lock in enumerate(locks)):
            raise ValueError("requested_pose_changes_locked_euler_channel")
    return {"bone":bone,"before":old,"location":list(location),"scale":list(scale),
            "rotation":rotation_values,"rotation_locks":locks,"world_target":target_world.copy(),
            "basis_target":matrix(basis)}

def apply_channel_plan(plan):
    bone=plan["bone"]
    for name,locks in (("location",bone.lock_location),("scale",bone.lock_scale)):
        destination=getattr(bone,name)
        for i,locked in enumerate(locks):
            if not locked:
                destination[i]=plan[name][i]
    if bone.rotation_mode=="QUATERNION":
        if plan["rotation_locks"] is None:
            if not any(bone.lock_rotation):
                bone.rotation_quaternion=plan["rotation"]
        else:
            for i,locked in enumerate(plan["rotation_locks"]):
                if not locked:
                    bone.rotation_quaternion[i]=plan["rotation"][i]
    else:
        for i,locked in enumerate(bone.lock_rotation):
            if not locked:
                bone.rotation_euler[i]=plan["rotation"][i]

def verify_locked(plan):
    bone=plan["bone"]
    old=plan["before"]
    now=channels(bone)
    if now["rotation_mode"]!=old["rotation_mode"]:
        raise ValueError("control_rotation_mode_changed")
    for field,lockfield in (("location","lock_location"),("scale","lock_scale")):
        if now[lockfield]!=old[lockfield] or any(lock and now[field][i]!=old[field][i] for i,lock in enumerate(old[lockfield])):
            raise ValueError("locked_control_channel_changed")
    for field in ("lock_rotation","lock_rotation_w","lock_rotations_4d"):
        if now[field]!=old[field]:
            raise ValueError("control_rotation_locks_changed")
    if bone.rotation_mode=="QUATERNION":
        if old["lock_rotations_4d"]:
            locks=[old["lock_rotation_w"],*old["lock_rotation"]]
            if any(lock and now["rotation_quaternion"][i]!=old["rotation_quaternion"][i] for i,lock in enumerate(locks)):
                raise ValueError("locked_quaternion_channel_changed")
        elif any(old["lock_rotation"]) and now["rotation_quaternion"]!=old["rotation_quaternion"]:
            raise ValueError("locked_quaternion_rotation_changed")
    elif any(lock and now["rotation_euler"][i]!=old["rotation_euler"][i] for i,lock in enumerate(old["lock_rotation"])):
        raise ValueError("locked_euler_channel_changed")
    return now

def render_pose(helper,bpy,out,scene,shot,height,audit,emit_preview):
    from mathutils import Vector
    angle=math.radians(shot["angle"])
    camera=scene.camera
    target=Vector(shot["target_world"])
    camera.location=target+Vector((math.sin(angle)*height*3.5,-math.cos(angle)*height*3.5,height*0.02))
    camera.rotation_euler=(target-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.ortho_scale=shot["ortho_scale"]
    scene.render.resolution_x,scene.render.resolution_y=shot["resolution"]
    scene.render.resolution_percentage=100
    bpy.context.view_layer.update()
    path=out/("snow-raised-arms-"+shot["name"]+".png")
    scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True,scene=scene.name)
    record={"model":"snow","phase":"raised-arms","pose":"raised-arms","view":shot["name"],
        "file":path.name,"bytes":path.stat().st_size,"sha256":sha(path),
        "resolution":shot["resolution"],"camera_target_world":shot["target_world"],
        "camera_azimuth":shot["angle"],"camera_ortho_scale":shot["ortho_scale"],
        "neutral_baseline_rerendered":False,"before_after_comparison_render":False,
        "camera_reference":shot["reference"]}
    audit["renders"].append(record)
    write_audit(out/"raised-arms-audit.json",audit)
    print("AVATAR_ACTUAL_RENDER "+encoded(record).decode().strip(),flush=True)
    if emit_preview:
        image=bpy.data.images.load(str(path),check_existing=False)
        image.scale(320,400)
        preview=path.with_name(path.stem+"-preview.jpg")
        image.file_format,image.filepath_raw="JPEG",str(preview)
        image.save()
        while preview.stat().st_size>65536 and image.size[0]>128:
            image.scale(max(128,int(image.size[0]*0.8)),max(96,int(image.size[1]*0.8)))
            image.save()
        if preview.stat().st_size>65536:
            raise ValueError("preview_byte_budget_exceeded")
        dimensions=list(image.size)
        bpy.data.images.remove(image)
        print("AVATAR_ACTUAL_JPEG "+json.dumps({"model":"snow","phase":"raised-arms",
            "pose":"raised-arms","view":shot["name"],"mime_type":"image/jpeg",
            "dimensions":dimensions,"bytes":preview.stat().st_size,
            "base64":base64.b64encode(preview.read_bytes()).decode("ascii")}),flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-root",required=True)
    parser.add_argument("--derivative-blend",required=True)
    parser.add_argument("--config",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--emit-preview",action="store_true")
    args=parser.parse_args()
    root=Path(args.source_root).resolve(strict=True)
    source=root/"snow/original/Snow/snow_v4.2.blend"
    blend=Path(args.derivative_blend).resolve(strict=True)
    producer=blend.with_name("soft-cloth-audit.json")
    out=Path(args.out).resolve()
    if out.is_relative_to(root) or out.is_relative_to(blend.parent) or source.is_relative_to(out) or blend.is_relative_to(out):
        raise ValueError("pose_output_overlaps_inputs")
    if sha(source)!=SOURCE_SHA or blend.stat().st_size!=INPUT_BYTES or sha(blend)!=INPUT_SHA:
        raise ValueError("frozen_pose_input_hash_mismatch")
    raw=Path(args.config).read_bytes()
    if git_blob(raw)!=CONFIG_BLOB:
        raise ValueError("reviewed_config_hash_mismatch")
    config=json.loads(raw)
    if config["poses"]!={"neutral":[]}:
        raise ValueError("source_neutral_config_mismatch")
    if producer.stat().st_size>1048576:
        raise ValueError("producer_audit_byte_budget_exceeded")
    frozen=json.loads(producer.read_text(encoding="utf-8"))
    if (frozen["source_sha256"]!=SOURCE_SHA or frozen["derivative"]["sha256"]!=INPUT_SHA
            or frozen["derivative"]["bytes"]!=INPUT_BYTES or not frozen["candidate_completed"]
            or not frozen["preservation_passed"] or frozen["helper_blob"]!=HELPER_BLOB
            or frozen["pair_blob"]!=PAIR_BLOB or frozen["config_blob"]!=CONFIG_BLOB
            or not frozen["texture_hash_recheck"]["complete"]):
        raise ValueError("frozen_soft_cloth_producer_identity_mismatch")
    front=frozen["camera_definitions"]["front"]
    if front["name"]!="front" or front["azimuth"]!=0:
        raise ValueError("frozen_front_camera_mismatch")
    out.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        target=out/"credits"/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/relative,target)
        credits.append({"file":str(target.relative_to(out)),"bytes":target.stat().st_size,"sha256":sha(target)})
    audit={"purpose":"Verified raised-arm controls; two posed views; facial readiness only",
        "source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"input_bytes":INPUT_BYTES,
        "producer_audit_sha256":sha(producer),"module_blobs":{"soft":SOFT_BLOB,"pair":PAIR_BLOB,
            "prototype":PROTOTYPE_BLOB,"helper":HELPER_BLOB,"config":CONFIG_BLOB},
        "credits":credits,"renders":[],"used_textures":[],"texture_preparation_complete":False,
        "models_saved":0,"solver_runs":0,"geometry_edits_performed":False,
        "garment_art_approved":False,"production_glb_approved":False,"animation_approved":False,
        "corrective_system_approved":False,"face_pose_approved":False,
        "limits":["Pose proof only; no baked clips, GLB, wardrobe or art acceptance.",
            "Raw key DATA is immutable; native corrective VALUES may change within actual finite RNA hard ranges.",
            "Evaluated comparisons concern matching viewport-evaluated topology only, not raw or render index mappings.",
            "Front camera uses frozen definition; three-quarter is a declared NEW 35 degree view.",
            "Face controls are data-only readiness, never transformed. No neutral views are rerendered."]}
    path=out/"raised-arms-audit.json"
    write_audit(path,audit)
    textures=audit["used_textures"]
    failure=None
    expected_files=0
    def recheck():
        unchanged=(sha(source)==SOURCE_SHA and sha(blend)==INPUT_SHA
                   and sha(producer)==audit["producer_audit_sha256"])
        checked=0
        match=True
        for image in textures:
            for item in image["files"]:
                checked+=1
                match=match and sha(source.parent/"textures"/item["file"])==item["sha256"]
        expected=audit.get("texture_expected_image_count")
        ready=sum(r.get("size_guard_passed",False) for r in textures)
        complete=(expected is not None and expected>0 and len(textures)==expected and ready==expected
            and audit.get("texture_preparation_complete",False) and checked==expected_files and checked>0)
        audit["source_and_input_unchanged"]=unchanged
        audit["texture_hash_recheck"]={"expected_images":expected,"attempted_images":len(textures),
            "ready_images":ready,"expected_files":expected_files,"checked_files":checked,
            "complete":complete,"all_checked_files_unchanged":match if checked else None}
        return unchanged and complete and match
    try:
        soft,pair,helper=load_reviewed()
        import bpy
        from mathutils import Matrix,Vector
        if sys.version_info[:2]!=(3,11) or tuple(bpy.app.version)!=(4,5,9):
            raise ValueError("requires_verified_python_3_11_bpy_4_5_9")
        bpy.context.preferences.filepaths.use_scripts_auto_execute=False
        bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False)
        policy=helper.disable_animation_and_scripts(bpy)
        audit["native_policy"]={"autoexec":False,"embedded_text_executed":False,
            "native_retained":sum(p["native_drivers_retained"] for p in policy),
            "complex_python_muted":sum(p["complex_python_drivers_muted"] for p in policy)}
        rig=bpy.data.objects.get("RIG-Snow")
        if rig is None or rig.type!="ARMATURE" or rig.mode not in ("OBJECT","POSE") or rig.data.pose_position!="POSE":
            raise ValueError("runtime_pose_rig_mode_mismatch")
        audit["rig_mode"]={"object_mode":rig.mode,"context_mode":bpy.context.mode,"pose_position":rig.data.pose_position}
        scale=rig.matrix_world.to_scale()
        loc,rot,scl=rig.matrix_world.decompose()
        if (min(scale)<=0 or max(scale)-min(scale)>1e-6 or rig.matrix_world.determinant()<=0
                or matrix_error(rig.matrix_world,Matrix.LocRotScale(loc,rot,scl))>1e-6):
            raise ValueError("unsupported_rig_world_scale_or_shear")
        objects=[]
        for name in config["mesh_names"]:
            obj=bpy.data.objects.get(name)
            if obj is None or obj.type!="MESH":
                raise ValueError("frozen_character_mesh_missing")
            objects.append(obj)
        scene=bpy.context.scene
        if scene is None or scene.camera is None or scene.render.engine!="CYCLES" or any(o.name not in scene.objects for o in objects):
            raise ValueError("frozen_pose_scene_missing")
        audit["linked_missing_modifier_dependencies"]=pair.ensure_saved_dependency_closure(bpy,scene,objects)
        materials=pair.used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
        images=pair.collect_images(materials)
        manifests={record["image"]:record for record in frozen["used_textures"]}
        if len(manifests)!=len(frozen["used_textures"]) or not images:
            raise ValueError("frozen_texture_manifest_not_unique")
        actual_manifest={}
        for image in images:
            if image.name not in manifests:
                raise ValueError("used_image_not_in_frozen_manifest")
            reference=manifests[image.name]
            filename=str(image.filepath).replace("\\","/").split("/")[-1]
            if image.source!=reference["source"] or filename!=reference["filename"] or not reference["size_guard_passed"]:
                raise ValueError("used_image_identity_differs_from_frozen_manifest")
            actual_manifest[image.name]=reference
            expected_files+=len(reference["files"])
        audit["texture_expected_image_count"]=len(images)
        audit["texture_expected_file_count"]=expected_files
        def texture_checkpoint():
            write_audit(path,audit)
        pair.relink_and_reload(images,source.parent/"textures",textures,texture_checkpoint)
        for record in textures:
            reference=actual_manifest[record["image"]]
            if record["files"]!=reference["files"]:
                raise ValueError("used_texture_bytes_differ_from_frozen_manifest")
        audit["texture_preparation_complete"]=True
        if not recheck():
            raise ValueError("frozen_used_texture_verification_failed")
        garment=bpy.data.objects.get("GEO-snow-shirt")
        if (garment not in objects or len(garment.data.vertices)!=1839
                or not garment.data.shape_keys or len(garment.data.shape_keys.key_blocks)!=10
                or garment.material_slots[0].link!="OBJECT"
                or garment.material_slots[0].material is None
                or garment.material_slots[0].material.name!=soft.MATERIAL_NAME
                or garment.data.materials[0] is not None):
            raise ValueError("frozen_soft_cloth_slot_or_geometry_mismatch")
        if soft.shader_signature(pair,garment.material_slots[0].material)!=frozen["new_target_shader_signature"]:
            raise ValueError("frozen_soft_cloth_shader_signature_mismatch")
        required=[*ARMS,*FACES,"Properties","UpperArm.L","UpperArm.R","Forearm.L","Forearm.R","Wrist.L","Wrist.R"]
        missing=[name for name in required if name not in rig.pose.bones]
        audit["missing_required_bones"]=missing
        write_audit(path,audit)
        if missing:
            raise ValueError("verified_control_bone_missing")
        expected_parents={"IK-Wrist.L":"P-IK-Wrist.L","IK-Wrist.R":"P-IK-Wrist.R",
            "POLE-UpperArm.L":"POLE-P-UpperArm.L","POLE-UpperArm.R":"POLE-P-UpperArm.R"}
        audit["runtime_arm_parent_guard"]={name:{"expected":parent,
            "actual":rig.pose.bones[name].parent.name if rig.pose.bones[name].parent else None}
            for name,parent in expected_parents.items()}
        write_audit(path,audit)
        if any(item["actual"]!=item["expected"] for item in audit["runtime_arm_parent_guard"].values()):
            raise ValueError("verified_arm_control_parent_mismatch")
        prop=rig.pose.bones["Properties"]
        properties_before=properties(prop)
        expected_properties={}
        for side in ("left","right"):
            for prefix,value in (("fk_hinge",0),("ik_stretch",1),("ik_pole_follow",0),("ik",1),("ik_parents",0)):
                expected_properties[prefix+"_"+side+"_upperarm"]=value
        audit["ik_properties"]={"required":expected_properties,"actual":properties_before}
        if any(key not in properties_before or properties_before[key]!=value for key,value in expected_properties.items()):
            raise ValueError("verified_upperarm_ik_properties_mismatch")
        bpy.context.view_layer.update()
        audit["controls_before"]=[control_record(rig,rig.pose.bones[name]) for name in ARMS]
        audit["face_readiness"]=[control_record(rig,rig.pose.bones[name]) for name in FACES]
        audit["face_readiness_only"]=True
        audit["driver_before"]=soft.driver_summary(helper,bpy)
        if audit["driver_before"]["active_invalid"]!=0:
            raise ValueError("native_driver_invalid_before_pose")
        raw_before=raw_preservation(bpy,helper,soft)
        graph_before=material_graph_hash(bpy,pair)
        rest_before=rest_rig_hash(rig)
        keys_before=key_values(bpy)
        audit["raw_preservation_before"]=raw_before
        audit["material_graph_sha256_before"]=graph_before
        audit["rig_rest_sha256_before"]=rest_before
        audit["native_key_values_before"]=keys_before
        evaluated_before=evaluated_snapshot(bpy,objects)
        audit["evaluated_before"]=evaluated_report(evaluated_before)
        plans=[]
        side_states=[]
        for side,angle in (("L",-60),("R",60)):
            wrist=rig.pose.bones["IK-Wrist."+side]
            pole=rig.pose.bones["POLE-UpperArm."+side]
            upper=rig.pose.bones["UpperArm."+side]
            chain=rig.pose.bones["Wrist."+side]
            pivot=rig.matrix_world@upper.head
            wrist_world=rig.matrix_world@wrist.matrix
            pole_world=rig.matrix_world@pole.matrix
            chain_head=rig.matrix_world@chain.head
            wrist_head=rig.matrix_world@wrist.head
            if (chain_head-wrist_head).length>TOL or (wrist_world.translation-wrist_head).length>TOL:
                raise ValueError("baseline_chain_target_head_correspondence_unproven")
            rotation=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(angle),4,"Y")@Matrix.Translation(-pivot)
            wrist_goal=rotation@wrist_world
            pole_goal=pole_world.copy()
            pole_goal.translation=rotation@pole_world.translation
            state={"side":side,"angle_world_y_degrees":angle,"pivot":pivot.copy(),
                "wrist_before":wrist_world.copy(),"wrist_goal":wrist_goal,
                "pole_before":pole_world.copy(),"pole_goal":pole_goal,
                "chain_before":chain_head.copy(),"reach_before":(wrist_head-pivot).length}
            side_states.append(state)
            audit.setdefault("world_pose_plan",[]).append({"side":side,"angle_world_y_degrees":angle,
                "runtime_pivot_world":list(pivot),"wrist_world_before":matrix(wrist_world),
                "wrist_world_target":matrix(wrist_goal),"pole_world_before":matrix(pole_world),
                "pole_world_target":matrix(pole_goal),"reach_before":state["reach_before"],
                "pole_rotation_intentionally_preserved":True})
            write_audit(path,audit)
            for bone,goal in ((wrist,wrist_goal),(pole,pole_goal)):
                plan=make_channel_plan(rig,bone,goal)
                plans.append(plan)
                audit.setdefault("channel_plans",[]).append({"bone":bone.name,"before":plan["before"],
                    "location_target":plan["location"],"rotation_target":plan["rotation"],
                    "scale_target":plan["scale"],"basis_target":plan["basis_target"]})
                write_audit(path,audit)
        for plan in plans:
            apply_channel_plan(plan)
        bpy.context.view_layer.update()
        audit["locked_channels_after"]={p["bone"].name:verify_locked(p) for p in plans}
        results=[]
        for state in side_states:
            side=state["side"]
            pivot=rig.matrix_world@rig.pose.bones["UpperArm."+side].head
            wrist=rig.matrix_world@rig.pose.bones["IK-Wrist."+side].matrix
            pole=rig.matrix_world@rig.pose.bones["POLE-UpperArm."+side].matrix
            chain=rig.matrix_world@rig.pose.bones["Wrist."+side].head
            pole_rotation_error=max(abs(pole[i][j]-state["pole_before"][i][j]) for i in range(3) for j in range(3))
            report={"side":side,"target_head_motion":(wrist.translation-state["wrist_before"].translation).length,
                "chain_head_motion":(chain-state["chain_before"]).length,
                "target_matrix_residual":matrix_error(wrist,state["wrist_goal"]),
                "chain_target_head_residual":(chain-wrist.translation).length,
                "pivot_drift":(pivot-state["pivot"]).length,
                "target_reach_change":abs((wrist.translation-pivot).length-state["reach_before"]),
                "actual_chain_reach_change":abs((chain-pivot).length-state["reach_before"]),
                "pole_position_residual":(pole.translation-state["pole_goal"].translation).length,
                "pole_orientation_matrix_residual":pole_rotation_error,
                "wrist_head_world":list(wrist.translation),"chain_head_world":list(chain),
                "pivot_world":list(pivot)}
            results.append(report)
        audit["actual_chain_results"]=results
        write_audit(path,audit)
        if any(r["target_head_motion"]<=0.2 or r["chain_head_motion"]<=0.2
                or any(r[key]>TOL for key in ("target_matrix_residual","chain_target_head_residual",
                    "pivot_drift","target_reach_change","actual_chain_reach_change",
                    "pole_position_residual","pole_orientation_matrix_residual")) for r in results):
            raise ValueError("raised_arm_chain_target_or_reach_gate_failed")
        audit["controls_after"]=[control_record(rig,rig.pose.bones[name]) for name in ARMS]
        if properties(prop)!=properties_before:
            raise ValueError("source_ik_properties_changed")
        audit["native_key_values_after_pose"]=key_values(bpy)
        audit["driver_after_pose"]=soft.driver_summary(helper,bpy)
        if audit["driver_after_pose"]["active_invalid"]!=0:
            raise ValueError("native_driver_invalid_after_pose")
        if rest_rig_hash(rig)!=rest_before or raw_preservation(bpy,helper,soft)!=raw_before or material_graph_hash(bpy,pair)!=graph_before:
            raise ValueError("immutable_raw_data_materials_or_rig_rest_changed")
        evaluated_after=evaluated_snapshot(bpy,objects)
        audit["evaluated_after"]=evaluated_report(evaluated_after)
        audit["deformation"]=deformation(evaluated_before,evaluated_after)
        for name in ("GEO-snow-body","GEO-snow-shirt"):
            record=audit["deformation"][name]
            if not record["evaluated_topology_comparable"]:
                raise ValueError("evaluated_topology_changed_index_comparison_unavailable")
            if record["changed_vertices"]==0 or record["maximum_world_displacement"]<=1e-6:
                raise ValueError("actual_evaluated_body_or_shirt_deformation_not_established")
        audit["pose_numeric_gates_passed"]=True
        if not recheck():
            raise ValueError("immutable_inputs_or_textures_changed_before_render")
        write_audit(path,audit)
        scene.cycles.seed=SEED
        scene.cycles.use_animated_seed=False
        height=float(front["ortho_scale"])/1.32
        shots=[{"name":"front","target_world":front["target_world"],"ortho_scale":front["ortho_scale"],
                "resolution":front["resolution"],"angle":0,"reference":"frozen soft-cloth front camera"},
               {"name":"threequarter","target_world":front["target_world"],"ortho_scale":front["ortho_scale"],
                "resolution":front["resolution"],"angle":35,"reference":"NEW declared 35 degree posed camera; not an old frozen threequarter"}]
        for shot in shots:
            # Prepare the same view before hashing; render_pose repeats this exact formula.
            angle=math.radians(shot["angle"])
            target=Vector(shot["target_world"])
            scene.camera.location=target+Vector((math.sin(angle)*height*3.5,-math.cos(angle)*height*3.5,height*0.02))
            scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat("-Z","Y").to_euler()
            scene.camera.data.ortho_scale=shot["ortho_scale"]
            scene.render.resolution_x,scene.render.resolution_y=shot["resolution"]
            scene.render.resolution_percentage=100
            bpy.context.view_layer.update()
            before=pair.control_snapshot(bpy,scene,objects,materials,None,None)
            render_pose(helper,bpy,out,scene,shot,height,audit,args.emit_preview)
            after=pair.control_snapshot(bpy,scene,objects,materials,None,None)
            if before["sha256"]!=after["sha256"]:
                raise ValueError("posed_render_controls_changed")
            audit.setdefault("render_controls",[]).append({"view":shot["name"],
                "before":before["sha256"],"after":after["sha256"],"match":True,
                "pose":"raised-arms","seed":SEED,"use_animated_seed":False})
            write_audit(path,audit)
        if len(audit["renders"])!=2:
            raise ValueError("posed_view_count_mismatch")
        audit["driver_after_render"]=soft.driver_summary(helper,bpy)
        audit["native_key_values_after_render"]=key_values(bpy)
        audit["raw_preservation_after"]=raw_preservation(bpy,helper,soft)
        audit["material_graph_sha256_after"]=material_graph_hash(bpy,pair)
        audit["preservation_passed"]=(audit["raw_preservation_after"]==raw_before
            and audit["material_graph_sha256_after"]==graph_before and rest_rig_hash(rig)==rest_before
            and properties(prop)==properties_before)
        if not audit["preservation_passed"] or audit["driver_after_render"]["active_invalid"]!=0 or not recheck():
            raise ValueError("final_pose_readonly_or_driver_guard_failed")
        audit["proof_completed"]=True
    except Exception as error:
        failure=error
        code=error.args[0] if isinstance(error,ValueError) and len(error.args)==1 and isinstance(error.args[0],str) else None
        if not code or len(code)>100 or not all(c.islower() or c=="_" for c in code):
            code=None
        audit["failure"]={"error_type":type(error).__name__,"error_code":code}
        raise
    finally:
        try:
            read_only_ok=recheck()
            write_audit(path,audit)
            face_summary=[{"name":r["name"],"parent":r["parent"],
                "rotation_mode":r["channels"]["rotation_mode"],
                "lock_location":r["channels"]["lock_location"],"lock_rotation":r["channels"]["lock_rotation"],
                "lock_scale":r["channels"]["lock_scale"],"constraint_count":len(r["constraints"]),
                "custom_property_names":[p["name"] for p in r["custom_properties"]],
                "transform_ranges":r["rna_transform_ranges"]} for r in audit.get("face_readiness",[])]
            key_before={(r["data"],r["key"]):r["value"] for r in audit.get("native_key_values_before",[])}
            key_after=audit.get("native_key_values_after_render",audit.get("native_key_values_after_pose",[]))
            key_changes=[{"data":r["data"],"key":r["key"],"before":key_before[(r["data"],r["key"])],"after":r["value"]}
                for r in key_after if (r["data"],r["key"]) in key_before and r["value"]!=key_before[(r["data"],r["key"])]]
            marker={"proof_completed":audit.get("proof_completed",False),"failure":audit.get("failure"),
                "pose_numeric_gates_passed":audit.get("pose_numeric_gates_passed",False),
                "renders":len(audit["renders"]),"views":[r["view"] for r in audit["renders"]],
                "pose":"raised-arms","neutral_renders":0,"models_saved":0,"solver_runs":0,
                "source_and_input_unchanged":audit.get("source_and_input_unchanged"),
                "texture_hash_recheck":audit.get("texture_hash_recheck"),"native_policy":audit.get("native_policy"),
                "driver_before":audit.get("driver_before"),"driver_after":audit.get("driver_after_render",audit.get("driver_after_pose")),
                "actual_chain_results":audit.get("actual_chain_results"),
                "deformation":{name:audit.get("deformation",{}).get(name) for name in ("GEO-snow-body","GEO-snow-shirt")},
                "runtime_arm_parent_guard":audit.get("runtime_arm_parent_guard"),
                "preservation_passed":audit.get("preservation_passed",False),
                "native_key_count":len(key_after),"native_key_changed_count":len(key_changes),
                "native_key_changed_samples":key_changes[:12],"native_key_values_finite_within_actual_rna_hard_ranges":bool(key_after),
                "face_readiness_only":True,"face_controls":face_summary,"render_controls":audit.get("render_controls",[]),
                "garment_art_approved":False,"production_glb_approved":False,"animation_approved":False,
                "corrective_system_approved":False,"face_pose_approved":False,
                "raw_to_evaluated_mapping":"unproven; evaluated comparisons only after matching evaluated topology"}
            if len(encoded(marker))>24000:
                raise ValueError("raised_arm_stdout_byte_budget_exceeded")
            print("SNOW_RAISED_ARMS_PROOF "+encoded(marker).decode().strip(),flush=True)
            if failure is None and not read_only_ok:
                raise ValueError("pose_final_readonly_check_failed")
        except Exception as cleanup_error:
            if failure is None:
                raise
            print("SNOW_RAISED_ARMS_CLEANUP_FAILED "+json.dumps({"error_type":type(cleanup_error).__name__[:80]}),flush=True)

if __name__=="__main__":
    main()
