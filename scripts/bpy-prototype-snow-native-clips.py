"""Three bounded native Action candidates: idle, wave and celebrate.
Native control authoring, Fcurve playback and saved-file readback; no export or art acceptance.
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

NATURAL_BLOB="4628a9f9962e35c3eac9754c019b31ab4c6bcc5c"
ROTATION_TOL_DEGREES=0.05
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
    if len(raw)>2097152:
        raise ValueError("native_clips_audit_byte_budget_exceeded")
    path.write_bytes(raw)

def load_reviewed():
    path=Path(__file__).with_name("bpy-proof-snow-natural-wrists.py")
    if git_blob(path.read_bytes())!=NATURAL_BLOB:
        raise ValueError("reviewed_native_clip_natural_functions_hash_mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_snow_natural_functions",path)
    natural=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(natural)
    return (natural,*natural.load_reviewed())

FRAMES=tuple(range(49))
FPS=24
CLIPS=("idle","wave","celebrate")
PROOF_FRAMES={"idle":(12,36),"wave":(12,24),"celebrate":(12,24)}
GEOMETRY_FRAMES=(0,12,24,36,48)
ACTION_PREFIX="COOP_SNOW_NATIVE_"

def assign_action(rig,action,slot):
    ad=rig.animation_data_create()
    if len(ad.nla_tracks)!=0:
        raise ValueError("native_clip_nla_not_empty")
    ad.action=action
    ad.action_slot=slot
    if ad.action!=action or ad.action_slot!=slot:
        raise ValueError("native_clip_action_slot_assignment_failed")

def selected_bag(action,slot):
    if len(action.slots)!=1 or len(action.layers)!=1 or len(action.layers[0].strips)!=1:
        raise ValueError("native_clip_action_layout_mismatch")
    strip=action.layers[0].strips[0]
    if strip.type!="KEYFRAME":
        raise ValueError("native_clip_strip_type_mismatch")
    bag=strip.channelbag(slot,ensure=False)
    if bag is None or len(strip.channelbags)!=1:
        raise ValueError("native_clip_selected_channelbag_missing")
    return bag

def curve_descriptor(action,slot,expected_paths,complete):
    bag=selected_bag(action,slot)
    actual={(f.data_path,f.array_index) for f in bag.fcurves}
    if actual!={tuple(path) for path in expected_paths} or len(bag.fcurves)!=len(expected_paths):
        raise ValueError("native_clip_selected_slot_curve_paths_mismatch")
    records=[]
    for f in sorted(bag.fcurves,key=lambda f:(f.data_path,f.array_index)):
        points=[{"frame":float(p.co[0]),"value":float(p.co[1]),"interpolation":p.interpolation} for p in f.keyframe_points]
        if not all(math.isfinite(p["frame"]) and math.isfinite(p["value"]) for p in points):
            raise ValueError("native_clip_curve_contains_nonfinite_point")
        if complete and ([p["frame"] for p in points]!=list(FRAMES) or any(p["interpolation"]!="LINEAR" for p in points)):
            raise ValueError("native_clip_curve_frame_or_linear_guard_failed")
        records.append({"path":f.data_path,"index":f.array_index,"points":points})
    return {"action":action.name,"slot_identifier":slot.identifier,"slot_handle":int(slot.handle),
        "slot_count":len(action.slots),"layer_count":len(action.layers),"strip_count":len(action.layers[0].strips),
        "selected_bag_curve_count":len(records),"curve_sha256":hashlib.sha256(encoded(records)).hexdigest(),
        "all_linear":all(p["interpolation"]=="LINEAR" for r in records for p in r["points"]),
        "keyframe_count":sum(len(r["points"]) for r in records),"fake_user":bool(action.use_fake_user)}

def original_actions_hash(bpy,names):
    records=[]
    for name in sorted(names):
        action=bpy.data.actions.get(name)
        if action is None:
            raise ValueError("original_action_library_missing")
        layers=[]
        for layer in action.layers:
            strips=[]
            for strip in layer.strips:
                bags=[]
                if strip.type=="KEYFRAME":
                    for slot in action.slots:
                        bag=strip.channelbag(slot,ensure=False)
                        if bag is not None:
                            curves=[]
                            for f in bag.fcurves:
                                points=[(list(p.co),list(p.handle_left),list(p.handle_right),p.interpolation,p.easing) for p in f.keyframe_points]
                                curves.append((f.data_path,f.array_index,f.extrapolation,points))
                            bags.append((slot.identifier,curves))
                strips.append((strip.type,bags))
            layers.append((layer.name,strips))
        records.append({"name":name,"fake_user":bool(action.use_fake_user),
            "slots":[(s.identifier,int(s.handle)) for s in action.slots],"layers":layers})
    return hashlib.sha256(encoded(records)).hexdigest()

def reset_controls(proof,rig,baseline):
    for name,state in baseline.items():
        bone=rig.pose.bones[name]
        if bone.rotation_mode!=state["rotation_mode"]:
            raise ValueError("native_clip_control_mode_changed")
        now=proof.channels(bone)
        for key in ("lock_location","lock_scale","lock_rotation","lock_rotation_w","lock_rotations_4d"):
            if now[key]!=state[key]:
                raise ValueError("native_clip_control_locks_changed")
        for field,locks in (("location",bone.lock_location),("scale",bone.lock_scale)):
            target=getattr(bone,field)
            for i,locked in enumerate(locks):
                if locked and abs(float(target[i])-state[field][i])>1e-6:
                    raise ValueError("native_clip_locked_channel_drift")
                if not locked:
                    target[i]=state[field][i]
        field="rotation_quaternion" if bone.rotation_mode=="QUATERNION" else "rotation_euler"
        target=getattr(bone,field)
        if field=="rotation_quaternion":
            if bone.lock_rotations_4d:
                locks=[bone.lock_rotation_w,*bone.lock_rotation]
            elif any(bone.lock_rotation):
                if any(abs(float(target[i])-state[field][i])>1e-6 for i in range(4)):
                    raise ValueError("native_clip_locked_quaternion_drift")
                continue
            else:
                locks=[False]*4
        else:
            locks=bone.lock_rotation
        for i,locked in enumerate(locks):
            if locked and abs(float(target[i])-state[field][i])>1e-6:
                raise ValueError("native_clip_locked_rotation_drift")
            if not locked:
                target[i]=state[field][i]

def clip_profile(clip,frame,side):
    t=frame/48
    envelope=math.sin(math.pi*t)**2
    sway=2*math.sin(2*math.pi*t)
    sign=1 if side=="L" else -1
    angle=sign*(75+sway)
    reach=0.95
    if clip=="wave" and side=="L":
        angle=(1-envelope)*(75+sway)+envelope*(-60+8*math.sin(4*math.pi*t))
        reach=0.95-0.20*envelope
    elif clip=="celebrate":
        angle=sign*((1-envelope)*(75+sway)+envelope*(-60+3*math.sin(4*math.pi*t)))
    return angle,reach

def arm_baselines(natural,proof,rig):
    result={}
    for side in ("L","R"):
        u,e,w=[natural.world_head(rig,n+"."+side) for n in ("UpperArm","Forearm","Wrist")]
        wrist=rig.matrix_world@rig.pose.bones["IK-Wrist."+side].matrix
        pole=rig.matrix_world@rig.pose.bones["POLE-UpperArm."+side].matrix
        if (w-wrist.translation).length>TOL:
            raise ValueError("native_clip_baseline_target_mapping_unproven")
        result[side]={"pivot":u.copy(),"chain_before":w.copy(),"first":(e-u).length,
            "second":(w-e).length,"reach":(wrist.translation-u).length,
            "wrist_before":wrist.copy(),"pole_before":pole.copy()}
    return result

def restore_clip_relative_wrist_once(bpy,natural,proof,soft,helper,rig,states,baseline,bent,audit,path):
    """Reviewed 4628 orientation phase; only static >0.1m motion predicate is omitted.
    Clips cross the neutral position; whole-clip actual joint/mesh motion is guarded separately.
    All position, offset, rotation, scale, segment, angle, pole and driver gates are unchanged.
    """
    from mathutils import Matrix,Quaternion,Vector
    plans=[]
    desired={}
    records=[]
    audit["wrist_rotation_policy"]={"orientation_phases_requested":1,"orientation_phases_applied":0,
        "rotation_tolerance_degrees":ROTATION_TOL_DEGREES,"position_tolerance_m":TOL,
        "formula":"Qactual_goal=Qforearm_bent*Qrelative_baseline; Qcontrol_goal=Qactual_goal*inverse(Qoffset_bent)",
        "offset_scope":"measured control-to-actual Wrist correspondence, not an anatomical limit",
        "iterations_sweeps_or_fallback":False}
    for side in ("L","R"):
        before,posed=baseline[side],bent[side]
        offset0=Quaternion(before["control_to_actual_wrist_offset_quaternion"])
        offset1=Quaternion(posed["control_to_actual_wrist_offset_quaternion"])
        residual=natural.quaternion_angle(offset0,offset1)
        record={"side":side,"offset_baseline":list(offset0),"offset_bent":list(offset1),
            "offset_correspondence_error_degrees":residual,
            "offset_correspondence_tolerance_degrees":ROTATION_TOL_DEGREES,
            "offset_correspondence_passed":residual<=ROTATION_TOL_DEGREES}
        records.append(record)
        audit["wrist_rotation_plans"]=records
        natural.write_audit(path,audit)
        if not record["offset_correspondence_passed"]:
            raise ValueError("control_actual_wrist_offset_correspondence_unproven")
        forearm=Quaternion(posed["quaternions"]["forearm"])
        relative0=Quaternion(before["relative_wrist_forearm_quaternion"])
        actual_goal=(forearm@relative0).normalized()
        control_goal=(actual_goal@offset1.inverted()).normalized()
        control=rig.pose.bones["IK-Wrist."+side]
        current=rig.matrix_world@control.matrix
        location,rotation,scale=current.decompose()
        if proof.matrix_error(current,Matrix.LocRotScale(location,rotation,scale))>1e-6 or min(scale)<=0:
            raise ValueError("natural_wrist_control_world_shear_or_scale_unsupported")
        goal=Matrix.LocRotScale(location,control_goal,scale)
        plan=proof.make_channel_plan(rig,control,goal)
        plans.append(plan)
        desired[side]={"actual_quaternion":actual_goal,"control_quaternion":control_goal,
            "world_goal":goal,"location":location.copy(),"scale":scale.copy()}
        record.update({"relative_baseline_quaternion":list(relative0),
            "actual_wrist_goal_quaternion":list(actual_goal),"control_goal_quaternion":list(control_goal),
            "world_control_goal":proof.matrix(goal),"before_channels":plan["before"],
            "location_target":plan["location"],"rotation_target":plan["rotation"],"scale_target":plan["scale"],
            "basis_target":plan["basis_target"],"world_position_and_scale_held":True})
        natural.write_audit(path,audit)
    for plan in plans:
        proof.apply_channel_plan(plan)
    audit["wrist_rotation_policy"]["orientation_phases_applied"]=1
    bpy.context.view_layer.update()
    audit["orientation_locked_channels_after"]={plan["bone"].name:proof.verify_locked(plan) for plan in plans}
    final=natural.wrist_rotation_state(proof,rig)
    audit["wrist_rotation_after"]=final
    results=[]
    for state in states:
        side=state["side"]
        initial,posed,actual=baseline[side],bent[side],final[side]
        u,e,w=[natural.world_head(rig,name+"."+side) for name in ("UpperArm","Forearm","Wrist")]
        control=rig.matrix_world@rig.pose.bones["IK-Wrist."+side].matrix
        pole=rig.matrix_world@rig.pose.bones["POLE-UpperArm."+side].matrix
        actual_q=Quaternion(actual["quaternions"]["wrist"])
        relative_q=Quaternion(actual["relative_wrist_forearm_quaternion"])
        offset_q=Quaternion(actual["control_to_actual_wrist_offset_quaternion"])
        actual_scale=control.to_scale()
        first,second=(e-u).length,(w-e).length
        angle=natural.elbow_angle(u,e,w)
        movement={name:(Vector(actual["heads_world"][name])-Vector(posed["heads_world"][name])).length
            for name in ("UpperArm","Forearm","Wrist")}
        record={"side":side,"upperarm_head_world":list(u),"elbow_head_world":list(e),"wrist_head_world":list(w),
            "target_head_world":list(control.translation),"first_segment_length":first,"second_segment_length":second,
            "first_segment_length_change":abs(first-state["first"]),"second_segment_length_change":abs(second-state["second"]),
            "elbow_internal_angle_degrees":angle,"straight_angle_convention":180,
            "chain_head_motion":(w-state["chain_before"]).length,
            "chain_target_residual":(w-control.translation).length,"pivot_drift":(u-state["pivot"]).length,
            "target_reach_error":abs((control.translation-u).length-state["goal_reach"]),
            "actual_chain_reach_error":abs((w-u).length-state["goal_reach"]),
            "joint_position_change_from_bent_world":movement,
            "control_position_change_from_bent_world":(control.translation-Vector(tuple(posed["matrices"]["control"][i][3] for i in range(3)))).length,
            "control_goal_matrix_residual":proof.matrix_error(control,desired[side]["world_goal"]),
            "control_scale_change_from_bent":max(abs(actual_scale[i]-desired[side]["scale"][i]) for i in range(3)),
            "pole_matrix_change_from_bent":proof.matrix_error(pole,Matrix(posed["pole_matrix"])),
            "pole_position_residual":(pole.translation-state["pole_goal"].translation).length,
            "relative_rotation_error_from_baseline_degrees":natural.quaternion_angle(relative_q,Quaternion(initial["relative_wrist_forearm_quaternion"])),
            "actual_wrist_goal_rotation_error_degrees":natural.quaternion_angle(actual_q,desired[side]["actual_quaternion"]),
            "control_goal_rotation_error_degrees":natural.quaternion_angle(control.to_quaternion(),desired[side]["control_quaternion"]),
            "offset_after_error_from_bent_degrees":natural.quaternion_angle(offset_q,Quaternion(posed["control_to_actual_wrist_offset_quaternion"])),
            "rotation_scope":"coordinate-relative restoration only; no anatomical or hand-art acceptance"}
        record["numeric_passed"]=(20<angle<160
            and all(value<=TOL for value in movement.values())
            and all(record[key]<=TOL for key in ("first_segment_length_change","second_segment_length_change",
                "chain_target_residual","pivot_drift","target_reach_error","actual_chain_reach_error",
                "control_position_change_from_bent_world","control_goal_matrix_residual","pole_matrix_change_from_bent","pole_position_residual"))
            and record["control_scale_change_from_bent"]<=1e-6
            and all(record[key]<=ROTATION_TOL_DEGREES for key in ("relative_rotation_error_from_baseline_degrees",
                "actual_wrist_goal_rotation_error_degrees","control_goal_rotation_error_degrees","offset_after_error_from_bent_degrees")))
        results.append(record)
    audit["actual_chain_results"]=results
    audit["driver_after_orientation"]=soft.driver_summary(helper,bpy)
    natural.write_audit(path,audit)
    if not all(record["numeric_passed"] for record in results):
        raise ValueError("natural_wrist_rotation_or_position_coupling_gate_failed")
    if audit["driver_after_orientation"]["active_invalid"]!=0:
        raise ValueError("native_driver_invalid_after_wrist_orientation")
    audit["numeric_orientation_gates_passed"]=True
    return results


def author_profile_frame(bpy,natural,proof,soft,helper,rig,baseline,baseline_channels,baseline_rotations,clip,frame,out):
    from mathutils import Matrix
    reset_controls(proof,rig,baseline_channels)
    bpy.context.view_layer.update()
    plans=[]
    states=[]
    profile=[]
    for side in ("L","R"):
        state=dict(baseline[side])
        angle,fraction=clip_profile(clip,frame,side)
        pivot=state["pivot"]
        goal_reach=state["reach"]*fraction
        margin=max(1e-5,(state["first"]+state["second"])*1e-4)
        if not abs(state["first"]-state["second"])+margin<goal_reach<state["first"]+state["second"]-margin:
            raise ValueError("native_clip_profile_outside_strict_arm_annulus")
        rotation=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(angle),4,"Y")@Matrix.Translation(-pivot)
        wrist_goal=rotation@state["wrist_before"]
        wrist_goal.translation=pivot+fraction*(wrist_goal.translation-pivot)
        pole_goal=state["pole_before"].copy()
        pole_goal.translation=rotation@state["pole_before"].translation
        arm,pole=wrist_goal.translation-pivot,pole_goal.translation-pivot
        sine=arm.cross(pole).length/(arm.length*pole.length) if arm.length*pole.length>0 else 0
        if not math.isfinite(sine) or sine<1e-3:
            raise ValueError("native_clip_profile_pole_plane_degenerate")
        state.update({"side":side,"goal_reach":goal_reach,"wrist_goal":wrist_goal,"pole_goal":pole_goal})
        states.append(state)
        profile.append({"side":side,"world_y_degrees":angle,"reach_fraction":fraction,
            "target_reach":goal_reach,"pole_plane_sine":sine})
        for name,goal in (("IK-Wrist."+side,wrist_goal),("POLE-UpperArm."+side,pole_goal)):
            plans.append(proof.make_channel_plan(rig,rig.pose.bones[name],goal))
    for plan in plans:
        proof.apply_channel_plan(plan)
    bpy.context.view_layer.update()
    for plan in plans:
        proof.verify_locked(plan)
    local={"clip":clip,"frame":frame,"profile":profile,"renders":[]}
    bent=natural.wrist_rotation_state(proof,rig)
    results=restore_clip_relative_wrist_once(bpy,natural,proof,soft,helper,rig,states,
        baseline_rotations,bent,local,out/"orientation-latest.json")
    return {"profile":profile,"orientation_phases":local["wrist_rotation_policy"]["orientation_phases_applied"],
        "orientation_results":[{k:r[k] for k in ("side","numeric_passed","elbow_internal_angle_degrees",
            "chain_target_residual","pivot_drift","relative_rotation_error_from_baseline_degrees",
            "first_segment_length_change","second_segment_length_change")} for r in results]}

def channel_paths(proof,rig):
    result=[]
    for name in proof.ARMS:
        bone=rig.pose.bones[name]
        rotation="rotation_quaternion" if bone.rotation_mode=="QUATERNION" else "rotation_euler"
        for field,count in (("location",3),(rotation,4 if rotation=="rotation_quaternion" else 3),("scale",3)):
            path=bone.path_from_id(field)
            values=rig.path_resolve(path)
            if len(values)!=count:
                raise ValueError("native_clip_nested_rna_path_length_mismatch")
            result.extend((path,i) for i in range(count))
    return result

def key_controls(rig,action,slot,proof,frame):
    if rig.animation_data.action!=action or rig.animation_data.action_slot!=slot:
        raise ValueError("native_clip_wrong_action_before_key_insert")
    for name in proof.ARMS:
        bone=rig.pose.bones[name]
        rotation="rotation_quaternion" if bone.rotation_mode=="QUATERNION" else "rotation_euler"
        for field in ("location",rotation,"scale"):
            if rig.animation_data.action!=action or rig.animation_data.action_slot!=slot:
                raise ValueError("native_clip_action_changed_during_insert")
            if rig.keyframe_insert(data_path=bone.path_from_id(field),index=-1,frame=frame,group=name) is not True:
                raise ValueError("native_clip_nested_keyframe_insert_failed")

def channel_difference(actual,expected):
    worst=0.0
    for name,state in expected.items():
        now=actual[name]
        for key in ("rotation_mode","lock_location","lock_rotation","lock_scale","lock_rotation_w","lock_rotations_4d"):
            if now[key]!=state[key]:
                raise ValueError("native_clip_playback_mode_or_locks_mismatch")
        rotation="rotation_quaternion" if state["rotation_mode"]=="QUATERNION" else "rotation_euler"
        for field in ("location",rotation,"scale"):
            worst=max(worst,max(abs(float(a)-float(b)) for a,b in zip(now[field],state[field])))
    return worst

def joint_snapshot(natural,rig,evaluated=False,bpy=None):
    sample=rig.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluated else rig
    return {side:{name:list(sample.matrix_world@sample.pose.bones[name+"."+side].head)
        for name in ("UpperArm","Forearm","Wrist")} for side in ("L","R")}

def max_joint_difference(a,b):
    return max(math.sqrt(sum((x-y)**2 for x,y in zip(a[s][n],b[s][n])))
        for s in ("L","R") for n in ("UpperArm","Forearm","Wrist"))

def geometry_sample(proof,bpy,objects):
    snapshot=proof.evaluated_snapshot(bpy,objects)
    records={}
    for name,item in snapshot.items():
        coords=item["coords"]
        if not coords:
            raise ValueError("native_clip_empty_evaluated_mesh")
        indices=sorted(set(round(i*(len(coords)-1)/63) for i in range(64)))
        records[name]={"topology":item["topology_sha256"],"count":len(coords),
            "samples":[{"index":i,"co":list(coords[i])} for i in indices]}
    return snapshot,records

def geometry_difference(actual,expected):
    worst=0.0
    for name,reference in expected.items():
        current=actual[name]
        if current["topology"]!=reference["topology"] or current["count"]!=reference["count"]:
            raise ValueError("native_clip_evaluated_topology_changed")
        if [r["index"] for r in current["samples"]]!=[r["index"] for r in reference["samples"]]:
            raise ValueError("native_clip_geometry_sample_indices_changed")
        for a,b in zip(current["samples"],reference["samples"]):
            worst=max(worst,math.sqrt(sum((x-y)**2 for x,y in zip(a["co"],b["co"]))))
    return worst

def held_face_state(proof,rig):
    names=("ACT-Lips_Corner.L","ACT-Lips_Corner.R","MSTR-Eyebrow.L","MSTR-Eyebrow.R","MSTR-Mouth","TGT-Eyes")
    return {"channels":{n:proof.channels(rig.pose.bones[n]) for n in names},
        "properties":{s:{k:float(rig.pose.bones["ACT-Lips_Corner."+s]["RIG-snow-Lips"+k+"."+s])
            for k in ("Up","Wide")} for s in ("L","R")},
        "jaw_matrix":proof.matrix(rig.pose.bones["MCH-JawOpennessMeasurer"].matrix)}

def validate_frame(bpy,natural,face,proof,soft,helper,rig,baseline,relative0,held,properties,clip,frame):
    from mathutils import Quaternion,Vector,Matrix
    face_now=held_face_state(proof,rig)
    if face_now["channels"]!=held["channels"]:
        raise ValueError("native_clip_held_face_channels_changed")
    face_drift=max(abs(face_now["properties"][s][k]-held["properties"][s][k]) for s in ("L","R") for k in ("Up","Wide"))
    if not math.isfinite(face_drift) or face_drift>1e-4 or proof.matrix_error(Matrix(face_now["jaw_matrix"]),Matrix(held["jaw_matrix"]))>1e-6:
        raise ValueError("native_clip_held_face_or_jaw_changed")
    if proof.properties(rig.pose.bones["Properties"])!=properties:
        raise ValueError("native_clip_ik_properties_changed")
    rotations=natural.wrist_rotation_state(proof,rig)
    chains=[]
    for side in ("L","R"):
        b=baseline[side]
        u,e,w=[natural.world_head(rig,n+"."+side) for n in ("UpperArm","Forearm","Wrist")]
        control=rig.matrix_world@rig.pose.bones["IK-Wrist."+side].matrix
        pole=rig.matrix_world@rig.pose.bones["POLE-UpperArm."+side].matrix
        c=rig.pose.bones["IK-M-Forearm."+side].constraints.get("Ik")
        if (c is None or c.type!="IK" or c.mute or c.influence<=0 or c.use_rotation is not False
                or c.chain_count!=2 or c.target!=rig or c.subtarget!="IK-M-Wrist."+side
                or c.pole_target!=rig or c.pole_subtarget!="POLE-UpperArm."+side):
            raise ValueError("native_clip_native_ik_configuration_changed")
        angle,fraction=clip_profile(clip,frame,side)
        reach=b["reach"]*fraction
        first,second=(e-u).length,(w-e).length
        margin=max(1e-5,(b["first"]+b["second"])*1e-4)
        arm_vector,pole_vector=control.translation-u,pole.translation-u
        denominator=arm_vector.length*pole_vector.length
        pole_sine=arm_vector.cross(pole_vector).length/denominator if denominator>0 else 0
        elbow=natural.elbow_angle(u,e,w)
        rel_error=natural.quaternion_angle(Quaternion(rotations[side]["relative_wrist_forearm_quaternion"]),
            Quaternion(relative0[side]["relative_wrist_forearm_quaternion"]))
        row={"side":side,"elbow_degrees":elbow,"chain_residual":(w-control.translation).length,
            "pivot_drift":(u-b["pivot"]).length,"first_length_change":abs(first-b["first"]),
            "second_length_change":abs(second-b["second"]),"reach_error":abs((w-u).length-reach),
            "target_reach_error":abs((control.translation-u).length-reach),
            "relative_wrist_degrees":rel_error,"pole_sine":pole_sine}
        chains.append(row)
        if (not abs(b["first"]-b["second"])+margin<reach<b["first"]+b["second"]-margin
                or not 20<elbow<160 or pole_sine<1e-3 or rel_error>natural.ROTATION_TOL_DEGREES
                or any(row[k]>TOL for k in ("chain_residual","pivot_drift","first_length_change",
                    "second_length_change","reach_error","target_reach_error"))):
            raise ValueError("native_clip_frame_chain_or_wrist_guard_failed")
    drivers=soft.driver_summary(helper,bpy)
    if drivers["active_invalid"]!=0:
        raise ValueError("native_clip_frame_has_invalid_driver")
    values=proof.key_values(bpy)
    finger_records=natural.fingers(proof,rig)
    if len(finger_records)!=10:
        raise ValueError("native_clip_finger_endpoint_count_mismatch")
    controls={n:proof.channels(rig.pose.bones[n]) for n in proof.ARMS}
    if not all(math.isfinite(v) for state in controls.values() for key in ("location","rotation_euler","rotation_quaternion","scale") for v in state[key]):
        raise ValueError("native_clip_control_channel_nonfinite")
    return {"frame":frame,"chains":chains,"driver_invalid":drivers["active_invalid"],
        "key_count":len(values),"face_max_property_drift":face_drift,"finger_endpoints_finite":True},controls

def invariants(bpy,natural,face,proof,soft,pair,helper,rig,source_names):
    names=[b.name for b in rig.pose.bones]
    return {"raw":proof.raw_preservation(bpy,helper,soft),"materials":proof.material_graph_hash(bpy,pair),
        "rest_rig":proof.rest_rig_hash(rig),"source_actions":original_actions_hash(bpy,source_names),
        "native_constraints":natural.configuration_hash(proof,natural.native_constraints(face,rig,names))}

def require_invariants(current,baseline):
    if current!=baseline:
        differing=[key for key in baseline if current.get(key)!=baseline[key]]
        raise ValueError("native_clip_preservation_changed_"+("_".join(differing))[:50])

def fixed_shot(points):
    from mathutils import Vector
    if not points or not all(math.isfinite(v) for p in points for v in p):
        raise ValueError("native_clip_camera_union_nonfinite")
    low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    target=(low+high)/2
    location=target+Vector((0,-max(2.0,(high-low).length*3),0.03))
    q=(target-location).to_track_quat("-Z","Y")
    right,up=q@Vector((1,0,0)),q@Vector((0,1,0))
    scale=2*max(max(abs((p-target).dot(up)) for p in points)+0.06,
        (max(abs((p-target).dot(right)) for p in points)+0.06)/(480/600))
    return {"target":list(target),"camera_location":list(location),"rotation_quaternion":list(q),
        "scale":scale,"resolution":[480,600],"preview":[320,400],
        "union_bounds":{"min":list(low),"max":list(high)},"world_margin":0.06,
        "scope":"ONE shared union body bounds camera for all six new clip frames; no per-frame recentering"}

def render_clip(bpy,natural,pair,scene,objects,materials,out,clip,frame,shot,audit,emit):
    natural.configure_shot(bpy,scene,shot)
    scene.cycles.seed=SEED
    scene.cycles.use_animated_seed=False
    before=pair.control_snapshot(bpy,scene,objects,materials,None,None)
    file=out/("snow-native-"+clip+"-frame-"+str(frame).zfill(2)+".png")
    scene.render.filepath=str(file)
    bpy.ops.render.render(write_still=True,scene=scene.name)
    record={"model":"snow","phase":"native-clips-candidate","clip":clip,"frame":frame,"fps":FPS,
        "file":file.name,"bytes":file.stat().st_size,"sha256":sha(file),"resolution":[480,600],
        "pose_source":"NEW Action selected-slot Fcurve playback","old_static_baseline_rerendered":False,
        "camera_shared_across_all_six":True,"seed":SEED}
    audit["renders"].append(record)
    after=pair.control_snapshot(bpy,scene,objects,materials,None,None)
    if before["sha256"]!=after["sha256"]:
        raise ValueError("native_clip_render_controls_changed")
    record["controls_sha256"]=before["sha256"]
    write_audit(out/"native-clips-audit.json",audit)
    print("AVATAR_ACTUAL_RENDER "+encoded(record).decode().strip(),flush=True)
    if emit:
        image=bpy.data.images.load(str(file),check_existing=False)
        image.scale(320,400)
        preview=file.with_name(file.stem+"-preview.jpg")
        image.file_format,image.filepath_raw="JPEG",str(preview)
        image.save()
        while preview.stat().st_size>65536 and image.size[0]>128:
            width=max(128,int(image.size[0]*0.8))
            image.scale(width,round(width*600/480))
            image.save()
        if preview.stat().st_size>65536:
            raise ValueError("native_clip_preview_byte_budget_exceeded")
        dimensions=list(image.size)
        bpy.data.images.remove(image)
        print("AVATAR_ACTUAL_JPEG "+json.dumps({"model":"snow","phase":"native-clips-candidate",
            "clip":clip,"frame":frame,"mime_type":"image/jpeg","dimensions":dimensions,
            "bytes":preview.stat().st_size,"base64":base64.b64encode(preview.read_bytes()).decode("ascii")}),flush=True)

def playback_clip(bpy,natural,face,proof,soft,pair,helper,rig,scene,objects,baseline,relative0,baseline_channels,held,properties,
                  action,slot,expected_paths,expected,clip,audit,out,render_frames=(),shot=None,materials=None,emit=False,render_objects=None):
    assign_action(rig,action,slot)
    reset_controls(proof,rig,baseline_channels)
    descriptor=curve_descriptor(action,slot,expected_paths,True)
    metrics=[]
    geometry_worst=0.0
    for frame in FRAMES:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        record,controls=validate_frame(bpy,natural,face,proof,soft,helper,rig,baseline,relative0,held,properties,clip,frame)
        expected_frame=expected["frames"][frame]
        channel_residual=channel_difference(controls,expected_frame["controls"])
        joints=joint_snapshot(natural,rig)
        joint_residual=max_joint_difference(joints,expected_frame["joints"])
        if channel_residual>1e-5 or joint_residual>TOL:
            raise ValueError("native_clip_fcurve_playback_control_or_joint_mismatch")
        record.update({"control_residual":channel_residual,"joint_residual":joint_residual})
        if frame in GEOMETRY_FRAMES:
            evaluated_joints=joint_snapshot(natural,rig,evaluated=True,bpy=bpy)
            record["original_evaluated_rig_head_residual"]=max_joint_difference(joints,evaluated_joints)
            if record["original_evaluated_rig_head_residual"]>TOL:
                raise ValueError("native_clip_evaluated_rig_head_mapping_mismatch")
            _,samples=geometry_sample(proof,bpy,objects)
            residual=geometry_difference(samples,expected["geometry"][str(frame)])
            geometry_worst=max(geometry_worst,residual)
            if residual>TOL:
                raise ValueError("native_clip_playback_evaluated_mesh_mismatch")
            record["mesh_sample_residual"]=residual
        metrics.append(record)
        audit["active_phase_frame"]={"phase":audit.get("active_phase"),"clip":clip,"frame":frame}
        if frame in render_frames:
            render_clip(bpy,natural,pair,scene,render_objects,materials,out,clip,frame,shot,audit,emit)
    return {"action":descriptor,"frames_checked":len(metrics),"metrics":metrics,
        "mesh_sample_max_residual":geometry_worst,"fcurve_playback_passed":True}

def build_candidate(bpy,natural,face,proof,soft,pair,helper,config,source,blend,producer,frozen,out,audit,args):
    from mathutils import Matrix,Vector
    textures=audit["used_textures"]
    expected_files=0
    bpy.context.preferences.filepaths.use_scripts_auto_execute=False
    bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False)
    policy=helper.disable_animation_and_scripts(bpy)
    audit["native_policy"]={"autoexec":False,"embedded_text_executed":False,
        "native_retained":sum(p["native_drivers_retained"] for p in policy),
        "complex_python_muted":sum(p["complex_python_drivers_muted"] for p in policy)}
    rig=bpy.data.objects.get("RIG-Snow")
    if rig is None or rig.type!="ARMATURE" or rig.mode not in ("OBJECT","POSE") or rig.data.pose_position!="POSE":
        raise ValueError("runtime_native_clip_rig_mode_mismatch")
    audit["rig_mode"]={"object_mode":rig.mode,"context_mode":bpy.context.mode,"pose_position":rig.data.pose_position}
    loc,rot,scale=rig.matrix_world.decompose()
    if (min(scale)<=0 or max(scale)-min(scale)>1e-6 or rig.matrix_world.determinant()<=0
            or proof.matrix_error(rig.matrix_world,Matrix.LocRotScale(loc,rot,scale))>1e-6):
        raise ValueError("unsupported_native_clip_rig_world_scale_or_shear")
    objects=[]
    for name in config["mesh_names"]:
        obj=bpy.data.objects.get(name)
        if obj is None or obj.type!="MESH":
            raise ValueError("frozen_native_clip_character_mesh_missing")
        objects.append(obj)
    scene=bpy.context.scene
    if scene is None or scene.camera is None or scene.camera.data.type!="ORTHO" or scene.render.engine!="CYCLES" or any(o.name not in scene.objects for o in objects):
        raise ValueError("frozen_native_clip_scene_missing")
    audit["linked_missing_modifier_dependencies"]=pair.ensure_saved_dependency_closure(bpy,scene,objects)
    materials=pair.used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
    images=pair.collect_images(materials)
    manifest={r["image"]:r for r in frozen["used_textures"]}
    if len(manifest)!=len(frozen["used_textures"]) or not images:
        raise ValueError("frozen_native_clip_texture_manifest_not_unique")
    used={}
    for image in images:
        if image.name not in manifest:
            raise ValueError("used_image_not_in_native_clip_frozen_manifest")
        reference=manifest[image.name]
        filename=str(image.filepath).replace("\\","/").split("/")[-1]
        if image.source!=reference["source"] or filename!=reference["filename"] or not reference["size_guard_passed"]:
            raise ValueError("used_image_identity_differs_from_native_clip_frozen_manifest")
        used[image.name]=reference
        expected_files+=len(reference["files"])
    audit["texture_expected_image_count"]=len(images)
    audit["texture_expected_file_count"]=expected_files
    pair.relink_and_reload(images,source.parent/"textures",textures,lambda:write_audit(out/"native-clips-audit.json",audit))
    for record in textures:
        if record["files"]!=used[record["image"]]["files"]:
            raise ValueError("used_texture_bytes_differ_from_native_clip_frozen_manifest")
    audit["texture_preparation_complete"]=True
    if not recheck_inputs(source,blend,producer,audit):
        raise ValueError("native_clip_used_texture_verification_failed")
    garment=bpy.data.objects.get("GEO-snow-shirt")
    if (garment not in objects or len(garment.data.vertices)!=1839 or not garment.data.shape_keys
            or len(garment.data.shape_keys.key_blocks)!=10 or not garment.material_slots
            or garment.material_slots[0].link!="OBJECT" or garment.material_slots[0].material is None
            or garment.material_slots[0].material.name!=soft.MATERIAL_NAME or garment.data.materials[0] is not None):
        raise ValueError("frozen_native_clip_shirt_binding_or_geometry_mismatch")
    held_names=["ACT-Lips_Corner.L","ACT-Lips_Corner.R","MSTR-Eyebrow.L","MSTR-Eyebrow.R","MSTR-Mouth","TGT-Eyes"]
    chain_names=[prefix+"."+side for side in ("L","R") for prefix in ("UpperArm","Forearm","Wrist")]
    finger_names=["Finger_"+digit+"3."+side for side in ("L","R") for digit in DIGITS]
    required=[*proof.ARMS,*chain_names,*held_names,*finger_names,"Properties","MCH-JawOpennessMeasurer"]
    missing=[name for name in required if name not in rig.pose.bones]
    audit["missing_required_bones"]=missing
    write_audit(out/"native-clips-audit.json",audit)
    if missing:
        raise ValueError("verified_native_clip_or_finger_control_missing")
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
            "chain_count":getattr(c,"chain_count",None) if c else None,
            "use_rotation":getattr(c,"use_rotation",None) if c else None}
        record["verified"]=(owner is not None and owner.parent is not None
            and owner.parent.name=="IK-M-UpperArm."+side and c is not None
            and c.type=="IK" and not c.mute and c.influence>0
            and c.target==rig and c.subtarget=="IK-M-Wrist."+side
            and c.chain_count==2 and c.use_rotation is False
            and c.pole_target==rig and c.pole_subtarget=="POLE-UpperArm."+side)
        ik_mapping[side]=record
        if owner:
            ik_owners.append(owner.name)
        # Read the known native wrist/stretch indirection too; no pose/config writes.
        for prefix in ("IK-M-Wrist","IK-C-Wrist","IK-STR-UpperArm","IK-M-UpperArm"):
            name=prefix+"."+side
            if name in rig.pose.bones:
                ik_owners.append(name)
    inspected_names=[*proof.ARMS,*chain_names,*ik_owners]
    constraints_before=natural.native_constraints(face,rig,inspected_names)
    audit["native_arm_constraints_before"]=constraints_before
    audit["direct_native_ik_mapping"]=ik_mapping
    bpy.context.view_layer.update()
    audit["controls_before"]=[proof.control_record(rig,rig.pose.bones[n]) for n in proof.ARMS]
    write_audit(out/"native-clips-audit.json",audit)
    if any(item["actual"]!=item["expected"] for item in audit["runtime_parent_guard"].values()):
        raise ValueError("verified_native_clip_parent_mismatch")
    if any(key not in properties_before or properties_before[key]!=value for key,value in expected_properties.items()):
        raise ValueError("verified_native_clip_ik_properties_mismatch")
    if any(not item["verified"] for item in ik_mapping.values()):
        raise ValueError("direct_native_native_clip_ik_mapping_unproven")
    constraint_hash_before=natural.configuration_hash(proof,constraints_before)
    held_before={name:proof.channels(rig.pose.bones[name]) for name in held_names}
    face_properties_before={side:{kind:float(rig.pose.bones["ACT-Lips_Corner."+side]["RIG-snow-Lips"+kind+"."+side])
                                 for kind in ("Up","Wide")} for side in ("L","R")}
    if not all(math.isfinite(v) for values in face_properties_before.values() for v in values.values()):
        raise ValueError("nonfinite_selected_face_property")
    jaw_before=rig.pose.bones["MCH-JawOpennessMeasurer"].matrix.copy()
    audit["held_face_before"]=held_before
    audit["held_face_properties_before"]=face_properties_before
    audit["fingers_before"]=natural.fingers(proof,rig)
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
        raise ValueError("native_driver_invalid_before_native_clip")
    evaluated_before=proof.evaluated_snapshot(bpy,objects)
    audit["evaluated_before"]=proof.evaluated_report(evaluated_before)

    scene.render.fps=FPS
    scene.render.fps_base=1.0
    scene.frame_start,scene.frame_end=0,48
    baseline=arm_baselines(natural,proof,rig)
    baseline_channels={n:proof.channels(rig.pose.bones[n]) for n in proof.ARMS}
    relative0=natural.wrist_rotation_state(proof,rig)
    held=held_face_state(proof,rig)
    source_names=[a.name for a in bpy.data.actions]
    preserved=invariants(bpy,natural,face,proof,soft,pair,helper,rig,source_names)
    audit["preservation_baseline"]=preserved
    audit["baseline_control_channels"]=baseline_channels
    audit["baseline_relative_rotations"]=relative0
    audit["native_constraints_scope"]="all enumerated pose-bone constraint descriptors; native ACTION eval_time excluded"
    geometry_objects=[bpy.data.objects[n] for n in ("GEO-snow-body","GEO-snow-shirt")]
    union_points=[]
    for name,record in evaluated_before.items():
        if name not in ("GEO-snow-body","GEO-snow-shirt"):
            union_points.extend(record["coords"])
    paths=channel_paths(proof,rig)
    expected={"source_action_names":source_names,"preserved":preserved,"baseline_channels":baseline_channels,
        "relative0":relative0,"held":held,"properties":properties_before,"expected_paths":paths,
        "baseline":{s:{"pivot":list(b["pivot"]),"chain_before":list(b["chain_before"]),
            "first":b["first"],"second":b["second"],"reach":b["reach"]} for s,b in baseline.items()},"clips":{}}
    actions={}
    audit["clips"]={}
    audit["active_phase"]="AUTHOR"
    for clip in CLIPS:
        name=ACTION_PREFIX+clip.upper()+"_CANDIDATE"
        if name in bpy.data.actions:
            raise ValueError("native_clip_new_action_name_collision")
        action=bpy.data.actions.new(name)
        slot=action.slots.new(rig.id_type,rig.name)
        layer=action.layers.new(name="Native "+clip)
        strip=layer.strips.new(type="KEYFRAME")
        strip.channelbags.new(slot=slot)
        action.use_fake_user=True
        assign_action(rig,action,slot)
        actions[clip]=(action,slot)
        clip_expected={"frames":[],"geometry":{}}
        clip_audit={"action":name,"author_metrics":[],"geometry_motion":{}}
        audit["clips"][clip]=clip_audit
        first_geometry=None
        maximum_mesh_motion={n:0.0 for n in ("GEO-snow-body","GEO-snow-shirt")}
        previous_channels=None
        for frame in FRAMES:
            audit["active_phase_frame"]={"phase":"AUTHOR","clip":clip,"frame":frame}
            write_audit(out/"native-clips-audit.json",audit)
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            profile=author_profile_frame(bpy,natural,proof,soft,helper,rig,baseline,baseline_channels,relative0,clip,frame,out)
            metrics,controls=validate_frame(bpy,natural,face,proof,soft,helper,rig,baseline,relative0,held,properties_before,clip,frame)
            metrics["orientation_phases"]=profile["orientation_phases"]
            if metrics["orientation_phases"]!=1:
                raise ValueError("native_clip_orientation_phase_count_mismatch")
            if previous_channels is not None:
                for bone_name,state in controls.items():
                    previous=previous_channels[bone_name]
                    field="rotation_quaternion" if state["rotation_mode"]=="QUATERNION" else "rotation_euler"
                    if field=="rotation_euler":
                        if max(abs(a-b) for a,b in zip(state[field],previous[field]))>math.pi/2:
                            raise ValueError("native_clip_euler_key_discontinuity")
                    elif sum(a*b for a,b in zip(state[field],previous[field]))<=0:
                        raise ValueError("native_clip_quaternion_key_sign_discontinuity")
            previous_channels=controls
            key_controls(rig,action,slot,proof,frame)
            curve_descriptor(action,slot,paths,False)
            joints=joint_snapshot(natural,rig)
            clip_expected["frames"].append({"frame":frame,"controls":controls,"joints":joints})
            if frame in GEOMETRY_FRAMES:
                evaluated_joints=joint_snapshot(natural,rig,evaluated=True,bpy=bpy)
                metrics["evaluated_rig_head_residual"]=max_joint_difference(joints,evaluated_joints)
                if metrics["evaluated_rig_head_residual"]>TOL:
                    raise ValueError("native_clip_author_evaluated_head_mismatch")
                snapshot,samples=geometry_sample(proof,bpy,geometry_objects)
                clip_expected["geometry"][str(frame)]=samples
                for item in snapshot.values():
                    union_points.extend(item["coords"])
                if first_geometry is None:
                    first_geometry=snapshot
                else:
                    deformation=proof.deformation(first_geometry,snapshot)
                    for mesh_name,row in deformation.items():
                        if not row["evaluated_topology_comparable"]:
                            raise ValueError("native_clip_author_evaluated_topology_changed")
                        maximum_mesh_motion[mesh_name]=max(maximum_mesh_motion[mesh_name],row["maximum_world_displacement"])
            clip_audit["author_metrics"].append(metrics)
        bag=selected_bag(action,slot)
        for curve in bag.fcurves:
            curve.extrapolation="CONSTANT"
            for point in curve.keyframe_points:
                point.interpolation="LINEAR"
            curve.update()
        descriptor=curve_descriptor(action,slot,paths,True)
        first,last=clip_expected["frames"][0],clip_expected["frames"][-1]
        loop_channels=channel_difference(last["controls"],first["controls"])
        loop_joints=max_joint_difference(last["joints"],first["joints"])
        sweep=max(max_joint_difference(row["joints"],first["joints"]) for row in clip_expected["frames"])
        velocity_gap=0.0
        for side in ("L","R"):
            p0=Vector(first["joints"][side]["Wrist"])
            p1=Vector(clip_expected["frames"][1]["joints"][side]["Wrist"])
            p47=Vector(clip_expected["frames"][-2]["joints"][side]["Wrist"])
            p48=Vector(last["joints"][side]["Wrist"])
            velocity_gap=max(velocity_gap,((p1-p0)-(p48-p47)).length)
        clip_audit.update({"action_descriptor":descriptor,"loop_channel_residual":loop_channels,
            "loop_joint_residual":loop_joints,"boundary_velocity_gap_m_per_frame":velocity_gap,
            "boundary_velocity_guard":0.03,"joint_sweep_m":sweep,"geometry_motion":maximum_mesh_motion})
        if (loop_channels>1e-5 or loop_joints>TOL or velocity_gap>0.03 or sweep<=0.001
                or any(v<=1e-5 for v in maximum_mesh_motion.values())):
            raise ValueError("native_clip_loop_or_actual_mesh_motion_gate_failed")
        clip_expected["action_descriptor"]=descriptor
        expected["clips"][clip]=clip_expected
        require_invariants(invariants(bpy,natural,face,proof,soft,pair,helper,rig,source_names),preserved)
        clip_audit["author_passed"]=True
        write_audit(out/"native-clips-audit.json",audit)
    pair_distances={}
    for i,a in enumerate(CLIPS):
        for b in CLIPS[i+1:]:
            distance=max(max_joint_difference(x["joints"],y["joints"])
                for x,y in zip(expected["clips"][a]["frames"],expected["clips"][b]["frames"]))
            pair_distances[a+"_"+b]=distance
    audit["profile_distinctness_world_m"]=pair_distances
    if any(v<=0.01 for v in pair_distances.values()):
        raise ValueError("native_clip_profiles_not_physically_distinct")
    shot=fixed_shot(union_points)
    audit["camera_config"]=shot
    audit["active_phase"]="PLAYBACK"
    for clip in CLIPS:
        action,slot=actions[clip]
        result=playback_clip(bpy,natural,face,proof,soft,pair,helper,rig,scene,geometry_objects,
            baseline,relative0,baseline_channels,held,properties_before,action,slot,paths,expected["clips"][clip],
            clip,audit,out,render_frames=PROOF_FRAMES[clip],shot=shot,materials=materials,emit=args.emit_preview,render_objects=objects)
        audit["clips"][clip]["playback"]=result
        require_invariants(invariants(bpy,natural,face,proof,soft,pair,helper,rig,source_names),preserved)
        write_audit(out/"native-clips-audit.json",audit)
    if len(audit["renders"])!=6:
        raise ValueError("native_clip_six_new_render_count_mismatch")
    idle_action,idle_slot=actions["idle"]
    assign_action(rig,idle_action,idle_slot)
    scene.frame_set(0)
    bpy.context.view_layer.update()
    require_invariants(invariants(bpy,natural,face,proof,soft,pair,helper,rig,source_names),preserved)
    if not recheck_inputs(source,blend,producer,audit):
        raise ValueError("native_clip_inputs_changed_before_save")
    target=out/"snow-native-clips-candidate.blend"
    if target.exists():
        raise ValueError("native_clip_candidate_output_already_exists")
    result=bpy.ops.wm.save_as_mainfile(filepath=str(target),check_existing=False)
    if "FINISHED" not in result or not target.is_file():
        raise ValueError("native_clip_candidate_save_failed")
    audit["models_saved"]=1
    audit["derivative"]={"file":target.name,"bytes":target.stat().st_size,"sha256":sha(target)}
    audit["saved_active_action"]={"action":idle_action.name,"slot_identifier":idle_slot.identifier,"frame":int(scene.frame_current)}
    audit["textures_packed"]=False
    audit["external_texture_portability"]="source texture paths remain external; no packing/export performed"
    expected["saved_active_action"]=audit["saved_active_action"]
    expected["candidate_sha256"]=audit["derivative"]["sha256"]
    expected=json.loads(encoded(expected))
    (out/"native-clips-expectations.json").write_bytes(encoded(expected))
    audit["author_and_playback_passed"]=True
    write_audit(out/"native-clips-audit.json",audit)
    return expected

def recheck_inputs(source,blend,producer,audit):
    unchanged=(sha(source)==SOURCE_SHA and sha(blend)==INPUT_SHA
        and sha(producer)==audit["producer_audit_sha256"])
    count=0
    files_match=True
    for image in audit["used_textures"]:
        for item in image["files"]:
            count+=1
            files_match=files_match and sha(source.parent/"textures"/item["file"])==item["sha256"]
    expected=audit.get("texture_expected_image_count")
    ready=sum(r.get("size_guard_passed",False) for r in audit["used_textures"])
    complete=(expected is not None and expected>0 and len(audit["used_textures"])==ready==expected
        and count==audit.get("texture_expected_file_count") and count>0 and audit["texture_preparation_complete"])
    audit["source_and_input_unchanged"]=unchanged
    audit["texture_hash_recheck"]={"expected_images":expected,"attempted_images":len(audit["used_textures"]),
        "ready_images":ready,"checked_files":count,"expected_files":audit.get("texture_expected_file_count"),
        "complete":complete,"all_checked_files_unchanged":files_match if count else None}
    return unchanged and complete and files_match

def reopen_verify(bpy,natural,face,proof,soft,pair,helper,config,source,target,expected,out,audit):
    # build_candidate has returned ONLY JSON data; no previous rig/Bone/Action/material RNA refs are used here.
    from mathutils import Vector
    if sha(target)!=expected["candidate_sha256"]:
        raise ValueError("native_clip_saved_candidate_hash_changed_before_reopen")
    bpy.context.preferences.filepaths.use_scripts_auto_execute=False
    bpy.ops.wm.open_mainfile(filepath=str(target),load_ui=False,use_scripts=False)
    rig=bpy.data.objects.get("RIG-Snow")
    scene=bpy.context.scene
    if rig is None or rig.type!="ARMATURE" or rig.data.pose_position!="POSE" or scene is None:
        raise ValueError("native_clip_reopened_rig_scene_missing")
    if bpy.context.preferences.filepaths.use_scripts_auto_execute:
        raise ValueError("native_clip_reopened_autoexec_enabled")
    active=expected["saved_active_action"]
    ad=rig.animation_data
    if (ad is None or ad.action is None or ad.action_slot is None or len(ad.nla_tracks)!=0
            or ad.action.name!=active["action"] or ad.action_slot.identifier!=active["slot_identifier"]
            or int(scene.frame_current)!=active["frame"] or scene.render.fps!=FPS or scene.render.fps_base!=1.0
            or scene.frame_start!=0 or scene.frame_end!=48):
        raise ValueError("native_clip_saved_active_binding_readback_mismatch")
    audit["reopened_active_binding"]={"action":ad.action.name,"slot_identifier":ad.action_slot.identifier,
        "frame":int(scene.frame_current),"autoexec":False}
    objects=[bpy.data.objects[n] for n in ("GEO-snow-body","GEO-snow-shirt")]
    materials=pair.used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
    images=pair.collect_images(materials)
    manifest={r["image"]:r for r in audit["used_textures"]}
    if set(i.name for i in images)!=set(manifest):
        raise ValueError("native_clip_reopened_used_image_set_mismatch")
    ready=[]
    for image in images:
        reference=manifest[image.name]
        filename=str(image.filepath).replace("\\","/").split("/")[-1]
        actual_parent=Path(bpy.path.abspath(image.filepath)).parent.resolve()
        if (image.source!=reference["source"] or filename!=reference["filename"]
                or actual_parent!=(source.parent/"textures").resolve()):
            raise ValueError("native_clip_reopened_texture_identity_or_path_mismatch")
        for item in reference["files"]:
            file=actual_parent/item["file"]
            if not file.is_file() or file.stat().st_size!=item["bytes"] or sha(file)!=item["sha256"]:
                raise ValueError("native_clip_reopened_texture_file_hash_mismatch")
        size=list(image.size)
        if len(size)!=2 or min(size)<=0 or not image.has_data:
            raise ValueError("native_clip_reopened_image_buffer_missing")
        ready.append({"image":image.name,"size":size,"has_data":True})
    audit["reopened_texture_buffers"]=ready
    baseline={s:{**b,"pivot":Vector(b["pivot"]),"chain_before":Vector(b["chain_before"])}
        for s,b in expected["baseline"].items()}
    require_invariants(invariants(bpy,natural,face,proof,soft,pair,helper,rig,expected["source_action_names"]),expected["preserved"])
    audit["reopen_playback"]={}
    for clip in CLIPS:
        reference=expected["clips"][clip]["action_descriptor"]
        action=bpy.data.actions.get(reference["action"])
        if action is None or not action.use_fake_user:
            raise ValueError("native_clip_saved_action_fake_user_missing")
        matches=[s for s in action.slots if s.identifier==reference["slot_identifier"]]
        if len(matches)!=1:
            raise ValueError("native_clip_saved_slot_identifier_mismatch")
        slot=matches[0]
        descriptor=curve_descriptor(action,slot,expected["expected_paths"],True)
        if descriptor!=reference:
            raise ValueError("native_clip_saved_curve_or_slot_readback_mismatch")
        result=playback_clip(bpy,natural,face,proof,soft,pair,helper,rig,scene,objects,
            baseline,expected["relative0"],expected["baseline_channels"],expected["held"],expected["properties"],
            action,slot,expected["expected_paths"],expected["clips"][clip],clip,audit,out)
        audit["reopen_playback"][clip]=result
        require_invariants(invariants(bpy,natural,face,proof,soft,pair,helper,rig,expected["source_action_names"]),expected["preserved"])
        write_audit(out/"native-clips-audit.json",audit)
    if sha(target)!=expected["candidate_sha256"]:
        raise ValueError("native_clip_readback_modified_saved_file")
    audit["reopen_verification_passed"]=True
    audit["preservation_passed"]=True
    manifest={"candidate":audit["derivative"],"source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,
        "producer_audit_sha256":audit["producer_audit_sha256"],"fps":FPS,"frames":[0,48],
        "clips":{name:audit["reopen_playback"][name]["action"] for name in CLIPS},
        "saved_active_binding":audit["reopened_active_binding"],"textures_external":True,
        "numeric_native_clip_candidate_verified":True,"overall_art_approved":False,
        "browser_animation_approved":False,"production_glb_approved":False}
    (out/"native-clips-saved-manifest.json").write_bytes(encoded(manifest))

def main():
    parser=argparse.ArgumentParser()
    for field in ("source-root","derivative-blend","config","out"):
        parser.add_argument("--"+field,required=True)
    parser.add_argument("--emit-preview",action="store_true")
    args=parser.parse_args()
    root=Path(args.source_root).resolve(strict=True)
    source=root/"snow/original/Snow/snow_v4.2.blend"
    blend=Path(args.derivative_blend).resolve(strict=True)
    producer=blend.with_name("friendly-face-audit.json")
    out=Path(args.out).resolve()
    if out.is_relative_to(root) or out.is_relative_to(blend.parent) or source.is_relative_to(out) or blend.is_relative_to(out):
        raise ValueError("native_clip_output_overlaps_inputs")
    if sha(source)!=SOURCE_SHA or sha(blend)!=INPUT_SHA or blend.stat().st_size!=INPUT_BYTES:
        raise ValueError("frozen_native_clip_input_hash_mismatch")
    raw=Path(args.config).read_bytes()
    if git_blob(raw)!=CONFIG_BLOB:
        raise ValueError("reviewed_native_clip_config_hash_mismatch")
    config=json.loads(raw)
    if config["poses"]!={"neutral":[]} or producer.stat().st_size>1048576:
        raise ValueError("native_clip_frozen_config_or_producer_size_mismatch")
    frozen=json.loads(producer.read_text(encoding="utf-8"))
    if (frozen["source_sha256"]!=SOURCE_SHA or frozen["derivative"]["sha256"]!=INPUT_SHA
            or frozen["derivative"]["bytes"]!=INPUT_BYTES or not frozen["candidate_completed"]
            or not frozen["preservation_passed"] or not frozen["numeric_width_gates_passed"]
            or frozen["friendly_functions_blob"]!=FACE_BLOB or frozen["pose_functions_blob"]!=POSE_BLOB
            or not frozen["texture_hash_recheck"]["complete"]):
        raise ValueError("frozen_width_producer_identity_mismatch")
    out.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        file=out/"credits"/relative
        file.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/relative,file)
        credits.append({"file":str(file.relative_to(out)),"bytes":file.stat().st_size,"sha256":sha(file)})
    audit={"purpose":"Three native Action candidates with AUTHOR, Fcurve PLAYBACK and saved-file REOPEN proof",
        "source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"input_bytes":INPUT_BYTES,
        "producer_audit_sha256":sha(producer),"producer_parent_input_sha256":frozen["input_sha256"],
        "natural_functions_blob":NATURAL_BLOB,"credits":credits,"used_textures":[],
        "texture_preparation_complete":False,"renders":[],"models_saved":0,"solver_runs":0,
        "fps":FPS,"frames":[0,48],"geometry_sample_frames":list(GEOMETRY_FRAMES),
        "finger_channels_written":False,"geometry_edits_performed":False,
        "overall_art_approved":False,"hand_art_approved":False,"clip_art_approved":False,
        "animation_approved":False,"browser_animation_approved":False,"production_glb_approved":False,
        "limits":["Untested three native candidate profiles; stop on unsupported mapping, no fallback or sweeps.",
            "All 49 frames checked in AUTHOR, Fcurve PLAYBACK and REOPEN; selected geometry frames only.",
            "One measured-offset relative-wrist orientation phase for each AUTHOR frame; never during PLAYBACK/REOPEN.",
            "Native shape-key VALUES may respond; current loaded DATA preserved without a hardcoded total/cross-save claim.",
            "Six NEW full-body clip frames share one union-bounds camera; no old static baseline renders.",
            "No continuous-time collision, finger articulation, professional motion, glTF/B-Bone export or browser acceptance.",
            "Textures remain externally referenced to verified originals; no packing or export."]}
    failure=None
    path=out/"native-clips-audit.json"
    write_audit(path,audit)
    try:
        natural,face,proof,soft,pair,helper=load_reviewed()
        import bpy
        if sys.version_info[:2]!=(3,11) or tuple(bpy.app.version)!=(4,5,9):
            raise ValueError("requires_verified_python_3_11_bpy_4_5_9")
        expected=build_candidate(bpy,natural,face,proof,soft,pair,helper,config,source,blend,producer,frozen,out,audit,args)
        audit["active_phase"]="REOPEN"
        # build_candidate's local RNA references have left scope. Only the following plain JSON expectations remain.
        reopen_verify(bpy,natural,face,proof,soft,pair,helper,config,source,
            out/"snow-native-clips-candidate.blend",expected,out,audit)
        if len(audit["renders"])!=6 or not recheck_inputs(source,blend,producer,audit):
            raise ValueError("native_clip_final_render_or_readonly_guard_failed")
        audit["numeric_native_clip_candidate_verified"]=True
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
            readonly=recheck_inputs(source,blend,producer,audit)
            write_audit(path,audit)
            clip_summary={}
            for name,record in audit.get("clips",{}).items():
                metrics=record.get("author_metrics",[])
                chains=[c for frame in metrics for c in frame["chains"]]
                playback=record.get("playback",{})
                reopen=audit.get("reopen_playback",{}).get(name,{})
                clip_summary[name]={"action":record.get("action_descriptor"),
                    "author_frames":len(metrics),"playback_frames":playback.get("frames_checked",0),
                    "reopen_frames":reopen.get("frames_checked",0),"loop_channel_residual":record.get("loop_channel_residual"),
                    "loop_joint_residual":record.get("loop_joint_residual"),"joint_sweep_m":record.get("joint_sweep_m"),
                    "geometry_motion":record.get("geometry_motion"),"boundary_velocity_gap_m_per_frame":record.get("boundary_velocity_gap_m_per_frame"),
                    "max_chain_residual":max((c["chain_residual"] for c in chains),default=None),
                    "max_relative_wrist_degrees":max((c["relative_wrist_degrees"] for c in chains),default=None),
                    "elbow_range_degrees":[min((c["elbow_degrees"] for c in chains),default=0),max((c["elbow_degrees"] for c in chains),default=0)],
                    "driver_invalid_max":max((m["driver_invalid"] for m in metrics),default=None),
                    "current_key_counts":sorted(set(m["key_count"] for m in metrics)),
                    "playback_mesh_sample_residual":playback.get("mesh_sample_max_residual"),
                    "reopen_mesh_sample_residual":reopen.get("mesh_sample_max_residual")}
            marker={"candidate_completed":audit.get("candidate_completed",False),"failure":audit.get("failure"),
                "active_phase_frame":audit.get("active_phase_frame"),"clips":clip_summary,
                "profile_distinctness_world_m":audit.get("profile_distinctness_world_m"),
                "author_and_playback_passed":audit.get("author_and_playback_passed",False),
                "reopen_verification_passed":audit.get("reopen_verification_passed",False),
                "preservation_passed":audit.get("preservation_passed",False),"models_saved":audit["models_saved"],
                "derivative":audit.get("derivative"),"renders":len(audit["renders"]),
                "views":[{"clip":r["clip"],"frame":r["frame"]} for r in audit["renders"]],
                "source_and_input_unchanged":audit.get("source_and_input_unchanged"),
                "texture_hash_recheck":audit.get("texture_hash_recheck"),"native_policy":audit.get("native_policy"),
                "finger_channels_written":False,"solver_runs":0,"old_static_baseline_renders":0,
                "overall_art_approved":False,"clip_art_approved":False,"animation_approved":False,
                "browser_animation_approved":False,"production_glb_approved":False}
            if len(encoded(marker))>24000:
                raise ValueError("native_clips_stdout_byte_budget_exceeded")
            print("SNOW_NATIVE_CLIPS_CANDIDATE "+encoded(marker).decode().strip(),flush=True)
            if failure is None and not readonly:
                raise ValueError("native_clip_final_readonly_check_failed")
        except Exception as cleanup_error:
            if failure is None:
                raise
            print("SNOW_NATIVE_CLIPS_CLEANUP_FAILED "+json.dumps({"error_type":type(cleanup_error).__name__[:80]}),flush=True)

if __name__=="__main__":
    main()
