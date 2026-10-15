#!/usr/bin/env python3
"""One offline rotation-only CUBICSPLINE candidate using pinned native epsilon matrices."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import zipfile
import numpy as np
MAX_GLB=32*1024*1024
MAX_JSON=2*1024*1024
ARRAY_CAP=256*1024*1024
CLIPS=("idle","wave","celebrate")
CONTRACT="native_eps1024_rotation_cubic_v1"
PLAN_SHA="b96456634d1f79b130c1cc17a0e5dc31ab15f4a7e00d5cfe0a6943bb4c0033af"
PLAN_BLOB="c2678d3962be9f70cf1a9188955ee0f5a15306e1"
ENVELOPE_SHA="51634410b89dcc9ba97801d75bae680ad90c4252216c37bc9d16c757921b4e0a"
PINNED={
    "source.glb": [
        30598112,
        "7308349db07a0542b54b3ec29949f2610562a2b3501ceaa51633ad0930571c06"
    ],
    "native_reference.npz": [
        31443671,
        "6dca400a201b003e7ed81c8556d06cfa5afde07edad30705e2bf22ee487d9f94"
    ],
    "native_reference.json": [
        143763,
        "83471e5eb420f716ef024b04e660ba29ba975f6e13a52835f65498c964fecb9d"
    ],
    "source-writer-audit.json": [
        7484,
        "ce426af96c85ee809f14e8681c549c0021bfa63c43b58944b9ab3c27079c4ae4"
    ],
    "source-reader-audit.json": [
        289659,
        "245480cadc22088f71283af1d5dfd26877eb65e4445cf836b168f775d67d8b76"
    ]
}
PACKET_PINS=[
    {
        "native-rotation-packet-0.npz": [
            3582712,
            "1a8f65768e5e888da102e2dd121a45d28a89687732a0db1966e230e1bdd5ef56"
        ],
        "native-rotation-packet-0.json": [
            128234,
            "898cce9b009af6388bfc719aa3eea673d33e47319963c96cea1d59c3f92b5e8d"
        ],
        "capture-audit.json": [
            166149,
            "a12d9ede526bee8e42e181c8cd57694f2231564c09d1a8ab51c1610f9b874bb6"
        ]
    },
    {
        "native-rotation-packet-1.npz": [
            1226442,
            "7215408b76bc1fb344d908ca9c271b1d0dc22d7d55c6f4422fe8fb398947b150"
        ],
        "native-rotation-packet-1.json": [
            122328,
            "1c620a0baf06202155b8455d3ec1e5e39fef7ee22c359704aaa210ff6e808d6b"
        ],
        "capture-audit.json": [
            160280,
            "ab92e7c057e941d550c851cc925d75154804a940e9e65b0c567871276c1452e2"
        ]
    }
]
CREDITS=("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt")
CREDIT_SHA={"LICENSES.md":"21ffbcb7404ceeb59a8038da34ad28df24ee3f390d33f9c16bac04952cbab71c",
    "rain/ATTRIBUTION.txt":"41d2a5693de42c5ee60dafaea599dfadd5a34ede8554a4d8a7c98af0cd008f24",
    "snow/ATTRIBUTION.txt":"cf280b50c86fc5b1518643f4bb8be5befba91b29bdfeb5311ad3f98b65fddc9d"}
WIDTH={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}
OUTPUT_NAME="snow-armature-native-rotation-cubic-prototype.glb"

def require(ok, code):
    if not ok:
        raise ValueError("native_rotation_" + code)


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def finite(data):
    require(np.isfinite(data).all(), "nonfinite")
    return data


def frozen_files(root,pins=PINNED):
    result = {}
    for name, (size, checksum) in pins.items():
        path = root/name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == size,
                "input_file_size_or_type")
        require(digest(path) == checksum, "input_checksum")
        require(path.stat().st_mode & 0o222 == 0, "input_not_readonly")
        result[name] = {"bytes": size, "sha256": checksum}
    for name in CREDITS:
        path = root/"credits"/name
        require(path.is_file() and not path.is_symlink()
                and 0 < path.stat().st_size <= 65536
                and path.stat().st_mode & 0o222 == 0, "credits_missing_or_unbounded")
        result["credits/"+name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    return result


def read_json(path):
    require(path.stat().st_size <= MAX_JSON, "json_budget")
    return json.loads(path.read_text("utf-8"))


def read_glb(path):
    raw = path.read_bytes()
    require(20 <= len(raw) <= MAX_GLB, "input_glb_budget")
    require(struct.unpack_from("<III", raw, 0) == (0x46546c67, 2, len(raw)), "glb_header")
    cursor, chunks = 12, []
    while cursor < len(raw):
        require(cursor+8 <= len(raw), "glb_chunk_header")
        length, kind = struct.unpack_from("<II", raw, cursor)
        cursor += 8
        require(length % 4 == 0 and cursor+length <= len(raw), "glb_chunk_bounds")
        chunks.append((kind, raw[cursor:cursor+length]))
        cursor += length
    require(len(chunks) == 2 and chunks[0][0] == 0x4e4f534a and chunks[1][0] == 0x004e4942,
            "glb_two_chunks")
    doc = json.loads(chunks[0][1].decode("utf-8"))
    buffers = doc.get("buffers", [])
    require(len(buffers) == 1 and "uri" not in buffers[0], "glb_internal_buffer")
    length = buffers[0]["byteLength"]
    require(type(length) is int and 0 < length <= len(chunks[1][1])
            and len(chunks[1][1])-length <= 3, "glb_buffer_length")
    require(doc.get("asset", {}).get("extras", {}).get("coop_corrective_contract") == "coop-armature-factor-correctives-48hz-v1",
            "glb_contract")
    return doc, chunks[1][1][:length]


def values(doc, binary, index, expected):
    require(type(index) is int and 0 <= index < len(doc["accessors"]), "accessor_index")
    accessor = doc["accessors"][index]
    require(accessor.get("componentType") == 5126 and accessor.get("type") == expected
            and not accessor.get("normalized", False) and "sparse" not in accessor,
            "animation_accessor_type")
    vi = accessor["bufferView"]
    require(type(vi) is int and 0 <= vi < len(doc["bufferViews"]), "view_index")
    view = doc["bufferViews"][vi]
    require(view.get("buffer") == 0 and "byteStride" not in view, "animation_view_layout")
    count, width = accessor["count"], WIDTH[expected]
    require(type(count) is int and 0 < count <= 100000, "animation_count")
    relative = accessor.get("byteOffset", 0)
    start, size = view.get("byteOffset", 0)+relative, count*width*4
    require(type(relative) is int and relative >= 0 and start % 4 == 0
            and relative+size <= view["byteLength"] and start+size <= len(binary),
            "animation_accessor_bounds")
    return finite(np.frombuffer(binary, dtype="<f4", count=count*width,
                                offset=start).reshape(count, width).copy())


def unit_quaternion64(R):
    require(np.max(np.abs(R.T@R-np.eye(3)))<=1e-10 and abs(float(np.linalg.det(R))-1)<=1e-10,"rotation_not_proper")
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
    q=finite(q);norm=float(np.linalg.norm(q))
    require(norm>1e-12,"quaternion_zero")
    return q/norm

def load_npz(path,expected):
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist()
        require(len(infos)==len(expected) and len({i.filename for i in infos})==len(expected)
            and {i.filename for i in infos}=={k+".npy" for k in expected},"npz_members")
        expanded=sum(i.file_size for i in infos)
        require(expanded<=ARRAY_CAP,"npz_expanded_cap")
    with np.load(path,allow_pickle=False) as data:
        require(set(data.files)==set(expected),"npz_array_names")
        result={k:data[k] for k in expected}
    for key,shape in expected.items():
        a=result[key]
        require(a.dtype==np.dtype("<f8") and a.shape==shape,"npz_dtype_shape")
        finite(a);a.flags.writeable=False
    return result,expanded

def load_inputs(source,packet_roots,plan_path,audit):
    before={"source":frozen_files(source),"packets":[frozen_files(p,PACKET_PINS[i]) for i,p in enumerate(packet_roots)],
        "plan":digest(plan_path)}
    require(before["plan"]==PLAN_SHA,"plan_sha")
    for inventory in (before["source"],*before["packets"]):
        require(all(inventory["credits/"+name]["sha256"]==CREDIT_SHA[name] for name in CREDITS),"credit_sha")
    reference=read_json(source/"native_reference.json")
    writer=read_json(source/"source-writer-audit.json");reader=read_json(source/"source-reader-audit.json")
    summary=reader["summary"]
    require(writer["writer_completed"] and writer["readonly_cleanup_passed"] and writer["native_reference_hash_recheck"]
        and writer["failure"] is None and writer["classification"]["factored_indices"]==[183]
        and summary["authored_frames_checked"]==291 and summary["authored_passed"]
        and summary["fractional_frames_checked"]==24 and not summary["fractional_passed"] and not summary["passed"]
        and len(reader["fractional_frames"])==24
        and sum(not r["joint_matrix_passed"] for r in reader["fractional_frames"])==6
        and all(m["passed"] for r in reader["fractional_frames"] for m in r["meshes"]),"source_checkpoint")
    require(reference["reference_npz_sha256"]==PINNED["native_reference.npz"][1]
        and reference["reference_npz_bytes"]==PINNED["native_reference.npz"][0]
        and reference["sampling_contract"]=="native48hz_keys291_holdouts24_v1"
        and reference["fps"]==24 and reference["export_sample_rate"]==48
        and len(reference["frames"])==291 and len(reference["fractional_frames"])==24,"reference_contract")
    for ci,clip in enumerate(CLIPS):
        for k in range(97):
            require(reference["frames"][ci*97+k]=={"clip":clip,"frame":k/2,"time":k/48,"row":ci*97+k},"native_key_rows")
    plan=read_json(plan_path)
    require(plan["contract"]=="snow_native_rotation_derivative_eps1024_split_v1"
        and plan["contains_captured_pose_data"] is False
        and plan["epsilon_rational_source_frames"]==[1,1024]
        and plan["difference_rational_seconds"]==[1,24576]
        and plan["reference_npz_sha256"]==PINNED["native_reference.npz"][1]
        and plan["reference_metadata_sha256"]==PINNED["native_reference.json"][1]
        and plan["source_glb_sha256"]==PINNED["source.glb"][1],"plan_contract")
    expected_eps=[]
    for ci,clip in enumerate(CLIPS):
        for k in range(97):
            for side in ("incoming","outgoing"):
                if (side=="incoming" and k==0) or (side=="outgoing" and k==96):continue
                i=len(expected_eps)
                expected_eps.append({"id":i,"packet":0 if i<288 else 1,"clip":clip,"key_index":k,
                    "authored_row":ci*97+k,"key_frame":k/2,"side":side,
                    "sample_frame":k/2+(-1 if side=="incoming" else 1)/1024})
    fresh_expected=[{"id":ci*8+i,"packet":0,"clip":clip,"sample_frame":frame,
        "role":"fresh_geometry_and_joint_validation"} for ci,clip in enumerate(CLIPS)
        for i,frame in enumerate((.125,.375,12.125,12.375,24.125,24.375,36.125,36.375))]
    require(plan["epsilon_joint_only_samples"]==expected_eps and plan["fresh_validation_samples"]==fresh_expected,"canonical_plan")
    arrays,total=load_npz(source/"native_reference.npz",{"joint_world":(291,187,4,4),
        "fractional_joint_world":(24,187,4,4),"mesh0_positions":(291,5828,3),"mesh1_positions":(291,1839,3),
        "mesh0_fractional_positions":(24,5828,3),"mesh1_fractional_positions":(24,1839,3)})
    packets=[];envelope=None;registry=[]
    for i,root in enumerate(packet_roots):
        metadata=read_json(root/("native-rotation-packet-"+str(i)+".json"));a=read_json(root/"capture-audit.json")
        require(metadata["capture_complete"] and metadata["readonly_cleanup_passed"] and metadata["packet_id"]==i
            and a["capture_complete"] and a["readonly_cleanup_passed"] and a.get("failure") is None
            and all(a[k] for k in ("input_id_inventory_preserved","input_preservation_passed","original_binding_restored"))
            and a["input_driver_before"]==a["input_driver_after"]
            and a["input_driver_after"]["count"]==1291 and a["input_driver_after"]["active_invalid"]==0
            and a["input_driver_after"]["muted"]==0 and a["input_key_count_before"]==a["input_key_count_after"]==120
            and a["native_policy_before"]==a["native_policy_after"]
            and a["native_sample_guards"]["maximum_held_face_property_drift"]==0
            and a["native_sample_guards"]["maximum_zero_pre_armature_world_error_m"]==0
            and a["native_sample_guards"]["zero_binding_count"]==792,"packet_checkpoint")
        require(metadata["sampling_plan_sha256"]==PLAN_SHA
            and metadata["contract"]==plan["contract"]
            and metadata["packet_payload"]==a["packet_payload"]
            and metadata["pose_registry"]==a["pose_registry"]
            and metadata["provenance_envelope"]==a["provenance_envelope"]
            and metadata["joints"]==reference["joints"]
            and metadata["overlap_sentinel"]["passed"]
            and metadata["overlap_sentinel"]["maximum_joint_matrix_abs_error"]==0
            and metadata["overlap_sentinel"]["maximum_position_world_error_m"]==0,"packet_metadata")
        current=metadata["provenance_envelope"]
        raw=(json.dumps(current,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n").encode()
        require(hashlib.sha256(raw).hexdigest()==metadata["provenance_envelope_sha256"]==ENVELOPE_SHA
            and set(current)==set(plan["packet_envelope_must_bind"]),"packet_envelope")
        require(envelope is None or envelope==current,"packet_envelope_mismatch")
        envelope=current
        require(current["source_glb_sha256"]==PINNED["source.glb"][1]
            and current["reference_npz_sha256"]==PINNED["native_reference.npz"][1]
            and current["reference_metadata_sha256"]==PINNED["native_reference.json"][1]
            and current["sampling_plan_sha256"]==PLAN_SHA
            and current["source_native_blend_sha256"]==reference["candidate_sha256"],"packet_source_identity")
        fresh_count=24 if i==0 else 0
        expected={"epsilon_joint_world":(288,187,4,4),"fresh_joint_world":(fresh_count,187,4,4),
            "fresh_mesh0_positions":(fresh_count,5828,3),"fresh_mesh1_positions":(fresh_count,1839,3)}
        packet,expanded=load_npz(root/("native-rotation-packet-"+str(i)+".npz"),expected);total+=expanded
        require(total<=ARRAY_CAP,"combined_reference_expanded_cap")
        for key in ("epsilon_joint_world","fresh_joint_world"):
            require(np.array_equal(packet[key][:,186],np.broadcast_to(np.eye(4),packet[key][:,186].shape)),"packet_auxiliary_identity")
        selected=[r for r in metadata["pose_registry"] if r["kind"]=="epsilon_joint_only"]
        fresh=[r for r in metadata["pose_registry"] if r["kind"]=="fresh_geometry"]
        require(len(selected)==288 and len(fresh)==fresh_count,"packet_registry_counts")
        for j,r in enumerate(selected):
            e=expected_eps[i*288+j]
            require(r["local_row"]==j and all(r[k]==v for k,v in e.items())
                and r["geometry_proved"] is False and r["native_driver_invalid"]==0
                and r["held_face_passed"] and r["finite_key_values_passed"],"packet_epsilon_registry")
        for j,r in enumerate(fresh):
            require(r["local_row"]==j and all(r[k]==v for k,v in fresh_expected[j].items())
                and r["geometry_proved"] and r["native_driver_invalid"]==0
                and r["maximum_zero_world_error_m"]==0,"packet_fresh_registry")
        require(len(metadata["pose_registry"])==288+fresh_count
            and all(r["correspondence_pose_count"]==1+fresh_count and r["correspondence_passed"]
                for r in a["native_binding_correspondence"]),"packet_geometry_count")
        registry.extend(metadata["pose_registry"])
        packets.append((metadata,packet))
    old={(r["clip"],float(r["frame"])) for r in reference["frames"]+reference["fractional_frames"]}
    require(len(registry)==600 and len({(r["clip"],r["sample_frame"]) for r in registry})==600
        and all((r["clip"],r["sample_frame"]) not in old for r in registry),"registry_union")
    audit["input_files"]=before
    audit["native_data_contract"]={"epsilon_joint_only":576,"fresh_geometry":24,"unique_new":600,
        "geometry_inherited":315,"geometry_combined":339,"epsilon_geometry_proofs":0,
        "sentinel_adds_unique":0,"envelope_sha256":ENVELOPE_SHA,"expanded_reference_bytes":total,
        "expanded_reference_cap":ARRAY_CAP,"binary_npz_pins_shapes_finite_rechecked":True,
        "holdouts_used_for_field_or_tangents":False}
    return before,reference,arrays,packets,plan

def graph_and_streams(doc,binary,reference):
    require(len(doc["nodes"])==196 and len(doc["meshes"])==2 and len(doc["skins"])==2
        and doc["asset"]["extras"]["factored_native_palette_indices"]==[183],"fixed_graph_counts")
    nodes=doc["nodes"];parents=[-1]*196
    for i,node in enumerate(nodes):
        require("matrix" not in node,"matrix_node_unsupported")
        for child in node.get("children",[]):
            require(type(child) is int and 0<=child<196 and parents[child]==-1,"graph_multi_parent")
            parents[child]=i
    expected=[j["parent_index"] if j["parent_index"]>=0 else 187 for j in reference["joints"]]+[-1]+[173,188,189,190,191,192]+[-1,-1]
    expected[183]=193
    require(parents==expected and doc["scenes"]==[{"nodes":[187,194,195]}] and doc["scene"]==0,"fixed_graph_parents")
    require(nodes[187]["extras"]=={"coop_export_common_root":True}
        and nodes[183]["extras"]=={"coop_native_affine_tail":183},"fixed_graph_extras")
    for k in range(6):
        require(nodes[188+k]["extras"]=={"coop_affine_factor":{"native_palette_index":183,"stage":k}},"factor_helper_extras")
    for i,joint in enumerate(reference["joints"]):
        require(nodes[i]["name"]==joint["node_name"],"native_palette_name")
    for i,skin in enumerate(doc["skins"]):
        require(skin["joints"]==list(range(187)) and skin["skeleton"]==187
            and nodes[194+i]["mesh"]==i and nodes[194+i]["skin"]==i,"skin_graph")
    animated=[i for i in range(194) if i!=187]
    require(len(doc["animations"])==3 and [a["name"] for a in doc["animations"]]==list(CLIPS),"semantic_clips")
    rotations=[]
    for ci,animation in enumerate(doc["animations"]):
        by_target={};uses={}
        for channel in animation["channels"]:
            ni,path=channel["target"]["node"],channel["target"]["path"]
            require((ni,path) not in by_target,"duplicate_channel")
            si=channel["sampler"];require(type(si) is int and 0<=si<len(animation["samplers"]),"channel_sampler")
            by_target[(ni,path)]=si;uses.setdefault(si,[]).append((ni,path))
        require(set(by_target)=={(ni,path) for ni in animated for path in ("translation","rotation","scale")}
            |{(194,"weights"),(195,"weights")},"animation_channel_set")
        require(set(uses)==set(range(len(animation["samplers"]))),"unused_sampler")
        for sampler in animation["samplers"]:
            require(sampler.get("interpolation","LINEAR")=="LINEAR","source_interpolation")
            times=values(doc,binary,sampler["input"],"SCALAR")
            require(times.shape==(97,1) and np.array_equal(times[:,0],np.arange(97,dtype=np.float32)/np.float32(48)),"time_values")
        for ni in animated:
            si=by_target[(ni,"rotation")];sampler=animation["samplers"][si]
            require(uses[si]==[(ni,"rotation")],"rotation_sampler_not_exclusive")
            keys=values(doc,binary,sampler["output"],"VEC4")
            require(keys.shape==(97,4) and np.max(np.abs(np.linalg.norm(keys.astype(np.float64),axis=1)-1))<1e-4
                and np.all(np.sum(keys[1:].astype(np.float64)*keys[:-1],axis=1)>=0),"stored_key_quaternion")
            rotations.append({"clip_index":ci,"node":ni,"sampler":si,"accessor":sampler["output"],
                "view":doc["accessors"][sampler["output"]]["bufferView"],"keys":keys})
    require(len(rotations)==579 and len({r["accessor"] for r in rotations})==579
        and len({r["view"] for r in rotations})==579,"rotation_stream_count")
    return animated,rotations

def native_locals(world,reference,context):
    finite(world);require(world.shape==(187,4,4),"native_world_shape")
    require(np.max(np.abs(world[:,3,:]-[0,0,0,1]))<=1e-7,"native_world_affine")
    local=np.empty_like(world)
    for i,j in enumerate(reference["joints"]):
        p=j["parent_index"];context["native_palette_index"]=i
        try:
            local[i]=world[i] if p<0 else np.linalg.solve(world[p],world[i])
        except Exception:
            context["native_world_matrix"]=world[i].tolist()
            context["native_parent_index"]=p
            raise
    finite(local)
    require(np.max(np.abs(local[:,3,:]-[0,0,0,1]))<=1e-7,"native_local_affine")
    return local

def field64(world,reference,signs,bind_sign,context):
    local=native_locals(world,reference,context)
    result=np.zeros((194,4),dtype=np.float64);result[:,3]=1
    for i in range(186):
        context["native_palette_index"]=i
        A=local[i,:3,:3]
        try:
            if i!=183:
                require(float(np.linalg.det(A))*float(np.prod(signs[i]))>1e-12,"ordinary_reflection")
                U,sv,Vt=np.linalg.svd(A*signs[i][None,:])
                require(np.min(sv)>1e-8 and np.max(sv)/np.min(sv)<=1e6,"ordinary_domain")
                result[i]=unit_quaternion64(U@Vt)
                continue
            require(float(np.linalg.det(A))*bind_sign>1e-12,"factor_determinant_sign")
            a=A[:,0];n0=float(np.linalg.norm(a));require(n0>1e-8,"qr_first")
            q0=a/n0;v=A[:,1]-np.dot(q0,A[:,1])*q0;n1=float(np.linalg.norm(v));require(n1>1e-8,"qr_second")
            q1=v/n1;q2=np.cross(q0,q1);Q=np.column_stack((q0,q1,q2));R=Q.T@A
            require(np.max(np.abs(np.tril(R,-1)))<=1e-10 and np.max(np.abs(Q@R-A))<=1e-10,"qr_reconstruction")
            D=np.diag(R).copy()
            require(np.all(np.abs(D)>1e-8) and np.array_equal(np.sign(D),[1,1,bind_sign]),"qr_diagonal_sign")
            result[188]=unit_quaternion64(Q)
            x,y,z=R[0,1]/D[0],R[0,2]/D[0],R[1,2]/D[1]
            reconstruction=Q@np.diag(D)
            for stage,(a,b,k) in enumerate(((0,1,x),(0,2,y-x*z),(1,2,z))):
                theta1=math.pi/4-.5*math.atan(k/2);theta2=-math.pi/4-.5*math.atan(k/2)
                plus=math.exp(math.asinh(k/2));minus=math.exp(-math.asinh(k/2))
                require(math.isfinite(plus) and math.isfinite(minus) and plus>1e-8 and minus>1e-8,"shear_scale_domain")
                for side,theta in enumerate((theta1,theta2)):
                    plane=np.eye(3);c,s=math.cos(theta),math.sin(theta)
                    plane[a,a]=plane[b,b]=c;plane[a,b]=-s;plane[b,a]=s
                    node=189+2*stage+side
                    if node==194:node=183
                    result[node]=unit_quaternion64(plane)
                    scale=np.ones(3)
                    if side==0:scale[a],scale[b]=plus,minus
                    reconstruction=reconstruction@plane@np.diag(scale)
            require(np.max(np.abs(reconstruction-A))<=1e-10,"analytic_factor_reconstruction")
        except Exception:
            context["native_local_matrix"]=local[i].tolist()
            raise
    return finite(result)

def plan_repack(doc,binary,streams,audit):
    target=copy.deepcopy(doc)
    by_view={r["view"]:r for r in streams}
    views=target["bufferViews"];accessors=target["accessors"]
    require(len(views)==len(accessors),"one_accessor_per_view")
    owners={}
    for ai,accessor in enumerate(accessors):
        vi=accessor["bufferView"]
        require(type(vi) is int and vi not in owners and 0<=vi<len(views)
            and accessor.get("byteOffset",0)==0 and "sparse" not in accessor,"accessor_exclusive_view")
        owners[vi]=ai
    old_cursor=new_cursor=0
    for vi,view in enumerate(views):
        original=doc["bufferViews"][vi];accessor=accessors[owners[vi]]
        require(view["buffer"]==0 and "byteStride" not in view and "uri" not in view,"view_layout")
        old_cursor=(old_cursor+3)&~3
        require(original.get("byteOffset",0)==old_cursor and original["byteLength"]>0,"source_view_order_or_gap")
        old_cursor+=original["byteLength"]
        width=WIDTH[accessor["type"]];component={5126:4,5123:2,5125:4}.get(accessor["componentType"])
        require(component is not None and accessor["count"]*width*component==original["byteLength"],"accessor_view_exact_length")
        new_cursor=(new_cursor+3)&~3;view["byteOffset"]=new_cursor
        if vi in by_view:
            r=by_view[vi]
            require(owners[vi]==r["accessor"] and accessor["count"]==97 and accessor["type"]=="VEC4"
                and accessor["componentType"]==5126 and not accessor.get("normalized",False)
                and "min" not in accessor and "max" not in accessor,"rotation_view_ownership")
            accessor["count"]=291;view["byteLength"]=original["byteLength"]*3
            target["animations"][r["clip_index"]]["samplers"][r["sampler"]]["interpolation"]="CUBICSPLINE"
        new_cursor+=view["byteLength"]
    require(old_cursor==len(binary),"source_binary_unused_tail")
    target["buffers"][0]["byteLength"]=new_cursor
    target["asset"]["extras"]["coop_native_rotation_derivative_contract"]=CONTRACT
    js=encoded(target);padded_json=len(js)+(-len(js))%4;padded_binary=new_cursor+(-new_cursor)%4
    size=12+8+padded_json+8+padded_binary
    audit["preflight"]={"exact_glb_bytes":size,"binary_bytes":new_cursor,"json_bytes":len(js),
        "cap_bytes":MAX_GLB,"before_new_tangent_or_output_binary_allocation":True,
        "rotation_streams":len(streams),"tangent_binary_increment":new_cursor-len(binary),
        "source_binary_bytes":len(binary),"old_rotation_views_replaced_not_appended":True}
    require(new_cursor-len(binary)==1797216 and len(js)<=MAX_JSON and size<=MAX_GLB,"exact_output_cap")
    return target,js,new_cursor,size

def rewrite(source,packet_roots,plan_path,out,audit):
    before,reference,arrays,packets,plan=load_inputs(source,packet_roots,plan_path,audit)
    doc,binary=read_glb(source/"source.glb")
    animated,streams=graph_and_streams(doc,binary,reference)
    target,js,new_size,glb_size=plan_repack(doc,binary,streams,audit)
    audit["source_checkpoint_passed"]=True
    signs=np.sign(np.asarray([n["scale"] for n in doc["nodes"][:187]],dtype=np.float64))
    require(np.all(np.abs(signs)==1),"bind_scale_signs")
    bind_local=native_locals(arrays["joint_world"][0],reference,{})
    determinant=float(np.linalg.det(bind_local[183,:3,:3]));require(abs(determinant)>1e-12,"bind_factor_determinant")
    bind_sign=1 if determinant>0 else -1
    # Only authored keys and epsilon samples enter this field, never validation matrices/positions.
    key_fields=np.empty((291,194,4),dtype=np.float64)
    by_node={(r["clip_index"],r["node"]):r for r in streams}
    for row,world in enumerate(arrays["joint_world"]):
        context={"phase":"key","row":row,"clip":reference["frames"][row]["clip"],"frame":reference["frames"][row]["frame"]}
        audit["active_field_context"]=context
        field=field64(world,reference,signs,bind_sign,context)
        ci,k=divmod(row,97)
        for ni in animated:
            stored=by_node[(ci,ni)]["keys"][k].astype(np.float64)
            norm=float(np.linalg.norm(stored));require(norm>1e-12,"stored_quaternion_zero")
            dot=float(np.dot(field[ni],stored/norm))
            require(math.isfinite(dot) and dot!=0,"key_hemisphere_ambiguous")
            if dot<0:field[ni]*=-1
            if not np.array_equal(field[ni].astype(np.float32),by_node[(ci,ni)]["keys"][k]):
                audit["key_field_mismatch"]={"clip":CLIPS[ci],"key":k,"node":ni,"node_name":doc["nodes"][ni]["name"],
                    "native_field_f64":field[ni].tolist(),"native_field_f32":field[ni].astype(np.float32).tolist(),
                    "stored_f32":by_node[(ci,ni)]["keys"][k].tolist()}
                raise ValueError("native_rotation_key_field_f32_mismatch")
        key_fields[row]=field
    outputs={}
    for r in streams:
        v=np.zeros((97,3,4),dtype="<f4");v[:,1]=r["keys"]
        outputs[(r["clip_index"],r["node"])]=v
    used=set();maximum_tangent=0.0
    for metadata,packet in packets:
        records=[r for r in metadata["pose_registry"] if r["kind"]=="epsilon_joint_only"]
        for record in records:
            row=record["authored_row"];ci,k=divmod(row,97);side=record["side"]
            context={"phase":"epsilon","epsilon_id":record["id"],"clip":record["clip"],
                "frame":record["sample_frame"],"key":k,"side":side}
            audit["active_field_context"]=context
            field=field64(packet["epsilon_joint_world"][record["local_row"]],reference,signs,bind_sign,context)
            slot=(ci,k,side);require(slot not in used,"duplicate_tangent_side");used.add(slot)
            for ni in animated:
                key=key_fields[row,ni];dot=float(np.dot(field[ni],key))
                require(math.isfinite(dot) and dot!=0,"epsilon_hemisphere_ambiguous")
                if dot<0:field[ni]*=-1
                source_key=by_node[(ci,ni)]["keys"][k].astype(np.float64)
                require(float(np.dot(field[ni],source_key))>0,"epsilon_stored_key_hemisphere")
                difference=(key-field[ni]) if side=="incoming" else (field[ni]-key)
                tangent=finite(difference*24576.0).astype(np.float32);finite(tangent)
                if ni==186:
                    require(np.array_equal(tangent,np.zeros(4,np.float32)),"auxiliary_nonzero_tangent")
                outputs[(ci,ni)][k,0 if side=="incoming" else 2]=tangent
                maximum_tangent=max(maximum_tangent,float(np.max(np.abs(tangent))))
    expected={(ci,k,side) for ci in range(3) for k in range(97) for side in ("incoming","outgoing")
        if not ((side=="incoming" and k==0) or (side=="outgoing" and k==96))}
    require(used==expected and len(used)==576,"tangent_side_coverage")
    for r in streams:
        v=outputs[(r["clip_index"],r["node"])]
        require(v[:,1].tobytes()==r["keys"].tobytes() and not np.any(v[0,0]) and not np.any(v[-1,2]),"key_or_endpoint_changed")
        if r["node"]==186:require(not np.any(v[:,(0,2),:]),"auxiliary_tangent_changed")
    data=bytearray(new_size);view_streams={r["view"]:r for r in streams}
    for vi,view in enumerate(target["bufferViews"]):
        start=view["byteOffset"];original=doc["bufferViews"][vi];old_start=original.get("byteOffset",0)
        if vi in view_streams:
            r=view_streams[vi];raw=outputs[(r["clip_index"],r["node"])].tobytes()
        else:
            raw=binary[old_start:old_start+original["byteLength"]]
        require(len(raw)==view["byteLength"],"repack_view_length")
        data[start:start+len(raw)]=raw
    json_pad=js+b" "*((-len(js))%4);bin_pad=bytes(data)+b"\0"*((-len(data))%4)
    require(12+8+len(json_pad)+8+len(bin_pad)==glb_size<=MAX_GLB,"serialized_size")
    path=out/OUTPUT_NAME
    with path.open("xb") as f:
        f.write(struct.pack("<III",0x46546c67,2,glb_size))
        f.write(struct.pack("<II",len(json_pad),0x4e4f534a));f.write(json_pad)
        f.write(struct.pack("<II",len(bin_pad),0x004e4942));f.write(bin_pad)
    audit["glb_written"]={"file":OUTPUT_NAME,"bytes":path.stat().st_size,"sha256":digest(path)}
    # A postwrite read of the actual file verifies payload transport, independently of writer arrays.
    decoded,new_binary=read_glb(path)
    for vi,view in enumerate(decoded["bufferViews"]):
        r=view_streams.get(vi);start=view["byteOffset"]
        raw=new_binary[start:start+view["byteLength"]]
        if r is None:
            original=doc["bufferViews"][vi];old_start=original.get("byteOffset",0)
            require(raw==binary[old_start:old_start+original["byteLength"]],"nonrotation_payload_changed")
        else:
            actual=values(decoded,new_binary,r["accessor"],"VEC4").reshape(97,3,4)
            require(actual[:,1].tobytes()==r["keys"].tobytes()
                and np.array_equal(actual,outputs[(r["clip_index"],r["node"])]),"written_rotation_transport")
    audit["tangent_policy"]={"contract":CONTRACT,"epsilon_source_frames":[1,1024],
        "difference_seconds":[1,24576],"one_sided_native_epsilon_records":576,"quaternion_rotation_tracks_per_clip":193,
        "rotation_streams":579,"key_value_and_time_bytes_unchanged":True,"translation_scale_morph_linear_unchanged":True,
        "normalized_f64_key_and_epsilon_field_before_difference":True,"key_field_matches_stored_f32_values":True,
        "finished_tangents_float32":True,"derivative_projection":False,"holdouts_used":False,
        "maximum_absolute_tangent_component_per_second":maximum_tangent,"unused_endpoint_and_auxiliary_tangents_zero":True}
    audit["writer_actual_glb_transport_check_passed"]=True
    for name in ("native_reference.npz","native_reference.json"):
        shutil.copyfile(source/name,out/name)
        require(digest(out/name)==PINNED[name][1],"copied_reference_hash")
    for i,root in enumerate(packet_roots):
        for suffix in ("npz","json"):
            name="native-rotation-packet-"+str(i)+"."+suffix
            shutil.copyfile(root/name,out/name)
            require(digest(out/name)==PACKET_PINS[i][name][1],"copied_packet_hash")
    shutil.copyfile(plan_path,out/"snow-native-rotation-derivative-plan.json")
    require(digest(out/"snow-native-rotation-derivative-plan.json")==PLAN_SHA,"copied_plan_hash")
    audit["native_reference_hash_recheck"]=True
    audit["writer_completed"]=True
    return before

def main():
    parser=argparse.ArgumentParser()
    for name in ("source-root","packet0-root","packet1-root","plan","out"):
        parser.add_argument("--"+name,required=True)
    args=parser.parse_args()
    source=Path(args.source_root).resolve(strict=True)
    roots=[Path(args.packet0_root).resolve(strict=True),Path(args.packet1_root).resolve(strict=True)]
    plan_path=Path(args.plan).resolve(strict=True);out=Path(args.out).resolve()
    require(sys.version_info[:2]==(3,11) and np.__version__=="1.26.4","python_numpy_version")
    require(len({source,*roots})==3 and all(r.is_dir() for r in (source,*roots)),"input_directories")
    require(not out.exists() and all(not out.is_relative_to(r) and not r.is_relative_to(out) for r in (source,*roots))
        and not plan_path.is_relative_to(out),"output_overlap")
    out.mkdir(parents=True,exist_ok=False)
    audit={"purpose":"One rotation-only CUBICSPLINE candidate from true native epsilon matrices",
        "writer_completed":False,"source_checkpoint_passed":False,"readonly_cleanup_passed":False,
        "native_reference_hash_recheck":False,"glb_written":None,"error":None,
        "renders":0,"models_saved":0,"native_playback_this_job":False,"source_geometry_edits":0,
        "overall_art_approved":False,"production_glb_approved":False,"browser_animation_approved":False,
        "limits":["BODY+SHIRT Armature-stage POSITION-only/all eligible weights retained; four-weight adapter disabled.",
            "Native315 reference rows and576 epsilon/24 fresh rows inherited; no bpy or native pose capture.",
            "Fresh24 cover limited first-half-key intervals; no arbitrary pose/continuous/crossfade/art acceptance.",
            "No UV/NORMAL/PBR/UDIM/downstream modifiers/full avatar/browser acceptance.",
            "Writer completion is not independent geometric/joint fidelity acceptance."]}
    failure=None
    try:
        for name in CREDITS:
            target=out/"credits"/name;target.parent.mkdir(parents=True,exist_ok=True)
            require(digest(source/"credits"/name)==CREDIT_SHA[name],"source_credit_pin")
            shutil.copyfile(source/"credits"/name,target)
        rewrite(source,roots,plan_path,out,audit)
    except Exception as error:
        failure=error
        code=error.args[0] if isinstance(error,ValueError) and len(error.args)==1 else None
        frames=[];tb=error.__traceback__
        while tb is not None:
            frames.append({"file":Path(tb.tb_frame.f_code.co_filename).name,"line":tb.tb_lineno,
                "function":tb.tb_frame.f_code.co_name});frames=frames[-6:];tb=tb.tb_next
        audit["error"]={"type":type(error).__name__,"code":code if isinstance(code,str)
            and code.startswith("native_rotation_") and len(code)<180 else None,"frames":frames}
    finally:
        try:
            before=audit.get("input_files")
            after={"source":frozen_files(source),"packets":[frozen_files(r,PACKET_PINS[i]) for i,r in enumerate(roots)],
                "plan":digest(plan_path)}
            audit["input_files_unchanged"]=before is not None and before==after
            audit["readonly_cleanup_passed"]=audit["input_files_unchanged"]
        except Exception as error:
            audit["input_files_unchanged"]=False
            audit["cleanup_error_type"]=type(error).__name__
        audit["writer_completed"]=audit["writer_completed"] and failure is None and audit["readonly_cleanup_passed"]
        raw=encoded(audit);require(len(raw)<=MAX_JSON,"audit_byte_budget")
        (out/"native-rotation-writer-audit.json").write_bytes(raw)
        summary={k:audit.get(k) for k in ("writer_completed","error","active_field_context","key_field_mismatch",
            "preflight","native_data_contract","tangent_policy","glb_written","input_files_unchanged",
            "native_reference_hash_recheck","readonly_cleanup_passed","native_playback_this_job",
            "overall_art_approved","production_glb_approved","browser_animation_approved")}
        require(len(encoded(summary))<=24576,"stdout_budget")
        print("SNOW_NATIVE_ROTATION_CUBIC_WRITER "+encoded(summary).decode(),flush=True)
    return 0 if audit["writer_completed"] else 1

if __name__=="__main__":
    sys.exit(main())
