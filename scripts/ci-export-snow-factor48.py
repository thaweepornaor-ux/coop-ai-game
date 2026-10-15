#!/usr/bin/env python3
"""One offline factorized-TRS corrective GLB candidate from immutable native keys.

No bpy, mathutils, native rig editing or fractional validation data are used
to choose the encoding. An independent process reads the resulting GLB.
"""
import argparse, hashlib, json, math, shutil, struct, sys, zipfile
from pathlib import Path
import numpy as np
CAP=32*1024*1024
MAX_JSON=1048576
TRS_TOL=1e-5
JOINT_TOL=1e-4
CONDITION_CAP=1e6
CLIPS=("idle","wave","celebrate")
CONTRACT="coop-armature-factor-correctives-48hz-v1"
OUTPUT_NAME="snow-armature-factor48-prototype.glb"
CREDITS=("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt")
SOURCE_PINS={
 "source.glb":(15845580,"4a91efd3b9e69e0549180b0b1c348ef35effc0b13ab561909ee5b8ebb1215f90"),
 "source-writer-audit.json":(31022,"1878e544b4e5c263a0cdfbf9f9c786effe3dfe5bb1766fd1b401a72073f1347e"),
 "source-reader-audit.json":(121100,"946bf478b943609170e458983f215e90dc250b4cd2769bb3468076b19f68d150")}
REFERENCE_PINS={
 "native_reference.npz":(31443671,"6dca400a201b003e7ed81c8556d06cfa5afde07edad30705e2bf22ee487d9f94"),
 "native_reference.json":(143763,"83471e5eb420f716ef024b04e660ba29ba975f6e13a52835f65498c964fecb9d"),
 "glb-correctives-audit.json":(110470,"3a3e7016883e6998180ece3a24f7efecfc06f50b202890265aa59aa4af372fa7")}
WIDTH={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}
DTYPE={5123:"<u2",5125:"<u4",5126:"<f4"}

def check(value,code):
    if not value:
        raise ValueError("factor48_"+code)
def require_finite(value):
    check(np.isfinite(value).all(),"nonfinite")
    return value
