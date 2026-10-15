"""One bent-elbow/hand proof from frozen selected width baseline.
Two arm targets/poles only; no finger/face channel writes, neutral rerenders or blend saves.
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

FACE_BLOB="6b148270492cd0b5db9c697028be5699f05d1ddb"
POSE_BLOB="23ff416d8c2744b9d8eaafd51fbe9e3fe1504e7a"
CONFIG_BLOB="f0612039b320e8dac77587ec4aecdc2c84618843"
SOURCE_SHA="80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
INPUT_SHA="572897f5416f256950134e408ead8d77ecf53c0accbe5f7912be976c3c763ea4"
INPUT_BYTES=8454178
SEED=1729
REACH_FRACTION=0.75
TOL=0.0001
DIGITS=("Thumb","Index","Middle","Ring","Pinky")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n").encode()

def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def write_audit(path,audit):
    raw=encoded(audit)
    if len(raw)>1048576:
        raise ValueError("bent_elbow_audit_byte_budget_exceeded")
    path.write_bytes(raw)

def load_reviewed():
    path=Path(__file__).with_name("bpy-prototype-snow-friendly-face.py")
    if git_blob(path.read_bytes())!=FACE_BLOB:
        raise ValueError("reviewed_bent_elbow_face_functions_hash_mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_snow_face_functions",path)
    face=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(face)
    proof,soft,pair,helper=face.load_reviewed()
    if face.POSE_BLOB!=POSE_BLOB or face.CONFIG_BLOB!=CONFIG_BLOB:
        raise ValueError("reviewed_bent_elbow_import_chain_mismatch")
    return face,proof,soft,pair,helper

def world_head(rig,name):
    return rig.matrix_world@rig.pose.bones[name].head

def elbow_angle(u,e,w):
    a,b=u-e,w-e
    if a.length<=1e-8 or b.length<=1e-8:
        raise ValueError("degenerate_elbow_segment")
    return math.degrees(math.acos(max(-1.0,min(1.0,a.dot(b)/(a.length*b.length)))))

def quaternion_delta_degrees(a,b):
    qa,qb=a.to_quaternion().normalized(),b.to_quaternion().normalized()
    return math.degrees(2*math.acos(max(0.0,min(1.0,abs(qa.dot(qb))))))

def fingers(proof,rig):
    records=[]
    for side in ("L","R"):
        for digit in DIGITS:
            name="Finger_"+digit+"3."+side
            bone=rig.pose.bones[name]
            head,tail=rig.matrix_world@bone.head,rig.matrix_world@bone.tail
            if not all(math.isfinite(v) for p in (head,tail) for v in p):
                raise ValueError("nonfinite_finger_third_segment_endpoint")
            records.append({"bone":name,"side":side,"digit":digit,"parent":bone.parent.name if bone.parent else None,
                "head_world":list(head),"tail_world":list(tail),"length_world":(tail-head).length,
                "channels":proof.channels(bone)})
    return records

def native_constraints(face,rig,names):
    records=[]
    for name in sorted(set(names)):
        for c in rig.pose.bones[name].constraints:
            record=face.constraint_record(c)
            for field in ("chain_count","iterations","pole_angle","use_tail","use_stretch","use_location","use_rotation","orient_weight","weight"):
                if hasattr(c,field):
                    value=getattr(c,field)
                    if isinstance(value,(bool,int,float,str)):
                        record[field]=value
            pole=getattr(c,"pole_target",None)
            record["pole_target"]=pole.name if pole else None
            record["pole_subtarget"]=getattr(c,"pole_subtarget",None)
            records.append({"owner":name,"constraint":record})
    return records

def configuration_hash(proof,records):
    payload=[]
    for entry in records:
        c=dict(entry["constraint"])
        c.pop("eval_time",None)
        payload.append({"owner":entry["owner"],"constraint":c})
    return proof.digest(payload)

def framed_shot(name,points,angle,resolution,preview,margin):
    from mathutils import Vector
    if not points or not all(math.isfinite(v) for p in points for v in p):
        raise ValueError("nonfinite_or_empty_pose_crop_anchors")
    low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    target=(low+high)/2
    distance=max(1.0,(high-low).length*3)
    a=math.radians(angle)
    location=target+Vector((math.sin(a)*distance,-math.cos(a)*distance,0.01))
    rotation=(target-location).to_track_quat("-Z","Y")
    right=rotation@Vector((1,0,0))
    up=rotation@Vector((0,1,0))
    aspect=resolution[0]/resolution[1]
    half_x=max(abs((p-target).dot(right)) for p in points)+margin
    half_y=max(abs((p-target).dot(up)) for p in points)+margin
    scale=2*max(half_y,half_x/aspect)
    if not math.isfinite(scale) or scale<=0:
        raise ValueError("pose_crop_scale_invalid")
    return {"name":name,"target":list(target),"camera_location":list(location),"rotation_quaternion":list(rotation),
        "angle":angle,"scale":scale,"resolution":list(resolution),"preview":list(preview),
        "anchor_count":len(points),"anchor_bounds":{"min":list(low),"max":list(high)},
        "world_margin":margin,"anchor_coverage_verified":True,
        "coverage_scope":"finite bone/evaluated surface anchors plus margin; not proof of visible finger separation"}

def configure_shot(bpy,scene,shot):
    from mathutils import Vector,Quaternion
    camera=scene.camera
    camera.location=Vector(shot["camera_location"])
    camera.rotation_euler=Quaternion(shot["rotation_quaternion"]).to_euler()
    camera.data.ortho_scale=shot["scale"]
    scene.render.resolution_x,scene.render.resolution_y=shot["resolution"]
    scene.render.resolution_percentage=100
    bpy.context.view_layer.update()

def render_proof(bpy,out,scene,shot,audit,emit_preview):
    configure_shot(bpy,scene,shot)
    file=out/("snow-bent-elbows-"+shot["name"]+".png")
    scene.render.filepath=str(file)
    bpy.ops.render.render(write_still=True,scene=scene.name)
    record={"model":"snow","phase":"bent-elbows-proof","pose":"bent-elbows-proof","view":shot["name"],
        "file":file.name,"bytes":file.stat().st_size,"sha256":sha(file),"resolution":shot["resolution"],
        "camera_target_world":shot["target"],"camera_azimuth":shot["angle"],"camera_ortho_scale":shot["scale"],
        "camera_reference":"NEW posed actual joint/fingertip/evaluated head/shirt anchors",
        "neutral_or_straight_arm_baseline_rerendered":False,"before_after_comparison_render":False}
    audit["renders"].append(record)
    write_audit(out/"bent-elbows-audit.json",audit)
    print("AVATAR_ACTUAL_RENDER "+encoded(record).decode().strip(),flush=True)
    if emit_preview:
        image=bpy.data.images.load(str(file),check_existing=False)
        image.scale(*shot["preview"])
        preview=file.with_name(file.stem+"-preview.jpg")
        image.file_format,image.filepath_raw="JPEG",str(preview)
        image.save()
        while preview.stat().st_size>65536 and image.size[0]>128:
            width=max(128,int(image.size[0]*0.8))
            height=max(96,round(width*shot["resolution"][1]/shot["resolution"][0]))
            image.scale(width,height)
            image.save()
        if preview.stat().st_size>65536:
            raise ValueError("bent_elbow_preview_byte_budget_exceeded")
        dimensions=list(image.size)
        bpy.data.images.remove(image)
        print("AVATAR_ACTUAL_JPEG "+json.dumps({"model":"snow","phase":"bent-elbows-proof",
            "pose":"bent-elbows-proof","view":shot["name"],"mime_type":"image/jpeg",
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
    producer=blend.with_name("friendly-face-audit.json")
    out=Path(args.out).resolve()
    if out.is_relative_to(root) or out.is_relative_to(blend.parent) or source.is_relative_to(out) or blend.is_relative_to(out):
        raise ValueError("bent_elbow_output_overlaps_inputs")
    if sha(source)!=SOURCE_SHA or sha(blend)!=INPUT_SHA or blend.stat().st_size!=INPUT_BYTES:
        raise ValueError("frozen_bent_elbow_input_hash_mismatch")
    raw=Path(args.config).read_bytes()
    if git_blob(raw)!=CONFIG_BLOB:
        raise ValueError("reviewed_config_hash_mismatch")
    config=json.loads(raw)
    if config["poses"]!={"neutral":[]}:
        raise ValueError("reviewed_bent_elbow_source_config_mismatch")
    if producer.stat().st_size>1048576:
        raise ValueError("frozen_bent_elbow_producer_oversized")
    frozen=json.loads(producer.read_text(encoding="utf-8"))
    if (frozen["source_sha256"]!=SOURCE_SHA or frozen["derivative"]["sha256"]!=INPUT_SHA
            or frozen["derivative"]["bytes"]!=INPUT_BYTES or not frozen["candidate_completed"]
            or not frozen["preservation_passed"] or not frozen["numeric_width_gates_passed"]
            or frozen["friendly_functions_blob"]!=FACE_BLOB or frozen["pose_functions_blob"]!=POSE_BLOB
            or not frozen["texture_hash_recheck"]["complete"]):
        raise ValueError("frozen_width_derivative_producer_identity_mismatch")
    out.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        target=out/"credits"/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/relative,target)
        credits.append({"file":str(target.relative_to(out)),"bytes":target.stat().st_size,"sha256":sha(target)})
    audit={"purpose":"Bent-elbow and hand inspection only; selected width face baseline held",
        "source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"input_bytes":INPUT_BYTES,
        "producer_audit_sha256":sha(producer),"producer_parent_input_sha256":frozen["input_sha256"],
        "friendly_functions_blob":FACE_BLOB,"pose_functions_blob":POSE_BLOB,"credits":credits,
        "renders":[],"used_textures":[],"texture_preparation_complete":False,"models_saved":0,"solver_runs":0,
        "geometry_edits_performed":False,"reach_fraction":REACH_FRACTION,
        "overall_art_approved":False,"hand_art_approved":False,"clip_approved":False,
        "animation_approved":False,"production_glb_approved":False,"corrective_system_approved":False,
        "limits":["Static proof only; no clip/export/hand articulation acceptance or blend save.",
            "Only four arm controls change; fingers/face channels are never written.",
            "Wrist orientation starts with same worldY rotation; relative wrist/forearm change is measured, not accepted from residual alone.",
            "Raw/key DATA/materials/UV/weights/modifiers/ALL slots/rest rig remain immutable; finite native values may respond.",
            "Finger3 finite endpoints and crop coverage are numeric continuity, not visible separation or finger bending proof.",
            "Evaluated comparisons require matching viewport topology; no raw or final-render index correspondence claim.",
            "Three NEW posed views only; no neutral/straight-arm baseline rerender."]}
    path=out/"bent-elbows-audit.json"
    write_audit(path,audit)
    textures=audit["used_textures"]
    expected_files=0
    failure=None
    def recheck():
        unchanged=sha(source)==SOURCE_SHA and sha(blend)==INPUT_SHA and sha(producer)==audit["producer_audit_sha256"]
        count=0
        matches=True
        for image in textures:
            for record in image["files"]:
                count+=1
                matches=matches and sha(source.parent/"textures"/record["file"])==record["sha256"]
        expected=audit.get("texture_expected_image_count")
        ready=sum(r.get("size_guard_passed",False) for r in textures)
        complete=(expected is not None and expected>0 and len(textures)==ready==expected
            and audit["texture_preparation_complete"] and count==expected_files and count>0)
        audit["source_and_input_unchanged"]=unchanged
        audit["texture_hash_recheck"]={"expected_images":expected,"attempted_images":len(textures),"ready_images":ready,
            "expected_files":expected_files,"checked_files":count,"complete":complete,
            "all_checked_files_unchanged":matches if count else None}
        return unchanged and complete and matches
    try:
        face,proof,soft,pair,helper=load_reviewed()
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
            raise ValueError("runtime_bent_elbow_rig_mode_mismatch")
        audit["rig_mode"]={"object_mode":rig.mode,"context_mode":bpy.context.mode,"pose_position":rig.data.pose_position}
        loc,rot,scale=rig.matrix_world.decompose()
        if (min(scale)<=0 or max(scale)-min(scale)>1e-6 or rig.matrix_world.determinant()<=0
                or proof.matrix_error(rig.matrix_world,Matrix.LocRotScale(loc,rot,scale))>1e-6):
            raise ValueError("unsupported_bent_elbow_rig_world_scale_or_shear")
        objects=[]
        for name in config["mesh_names"]:
            obj=bpy.data.objects.get(name)
            if obj is None or obj.type!="MESH":
                raise ValueError("frozen_bent_elbow_character_mesh_missing")
            objects.append(obj)
        scene=bpy.context.scene
        if scene is None or scene.camera is None or scene.camera.data.type!="ORTHO" or scene.render.engine!="CYCLES" or any(o.name not in scene.objects for o in objects):
            raise ValueError("frozen_bent_elbow_scene_missing")
        audit["linked_missing_modifier_dependencies"]=pair.ensure_saved_dependency_closure(bpy,scene,objects)
        materials=pair.used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
        images=pair.collect_images(materials)
        manifest={r["image"]:r for r in frozen["used_textures"]}
        if len(manifest)!=len(frozen["used_textures"]) or not images:
            raise ValueError("frozen_bent_elbow_texture_manifest_not_unique")
        used={}
        for image in images:
            if image.name not in manifest:
                raise ValueError("used_image_not_in_bent_elbow_frozen_manifest")
            reference=manifest[image.name]
            filename=str(image.filepath).replace("\\","/").split("/")[-1]
            if image.source!=reference["source"] or filename!=reference["filename"] or not reference["size_guard_passed"]:
                raise ValueError("used_image_identity_differs_from_bent_elbow_frozen_manifest")
            used[image.name]=reference
            expected_files+=len(reference["files"])
        audit["texture_expected_image_count"]=len(images)
        audit["texture_expected_file_count"]=expected_files
        pair.relink_and_reload(images,source.parent/"textures",textures,lambda:write_audit(path,audit))
        for record in textures:
            if record["files"]!=used[record["image"]]["files"]:
                raise ValueError("used_texture_bytes_differ_from_bent_elbow_frozen_manifest")
        audit["texture_preparation_complete"]=True
        if not recheck():
            raise ValueError("bent_elbow_used_texture_verification_failed")
        garment=bpy.data.objects.get("GEO-snow-shirt")
        if (garment not in objects or len(garment.data.vertices)!=1839 or not garment.data.shape_keys
                or len(garment.data.shape_keys.key_blocks)!=10 or not garment.material_slots
                or garment.material_slots[0].link!="OBJECT" or garment.material_slots[0].material is None
                or garment.material_slots[0].material.name!=soft.MATERIAL_NAME or garment.data.materials[0] is not None):
            raise ValueError("frozen_bent_elbow_shirt_binding_or_geometry_mismatch")
        held_names=["ACT-Lips_Corner.L","ACT-Lips_Corner.R","MSTR-Eyebrow.L","MSTR-Eyebrow.R","MSTR-Mouth","TGT-Eyes"]
        chain_names=[prefix+"."+side for side in ("L","R") for prefix in ("UpperArm","Forearm","Wrist")]
        finger_names=["Finger_"+digit+"3."+side for side in ("L","R") for digit in DIGITS]
        required=[*proof.ARMS,*chain_names,*held_names,*finger_names,"Properties","MCH-JawOpennessMeasurer"]
        missing=[name for name in required if name not in rig.pose.bones]
        audit["missing_required_bones"]=missing
        write_audit(path,audit)
        if missing:
            raise ValueError("verified_bent_elbow_or_finger_control_missing")
        parents={"IK-Wrist.L":"P-IK-Wrist.L","IK-Wrist.R":"P-IK-Wrist.R",
            "POLE-UpperArm.L":"POLE-P-UpperArm.L","POLE-UpperArm.R":"POLE-P-UpperArm.R"}
        audit["runtime_parent_guard"]={name:{"expected":parent,"actual":rig.pose.bones[name].parent.name if rig.pose.bones[name].parent else None}
            for name,parent in parents.items()}
        properties_before=proof.properties(rig.pose.bones["Properties"])
        expected_properties={}
        for side in ("left","right"):
            for prefix,value in (("fk_hinge",0),("ik_stretch",1),("ik_pole_follow",0),("ik",1),("ik_parents",0)):
                expected_properties[prefix+"_"+side+"_upperarm"]=value
        audit["ik_properties"]={"required":expected_properties,"actual":properties_before}
        ik_owners=[]
        ik_mapping={}
        for side in ("L","R"):
            # Actual cached rig indirection; never assume IK directly targets the UI wrist.
            owner=rig.pose.bones.get("IK-M-Forearm."+side)
            c=owner.constraints.get("Ik") if owner else None
            record={"owner":owner.name if owner else None,"expected_owner":"IK-M-Forearm."+side,
                "actual_parent":owner.parent.name if owner and owner.parent else None,
                "expected_parent":"IK-M-UpperArm."+side,"expected_target":"IK-M-Wrist."+side,
                "constraint":face.constraint_record(c) if c else None,
                "pole_target":getattr(getattr(c,"pole_target",None),"name",None) if c else None,
                "pole_subtarget":getattr(c,"pole_subtarget",None) if c else None,
                "chain_count":getattr(c,"chain_count",None) if c else None}
            record["verified"]=(owner is not None and owner.parent is not None
                and owner.parent.name=="IK-M-UpperArm."+side and c is not None
                and c.type=="IK" and not c.mute and c.influence>0
                and c.target==rig and c.subtarget=="IK-M-Wrist."+side)
            ik_mapping[side]=record
            if owner:
                ik_owners.append(owner.name)
            # Read the known native wrist/stretch indirection too; no pose/config writes.
            for prefix in ("IK-M-Wrist","IK-C-Wrist","IK-STR-UpperArm","IK-M-UpperArm"):
                name=prefix+"."+side
                if name in rig.pose.bones:
                    ik_owners.append(name)
        inspected_names=[*proof.ARMS,*chain_names,*ik_owners]
        constraints_before=native_constraints(face,rig,inspected_names)
        audit["native_arm_constraints_before"]=constraints_before
        audit["direct_native_ik_mapping"]=ik_mapping
        bpy.context.view_layer.update()
        audit["controls_before"]=[proof.control_record(rig,rig.pose.bones[n]) for n in proof.ARMS]
        write_audit(path,audit)
        if any(item["actual"]!=item["expected"] for item in audit["runtime_parent_guard"].values()):
            raise ValueError("verified_bent_elbow_parent_mismatch")
        if any(key not in properties_before or properties_before[key]!=value for key,value in expected_properties.items()):
            raise ValueError("verified_bent_elbow_ik_properties_mismatch")
        if any(not item["verified"] for item in ik_mapping.values()):
            raise ValueError("direct_native_bent_elbow_ik_mapping_unproven")
        constraint_hash_before=configuration_hash(proof,constraints_before)
        held_before={name:proof.channels(rig.pose.bones[name]) for name in held_names}
        face_properties_before={side:{kind:float(rig.pose.bones["ACT-Lips_Corner."+side]["RIG-snow-Lips"+kind+"."+side])
                                     for kind in ("Up","Wide")} for side in ("L","R")}
        if not all(math.isfinite(v) for values in face_properties_before.values() for v in values.values()):
            raise ValueError("nonfinite_selected_face_property")
        jaw_before=rig.pose.bones["MCH-JawOpennessMeasurer"].matrix.copy()
        audit["held_face_before"]=held_before
        audit["held_face_properties_before"]=face_properties_before
        audit["fingers_before"]=fingers(proof,rig)
        finger_channels_before={r["bone"]:r["channels"] for r in audit["fingers_before"]}
        raw_before=proof.raw_preservation(bpy,helper,soft)
        graphs_before=proof.material_graph_hash(bpy,pair)
        rest_before=proof.rest_rig_hash(rig)
        audit["raw_preservation_before"]=raw_before
        audit["material_graph_sha256_before"]=graphs_before
        audit["rig_rest_sha256_before"]=rest_before
        audit["native_key_values_before"]=proof.key_values(bpy)
        audit["driver_before"]=soft.driver_summary(helper,bpy)
        if audit["driver_before"]["active_invalid"]!=0:
            raise ValueError("native_driver_invalid_before_bent_elbow")
        evaluated_before=proof.evaluated_snapshot(bpy,objects)
        audit["evaluated_before"]=proof.evaluated_report(evaluated_before)
        plans=[]
        states=[]
        for side,angle in (("L",-60),("R",60)):
            u,e,w=[world_head(rig,name+"."+side) for name in ("UpperArm","Forearm","Wrist")]
            wrist=rig.pose.bones["IK-Wrist."+side]
            pole=rig.pose.bones["POLE-UpperArm."+side]
            wrist_world=rig.matrix_world@wrist.matrix
            pole_world=rig.matrix_world@pole.matrix
            if (w-wrist_world.translation).length>TOL:
                raise ValueError("baseline_chain_target_head_mapping_unproven")
            first,second=(e-u).length,(w-e).length
            reach=(wrist_world.translation-u).length
            goal_reach=reach*REACH_FRACTION
            margin=max(1e-5,(first+second)*1e-4)
            arm_vector=wrist_world.translation-u
            pole_vector=pole_world.translation-u
            denominator=arm_vector.length*pole_vector.length
            sine=arm_vector.cross(pole_vector).length/denominator if denominator>0 else 0
            inspection={"side":side,"first_segment_length":first,"second_segment_length":second,
                "reach_before":reach,"target_reach":goal_reach,"annulus_lower":abs(first-second),
                "annulus_upper":first+second,"annulus_margin":margin,
                "pole_plane_sine_before":sine,"elbow_internal_angle_before_degrees":elbow_angle(u,e,w),
                "straight_angle_convention":180}
            audit.setdefault("reach_inspection",[]).append(inspection)
            write_audit(path,audit)
            if not (math.isfinite(goal_reach) and abs(first-second)+margin<goal_reach<first+second-margin):
                raise ValueError("shortened_target_outside_strict_two_segment_annulus")
            if not math.isfinite(sine) or sine<1e-3:
                raise ValueError("native_pole_plane_collinear_or_unsupported")
            rotation=Matrix.Translation(u)@Matrix.Rotation(math.radians(angle),4,"Y")@Matrix.Translation(-u)
            wrist_goal=rotation@wrist_world
            # Shorten TRANSLATION only; retain rotated orientation and original scale.
            wrist_goal.translation=u+REACH_FRACTION*(wrist_goal.translation-u)
            pole_goal=pole_world.copy()
            pole_goal.translation=rotation@pole_world.translation
            new_arm=wrist_goal.translation-u
            new_pole=pole_goal.translation-u
            goal_sine=new_arm.cross(new_pole).length/(new_arm.length*new_pole.length)
            if goal_sine<1e-3:
                raise ValueError("planned_bent_elbow_pole_plane_collinear")
            relative=(rig.matrix_world@rig.pose.bones["Forearm."+side].matrix).inverted()@(rig.matrix_world@rig.pose.bones["Wrist."+side].matrix)
            states.append({"side":side,"pivot":u.copy(),"elbow_before":e.copy(),"chain_before":w.copy(),
                "first":first,"second":second,"reach":reach,"goal_reach":goal_reach,
                "wrist_before":wrist_world.copy(),"wrist_goal":wrist_goal,"pole_before":pole_world.copy(),
                "pole_goal":pole_goal,"relative_wrist_before":relative.copy()})
            audit.setdefault("world_pose_plan",[]).append({"side":side,"world_y_degrees":angle,
                "pivot_world":list(u),"wrist_world_before":proof.matrix(wrist_world),
                "wrist_world_goal":proof.matrix(wrist_goal),"pole_world_before":proof.matrix(pole_world),
                "pole_world_goal":proof.matrix(pole_goal),"pole_orientation_preserved":True,
                "position_only_reach_fraction":REACH_FRACTION,"pole_plane_sine_goal":goal_sine,
                "predicted_elbow_internal_angle_degrees":math.degrees(math.acos(max(-1,min(1,
                    (first*first+second*second-goal_reach*goal_reach)/(2*first*second))))),
                "wrist_forearm_relative_before":proof.matrix(relative)})
            write_audit(path,audit)
            for bone,goal in ((wrist,wrist_goal),(pole,pole_goal)):
                plan=proof.make_channel_plan(rig,bone,goal)
                plans.append(plan)
                audit.setdefault("channel_plans",[]).append({"bone":bone.name,"before":plan["before"],
                    "location_target":plan["location"],"rotation_target":plan["rotation"],
                    "scale_target":plan["scale"],"basis_target":plan["basis_target"]})
                write_audit(path,audit)
        for plan in plans:
            proof.apply_channel_plan(plan)
        bpy.context.view_layer.update()
        audit["locked_channels_after"]={p["bone"].name:proof.verify_locked(p) for p in plans}
        results=[]
        for state in states:
            side=state["side"]
            u,e,w=[world_head(rig,name+"."+side) for name in ("UpperArm","Forearm","Wrist")]
            wrist=rig.matrix_world@rig.pose.bones["IK-Wrist."+side].matrix
            pole=rig.matrix_world@rig.pose.bones["POLE-UpperArm."+side].matrix
            forearm=rig.matrix_world@rig.pose.bones["Forearm."+side].matrix
            chain_wrist=rig.matrix_world@rig.pose.bones["Wrist."+side].matrix
            relative=forearm.inverted()@chain_wrist
            first,second=(e-u).length,(w-e).length
            angle=elbow_angle(u,e,w)
            report={"side":side,"upperarm_head_world":list(u),"elbow_head_world":list(e),"wrist_head_world":list(w),
                "target_head_world":list(wrist.translation),"first_segment_length":first,"second_segment_length":second,
                "first_segment_length_change":abs(first-state["first"]),"second_segment_length_change":abs(second-state["second"]),
                "elbow_internal_angle_degrees":angle,"straight_angle_convention":180,
                "chain_head_motion":(w-state["chain_before"]).length,
                "target_head_motion":(wrist.translation-state["wrist_before"].translation).length,
                "target_matrix_residual":proof.matrix_error(wrist,state["wrist_goal"]),
                "chain_target_residual":(w-wrist.translation).length,"pivot_drift":(u-state["pivot"]).length,
                "target_reach_error":abs((wrist.translation-u).length-state["goal_reach"]),
                "actual_chain_reach_error":abs((w-u).length-state["goal_reach"]),
                "pole_position_residual":(pole.translation-state["pole_goal"].translation).length,
                "pole_orientation_residual":max(abs(pole[i][j]-state["pole_before"][i][j]) for i in range(3) for j in range(3)),
                "wrist_forearm_relative_after":proof.matrix(relative),
                "wrist_forearm_relative_rotation_change_degrees":quaternion_delta_degrees(state["relative_wrist_before"],relative),
                "wrist_angle_scope":"coordinate-relative rotation change, not an anatomical/art limit or acceptance"}
            report["numeric_passed"]=(20<angle<160 and report["chain_head_motion"]>0.1
                and all(report[k]<=TOL for k in ("first_segment_length_change","second_segment_length_change",
                    "target_matrix_residual","chain_target_residual","pivot_drift","target_reach_error",
                    "actual_chain_reach_error","pole_position_residual","pole_orientation_residual")))
            results.append(report)
        audit["actual_chain_results"]=results
        audit["fingers_after"]=fingers(proof,rig)
        audit["finger_endpoint_motion"]=[{"bone":a["bone"],
            "head_motion_world":(Vector(b["head_world"])-Vector(a["head_world"])).length,
            "tail_motion_world":(Vector(b["tail_world"])-Vector(a["tail_world"])).length}
            for a,b in zip(audit["fingers_before"],audit["fingers_after"])]
        audit["native_key_values_after_pose"]=proof.key_values(bpy)
        audit["driver_after_pose"]=soft.driver_summary(helper,bpy)
        face_properties_after={side:{kind:float(rig.pose.bones["ACT-Lips_Corner."+side]["RIG-snow-Lips"+kind+"."+side])
                                    for kind in ("Up","Wide")} for side in ("L","R")}
        audit["held_face_properties_after"]=face_properties_after
        audit["held_face_property_drift"]={side:{kind:abs(face_properties_after[side][kind]-face_properties_before[side][kind])
                                               for kind in ("Up","Wide")} for side in ("L","R")}
        constraints_after=native_constraints(face,rig,inspected_names)
        audit["native_arm_constraints_after"]=constraints_after
        write_audit(path,audit)
        if not all(r["numeric_passed"] for r in results):
            raise ValueError("bent_elbow_angle_segment_chain_or_pole_gate_failed")
        if {n:proof.channels(rig.pose.bones[n]) for n in held_names}!=held_before:
            raise ValueError("selected_face_channels_changed_during_bent_elbow")
        if not all(math.isfinite(v) and v<=1e-4 for values in audit["held_face_property_drift"].values() for v in values.values()):
            raise ValueError("selected_face_up_or_wide_property_changed")
        if proof.matrix_error(jaw_before,rig.pose.bones["MCH-JawOpennessMeasurer"].matrix)>1e-6:
            raise ValueError("selected_jaw_mapping_target_changed")
        audit["finger_native_channel_change_count"]=sum(r["channels"]!=finger_channels_before[r["bone"]] for r in audit["fingers_after"])
        # Native finger response is recorded; this wrapper never assigns any finger channel.
        audit["pose_preservation_passed"]=(proof.raw_preservation(bpy,helper,soft)==raw_before
            and proof.material_graph_hash(bpy,pair)==graphs_before and proof.rest_rig_hash(rig)==rest_before
            and proof.properties(rig.pose.bones["Properties"])==properties_before
            and configuration_hash(proof,constraints_after)==constraint_hash_before
            and audit["driver_after_pose"]["active_invalid"]==0)
        if not audit["pose_preservation_passed"]:
            raise ValueError("bent_elbow_raw_material_rest_or_native_preservation_failed")
        evaluated_after=proof.evaluated_snapshot(bpy,objects)
        audit["evaluated_after"]=proof.evaluated_report(evaluated_after)
        audit["deformation"]=proof.deformation(evaluated_before,evaluated_after)
        for name in ("GEO-snow-body","GEO-snow-shirt"):
            item=audit["deformation"][name]
            if not item["evaluated_topology_comparable"] or item["changed_vertices"]==0 or item["maximum_world_displacement"]<=1e-6:
                raise ValueError("bent_elbow_evaluated_body_or_shirt_deformation_unproven")
        audit["numeric_pose_gates_passed"]=True
        if not recheck():
            raise ValueError("bent_elbow_inputs_changed_before_render")
        points=[]
        for name in ("GEO-snow-shirt","GEO-snow-head","GEO-snow-hair_base"):
            points.extend(evaluated_after[name]["coords"])
        for record in audit["fingers_after"]:
            points.extend((Vector(record["head_world"]),Vector(record["tail_world"])))
        for result in results:
            points.extend(Vector(result[key]) for key in ("upperarm_head_world","elbow_head_world","wrist_head_world"))
        shots=[framed_shot("upperbody-front",points,0,(640,800),(320,400),0.035)]
        for side,name,angle in (("L","left-hand-elbow",35),("R","right-hand-elbow",-35)):
            result=next(r for r in results if r["side"]==side)
            anchors=[Vector(result["elbow_head_world"]),Vector(result["wrist_head_world"])]
            for record in audit["fingers_after"]:
                if record["side"]==side:
                    anchors.extend((Vector(record["head_world"]),Vector(record["tail_world"])))
            shots.append(framed_shot(name,anchors,angle,(480,480),(240,240),0.035))
        audit["camera_shots"]=shots
        write_audit(path,audit)
        scene.cycles.seed=SEED
        scene.cycles.use_animated_seed=False
        for shot in shots:
            configure_shot(bpy,scene,shot)
            before=pair.control_snapshot(bpy,scene,objects,materials,None,None)
            render_proof(bpy,out,scene,shot,audit,args.emit_preview)
            after=pair.control_snapshot(bpy,scene,objects,materials,None,None)
            if before["sha256"]!=after["sha256"]:
                raise ValueError("bent_elbow_render_controls_changed")
            audit.setdefault("render_controls",[]).append({"view":shot["name"],"before":before["sha256"],"after":after["sha256"],
                "match":True,"pose":"bent-elbows-proof","seed":SEED,"use_animated_seed":False})
            write_audit(path,audit)
        audit["driver_after_render"]=soft.driver_summary(helper,bpy)
        audit["native_key_values_after_render"]=proof.key_values(bpy)
        audit["raw_preservation_after"]=proof.raw_preservation(bpy,helper,soft)
        audit["material_graph_sha256_after"]=proof.material_graph_hash(bpy,pair)
        audit["preservation_passed"]=(audit["raw_preservation_after"]==raw_before
            and audit["material_graph_sha256_after"]==graphs_before and proof.rest_rig_hash(rig)==rest_before
            and proof.properties(rig.pose.bones["Properties"])==properties_before
            and configuration_hash(proof,native_constraints(face,rig,inspected_names))==constraint_hash_before
            and {n:proof.channels(rig.pose.bones[n]) for n in held_names}==held_before
            and all(abs(float(rig.pose.bones["ACT-Lips_Corner."+s]["RIG-snow-Lips"+k+"."+s])-face_properties_before[s][k])<=1e-4
                    for s in ("L","R") for k in ("Up","Wide")))
        if len(audit["renders"])!=3 or not audit["preservation_passed"] or audit["driver_after_render"]["active_invalid"]!=0 or not recheck():
            raise ValueError("bent_elbow_final_pose_readonly_or_driver_guard_failed")
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
            readonly=recheck()
            write_audit(path,audit)
            marker={"proof_completed":audit.get("proof_completed",False),"failure":audit.get("failure"),
                "numeric_pose_gates_passed":audit.get("numeric_pose_gates_passed",False),
                "actual_chain_results":audit.get("actual_chain_results"),"reach_inspection":audit.get("reach_inspection"),
                "direct_native_ik_mapping":audit.get("direct_native_ik_mapping"),"runtime_parent_guard":audit.get("runtime_parent_guard"),
                "finger_third_segments_before":len(audit.get("fingers_before",[])),"finger_third_segments_after":len(audit.get("fingers_after",[])),
                "finger_endpoint_motion":audit.get("finger_endpoint_motion"),"finger_channels_written":False,
                "finger_native_channel_change_count":audit.get("finger_native_channel_change_count"),
                "face_property_drift":audit.get("held_face_property_drift"),
                "deformation":{n:audit.get("deformation",{}).get(n) for n in ("GEO-snow-body","GEO-snow-shirt")},
                "renders":len(audit["renders"]),"views":[r["view"] for r in audit["renders"]],
                "models_saved":0,"solver_runs":0,"neutral_or_straight_arm_baseline_renders":0,
                "source_and_input_unchanged":audit.get("source_and_input_unchanged"),"texture_hash_recheck":audit.get("texture_hash_recheck"),
                "native_policy":audit.get("native_policy"),"driver_before":audit.get("driver_before"),
                "driver_after":audit.get("driver_after_render",audit.get("driver_after_pose")),
                "preservation_passed":audit.get("preservation_passed",False),"render_controls":audit.get("render_controls",[]),
                "overall_art_approved":False,"hand_art_approved":False,"clip_approved":False,
                "animation_approved":False,"production_glb_approved":False,"corrective_system_approved":False,
                "raw_to_evaluated_mapping":"unproven; matching viewport-evaluated topology only"}
            if len(encoded(marker))>24000:
                raise ValueError("bent_elbow_stdout_byte_budget_exceeded")
            print("SNOW_BENT_ELBOWS_PROOF "+encoded(marker).decode().strip(),flush=True)
            if failure is None and not readonly:
                raise ValueError("bent_elbow_final_readonly_check_failed")
        except Exception as cleanup_error:
            if failure is None:
                raise
            print("SNOW_BENT_ELBOWS_CLEANUP_FAILED "+json.dumps({"error_type":type(cleanup_error).__name__[:80]}),flush=True)

if __name__=="__main__":
    main()
