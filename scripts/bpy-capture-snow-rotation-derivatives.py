"""Capture one fixed native rotation-derivative packet; never author, render or export."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys
import time
import zipfile
import numpy as np

BASE_BLOB="cd7c8bd2fc7d4e4c6507808b3b4b3e1dbfa34b25"
PLAN_BLOB="c2678d3962be9f70cf1a9188955ee0f5a15306e1"
PLAN_SHA="b96456634d1f79b130c1cc17a0e5dc31ab15f4a7e00d5cfe0a6943bb4c0033af"
PRODUCER_SHA="5c271962723af2b09bf331bd85d7f6e363f5334df6256265ee3ee4c983410518"
WHEEL_SHA="0bca32fe0658388f5ef669631220d7147fc2544bb0103a0042603519552b6b6a"
BIND_SIGNATURES=("658ce518697bc066093245581a6ffbf4ea87f863f2eabeac9074d95652155d1a",
    "0c3b7488dea92dc55cbad36e7685a7caf98837c6f49ae8e5f84d9a9f31c9a0d7")
PINNED={
    "source.glb":(30598112,"7308349db07a0542b54b3ec29949f2610562a2b3501ceaa51633ad0930571c06"),
    "native_reference.npz":(31443671,"6dca400a201b003e7ed81c8556d06cfa5afde07edad30705e2bf22ee487d9f94"),
    "native_reference.json":(143763,"83471e5eb420f716ef024b04e660ba29ba975f6e13a52835f65498c964fecb9d"),
    "source-writer-audit.json":(7484,"ce426af96c85ee809f14e8681c549c0021bfa63c43b58944b9ab3c27079c4ae4"),
    "source-reader-audit.json":(289659,"245480cadc22088f71283af1d5dfd26877eb65e4445cf836b168f775d67d8b76")}
def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def import_base():
    path=Path(__file__).with_name("bpy-prototype-snow-glb-correctives.py")
    if git_blob(path.read_bytes())!=BASE_BLOB:
        raise ValueError("rotation_packet_base_source_pin_mismatch")
    spec=importlib.util.spec_from_file_location("rotation_packet_reviewed_base",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
base=import_base()
SOURCE_SHA,INPUT_SHA,INPUT_BYTES,PARENT_SHA=base.SOURCE_SHA,base.INPUT_SHA,base.INPUT_BYTES,base.PARENT_SHA
CONFIG_BLOB,NATIVE_BLOB,MESH_NAMES=base.CONFIG_BLOB,base.NATIVE_BLOB,base.MESH_NAMES
sha,encode,checkpoint=base.sha,base.encode,base.checkpoint
load_reviewed,id_inventory,copy_stage,cleanup=base.load_reviewed,base.id_inventory,base.copy_stage,base.cleanup
restore_binding,require_finite=base.restore_binding,base.require_finite

def saved_native_policy(bpy):
    records=[]
    visited=set()
    for category in ("objects","meshes","armatures","shape_keys","materials","node_groups","scenes","worlds","curves"):
        for block in getattr(bpy.data,category):
            for item in (block,getattr(block,"node_tree",None)):
                if item is None or int(item.as_pointer()) in visited:
                    continue
                visited.add(int(item.as_pointer()))
                ad=getattr(item,"animation_data",None)
                if ad is None:
                    continue
                for curve in ad.drivers:
                    d=curve.driver
                    records.append((item.name,curve.data_path,int(curve.array_index),
                        bool(d.type!="SCRIPTED" or d.is_simple_expression),bool(curve.mute)))
    report={"autoexec_enabled":bool(bpy.context.preferences.filepaths.use_scripts_auto_execute),
        "driver_count":len(records),"non_native_unmuted":sum(not r[3] and not r[4] for r in records),
        "muted":sum(r[4] for r in records),"native_unmuted":sum(r[3] and not r[4] for r in records),
        "driver_policy_sha256":hashlib.sha256(encode(sorted(records))).hexdigest(),
        "action_detach_calls":0,"driver_mute_writes":0,"embedded_text_executed":False}
    if report["autoexec_enabled"] or report["non_native_unmuted"] or report["muted"]:
        raise ValueError("rotation_packet_saved_native_policy_unsupported")
    return report

def cache_files_match(root):
    return all((root/name).is_file() and (root/name).stat().st_size==size and sha(root/name)==digest
        for name,(size,digest) in PINNED.items())

def load_baseline(root):
    if not cache_files_match(root):
        raise ValueError("rotation_packet_frozen_baseline_pin_mismatch")
    reference=json.loads((root/"native_reference.json").read_text())
    writer=json.loads((root/"source-writer-audit.json").read_text())
    reader=json.loads((root/"source-reader-audit.json").read_text())
    summary=reader["summary"]
    if (not all(writer[k] for k in ("writer_completed","readonly_cleanup_passed","native_reference_hash_recheck"))
            or writer["failure"] is not None or writer["classification"]["factored_indices"]!=[183]
            or not summary["authored_passed"] or summary["authored_frames_checked"]!=291
            or summary["fractional_frames_checked"]!=24 or summary["fractional_passed"] or summary["passed"]
            or len(reader["fractional_frames"])!=24
            or sum(not r["joint_matrix_passed"] for r in reader["fractional_frames"])!=6
            or not all(m["passed"] for r in reader["fractional_frames"] for m in r["meshes"])
            or reference["candidate_sha256"]!=INPUT_SHA or reference["source_sha256"]!=SOURCE_SHA
            or reference["sampling_contract"]!="native48hz_keys291_holdouts24_v1"
            or reference["reference_npz_sha256"]!=PINNED["native_reference.npz"][1]
            or reference["identity_proof"]["membership"]["poses_checked"]!=315):
        raise ValueError("rotation_packet_expected_baseline_failure_contract")
    expected={"mesh0_positions":(291,5828,3),"mesh1_positions":(291,1839,3),
        "mesh0_fractional_positions":(24,5828,3),"mesh1_fractional_positions":(24,1839,3),
        "joint_world":(291,187,4,4),"fractional_joint_world":(24,187,4,4)}
    with zipfile.ZipFile(root/"native_reference.npz") as archive:
        infos=archive.infolist()
        if (len(infos)!=6 or len({i.filename for i in infos})!=6
                or {i.filename for i in infos}!={k+".npy" for k in expected}
                or sum(i.file_size for i in infos)>256*1024*1024):
            raise ValueError("rotation_packet_npz_expanded_budget_or_members")
    with np.load(root/"native_reference.npz",allow_pickle=False) as data:
        if set(data.files)!=set(expected):
            raise ValueError("rotation_packet_npz_array_names")
        arrays={k:data[k] for k in expected}
    for key,shape in expected.items():
        a=arrays[key]
        if a.dtype!=np.dtype("float64") or a.shape!=shape:
            raise ValueError("rotation_packet_npz_dtype_or_shape")
        require_finite(a)
        a.flags.writeable=False
    for key in ("joint_world","fractional_joint_world"):
        if not np.array_equal(arrays[key][:,186],np.broadcast_to(np.eye(4),arrays[key][:,186].shape)):
            raise ValueError("rotation_packet_cached_auxiliary_not_identity")
    return reference,arrays

def validate_plan(plan,packet):
    if (plan["contract"]!="snow_native_rotation_derivative_eps1024_split_v1"
            or plan["contains_captured_pose_data"] or plan["source_fps"]!=24
            or plan["epsilon_rational_source_frames"]!=[1,1024]
            or plan["difference_rational_seconds"]!=[1,24576]
            or plan["source_native_blend_sha256"]!=INPUT_SHA
            or plan["source_glb_sha256"]!=PINNED["source.glb"][1]
            or plan["reference_npz_sha256"]!=PINNED["native_reference.npz"][1]
            or plan["reference_metadata_sha256"]!=PINNED["native_reference.json"][1]):
        raise ValueError("rotation_packet_plan_contract")
    eps=plan["epsilon_joint_only_samples"]
    fresh=plan["fresh_validation_samples"]
    if (len(eps)!=576 or len(fresh)!=24 or [r["id"] for r in eps]!=list(range(576))
            or [r["id"] for r in fresh]!=list(range(24))):
        raise ValueError("rotation_packet_plan_registry")
    expected=[]
    for ci,clip in enumerate(("idle","wave","celebrate")):
        for k in range(97):
            for side in ("incoming","outgoing"):
                if (side=="incoming" and k==0) or (side=="outgoing" and k==96):
                    continue
                i=len(expected)
                expected.append({"id":i,"packet":0 if i<288 else 1,"clip":clip,"key_index":k,
                    "authored_row":ci*97+k,"key_frame":k/2,"side":side,
                    "sample_frame":k/2+(-1 if side=="incoming" else 1)/1024})
    if eps!=expected:
        raise ValueError("rotation_packet_epsilon_registry_not_fixed")
    quarters=(.125,.375,12.125,12.375,24.125,24.375,36.125,36.375)
    fresh_expected=[{"id":ci*8+i,"packet":0,"clip":clip,"sample_frame":frame,
        "role":"fresh_geometry_and_joint_validation"} for ci,clip in enumerate(("idle","wave","celebrate"))
        for i,frame in enumerate(quarters)]
    if fresh!=fresh_expected:
        raise ValueError("rotation_packet_fresh_registry_not_fixed")
    selected=[r for r in eps if r["packet"]==packet]
    selected_fresh=[r for r in fresh if r["packet"]==packet]
    if len(selected)!=288 or len(selected_fresh)!=(24 if packet==0 else 0):
        raise ValueError("rotation_packet_selection_count")
    return selected,selected_fresh

def capture_packet(bpy,native,proof,soft,helper,rig,sources,duplicates,pre_body,producer,C,out,audit,root,plan,packet):
    reference,arrays=load_baseline(root)
    eps,fresh=validate_plan(plan,packet)
    for filename in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        if sha(root/"credits"/filename)!=sha(out/"credits"/filename):
            raise ValueError("rotation_packet_credit_mismatch")
    base.select_pose(bpy,native,proof,rig,producer,"idle",0)
    bind=[base.snapshot(bpy,d,s,rig,C,triangles=True) for d,s in zip(duplicates,sources)]
    for i,(source,duplicate,mesh) in enumerate(zip(sources,duplicates,bind)):
        raw=base.raw_membership(source,rig)
        clone=base.raw_membership(duplicate,rig)
        info=[base.classify_membership(rows) for rows in (raw,clone,mesh["weights"])]
        inherited=reference["identity_proof"]["meshes"][i]
        error=float(np.max(np.linalg.norm(mesh["positions"]-arrays["mesh"+str(i)+"_positions"][0],axis=1)))
        flags={"full_membership_equal":raw==clone==mesh["weights"],
            "full_membership_hashes_equal":[r["sha256"] for r in info]==[inherited[k] for k in
                ("raw_source_sha256","raw_clone_sha256","evaluated_sha256")],
            "topology_uv_material_weight_signature_equal":mesh["signature"]==BIND_SIGNATURES[i],
            "point_ids_equal":mesh["source_point_ids"]==reference["meshes"][i]["source_point_ids"],
            "zero_ids_equal":info[0]["zero_ids"]==inherited["source_point_ids"],
            "tiny_positive_absent":not any(r["tiny_ids"] for r in info),"bind_position_passed":error<=1e-6}
        audit.setdefault("bind_recovery",[]).append({"mesh":source.name,"flags":flags,
            "maximum_position_error_m":error,"source_mapping_signature":mesh["signature"],
            "triangle_index_count":int(mesh["indices"].size)})
        checkpoint(out,audit)
        if not all(flags.values()):
            raise ValueError("rotation_packet_bind_recovery_failed")
    names,parents=base.bind_palette(rig,bind,audit,out)
    expected=reference["joints"]
    if (len(names)!=186 or len(expected)!=187 or any(expected[i]!={"index":i,"kind":"native",
            "node_name":"SnowJoint:"+name,"parent_index":parents[i]} for i,name in enumerate(names))
            or expected[186]!={"index":186,"kind":"auxiliary_identity","node_name":base.AUXILIARY_NAME,"parent_index":-1}):
        raise ValueError("rotation_packet_palette_or_parent_mismatch")
    flags=audit["actual_armature_flags"]
    if any(len(flags[s.name])!=1 or flags[s.name][0]["use_deform_preserve_volume"] is not True for s in sources):
        raise ValueError("rotation_packet_native_dq_changed")
    memberships=base.prepare_membership(sources,duplicates,pre_body,rig,bind,out,audit)
    zero_ids=memberships[0]["classification"]["zero_ids"]
    if len(zero_ids)!=792 or memberships[1]["classification"]["zero_ids"]:
        raise ValueError("rotation_packet_zero_binding_changed")
    zero_indices=np.asarray(zero_ids,dtype=np.int64)-1
    held=native.held_face_state(proof,rig)
    maximum_face=maximum_zero=0.0
    def capture(clip,frame,geometry):
        nonlocal maximum_face,maximum_zero
        base.select_pose(bpy,native,proof,rig,producer,clip,frame)
        state=native.held_face_state(proof,rig)
        drift=max(abs(state["properties"][s][k]-held["properties"][s][k])
            for s in ("L","R") for k in ("Up","Wide"))
        maximum_face=max(maximum_face,drift)
        if (state["channels"]!=held["channels"] or not math.isfinite(drift) or drift>1e-4
                or np.max(np.abs(np.asarray(state["jaw_matrix"])-np.asarray(held["jaw_matrix"])))>1e-6):
            raise ValueError("rotation_packet_held_face_or_jaw_changed")
        if soft.driver_summary(helper,bpy)["active_invalid"]!=0:
            raise ValueError("rotation_packet_native_driver_invalid")
        proof.key_values(bpy)
        if bpy.context.preferences.filepaths.use_scripts_auto_execute:
            raise ValueError("rotation_packet_autoexec_enabled_during_capture")
        world=np.empty((187,4,4),dtype=np.float64)
        world[:186]=base.native_joint_world(bpy,rig,names,C)
        world[186]=np.eye(4)
        require_finite(world)
        if not geometry:
            return world,None,0.0
        current=[]
        for i,(d,s) in enumerate(zip(duplicates,sources)):
            mesh=base.snapshot(bpy,d,s,rig,C)
            if mesh["signature"]!=bind[i]["signature"]:
                raise ValueError("rotation_packet_point_topology_uv_material_weights_changed")
            # Re-read BOTH source and raw owned memberships at every fresh geometry/sentinel pose.
            if base.raw_membership(s,rig)!=memberships[i]["weights"] or base.raw_membership(d,rig)!=memberships[i]["weights"]:
                raise ValueError("rotation_packet_raw_membership_changed")
            base.verify_membership_pose(mesh,memberships[i],audit["native_binding_correspondence"][i],out,audit)
            current.append(mesh)
        pre=base.snapshot(bpy,pre_body,sources[0],rig,C)
        if (pre["signature"]!=bind[0]["signature"] or pre["weights"]!=memberships[0]["weights"]
                or np.max(np.abs(np.asarray(pre["matrix_world"])-np.asarray(current[0]["matrix_world"])))>1e-12
                or np.max(np.abs(np.asarray(pre["matrix_world"])-np.asarray(sources[0].matrix_world)))>1e-12):
            raise ValueError("rotation_packet_pre_armature_current_input_mismatch")
        distance=require_finite(np.linalg.norm(current[0]["positions"][zero_indices]-pre["positions"][zero_indices],axis=1))
        error=float(np.max(distance));maximum_zero=max(maximum_zero,error)
        if error>1e-6:
            audit["zero_pre_armature_failure"]={"clip":clip,"frame":frame,
                "point_id":zero_ids[int(np.argmax(distance))],"maximum_world_error_m":error}
            checkpoint(out,audit)
            raise ValueError("rotation_packet_zero_binding_identity_failed")
        return world,[m["positions"] for m in current],error

    sentinel_rows=[r for r in reference["frames"] if r["clip"]=="wave" and r["frame"]==12.5]
    if len(sentinel_rows)!=1:
        raise ValueError("rotation_packet_sentinel_cached_row_missing")
    row=sentinel_rows[0]["row"]
    world,points,zero=capture("wave",12.5,True)
    matrix_error=float(np.max(np.abs(world-arrays["joint_world"][row])))
    position_error=max(float(np.max(np.linalg.norm(points[i]-arrays["mesh"+str(i)+"_positions"][row],axis=1))) for i in range(2))
    audit["overlap_sentinel"]={"clip":"wave","frame":12.5,"cached_authored_row":row,
        "maximum_joint_matrix_abs_error":matrix_error,"maximum_position_world_error_m":position_error,
        "maximum_zero_pre_armature_world_error_m":zero,"adds_unique_pose":False,
        "passed":matrix_error<=1e-6 and position_error<=1e-6}
    checkpoint(out,audit)
    if not audit["overlap_sentinel"]["passed"]:
        raise ValueError("rotation_packet_overlap_calibration_failed")
    expanded=288*187*16*8+len(fresh)*(187*16+3*(5828+1839))*8
    audit["preflight"]={"expanded_packet_array_bytes":expanded,"expanded_cap_bytes":256*1024*1024,
        "before_output_array_allocation":True,"duplicates_frozen_payloads":False}
    if expanded>256*1024*1024:
        raise ValueError("rotation_packet_expanded_array_budget")
    output={"epsilon_joint_world":np.empty((288,187,4,4),np.float64),
        "fresh_joint_world":np.empty((len(fresh),187,4,4),np.float64),
        "fresh_mesh0_positions":np.empty((len(fresh),5828,3),np.float64),
        "fresh_mesh1_positions":np.empty((len(fresh),1839,3),np.float64)}
    registry=[]
    started=time.monotonic()
    for kind,records in (("epsilon_joint_only",eps),("fresh_geometry",fresh)):
        for local,record in enumerate(records):
            audit["active_sample"]={"kind":kind,"local_row":local,**record}
            world,points,zero=capture(record["clip"],record["sample_frame"],kind=="fresh_geometry")
            output["epsilon_joint_world" if kind=="epsilon_joint_only" else "fresh_joint_world"][local]=world
            if points is not None:
                for i in range(2):
                    output["fresh_mesh"+str(i)+"_positions"][local]=points[i]
            registry.append({"kind":kind,"local_row":local,**record,"native_driver_invalid":0,
                "held_face_passed":True,"finite_key_values_passed":True,
                "geometry_proved":kind=="fresh_geometry","maximum_zero_world_error_m":zero if points is not None else None})
            if local%24==23 or local==len(records)-1:
                audit["capture_progress"]={"captured_unique":len(registry),"epsilon":sum(r["kind"]=="epsilon_joint_only" for r in registry),
                    "fresh_geometry":sum(r["kind"]=="fresh_geometry" for r in registry),
                    "elapsed_capture_seconds":time.monotonic()-started}
                checkpoint(out,audit)
                print("SNOW_ROTATION_PACKET_PROGRESS "+json.dumps(audit["capture_progress"]),flush=True)
    if (len(registry)!=288+len(fresh) or len({(r["clip"],r["sample_frame"]) for r in registry})!=len(registry)
            or any(r["correspondence_pose_count"]!=1+len(fresh) for r in audit["native_binding_correspondence"])):
        raise ValueError("rotation_packet_registry_incomplete")
    for a in output.values():
        require_finite(a);a.flags.writeable=False
    payload=out/("native-rotation-packet-"+str(packet)+".npz")
    with payload.open("xb") as file:
        np.savez_compressed(file,**output)
    digest=sha(payload)
    with np.load(payload,allow_pickle=False) as reopened:
        if set(reopened.files)!=set(output):
            raise ValueError("rotation_packet_saved_array_names")
        for k,a in output.items():
            b=reopened[k]
            if b.dtype!=np.dtype("float64") or b.shape!=a.shape or not np.array_equal(a,b):
                raise ValueError("rotation_packet_saved_array_readback")
    if sha(payload)!=digest or not cache_files_match(root):
        raise ValueError("rotation_packet_saved_or_input_hash_changed")
    audit["packet_payload"]={"file":payload.name,"bytes":payload.stat().st_size,"sha256":digest,
        "arrays":{k:{"shape":list(v.shape),"dtype":"float64","finite":True} for k,v in output.items()},
        "reopened_all_arrays_byte_values_equal":True,"sha256_recheck":True}
    audit["pose_registry"]=registry
    audit["proof_counts"]={"epsilon_joint_only_this_packet":288,"epsilon_geometry_proofs":0,
        "fresh_geometry_this_packet":len(fresh),"unique_new_this_packet":len(registry),
        "sentinel_unique":0,"geometry_inherited":315,"geometry_verified_from_baseline_plus_this_packet":315+len(fresh)}
    audit["native_sample_guards"]={"maximum_held_face_property_drift":maximum_face,
        "maximum_zero_pre_armature_world_error_m":maximum_zero,
        "native_invalid_count":0,"full_raw_clone_eval_memberships_for_geometry":True,
        "zero_binding_count":792,"source_point_ids_and_palette_exact":True}
    audit["data_capture_and_saved_readback_passed"]=True
    checkpoint(out,audit)

def main():
    parser=argparse.ArgumentParser()
    for field in ("source-root","derivative-blend","baseline-root","config","plan","out"):
        parser.add_argument("--"+field,required=True)
    parser.add_argument("--packet",type=int,choices=(0,1),required=True)
    args=parser.parse_args()
    root=Path(args.source_root).resolve(strict=True)
    source=root/"snow/original/Snow/snow_v4.2.blend"
    candidate=Path(args.derivative_blend).resolve(strict=True)
    producer_file=candidate.with_name("native-clips-audit.json")
    out=Path(args.out).resolve()
    reference_root=Path(args.baseline_root).resolve(strict=True)
    plan_path=Path(args.plan).resolve(strict=True)
    plan_raw=plan_path.read_bytes()
    if git_blob(plan_raw)!=PLAN_BLOB or hashlib.sha256(plan_raw).hexdigest()!=PLAN_SHA:
        raise ValueError("rotation_packet_plan_pin_mismatch")
    plan=json.loads(plan_raw)
    validate_plan(plan,args.packet)
    if (out.is_relative_to(root) or out.is_relative_to(candidate.parent) or source.is_relative_to(out)
            or candidate.is_relative_to(out) or out.is_relative_to(reference_root) or reference_root.is_relative_to(out)):
        raise ValueError("corrective_glb_output_overlaps_input")
    if sha(source)!=SOURCE_SHA or sha(candidate)!=INPUT_SHA or candidate.stat().st_size!=INPUT_BYTES:
        raise ValueError("corrective_glb_frozen_input_hash_mismatch")
    config_raw=Path(args.config).read_bytes()
    if git_blob(config_raw)!=CONFIG_BLOB:
        raise ValueError("corrective_glb_reviewed_config_hash_mismatch")
    config=json.loads(config_raw)
    if not all(name in config["mesh_names"] for name in MESH_NAMES) or producer_file.stat().st_size>2097152:
        raise ValueError("corrective_glb_config_or_producer_size_mismatch")
    if sha(producer_file)!=PRODUCER_SHA:
        raise ValueError("rotation_packet_native_producer_pin_mismatch")
    producer=json.loads(producer_file.read_text(encoding="utf-8"))
    if (producer["source_sha256"]!=SOURCE_SHA or producer["input_sha256"]!=PARENT_SHA
            or producer["derivative"]["sha256"]!=INPUT_SHA or producer["derivative"]["bytes"]!=INPUT_BYTES
            or producer["derivative"]["file"]!="snow-native-clips-candidate.blend"
            or not all(producer[k] for k in ("numeric_native_clip_candidate_verified","reopen_verification_passed",
                "preservation_passed","candidate_completed"))):
        raise ValueError("corrective_glb_producer_identity_mismatch")
    out.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","snow/ATTRIBUTION.txt","rain/ATTRIBUTION.txt"):
        file=out/"credits"/relative
        file.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/relative,file)
        credits.append({"file":str(file.relative_to(out)),"bytes":file.stat().st_size,"sha256":sha(file)})
    audit={"purpose":"One fixed native epsilon/fresh-validation capture packet; no GLB rewrite",
        "packet_id":args.packet,"sampling_plan_sha256":PLAN_SHA,
        "source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"producer_sha256":sha(producer_file),
        "producer_parent_input_sha256":PARENT_SHA,"native_functions_blob":NATIVE_BLOB,"credits":credits,
        "used_textures":[],"renders":0,"models_saved":0,"glb_written":False,
        "source_geometry_edits":False,"source_driver_mute_or_detach":False,
        "data_capture_and_saved_readback_passed":False,"capture_complete":False,
        "overall_art_approved":False,"browser_animation_approved":False,"production_glb_approved":False,
        "limits":["EPS samples contain joint matrices only, not mesh deformation proof.",
            "315 geometry rows inherited from38696896433; only fixed fresh24 geometry poses are new in packet0.",
            "Sentinel is a cached overlap calibration and adds no unique pose.",
            "Packet1 has no repeated fresh geometry poses; both packets required before offline derivatives.",
            "No native authoring/pose-control writes, model/GLB save, render or material bake.",
            "Armature-stage BODY+SHIRT only; no downstream modifier/full-avatar/browser/production acceptance."]}
    checkpoint(out,audit)
    failure=None
    rig=None
    modules=None
    binding=None
    baseline_ids=None
    baseline_invariants=None
    source_actions=None
    owned={"objects":[],"meshes":[],"keys":set()}
    def recheck_files():
        flags={"source":sha(source)==SOURCE_SHA,"candidate":sha(candidate)==INPUT_SHA,
            "producer":sha(producer_file)==audit["producer_sha256"],"cached_reference_files":cache_files_match(reference_root),
            "plan":sha(plan_path)==PLAN_SHA,"config":git_blob(Path(args.config).read_bytes())==CONFIG_BLOB,
            "capture_source":sha(Path(__file__))==audit.get("capture_source_sha256"),
            "runtime_report":Path("bpy-proof/bpy-runtime.json").is_file() and sha(Path("bpy-proof/bpy-runtime.json"))==audit.get("runtime_report_sha256")}
        flags["helper_sources"]=all(git_blob(Path(path).read_bytes())==blob for path,blob in audit.get("helper_source_paths",{}).items())
        count=0
        matching=True
        for image in audit["used_textures"]:
            for record in image["files"]:
                count+=1
                path=source.parent/"textures"/record["file"]
                matching=matching and path.is_file() and sha(path)==record["sha256"]
        expected=audit.get("expected_texture_images")
        ready=sum(r.get("size_guard_passed",False) for r in audit["used_textures"])
        complete=(expected is not None and expected>0 and len(audit["used_textures"])==ready==expected
            and count==audit.get("expected_texture_files") and count>0)
        audit["input_file_recheck"]={**flags,"checked_texture_files":count,
            "expected_texture_files":audit.get("expected_texture_files"),"textures_complete":complete,
            "all_checked_textures_unchanged":matching if count else None}
        return all(flags.values()) and complete and matching
    try:
        modules=load_reviewed()
        native,natural,face,proof,soft,pair,helper=modules
        import bpy
        if sys.version_info[:2]!=(3,11) or tuple(bpy.app.version)!=(4,5,9) or np.__version__!="1.26.4":
            raise ValueError("requires_verified_python_3_11_bpy_4_5_9")
        runtime_file=Path("bpy-proof/bpy-runtime.json")
        runtime=json.loads(runtime_file.read_text())
        if (not runtime["ok"] or runtime["wheel_sha256"]!=WHEEL_SHA or runtime["autoexec_enabled"]
                or not runtime["blender_version"].startswith("4.5.9")):
            raise ValueError("rotation_packet_verified_runtime_report_mismatch")
        module_paths={str(Path(m.__file__).resolve()):git_blob(Path(m.__file__).read_bytes()) for m in (base,*modules)}
        # Two transitive modules are validated by importers but are not returned in their tuples.
        for filename,pin in (("bpy-proof-snow-bent-elbows.py","49ca4d50be3a2c03300db2fa47980104f27455ab"),
                ("bpy-prototype-snow-crewneck.py","059fad9611e95ece356ff6911a9de879dcb3d363")):
            path=Path(__file__).with_name(filename).resolve()
            if git_blob(path.read_bytes())!=pin:
                raise ValueError("rotation_packet_transitive_helper_pin_mismatch")
            module_paths[str(path)]=pin
        audit["helper_source_paths"]=module_paths
        audit["capture_source_sha256"]=sha(Path(__file__))
        audit["runtime_report_sha256"]=sha(runtime_file)
        envelope={"sampling_plan_sha256":PLAN_SHA,"capture_wrapper_git_blob_sha":git_blob(Path(__file__).read_bytes()),
            "imported_helper_git_blob_pins":{Path(path).name:blob for path,blob in sorted(module_paths.items())},
            "source_native_blend_sha256":INPUT_SHA,"source_native_producer_audit_sha256":PRODUCER_SHA,
            "original_snow_sha256":SOURCE_SHA,"reference_npz_sha256":PINNED["native_reference.npz"][1],
            "reference_metadata_sha256":PINNED["native_reference.json"][1],
            "source_glb_sha256":PINNED["source.glb"][1],
            "bpy_version_and_wheel_sha256":{"version":list(bpy.app.version),"official_wheel_sha256":WHEEL_SHA},
            "render_config_sha256":hashlib.sha256(config_raw).hexdigest()}
        if set(envelope)!=set(plan["packet_envelope_must_bind"]):
            raise ValueError("rotation_packet_envelope_field_mismatch")
        audit["provenance_envelope"]=envelope
        audit["provenance_envelope_sha256"]=hashlib.sha256(encode(envelope)).hexdigest()
        bpy.context.preferences.filepaths.use_scripts_auto_execute=False
        bpy.ops.wm.open_mainfile(filepath=str(candidate),load_ui=False,use_scripts=False)
        rig=bpy.data.objects.get("RIG-Snow")
        sources=[bpy.data.objects.get(name) for name in MESH_NAMES]
        if (rig is None or rig.type!="ARMATURE" or rig.data.pose_position!="POSE"
                or any(obj is None or obj.type!="MESH" for obj in sources)):
            raise ValueError("corrective_glb_input_rig_or_mesh_missing")
        if any(o.name not in bpy.context.scene.objects for o in (rig,*sources)):
            raise ValueError("rotation_packet_loaded_rig_or_source_not_in_scene")
        audit["native_policy_before"]=saved_native_policy(bpy)
        if audit["native_policy_before"]["native_unmuted"]!=producer["native_policy"]["native_retained"]:
            raise ValueError("rotation_packet_saved_native_policy_count_mismatch")
        if bpy.context.scene.render.fps!=24 or float(bpy.context.scene.render.fps_base)!=1.0:
            raise ValueError("rotation_packet_native_scene_fps_changed")
        ad=rig.animation_data
        if ad is None or ad.action is None or ad.action_slot is None or len(ad.nla_tracks)!=0:
            raise ValueError("corrective_glb_input_action_or_slot_missing")
        binding={"action":ad.action.name,"slot_identifier":ad.action_slot.identifier,
            "frame":int(bpy.context.scene.frame_current),"subframe":float(bpy.context.scene.frame_subframe)}
        audit["initial_binding"]=binding
        materials=pair.used_materials([o for o in bpy.context.scene.objects if o.type=="MESH" and not o.hide_render])
        images=pair.collect_images(materials)
        references={item["image"]:item for item in producer["used_textures"]}
        if len(references)!=len(producer["used_textures"]) or not images:
            raise ValueError("corrective_glb_texture_manifest_invalid")
        count=0
        for image in images:
            reference=references.get(image.name)
            filename=str(image.filepath).replace("\\","/").split("/")[-1]
            if reference is None or image.source!=reference["source"] or filename!=reference["filename"] or not reference["size_guard_passed"]:
                raise ValueError("corrective_glb_used_texture_identity_mismatch")
            count+=len(reference["files"])
        audit["expected_texture_images"]=len(images)
        audit["expected_texture_files"]=count
        audit["material_graph_before_verified_relink"]=proof.material_graph_hash(bpy,pair)
        pair.relink_and_reload(images,source.parent/"textures",audit["used_textures"],lambda:checkpoint(out,audit))
        for item in audit["used_textures"]:
            if item["files"]!=references[item["image"]]["files"]:
                raise ValueError("corrective_glb_used_texture_hash_mismatch")
        audit["material_graph_after_verified_relink"]=proof.material_graph_hash(bpy,pair)
        audit["verified_texture_path_relink_intentional"]=True
        if not recheck_files():
            raise ValueError("corrective_glb_input_file_verification_failed")
        source_actions=[action.name for action in bpy.data.actions]
        baseline_ids=id_inventory(bpy)
        baseline_invariants=native.invariants(bpy,natural,face,proof,soft,pair,helper,rig,source_actions)
        audit["input_preservation_before"]=baseline_invariants
        audit["input_id_counts"]={key:len(value) for key,value in baseline_ids.items()}
        audit["input_driver_before"]=soft.driver_summary(helper,bpy)
        audit["input_key_count_before"]=len(proof.key_values(bpy))
        checkpoint(out,audit)
        if audit["input_driver_before"]["active_invalid"]!=0:
            raise ValueError("corrective_glb_input_native_driver_invalid")
        duplicates=[copy_stage(bpy,obj,rig,owned,audit,out) for obj in sources]
        bpy.context.view_layer.update()
        for duplicate,source_obj in zip(duplicates,sources):
            if helper.garment_geometry_signature(duplicate)!=helper.garment_geometry_signature(source_obj):
                raise ValueError("corrective_glb_copied_raw_or_key_data_differs")
        C=np.array(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)),dtype=np.float64)
        pre_body=copy_stage(bpy,sources[0],rig,owned,audit,out)
        if helper.garment_geometry_signature(pre_body)!=helper.garment_geometry_signature(sources[0]):
            raise ValueError("native48_pre_armature_copy_data_mismatch")
        for modifier in list(pre_body.modifiers):
            pre_body.modifiers.remove(modifier)
        capture_packet(bpy,native,proof,soft,helper,rig,sources,duplicates,pre_body,producer,C,out,audit,reference_root,plan,args.packet)
    except Exception as error:
        failure=error
        code=error.args[0] if isinstance(error,ValueError) and len(error.args)==1 and isinstance(error.args[0],str) else None
        if not code or len(code)>100 or not all(c.islower() or c.isdigit() or c=="_" for c in code):
            code=None
        audit["failure"]={"error_type":type(error).__name__,"error_code":code}
        raise
    finally:
        try:
            if modules is not None and rig is not None:
                native,natural,face,proof,soft,pair,helper=modules
                if baseline_ids is not None:
                    cleanup(bpy,owned,baseline_ids)
                if binding is not None:
                    restore_binding(bpy,native,rig,binding)
                    audit["original_binding_restored"]=(rig.animation_data.action.name==binding["action"]
                        and rig.animation_data.action_slot.identifier==binding["slot_identifier"]
                        and int(bpy.context.scene.frame_current)==binding["frame"]
                        and float(bpy.context.scene.frame_subframe)==binding["subframe"])
                if baseline_ids is not None:
                    audit["input_id_inventory_preserved"]=id_inventory(bpy)==baseline_ids
                    after=native.invariants(bpy,natural,face,proof,soft,pair,helper,rig,source_actions)
                    audit["input_preservation_after"]=after
                    audit["input_preservation_passed"]=after==baseline_invariants
                    audit["input_driver_after"]=soft.driver_summary(helper,bpy)
                    audit["input_key_count_after"]=len(proof.key_values(bpy))
                    audit["native_policy_after"]=saved_native_policy(bpy)
            readonly=recheck_files()
            final=(readonly and audit.get("original_binding_restored",False)
                and audit.get("input_id_inventory_preserved",False) and audit.get("input_preservation_passed",False)
                and audit.get("input_driver_after",{}).get("active_invalid")==0
                and audit.get("input_driver_after")==audit.get("input_driver_before")
                and audit.get("native_policy_after")==audit.get("native_policy_before"))
            audit["readonly_cleanup_passed"]=final
            audit["capture_complete"]=audit["data_capture_and_saved_readback_passed"] and failure is None and final
            if audit["capture_complete"]:
                packet_metadata={key:audit[key] for key in ("packet_id","sampling_plan_sha256","provenance_envelope",
                    "provenance_envelope_sha256","packet_payload","pose_registry","proof_counts","native_sample_guards",
                    "overlap_sentinel","readonly_cleanup_passed","capture_complete")}
                packet_metadata.update({"schema_version":1,"contract":plan["contract"],"joints":json.loads(
                    (reference_root/"native_reference.json").read_text())["joints"],
                    "epsilon_matrices_are_not_geometry_proof":True,"production_glb_approved":False})
                packet_file=out/("native-rotation-packet-"+str(args.packet)+".json")
                packet_raw=encode(packet_metadata)
                if len(packet_raw)>1048576:
                    raise ValueError("rotation_packet_metadata_byte_budget")
                packet_file.write_bytes(packet_raw)
                if json.loads(packet_file.read_text())!=packet_metadata or packet_file.read_bytes()!=packet_raw:
                    audit["capture_complete"]=False
                    raise ValueError("rotation_packet_metadata_saved_readback")
                audit["packet_metadata"]={"file":packet_file.name,"bytes":packet_file.stat().st_size,"sha256":sha(packet_file)}
            checkpoint(out,audit)
            summary={key:audit.get(key) for key in ("capture_complete","failure","active_sample","packet_id",
                "capture_progress","native_policy_before","native_policy_after","bind_recovery","overlap_sentinel","actual_armature_flags","preflight",
                "packet_payload","packet_metadata","proof_counts","native_sample_guards","provenance_envelope_sha256",
                "original_binding_restored","input_id_inventory_preserved","input_preservation_passed",
                "input_driver_before","input_driver_after","input_key_count_before","input_key_count_after",
                "input_file_recheck","readonly_cleanup_passed")}
            summary["identity_proof_summary"]=audit.get("identity_proof_summary")
            summary["zero_pre_armature_failure"]=audit.get("zero_pre_armature_failure")
            summary["native_binding_correspondence"]=[{key:report.get(key) for key in (
                "mesh_index","vertex_count","raw_source_sha256","raw_clone_sha256","evaluated_sha256",
                "zero_eligible_count","zero_ids_sha256","zero_ids_first","tiny_positive_count","tiny_ids_first",
                "correspondence_passed","correspondence_pose_count","offending_point_ids_first")}
                for report in audit.get("native_binding_correspondence",[])]
            summary.update({"renders":0,"models_saved":0,"independent_reader_passed":False,
                "overall_art_approved":False,"browser_animation_approved":False,"production_glb_approved":False})
            if len(encode(summary))>24000:
                raise ValueError("corrective_glb_stdout_byte_budget_exceeded")
            print("SNOW_ROTATION_NATIVE_PACKET "+encode(summary).decode().strip(),flush=True)
            if failure is None and not final:
                raise ValueError("corrective_glb_final_input_preservation_failed")
        except Exception as cleanup_error:
            if failure is None:
                raise
            audit["cleanup_error_type"]=type(cleanup_error).__name__[:80]
            try:
                checkpoint(out,audit)
            except Exception:
                pass
            print("SNOW_ROTATION_PACKET_CLEANUP_FAILED "+json.dumps({"error_type":type(cleanup_error).__name__[:80]}),flush=True)


if __name__=="__main__":
    main()