def encode(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode("utf-8")
def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()
def checkpoint(out,audit):
    raw=encode(audit)
    check(len(raw)<=MAX_JSON,"audit_budget")
    (out/"glb-correctives-audit.json").write_bytes(raw)
def read_json(path):
    check(0<path.stat().st_size<=MAX_JSON,"json_budget")
    return json.loads(path.read_text("utf-8"))
def pin(root,expected):
    result={}
    for name,(size,digest) in expected.items():
        p=root/name
        check(p.is_file() and not p.is_symlink() and p.stat().st_size==size,"input_file_size")
        check(p.stat().st_mode&0o222==0 and sha(p)==digest,"input_readonly_checksum")
        result[name]={"bytes":size,"sha256":digest}
    return result

def read_glb(path):
    raw=path.read_bytes()
    check(20<=len(raw)<=CAP and struct.unpack_from("<III",raw)==(0x46546c67,2,len(raw)),"source_glb_header")
    chunks=[]; at=12
    while at<len(raw):
        check(at+8<=len(raw),"source_chunk_header")
        length,kind=struct.unpack_from("<II",raw,at);at+=8
        check(length%4==0 and at+length<=len(raw),"source_chunk_bounds")
        chunks.append((kind,raw[at:at+length]));at+=length
    check([x[0] for x in chunks]==[0x4e4f534a,0x004e4942],"source_chunks")
    doc=json.loads(chunks[0][1].decode("utf-8"))
    check(doc["asset"]["extras"]["coop_corrective_contract"]=="coop-armature-correctives-v1","source_contract")
    check(not doc.get("extensionsUsed") and len(doc["buffers"])==1 and "uri" not in doc["buffers"][0],"source_buffer")
    n=doc["buffers"][0]["byteLength"]
    check(type(n) is int and n<=len(chunks[1][1])<=n+3,"source_buffer_length")
    return doc,chunks[1][1][:n]

def source_array(doc,binary,index):
    check(type(index) is int and 0<=index<len(doc["accessors"]),"source_accessor_index")
    a=doc["accessors"][index]
    check(a["componentType"] in DTYPE and a["type"] in WIDTH
          and not a.get("normalized") and "sparse" not in a,"source_accessor_type")
    v=doc["bufferViews"][a["bufferView"]]
    check(v.get("buffer")==0 and "byteStride" not in v,"source_view")
    dtype=np.dtype(DTYPE[a["componentType"]]);count=a["count"];width=WIDTH[a["type"]]
    offset=a.get("byteOffset",0); start=v.get("byteOffset",0)+offset; size=count*width*dtype.itemsize
    check(type(count) is int and 0<count<10000000 and type(offset) is int and offset>=0
          and start%dtype.itemsize==0 and offset+size<=v["byteLength"] and start+size<=len(binary),"source_accessor_bounds")
    array=np.frombuffer(binary,dtype=dtype,count=count*width,offset=start).reshape(count,width).copy()
    return require_finite(array)

def qmatrix(q):
    q=np.asarray(q,dtype=np.float64); norm=float(np.linalg.norm(q))
    check(q.shape==(4,) and math.isfinite(norm) and norm>1e-12,"quaternion")
    x,y,z,w=q/norm
    return np.array(((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
        (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
        (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y))),dtype=np.float64)
def compose(t,q,s):
    result=np.eye(4);result[:3,:3]=qmatrix(q)*np.asarray(s,dtype=np.float64)[None,:]
    result[:3,3]=t
    return require_finite(result)
def stored_quaternion(R):
    check(np.max(np.abs(R.T@R-np.eye(3)))<=1e-10 and abs(float(np.linalg.det(R))-1)<=1e-10,"rotation_not_proper")
    tr=float(np.trace(R))
    if tr>0:
        a=2*math.sqrt(tr+1)
        q=np.array(((R[2,1]-R[1,2])/a,(R[0,2]-R[2,0])/a,(R[1,0]-R[0,1])/a,a/4))
    else:
        i=int(np.argmax(np.diag(R)))
        if i==0:
            a=2*math.sqrt(1+R[0,0]-R[1,1]-R[2,2])
            q=np.array((a/4,(R[0,1]+R[1,0])/a,(R[0,2]+R[2,0])/a,(R[2,1]-R[1,2])/a))
        elif i==1:
            a=2*math.sqrt(1+R[1,1]-R[0,0]-R[2,2])
            q=np.array(((R[0,1]+R[1,0])/a,a/4,(R[1,2]+R[2,1])/a,(R[0,2]-R[2,0])/a))
        else:
            a=2*math.sqrt(1+R[2,2]-R[0,0]-R[1,1])
            q=np.array(((R[0,2]+R[2,0])/a,(R[1,2]+R[2,1])/a,a/4,(R[1,0]-R[0,1])/a))
    q=require_finite(q);norm=float(np.linalg.norm(q))
    check(norm>1e-12,"quaternion_zero")
    return (q/norm).astype(np.float32)


def chebyshev_scale(column,target,witness,audit,out,context):
    sign=1.0 if witness>0 else -1.0
    if not math.isfinite(float(witness)) or abs(float(witness))<=1e-8:
        raise ValueError("cached_glb_scale_witness_invalid")
    coefficients=column.astype(np.float64)*sign
    target=target.astype(np.float64)
    require_finite(coefficients);require_finite(target)
    center=abs(float(witness))
    residual=coefficients*center-target
    require_finite(residual)
    radius=float(np.max(np.abs(residual)))
    check(math.isfinite(radius),"centered_scale_radius_nonfinite")
    def centered_bounds(error):
        lower,upper=1e-8-center,float("inf")
        for coefficient,value in zip(coefficients,residual):
            if coefficient==0:
                if abs(float(value))>error:
                    return lower,upper,False
                continue
            a,b=(-error-value)/coefficient,(error-value)/coefficient
            lower=max(lower,min(a,b));upper=min(upper,max(a,b))
        valid=lower<=upper and math.isfinite(lower) and math.isfinite(upper)
        return lower,upper,bool(valid)
    def old_direct_bounds(error):
        lower,upper=1e-8,float("inf")
        for coefficient,value in zip(coefficients,target):
            if coefficient==0:
                if abs(float(value))>error:
                    return lower,upper,False
                continue
            a,b=(value-error)/coefficient,(value+error)/coefficient
            lower=max(lower,min(a,b));upper=min(upper,max(a,b))
        return lower,upper,bool(lower<=upper and math.isfinite(lower) and math.isfinite(upper))
    def safe(value):
        return float(value) if math.isfinite(float(value)) else None
    old_low,old_high,old_valid=old_direct_bounds(radius)
    initial_low,initial_high,initial_valid=centered_bounds(radius)
    contains_zero=initial_valid and initial_low<=0<=initial_high
    diagnostics=audit.setdefault("scale_interval_diagnostics",{
        "policy":"uniform witness-centered magnitude offset; unchanged signed Chebyshev objective",
        "bisections":64,"calls":0,"old_initial_empty_count":0,
        "centered_initial_failure_count":0,"examples":[],"holdouts_used":False})
    diagnostics["calls"]+=1
    if not old_valid:diagnostics["old_initial_empty_count"]+=1
    if not contains_zero:diagnostics["centered_initial_failure_count"]+=1
    example=None
    if (not old_valid or not contains_zero) and len(diagnostics["examples"])<3:
        example={"context":dict(context),"coefficient":coefficients.tolist(),
            "target":target.tolist(),"witness":float(witness),"sign":sign,
            "center_magnitude":center,"center_residual":residual.tolist(),"initial_radius":radius,
            "old_direct":{"lower":safe(old_low),"upper":safe(old_high),"feasible":old_valid,
                "bounds_finite":math.isfinite(old_low) and math.isfinite(old_high)},
            "centered":{"lower":safe(initial_low),"upper":safe(initial_high),"feasible":initial_valid,
                "contains_zero":bool(contains_zero)},
            "stored_scale":None,"direct_stored_column_error":None}
        diagnostics["examples"].append(example)
        checkpoint(out,audit)
    if not contains_zero:
        raise ValueError("cached_glb_centered_scale_initial_interval_invalid")
    lower,upper=0.0,radius
    best=(initial_low,initial_high)
    for iteration in range(64):
        middle=(lower+upper)*0.5
        low,high,valid=centered_bounds(middle)
        if not valid:
            lower=middle
        else:
            upper=middle;best=(low,high)
    offset=best[0]+(best[1]-best[0])*0.5
    magnitude=center+offset
    value=np.float32(sign*magnitude)
    if example is not None:
        example["fitted_offset"]=safe(offset);example["fitted_magnitude"]=safe(magnitude)
        example["stored_scale"]=safe(value)
        example["direct_stored_column_error"]=safe(np.max(np.abs(column.astype(np.float64)*float(value)-target)))
        checkpoint(out,audit)
    if not np.isfinite(value) or abs(float(value))<=1e-8 or np.sign(value)!=sign:
        raise ValueError("cached_glb_stored_scale_invalid")
    return value

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



def ordinary(local,signs,audit,out,context):
    A=local[:3,:3]
    check(np.linalg.det(A)*float(np.prod(signs))>1e-12,"ordinary_reflection_domain")
    U,sv,Vt=np.linalg.svd(A*signs[None,:])
    check(np.min(sv)>1e-8 and np.max(sv)/np.min(sv)<=CONDITION_CAP,"ordinary_degenerate")
    q=stored_quaternion(U@Vt)
    R=qmatrix(q);s=np.empty(3,dtype=np.float32)
    for j in range(3):
        witness=float(np.dot(R[:,j],A[:,j]))
        check(abs(witness)>1e-8 and np.sign(witness)==signs[j],"ordinary_scale_domain")
        context.update({"column":j,"stored_quaternion_xyzw":q.tolist(),"stored_rotation":R.tolist()})
        s[j]=chebyshev_scale(R[:,j],A[:,j],witness,audit,out,context)
    t=local[:3,3].astype(np.float32)
    return t,q,s,float(np.max(np.abs(compose(t,q,s)-local)))

def factor_chain(local,bind_det_sign):
    A=local[:3,:3];det=float(np.linalg.det(A))
    check(math.isfinite(det) and det*bind_det_sign>1e-12,"qr_determinant_domain")
    a=A[:,0];n0=float(np.linalg.norm(a));check(n0>1e-8,"qr_first_degenerate")
    q0=a/n0;v=A[:,1]-np.dot(q0,A[:,1])*q0;n1=float(np.linalg.norm(v))
    check(n1>1e-8,"qr_second_degenerate")
    q1=v/n1;q2=np.cross(q0,q1);Q=np.column_stack((q0,q1,q2))
    R=Q.T@A
    check(np.max(np.abs(np.tril(R,-1)))<=1e-10 and np.max(np.abs(Q@R-A))<=1e-10,"qr_reconstruction")
    D=np.diag(R).copy()
    check(np.all(np.abs(D)>1e-8) and np.array_equal(np.sign(D),[1,1,bind_det_sign]),"qr_bind_scale_sign")
    t0=local[:3,3].astype(np.float32)
    factors=[(t0,stored_quaternion(Q),D.astype(np.float32))]
    x,y,z=R[0,1]/D[0],R[0,2]/D[0],R[1,2]/D[1]
    for a,b,k in ((0,1,x),(0,2,y-x*z),(1,2,z)):
        theta1=math.pi/4-.5*math.atan(k/2);theta2=-math.pi/4-.5*math.atan(k/2)
        plus=math.exp(math.asinh(k/2));minus=math.exp(-math.asinh(k/2))
        check(math.isfinite(plus) and math.isfinite(minus) and plus>1e-8 and minus>1e-8,"shear_scale_range")
        for index,theta in enumerate((theta1,theta2)):
            plane=np.eye(3);c,s=math.cos(theta),math.sin(theta)
            plane[a,a]=plane[b,b]=c;plane[a,b]=-s;plane[b,a]=s
            scale=np.ones(3)
            if index==0:
                scale[a],scale[b]=plus,minus
            factors.append((np.zeros(3,dtype=np.float32),stored_quaternion(plane),scale.astype(np.float32)))
    result=np.eye(4)
    for t,q,s in factors:
        result=result@compose(t,q,s)
    error=float(np.max(np.abs(result-local)))
    check(error<=TRS_TOL,"stored_factor_product_error")
    return factors,error

def node_worlds(t,q,s,parents):
    result=[None]*len(parents);active=set()
    def visit(i):
        if result[i] is None:
            check(i not in active,"node_cycle")
            active.add(i)
            local=compose(t[i],q[i],s[i]);p=parents[i]
            result[i]=local if p<0 else visit(p)@local
            active.remove(i)
        return result[i]
    for i in range(len(parents)):
        visit(i)
    return np.stack(result)

def extract_payload(doc,binary,ref,old,new,arrays):
    check(old["writer_completed"] is True and old["readonly_cleanup_passed"] is True
          and old["input_preservation_passed"] is True,"old_writer")
    check(new["failure"]=={"error_code":"corrective_glb_joint_trs_recomposition_or_shear_unsupported","error_type":"ValueError"}
          and all(new[k] is True for k in ("readonly_cleanup_passed","input_preservation_passed",
              "input_id_inventory_preserved","original_binding_restored")),"new_native_checkpoint")
    check(new["identity_proof_summary"]["poses_checked"]==315 and new["identity_proof_summary"]["new156_passed"] is True
          and new["overlap_sentinel"]["passed"] is True
          and new["overlap_sentinel"]["maximum_position_error"]==0
          and new["overlap_sentinel"]["maximum_joint_matrix_error"]==0,"native315_provenance")
    check(new["source_sha256"]==old["source_sha256"]==ref["source_sha256"]
          and new["input_sha256"]==old["input_sha256"]==ref["candidate_sha256"],"native_source_identity")
    check(len(ref["joints"])==187 and ref["joints"][-1]["kind"]=="auxiliary_identity"
          and ref["fps"]==24 and ref["export_sample_rate"]==48
          and ref["sampling_contract"]=="native48hz_keys291_holdouts24_v1","native_reference_contract")
    check(ref["reference_npz_sha256"]==REFERENCE_PINS["native_reference.npz"][1]
          and ref["reference_npz_bytes"]==REFERENCE_PINS["native_reference.npz"][0],"native_reference_pin")
    nodes=doc["nodes"]
    for i,j in enumerate(ref["joints"]):
        check(nodes[i]["name"]==j["node_name"],"source_native_palette_order")
    source_parents=[-1]*len(nodes)
    for i,n in enumerate(nodes):
        for c in n.get("children",[]):
            check(source_parents[c]==-1,"source_multi_parent");source_parents[c]=i
    check(source_parents[:187]==[j["parent_index"] for j in ref["joints"]],"source_native_parent_map")
    check(len(doc["meshes"])==2 and len(doc["skins"])==2,"source_two_meshes")
    meshes=[]
    for i,m in enumerate(doc["meshes"]):
        check(len(m["primitives"])==1,"source_primitive_count")
        p=m["primitives"][0];attrs=p["attributes"];count=ref["meshes"][i]["vertex_count"]
        check(p.get("mode",4)==4 and count in (5828,1839),"source_mesh_layout")
        source_skin=doc["skins"][i]
        check(source_skin["joints"]==list(range(187)),"source_skin_palette")
        keys=set(attrs);sets=2 if i==0 else 1
        check(keys=={"POSITION"}|{n+"_"+str(k) for k in range(sets) for n in ("JOINTS","WEIGHTS")},"source_all_weight_sets")
        position=source_array(doc,binary,attrs["POSITION"])
        joints=[source_array(doc,binary,attrs["JOINTS_"+str(k)]) for k in range(sets)]
        weights=[source_array(doc,binary,attrs["WEIGHTS_"+str(k)]) for k in range(sets)]
        indices=source_array(doc,binary,p["indices"]).reshape(-1)
        check(position.dtype==np.dtype("<f4") and position.shape==(count,3)
              and all(j.dtype==np.dtype("<u2") and j.shape==(count,4) for j in joints)
              and all(w.dtype==np.dtype("<f4") and w.shape==(count,4) for w in weights)
              and indices.dtype==np.dtype("<u4") and len(indices)==(34626 if i==0 else 10698),"source_payload_types")
        J=np.concatenate(joints,axis=1);W=np.concatenate(weights,axis=1)
        check(np.min(J)>=0 and np.max(J)<187 and np.min(W)>=0
              and np.max(np.abs(W.astype(np.float64).sum(axis=1)-1))<=1e-5,"source_skin_weights")
        bind_error=float(np.max(np.linalg.norm(position.astype(np.float64)-arrays["mesh"+str(i)+"_positions"][0],axis=1)))
        check(bind_error<=1e-6,"source_bind_positions")
        check(old["bind_recovery"][i]["source_mapping_signature"]==new["bind_recovery"][i]["source_mapping_signature"]
              and old["bind_recovery"][i]["membership_sha256"]==new["bind_recovery"][i]["membership_sha256"]
              and new["bind_recovery"][i]["flags"]["source_point_ids_equal"] is True,"source_binding_signatures")
        meshes.append({"name":ref["meshes"][i]["node_name"],"position":position,
            "joints":J,"weights":W,"sets":sets,"indices":indices,"bind_error":bind_error})
    return meshes

def authored_arrays(npz):
    keys=("mesh0_positions","mesh1_positions","joint_world")
    with zipfile.ZipFile(npz) as z:
        check(len(z.infolist())==6 and sum(i.file_size for i in z.infolist())<=256*1024*1024,"npz_archive_budget")
    result={}
    # Intentionally never read the three fractional/validation arrays.
    with np.load(npz,allow_pickle=False) as src:
        check(set(src.files)=={"mesh0_positions","mesh1_positions","joint_world",
             "mesh0_fractional_positions","mesh1_fractional_positions","fractional_joint_world"},"npz_keys")
        for k in keys:
            a=src[k]
            expected=(291,187,4,4) if k=="joint_world" else (291,5828 if k=="mesh0_positions" else 1839,3)
            check(a.dtype==np.dtype("<f8") and a.shape==expected,"authored_array_layout")
            result[k]=require_finite(a);a.flags.writeable=False
    return result

def build_trs(doc,ref,arrays,audit,out):
    palette=ref["joints"];native_world=arrays["joint_world"]
    local=np.empty_like(native_world)
    for row in range(291):
        for i,j in enumerate(palette):
            p=j["parent_index"]
            local[row,i]=native_world[row,i] if p<0 else np.linalg.solve(native_world[row,p],native_world[row,i])
    require_finite(local)
    check(np.max(np.abs(local[:,:,3,:]-[0,0,0,1]))<=1e-7,"native_local_not_affine")
    ts=np.empty((291,187,3),dtype=np.float32);qs=np.empty((291,187,4),dtype=np.float32);ss=np.empty_like(ts)
    selected=[];maxima=[]
    for i in range(187):
        signs=np.sign(np.asarray(doc["nodes"][i]["scale"],dtype=np.float64))
        check(np.all(np.abs(signs)==1),"old_bind_scale_sign")
        errors=[]
        for row in range(291):
            context={"row":row,"clip":ref["frames"][row]["clip"],"frame":ref["frames"][row]["frame"],
                "palette_index":i,"node_name":palette[i]["node_name"],"native_local_matrix":local[row,i].tolist()}
            try:
                ts[row,i],qs[row,i],ss[row,i],error=ordinary(local[row,i],signs,audit,out,context)
            except Exception:
                audit["active_classifier_context"]=context;checkpoint(out,audit)
                raise
            errors.append(error)
        maximum=max(errors);maxima.append(maximum)
        if maximum>TRS_TOL:
            check(i!=186,"auxiliary_factor_refused")
            selected.append(i)
        if i%24==0:
            audit["classifier_progress"]={"native_palette_index":i,"factored_indices":selected.copy()}
            checkpoint(out,audit)
    N=188+6*len(selected);common=187
    parents=[j["parent_index"] if j["parent_index"]>=0 else common for j in palette]+[-1]+[-1]*(6*len(selected))
    nodes=[{"name":j["node_name"]} for j in palette]+[{"name":"COOP_Export_CommonRoot","extras":{"coop_export_common_root":True}}]
    T=np.zeros((291,N,3),dtype=np.float32);Q=np.zeros((291,N,4),dtype=np.float32);Q[:,:,3]=1
    S=np.ones((291,N,3),dtype=np.float32);T[:,:187]=ts;Q[:,:187]=qs;S[:,:187]=ss
    nodes[186]["extras"]={"coop_joint_kind":"auxiliary_identity"}
    maximum_chain=0.0
    for order,i in enumerate(selected):
        first=188+6*order
        native_parent=palette[i]["parent_index"];parents[i]=first+5
        for stage in range(6):
            parents[first+stage]=(native_parent if native_parent>=0 else common) if stage==0 else first+stage-1
            nodes.append({"name":"COOP_Factor_"+str(i)+"_"+str(stage),
                          "extras":{"coop_affine_factor":{"native_palette_index":i,"stage":stage}}})
        nodes[i]["extras"]={"coop_native_affine_tail":i}
        sign=1 if np.linalg.det(local[0,i,:3,:3])>0 else -1
        for row in range(291):
            factors,error=factor_chain(local[row,i],sign);maximum_chain=max(maximum_chain,error)
            for stage,(t,q,s) in enumerate(factors):
                ni=i if stage==6 else first+stage
                T[row,ni],Q[row,ni],S[row,ni]=t,q,s
    # Quaternion signs are continuous inside each clip; this does not change any rotation.
    for ci in range(3):
        for k in range(1,97):
            row=ci*97+k;flip=np.sum(Q[row].astype(np.float64)*Q[row-1],axis=1)<0
            Q[row,flip]*=-1
    stored=np.empty_like(native_world);maxworld=0.0
    for row in range(291):
        world=node_worlds(T[row],Q[row],S[row],parents)
        stored[row]=world[:187]
        error=float(np.max(np.abs(stored[row]-native_world[row])));maxworld=max(maxworld,error)
        check(error<=JOINT_TOL,"native_world_residual")
    for i,n in enumerate(nodes):
        n.update({"translation":T[0,i].tolist(),"rotation":Q[0,i].tolist(),"scale":S[0,i].tolist()})
        children=[j for j,p in enumerate(parents) if p==i]
        if children:n["children"]=children
    audit["classification"]={"policy":"all291 authored keys only; ordinary polar-F32-centered-Cheb64 otherwise fixed7TRS",
        "local_tolerance":TRS_TOL,"factored_indices":selected,"ordinary_maximum_by_palette_index":maxima,
        "factor_helper_nodes":6*len(selected),"common_identity_root":common,
        "maximum_stored_factor_chain_error":maximum_chain,"maximum_real_joint_world_error":maxworld,
        "fractional_targets_read_or_used":False}
    checkpoint(out,audit)
    return nodes,parents,T,Q,S,stored,selected

def write_candidate(doc,ref,arrays,meshes,layout,out,audit):
    nodes,parents,T,Q,S,stored,selected=layout
    n=len(nodes);animated=[i for i in range(n) if i!=187]
    # Complete conservative budget before corrective POSITION allocation.
    estimate=(26773164+sum(m["position"].nbytes+m["indices"].nbytes+m["joints"].nbytes+m["weights"].nbytes for m in meshes)
        +187*16*4+len(animated)*291*10*4+3*97*291*4+3*97*4+2097152+4096)
    audit["preflight"]={"conservative_glb_bytes":int(estimate),"cap_bytes":CAP,
        "factored_joint_count":len(selected),"factor_helper_nodes":6*len(selected),"transform_nodes":n,
        "position_target_bytes":26773164,"json_budget_bytes":2097152,
        "before_corrective_target_allocation":True,"reference_and_archive_caps_separate":True}
    checkpoint(out,audit)
    check(estimate<=CAP,"complete_preflight_cap")
    writer=GLBBuffer()
    ibm=require_finite(np.linalg.inv(stored[0])).astype(np.float32)
    ibm_acc=writer.add(ibm.transpose(0,2,1).reshape(187,16),"MAT4")
    output_meshes=[];maxcondition=0.0;maxresidual=0.0
    for mi,m in enumerate(meshes):
        attrs={"POSITION":writer.add(m["position"],"VEC3",target=34962,bounds=True)}
        for k in range(m["sets"]):
            attrs["JOINTS_"+str(k)]=writer.add(m["joints"][:,4*k:4*k+4],"VEC4",5123,34962)
            attrs["WEIGHTS_"+str(k)]=writer.add(m["weights"][:,4*k:4*k+4],"VEC4",5126,34962)
        index=writer.add(m["indices"],"SCALAR",5125,34963)
        targets=[];base=m["position"].astype(np.float64)
        for row in range(291):
            palette=stored[row]@ibm.astype(np.float64)
            skin=np.einsum("nk,nkij->nij",m["weights"].astype(np.float64),palette[m["joints"]])
            require_finite(skin);linear=skin[:,:3,:3]
            conditions=require_finite(np.linalg.cond(linear));maximum=float(np.max(conditions))
            maxcondition=max(maxcondition,maximum);check(maximum<=CONDITION_CAP,"skin_condition_cap")
            target=arrays["mesh"+str(mi)+"_positions"][row]
            delta=require_finite(np.linalg.solve(linear,target-skin[:,:3,3])-base).astype(np.float32)
            pred=np.einsum("nij,nj->ni",linear,base+delta.astype(np.float64))+skin[:,:3,3]
            residual=float(np.max(np.linalg.norm(pred-target,axis=1)));maxresidual=max(maxresidual,residual)
            if residual>1e-4:
                audit["residual_failure"]={"mesh":mi,"row":row,"maximum_world_error":residual}
                checkpoint(out,audit);check(False,"stored_corrective_residual")
            targets.append({"POSITION":writer.add(delta,"VEC3",target=34962,bounds=True)})
        output_meshes.append({"name":m["name"],"primitives":[{"attributes":attrs,"indices":index,
            "mode":4,"targets":targets}],"weights":[1.0]+[0.0]*290})
    mesh_nodes=[n,n+1]
    nodes.extend({"name":m["name"],"mesh":i,"skin":i} for i,m in enumerate(meshes))
    animations=[]
    for ci,clip in enumerate(CLIPS):
        times=writer.add(np.arange(97,dtype=np.float32)/np.float32(48),"SCALAR",bounds=True)
        samplers=[];channels=[];start=ci*97
        for ni in animated:
            for path,values,kind in (("translation",T,"VEC3"),("rotation",Q,"VEC4"),("scale",S,"VEC3")):
                acc=writer.add(values[start:start+97,ni],kind)
                samplers.append({"input":times,"output":acc,"interpolation":"LINEAR"})
                channels.append({"sampler":len(samplers)-1,"target":{"node":ni,"path":path}})
        weights=np.zeros((97,291),dtype=np.float32)
        weights[np.arange(97),start+np.arange(97)]=1
        acc=writer.add(weights.reshape(-1),"SCALAR");samplers.append({"input":times,"output":acc,"interpolation":"LINEAR"})
        channels.extend({"sampler":len(samplers)-1,"target":{"node":ni,"path":"weights"}} for ni in mesh_nodes)
        animations.append({"name":clip,"samplers":samplers,"channels":channels})
    gltf={"asset":{"version":"2.0","copyright":doc["asset"]["copyright"],"generator":"Coop offline factor48 POSITION pilot",
        "extras":{"coop_corrective_contract":CONTRACT,"factored_native_palette_indices":selected,
            "production_approved":False,"all_influences_not_four_weight_adapter":True}},
        "scene":0,"scenes":[{"nodes":[187]+mesh_nodes}],"nodes":nodes,"meshes":output_meshes,
        "skins":[{"name":m["name"],"joints":list(range(187)),"inverseBindMatrices":ibm_acc,"skeleton":187} for m in meshes],
        "animations":animations,"buffers":[{"byteLength":len(writer.data)}],
        "bufferViews":writer.views,"accessors":writer.accessors}
    js=encode(gltf);check(len(js)<=2097152,"gltf_json_cap");js+=b" "*((-len(js))%4)
    binary=bytes(writer.data)+b"\0"*((-len(writer.data))%4)
    size=12+8+len(js)+8+len(binary);check(size<=CAP,"glb_final_cap")
    p=out/OUTPUT_NAME
    with p.open("xb") as f:
        f.write(struct.pack("<III",0x46546c67,2,size));f.write(struct.pack("<II",len(js),0x4e4f534a));f.write(js)
        f.write(struct.pack("<II",len(binary),0x004e4942));f.write(binary)
    audit["glb_written"]={"file":OUTPUT_NAME,"bytes":p.stat().st_size,"sha256":sha(p)}
    audit["maximum_skin_condition"]=maxcondition;audit["maximum_quantized_writer_residual"]=maxresidual
    checkpoint(out,audit)

def run(source_root,reference_root,out,audit):
    doc,binary=read_glb(source_root/"source.glb")
    ref=read_json(reference_root/"native_reference.json")
    old=read_json(source_root/"source-writer-audit.json");new=read_json(reference_root/"glb-correctives-audit.json")
    old_reader=read_json(source_root/"source-reader-audit.json")["summary"]
    check(old_reader["authored_passed"] is True and old_reader["fractional_passed"] is False
          and old_reader["passed"] is False,"source_expected_diagnostic_failure")
    arrays=authored_arrays(reference_root/"native_reference.npz")
    meshes=extract_payload(doc,binary,ref,old,new,arrays)
    layout=build_trs(doc,ref,arrays,audit,out)
    write_candidate(doc,ref,arrays,meshes,layout,out,audit)
    for name in ("native_reference.npz","native_reference.json"):
        shutil.copyfile(reference_root/name,out/name)
        check(sha(out/name)==REFERENCE_PINS[name][1],"copied_reference_checksum")
    audit["native_reference"]={"npz_bytes":REFERENCE_PINS["native_reference.npz"][0],
        "npz_sha256":REFERENCE_PINS["native_reference.npz"][1],
        "metadata_bytes":REFERENCE_PINS["native_reference.json"][0],
        "metadata_sha256":REFERENCE_PINS["native_reference.json"][1],"inherited_run":38696896433,"recaptured":False}
    audit["native_reference_hash_recheck"]=True;audit["writer_completed"]=True

def main():
    parser=argparse.ArgumentParser()
    for name in ("source-root","reference-root","out"):parser.add_argument("--"+name,required=True)
    args=parser.parse_args();source=Path(args.source_root).resolve();reference=Path(args.reference_root).resolve();out=Path(args.out).resolve()
    check(source.is_dir() and reference.is_dir() and source!=reference and out!=source and out!=reference
          and source not in out.parents and reference not in out.parents and out not in source.parents and out not in reference.parents,"directories")
    check(not out.exists(),"output_exists");out.mkdir(parents=True)
    audit={"purpose":"one offline stable-factor48 GLB, authored keys only",
        "writer_completed":False,"glb_written":None,"failure":None,"readonly_cleanup_passed":False,
        "native_reference_hash_recheck":False,"native_capture_this_job":False,"renders":0,"models_saved":0,
        "production_glb_approved":False,"browser_fidelity_approved":False,"overall_art_approved":False,
        "limits":["Only BODY+SHIRT ARMATURE-stage POSITION correction; all weights retained.",
            "No normals/UV/PBR/downstream modifiers/full avatar/four-weight adapter/browser approval.",
            "315 native rows and identity proof inherited, not recaptured.",
            "Old LINEAR source is a diagnostic data container with a known common-root structural gap.",
            "24 fixed quarter samples do not certify continuous-time/crossfade or arbitrary-pose fidelity."]}
    before=None
    def input_state():
        return {"source":pin(source,SOURCE_PINS),"reference":pin(reference,REFERENCE_PINS),
            "credits":{name:sha(reference/"credits"/name) for name in CREDITS}}
    try:
        before=input_state();audit["input_files"]=before
        for name in CREDITS:
            p=reference/"credits"/name
            check(p.is_file() and not p.is_symlink() and 0<p.stat().st_size<=65536
                  and p.stat().st_mode&0o222==0 and sha(p)==sha(source/"credits"/name),"attribution_guard")
            dest=out/"credits"/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        run(source,reference,out,audit)
    except Exception as error:
        code=error.args[0] if isinstance(error,ValueError) and len(error.args)==1 else None
        tb=error.__traceback__;frames=[]
        while tb is not None:
            frames.append({"file":Path(tb.tb_frame.f_code.co_filename).name,"line":tb.tb_lineno,"function":tb.tb_frame.f_code.co_name})
            frames=frames[-6:];tb=tb.tb_next
        audit["failure"]={"error_type":type(error).__name__,"error_code":code if isinstance(code,str)
            and len(code)<160 and all(c.islower() or c.isdigit() or c=="_" for c in code) else None,"frames":frames}
    finally:
        try:audit["readonly_cleanup_passed"]=before is not None and before==input_state()
        except Exception:audit["readonly_cleanup_passed"]=False
        audit["writer_completed"]=audit["writer_completed"] and audit["readonly_cleanup_passed"]
        checkpoint(out,audit)
        small={key:audit.get(key) for key in ("writer_completed","failure","glb_written","preflight",
            "maximum_skin_condition","maximum_quantized_writer_residual","native_reference",
            "native_reference_hash_recheck","readonly_cleanup_passed","classifier_progress")}
        if "classification" in audit:
            small["classification"]={k:v for k,v in audit["classification"].items() if k!="ordinary_maximum_by_palette_index"}
        if "scale_interval_diagnostics" in audit:
            small["scale_interval_diagnostics"]={k:v for k,v in audit["scale_interval_diagnostics"].items() if k!="examples"}
        check(len(encode(small))<=24576,"stdout_budget")
        print("SNOW_GLB_FACTOR48_WRITER "+encode(small).decode(),flush=True)
    return 0 if audit["writer_completed"] else 1
if __name__=="__main__":
    sys.exit(main())
