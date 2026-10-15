"""One conditional smile-width candidate on the frozen SOFTER-NEUTRAL Snow.
No baseline rerender, Up/brow/arm application, expression eval or geometry edits.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

FACE_BLOB="6b148270492cd0b5db9c697028be5699f05d1ddb"
POSE_BLOB="23ff416d8c2744b9d8eaafd51fbe9e3fe1504e7a"
SOURCE_SHA="80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
INPUT_SHA="8c56cf78aec2a0ea3c84dd232cd2fffd53e85a0646c051e2db9e28c966c92ed8"
INPUT_BYTES=8456589
CONFIG_BLOB="f0612039b320e8dac77587ec4aecdc2c84618843"
SEED=1729
FRACTION=0.1
CONTROL_CAP=0.006

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n").encode()

def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def write_audit(path,audit):
    raw=encoded(audit)
    if len(raw)>1048576:
        raise ValueError("smile_width_audit_byte_budget_exceeded")
    path.write_bytes(raw)

def load_reviewed():
    path=Path(__file__).with_name("bpy-prototype-snow-friendly-face.py")
    if git_blob(path.read_bytes())!=FACE_BLOB:
        raise ValueError("reviewed_friendly_face_hash_mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_snow_friendly_functions",path)
    face=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(face)
    proof,soft,pair,helper=face.load_reviewed()
    if face.POSE_BLOB!=POSE_BLOB or face.CONFIG_BLOB!=CONFIG_BLOB:
        raise ValueError("reviewed_width_import_chain_mismatch")
    return face,proof,soft,pair,helper

def unit_clamp_affine(expression,variable):
    """Read ONLY root clamp(affine) or explicit min/max unit-clamp AST data; never evaluate driver code."""
    if len(expression)>2048 or variable in ("min","max","clamp"):
        return {"supported":False,"reason":"expression_size_or_variable_unsupported"}
    try:
        tree=ast.parse(expression,mode="eval")
        if sum(1 for _ in ast.walk(tree))>96:
            raise ValueError("ast_budget")
        def affine(node,depth=0):
            if depth>14:
                raise ValueError("ast_depth")
            if isinstance(node,ast.Constant) and isinstance(node.value,(float,int)) and not isinstance(node.value,bool):
                a,b=0.0,float(node.value)
            elif isinstance(node,ast.Name) and node.id==variable:
                a,b=1.0,0.0
            elif isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
                a,b=affine(node.operand,depth+1)
                if isinstance(node.op,ast.USub):
                    a,b=-a,-b
            elif isinstance(node,ast.BinOp):
                a,b=affine(node.left,depth+1)
                c,d=affine(node.right,depth+1)
                if isinstance(node.op,ast.Add):
                    a,b=a+c,b+d
                elif isinstance(node.op,ast.Sub):
                    a,b=a-c,b-d
                elif isinstance(node.op,ast.Mult) and (a==0 or c==0):
                    a,b=(c*b,d*b) if a==0 else (a*d,b*d)
                elif isinstance(node.op,ast.Div) and c==0 and d!=0:
                    a,b=a/d,b/d
                else:
                    raise ValueError("nonlinear_or_unsupported_arithmetic")
            else:
                raise ValueError("non_affine_inner_expression")
            if not math.isfinite(a) or not math.isfinite(b):
                raise ValueError("nonfinite_affine_coefficient")
            return a,b
        def unwrap(node,function,bound):
            if not (isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
                    and node.func.id==function and len(node.args)==2 and not node.keywords):
                return None
            for i in (0,1):
                try:
                    a,b=affine(node.args[i])
                except ValueError:
                    continue
                if a==0 and b==bound:
                    return node.args[1-i]
            return None
        inner=None
        root=tree.body
        # Blender's native simple-expression clamp(x) uses fixed unit bounds.
        # Accept this ROOT shape only; its inner argument must still be affine.
        if (isinstance(root,ast.Call) and isinstance(root.func,ast.Name)
                and root.func.id=="clamp" and len(root.args)==1 and not root.keywords):
            inner=root.args[0]
        else:
            first=unwrap(root,"min",1.0)
            if first is not None:
                inner=unwrap(first,"max",0.0)
            if inner is None:
                first=unwrap(root,"max",0.0)
                if first is not None:
                    inner=unwrap(first,"min",1.0)
        if inner is None:
            raise ValueError("not_an_explicit_unit_clamp")
        a,b=affine(inner)
        if a==0:
            raise ValueError("zero_affine_slope")
        return {"supported":True,"a":a,"b":b,"lower":0.0,"upper":1.0,
            "scope":"only native root clamp(affine) or explicit min/max unit clamp of finite affine AST data"}
    except (SyntaxError,ValueError,TypeError,ZeroDivisionError,OverflowError) as error:
        return {"supported":False,"reason":type(error).__name__}

def inspect_width(face,proof,rig,side):
    act=rig.pose.bones["ACT-Lips_Corner."+side]
    outer=rig.pose.bones["OuterLip_Corner."+side]
    key="RIG-snow-LipsWide."+side
    prop_path=act.path_from_id()+"["+json.dumps(key)+"]"
    curve,driver=face.driver_record(rig,prop_path)
    constraints={c.name:c for c in act.constraints}
    limit=constraints.get("KEEP-Limit Location")
    transform=constraints.get("KEEP-Transformation")
    record={"side":side,"act":proof.control_record(rig,act),"wide_property":key,
        "property_present":key in act,"driver":driver,
        "constraints":[face.constraint_record(c) for c in act.constraints],
        "outer_corner_constraint_names":[c.name for c in outer.constraints],
        "mapping_reasons":[]}
    reasons=record["mapping_reasons"]
    def require(ok,reason):
        if not ok:
            reasons.append(reason)
    require(act.parent is not None and act.parent.name=="CON-ACT-Lips_Corner."+side,"act_parent_mismatch")
    require(act.rotation_mode in proof.MODES and not act.lock_location[0],"act_x_mode_or_lock_unsupported")
    expected={"KEEP-Limit Location":"LIMIT_LOCATION","KEEP-Limit Scale":"LIMIT_SCALE","KEEP-Transformation":"TRANSFORM"}
    require(set(constraints)==set(expected) and all(constraints[n].type==kind for n,kind in expected.items() if n in constraints),
            "act_constraint_set_mismatch")
    require(all(not c.mute and c.influence>0 for c in act.constraints),"act_constraint_not_active")
    require(limit is not None and limit.type=="LIMIT_LOCATION" and limit.owner_space=="LOCAL","local_x_limit_unproven")
    jaw=rig.pose.bones.get("MCH-JawOpennessMeasurer")
    require(transform is not None and transform.type=="TRANSFORM" and transform.target==rig
            and transform.subtarget=="MCH-JawOpennessMeasurer" and jaw is not None,"jaw_constraint_target_unproven")
    if jaw:
        record["jaw_matrix"]=proof.matrix(jaw.matrix)
    current=float(act.location.x)
    record["current_local_x"]=current
    wide=float(act[key]) if key in act else None
    record["wide_before"]=wide
    require(wide is not None and math.isfinite(wide) and 0<=wide<1,"wide_unit_headroom_unproven")
    valid=(curve is not None and curve.driver.type=="SCRIPTED" and not curve.mute
        and curve.is_valid and curve.driver.is_simple_expression and len(curve.driver.variables)==1)
    require(valid,"native_wide_driver_unproven")
    parsed={"supported":False,"reason":"driver_not_established"}
    if valid:
        variable=curve.driver.variables[0]
        require(variable.type=="TRANSFORMS" and len(variable.targets)==1
            and variable.targets[0].id==rig and variable.targets[0].bone_target==act.name
            and variable.targets[0].transform_type=="LOC_X"
            and variable.targets[0].transform_space=="LOCAL_SPACE","wide_loc_x_local_space_target_unproven")
        parsed=unit_clamp_affine(curve.driver.expression,variable.name)
        require(parsed["supported"],"wide_unit_clamp_affine_unproven")
    record["affine_mapping"]=parsed
    if limit is not None and limit.type=="LIMIT_LOCATION":
        record["actual_x_limits"]={"owner_space":limit.owner_space,
            "use_min":limit.use_min_x,"min":float(limit.min_x),
            "use_max":limit.use_max_x,"max":float(limit.max_x),
            "use_transform_limit":limit.use_transform_limit}
        require(math.isfinite(current),"current_local_x_nonfinite")
        require(not limit.use_min_x or current>=limit.min_x-1e-6,"current_x_below_actual_limit")
        require(not limit.use_max_x or current<=limit.max_x+1e-6,"current_x_above_actual_limit")
        if parsed["supported"] and wide is not None and math.isfinite(wide):
            a=parsed["a"]
            direction=1 if a>0 else -1
            enabled=limit.use_max_x if direction>0 else limit.use_min_x
            boundary=float(limit.max_x if direction>0 else limit.min_x)
            headroom=direction*(boundary-current)
            gain_cap=FRACTION*(1-wide)/abs(a)
            distance=min(FRACTION*headroom,CONTROL_CAP,gain_cap) if enabled else 0
            target=current+direction*distance
            record["candidate"]={"direction_from_affine_sign":direction,"actual_limit_boundary":boundary,
                "actual_signed_headroom":headroom,"fraction_of_headroom":FRACTION,
                "control_distance_cap":CONTROL_CAP,"unit_gain_cap":gain_cap,
                "delta_local_x":direction*distance,"target_local_x":target,
                "maximum_allowed_wide_increase":FRACTION*(1-wide)+1e-4}
            require(enabled and all(math.isfinite(v) for v in (boundary,headroom,gain_cap,distance,target))
                    and headroom>0 and gain_cap>0 and distance>1e-8,"signed_width_step_unproven")
            require(not limit.use_min_x or target>=limit.min_x-1e-7,"target_below_actual_min_x")
            require(not limit.use_max_x or target<=limit.max_x+1e-7,"target_above_actual_max_x")
    paths={act.path_from_id(k) for k in ("location","rotation_euler","rotation_quaternion","scale")}
    require(not rig.animation_data or not any(not f.mute and f.data_path in paths for f in rig.animation_data.drivers),
            "act_transform_channel_driven")
    consumers=[]
    for consumer in rig.animation_data.drivers if rig.animation_data else ():
        if any(v.type=="SINGLE_PROP" and any(t.id==rig and t.data_path==prop_path for t in v.targets)
               for v in consumer.driver.variables):
            consumers.append({"data_path":consumer.data_path,"index":consumer.array_index,"type":consumer.driver.type,
                              "valid":consumer.is_valid,"muted":consumer.mute})
    record["direct_consumer_count"]=len(consumers)
    record["direct_consumers"]=consumers[:64]
    require(0<len(consumers)<=64,"bounded_direct_wide_consumers_unproven")
    cheek=rig.pose.bones.get("Cheek1_3."+side)
    representative=None
    if cheek is not None:
        for action in cheek.constraints:
            if action.type!="ACTION":
                continue
            path=action.path_from_id("eval_time")
            candidate,candidate_record=face.driver_record(rig,path)
            if candidate is None or candidate.driver.type!="SUM" or len(candidate.driver.variables)!=1:
                continue
            var=candidate.driver.variables[0]
            if not (var.type=="SINGLE_PROP" and len(var.targets)==1
                    and var.targets[0].id==rig and var.targets[0].data_path==prop_path):
                continue
            representative={"owner":cheek.name,"constraint":face.constraint_record(action),"driver":candidate_record}
            require(not action.mute and action.influence>0 and action.action is not None
                    and getattr(action,"use_eval_time",False) and not candidate.mute and candidate.is_valid,
                    "representative_wide_action_not_active")
            break
    record["representative_native_consumer"]=representative
    require(representative is not None,"actual_cheek_wide_consumer_unproven")
    record["mapping_supported"]=not reasons
    record["mapping_scope"]="targeted direct Wide driver/real Cheek consumer only; no complete closure and no invented Corner ActionWide"
    return record

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
        raise ValueError("smile_width_output_overlaps_inputs")
    if sha(source)!=SOURCE_SHA or sha(blend)!=INPUT_SHA or blend.stat().st_size!=INPUT_BYTES:
        raise ValueError("frozen_smile_width_input_hash_mismatch")
    raw=Path(args.config).read_bytes()
    if git_blob(raw)!=CONFIG_BLOB:
        raise ValueError("reviewed_config_hash_mismatch")
    config=json.loads(raw)
    if config["poses"]!={"neutral":[]}:
        raise ValueError("reviewed_source_config_mismatch")
    if producer.stat().st_size>1048576:
        raise ValueError("frozen_producer_audit_oversized")
    frozen=json.loads(producer.read_text(encoding="utf-8"))
    if (frozen["source_sha256"]!=SOURCE_SHA or frozen["derivative"]["sha256"]!=INPUT_SHA
            or frozen["derivative"]["bytes"]!=INPUT_BYTES or not frozen["candidate_completed"]
            or not frozen["preservation_passed"] or not frozen["numeric_face_gates_passed"]
            or frozen["pose_functions_blob"]!=POSE_BLOB or not frozen["texture_hash_recheck"]["complete"]):
        raise ValueError("frozen_friendly_derivative_producer_identity_mismatch")
    camera_config=frozen["camera_config"]
    if (camera_config["resolution"]!=[640,640] or camera_config["angles"]!=[0,35]
            or len(camera_config["target"])!=3
            or not all(math.isfinite(v) for v in (*camera_config["target"],camera_config["scale"],camera_config["distance"]))
            or camera_config["scale"]<=0 or camera_config["distance"]<=0):
        raise ValueError("frozen_head_camera_definition_mismatch")
    out.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        target=out/"credits"/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/relative,target)
        credits.append({"file":str(target.relative_to(out)),"bytes":target.stat().st_size,"sha256":sha(target)})
    audit={"purpose":"ONE smile-width candidate; previous Up and brows held; baseline is softer-neutral only",
        "candidate_kind":"smile-width","source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"input_bytes":INPUT_BYTES,
        "producer_audit_sha256":sha(producer),"friendly_functions_blob":FACE_BLOB,"pose_functions_blob":POSE_BLOB,
        "producer_parent_input_sha256":frozen["input_sha256"],
        "camera_config":camera_config,"camera_reused_from_frozen_producer":True,
        "credits":credits,"renders":[],"used_textures":[],"texture_preparation_complete":False,
        "models_saved":0,"derivative_saved":False,"solver_runs":0,"geometry_edits_performed":False,
        "friendly_art_approved":False,"garment_art_approved":False,"animation_approved":False,
        "production_glb_approved":False,"corrective_system_approved":False,
        "limits":["One width candidate only, not a sweep or final smile/art selection.",
            "Only ACT lip localX changes; previous Up/localY/brows/Mouth/Eyes/arms are held.",
            "Parsed only unit-clamped affine AST data; no expression eval, mute, formula changes or direct OuterLip write.",
            "Raw/key DATA/materials/UV/weights/modifiers/slots/rest rig remain unchanged; finite native values may respond.",
            "Direct Wide/Cheek dependency sample is not complete closure; Corner has no invented ActionWide.",
            "Corner deltaZ is recorded without forcing previous height.",
            "Renderer generic friendly-face-candidate label describes this width variant; filename friendly-face-audit is reused intentionally.",
            "Render helper camera-reference wording describes the ORIGINAL neutral-bounds camera origin; exact config is reused frozen here.",
            "No neutral or Up baseline rerender. External texture paths remain unportable; no GLB/animation acceptance."]}
    path=out/"friendly-face-audit.json"
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
        from mathutils import Vector
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
            raise ValueError("runtime_width_rig_mode_mismatch")
        objects=[]
        for name in config["mesh_names"]:
            obj=bpy.data.objects.get(name)
            if obj is None or obj.type!="MESH":
                raise ValueError("frozen_width_character_mesh_missing")
            objects.append(obj)
        scene=bpy.context.scene
        if scene is None or scene.camera is None or scene.camera.data.type!="ORTHO" or scene.render.engine!="CYCLES" or any(o.name not in scene.objects for o in objects):
            raise ValueError("frozen_width_scene_missing")
        audit["linked_missing_modifier_dependencies"]=pair.ensure_saved_dependency_closure(bpy,scene,objects)
        materials=pair.used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
        images=pair.collect_images(materials)
        manifest={r["image"]:r for r in frozen["used_textures"]}
        if len(manifest)!=len(frozen["used_textures"]) or not images:
            raise ValueError("frozen_width_texture_manifest_not_unique")
        used={}
        for image in images:
            if image.name not in manifest:
                raise ValueError("used_image_not_in_frozen_width_manifest")
            reference=manifest[image.name]
            filename=str(image.filepath).replace("\\","/").split("/")[-1]
            if image.source!=reference["source"] or filename!=reference["filename"] or not reference["size_guard_passed"]:
                raise ValueError("used_image_identity_differs_from_frozen_width_manifest")
            used[image.name]=reference
            expected_files+=len(reference["files"])
        audit["texture_expected_image_count"]=len(images)
        audit["texture_expected_file_count"]=expected_files
        pair.relink_and_reload(images,source.parent/"textures",textures,lambda:write_audit(path,audit))
        for record in textures:
            if record["files"]!=used[record["image"]]["files"]:
                raise ValueError("used_texture_bytes_differ_from_frozen_width_manifest")
        audit["texture_preparation_complete"]=True
        if not recheck():
            raise ValueError("frozen_width_used_texture_verification_failed")
        garment=bpy.data.objects.get("GEO-snow-shirt")
        if (garment not in objects or len(garment.data.vertices)!=1839 or not garment.data.shape_keys
                or len(garment.data.shape_keys.key_blocks)!=10 or not garment.material_slots
                or garment.material_slots[0].link!="OBJECT" or garment.material_slots[0].material is None
                or garment.material_slots[0].material.name!=soft.MATERIAL_NAME or garment.data.materials[0] is not None):
            raise ValueError("frozen_width_shirt_binding_or_geometry_mismatch")
        # Whole frozen blend SHA guards current shader; producer has no old soft-cloth shader-signature field.
        required=["ACT-Lips_Corner."+s for s in ("L","R")]+["OuterLip_Corner."+s for s in ("L","R")]+[
            "MSTR-Eyebrow.L","MSTR-Eyebrow.R","MSTR-Mouth","TGT-Eyes","Properties","MCH-JawOpennessMeasurer",*proof.ARMS]
        missing=[name for name in required if name not in rig.pose.bones]
        audit["missing_required_bones"]=missing
        write_audit(path,audit)
        if missing:
            raise ValueError("verified_width_control_missing")
        bpy.context.view_layer.update()
        inspection=[inspect_width(face,proof,rig,s) for s in ("L","R")]
        audit["width_mapping_inspection"]=inspection
        audit["mapping_supported"]=all(r["mapping_supported"] for r in inspection)
        write_audit(path,audit)
        marker={"mapping_supported":audit["mapping_supported"],"sides":[{
            "side":r["side"],"reasons":r["mapping_reasons"],"current_local_x":r["current_local_x"],
            "wide_before":r["wide_before"],"actual_x_limits":r.get("actual_x_limits"),
            "affine_mapping":r["affine_mapping"],"candidate":r.get("candidate"),"driver":r["driver"],
            "act_constraints":r["constraints"],"direct_consumer_count":r["direct_consumer_count"],
            "representative_native_consumer":r["representative_native_consumer"],
            "outer_corner_constraint_names":r["outer_corner_constraint_names"]} for r in inspection]}
        if len(encoded(marker))>24000:
            raise ValueError("smile_width_inspection_stdout_budget_exceeded")
        print("SNOW_SMILE_WIDTH_INSPECTION "+encoded(marker).decode().strip(),flush=True)
        if not audit["mapping_supported"]:
            raise ValueError("smile_width_mapping_unproven")
        act=[rig.pose.bones["ACT-Lips_Corner."+s] for s in ("L","R")]
        control_before={b.name:proof.channels(b) for b in act}
        up_before={s:float(rig.pose.bones["ACT-Lips_Corner."+s]["RIG-snow-LipsUp."+s]) for s in ("L","R")}
        audit["up_before"]=up_before
        if any(not math.isfinite(v) or abs(v-0.2000133)>1e-4 for v in up_before.values()):
            raise ValueError("frozen_lips_up_baseline_value_mismatch")
        held_names=["MSTR-Eyebrow.L","MSTR-Eyebrow.R","MSTR-Mouth","TGT-Eyes",*proof.ARMS]
        held_before={name:proof.channels(rig.pose.bones[name]) for name in held_names}
        audit["held_controls_before"]=held_before
        jaw_before=rig.pose.bones["MCH-JawOpennessMeasurer"].matrix.copy()
        corner_before={s:(rig.matrix_world@rig.pose.bones["OuterLip_Corner."+s].head).copy() for s in ("L","R")}
        props_before=proof.properties(rig.pose.bones["Properties"])
        rig_before=proof.rest_rig_hash(rig)
        raw_before=proof.raw_preservation(bpy,helper,soft)
        graphs_before=proof.material_graph_hash(bpy,pair)
        keys_before=proof.key_values(bpy)
        audit["raw_preservation_before"]=raw_before
        audit["material_graph_sha256_before"]=graphs_before
        audit["rig_rest_sha256_before"]=rig_before
        audit["native_key_values_before"]=keys_before
        audit["driver_before"]=soft.driver_summary(helper,bpy)
        if audit["driver_before"]["active_invalid"]!=0:
            raise ValueError("native_driver_invalid_before_width_candidate")
        inspected_names=[b.name for b in act]+["OuterLip_Corner.L","OuterLip_Corner.R"]
        for r in inspection:
            inspected_names.append(r["representative_native_consumer"]["owner"])
        inspected_names=sorted(set(inspected_names))
        configs_before=face.constraint_config_hash(proof,rig,inspected_names)
        head=bpy.data.objects["GEO-snow-head"]
        head_before=proof.evaluated_snapshot(bpy,[head])
        audit["intentional_changes"]=[{"bone":r["act"]["name"],"channel":"location.x",
            "before":r["current_local_x"],"after":r["candidate"]["target_local_x"],
            "delta":r["candidate"]["delta_local_x"],"rule":r["candidate"]} for r in inspection]
        write_audit(path,audit)
        for bone,r in zip(act,inspection):
            bone.location.x=r["candidate"]["target_local_x"]
        bpy.context.view_layer.update()
        response=[]
        for bone,r in zip(act,inspection):
            side=r["side"]
            wide=float(bone[r["wide_property"]])
            up=float(bone["RIG-snow-LipsUp."+side])
            corner=rig.matrix_world@rig.pose.bones["OuterLip_Corner."+side].head
            delta=corner-corner_before[side]
            outward=delta.x if side=="L" else -delta.x
            rep=r["representative_native_consumer"]
            action=rig.pose.bones[rep["owner"]].constraints[rep["constraint"]["name"]]
            record={"side":side,"wide_before":r["wide_before"],"wide_after":wide,
                "wide_increase":wide-r["wide_before"],"max_wide_increase":r["candidate"]["maximum_allowed_wide_increase"],
                "up_before":up_before[side],"up_after":up,"up_absolute_drift":abs(up-up_before[side]),
                "corner_before":list(corner_before[side]),"corner_after":list(corner),"corner_delta_world":list(delta),
                "outward_world_x_distance":outward,"corner_delta_z_not_forced":delta.z,
                "actual_local_x":float(bone.location.x),"requested_local_x":r["candidate"]["target_local_x"],
                "representative_eval_time_after":float(action.eval_time),
                "representative_sum_residual":abs(float(action.eval_time)-wide)}
            record["response_passed"]=(all(math.isfinite(v) for v in (wide,up,*delta,float(action.eval_time)))
                and 0<=wide<=1 and record["wide_increase"]>1e-7
                and record["wide_increase"]<=record["max_wide_increase"] and outward>1e-6
                and record["up_absolute_drift"]<=1e-4 and record["representative_sum_residual"]<1e-5
                and abs(record["actual_local_x"]-record["requested_local_x"])<1e-7)
            response.append(record)
        audit["native_width_response"]=response
        audit["corner_symmetry"]={"outward_x_distance_difference":abs(response[0]["outward_world_x_distance"]-response[1]["outward_world_x_distance"]),
            "delta_z_difference":abs(response[0]["corner_delta_z_not_forced"]-response[1]["corner_delta_z_not_forced"]),
            "not_an_art_acceptance":True}
        audit["direct_controls_after"]={b.name:proof.control_record(rig,b) for b in act}
        audit["driver_after_pose"]=soft.driver_summary(helper,bpy)
        audit["native_key_values_after_pose"]=proof.key_values(bpy)
        write_audit(path,audit)
        if not all(r["response_passed"] for r in response):
            raise ValueError("native_width_gain_outward_corner_or_up_hold_unproven")
        for bone in act:
            before=control_before[bone.name]
            now=proof.channels(bone)
            if any(now[k]!=before[k] for k in now if k!="location") or any(now["location"][i]!=before["location"][i] for i in (1,2)):
                raise ValueError("unintended_width_control_channel_change")
            if any(lock and now["location"][i]!=before["location"][i] for i,lock in enumerate(before["lock_location"])):
                raise ValueError("locked_width_control_channel_changed")
        if {name:proof.channels(rig.pose.bones[name]) for name in held_names}!=held_before:
            raise ValueError("brows_mouth_eyes_or_arms_changed_during_width")
        if proof.matrix_error(jaw_before,rig.pose.bones["MCH-JawOpennessMeasurer"].matrix)>1e-6:
            raise ValueError("jaw_mapping_target_changed_during_width")
        if face.constraint_config_hash(proof,rig,inspected_names)!=configs_before:
            raise ValueError("native_width_constraint_configuration_changed")
        audit["pose_preservation_passed"]=(proof.raw_preservation(bpy,helper,soft)==raw_before
            and proof.material_graph_hash(bpy,pair)==graphs_before and proof.rest_rig_hash(rig)==rig_before
            and proof.properties(rig.pose.bones["Properties"])==props_before
            and audit["driver_after_pose"]["active_invalid"]==0)
        if not audit["pose_preservation_passed"]:
            raise ValueError("width_raw_material_rig_or_driver_preservation_failed")
        head_after=proof.evaluated_snapshot(bpy,[head])
        audit["head_evaluated_before"]=proof.evaluated_report(head_before)
        audit["head_evaluated_after"]=proof.evaluated_report(head_after)
        audit["head_deformation"]=proof.deformation(head_before,head_after)
        deformation=audit["head_deformation"][head.name]
        if not deformation["evaluated_topology_comparable"] or deformation["changed_vertices"]==0 or deformation["maximum_world_displacement"]<=1e-6:
            raise ValueError("actual_width_head_deformation_unproven")
        audit["numeric_face_gates_passed"]=True
        audit["numeric_width_gates_passed"]=True
        if not recheck():
            raise ValueError("smile_width_inputs_changed_before_render")
        write_audit(path,audit)
        scene.cycles.seed=SEED
        scene.cycles.use_animated_seed=False
        target=Vector(camera_config["target"])
        for name,angle in (("front",0),("threequarter",35)):
            shot={"name":name,"angle":angle,"target":camera_config["target"],
                "scale":camera_config["scale"],"distance":camera_config["distance"]}
            a=math.radians(angle)
            scene.camera.location=target+Vector((math.sin(a)*shot["distance"],-math.cos(a)*shot["distance"],0.01))
            scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat("-Z","Y").to_euler()
            scene.camera.data.ortho_scale=shot["scale"]
            scene.render.resolution_x=scene.render.resolution_y=640
            scene.render.resolution_percentage=100
            bpy.context.view_layer.update()
            before=pair.control_snapshot(bpy,scene,objects,materials,None,None)
            face.render_face(bpy,out,scene,shot,audit,args.emit_preview)
            after=pair.control_snapshot(bpy,scene,objects,materials,None,None)
            if before["sha256"]!=after["sha256"]:
                raise ValueError("smile_width_render_controls_changed")
            audit["renders"][-1]["candidate_kind"]="smile-width"
            audit["renders"][-1]["camera_reused_from_frozen_producer"]=True
            audit.setdefault("render_controls",[]).append({"view":name,"before":before["sha256"],"after":after["sha256"],
                "match":True,"candidate_kind":"smile-width","seed":SEED,"use_animated_seed":False})
            write_audit(path,audit)
        audit["driver_after_render"]=soft.driver_summary(helper,bpy)
        audit["native_key_values_after_render"]=proof.key_values(bpy)
        audit["preservation_passed"]=(proof.raw_preservation(bpy,helper,soft)==raw_before
            and proof.material_graph_hash(bpy,pair)==graphs_before and proof.rest_rig_hash(rig)==rig_before
            and proof.properties(rig.pose.bones["Properties"])==props_before
            and face.constraint_config_hash(proof,rig,inspected_names)==configs_before
            and {name:proof.channels(rig.pose.bones[name]) for name in held_names}==held_before
            and all(abs(float(rig.pose.bones["ACT-Lips_Corner."+s]["RIG-snow-LipsUp."+s])-up_before[s])<=1e-4 for s in ("L","R")))
        if len(audit["renders"])!=2 or not audit["preservation_passed"] or audit["driver_after_render"]["active_invalid"]!=0 or not recheck():
            raise ValueError("smile_width_final_guard_failed")
        write_audit(path,audit)
        output=out/"snow-smile-width-prototype.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(output),check_existing=False)
        audit["models_saved"]=1
        audit["derivative_saved"]=True
        audit["derivative"]={"file":output.name,"bytes":output.stat().st_size,"sha256":sha(output),
            "textures_packed":False,"external_texture_paths_portable":False,"requires_original_texture_relink":True}
        audit["candidate_completed"]=True
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
            marker={"candidate_completed":audit.get("candidate_completed",False),"candidate_kind":"smile-width",
                "failure":audit.get("failure"),"mapping_supported":audit.get("mapping_supported",False),
                "mapping_reasons":[{"side":r["side"],"reasons":r["mapping_reasons"]} for r in audit.get("width_mapping_inspection",[])],
                "numeric_width_gates_passed":audit.get("numeric_width_gates_passed",False),
                "native_width_response":audit.get("native_width_response"),"symmetry":audit.get("corner_symmetry"),
                "intentional_changes":audit.get("intentional_changes"),"renders":len(audit["renders"]),
                "views":[r["view"] for r in audit["renders"]],"models_saved":audit["models_saved"],
                "derivative_saved":audit["derivative_saved"],"derivative":audit.get("derivative"),
                "neutral_or_up_baseline_renders":0,"solver_runs":0,"source_and_input_unchanged":audit.get("source_and_input_unchanged"),
                "texture_hash_recheck":audit.get("texture_hash_recheck"),"native_policy":audit.get("native_policy"),
                "driver_before":audit.get("driver_before"),"driver_after":audit.get("driver_after_render",audit.get("driver_after_pose")),
                "preservation_passed":audit.get("preservation_passed",False),"head_deformation":audit.get("head_deformation"),
                "render_controls":audit.get("render_controls",[]),"friendly_art_approved":False,
                "garment_art_approved":False,"animation_approved":False,"production_glb_approved":False,
                "corrective_system_approved":False,"raw_to_evaluated_mapping":"unproven; matched viewport topology only",
                "external_texture_paths_portable":False}
            if len(encoded(marker))>24000:
                raise ValueError("smile_width_stdout_byte_budget_exceeded")
            print("SNOW_SMILE_WIDTH_CANDIDATE "+encoded(marker).decode().strip(),flush=True)
            if failure is None and not readonly:
                raise ValueError("smile_width_final_readonly_check_failed")
        except Exception as cleanup_error:
            if failure is None:
                raise
            print("SNOW_SMILE_WIDTH_CLEANUP_FAILED "+json.dumps({"error_type":type(cleanup_error).__name__[:80]}),flush=True)

if __name__=="__main__":
    main()
