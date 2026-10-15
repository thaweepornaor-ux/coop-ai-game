"""Conditional friendly-face candidate on frozen neutral soft-cloth Snow.
Runtime mapping inspection first; unsupported mapping stops before posing/rendering.
No driver expressions are evaluated by Python. No arm application/imported main runs.
"""
import argparse
import ast
import base64
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

POSE_BLOB="23ff416d8c2744b9d8eaafd51fbe9e3fe1504e7a"
SOFT_BLOB="405a46b744084975adbe23f59d494cdc29d5e0a1"
PAIR_BLOB="d04197931cf9b705612d4d99d53e79be643e491e"
HELPER_BLOB="a64c4f14e977a6ae720fb57b01ffa9f69d5703f8"
CONFIG_BLOB="f0612039b320e8dac77587ec4aecdc2c84618843"
SOURCE_SHA="80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
INPUT_SHA="02e4f1300a90426dcfc83621020df40af898a3671d2fc970b9e2d9a39788031d"
INPUT_BYTES=8468919
SEED=1729
BROW_DELTA=0.002
LIP_FRACTION=0.2
LIP_CAP=0.006

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n").encode()

def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def write_audit(path,audit):
    raw=encoded(audit)
    if len(raw)>1048576:
        raise ValueError("friendly_face_audit_byte_budget_exceeded")
    path.write_bytes(raw)

def load_reviewed():
    path=Path(__file__).with_name("bpy-proof-snow-raised-arms.py")
    if git_blob(path.read_bytes())!=POSE_BLOB:
        raise ValueError("reviewed_pose_wrapper_hash_mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_snow_pose_functions",path)
    proof=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    soft,pair,helper=proof.load_reviewed()
    if (proof.SOFT_BLOB!=SOFT_BLOB or proof.PAIR_BLOB!=PAIR_BLOB
            or proof.HELPER_BLOB!=HELPER_BLOB or proof.CONFIG_BLOB!=CONFIG_BLOB):
        raise ValueError("reviewed_face_import_chain_mismatch")
    return proof,soft,pair,helper

def positive_local_y_structure(expression,variable):
    """Bounded AST DATA whitelist, not an evaluator of the variable expression.
    Proves nondecreasing dependence using positive affine operations/min-max clamps.
    Strict positive response must separately be observed in Blender's native driver.
    """
    if len(expression)>2048 or variable in ("min","max","clamp"):
        return {"supported":False,"reason":"unsupported_expression_size_or_variable"}
    try:
        tree=ast.parse(expression,mode="eval")
        if sum(1 for _ in ast.walk(tree))>96:
            raise ValueError("expression_ast_budget")
        def classify(node,depth=0):
            if depth>14:
                raise ValueError("expression_ast_depth")
            if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)) and not isinstance(node.value,bool):
                value=float(node.value)
                if not math.isfinite(value):
                    raise ValueError("nonfinite_literal")
                return False,value
            if isinstance(node,ast.Name) and node.id==variable:
                return True,None
            if isinstance(node,ast.UnaryOp):
                dependent,value=classify(node.operand,depth+1)
                if isinstance(node.op,ast.UAdd):
                    return dependent,value
                if isinstance(node.op,ast.USub) and not dependent:
                    return False,-value
                raise ValueError("unsupported_unary")
            if isinstance(node,ast.BinOp):
                da,a=classify(node.left,depth+1)
                db,b=classify(node.right,depth+1)
                if isinstance(node.op,ast.Add):
                    result=(da or db,None) if da or db else (False,a+b)
                elif isinstance(node.op,ast.Sub) and not db:
                    result=(True,None) if da else (False,a-b)
                elif isinstance(node.op,ast.Mult) and not (da and db):
                    if not da and not db:
                        result=False,a*b
                    else:
                        scale=b if da else a
                        if scale<=0:
                            raise ValueError("nonpositive_scale")
                        result=True,None
                elif isinstance(node.op,ast.Div) and not db and b>0:
                    result=(True,None) if da else (False,a/b)
                else:
                    raise ValueError("unsupported_arithmetic")
                if not result[0] and not math.isfinite(result[1]):
                    raise ValueError("nonfinite_literal_arithmetic")
                return result
            # Blender v4.5.9 unary op_clamp is the fixed [0,1] monotone clamp.
            # Only this measured one-argument form is supported; no arbitrary call runs.
            if (isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
                    and node.func.id=="clamp" and len(node.args)==1 and not node.keywords):
                dependent,value=classify(node.args[0],depth+1)
                return (True,None) if dependent else (False,min(max(value,0.0),1.0))
            if (isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
                    and node.func.id in ("min","max") and len(node.args)==2 and not node.keywords):
                a,b=[classify(arg,depth+1) for arg in node.args]
                if a[0] or b[0]:
                    return True,None
                return False,min(a[1],b[1]) if node.func.id=="min" else max(a[1],b[1])
            raise ValueError("unsupported_expression_structure")
        dependent,_=classify(tree.body)
        return {"supported":dependent,"reason":None if dependent else "constant_expression",
                "scope":"data-only nondecreasing structure; native positive response still required"}
    except (SyntaxError,ValueError,TypeError,ZeroDivisionError,OverflowError) as error:
        return {"supported":False,"reason":type(error).__name__}

