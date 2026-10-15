"""One native48Hz two-mesh corrective GLB candidate; cached/native provenance explicit."""
import argparse, copy, hashlib, importlib.util, json, math, shutil, struct, sys, zipfile
from pathlib import Path
import numpy as np
CACHED_BLOB="d8d357c8abf4a8546fa8e9ff8b8af2815c17d40d"
def load_cached_utilities():
    path=Path(__file__).with_name("bpy-export-snow-cached-correctives.py")
    raw=path.read_bytes()
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=CACHED_BLOB:
        raise ValueError("native48_reviewed_cached_utilities_mismatch")
    spec=importlib.util.spec_from_file_location("_reviewed_cached_export",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
cached=load_cached_utilities()
base=cached.base
SOURCE_SHA,INPUT_SHA,INPUT_BYTES,PARENT_SHA=base.SOURCE_SHA,base.INPUT_SHA,base.INPUT_BYTES,base.PARENT_SHA
CONFIG_BLOB,NATIVE_BLOB,MESH_NAMES,CLIPS=base.CONFIG_BLOB,base.NATIVE_BLOB,base.MESH_NAMES,base.CLIPS
CAP,TRS_TOL,JOINT_TOL,CONDITION_CAP=base.CAP,base.TRS_TOL,base.JOINT_TOL,base.CONDITION_CAP
sha,git_blob,encode,checkpoint=base.sha,base.git_blob,base.encode,base.checkpoint
load_reviewed,id_inventory,copy_stage,cleanup=base.load_reviewed,base.id_inventory,base.copy_stage,base.cleanup
restore_binding,compose,require_finite=base.restore_binding,base.compose,base.require_finite
cache_files_match,load_cached,serialize_trs=cached.cache_files_match,cached.load_cached,cached.serialize_trs
PINNED=cached.PINNED
GLBBuffer=base.GLBBuffer
AUXILIARY_NAME=base.AUXILIARY_NAME
FRAMES=tuple(k/2 for k in range(97))
FRACTIONAL=(.25,.75,12.25,12.75,24.25,24.75,36.25,36.75)
OLD_HALF=(.5,12.5,24.5,36.5)

def write_glb(out,names,parents,meshes,trs,world_stored,ibm,joint_arrays,weight_arrays,frames,audit):
    writer=GLBBuffer()
    joint_count=len(names)
    nodes=[]
    for i,name in enumerate(names):
        node={"name":name if name==AUXILIARY_NAME else "SnowJoint:"+name,"translation":trs["translation"][0,i].tolist(),
            "rotation":trs["rotation"][0,i].tolist(),"scale":trs["scale"][0,i].tolist()}
        if name==AUXILIARY_NAME:
            node["extras"]={"coop_joint_kind":"auxiliary_identity"}
        children=[j for j,parent in enumerate(parents) if parent==i]
        if children:
            node["children"]=children
        nodes.append(node)
    mesh_nodes=[joint_count+i for i in range(2)]
    for i,name in enumerate(MESH_NAMES):
        nodes.append({"name":name+":ArmatureStage","mesh":i,"skin":i})
    ibm_accessor=writer.add(ibm.transpose(0,2,1).reshape(joint_count,16),"MAT4")
    gltf_meshes=[]
    maximum_condition=0.0
    maximum_writer_residual=0.0
    for mesh_index,mesh in enumerate(meshes):
        base=mesh["bind_positions"].astype(np.float32)
        joint_indices=joint_arrays[mesh_index]
        weights=weight_arrays[mesh_index]
        attributes={"POSITION":writer.add(base,"VEC3",target=34962,bounds=True)}
        for k in range(joint_indices.shape[1]//4):
            attributes["JOINTS_"+str(k)]=writer.add(joint_indices[:,k*4:k*4+4],"VEC4",5123,34962)
            attributes["WEIGHTS_"+str(k)]=writer.add(weights[:,k*4:k*4+4],"VEC4",5126,34962)
        indices=writer.add(mesh["indices"],"SCALAR",5125,34963)
        targets=[]
        frame_stats=[]
        for row in range(291):
            palette=world_stored[row]@ibm.astype(np.float64)
            S=np.einsum("nk,nkij->nij",weights.astype(np.float64),palette[joint_indices])
            require_finite(S)
            A=S[:,:3,:3]
            condition=np.linalg.cond(A)
            require_finite(condition)
            worst_condition=float(np.max(condition))
            maximum_condition=max(maximum_condition,worst_condition)
            if worst_condition>CONDITION_CAP:
                vertex=int(np.argmax(condition))
                audit["condition_failure"]={"mesh":MESH_NAMES[mesh_index],"row":row,"maximum":worst_condition,
                    "vertex_index":vertex,"source_point_id":mesh["source_point_ids"][vertex],
                    "serialized_skin_linear":A[vertex].tolist(),"serialized_skin_translation":S[vertex,:3,3].tolist(),
                    "native_target_world":mesh["native_positions"][row,vertex].tolist()}
                checkpoint(out,audit)
                raise ValueError("corrective_glb_skin_condition_cap_exceeded")
            native_target=mesh["native_positions"][row]
            morphed=np.linalg.solve(A,native_target-S[:,:3,3])
            delta=require_finite(morphed-base.astype(np.float64)).astype(np.float32)
            # Quantized target+base and every skin value below are the values written to the GLB.
            actual=np.einsum("nij,nj->ni",A,base.astype(np.float64)+delta.astype(np.float64))+S[:,:3,3]
            error=np.linalg.norm(actual-native_target,axis=1)
            require_finite(error)
            worst_error=float(np.max(error))
            maximum_writer_residual=max(maximum_writer_residual,worst_error)
            if worst_error>1e-4:
                vertex=int(np.argmax(error))
                audit["residual_failure"]={"mesh":MESH_NAMES[mesh_index],"row":row,"vertex_index":vertex,
                    "source_point_id":mesh["source_point_ids"][vertex],"error_world_m":worst_error,
                    "condition":float(condition[vertex]),"native_target_world":native_target[vertex].tolist(),
                    "quantized_prediction":actual[vertex].tolist(),"stored_delta":delta[vertex].tolist()}
                checkpoint(out,audit)
                raise ValueError("corrective_glb_quantized_corrective_residual_exceeded")
            targets.append({"POSITION":writer.add(delta,"VEC3",target=34962,bounds=True)})
            frame_stats.append({"row":row,"maximum_condition":worst_condition,"maximum_quantized_writer_error":worst_error})
        gltf_meshes.append({"name":MESH_NAMES[mesh_index]+":ArmatureStage",
            "primitives":[{"attributes":attributes,"indices":indices,"mode":4,"targets":targets}],
            "weights":[1.0]+[0.0]*290,
            "extras":{"stage":"ARMATURE_ONLY","source_uv_checked_but_not_exported":True,
                "normals_not_exported":True,"all_positive_eligible_influences_retained":True}})
        audit.setdefault("corrective_solve",{})[MESH_NAMES[mesh_index]]={"frame_count":291,
            "maximum_condition":max(r["maximum_condition"] for r in frame_stats),
            "maximum_quantized_writer_error":max(r["maximum_quantized_writer_error"] for r in frame_stats)}
    animations=[]
    for clip_index,clip in enumerate(CLIPS):
        offset=clip_index*97
        time=writer.add(np.arange(97,dtype=np.float32)/np.float32(48),"SCALAR",bounds=True)
        samplers=[]
        channels=[]
        for joint in range(joint_count):
            for path,key,kind in (("translation","translation","VEC3"),("rotation","rotation","VEC4"),("scale","scale","VEC3")):
                output=writer.add(trs[key][offset:offset+97,joint],kind)
                samplers.append({"input":time,"output":output,"interpolation":"LINEAR"})
                channels.append({"sampler":len(samplers)-1,"target":{"node":joint,"path":path}})
        morph_weights=np.zeros((97,291),dtype=np.float32)
        morph_weights[np.arange(97),offset+np.arange(97)]=1.0
        output=writer.add(morph_weights.reshape(-1),"SCALAR")
        samplers.append({"input":time,"output":output,"interpolation":"LINEAR"})
        for node in mesh_nodes:
            channels.append({"sampler":len(samplers)-1,"target":{"node":node,"path":"weights"}})
        animations.append({"name":clip,"samplers":samplers,"channels":channels})
    attribution=(out/"credits/snow/ATTRIBUTION.txt").read_text(encoding="utf-8").strip()
    if len(attribution.encode())>16384:
        raise ValueError("corrective_glb_attribution_byte_budget_exceeded")
    gltf={"asset":{"version":"2.0","copyright":attribution,"generator":"Coop native Armature-stage corrective prototype",
        "extras":{"coop_corrective_contract":"coop-armature-correctives-48hz-v1","appearance_approved":False,
            "all_influences_prototype_not_four_weight_adapter":True,
            "source_credits":["credits/LICENSES.md","credits/snow/ATTRIBUTION.txt","credits/rain/ATTRIBUTION.txt"]}},
        "scene":0,"scenes":[{"nodes":[i for i,parent in enumerate(parents) if parent<0]+mesh_nodes}],
        "nodes":nodes,"meshes":gltf_meshes,
        "skins":[{"name":MESH_NAMES[i]+":native-ordinary-palette","joints":list(range(joint_count)),
            "inverseBindMatrices":ibm_accessor} for i in range(2)],
        "animations":animations,"buffers":[{"byteLength":len(writer.data)}],
        "bufferViews":writer.views,"accessors":writer.accessors}
    raw=json.dumps(gltf,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
    if len(raw)>2097152:
        raise ValueError("corrective_glb_json_size_cap_exceeded")
    raw+=b" "*((-len(raw))%4)
    binary=bytes(writer.data)+b"\0"*((-len(writer.data))%4)
    total=12+8+len(raw)+8+len(binary)
    if total>CAP:
        raise ValueError("corrective_glb_total_size_cap_exceeded")
    file=out/"snow-armature-correctives-48hz-prototype.glb"
    with file.open("xb") as handle:
        handle.write(struct.pack("<III",0x46546C67,2,total))
        handle.write(struct.pack("<II",len(raw),0x4E4F534A));handle.write(raw)
        handle.write(struct.pack("<II",len(binary),0x004E4942));handle.write(binary)
    audit["glb_written"]={"file":file.name,"bytes":file.stat().st_size,"sha256":sha(file)}
    audit["maximum_skin_condition"]=maximum_condition
    audit["maximum_quantized_writer_residual"]=maximum_writer_residual
    checkpoint(out,audit)
    return mesh_nodes


def export_uniform48(bpy,native,proof,soft,helper,rig,sources,duplicates,pre_body,producer,C,out,audit,reference_root):
    reference,cached,arrays=load_cached(reference_root)
    for filename in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        if sha(reference_root/"credits"/filename)!=sha(out/"credits"/filename):
            raise ValueError("native48_cached_attribution_changed")
    if cached["producer_sha256"]!=audit["producer_sha256"]:
        raise ValueError("cached_glb_native_producer_changed")
    audit["cached_reference_guard"]={"frozen_run":38688634504,"frozen_head":"ebc6a2b7df5891abdc6a1160a1020fcfcd3038d1",
        "frozen_artifact":11951975296,"file_pins_rechecked":True,"expected_prior_trs_failure":True,
        "cached_source_preservation_passed":True,"npz_sha256":PINNED["native_reference.npz"][1]}
    audit["native_pose_provenance"]={"cached_run":38688634504,"inherited_pose_count":159,"newly_captured_pose_count":0,
        "old_half_validation_reclassified_as_keys":12,"current_bind_pose_evaluations":1,"overlap_calibrations":0}
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

    flags=audit["actual_armature_flags"]
    if any(len(flags[s.name])!=1 or flags[s.name][0]["use_deform_preserve_volume"] is not True for s in sources):
        raise ValueError("native48_actual_native_dq_changed")
    memberships=base.prepare_membership(sources,duplicates,pre_body,rig,bind,out,audit)
    for i,membership in enumerate(memberships):
        inherited=reference["identity_proof"]["meshes"][i]
        if (membership["classification"]["zero_ids"]!=inherited["source_point_ids"]
                or membership["classification"]["sha256"]!=inherited["raw_source_sha256"]):
            raise ValueError("native48_membership_inherited_mismatch")
    # Conservative COMPLETE file bound, including actual binding/triangle streams and 2MiB JSON.
    sets=[max(1,(max(sum(1 for r in row if r[3]) for row in mesh["weights"])+3)//4) for mesh in bind]
    vertices=sum(len(m["positions"]) for m in bind)
    targets_bytes=vertices*291*3*4
    estimate=(targets_bytes+vertices*3*4+sum(m["indices"].nbytes for m in bind)
        +sum(len(m["positions"])*sets[i]*4*6 for i,m in enumerate(bind))
        +187*16*4+187*291*10*4+3*97*291*4+3*97*4+2097152+4096)
    expanded_reference_bytes=(291+24)*(vertices*3*8+187*16*8)
    audit["preflight"]={"cap_bytes":CAP,"conservative_glb_bytes":int(estimate),"position_target_bytes":targets_bytes,
        "position_target_count":291,"before_corrective_target_or_reference_allocation":True,
        "json_budget_bytes":2097152,"alignment_and_headers_budget":4096,
        "reference_expanded_bytes":expanded_reference_bytes,"reference_cap_bytes":256*1024*1024,
        "input_archive_caps_separate_from_output_glb_and_reference_caps":True,"influence_set_counts":sets}
    checkpoint(out,audit)
    if estimate>CAP or expanded_reference_bytes>256*1024*1024:
        raise ValueError("native48_preflight_file_or_reference_cap_exceeded")
    held=native.held_face_state(proof,rig)
    zero_ids=memberships[0]["classification"]["zero_ids"]
    if len(zero_ids)!=792:
        raise ValueError("native48_body_true_zero_count_changed")
    zero_indices=np.asarray(zero_ids,dtype=np.int64)-1
    maximum_face_drift=0.0
    def capture(clip,frame,record_membership):
        nonlocal maximum_face_drift
        base.select_pose(bpy,native,proof,rig,producer,clip,frame)
        current=[]
        for i,(duplicate,source) in enumerate(zip(duplicates,sources)):
            mesh=base.snapshot(bpy,duplicate,source,rig,C)
            if mesh["signature"]!=bind[i]["signature"]:
                raise ValueError("native48_ids_uv_topology_material_weights_changed")
            if record_membership:
                base.verify_membership_pose(mesh,memberships[i],audit["native_binding_correspondence"][i],out,audit)
            elif mesh["weights"]!=memberships[i]["weights"]:
                raise ValueError("native48_sentinel_full_membership_changed")
            current.append(mesh)
        pre=base.snapshot(bpy,pre_body,sources[0],rig,C)
        if (pre["signature"]!=bind[0]["signature"] or pre["weights"]!=memberships[0]["weights"]
                or np.max(np.abs(np.asarray(pre["matrix_world"])-np.asarray(current[0]["matrix_world"])))>1e-12
                or np.max(np.abs(np.asarray(pre["matrix_world"])-np.asarray(sources[0].matrix_world)))>1e-12):
            raise ValueError("native48_pre_armature_current_input_mismatch")
        distance=require_finite(np.linalg.norm(
            current[0]["positions"][zero_indices]-pre["positions"][zero_indices],axis=1))
        maximum=float(np.max(distance))
        if maximum>1e-6:
            k=int(np.argmax(distance))
            audit["zero_pre_armature_failure"]={"clip":clip,"frame":frame,"point_id":zero_ids[k],
                "maximum_world_error":maximum}
            checkpoint(out,audit)
            raise ValueError("native48_zero_binding_not_identity")
        state=native.held_face_state(proof,rig)
        drift=max(abs(state["properties"][side][kind]-held["properties"][side][kind])
            for side in ("L","R") for kind in ("Up","Wide"))
        maximum_face_drift=max(maximum_face_drift,drift)
        if (state["channels"]!=held["channels"] or not math.isfinite(drift) or drift>1e-4
                or np.max(np.abs(np.asarray(state["jaw_matrix"])-np.asarray(held["jaw_matrix"])))>1e-6):
            raise ValueError("native48_held_face_or_jaw_changed")
        if soft.driver_summary(helper,bpy)["active_invalid"]!=0:
            raise ValueError("native48_native_driver_invalid")
        proof.key_values(bpy)
        world=base.native_joint_world(bpy,rig,names,C)
        return [m["positions"] for m in current],world,maximum

    # One overlap calibration BEFORE cached/native rows are mixed. Not a new validation point.
    sentinel_row=next(r["row"] for r in reference["fractional_frames"] if r["clip"]=="wave" and r["frame"]==12.5)
    sentinel_positions,sentinel_world,sentinel_zero=capture("wave",12.5,False)
    sentinel={"clip":"wave","frame":12.5,
        "maximum_position_error":max(float(np.max(np.linalg.norm(sentinel_positions[i]
             -arrays["mesh"+str(i)+"_fractional_positions"][sentinel_row],axis=1))) for i in range(2)),
        "maximum_joint_matrix_error":float(np.max(np.abs(sentinel_world
             -arrays["fractional_joint_world"][sentinel_row,:186]))),
        "source_mapping_signatures_match":True,"native_membership_passed":True,
        "zero_pre_armature_maximum_world_error":sentinel_zero}
    sentinel["passed"]=(sentinel["maximum_position_error"]<=1e-6 and sentinel["maximum_joint_matrix_error"]<=1e-6)
    audit["overlap_sentinel"]=sentinel
    audit["native_pose_provenance"]["overlap_calibrations"]=1
    checkpoint(out,audit)
    if not sentinel["passed"]:
        raise ValueError("native48_cached_overlap_calibration_mismatch")
    positions=[np.empty((291,len(m["positions"]),3),dtype=np.float64) for m in bind]
    fractional_positions=[np.empty((24,len(m["positions"]),3),dtype=np.float64) for m in bind]
    joint_world=np.empty((291,187,4,4),dtype=np.float64)
    fractional_joint_world=np.empty((24,187,4,4),dtype=np.float64)
    inherited={}
    for phase,records in (("authored",reference["frames"]),("fractional",reference["fractional_frames"])):
        for rec in records:
            key=(rec["clip"],float(rec["frame"]))
            if key in inherited:
                raise ValueError("native48_cached_registry_duplicate")
            inherited[key]=(phase,rec["row"])
    if len(inherited)!=159:
        raise ValueError("native48_cached_registry_count")
    registry=[]; frame_map=[]; fractional_map=[]
    zero_maximum=0.0
    new_count=0
    audit["pose_registry"]=registry
    for fractional,samples in ((False,FRAMES),(True,FRACTIONAL)):
        for ci,clip in enumerate(CLIPS):
            for si,frame in enumerate(samples):
                row=ci*len(samples)+si
                phase="fractional" if fractional else "authored"
                audit["active_sample"]={"clip":clip,"frame":frame,"phase":phase,"row":row}
                key=(clip,float(frame))
                old=inherited.get(key)
                if fractional and old is not None:
                    raise ValueError("native48_holdout_not_disjoint")
                if old is not None:
                    old_phase,old_row=old
                    suffix="_fractional_positions" if old_phase=="fractional" else "_positions"
                    points=[arrays["mesh"+str(i)+suffix][old_row] for i in range(2)]
                    native_world=arrays["fractional_joint_world" if old_phase=="fractional" else "joint_world"][old_row,:186]
                    maximum=0.0
                    origin="cached_half" if old_phase=="fractional" else "cached_integer"
                else:
                    points,native_world,maximum=capture(clip,frame,True)
                    new_count+=1
                    audit["native_pose_provenance"]["newly_captured_pose_count"]=new_count
                    origin="new_quarter" if fractional else "new_half"
                for i in range(2):
                    (fractional_positions if fractional else positions)[i][row]=points[i]
                destination=fractional_joint_world if fractional else joint_world
                destination[row,:186]=native_world
                destination[row,186]=np.eye(4)
                zero_maximum=max(zero_maximum,maximum)
                registry.append({"clip":clip,"frame":frame,"phase":phase,"row":row,"origin":origin,
                    "membership_passed":True,"zero_pre_armature_maximum_world_error":maximum})
                rec={"clip":clip,"frame":frame,"time":frame/24.0,"row":row}
                (fractional_map if fractional else frame_map).append(rec)
            audit["native_pose_provenance"]["newly_captured_pose_count"]=new_count
            audit["pose_registry_progress"]={"unique":len(registry),"new":new_count}
            checkpoint(out,audit)
    counts={origin:sum(r["origin"]==origin for r in registry) for origin in
        ("cached_integer","cached_half","new_half","new_quarter")}
    if (counts!={"cached_integer":147,"cached_half":12,"new_half":132,"new_quarter":24}
            or len(registry)!=315 or len({(r["clip"],r["frame"]) for r in registry})!=315
            or new_count!=156 or any(r["correspondence_pose_count"]!=156 for r in audit["native_binding_correspondence"])):
        raise ValueError("native48_pose_registry_or_new_proof_incomplete")
    for a in (*positions,*fractional_positions,joint_world,fractional_joint_world):
        require_finite(a)
    identity=copy.deepcopy(reference["identity_proof"])
    identity["membership"]["poses_checked"]=315
    identity["pre_armature"]["poses_checked"]=315
    identity["pre_armature"]["maximum_world_error"]=zero_maximum
    identity["pose_registry"]=registry
    audit["identity_proof_summary"]={"joint_index":186,"native_joint_count":186,"poses_checked":315,
        "zero_count":792,"ids_sha256":base.ids_hash(zero_ids),"membership_passed":True,
        "maximum_pre_armature_world_error":zero_maximum,"origin_counts":counts,"new156_passed":True}
    # Full proof is now complete; only now materialize the export-only identity binding.
    names=list(names)+[AUXILIARY_NAME]; parents=list(parents)+[-1]
    serialized=[base.serialized_weights(m,names,identity["meshes"][i]["source_point_ids"],186) for i,m in enumerate(bind)]
    joint_arrays=[v[0] for v in serialized]; weight_arrays=[v[1] for v in serialized]
    npz=out/"native_reference.npz"
    with npz.open("xb") as file:
        np.savez_compressed(file,mesh0_positions=positions[0],mesh1_positions=positions[1],
            mesh0_fractional_positions=fractional_positions[0],mesh1_fractional_positions=fractional_positions[1],
            joint_world=joint_world,fractional_joint_world=fractional_joint_world)
    for a in (*positions,*fractional_positions,joint_world,fractional_joint_world):
        a.flags.writeable=False
    metadata=copy.deepcopy(reference)
    metadata.update({"fps":24,"export_sample_rate":48,"sampling_contract":"native48hz_keys291_holdouts24_v1",
        "frames":frame_map,"fractional_frames":fractional_map,"identity_proof":identity,
        "reference_npz_sha256":sha(npz),"reference_npz_bytes":npz.stat().st_size,
        "provenance":{**audit["native_pose_provenance"],"overlap_sentinel":sentinel}})
    raw=encode(metadata)
    if len(raw)>1048576:
        raise ValueError("native48_reference_json_budget")
    (out/"native_reference.json").write_bytes(raw)
    audit["native_reference"]={"metadata_bytes":len(raw),"metadata_sha256":sha(out/"native_reference.json"),
        "npz_bytes":npz.stat().st_size,"npz_sha256":sha(npz),"authored_rows":291,"fractional_rows":24,
        "captured_and_saved_before_trs_or_corrective_solve":True,
        "inherited_rows":159,"newly_captured_rows":156}
    checkpoint(out,audit)
    trs={"translation":np.empty((291,187,3),dtype=np.float32),
        "rotation":np.empty((291,187,4),dtype=np.float32),"scale":np.empty((291,187,3),dtype=np.float32)}
    stored_world=np.empty_like(joint_world)
    maximum_local=maximum_world=0.0
    scale_signs=None
    for ci,clip in enumerate(CLIPS):
        previous=None
        for si,frame in enumerate(FRAMES):
            row=ci*97+si
            t,q,s,error=serialize_trs(joint_world[row],parents,previous,scale_signs,audit,out,row)
            if scale_signs is None:
                scale_signs=np.sign(s)
            previous=q.astype(np.float64)
            trs["translation"][row],trs["rotation"][row],trs["scale"][row]=t,q,s
            reconstruction=base.world_from_trs(t,q,s,parents)
            stored_world[row]=reconstruction
            discrepancy=float(np.max(np.abs(reconstruction-joint_world[row])))
            maximum_local=max(maximum_local,error); maximum_world=max(maximum_world,discrepancy)
            if discrepancy>JOINT_TOL:
                audit["joint_serialization_failure"]={"row":row,"clip":clip,"frame":frame,"maximum_world_matrix_error":discrepancy}
                checkpoint(out,audit)
                raise ValueError("native48_quantized_joint_world_residual_exceeded")
    audit["joint_serialization"]={"maximum_local_recompose_error":maximum_local,
        "maximum_world_matrix_error":maximum_world,"maximum_face_drift_new_samples":maximum_face_drift}
    ibm=require_finite(np.linalg.inv(stored_world[0])).astype(np.float32)
    for i,mesh in enumerate(bind):
        mesh["bind_positions"]=positions[i][0].copy(); mesh["native_positions"]=positions[i]
    write_glb(out,names,parents,bind,trs,stored_world,ibm,joint_arrays,weight_arrays,frame_map,audit)
    if (not cache_files_match(reference_root) or sha(npz)!=metadata["reference_npz_sha256"]
            or sha(out/"native_reference.json")!=audit["native_reference"]["metadata_sha256"]):
        raise ValueError("native48_reference_file_modified")
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
    audit={"purpose":"Native48Hz mixed-cache POSITION-only BODY+SHIRT corrective GLB candidate",
        "source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"producer_sha256":sha(producer_file),
        "producer_parent_input_sha256":PARENT_SHA,"native_functions_blob":NATIVE_BLOB,"credits":credits,
        "used_textures":[],"renders":0,"models_saved":0,"source_geometry_edits":False,"source_driver_mute_or_detach":False,
        "writer_completed":False,"independent_reader_passed":False,"overall_art_approved":False,
        "browser_animation_approved":False,"production_glb_approved":False,
        "limits":["Armature-stage only: downstream CorrectiveSmooth/Mask/Subdivision/render-DG not exported or accepted.",
            "All eligible positive influences retained in JOINTS_n/WEIGHTS_n; no four-weight adapter or pruning.",
            "159 inherited rows plus156 NEW native poses; cached wave12.5 overlap calibration; 291keys+24freshquarter holdouts.",
            "Source UV/point/topology/material-index/full weights checked, but UV/NORMAL/material textures not exported.",
            "Fixed bind-polygon triangulation, not native deformed-quad surface or render equivalence.",
            "Native DQ and B-Bones remain unchanged; ordinary palette plus known-clip POSITION correctives is a bounded prototype.",
            "Independent GLB reader must validate authored/fractional positions and joints; writer residual is insufficient.",
            "No arbitrary poses/costumes/face changes, optimization, image generation, material bake or .blend save.",
            "Exactly one export-only identity joint is allowed only after all true-zero memberships and 315 disjoint inherited/new pre-Armature checks pass; never a native rig edit."]}
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
        pre_body=copy_stage(bpy,sources[0],rig,owned,audit,out)
        if helper.garment_geometry_signature(pre_body)!=helper.garment_geometry_signature(sources[0]):
            raise ValueError("native48_pre_armature_copy_data_mismatch")
        for modifier in list(pre_body.modifiers):
            pre_body.modifiers.remove(modifier)
        export_uniform48(bpy,native,proof,soft,helper,rig,sources,duplicates,pre_body,producer,C,out,audit,reference_root)
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
            readonly=recheck_files()
            final=(readonly and audit.get("original_binding_restored",False)
                and audit.get("input_id_inventory_preserved",False) and audit.get("input_preservation_passed",False)
                and audit.get("input_driver_after",{}).get("active_invalid")==0)
            audit["readonly_cleanup_passed"]=final
            audit["writer_completed"]=audit["writer_completed"] and failure is None and final
            checkpoint(out,audit)
            summary={key:audit.get(key) for key in ("writer_completed","failure","active_sample","active_joint_serialization",
                "cached_reference_guard","bind_recovery","native_pose_provenance","overlap_sentinel","pose_registry_progress","scale_fit","scale_fit_failure",
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
            print("SNOW_GLB_NATIVE48_WRITER "+encode(summary).decode().strip(),flush=True)
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
