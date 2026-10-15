"""Two real Armature-stage meshes, native ordinary joints and sampled corrective GLB.
POSITION-only/all-influence prototype; no downstream modifiers, render, material bake or export acceptance.
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
import numpy as np

NATIVE_BLOB="051f18c2633a7aa2b1fd6b95483e23d5a96adcb9"
CONFIG_BLOB="f0612039b320e8dac77587ec4aecdc2c84618843"
SOURCE_SHA="80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
INPUT_SHA="b22306981a809bdb2e537c52087efe8d503bc30a0efe73573a51bb6200aeffa3"
INPUT_BYTES=8297412
PARENT_SHA="572897f5416f256950134e408ead8d77ecf53c0accbe5f7912be976c3c763ea4"
MESH_NAMES=("GEO-snow-body","GEO-snow-shirt")
CLIPS=("idle","wave","celebrate")
FRAMES=tuple(range(49))
FRACTIONAL=(0.5,12.5,24.5,36.5)
TAG="_coop_glb_source_point_id"
AUXILIARY_NAME="exportaux_identityjoint"
EXPECTED_BODY_ZERO_COUNT=792
CAP=32*1024*1024
TRS_TOL=1e-5
JOINT_TOL=1e-4
CONDITION_CAP=1e6

def encode(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n").encode()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()

def checkpoint(out,audit):
    raw=encode(audit)
    if len(raw)>1048576:
        raise ValueError("corrective_glb_audit_byte_budget_exceeded")
    (out/"glb-correctives-audit.json").write_bytes(raw)

def require_finite(value):
    if not np.isfinite(value).all():
        raise ValueError("corrective_glb_numeric_nonfinite")
    return value

def load_reviewed():
    path=Path(__file__).with_name("bpy-prototype-snow-native-clips.py")
    if git_blob(path.read_bytes())!=NATIVE_BLOB:
        raise ValueError("corrective_glb_reviewed_native_functions_hash_mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_native_clip_functions",path)
    native=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    return (native,*native.load_reviewed())

def id_inventory(bpy):
    return {kind:sorted((item.name,int(item.as_pointer())) for item in getattr(bpy.data,kind))
        for kind in ("objects","meshes","shape_keys","actions")}

def shape_values(keys):
    return [(k.name,float(k.value)) for k in keys.key_blocks] if keys else []

def copy_stage(bpy,source,rig,owned,audit,out):
    modifiers=[(i,m) for i,m in enumerate(source.modifiers) if m.type=="ARMATURE" and m.show_viewport]
    flags=[]
    for i,m in modifiers:
        flags.append({"index":i,"name":m.name,"target":m.object.name if m.object else None,
            **{field:getattr(m,field) for field in ("use_deform_preserve_volume","use_vertex_groups",
                "use_bone_envelopes","use_multi_modifier","vertex_group","invert_vertex_group","show_viewport","show_render")}})
    audit.setdefault("actual_armature_flags",{})[source.name]=flags
    checkpoint(out,audit)
    if (len(modifiers)!=1 or modifiers[0][0]!=0 or modifiers[0][1].object!=rig
            or not modifiers[0][1].use_vertex_groups or modifiers[0][1].use_bone_envelopes
            or modifiers[0][1].use_multi_modifier or modifiers[0][1].vertex_group!=""
            or modifiers[0][1].invert_vertex_group):
        raise ValueError("corrective_glb_armature_stage_flags_unsupported")
    # Preserve native Preserve Volume/DQ and B-Bones unchanged. Only downstream copy modifiers are removed.
    duplicate=source.copy()
    owned["objects"].append(duplicate)
    mesh=source.data.copy()
    owned["meshes"].append(mesh)
    duplicate.data=mesh
    if mesh==source.data or (source.data.shape_keys and (mesh.shape_keys is None or mesh.shape_keys==source.data.shape_keys)):
        raise ValueError("corrective_glb_duplicate_mesh_or_key_not_independent")
    if mesh.shape_keys:
        owned["keys"].add(int(mesh.shape_keys.as_pointer()))
    if shape_values(mesh.shape_keys)!=shape_values(source.data.shape_keys):
        raise ValueError("corrective_glb_copied_key_values_differ")
    if mesh.attributes.get(TAG):
        raise ValueError("corrective_glb_point_id_attribute_collision")
    attribute=mesh.attributes.new(name=TAG,type="INT",domain="POINT")
    for i,value in enumerate(attribute.data):
        value.value=i+1
    for modifier in list(duplicate.modifiers)[1:]:
        duplicate.modifiers.remove(modifier)
    duplicate.name="COOP_GLB_STAGE_"+source.name
    duplicate.hide_render=True
    duplicate.hide_viewport=False
    bpy.context.scene.collection.objects.link(duplicate)
    duplicate.hide_set(False)
    return duplicate

def cleanup(bpy,owned,original):
    old_objects={p for n,p in original["objects"]}
    old_meshes={p for n,p in original["meshes"]}
    old_keys={p for n,p in original["shape_keys"]}
    for obj in reversed(owned["objects"]):
        if int(obj.as_pointer()) in old_objects:
            raise ValueError("corrective_glb_cleanup_original_object_refused")
        bpy.data.objects.remove(obj,do_unlink=True)
    for mesh in reversed(owned["meshes"]):
        if int(mesh.as_pointer()) in old_meshes:
            raise ValueError("corrective_glb_cleanup_original_mesh_refused")
        bpy.data.meshes.remove(mesh,do_unlink=True)
    for key in list(bpy.data.shape_keys):
        pointer=int(key.as_pointer())
        if pointer in owned["keys"] and pointer not in old_keys:
            key.use_fake_user=False
            if key.users!=0:
                raise ValueError("corrective_glb_owned_key_still_used")
            bpy.data.batch_remove(ids=[key])


def positive_groups(vertex,group_names,rig):
    records=[]
    for entry in vertex.groups:
        weight=float(entry.weight)
        if not math.isfinite(weight) or weight<0 or entry.group not in group_names:
            raise ValueError("corrective_glb_source_weight_invalid")
        if weight==0:
            continue
        name=group_names[entry.group]
        bone=rig.data.bones.get(name)
        exists=bone is not None
        use_deform=bool(bone.use_deform) if exists else False
        records.append((int(entry.group),name,weight,exists and use_deform,exists,use_deform))
    return sorted(records)

def raw_membership(obj,rig):
    names={g.index:g.name for g in obj.vertex_groups}
    return [positive_groups(vertex,names,rig) for vertex in obj.data.vertices]

def classify_membership(weights):
    sums=[sum(row[2] for row in records if row[3]) for records in weights]
    if not all(math.isfinite(value) and value>=0 for value in sums):
        raise ValueError("corrective_glb_native_eligible_sum_invalid")
    zero=[i+1 for i,value in enumerate(sums) if value==0]
    tiny=[i+1 for i,value in enumerate(sums) if 0<value<=0.0001]
    payload={"source_point_ids":list(range(1,len(weights)+1)),"positive_groups":weights,"eligible_sums":sums}
    return {"sha256":digest(payload),"zero_ids":zero,"tiny_ids":tiny,"eligible_sums":sums,
        "positive_records":sum(len(row) for row in weights)}

def membership_examples(weights,classification,ids):
    return [{"source_point_id":i,"positive_group_records":weights[i-1],
        "eligible_sum":classification["eligible_sums"][i-1]} for i in ids[:16]]

def ids_hash(ids):
    return hashlib.sha256(np.asarray(ids,dtype="<u4").tobytes()).hexdigest()

def prepare_membership(sources,duplicates,pre_body,rig,bind,out,audit):
    baselines=[]
    audit["native_binding_correspondence"]=[]
    for i,(source,duplicate,mesh) in enumerate(zip(sources,duplicates,bind)):
        raw=raw_membership(source,rig)
        clone=raw_membership(duplicate,rig)
        evaluated=mesh["weights"]
        raw_info,clone_info,eval_info=[classify_membership(rows) for rows in (raw,clone,evaluated)]
        report={"mesh_index":i,"mesh":source.name,"vertex_count":len(raw),
            "raw_source_sha256":raw_info["sha256"],"raw_clone_sha256":clone_info["sha256"],
            "evaluated_sha256":eval_info["sha256"],"raw_positive_records":raw_info["positive_records"],
            "raw_clone_positive_records":clone_info["positive_records"],"evaluated_positive_records":eval_info["positive_records"],
            "zero_eligible_count":len(raw_info["zero_ids"]),"zero_ids_sha256":ids_hash(raw_info["zero_ids"]),
            "zero_ids_first":raw_info["zero_ids"][:16],"tiny_positive_count":len(raw_info["tiny_ids"]),
            "tiny_ids_first":raw_info["tiny_ids"][:16],"correspondence_pose_count":0,
            "full_membership_compared":True,"correspondence_passed":raw==clone==evaluated,
            "examples":{"raw_source":membership_examples(raw,raw_info,list(range(1,len(raw)+1))),
                "raw_clone":membership_examples(clone,clone_info,list(range(1,len(raw)+1))),
                "evaluated":membership_examples(evaluated,eval_info,list(range(1,len(raw)+1)))}}
        audit["native_binding_correspondence"].append(report)
        if raw!=clone or raw!=evaluated:
            bad=[j+1 for j,(a,b,c) in enumerate(zip(raw,clone,evaluated)) if a!=b or a!=c][:16]
            report["offending_point_ids_first"]=bad
            report["offending_examples"]={"raw_source":membership_examples(raw,raw_info,bad),
                "raw_clone":membership_examples(clone,clone_info,bad),
                "evaluated":membership_examples(evaluated,eval_info,bad)}
            checkpoint(out,audit)
            raise ValueError("corrective_glb_raw_clone_evaluated_membership_mismatch")
        if raw_info["tiny_ids"]:
            report["tiny_positive_examples"]=membership_examples(raw,raw_info,raw_info["tiny_ids"])
            checkpoint(out,audit)
            raise ValueError("corrective_glb_tiny_positive_native_binding_unsupported")
        if i==0:
            pre_raw=raw_membership(pre_body,rig)
            report["pre_armature_raw_clone_sha256"]=classify_membership(pre_raw)["sha256"]
            if pre_raw!=raw:
                checkpoint(out,audit)
                raise ValueError("corrective_glb_pre_armature_raw_membership_mismatch")
        baselines.append({"weights":raw,"classification":raw_info})
    if baselines[1]["classification"]["zero_ids"]:
        checkpoint(out,audit)
        raise ValueError("corrective_glb_non_body_zero_binding_unproved")
    checkpoint(out,audit)
    return baselines

def verify_membership_pose(current,baseline,report,out,audit):
    weights=current["weights"]
    info=classify_membership(weights)
    if weights!=baseline["weights"] or info["tiny_ids"] or info["zero_ids"]!=baseline["classification"]["zero_ids"]:
        report["correspondence_passed"]=False
        report["evaluated_sha256"]=info["sha256"]
        bad=[i+1 for i,(a,b) in enumerate(zip(baseline["weights"],weights)) if a!=b][:16]
        report["offending_point_ids_first"]=bad
        report["offending_evaluated_first"]=membership_examples(weights,info,bad)
        checkpoint(out,audit)
        raise ValueError("corrective_glb_native_membership_changed_during_pose")
    report["correspondence_pose_count"]+=1
    report["evaluated_sha256"]=info["sha256"]


def snapshot(bpy,duplicate,source,rig,C,triangles=False):
    if len(source.data.vertices)!=len(duplicate.data.vertices):
        raise ValueError("corrective_glb_duplicate_vertex_count_changed")
    a,b=shape_values(source.data.shape_keys),shape_values(duplicate.data.shape_keys)
    if len(a)!=len(b) or any(x[0]!=y[0] or abs(x[1]-y[1])>1e-6 for x,y in zip(a,b)):
        raise ValueError("corrective_glb_duplicate_native_key_response_mismatch")
    dg=bpy.context.evaluated_depsgraph_get()
    evaluated=duplicate.evaluated_get(dg)
    mesh=None
    try:
        mesh=evaluated.to_mesh(preserve_all_data_layers=True,depsgraph=dg)
        attr=mesh.attributes.get(TAG)
        n=len(source.data.vertices)
        if attr is None or attr.data_type!="INT" or attr.domain!="POINT":
            raise ValueError("corrective_glb_point_identity_attribute_lost")
        ids=[int(v.value) for v in attr.data]
        if len(ids)!=n or len(mesh.vertices)!=n or len(set(ids))!=n or set(ids)!=set(range(1,n+1)):
            raise ValueError("corrective_glb_armature_point_identity_not_one_to_one")
        matrix=np.array(evaluated.matrix_world,dtype=np.float64)
        require_finite(matrix)
        positions=np.empty((n,3),dtype=np.float64)
        full_weights=[None]*n
        group_names={g.index:g.name for g in duplicate.vertex_groups}
        for vertex in mesh.vertices:
            pid=ids[vertex.index]-1
            co=np.array((*vertex.co,1.0),dtype=np.float64)
            positions[pid]=(C@matrix@co)[:3]
            full_weights[pid]=positive_groups(vertex,group_names,rig)
        polygons=[([ids[v] for v in p.vertices],int(p.material_index)) for p in mesh.polygons]
        edges=[sorted(ids[v] for v in e.vertices) for e in mesh.edges]
        uv=[{"name":layer.name,"values":[list(item.uv) for item in layer.data]} for layer in mesh.uv_layers]
        signature=digest({"polygons":polygons,"edges":edges,"uv":uv,"full_positive_weights":full_weights})
        indices=None
        if triangles:
            mesh.calc_loop_triangles()
            indices=np.array([[ids[i]-1 for i in triangle.vertices] for triangle in mesh.loop_triangles],dtype=np.uint32).reshape(-1)
        return {"positions":require_finite(positions),"signature":signature,"weights":full_weights,
            "indices":indices,"source_point_ids":list(range(1,n+1)),"matrix_world":matrix.tolist()}
    finally:
        if mesh is not None:
            evaluated.to_mesh_clear()

def bind_palette(rig,meshes,audit,out):
    needed=set()
    weighted=set()
    for mesh in meshes:
        for weights in mesh["weights"]:
            eligible=[r for r in weights if r[3]]
            if not eligible:
                continue  # No helper yet: true-zero classification and 159-pose proof are still pending.
            for group,name,weight,deform,*classification in eligible:
                weighted.add(name)
                bone=rig.data.bones[name]
                while bone is not None:
                    needed.add(bone.name)
                    bone=bone.parent
    def depth(name):
        count=0
        bone=rig.data.bones[name].parent
        while bone:
            count+=1
            bone=bone.parent
        return count
    flags=[{"bone":name,"use_deform":bool(rig.data.bones[name].use_deform),
        "envelope_multiply":bool(rig.data.bones[name].use_envelope_multiply),
        "segments":int(rig.data.bones[name].bbone_segments)} for name in sorted(weighted)]
    audit["actual_eligible_weighted_bone_flags"]=flags
    checkpoint(out,audit)
    if any(item["envelope_multiply"] for item in flags):
        raise ValueError("corrective_glb_weighted_bone_envelope_multiply_unsupported")
    names=sorted(needed,key=lambda name:(depth(name),name))
    index={name:i for i,name in enumerate(names)}
    parents=[index[rig.data.bones[name].parent.name] if rig.data.bones[name].parent else -1 for name in names]
    return names,parents

def native_joint_world(bpy,rig,names,C):
    if AUXILIARY_NAME in names:
        raise ValueError("corrective_glb_auxiliary_not_native_bone_lookup")
    evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    world=np.array(evaluated.matrix_world,dtype=np.float64)
    return require_finite(np.array([C@world@np.array(evaluated.pose.bones[name].matrix,dtype=np.float64) for name in names]))

def quaternion_matrix(q):
    q=np.array(q,dtype=np.float64)
    norm=float(np.linalg.norm(q))
    if not math.isfinite(norm) or abs(norm-1)>1e-5:
        raise ValueError("corrective_glb_serialized_quaternion_not_unit")
    x,y,z,w=q/norm
    return np.array(((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
        (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
        (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y))),dtype=np.float64)

def compose(t,q,s):
    result=np.eye(4,dtype=np.float64)
    result[:3,:3]=quaternion_matrix(q)*np.array(s,dtype=np.float64)[None,:]
    result[:3,3]=t
    return require_finite(result)

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
        error=float(np.max(np.abs(compose(translation[i],rotation[i],scale[i])-local)))
        local_error=max(local_error,error)
        if error>TRS_TOL:
            if audit is not None:
                audit["joint_trs_failure"]={"row":row,"joint_index":i,"maximum_local_error":error,
                    "native_local_matrix":local.tolist(),"stored_translation":translation[i].tolist(),
                    "stored_rotation":rotation[i].tolist(),"stored_scale":scale[i].tolist()}
                checkpoint(out,audit)
            raise ValueError("corrective_glb_joint_trs_recomposition_or_shear_unsupported")
    return translation,rotation,scale,local_error

def world_from_trs(t,r,s,parents):
    world=np.empty((len(parents),4,4),dtype=np.float64)
    for i,parent in enumerate(parents):
        local=compose(t[i],r[i],s[i])
        world[i]=local if parent<0 else world[parent]@local
    return require_finite(world)

def serialized_weights(mesh,names,zero_ids=(),helper_index=None):
    zero_ids=set(zero_ids)
    bone_indices={name:i for i,name in enumerate(names)}
    maximum=max(1,max(sum(1 for r in weights if r[3]) for weights in mesh["weights"]))
    sets=(maximum+3)//4
    joints=np.zeros((len(mesh["weights"]),sets*4),dtype=np.uint16)
    weights=np.zeros((len(mesh["weights"]),sets*4),dtype=np.float32)
    for i,full in enumerate(mesh["weights"]):
        eligible=[r for r in full if r[3]]
        total=sum(r[2] for r in eligible)
        if total<=0:
            if total==0 and i+1 in zero_ids and helper_index is not None:
                joints[i,0]=helper_index
                weights[i,0]=1.0
                continue
            raise ValueError("corrective_glb_zero_vertex_identity_proof_missing")
        for column,record in enumerate(eligible):
            group,name,weight,deform=record[:4]
            joints[i,column]=bone_indices[name]
            weights[i,column]=weight/total
            if weights[i,column]<=0:
                raise ValueError("corrective_glb_positive_weight_underflow_unsupported")
    if len(names)>65535 or np.max(np.abs(weights.astype(np.float64).sum(axis=1)-1))>1e-5:
        raise ValueError("corrective_glb_serialized_weight_or_joint_limit_invalid")
    return joints,weights,sets

class GLBBuffer:
    def __init__(self):
        self.data=bytearray()
        self.views=[]
        self.accessors=[]
    def add(self,array,kind,component=5126,target=None,bounds=False):
        dtype={5126:"<f4",5123:"<u2",5125:"<u4"}[component]
        values=np.ascontiguousarray(array,dtype=dtype)
        if not np.isfinite(values).all():
            raise ValueError("corrective_glb_buffer_nonfinite")
        while len(self.data)%4:
            self.data.append(0)
        raw=values.tobytes()
        if len(self.data)+len(raw)>CAP:
            raise ValueError("corrective_glb_binary_size_cap_exceeded")
        view={"buffer":0,"byteOffset":len(self.data),"byteLength":len(raw)}
        if target is not None:
            view["target"]=target
        self.views.append(view)
        self.data.extend(raw)
        accessor={"bufferView":len(self.views)-1,"componentType":component,"count":int(values.shape[0]),"type":kind}
        if bounds:
            accessor["min"]=values.min(axis=0).reshape(-1).astype(float).tolist()
            accessor["max"]=values.max(axis=0).reshape(-1).astype(float).tolist()
        self.accessors.append(accessor)
        return len(self.accessors)-1

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
        for row in range(147):
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
            "weights":[1.0]+[0.0]*146,
            "extras":{"stage":"ARMATURE_ONLY","source_uv_checked_but_not_exported":True,
                "normals_not_exported":True,"all_positive_eligible_influences_retained":True}})
        audit.setdefault("corrective_solve",{})[MESH_NAMES[mesh_index]]={"frame_count":147,
            "maximum_condition":max(r["maximum_condition"] for r in frame_stats),
            "maximum_quantized_writer_error":max(r["maximum_quantized_writer_error"] for r in frame_stats)}
    animations=[]
    for clip_index,clip in enumerate(CLIPS):
        offset=clip_index*49
        time=writer.add(np.arange(49,dtype=np.float32)/np.float32(24),"SCALAR",bounds=True)
        samplers=[]
        channels=[]
        for joint in range(joint_count):
            for path,key,kind in (("translation","translation","VEC3"),("rotation","rotation","VEC4"),("scale","scale","VEC3")):
                output=writer.add(trs[key][offset:offset+49,joint],kind)
                samplers.append({"input":time,"output":output,"interpolation":"LINEAR"})
                channels.append({"sampler":len(samplers)-1,"target":{"node":joint,"path":path}})
        morph_weights=np.zeros((49,147),dtype=np.float32)
        morph_weights[np.arange(49),offset+np.arange(49)]=1.0
        output=writer.add(morph_weights.reshape(-1),"SCALAR")
        samplers.append({"input":time,"output":output,"interpolation":"LINEAR"})
        for node in mesh_nodes:
            channels.append({"sampler":len(samplers)-1,"target":{"node":node,"path":"weights"}})
        animations.append({"name":clip,"samplers":samplers,"channels":channels})
    attribution=(out/"credits/snow/ATTRIBUTION.txt").read_text(encoding="utf-8").strip()
    if len(attribution.encode())>16384:
        raise ValueError("corrective_glb_attribution_byte_budget_exceeded")
    gltf={"asset":{"version":"2.0","copyright":attribution,"generator":"Coop native Armature-stage corrective prototype",
        "extras":{"coop_corrective_contract":"coop-armature-correctives-v1","appearance_approved":False,
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
    file=out/"snow-armature-correctives-prototype.glb"
    with file.open("xb") as handle:
        handle.write(struct.pack("<III",0x46546C67,2,total))
        handle.write(struct.pack("<II",len(raw),0x4E4F534A));handle.write(raw)
        handle.write(struct.pack("<II",len(binary),0x004E4942));handle.write(binary)
    audit["glb_written"]={"file":file.name,"bytes":file.stat().st_size,"sha256":sha(file)}
    audit["maximum_skin_condition"]=maximum_condition
    audit["maximum_quantized_writer_residual"]=maximum_writer_residual
    checkpoint(out,audit)
    return mesh_nodes

def select_pose(bpy,native,proof,rig,producer,clip,frame):
    descriptor=producer["clips"][clip]["action_descriptor"]
    action=bpy.data.actions.get(descriptor["action"])
    if action is None:
        raise ValueError("corrective_glb_native_action_missing")
    slots=[slot for slot in action.slots if slot.identifier==descriptor["slot_identifier"]]
    if len(slots)!=1:
        raise ValueError("corrective_glb_native_slot_missing")
    if native.curve_descriptor(action,slots[0],native.channel_paths(proof,rig),True)!=descriptor:
        raise ValueError("corrective_glb_native_action_data_mismatch")
    native.assign_action(rig,action,slots[0])
    integer=math.floor(frame)
    bpy.context.scene.frame_set(integer,subframe=float(frame-integer))
    bpy.context.view_layer.update()

def collect_and_write(bpy,native,natural,face,proof,soft,pair,helper,rig,sources,duplicates,pre_body,producer,C,out,audit):
    select_pose(bpy,native,proof,rig,producer,"idle",0)
    held=native.held_face_state(proof,rig)
    bind=[snapshot(bpy,d,s,rig,C,triangles=True) for d,s in zip(duplicates,sources)]
    audit["bind_mesh_inventory"]=[{"mesh":MESH_NAMES[i],"vertices":len(mesh["positions"]),
        "source_mapping_signature":mesh["signature"],
        "maximum_positive_eligible_weights":max(sum(1 for item in row if item[3]) for row in mesh["weights"]),
        "unweighted_vertices":sum(not any(item[3] for item in row) for row in mesh["weights"])} for i,mesh in enumerate(bind)]
    checkpoint(out,audit)
    memberships=prepare_membership(sources,duplicates,pre_body,rig,bind,out,audit)
    if len(memberships[0]["classification"]["zero_ids"])!=EXPECTED_BODY_ZERO_COUNT:
        checkpoint(out,audit)
        raise ValueError("corrective_glb_pinned_body_zero_count_mismatch")
    names,parents=bind_palette(rig,bind,audit,out)
    if not names:
        raise ValueError("corrective_glb_empty_actual_bone_palette")
    native_joint_count=len(names)
    if AUXILIARY_NAME in names or AUXILIARY_NAME in rig.pose.bones:
        raise ValueError("corrective_glb_auxiliary_joint_name_collision")
    provisional_sets=[max(1,(max(sum(1 for r in row if r[3]) for row in mesh["weights"])+3)//4) for mesh in bind]
    estimated_weight_bytes=sum(len(mesh["positions"])*sets*4*6 for mesh,sets in zip(bind,provisional_sets))
    vertices=sum(len(mesh["positions"]) for mesh in bind)
    targets_bytes=vertices*147*3*4
    estimate=(targets_bytes+vertices*3*4+sum(mesh["indices"].nbytes for mesh in bind)
        +estimated_weight_bytes
        +(native_joint_count+1)*16*4+(native_joint_count+1)*147*10*4+3*49*147*4+3*49*4+2097152+4096)
    audit["preflight"]={"body_shirt_vertices":vertices,"joint_palette_count_with_pending_identity":native_joint_count+1,
        "position_target_count":147,"position_target_bytes":targets_bytes,"conservative_glb_bytes":estimate,
        "cap_bytes":CAP,"preflight_before_target_or_reference_allocation":True,"influence_set_counts":provisional_sets}
    checkpoint(out,audit)
    if estimate>CAP:
        raise ValueError("corrective_glb_preflight_size_cap_exceeded")
    positions=[np.empty((147,len(mesh["positions"]),3),dtype=np.float64) for mesh in bind]
    fractional_positions=[np.empty((12,len(mesh["positions"]),3),dtype=np.float64) for mesh in bind]
    joint_world=np.empty((147,len(names),4,4),dtype=np.float64)
    fractional_joint_world=np.empty((12,len(names),4,4),dtype=np.float64)
    frame_map=[]
    fractional_map=[]
    maximum_face_drift=0.0
    zero_ids=memberships[0]["classification"]["zero_ids"]
    zero_indices=np.asarray(zero_ids,dtype=np.int64)-1
    zero_rows=[]
    zero_maximum=0.0
    for fractional in (False,True):
        samples=FRACTIONAL if fractional else FRAMES
        for clip_index,clip in enumerate(CLIPS):
            for sample_index,frame in enumerate(samples):
                row=clip_index*len(samples)+sample_index
                audit["active_sample"]={"clip":clip,"frame":frame,"row":row,
                    "phase":"fractional_native_reference" if fractional else "authored_native_reference"}
                select_pose(bpy,native,proof,rig,producer,clip,frame)
                body_current=None
                for i,(duplicate,source) in enumerate(zip(duplicates,sources)):
                    current=snapshot(bpy,duplicate,source,rig,C)
                    verify_membership_pose(current,memberships[i],audit["native_binding_correspondence"][i],out,audit)
                    if current["signature"]!=bind[i]["signature"]:
                        raise ValueError("corrective_glb_ids_uv_topology_material_or_full_weights_changed")
                    destination=fractional_positions[i] if fractional else positions[i]
                    destination[row]=current["positions"].copy()
                    if i==0:
                        body_current=current
                pre_current=snapshot(bpy,pre_body,sources[0],rig,C)
                weights_equal=pre_current["weights"]==memberships[0]["weights"]
                signature_equal=pre_current["signature"]==bind[0]["signature"]
                pre_matrix=np.asarray(pre_current["matrix_world"])
                native_matrix=np.asarray(body_current["matrix_world"])
                source_matrix=np.asarray(sources[0].matrix_world)
                maxpre_vs_native_matrix_error=float(np.max(np.abs(pre_matrix-native_matrix)))
                maxpre_vs_source_matrix_error=float(np.max(np.abs(pre_matrix-source_matrix)))
                if (not weights_equal or not signature_equal or maxpre_vs_native_matrix_error>1e-12
                        or maxpre_vs_source_matrix_error>1e-12):
                    audit["pre_armature_input_failure"]={"clip":clip,"frame":frame,"row":row,
                        "weights_equal":weights_equal,"signature_equal":signature_equal,
                        "maxpre_vs_native_matrix_error":maxpre_vs_native_matrix_error,
                        "maxpre_vs_source_matrix_error":maxpre_vs_source_matrix_error,
                        "pre_armature_matrix_world":pre_matrix.tolist(),
                        "native_armature_matrix_world":native_matrix.tolist(),
                        "source_matrix_world":source_matrix.tolist()}
                    checkpoint(out,audit)
                    raise ValueError("corrective_glb_pre_armature_identity_input_mismatch")
                errors=np.linalg.norm(body_current["positions"][zero_indices]-pre_current["positions"][zero_indices],axis=1)
                require_finite(errors)
                worst=float(np.max(errors))
                zero_maximum=max(zero_maximum,worst)
                zero_rows.append({"clip":clip,"frame":frame,"row":row,"fractional":fractional,
                    "zero_eligible_count":len(zero_ids),"maximum_world_error":worst,"membership_passed":True})
                audit["zero_pre_armature_rows"]=zero_rows
                if worst>1e-6:
                    point=int(np.argmax(errors))
                    pid=zero_ids[point]
                    audit["zero_pre_armature_failure"]={"clip":clip,"frame":frame,"source_point_id":pid,
                        "maximum_world_error":worst,"native_armature_world":body_current["positions"][pid-1].tolist(),
                        "pre_armature_current_input_world":pre_current["positions"][pid-1].tolist(),
                        "positive_group_records":memberships[0]["weights"][pid-1]}
                    checkpoint(out,audit)
                    raise ValueError("corrective_glb_true_zero_armature_effect_not_identity")
                actual=native_joint_world(bpy,rig,names,C)
                if fractional:
                    fractional_joint_world[row]=actual.copy()
                else:
                    joint_world[row]=actual.copy()
                current_face=native.held_face_state(proof,rig)
                if current_face["channels"]!=held["channels"]:
                    raise ValueError("corrective_glb_held_face_channels_changed")
                drift=max(abs(current_face["properties"][side][kind]-held["properties"][side][kind])
                    for side in ("L","R") for kind in ("Up","Wide"))
                maximum_face_drift=max(maximum_face_drift,drift)
                if (not math.isfinite(drift) or drift>1e-4
                        or np.max(np.abs(np.array(current_face["jaw_matrix"])-np.array(held["jaw_matrix"])))>1e-6):
                    raise ValueError("corrective_glb_held_face_or_jaw_changed")
                if soft.driver_summary(helper,bpy)["active_invalid"]!=0:
                    raise ValueError("corrective_glb_temporary_or_input_driver_invalid")
                proof.key_values(bpy)
                record={"row":row,"clip":clip,"frame":frame,"time":frame/24}
                (fractional_map if fractional else frame_map).append(record)
            checkpoint(out,audit)
    if len(zero_rows)!=159 or any(report["correspondence_pose_count"]!=159 for report in audit["native_binding_correspondence"]):
        raise ValueError("corrective_glb_zero_binding_pose_proof_incomplete")
    # Only after the complete native membership+pre-Armature proof may ONE export-only identity joint exist.
    helper_index=native_joint_count
    identity_proof={"schema":"coop-armature-zero-identity-v1","joint_index":helper_index,
        "membership":{"raw_source_raw_clone_evaluated_equal":True,"full_membership_compared":True,"poses_checked":159},
        "pre_armature":{"poses_checked":159,"tolerance_world_m":1e-6,"maximum_world_error":zero_maximum,
            "all_zero_eligible_vertices_compared":True},
        "meshes":[{"index":i,"source_point_ids":membership["classification"]["zero_ids"],
            "zero_eligible_count":len(membership["classification"]["zero_ids"]),
            "ids_sha256":ids_hash(membership["classification"]["zero_ids"]),"ids_hash_encoding":"uint32_le",
            "raw_source_sha256":audit["native_binding_correspondence"][i]["raw_source_sha256"],
            "raw_clone_sha256":audit["native_binding_correspondence"][i]["raw_clone_sha256"],
            "evaluated_sha256":audit["native_binding_correspondence"][i]["evaluated_sha256"]} for i,membership in enumerate(memberships)]}
    audit["identity_proof_summary"]={"joint_index":helper_index,"native_joint_count":native_joint_count,
        "poses_checked":159,"zero_count":len(zero_ids),"ids_sha256":ids_hash(zero_ids),
        "maximum_pre_armature_world_error":zero_maximum,"membership_passed":True}
    names=list(names)+[AUXILIARY_NAME]
    parents=list(parents)+[-1]
    joint_world=np.concatenate((joint_world,np.repeat(np.eye(4)[None,None,:,:],147,axis=0)),axis=1)
    fractional_joint_world=np.concatenate((fractional_joint_world,np.repeat(np.eye(4)[None,None,:,:],12,axis=0)),axis=1)
    serialized=[serialized_weights(mesh,names,membership["classification"]["zero_ids"],helper_index)
        for mesh,membership in zip(bind,memberships)]
    joint_arrays=[item[0] for item in serialized]
    weight_arrays=[item[1] for item in serialized]
    # Immutable native references are saved/hash-anchored BEFORE any TRS reconstruction or corrective solve.
    npz_path=out/"native_reference.npz"
    with npz_path.open("xb") as file:
        np.savez_compressed(file,mesh0_positions=positions[0],mesh1_positions=positions[1],
            mesh0_fractional_positions=fractional_positions[0],mesh1_fractional_positions=fractional_positions[1],
            joint_world=joint_world,fractional_joint_world=fractional_joint_world)
    for array in (*positions,*fractional_positions,joint_world,fractional_joint_world):
        array.flags.writeable=False
    npz_hash=sha(npz_path)
    metadata={"schema_version":1,"schema":"coop-avatar-corrective-reference-v1",
        "coordinate_system":"RH_Y_UP_METERS","axis_conversion":"BLENDER_Z_UP_TO_GLTF_Y_UP_X_Z_NEGY",
        "stage":"ARMATURE_ONLY","position_space":"MESH_LOCAL_IDENTITY_WORLD",
        "authored_tolerance_world_m":0.0001,"fractional_tolerance_world_m":0.001,
        "joint_matrix_tolerance":0.0001,"fractional_joint_matrix_tolerance":0.001,
        "local_trs_recompose_tolerance":TRS_TOL,"skin_condition_cap":CONDITION_CAP,
        "source_sha256":SOURCE_SHA,"candidate_sha256":INPUT_SHA,"fps":24,
        "reference_npz_sha256":npz_hash,"reference_npz_bytes":npz_path.stat().st_size,
        "frames":frame_map,"fractional_frames":fractional_map,
        "meshes":[{"index":i,"node_name":MESH_NAMES[i]+":ArmatureStage","position_key":"mesh"+str(i)+"_positions",
            "fractional_position_key":"mesh"+str(i)+"_fractional_positions","vertex_count":len(mesh["positions"]),
            "source_point_ids":mesh["source_point_ids"]} for i,mesh in enumerate(bind)],
        "joints":[{"index":i,"node_name":name if name==AUXILIARY_NAME else "SnowJoint:"+name,
            "parent_index":parents[i],"kind":"auxiliary_identity" if name==AUXILIARY_NAME else "native"} for i,name in enumerate(names)],
        "identity_proof":identity_proof,
        "native_joint_world_key":"joint_world","fractional_joint_world_key":"fractional_joint_world",
        "native_reference_captured_before_corrective_solve":True}
    raw=encode(metadata)
    if len(raw)>1048576:
        raise ValueError("corrective_glb_reference_json_size_cap_exceeded")
    (out/"native_reference.json").write_bytes(raw)
    audit["native_reference"]={"metadata_bytes":len(raw),"metadata_sha256":sha(out/"native_reference.json"),
        "npz_bytes":npz_path.stat().st_size,"npz_sha256":npz_hash,"authored_rows":147,"fractional_rows":12,
        "captured_and_saved_before_trs_or_corrective_solve":True}
    checkpoint(out,audit)
    trs={"translation":np.empty((147,len(names),3),dtype=np.float32),
        "rotation":np.empty((147,len(names),4),dtype=np.float32),
        "scale":np.empty((147,len(names),3),dtype=np.float32)}
    world_stored=np.empty_like(joint_world)
    local_error=joint_error=translation_error=linear_error=0.0
    scale_signs=None
    for clip_index,clip in enumerate(CLIPS):
        previous=None
        for frame in FRAMES:
            row=clip_index*49+frame
            actual=joint_world[row]
            t,q,s,error=serialize_trs(actual,parents,previous,scale_signs,audit,out,row)
            if scale_signs is None:
                scale_signs=np.sign(s)
            previous=q.astype(np.float64)
            trs["translation"][row],trs["rotation"][row],trs["scale"][row]=t,q,s
            reconstructed=world_from_trs(t,q,s,parents)
            world_stored[row]=reconstructed
            discrepancy=float(np.max(np.abs(reconstructed-actual)))
            local_error=max(local_error,error)
            joint_error=max(joint_error,discrepancy)
            translation_error=max(translation_error,float(np.max(np.linalg.norm(reconstructed[:,:3,3]-actual[:,:3,3],axis=1))))
            linear_error=max(linear_error,float(np.max(np.abs(reconstructed[:,:3,:3]-actual[:,:3,:3]))))
            if discrepancy>JOINT_TOL:
                audit["joint_serialization_failure"]={"row":row,"maximum_world_matrix_error":discrepancy}
                checkpoint(out,audit)
                raise ValueError("corrective_glb_quantized_joint_world_residual_exceeded")
    audit["joint_serialization"]={"maximum_local_recompose_error":local_error,"maximum_world_matrix_error":joint_error,
        "maximum_world_translation_error":translation_error,"maximum_world_linear_element_error":linear_error,
        "maximum_face_property_drift":maximum_face_drift}
    try:
        ibm=require_finite(np.linalg.inv(world_stored[0])).astype(np.float32)
    except np.linalg.LinAlgError:
        raise ValueError("corrective_glb_bind_joint_inverse_unsupported") from None
    for i,mesh in enumerate(bind):
        mesh["bind_positions"]=positions[i][0].copy()
        mesh["native_positions"]=positions[i]
    write_glb(out,names,parents,bind,trs,world_stored,ibm,joint_arrays,weight_arrays,frame_map,audit)
    if sha(npz_path)!=npz_hash or sha(out/"native_reference.json")!=audit["native_reference"]["metadata_sha256"]:
        raise ValueError("corrective_glb_native_reference_file_modified")
    audit["native_reference_hash_recheck"]=True
    audit["writer_completed"]=True
    audit["independent_reader_passed"]=False
    audit["reader_required"]="Independent reader must read GLB bytes and native_reference files; writer residual is not independent proof."
    checkpoint(out,audit)

def restore_binding(bpy,native,rig,state):
    action=bpy.data.actions.get(state["action"])
    slots=[slot for slot in action.slots if slot.identifier==state["slot_identifier"]] if action else []
    if len(slots)!=1:
        raise ValueError("corrective_glb_original_binding_restore_unsupported")
    native.assign_action(rig,action,slots[0])
    bpy.context.scene.frame_set(state["frame"],subframe=state["subframe"])
    bpy.context.view_layer.update()

def main():
    parser=argparse.ArgumentParser()
    for field in ("source-root","derivative-blend","config","out"):
        parser.add_argument("--"+field,required=True)
    args=parser.parse_args()
    root=Path(args.source_root).resolve(strict=True)
    source=root/"snow/original/Snow/snow_v4.2.blend"
    candidate=Path(args.derivative_blend).resolve(strict=True)
    producer_file=candidate.with_name("native-clips-audit.json")
    out=Path(args.out).resolve()
    if out.is_relative_to(root) or out.is_relative_to(candidate.parent) or source.is_relative_to(out) or candidate.is_relative_to(out):
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
    audit={"purpose":"Actual POSITION-only BODY+SHIRT Armature-stage native-clip corrective GLB prototype",
        "source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"producer_sha256":sha(producer_file),
        "producer_parent_input_sha256":PARENT_SHA,"native_functions_blob":NATIVE_BLOB,"credits":credits,
        "used_textures":[],"renders":0,"models_saved":0,"source_geometry_edits":False,"source_driver_mute_or_detach":False,
        "writer_completed":False,"independent_reader_passed":False,"overall_art_approved":False,
        "browser_animation_approved":False,"production_glb_approved":False,
        "limits":["Armature-stage only: downstream CorrectiveSmooth/Mask/Subdivision/render-DG not exported or accepted.",
            "All eligible positive influences retained in JOINTS_n/WEIGHTS_n; no four-weight adapter or pruning.",
            "147 native authored and 12 fractional references captured BEFORE TRS or corrective solve.",
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
            "producer":sha(producer_file)==audit["producer_sha256"]}
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
        pre_body=copy_stage(bpy,sources[0],rig,owned,audit,out)
        pre_body.name="COOP_GLB_PRE_ARMATURE_BODY"
        for modifier in list(pre_body.modifiers):
            pre_body.modifiers.remove(modifier)
        bpy.context.view_layer.update()
        if helper.garment_geometry_signature(pre_body)!=helper.garment_geometry_signature(sources[0]):
            raise ValueError("corrective_glb_pre_armature_raw_or_key_data_differs")
        audit["pre_armature_copy"]={"owned_independent_mesh_and_key":True,"modifier_count":len(pre_body.modifiers),
            "source_coordinate_key_data_equal":True,"original_modifiers_edited":False}
        for duplicate,source_obj in zip(duplicates,sources):
            if helper.garment_geometry_signature(duplicate)!=helper.garment_geometry_signature(source_obj):
                raise ValueError("corrective_glb_copied_raw_or_key_data_differs")
        C=np.array(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)),dtype=np.float64)
        collect_and_write(bpy,native,natural,face,proof,soft,pair,helper,rig,sources,duplicates,pre_body,producer,C,out,audit)
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