def constraint_record(constraint):
    fields=("owner_space","target_space","mute","influence","use_min_x","use_min_y","use_min_z",
        "use_max_x","use_max_y","use_max_z","min_x","min_y","min_z","max_x","max_y","max_z",
        "use_transform_limit","map_from","map_to","map_to_x_from","map_to_y_from","map_to_z_from",
        "from_min_x","from_min_y","from_min_z","from_max_x","from_max_y","from_max_z",
        "from_min_x_rot","from_min_y_rot","from_min_z_rot","from_max_x_rot","from_max_y_rot","from_max_z_rot",
        "from_min_x_scale","from_min_y_scale","from_min_z_scale","from_max_x_scale","from_max_y_scale","from_max_z_scale",
        "to_min_x","to_min_y","to_min_z","to_max_x","to_max_y","to_max_z","mix_mode","mix_mode_rot",
        "mix_mode_scale","mix_mode_loc","use_motion_extrapolate","use_eval_time","eval_time","frame_start","frame_end",
        "min","max","transform_channel","use_bone_object_action")
    result={"name":constraint.name,"type":constraint.type}
    for name in fields:
        if hasattr(constraint,name):
            value=getattr(constraint,name)
            if isinstance(value,(str,bool,int,float)):
                result[name]=value
    for name in ("target","action"):
        block=getattr(constraint,name,None)
        result[name]=block.name if block else None
    result["subtarget"]=getattr(constraint,"subtarget",None)
    slot=getattr(constraint,"action_slot",None)
    result["action_slot"]=getattr(slot,"identifier",None) if slot else None
    targets=getattr(constraint,"targets",None)
    if targets is not None:
        result["targets"]=[{"target":t.target.name if t.target else None,"subtarget":t.subtarget,
                            "weight":float(t.weight)} for t in targets]
    return result

def driver_record(rig,path):
    curves=[f for f in rig.animation_data.drivers if f.data_path==path and f.array_index==0] if rig.animation_data else []
    record={"data_path":path,"matching_curve_count":len(curves)}
    if len(curves)!=1:
        return None,record
    curve=curves[0]
    driver=curve.driver
    record.update({"type":driver.type,"muted":curve.mute,"valid":curve.is_valid,
        "native_simple":driver.is_simple_expression if driver.type=="SCRIPTED" else True,
        "expression":driver.expression[:2048] if driver.type=="SCRIPTED" else None,
        "expression_truncated":driver.type=="SCRIPTED" and len(driver.expression)>2048,
        "variables":[{"name":v.name,"type":v.type,"targets":[{
            "id":getattr(t.id,"name",None),"bone_target":t.bone_target,"data_path":t.data_path,
            "transform_type":t.transform_type,"transform_space":t.transform_space}
            for t in v.targets]} for v in driver.variables]})
    return curve,record

