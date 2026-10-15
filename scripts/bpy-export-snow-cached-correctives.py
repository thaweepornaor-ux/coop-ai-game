"""Cached-native two-mesh corrective GLB pilot. No native pose recapture or production acceptance."""
import argparse, hashlib, importlib.util, json, math, shutil, sys, zipfile
from pathlib import Path
import numpy as np
BASE_BLOB="cd7c8bd2fc7d4e4c6507808b3b4b3e1dbfa34b25"
def load_base():
    path=Path(__file__).with_name("bpy-prototype-snow-glb-correctives.py")
    raw=path.read_bytes()
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=BASE_BLOB:
        raise ValueError("cached_glb_reviewed_base_mismatch")
    spec=importlib.util.spec_from_file_location("_reviewed_corrective_utilities",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
base=load_base()
SOURCE_SHA,INPUT_SHA,INPUT_BYTES,PARENT_SHA=base.SOURCE_SHA,base.INPUT_SHA,base.INPUT_BYTES,base.PARENT_SHA
CONFIG_BLOB,NATIVE_BLOB,MESH_NAMES,CLIPS,FRAMES=base.CONFIG_BLOB,base.NATIVE_BLOB,base.MESH_NAMES,base.CLIPS,base.FRAMES
CAP,TRS_TOL,JOINT_TOL,CONDITION_CAP=base.CAP,base.TRS_TOL,base.JOINT_TOL,base.CONDITION_CAP
sha,git_blob,encode,checkpoint=base.sha,base.git_blob,base.encode,base.checkpoint
load_reviewed,id_inventory,copy_stage,cleanup=base.load_reviewed,base.id_inventory,base.copy_stage,base.cleanup
restore_binding,compose,require_finite=base.restore_binding,base.compose,base.require_finite
PINNED={
 "native_reference.npz":(15870464,"d21f2d557cf3261604e0dee37399fe65323516092ab8ece4ef1babe3d2dbe2be"),
 "native_reference.json":(79868,"ca8aa6a0785ad894619cedd673fc35cdd12298fa2cea579ee6db7d2ac5226df1"),
 "glb-correctives-audit.json":(78798,"44297fec9e3ea1b8415dd8917b2acd6597314235e09f90e1bb715d311b5f326a")}
def cache_files_match(root):
    return all((root/name).is_file() and not (root/name).is_symlink()
        and (root/name).stat().st_size==size and sha(root/name)==digest
        for name,(size,digest) in PINNED.items())

def chebyshev_scale(column,target,witness):
    sign=1.0 if witness>0 else -1.0
    if not math.isfinite(float(witness)) or abs(float(witness))<=1e-8:
        raise ValueError("cached_glb_scale_witness_invalid")
    coefficients=column.astype(np.float64)*sign
    target=target.astype(np.float64)
    def interval(error):
        lower,upper=1e-8,float("inf")
        for coefficient,value in zip(coefficients,target):
            if coefficient==0:
                if abs(value)>error:
                    return None
                continue
            a,b=(value-error)/coefficient,(value+error)/coefficient
            lower=max(lower,min(a,b));upper=min(upper,max(a,b))
        return (lower,upper) if lower<=upper and math.isfinite(lower) and math.isfinite(upper) else None
    lower=0.0
    upper=float(np.max(np.abs(coefficients*abs(float(witness))-target)))
    best=interval(upper)
    if best is None:
        raise ValueError("cached_glb_scale_initial_interval_invalid")
    for iteration in range(64):
        middle=(lower+upper)*0.5
        candidate=interval(middle)
        if candidate is None:
            lower=middle
        else:
            upper=middle;best=candidate
    magnitude=best[0]+(best[1]-best[0])*0.5
    value=np.float32(sign*magnitude)
    if not np.isfinite(value) or abs(float(value))<=1e-8 or np.sign(value)!=sign:
        raise ValueError("cached_glb_stored_scale_invalid")
    return value

def serialize_trs(world,parents,previous=None,scale_signs=None,audit=None,out=None,row=None):
    from mathutils import Matrix
    count=len(parents)
    translation=np.empty((count,3),dtype=np.float32)
    rotation=np.empty((count,4),dtype=np.float32)
    scale=np.empty((count,3),dtype=np.float32)
    local_error=0.0
    for i,parent in enumerate(parents):
        if audit is not None:
            audit["active_joint_serialization"]={"row":row,"joint_index":i}
        try:
            local=world[i] if parent<0 else np.linalg.solve(world[parent],world[i])
        except np.linalg.LinAlgError:
            if audit is not None:
                audit["joint_trs_failure"]={"row":row,"joint_index":i,"parent_index":parent,
                    "native_world_matrix":world[i].tolist(),"native_parent_matrix":world[parent].tolist()}
                checkpoint(out,audit)
            raise ValueError("corrective_glb_parent_joint_inverse_unsupported") from None
        require_finite(local)
        if abs(float(np.linalg.det(local[:3,:3])))<=1e-12:
            raise ValueError("corrective_glb_joint_local_not_invertible")
        t,q,s=Matrix(local.tolist()).decompose()
        q=np.array((q.x,q.y,q.z,q.w),dtype=np.float64)
        norm=float(np.linalg.norm(q))
        if not math.isfinite(norm) or norm<=1e-12:
            raise ValueError("corrective_glb_native_quaternion_invalid")
        q/=norm
        if previous is not None and float(np.dot(q,previous[i]))<0:
            q=-q
        translation[i],rotation[i],scale[i]=t,q,s
        if np.any(np.abs(scale[i])<=1e-8):
            raise ValueError("corrective_glb_joint_scale_zero")
        if scale_signs is not None and not np.array_equal(np.sign(scale[i]),scale_signs[i]):
            raise ValueError("corrective_glb_joint_scale_sign_changed")
        original_scale=scale[i].copy()
        original_error=float(np.max(np.abs(compose(translation[i],rotation[i],original_scale)-local)))
        R=base.quaternion_matrix(rotation[i])
        for column in range(3):
            try:
                scale[i,column]=chebyshev_scale(R[:,column],local[:3,column],original_scale[column])
            except ValueError:
                if audit is not None:
                    audit["scale_fit_failure"]={"row":row,"joint_index":i,"column":column,
                        "native_local_matrix":local.tolist(),"stored_rotation":rotation[i].tolist(),
                        "original_scale":original_scale.tolist()}
                    checkpoint(out,audit)
                raise
        error=float(np.max(np.abs(compose(translation[i],rotation[i],scale[i])-local)))
        if audit is not None:
            stats=audit.setdefault("scale_fit",{"algorithm":"fixed_quantized_rotation_signed_chebyshev_scale",
                "iterations_per_column":64,"local_tolerance":TRS_TOL,"joint_samples":0,
                "maximum_original_local_error":0.0,"maximum_stored_local_error":0.0,
                "maximum_scale_change":0.0,"examples":[]})
            stats["joint_samples"]+=1
            stats["maximum_original_local_error"]=max(stats["maximum_original_local_error"],original_error)
            stats["maximum_stored_local_error"]=max(stats["maximum_stored_local_error"],error)
            change=float(np.max(np.abs(scale[i].astype(np.float64)-original_scale.astype(np.float64))))
            stats["maximum_scale_change"]=max(stats["maximum_scale_change"],change)
            if (original_error>TRS_TOL or error>TRS_TOL) and len(stats["examples"])<12:
                stats["examples"].append({"row":row,"joint_index":i,"original_scale":original_scale.tolist(),
                    "stored_fitted_scale":scale[i].tolist(),"original_error":original_error,"stored_error":error})
        local_error=max(local_error,error)
        if error>TRS_TOL:
            if audit is not None:
                audit["joint_trs_failure"]={"row":row,"joint_index":i,"maximum_local_error":error,
                    "native_local_matrix":local.tolist(),"stored_translation":translation[i].tolist(),
                    "stored_rotation":rotation[i].tolist(),"stored_scale":scale[i].tolist()}
                checkpoint(out,audit)
            raise ValueError("corrective_glb_joint_trs_recomposition_or_shear_unsupported")
    return translation,rotation,scale,local_error



def load_cached(root):
    if not cache_files_match(root):
        raise ValueError("cached_glb_reference_file_pin_mismatch")
    reference=json.loads((root/"native_reference.json").read_text("utf-8"))
    cached=json.loads((root/"glb-correctives-audit.json").read_text("utf-8"))
    required=("readonly_cleanup_passed","input_id_inventory_preserved","input_preservation_passed","original_binding_restored")
    if (cached.get("failure")!={"error_code":"corrective_glb_joint_trs_recomposition_or_shear_unsupported","error_type":"ValueError"}
            or cached.get("writer_completed") is not False or not all(cached.get(k) is True for k in required)
            or cached.get("source_sha256")!=SOURCE_SHA or cached.get("input_sha256")!=INPUT_SHA
            or cached.get("native_functions_blob")!=NATIVE_BLOB):
        raise ValueError("cached_glb_failed_checkpoint_contract_mismatch")
    expected=cached["native_reference"]
    if (expected["authored_rows"]!=147 or expected["fractional_rows"]!=12
            or expected["captured_and_saved_before_trs_or_corrective_solve"] is not True
            or (expected["npz_bytes"],expected["npz_sha256"])!=PINNED["native_reference.npz"]
            or (expected["metadata_bytes"],expected["metadata_sha256"])!=PINNED["native_reference.json"]
            or reference["source_sha256"]!=SOURCE_SHA or reference["candidate_sha256"]!=INPUT_SHA
            or reference["reference_npz_sha256"]!=PINNED["native_reference.npz"][1]
            or reference["reference_npz_bytes"]!=PINNED["native_reference.npz"][0]):
        raise ValueError("cached_glb_native_reference_contract_mismatch")
    identity=reference["identity_proof"]
    if (identity["schema"]!="coop-armature-zero-identity-v1" or identity["joint_index"]!=186
            or identity["membership"]!={"full_membership_compared":True,"poses_checked":159,
                "raw_source_raw_clone_evaluated_equal":True}
            or identity["pre_armature"]["poses_checked"]!=159
            or identity["pre_armature"]["tolerance_world_m"]!=1e-6
            or identity["pre_armature"]["maximum_world_error"]!=0
            or identity["pre_armature"]["all_zero_eligible_vertices_compared"] is not True):
        raise ValueError("cached_glb_inherited_zero_proof_mismatch")
    keys={"mesh0_positions","mesh1_positions","mesh0_fractional_positions","mesh1_fractional_positions",
        "joint_world","fractional_joint_world"}
    npz=root/"native_reference.npz"
    with zipfile.ZipFile(npz) as z:
        infos=z.infolist()
        if (len(infos)!=6 or {i.filename for i in infos}!={k+".npy" for k in keys}
                or sum(i.file_size for i in infos)>256*1024*1024):
            raise ValueError("cached_glb_native_array_budget_mismatch")
    arrays={}
    shapes={"mesh0_positions":(147,5828,3),"mesh1_positions":(147,1839,3),
        "mesh0_fractional_positions":(12,5828,3),"mesh1_fractional_positions":(12,1839,3),
        "joint_world":(147,187,4,4),"fractional_joint_world":(12,187,4,4)}
    with np.load(npz,allow_pickle=False) as archive:
        if set(archive.files)!=keys:
            raise ValueError("cached_glb_native_array_names_mismatch")
        for key in keys:
            array=archive[key]
            if array.dtype.kind!="f" or array.dtype.itemsize!=8 or array.shape!=shapes[key]:
                raise ValueError("cached_glb_native_array_layout_mismatch")
            require_finite(array)
            array.flags.writeable=False
            arrays[key]=array
    if (not np.array_equal(arrays["joint_world"][:,-1],np.broadcast_to(np.eye(4),(147,4,4)))
            or not np.array_equal(arrays["fractional_joint_world"][:,-1],np.broadcast_to(np.eye(4),(12,4,4)))):
        raise ValueError("cached_glb_inherited_auxiliary_not_identity")
    return reference,cached,arrays

def export_cached(bpy,native,proof,soft,helper,rig,sources,duplicates,producer,C,out,audit,reference_root):
    reference,cached,arrays=load_cached(reference_root)
    if cached["producer_sha256"]!=audit["producer_sha256"]:
        raise ValueError("cached_glb_native_producer_changed")
    audit["cached_reference_guard"]={"frozen_run":38688634504,"frozen_head":"ebc6a2b7df5891abdc6a1160a1020fcfcd3038d1",
        "frozen_artifact":11951975296,"file_pins_rechecked":True,"expected_prior_trs_failure":True,
        "cached_source_preservation_passed":True,"npz_sha256":PINNED["native_reference.npz"][1]}
    audit["native_pose_provenance"]={"native_run":38688634504,"authored_rows_inherited":147,
        "fractional_rows_inherited":12,"zero_binding_poses_inherited":159,"native_frames_recaptured":0,
        "current_bind_pose_evaluations":1,"cached_proof_is_new_native_playback":False}
    checkpoint(out,audit)
    base.select_pose(bpy,native,proof,rig,producer,"idle",0)
    bind=[base.snapshot(bpy,d,s,rig,C,triangles=True) for d,s in zip(duplicates,sources)]
    recovery=[]
    for i,(source,duplicate,mesh) in enumerate(zip(sources,duplicates,bind)):
        expected=cached["bind_mesh_inventory"][i]
        raw=base.raw_membership(source,rig)
        clone=base.raw_membership(duplicate,rig)
        evaluation=mesh["weights"]
        classifications=[base.classify_membership(rows) for rows in (raw,clone,evaluation)]
        inherited=reference["identity_proof"]["meshes"][i]
        actual_hashes=[c["sha256"] for c in classifications]
        expected_hashes=[inherited[k] for k in ("raw_source_sha256","raw_clone_sha256","evaluated_sha256")]
        position_error=float(np.max(np.linalg.norm(mesh["positions"]-arrays["mesh"+str(i)+"_positions"][0],axis=1)))
        flags={"group_records_equal":raw==clone==evaluation,"membership_hashes_equal":actual_hashes==expected_hashes,
            "topology_uv_material_full_group_signature_equal":mesh["signature"]==expected["source_mapping_signature"],
            "source_point_ids_equal":mesh["source_point_ids"]==reference["meshes"][i]["source_point_ids"],
            "zero_ids_equal":classifications[0]["zero_ids"]==inherited["source_point_ids"],
            "no_tiny_positive":not any(c["tiny_ids"] for c in classifications),
            "bind_positions_equal_within_tolerance":position_error<=1e-6}
        recovery.append({"mesh":source.name,"vertex_count":len(mesh["positions"]),"flags":flags,
            "maximum_bind_world_error":position_error,"bind_tolerance_world_m":1e-6,
            "source_mapping_signature":mesh["signature"],"membership_sha256":actual_hashes,
            "zero_count":len(classifications[0]["zero_ids"]),
            "zero_ids_sha256":base.ids_hash(classifications[0]["zero_ids"]),
            "triangle_index_count":int(mesh["indices"].size)})
        audit["bind_recovery"]=recovery
        checkpoint(out,audit)
        if not all(flags.values()):
            raise ValueError("cached_glb_bind_recovery_mismatch")
    names,parents=base.bind_palette(rig,bind,audit,out)
    expected_joints=reference["joints"]
    native_count=len(names)
    if (native_count!=186 or len(expected_joints)!=187
            or any(expected_joints[i]!={"index":i,"kind":"native","node_name":"SnowJoint:"+name,"parent_index":parents[i]}
                for i,name in enumerate(names))
            or expected_joints[-1]!={"index":186,"kind":"auxiliary_identity","node_name":base.AUXILIARY_NAME,"parent_index":-1}):
        raise ValueError("cached_glb_native_palette_or_parent_changed")
    actual_bind_world=base.native_joint_world(bpy,rig,names,C)
    bind_joint_error=float(np.max(np.abs(actual_bind_world-arrays["joint_world"][0,:native_count])))
    audit["bind_joint_recovery"]={"native_joint_count":native_count,"maximum_matrix_error":bind_joint_error,
        "matrix_tolerance":1e-6,"palette_and_parent_mapping_exact":True}
    checkpoint(out,audit)
    if bind_joint_error>1e-6:
        raise ValueError("cached_glb_bind_joint_world_changed")
    if soft.driver_summary(helper,bpy)["active_invalid"]!=0:
        raise ValueError("cached_glb_current_native_driver_invalid")
    proof.key_values(bpy)
    names=list(names)+[base.AUXILIARY_NAME]
    parents=list(parents)+[-1]
    serialized=[base.serialized_weights(mesh,names,reference["identity_proof"]["meshes"][i]["source_point_ids"],186)
        for i,mesh in enumerate(bind)]
    joint_arrays=[v[0] for v in serialized]
    weight_arrays=[v[1] for v in serialized]
    total_vertices=sum(len(mesh["positions"]) for mesh in bind)
    target_bytes=total_vertices*147*3*4
    estimate=(target_bytes+total_vertices*3*4+sum(mesh["indices"].nbytes for mesh in bind)
        +sum(j.nbytes+w.nbytes for j,w in zip(joint_arrays,weight_arrays))
        +len(names)*16*4+len(names)*147*10*4+3*49*147*4+3*49*4+2097152+4096)
    audit["preflight"]={"conservative_glb_bytes":int(estimate),"cap_bytes":CAP,"position_target_bytes":target_bytes,
        "before_corrective_target_allocation":True,"influence_set_counts":[v[2] for v in serialized]}
    checkpoint(out,audit)
    if estimate>CAP:
        raise ValueError("cached_glb_preflight_cap_exceeded")
    for filename in ("native_reference.json","native_reference.npz"):
        shutil.copyfile(reference_root/filename,out/filename)
    for filename in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        if sha(reference_root/"credits"/filename)!=sha(out/"credits"/filename):
            raise ValueError("cached_glb_attribution_changed")
    audit["native_reference"]={**cached["native_reference"],"inherited_from_run":38688634504,"recaptured":False}
    checkpoint(out,audit)
    native_world=arrays["joint_world"]
    trs={"translation":np.empty((147,len(names),3),dtype=np.float32),
        "rotation":np.empty((147,len(names),4),dtype=np.float32),
        "scale":np.empty((147,len(names),3),dtype=np.float32)}
    stored_world=np.empty_like(native_world)
    maximum_local=maximum_world=0.0
    scale_signs=None
    for clip_index,clip in enumerate(CLIPS):
        previous=None
        for frame in FRAMES:
            row=clip_index*49+frame
            t,q,s,error=serialize_trs(native_world[row],parents,previous,scale_signs,audit,out,row)
            if scale_signs is None:
                scale_signs=np.sign(s)
            previous=q.astype(np.float64)
            trs["translation"][row],trs["rotation"][row],trs["scale"][row]=t,q,s
            reconstruction=base.world_from_trs(t,q,s,parents)
            stored_world[row]=reconstruction
            discrepancy=float(np.max(np.abs(reconstruction-native_world[row])))
            maximum_local=max(maximum_local,error)
            maximum_world=max(maximum_world,discrepancy)
            if discrepancy>JOINT_TOL:
                audit["joint_serialization_failure"]={"row":row,"clip":clip,"frame":frame,
                    "maximum_world_matrix_error":discrepancy}
                checkpoint(out,audit)
                raise ValueError("cached_glb_quantized_joint_world_residual_exceeded")
    audit["joint_serialization"]={"maximum_local_recompose_error":maximum_local,
        "maximum_world_matrix_error":maximum_world,"native_reference_inherited":True}
    try:
        ibm=require_finite(np.linalg.inv(stored_world[0])).astype(np.float32)
    except np.linalg.LinAlgError:
        raise ValueError("cached_glb_bind_inverse_unsupported") from None
    for i,mesh in enumerate(bind):
        mesh["bind_positions"]=arrays["mesh"+str(i)+"_positions"][0].copy()
        mesh["native_positions"]=arrays["mesh"+str(i)+"_positions"]
    base.write_glb(out,names,parents,bind,trs,stored_world,ibm,joint_arrays,weight_arrays,reference["frames"],audit)
    if (not cache_files_match(reference_root)
            or sha(out/"native_reference.npz")!=PINNED["native_reference.npz"][1]
            or sha(out/"native_reference.json")!=PINNED["native_reference.json"][1]):
        raise ValueError("cached_glb_native_reference_modified")
    audit["native_reference_hash_recheck"]=True
    audit["writer_completed"]=True
    audit["independent_reader_passed"]=False
    checkpoint(out,audit)

def main():
    parser=argparse.ArgumentParser()
    for field in ("source-root","derivative-blend","reference-root","config","out"):
        parser.add_argument("--"+field,required=True)
    args=parser.parse_args()
    root=Path(args.source_root).resolve(strict=True)
    source=root/"snow/original/Snow/snow_v4.2.blend"
    candidate=Path(args.derivative_blend).resolve(strict=True)
    producer_file=candidate.with_name("native-clips-audit.json")
    out=Path(args.out).resolve()
    reference_root=Path(args.reference_root).resolve(strict=True)
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
    audit={"purpose":"Cached POSITION-only BODY+SHIRT corrective GLB with fixed-rotation Chebyshev scale fitting",
        "source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"producer_sha256":sha(producer_file),
        "producer_parent_input_sha256":PARENT_SHA,"native_functions_blob":NATIVE_BLOB,"credits":credits,
        "used_textures":[],"renders":0,"models_saved":0,"source_geometry_edits":False,"source_driver_mute_or_detach":False,
        "writer_completed":False,"independent_reader_passed":False,"overall_art_approved":False,
        "browser_animation_approved":False,"production_glb_approved":False,
        "limits":["Armature-stage only: downstream CorrectiveSmooth/Mask/Subdivision/render-DG not exported or accepted.",
            "All eligible positive influences retained in JOINTS_n/WEIGHTS_n; no four-weight adapter or pruning.",
            "147+12 native references and zero-binding proof inherited from frozen run38688634504; no native pose recapture.",
            "Source UV/point/topology/material-index/full weights checked, but UV/NORMAL/material textures not exported.",
            "Fixed bind-polygon triangulation, not native deformed-quad surface or render equivalence.",
            "Native DQ and B-Bones remain unchanged; ordinary palette plus known-clip POSITION correctives is a bounded prototype.",
            "Independent GLB reader must validate authored/fractional positions and joints; writer residual is insufficient.",
            "No arbitrary poses/costumes/face changes, optimization, image generation, material bake or .blend save.",
            "Exactly one export-only identity joint is allowed only after all true-zero memberships and 159 pre-Armature checks pass; never a native rig edit."]}
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
            "producer":sha(producer_file)==audit["producer_sha256"],"cached_reference_files":cache_files_match(reference_root)}
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
        if sys.version_info[:2]!=(3,11) or tuple(bpy.app.version)!=(4,5,9):
            raise ValueError("requires_verified_python_3_11_bpy_4_5_9")
        bpy.context.preferences.filepaths.use_scripts_auto_execute=False
        bpy.ops.wm.open_mainfile(filepath=str(candidate),load_ui=False,use_scripts=False)
        rig=bpy.data.objects.get("RIG-Snow")
        sources=[bpy.data.objects.get(name) for name in MESH_NAMES]
        if (rig is None or rig.type!="ARMATURE" or rig.data.pose_position!="POSE"
                or any(obj is None or obj.type!="MESH" for obj in sources)):
            raise ValueError("corrective_glb_input_rig_or_mesh_missing")
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
        export_cached(bpy,native,proof,soft,helper,rig,sources,duplicates,producer,C,out,audit,reference_root)
    except Exception as error:
        failure=error
        code=error.args[0] if isinstance(error,ValueError) and len(error.args)==1 and isinstance(error.args[0],str) else None
        if not code or len(code)>100 or not all(c.islower() or c=="_" for c in code):
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
            readonly=recheck_files()
            final=(readonly and audit.get("original_binding_restored",False)
                and audit.get("input_id_inventory_preserved",False) and audit.get("input_preservation_passed",False)
                and audit.get("input_driver_after",{}).get("active_invalid")==0)
            audit["readonly_cleanup_passed"]=final
            audit["writer_completed"]=audit["writer_completed"] and failure is None and final
            checkpoint(out,audit)
            summary={key:audit.get(key) for key in ("writer_completed","failure","active_sample","active_joint_serialization",
                "cached_reference_guard","bind_recovery","native_pose_provenance","scale_fit","scale_fit_failure",
                "joint_trs_failure","joint_serialization_failure","actual_armature_flags","preflight","native_reference",
                "joint_serialization","condition_failure","residual_failure","corrective_solve","glb_written","maximum_skin_condition",
                "maximum_quantized_writer_residual","native_reference_hash_recheck","original_binding_restored",
                "input_id_inventory_preserved","input_preservation_passed","input_driver_before","input_driver_after",
                "input_key_count_before","input_key_count_after","input_file_recheck","readonly_cleanup_passed")}
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
            print("SNOW_GLB_CORRECTIVES_WRITER "+encode(summary).decode().strip(),flush=True)
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
            print("SNOW_GLB_CORRECTIVES_CLEANUP_FAILED "+json.dumps({"error_type":type(cleanup_error).__name__[:80]}),flush=True)


if __name__=="__main__":
    main()