def inspect_lip(proof,rig,side):
    act=rig.pose.bones["ACT-Lips_Corner."+side]
    outer=rig.pose.bones["OuterLip_Corner."+side]
    key="RIG-snow-LipsUp."+side
    action_name="Action "+key
    constraints={c.name:c for c in act.constraints}
    action=outer.constraints.get(action_name)
    prop_path=act.path_from_id()+"["+json.dumps(key)+"]"
    curve,up=driver_record(rig,prop_path)
    action_curve,action_driver=driver_record(rig,action.path_from_id("eval_time")) if action else (None,{"matching_curve_count":0})
    limit=constraints.get("KEEP-Limit Location")
    transform=constraints.get("KEEP-Transformation")
    current=float(act.location.y)
    record={"side":side,"act":proof.control_record(rig,act),"outer":proof.control_record(rig,outer),
        "property":key,"property_present":key in act,"current_local_y":current,
        "act_constraints":[constraint_record(c) for c in act.constraints],
        "outer_constraints":[constraint_record(c) for c in outer.constraints],
        "up_driver":up,"action_eval_time_driver":action_driver,"mapping_reasons":[]}
    reasons=record["mapping_reasons"]
    def require(ok,reason):
        if not ok:
            reasons.append(reason)
    require(act.parent is not None and act.parent.name=="CON-ACT-Lips_Corner."+side,"act_parent_mismatch")
    require(act.rotation_mode in proof.MODES,"unsupported_act_rotation_mode")
    require(not act.lock_location[1],"act_local_y_locked")
    expected={"KEEP-Limit Location":"LIMIT_LOCATION","KEEP-Limit Scale":"LIMIT_SCALE","KEEP-Transformation":"TRANSFORM"}
    require(set(constraints)==set(expected) and all(constraints[n].type==t for n,t in expected.items() if n in constraints),
            "act_constraint_set_mismatch")
    require(all(not c.mute and c.influence>0 for c in act.constraints),"act_constraint_not_active")
    if limit:
        require(limit.type=="LIMIT_LOCATION" and limit.owner_space=="LOCAL","local_limit_space_unproven")
        require(limit.use_max_y,"positive_y_max_not_enabled")
        upper=float(limit.max_y)
        lower=float(limit.min_y) if limit.use_min_y else None
        record["actual_local_y_limit"]={"max":upper,"min":lower,"owner_space":limit.owner_space,
            "use_max":limit.use_max_y,"use_min":limit.use_min_y,"use_transform_limit":limit.use_transform_limit}
        require(math.isfinite(upper) and upper>0 and upper>current,"positive_headroom_unproven")
        require(lower is None or math.isfinite(lower) and current>=lower-1e-6,"current_y_below_actual_limit")
        require(current<=upper+1e-6,"current_y_above_actual_limit")
        delta=min(LIP_CAP,LIP_FRACTION*(upper-current)) if math.isfinite(upper) else 0
        record["candidate_delta_local_y"]=delta
        record["candidate_local_y"]=current+delta
        require(math.isfinite(delta) and delta>1e-7 and current+delta<=upper,"candidate_headroom_invalid")
    else:
        reasons.append("actual_limit_missing")
    jaw=rig.pose.bones.get("MCH-JawOpennessMeasurer")
    require(transform is not None and transform.type=="TRANSFORM" and transform.target==rig
            and transform.subtarget=="MCH-JawOpennessMeasurer" and jaw is not None,"jaw_transform_target_unproven")
    if jaw:
        record["jaw_matrix_before"]=proof.matrix(jaw.matrix)
    require(key in act,"up_property_missing")
    if key in act:
        record["up_value_before"]=float(act[key])
        try:
            record["up_property_ui"]=proof.plain(act.id_properties_ui(key).as_dict())
        except (TypeError,ValueError,RuntimeError):
            record["up_property_ui"]={"available":False}
        require(math.isfinite(float(act[key])),"up_value_not_finite")
    valid_up=(curve is not None and curve.driver.type=="SCRIPTED" and not curve.mute
              and curve.is_valid and curve.driver.is_simple_expression and len(curve.driver.variables)==1)
    require(valid_up,"up_driver_native_structure_unproven")
    if valid_up:
        variable=curve.driver.variables[0]
        valid_target=(variable.type=="TRANSFORMS" and len(variable.targets)==1
            and variable.targets[0].id==rig and variable.targets[0].bone_target==act.name
            and variable.targets[0].transform_type=="LOC_Y"
            and variable.targets[0].transform_space in ("TRANSFORM_SPACE","LOCAL_SPACE"))
        require(valid_target,"up_transform_source_or_space_unproven")
        structure=positive_local_y_structure(curve.driver.expression,variable.name)
        record["expression_structure"]=structure
        require(structure["supported"],"up_expression_positive_structure_unproven")
    if action:
        record["up_action"]=constraint_record(action)
        require(action.type=="ACTION" and not action.mute and action.influence>0
                and action.action is not None and getattr(action,"use_eval_time",False),"active_eval_time_action_unproven")
        require(action.frame_end>action.frame_start,"action_frame_interval_unproven")
        prop=action.bl_rna.properties["eval_time"]
        record["action_eval_time_hard_range"]={"min":float(prop.hard_min),"max":float(prop.hard_max)}
    else:
        reasons.append("up_action_missing")
    valid_action=(action_curve is not None and action_curve.driver.type=="SUM" and not action_curve.mute
                  and action_curve.is_valid and len(action_curve.driver.variables)==1)
    require(valid_action,"action_sum_mapping_unproven")
    if valid_action:
        variable=action_curve.driver.variables[0]
        require(variable.type=="SINGLE_PROP" and len(variable.targets)==1
                and variable.targets[0].id==rig and variable.targets[0].data_path==prop_path,
                "action_sum_property_target_mismatch")
    paths={act.path_from_id(field) for field in ("location","rotation_euler","rotation_quaternion","scale")}
    require(not rig.animation_data or not any(not f.mute and f.data_path in paths for f in rig.animation_data.drivers),
            "act_transform_channels_driven")
    record["mapping_supported"]=not reasons
    record["mapping_scope"]="direct local-Y monotone structure plus fixed local constraints; native positive step must still be observed"
    return record

def constraint_config_hash(proof,rig,names):
    records=[]
    for name in names:
        for c in rig.pose.bones[name].constraints:
            record=constraint_record(c)
            record.pop("eval_time",None)
            records.append({"owner":name,"constraint":record})
    return proof.digest(records)

def render_face(bpy,out,scene,shot,audit,emit_preview):
    from mathutils import Vector
    target=Vector(shot["target"])
    angle=math.radians(shot["angle"])
    camera=scene.camera
    camera.location=target+Vector((math.sin(angle)*shot["distance"],-math.cos(angle)*shot["distance"],0.01))
    camera.rotation_euler=(target-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.ortho_scale=shot["scale"]
    scene.render.resolution_x=scene.render.resolution_y=640
    scene.render.resolution_percentage=100
    bpy.context.view_layer.update()
    file=out/("snow-friendly-face-"+shot["name"]+".png")
    scene.render.filepath=str(file)
    bpy.ops.render.render(write_still=True,scene=scene.name)
    record={"model":"snow","phase":"friendly-face-candidate","pose":"friendly-face-candidate",
        "view":shot["name"],"file":file.name,"bytes":file.stat().st_size,"sha256":sha(file),
        "resolution":[640,640],"camera_target_world":shot["target"],
        "camera_azimuth":shot["angle"],"camera_ortho_scale":shot["scale"],
        "camera_reference":"NEW input-neutral head+hair bounds crop; no old baseline rerender",
        "before_after_comparison_render":False,"neutral_baseline_rerendered":False}
    audit["renders"].append(record)
    write_audit(out/"friendly-face-audit.json",audit)
    print("AVATAR_ACTUAL_RENDER "+encoded(record).decode().strip(),flush=True)
    if emit_preview:
        image=bpy.data.images.load(str(file),check_existing=False)
        image.scale(320,320)
        preview=file.with_name(file.stem+"-preview.jpg")
        image.file_format,image.filepath_raw="JPEG",str(preview)
        image.save()
        while preview.stat().st_size>65536 and image.size[0]>128:
            n=max(128,int(image.size[0]*0.8))
            image.scale(n,n)
            image.save()
        if preview.stat().st_size>65536:
            raise ValueError("face_preview_byte_budget_exceeded")
        dimensions=list(image.size)
        bpy.data.images.remove(image)
        print("AVATAR_ACTUAL_JPEG "+json.dumps({"model":"snow","phase":"friendly-face-candidate",
            "pose":"friendly-face-candidate","view":shot["name"],"mime_type":"image/jpeg",
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
        raise ValueError("friendly_face_output_overlaps_inputs")
    if sha(source)!=SOURCE_SHA or blend.stat().st_size!=INPUT_BYTES or sha(blend)!=INPUT_SHA:
        raise ValueError("frozen_friendly_face_input_hash_mismatch")
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
    out.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        destination=out/"credits"/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/relative,destination)
        credits.append({"file":str(destination.relative_to(out)),"bytes":destination.stat().st_size,"sha256":sha(destination)})
    audit={"purpose":"Conditional native friendly-face candidate; direct mapping inspected before pose",
        "source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"input_bytes":INPUT_BYTES,
        "producer_audit_sha256":sha(producer),"pose_functions_blob":POSE_BLOB,"credits":credits,
        "renders":[],"used_textures":[],"texture_preparation_complete":False,"models_saved":0,
        "solver_runs":0,"geometry_edits_performed":False,"derivative_saved":False,
        "garment_art_approved":False,"production_glb_approved":False,"animation_approved":False,
        "friendly_art_approved":False,"corrective_system_approved":False,
        "limits":["Numeric positive response is not visual smile acceptance.",
            "Only ACT lip localY and unconstrained MSTR brow localY are written; no direct OuterLip/TGT/Mouth writes.",
            "Driver expression AST is read as data using a small monotonic structure whitelist; no Python expression evaluation.",
            "Direct mapping and one native step are inspected, not complete driver dependency closure or general rig acceptance.",
            "Raw/key DATA/materials remain unchanged; native pose/key VALUES may change within actual finite RNA hard ranges.",
            "New front and 35 degree head crops only; no full-body or neutral baseline rerender.",
            "Other textures remain external restored CI paths; saved derivative is not portable or GLB."]}
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
        ready=sum(record.get("size_guard_passed",False) for record in textures)
        complete=(expected is not None and expected>0 and len(textures)==ready==expected
            and audit["texture_preparation_complete"] and count==expected_files and count>0)
        audit["source_and_input_unchanged"]=unchanged
        audit["texture_hash_recheck"]={"expected_images":expected,"attempted_images":len(textures),"ready_images":ready,
            "expected_files":expected_files,"checked_files":count,"complete":complete,
            "all_checked_files_unchanged":matches if count else None}
        return unchanged and complete and matches
    try:
        proof,soft,pair,helper=load_reviewed()
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
            raise ValueError("runtime_face_rig_mode_mismatch")
        objects=[]
        for name in config["mesh_names"]:
            obj=bpy.data.objects.get(name)
            if obj is None or obj.type!="MESH":
                raise ValueError("frozen_character_mesh_missing")
            objects.append(obj)
        scene=bpy.context.scene
        if scene is None or scene.camera is None or scene.camera.data.type!="ORTHO" or scene.render.engine!="CYCLES" or any(o.name not in scene.objects for o in objects):
            raise ValueError("frozen_face_scene_missing")
        audit["linked_missing_modifier_dependencies"]=pair.ensure_saved_dependency_closure(bpy,scene,objects)
        materials=pair.used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
        images=pair.collect_images(materials)
        manifest={r["image"]:r for r in frozen["used_textures"]}
        if len(manifest)!=len(frozen["used_textures"]) or not images:
            raise ValueError("frozen_texture_manifest_not_unique")
        used={}
        for image in images:
            if image.name not in manifest:
                raise ValueError("used_image_not_in_frozen_manifest")
            reference=manifest[image.name]
            filename=str(image.filepath).replace("\\","/").split("/")[-1]
            if image.source!=reference["source"] or filename!=reference["filename"] or not reference["size_guard_passed"]:
                raise ValueError("used_image_identity_differs_from_frozen_manifest")
            used[image.name]=reference
            expected_files+=len(reference["files"])
        audit["texture_expected_image_count"]=len(images)
        audit["texture_expected_file_count"]=expected_files
        pair.relink_and_reload(images,source.parent/"textures",textures,lambda:write_audit(path,audit))
        for record in textures:
            if record["files"]!=used[record["image"]]["files"]:
                raise ValueError("used_texture_bytes_differ_from_frozen_manifest")
        audit["texture_preparation_complete"]=True
        if not recheck():
            raise ValueError("frozen_used_texture_verification_failed")
        garment=bpy.data.objects.get("GEO-snow-shirt")
        if (garment not in objects or len(garment.data.vertices)!=1839
                or not garment.data.shape_keys or len(garment.data.shape_keys.key_blocks)!=10
                or garment.material_slots[0].link!="OBJECT" or garment.data.materials[0] is not None
                or garment.material_slots[0].material is None
                or garment.material_slots[0].material.name!=soft.MATERIAL_NAME):
            raise ValueError("frozen_soft_cloth_binding_or_geometry_mismatch")
        if soft.shader_signature(pair,garment.material_slots[0].material)!=frozen["new_target_shader_signature"]:
            raise ValueError("frozen_soft_cloth_shader_signature_mismatch")
        required=["ACT-Lips_Corner."+s for s in ("L","R")]+["OuterLip_Corner."+s for s in ("L","R")]+["MSTR-Eyebrow."+s for s in ("L","R")]+["MSTR-Mouth","TGT-Eyes","Properties","MCH-JawOpennessMeasurer"]
        missing=[name for name in required if name not in rig.pose.bones]
        audit["missing_required_bones"]=missing
        write_audit(path,audit)
        if missing:
            raise ValueError("friendly_face_verified_control_missing")
        bpy.context.view_layer.update()
        inspection=[inspect_lip(proof,rig,side) for side in ("L","R")]
        audit["lip_mapping_inspection"]=inspection
        audit["mapping_supported"]=all(r["mapping_supported"] for r in inspection)
        write_audit(path,audit)
        inspection_marker={"mapping_supported":audit["mapping_supported"],"sides":[{
            "side":r["side"],"reasons":r["mapping_reasons"],"current_local_y":r["current_local_y"],
            "actual_local_y_limit":r.get("actual_local_y_limit"),"candidate_delta_local_y":r.get("candidate_delta_local_y"),
            "up_value_before":r.get("up_value_before"),"up_driver":r["up_driver"],
            "expression_structure":r.get("expression_structure"),"action_eval_time_driver":r["action_eval_time_driver"],
            "up_action":r.get("up_action"),"act_constraints":r["act_constraints"]} for r in inspection]}
        if len(encoded(inspection_marker))>24000:
            raise ValueError("friendly_face_inspection_stdout_budget_exceeded")
        print("SNOW_FRIENDLY_FACE_INSPECTION "+encoded(inspection_marker).decode().strip(),flush=True)
        if not audit["mapping_supported"]:
            raise ValueError("friendly_face_mapping_unproven")
        targets=[rig.pose.bones["ACT-Lips_Corner."+s] for s in ("L","R")]
        brows=[rig.pose.bones["MSTR-Eyebrow."+s] for s in ("L","R")]
        control_before={b.name:proof.channels(b) for b in targets+brows}
        audit["direct_controls_before"]={b.name:proof.control_record(rig,b) for b in targets+brows}
        audit["brow_local_y_delta"]=BROW_DELTA
        brow_predictions=[]
        for brow in brows:
            if brow.rotation_mode not in proof.MODES or brow.lock_location[1] or len(brow.constraints)!=0:
                raise ValueError("brow_local_y_unconstrained_unlocked_mapping_unproven")
            transform_paths={brow.path_from_id(k) for k in ("location","rotation_euler","rotation_quaternion","scale")}
            if rig.animation_data and any(not f.mute and f.data_path in transform_paths for f in rig.animation_data.drivers):
                raise ValueError("brow_transform_channel_has_active_driver")
            basis=brow.matrix_basis.copy()
            basis.translation.y+=BROW_DELTA
            kw={"parent_matrix":brow.parent.matrix.copy(),"parent_matrix_local":brow.parent.bone.matrix_local.copy()} if brow.parent else {}
            planned=brow.bone.convert_local_to_pose(basis,brow.bone.matrix_local,**kw)
            delta=rig.matrix_world@planned.translation-rig.matrix_world@brow.matrix.translation
            brow_predictions.append({"bone":brow.name,"predicted_world_delta":list(delta),
                "world_up_alignment":delta.normalized().z if delta.length else None})
        audit["brow_axis_predictions"]=brow_predictions
        write_audit(path,audit)
        if any(r["world_up_alignment"] is None or r["world_up_alignment"]<0.95 or r["predicted_world_delta"][2]<=0 for r in brow_predictions):
            raise ValueError("brow_local_y_world_up_mapping_unproven")
        driver_before=soft.driver_summary(helper,bpy)
        audit["driver_before"]=driver_before
        if driver_before["active_invalid"]!=0:
            raise ValueError("native_driver_invalid_before_face_candidate")
        raw_before=proof.raw_preservation(bpy,helper,soft)
        graphs_before=proof.material_graph_hash(bpy,pair)
        rig_before=proof.rest_rig_hash(rig)
        props_before=proof.properties(rig.pose.bones["Properties"])
        keys_before=proof.key_values(bpy)
        audit["raw_preservation_before"]=raw_before
        audit["material_graph_sha256_before"]=graphs_before
        audit["rig_rest_sha256_before"]=rig_before
        audit["native_key_values_before"]=keys_before
        held_names=["MSTR-Mouth","TGT-Eyes",*proof.ARMS]
        held_before={n:proof.channels(rig.pose.bones[n]) for n in held_names}
        audit["held_controls_before"]=held_before
        inspected_names=[b.name for b in targets+brows]+["OuterLip_Corner.L","OuterLip_Corner.R"]
        configs_before=constraint_config_hash(proof,rig,inspected_names)
        jaw_before=rig.pose.bones["MCH-JawOpennessMeasurer"].matrix.copy()
        corner_before={s:(rig.matrix_world@rig.pose.bones["OuterLip_Corner."+s].head).copy() for s in ("L","R")}
        brow_before={b.name:(rig.matrix_world@b.head).copy() for b in brows}
        head=bpy.data.objects["GEO-snow-head"]
        hair=bpy.data.objects["GEO-snow-hair_base"]
        head_before=proof.evaluated_snapshot(bpy,[head])
        crop_snapshot=proof.evaluated_snapshot(bpy,[head,hair])
        points=[co for data in crop_snapshot.values() for co in data["coords"]]
        bounds={"min":[min(co[i] for co in points) for i in range(3)],"max":[max(co[i] for co in points) for i in range(3)]}
        span=max(bounds["max"][2]-bounds["min"][2],bounds["max"][0]-bounds["min"][0])
        if not math.isfinite(span) or span<=0:
            raise ValueError("head_crop_bounds_invalid")
        center=[(bounds["min"][i]+bounds["max"][i])/2 for i in range(3)]
        camera_config={"input_neutral_bounds":bounds,"target":center,"scale":span*1.35,"distance":max(1.0,span*5),
            "resolution":[640,640],"angles":[0,35],"scope":"NEW fixed head crop from input state, not old neutral render"}
        audit["camera_config"]=camera_config
        audit["intentional_changes"]=[{"bone":r["act"]["name"],"channel":"location.y",
            "before":r["current_local_y"],"after":r["candidate_local_y"],
            "delta":r["candidate_delta_local_y"],"rule":"min(.006,.2*actual remaining positive headroom)"} for r in inspection]+[
            {"bone":b.name,"channel":"location.y","before":float(b.location.y),
             "after":float(b.location.y)+BROW_DELTA,"delta":BROW_DELTA} for b in brows]
        write_audit(path,audit)
        for r,bone in zip(inspection,targets):
            bone.location.y=r["candidate_local_y"]
        for brow in brows:
            brow.location.y+=BROW_DELTA
        bpy.context.view_layer.update()
        response=[]
        for r,bone in zip(inspection,targets):
            side=r["side"]
            key=r["property"]
            action=rig.pose.bones["OuterLip_Corner."+side].constraints["Action "+key]
            corner=rig.matrix_world@rig.pose.bones["OuterLip_Corner."+side].head
            up=float(bone[key])
            delta=corner-corner_before[side]
            item={"side":side,"up_before":r["up_value_before"],"up_after":up,
                "up_increase":up-r["up_value_before"],"corner_before":list(corner_before[side]),
                "corner_after":list(corner),"corner_delta_world":list(delta),
                "action_eval_time_after":float(action.eval_time),"eval_time_sum_residual":abs(float(action.eval_time)-up),
                "actual_local_y":float(bone.location.y),"requested_local_y":r["candidate_local_y"]}
            low,high=r["action_eval_time_hard_range"]["min"],r["action_eval_time_hard_range"]["max"]
            item["positive_response_passed"]=(all(math.isfinite(v) for v in (up,*delta,float(action.eval_time)))
                and item["up_increase"]>1e-7 and delta.z>1e-6 and low<=up<=high
                and item["eval_time_sum_residual"]<1e-5 and abs(item["actual_local_y"]-item["requested_local_y"])<1e-7)
            response.append(item)
        audit["native_lip_response"]=response
        audit["lip_corner_symmetry"]={"world_z_rise_difference":abs(response[0]["corner_delta_world"][2]-response[1]["corner_delta_world"][2]),
            "up_increase_difference":abs(response[0]["up_increase"]-response[1]["up_increase"]),
            "not_an_art_symmetry_acceptance":True}
        audit["actual_brow_response"]=[{"bone":b.name,"world_delta":list(rig.matrix_world@b.head-brow_before[b.name])} for b in brows]
        audit["direct_controls_after"]={b.name:proof.control_record(rig,b) for b in targets+brows}
        audit["driver_after_pose"]=soft.driver_summary(helper,bpy)
        audit["native_key_values_after_pose"]=proof.key_values(bpy)
        write_audit(path,audit)
        if not all(r["positive_response_passed"] for r in response):
            raise ValueError("native_lips_up_or_actual_corner_rise_not_established")
        if any(r["world_delta"][2]<=0 for r in audit["actual_brow_response"]):
            raise ValueError("actual_brow_world_up_response_not_established")
        if proof.matrix_error(jaw_before,rig.pose.bones["MCH-JawOpennessMeasurer"].matrix)>1e-6:
            raise ValueError("jaw_mapping_target_changed")
        for bone in targets+brows:
            old=control_before[bone.name]
            now=proof.channels(bone)
            if any(now[field]!=old[field] for field in now if field!="location") or any(now["location"][i]!=old["location"][i] for i in (0,2)):
                raise ValueError("unintended_direct_control_channel_change")
            for i,locked in enumerate(old["lock_location"]):
                if locked and now["location"][i]!=old["location"][i]:
                    raise ValueError("locked_face_location_channel_changed")
        if {n:proof.channels(rig.pose.bones[n]) for n in held_names}!=held_before:
            raise ValueError("held_mouth_eyes_or_arm_controls_changed")
        if constraint_config_hash(proof,rig,inspected_names)!=configs_before:
            raise ValueError("native_face_constraint_configuration_changed")
        audit["pose_preservation_passed"]=(proof.raw_preservation(bpy,helper,soft)==raw_before
            and proof.material_graph_hash(bpy,pair)==graphs_before and proof.rest_rig_hash(rig)==rig_before
            and proof.properties(rig.pose.bones["Properties"])==props_before
            and audit["driver_after_pose"]["active_invalid"]==0)
        if not audit["pose_preservation_passed"]:
            raise ValueError("friendly_face_raw_material_rig_or_driver_preservation_failed")
        head_after=proof.evaluated_snapshot(bpy,[head])
        audit["head_evaluated_before"]=proof.evaluated_report(head_before)
        audit["head_evaluated_after"]=proof.evaluated_report(head_after)
        audit["head_deformation"]=proof.deformation(head_before,head_after)
        deformation=audit["head_deformation"][head.name]
        if not deformation["evaluated_topology_comparable"] or deformation["changed_vertices"]==0 or deformation["maximum_world_displacement"]<=1e-6:
            raise ValueError("actual_evaluated_head_deformation_unproven")
        audit["numeric_face_gates_passed"]=True
        if not recheck():
            raise ValueError("friendly_face_inputs_changed_before_render")
        write_audit(path,audit)
        scene.cycles.seed=SEED
        scene.cycles.use_animated_seed=False
        for name,angle in (("front",0),("threequarter",35)):
            shot={"name":name,"angle":angle,"target":center,"scale":camera_config["scale"],"distance":camera_config["distance"]}
            target=Vector(center)
            a=math.radians(angle)
            scene.camera.location=target+Vector((math.sin(a)*shot["distance"],-math.cos(a)*shot["distance"],0.01))
            scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat("-Z","Y").to_euler()
            scene.camera.data.ortho_scale=shot["scale"]
            scene.render.resolution_x=scene.render.resolution_y=640
            scene.render.resolution_percentage=100
            bpy.context.view_layer.update()
            before=pair.control_snapshot(bpy,scene,objects,materials,None,None)
            render_face(bpy,out,scene,shot,audit,args.emit_preview)
            after=pair.control_snapshot(bpy,scene,objects,materials,None,None)
            if before["sha256"]!=after["sha256"]:
                raise ValueError("friendly_face_controls_changed_during_render")
            audit.setdefault("render_controls",[]).append({"view":name,"before":before["sha256"],"after":after["sha256"],
                "match":True,"seed":SEED,"use_animated_seed":False,"pose":"friendly-face-candidate"})
        audit["driver_after_render"]=soft.driver_summary(helper,bpy)
        audit["native_key_values_after_render"]=proof.key_values(bpy)
        audit["preservation_passed"]=(proof.raw_preservation(bpy,helper,soft)==raw_before
            and proof.material_graph_hash(bpy,pair)==graphs_before and proof.rest_rig_hash(rig)==rig_before
            and proof.properties(rig.pose.bones["Properties"])==props_before
            and constraint_config_hash(proof,rig,inspected_names)==configs_before
            and {n:proof.channels(rig.pose.bones[n]) for n in held_names}==held_before)
        if len(audit["renders"])!=2 or not audit["preservation_passed"] or audit["driver_after_render"]["active_invalid"]!=0 or not recheck():
            raise ValueError("friendly_face_final_guard_failed")
        write_audit(path,audit)
        output=out/"snow-friendly-face-prototype.blend"
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
            marker={"candidate_completed":audit.get("candidate_completed",False),"failure":audit.get("failure"),
                "mapping_supported":audit.get("mapping_supported",False),
                "mapping_reasons":[{"side":r["side"],"reasons":r["mapping_reasons"]} for r in audit.get("lip_mapping_inspection",[])],
                "numeric_face_gates_passed":audit.get("numeric_face_gates_passed",False),
                "native_lip_response":audit.get("native_lip_response"),"actual_brow_response":audit.get("actual_brow_response"),
                "symmetry":audit.get("lip_corner_symmetry"),"intentional_changes":audit.get("intentional_changes"),
                "renders":len(audit["renders"]),"views":[r["view"] for r in audit["renders"]],
                "pose":"friendly-face-candidate","models_saved":audit["models_saved"],
                "derivative_saved":audit["derivative_saved"],"derivative":audit.get("derivative"),
                "neutral_renders":0,"solver_runs":0,"source_and_input_unchanged":audit.get("source_and_input_unchanged"),
                "texture_hash_recheck":audit.get("texture_hash_recheck"),"native_policy":audit.get("native_policy"),
                "driver_before":audit.get("driver_before"),
                "driver_after":audit.get("driver_after_render",audit.get("driver_after_pose")),
                "preservation_passed":audit.get("preservation_passed",False),
                "head_deformation":audit.get("head_deformation"),"render_controls":audit.get("render_controls",[]),
                "friendly_art_approved":False,"garment_art_approved":False,"production_glb_approved":False,
                "animation_approved":False,"corrective_system_approved":False,
                "raw_to_evaluated_mapping":"unproven; matched viewport topology only",
                "external_texture_paths_portable":False}
            if len(encoded(marker))>24000:
                raise ValueError("friendly_face_stdout_byte_budget_exceeded")
            print("SNOW_FRIENDLY_FACE_CANDIDATE "+encoded(marker).decode().strip(),flush=True)
            if failure is None and not readonly:
                raise ValueError("friendly_face_final_readonly_check_failed")
        except Exception as cleanup_error:
            if failure is None:
                raise
            print("SNOW_FRIENDLY_FACE_CLEANUP_FAILED "+json.dumps({"error_type":type(cleanup_error).__name__[:80]}),flush=True)

if __name__=="__main__":
    main()
