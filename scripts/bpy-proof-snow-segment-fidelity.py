"""Duplicate-only bounded native B-Bone LBS fidelity probe; no render, export or save."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

NATIVE_BLOB="051f18c2633a7aa2b1fd6b95483e23d5a96adcb9"
CONFIG_BLOB="f0612039b320e8dac77587ec4aecdc2c84618843"
SOURCE_SHA="80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
INPUT_SHA="b22306981a809bdb2e537c52087efe8d503bc30a0efe73573a51bb6200aeffa3"
INPUT_BYTES=8297412
PARENT_SHA="572897f5416f256950134e408ead8d77ecf53c0accbe5f7912be976c3c763ea4"
TAG="_coop_fidelity_source_point_id"
SAMPLES=(("idle",0),("wave",24),("celebrate",24))
TOL=0.0001

def encoded(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n").encode()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def checkpoint(path,audit):
    raw=encoded(audit)
    if len(raw)>1048576:
        raise ValueError("segment_fidelity_report_byte_budget_exceeded")
    path.write_bytes(raw)

def load_reviewed():
    path=Path(__file__).with_name("bpy-prototype-snow-native-clips.py")
    if blob(path.read_bytes())!=NATIVE_BLOB:
        raise ValueError("reviewed_native_clip_functions_hash_mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_snow_native_clip_functions",path)
    native=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    return (native,*native.load_reviewed())

def id_inventory(bpy):
    return {category:sorted((item.name,int(item.as_pointer())) for item in getattr(bpy.data,category))
        for category in ("objects","meshes","shape_keys","actions")}

def armature_flags(obj,modifier,rig):
    fields=("use_deform_preserve_volume","use_vertex_groups","use_bone_envelopes",
        "use_multi_modifier","vertex_group","invert_vertex_group","show_viewport","show_render")
    report={"object":obj.name,"modifier":modifier.name,"modifier_index":list(obj.modifiers).index(modifier),
        "target":modifier.object.name if modifier.object else None}
    for field in fields:
        report[field]=getattr(modifier,field)
    report["supported_linear_cpu"]=(modifier.object==rig and modifier.show_viewport
        and not modifier.use_deform_preserve_volume and modifier.use_vertex_groups
        and not modifier.use_bone_envelopes and not modifier.use_multi_modifier
        and modifier.vertex_group=="" and not modifier.invert_vertex_group)
    return report

def contributors(vertex,group_names,rig):
    result=[]
    for entry in vertex.groups:
        weight=float(entry.weight)
        if not math.isfinite(weight) or weight<0:
            raise ValueError("segment_fidelity_weight_nonfinite_or_negative")
        if weight==0:
            continue
        if entry.group not in group_names:
            raise ValueError("segment_fidelity_vertex_group_index_unknown")
        name=group_names[entry.group]
        bone=rig.data.bones.get(name)
        eligible=bone is not None and bone.use_deform
        result.append({"group_index":int(entry.group),"group":name,"weight":weight,
            "bone_exists":bone is not None,"use_deform":bool(bone.use_deform) if bone else None,
            "segments":int(bone.bbone_segments) if bone else None,
            "envelope_multiply":bool(bone.use_envelope_multiply) if bone else None,
            "native_eligible":bool(eligible)})
    return sorted(result,key=lambda r:r["group_index"])

def weight_inventory(obj,rig):
    names={g.index:g.name for g in obj.vertex_groups}
    histogram={}
    bones={}
    positive=0
    for vertex in obj.data.vertices:
        records=contributors(vertex,names,rig)
        positive+=len(records)
        histogram[str(len(records))]=histogram.get(str(len(records)),0)+1
        for record in records:
            if record["bone_exists"]:
                item=bones.setdefault(record["group"],{"bone":record["group"],"use_deform":record["use_deform"],
                    "segments":record["segments"],"envelope_multiply":record["envelope_multiply"],"positive_weight_vertices":0})
                item["positive_weight_vertices"]+=1
    return {"vertices":len(obj.data.vertices),"positive_entries":positive,"positive_contributor_histogram":histogram,
        "maximum_positive_contributors":max((int(k) for k in histogram),default=0),
        "weighted_bones":sorted(bones.values(),key=lambda r:r["bone"])}

def select_action(native,proof,rig,bpy,producer,clip,frame):
    descriptor=producer["clips"][clip]["action_descriptor"]
    action=bpy.data.actions.get(descriptor["action"])
    if action is None:
        raise ValueError("segment_fidelity_native_action_missing")
    slots=[s for s in action.slots if s.identifier==descriptor["slot_identifier"]]
    if len(slots)!=1:
        raise ValueError("segment_fidelity_native_slot_missing")
    slot=slots[0]
    actual=native.curve_descriptor(action,slot,native.channel_paths(proof,rig),True)
    if actual!=descriptor:
        raise ValueError("segment_fidelity_native_action_curves_mismatch")
    native.assign_action(rig,action,slot)
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()

def require_matrix(value,invertible=False):
    if not all(math.isfinite(float(v)) for row in value for v in row):
        raise ValueError("segment_fidelity_matrix_nonfinite")
    if invertible:
        determinant=float(value.determinant())
        if not math.isfinite(determinant) or abs(determinant)<=1e-12:
            raise ValueError("segment_fidelity_matrix_not_invertible")
    return value

def require_vector(value):
    if not all(math.isfinite(float(v)) for v in value):
        raise ValueError("segment_fidelity_vector_nonfinite")
    return value

def deform_bone_matrix(pb,point):
    """Official 4.5.9 PoseBone example: point is ARMATURE POSE SPACE, no DQ."""
    require_vector(point)
    require_matrix(pb.matrix)
    rest_inverse=require_matrix(pb.bone.matrix_local,invertible=True).inverted()
    if pb.bone.bbone_segments>1:
        index,blend_next=pb.bbone_segment_index(point)
        index,blend_next=int(index),float(blend_next)
        segments=int(pb.bone.bbone_segments)
        if not 0<=index<segments or not math.isfinite(blend_next) or not 0<=blend_next<=1:
            raise ValueError("segment_fidelity_native_segment_index_or_blend_invalid")
        pose1=require_matrix(pb.bbone_segment_matrix(index,rest=False))
        rest1=require_matrix(pb.bbone_segment_matrix(index,rest=True),invertible=True)
        pose2=require_matrix(pb.bbone_segment_matrix(index+1,rest=False))
        rest2=require_matrix(pb.bbone_segment_matrix(index+1,rest=True),invertible=True)
        d1=require_matrix(pose1@rest1.inverted())
        d2=require_matrix(pose2@rest2.inverted())
        inner=require_matrix(d1*(1-blend_next)+d2*blend_next)
        deform=require_matrix(pb.matrix@inner@rest_inverse)
        return deform,{"segment_index":index,"blend_next":blend_next,"segments":segments}
    return require_matrix(pb.matrix@rest_inverse),{"segment_index":None,"blend_next":None,"segments":1}

def topology_ids(mesh,ids):
    def cycle(values):
        return min(tuple(values[i:]+values[:i]) for i in range(len(values))) if values else ()
    edges=sorted(tuple(sorted((ids[e.vertices[0]],ids[e.vertices[1]]))) for e in mesh.edges)
    polygons=sorted(cycle([ids[v] for v in p.vertices]) for p in mesh.polygons)
    return digest({"edges":edges,"polygons":polygons})

def raw_topology(obj):
    return topology_ids(obj.data,list(range(1,len(obj.data.vertices)+1)))

def snapshot_duplicate(bpy,obj,rig,raw_count,topology,audit,phase,path):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=None
    try:
        mesh=evaluated.to_mesh(preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get())
        attribute=mesh.attributes.get(TAG)
        check={"phase":phase,"raw_count":raw_count,"evaluated_count":len(mesh.vertices),
            "attribute_exists":attribute is not None,"attribute_type":attribute.data_type if attribute else None,
            "attribute_domain":attribute.domain if attribute else None}
        audit.setdefault("id_mapping_checks",[]).append(check)
        checkpoint(path,audit)
        if attribute is None or attribute.data_type!="INT" or attribute.domain!="POINT":
            raise ValueError("segment_fidelity_point_id_attribute_lost")
        ids=[int(v.value) for v in attribute.data]
        check.update({"id_count":len(ids),"unique_count":len(set(ids)),
            "id_min":min(ids,default=None),"id_max":max(ids,default=None),
            "retained_subset":len(ids)<raw_count,
            "out_of_range_ids_first":sorted(i for i in ids if not 1<=i<=raw_count)[:16]})
        checkpoint(path,audit)
        if (len(ids)!=len(mesh.vertices) or not ids or len(set(ids))!=len(ids)
                or any(not 1<=i<=raw_count for i in ids)):
            raise ValueError("segment_fidelity_point_ids_not_one_to_one")
        actual_topology=topology_ids(mesh,ids)
        check.update({"id_topology_sha256":actual_topology,"expected_stage_id_topology_sha256":topology,
            "one_to_one_retained_ids":True,"topology_matches":topology is None or actual_topology==topology})
        checkpoint(path,audit)
        if topology is not None and actual_topology!=topology:
            raise ValueError("segment_fidelity_point_id_topology_changed")
        names={g.index:g.name for g in obj.vertex_groups}
        result={}
        for vertex in mesh.vertices:
            point_id=ids[vertex.index]
            co=list(vertex.co)
            if not all(math.isfinite(v) for v in co):
                raise ValueError("segment_fidelity_evaluated_coordinate_nonfinite")
            result[point_id]={"co":co,"contributors":contributors(vertex,names,rig)}
        require_matrix(evaluated.matrix_world,invertible=True)
        return {"points":result,"id_topology_sha256":actual_topology,"matrix_world":[list(r) for r in evaluated.matrix_world],
            "id_count":len(ids),"one_to_one_ids":True}
    finally:
        if mesh is not None:
            evaluated.to_mesh_clear()

def copy_probe_object(bpy,source,index,post,owned):
    duplicate=source.copy()
    owned["objects"].append(duplicate)
    mesh=source.data.copy()
    owned["meshes"].append(mesh)
    duplicate.data=mesh
    if mesh==source.data:
        raise ValueError("segment_fidelity_mesh_copy_not_independent")
    if source.data.shape_keys:
        if mesh.shape_keys is None or mesh.shape_keys==source.data.shape_keys:
            raise ValueError("segment_fidelity_key_copy_not_independent")
        owned["keys"].add(int(mesh.shape_keys.as_pointer()))
        source_keys=[(k.name,float(k.value)) for k in source.data.shape_keys.key_blocks]
        duplicate_keys=[(k.name,float(k.value)) for k in mesh.shape_keys.key_blocks]
        if source_keys!=duplicate_keys:
            raise ValueError("segment_fidelity_copy_current_key_values_mismatch")
    if mesh.attributes.get(TAG) is not None:
        raise ValueError("segment_fidelity_point_id_attribute_collision")
    attribute=mesh.attributes.new(name=TAG,type="INT",domain="POINT")
    for i,item in enumerate(attribute.data):
        item.value=i+1
    duplicate.name="COOP_FIDELITY_POST_TEMP" if post else "COOP_FIDELITY_PRE_TEMP"
    # Preserve all upstream modifiers unchanged; remove target+tail for pre, only tail for post.
    keep=index+1 if post else index
    for modifier in list(duplicate.modifiers)[keep:]:
        duplicate.modifiers.remove(modifier)
    duplicate.hide_render=True
    duplicate.hide_viewport=False
    bpy.context.scene.collection.objects.link(duplicate)
    duplicate.hide_set(False)
    return duplicate

def cleanup_owned(bpy,owned,original_ids):
    original_objects={pointer for name,pointer in original_ids["objects"]}
    original_meshes={pointer for name,pointer in original_ids["meshes"]}
    original_keys={pointer for name,pointer in original_ids["shape_keys"]}
    for obj in reversed(owned["objects"]):
        if obj.as_pointer() in original_objects:
            raise ValueError("segment_fidelity_cleanup_attempted_original_object")
        bpy.data.objects.remove(obj,do_unlink=True)
    for mesh in reversed(owned["meshes"]):
        if mesh.as_pointer() in original_meshes:
            raise ValueError("segment_fidelity_cleanup_attempted_original_mesh")
        bpy.data.meshes.remove(mesh,do_unlink=True)
    for key in list(bpy.data.shape_keys):
        pointer=int(key.as_pointer())
        if pointer in owned["keys"] and pointer not in original_keys:
            # Only this owned, independent Key may drop its copied fake-user retention.
            if key.use_fake_user:
                key.use_fake_user=False
            if key.users!=0:
                raise ValueError("segment_fidelity_owned_key_still_has_users")
            bpy.data.batch_remove(ids=[key])

def cpu_compare(rig,mesh_world,pre,post,point_ids):
    from mathutils import Matrix,Vector
    require_matrix(rig.matrix_world,invertible=True)
    require_matrix(mesh_world,invertible=True)
    mesh_to_rig=require_matrix(rig.matrix_world.inverted()@mesh_world,invertible=True)
    rig_to_mesh=require_matrix(mesh_world.inverted()@rig.matrix_world,invertible=True)
    rows=[]
    for point_id in point_ids:
        a,b=pre["points"][point_id],post["points"][point_id]
        if a["contributors"]!=b["contributors"]:
            raise ValueError("segment_fidelity_pre_post_full_weights_changed")
        point=require_vector(mesh_to_rig@Vector(a["co"]))
        displacement=Vector((0,0,0))
        contribution=0.0
        full=[]
        for record in a["contributors"]:
            item=dict(record)
            if record["native_eligible"]:
                if record["envelope_multiply"]:
                    raise ValueError("segment_fidelity_envelope_multiply_unsupported")
                pb=rig.pose.bones[record["group"]]
                transform,mapping=deform_bone_matrix(pb,point)
                delta=require_vector((require_matrix(transform)@point-point)*record["weight"])
                displacement+=delta
                require_vector(displacement)
                contribution+=record["weight"]
                item.update(mapping)
            full.append(item)
        # Native armature_deform.cc: aggregate contribution threshold, NEVER prune individual weights.
        if not math.isfinite(contribution):
            raise ValueError("segment_fidelity_contribution_nonfinite")
        result=require_vector(point+displacement/contribution if contribution>0.0001 else point.copy())
        predicted=require_vector(rig_to_mesh@result)
        actual=require_vector(Vector(b["co"]))
        mesh_error=(predicted-actual).length
        world_error=(require_vector(mesh_world@predicted)-require_vector(mesh_world@actual)).length
        if not math.isfinite(mesh_error) or not math.isfinite(world_error):
            raise ValueError("segment_fidelity_error_metric_nonfinite")
        rows.append({"point_id":point_id,"raw_vertex_index":point_id-1,"pre_mesh":a["co"],"native_post_mesh":b["co"],
            "cpu_post_mesh":list(predicted),"mesh_error":mesh_error,"world_error":world_error,
            "native_contribution_sum":contribution,"contributors":full})
    errors=[r["world_error"] for r in rows]
    return {"samples":rows,"sample_count":len(rows),"maximum_world_error":max(errors,default=0),
        "rms_world_error":math.sqrt(sum(v*v for v in errors)/len(errors)) if errors else 0,
        "tolerance_world_m":TOL,"passed":bool(rows) and max(errors)<=TOL}

def matrix_motion(a,b):
    return max(abs(x-y) for ma,mb in zip(a,b) for ra,rb in zip(ma,mb) for x,y in zip(ra,rb))

def key_values_equal(a,b):
    if a is None or b is None:
        return a is None and b is None
    ak,bk=list(a.key_blocks),list(b.key_blocks)
    return len(ak)==len(bk) and all(x.name==y.name and abs(float(x.value)-float(y.value))<=1e-6 for x,y in zip(ak,bk))

def verify_same_pre_input(a,b):
    from mathutils import Vector
    if set(a["points"])!=set(b["points"]) or a["id_topology_sha256"]!=b["id_topology_sha256"]:
        raise ValueError("segment_fidelity_duplicate_pre_stage_ids_differ")
    maximum=0.0
    for point_id,record in a["points"].items():
        other=b["points"][point_id]
        if record["contributors"]!=other["contributors"]:
            raise ValueError("segment_fidelity_duplicate_pre_stage_weights_differ")
        maximum=max(maximum,(Vector(record["co"])-Vector(other["co"])).length)
    if maximum>1e-7:
        raise ValueError("segment_fidelity_duplicate_pre_stage_coordinates_differ")
    return maximum

def restore_binding(bpy,native,rig,state):
    action=bpy.data.actions.get(state["action"])
    if action is None:
        raise ValueError("segment_fidelity_original_active_action_missing")
    slots=[s for s in action.slots if s.identifier==state["slot_identifier"]]
    if len(slots)!=1:
        raise ValueError("segment_fidelity_original_active_slot_missing")
    native.assign_action(rig,action,slots[0])
    bpy.context.scene.frame_set(state["frame"])
    bpy.context.view_layer.update()

def probe(bpy,native,natural,face,proof,soft,pair,helper,rig,body,producer,out,audit,path):
    from mathutils import Matrix,Vector
    modifiers=[m for m in body.modifiers if m.type=="ARMATURE"]
    audit["body_modifier_stack"]=[{"index":i,"name":m.name,"type":m.type,"viewport":m.show_viewport,"render":m.show_render}
        for i,m in enumerate(body.modifiers)]
    audit["actual_armature_flags"]=[armature_flags(body,m,rig) for m in modifiers]
    inventory=weight_inventory(body,rig)
    audit["body_positive_weight_inventory"]=inventory
    checkpoint(path,audit)
    active=[m for m in modifiers if m.show_viewport and m.object==rig]
    if len(active)!=1:
        raise ValueError("segment_fidelity_body_armature_target_not_unique")
    modifier=active[0]
    flags=armature_flags(body,modifier,rig)
    candidates=[r for r in inventory["weighted_bones"] if r["use_deform"] and r["segments"]>1]
    audit["weighted_segmented_bone_count"]=len(candidates)
    checkpoint(path,audit)
    if not candidates:
        raise ValueError("segment_fidelity_no_weighted_deforming_bbone")
    poses={}
    for clip,frame in SAMPLES:
        audit["active_probe"]={"phase":"weighted_bone_motion","clip":clip,"frame":frame}
        checkpoint(path,audit)
        select_action(native,proof,rig,bpy,producer,clip,frame)
        values={}
        for candidate in candidates:
            evaluated_rig=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            pb=evaluated_rig.pose.bones[candidate["bone"]]
            count=int(pb.bone.bbone_segments)
            indices=sorted(set((0,count//2,count)))
            matrices=[pb.matrix@pb.bbone_segment_matrix(index,rest=False) for index in indices]
            values[pb.name]=[[list(row) for row in matrix] for matrix in matrices]
        poses[clip]=values
    motion=[]
    for candidate in candidates:
        name=candidate["bone"]
        amount=max(matrix_motion(poses["idle"][name],poses[clip][name]) for clip in ("wave","celebrate"))
        motion.append({**candidate,"sampled_segment_matrix_max_delta":amount})
    motion.sort(key=lambda r:(-r["sampled_segment_matrix_max_delta"],r["bone"]))
    audit["weighted_moving_bone_candidates_first"]=motion[:12]
    selected=motion[0]
    audit["selected_weighted_bbone"]=selected
    unsupported=[]
    if not flags["supported_linear_cpu"]:
        unsupported.append("actual_modifier_flags_not_supported_by_linear_cpu")
    multiply=[r["bone"] for r in inventory["weighted_bones"] if r["use_deform"] and r["envelope_multiply"]]
    if multiply:
        unsupported.append("positive_weight_bone_envelope_multiply")
    audit["unsupported_reasons"]=unsupported
    audit["weighted_envelope_multiply_bones"]=multiply
    checkpoint(path,audit)
    if unsupported:
        raise ValueError("segment_fidelity_actual_native_deformation_mode_unsupported")
    if not math.isfinite(selected["sampled_segment_matrix_max_delta"]) or selected["sampled_segment_matrix_max_delta"]<=1e-6:
        raise ValueError("segment_fidelity_weighted_bbone_motion_not_observed")
    group_names={g.index:g.name for g in body.vertex_groups}
    weighted=[]
    for vertex in body.data.vertices:
        matching=[r for r in contributors(vertex,group_names,rig) if r["group"]==selected["bone"] and r["native_eligible"]]
        if matching:
            weighted.append((matching[0]["weight"],vertex.index+1))
    ids=[]
    audit["selected_point_ids"]=ids
    audit["selected_vertex_count"]=0
    audit["raw_positive_candidate_count"]=len(weighted)
    audit["selection_rule"]="up to 32 largest positive weights to the measured moving B-Bone; every positive contributor retained"
    checkpoint(path,audit)
    if not weighted:
        raise ValueError("segment_fidelity_selected_bbone_has_no_positive_vertices")
    original_ids=id_inventory(bpy)
    owned={"objects":[],"meshes":[],"keys":set()}
    original_signature=helper.garment_geometry_signature(body)
    original_error=None
    try:
        index=list(body.modifiers).index(modifier)
        pre=copy_probe_object(bpy,body,index,False,owned)
        post=copy_probe_object(bpy,body,index,True,owned)
        if helper.garment_geometry_signature(pre)!=original_signature or helper.garment_geometry_signature(post)!=original_signature:
            raise ValueError("segment_fidelity_duplicate_raw_or_key_data_differs")
        topology=raw_topology(body)
        audit["source_raw_id_topology_sha256"]=topology
        raw_count=len(body.data.vertices)
        audit["duplicate_only_isolation"]={"pre_modifier_count":len(pre.modifiers),"post_modifier_count":len(post.modifiers),
            "target_original_index":index,"point_id_attribute":TAG,"id_encoding":"raw vertex index + 1",
            "independent_mesh_and_key_data":True,"original_modifiers_edited":False}
        audit["frames"]=[]
        first_weights=None
        first_mappings=None
        first_post=None
        weights_stable=True
        indices_stable=True
        maximum_blend_change=0.0
        maximum_native_point_motion=0.0
        for clip,frame in SAMPLES:
            audit["active_probe"]={"phase":"duplicate_isolation","clip":clip,"frame":frame}
            checkpoint(path,audit)
            select_action(native,proof,rig,bpy,producer,clip,frame)
            if not key_values_equal(body.data.shape_keys,pre.data.shape_keys) or not key_values_equal(body.data.shape_keys,post.data.shape_keys):
                raise ValueError("segment_fidelity_duplicate_native_key_values_differ")
            before=snapshot_duplicate(bpy,pre,rig,raw_count,None,audit,clip+"_pre",path)
            if not ids:
                retained=[]
                for point_id,record in before["points"].items():
                    for item in record["contributors"]:
                        if item["group"]==selected["bone"] and item["native_eligible"]:
                            retained.append((item["weight"],point_id))
                ids=[point_id for weight,point_id in sorted(retained,key=lambda r:(-r[0],r[1]))[:32]]
                audit["selected_point_ids"]=ids
                audit["selected_vertex_count"]=len(ids)
                checkpoint(path,audit)
                if not ids:
                    raise ValueError("segment_fidelity_no_retained_weighted_sample_vertices")
            if any(i not in before["points"] for i in ids):
                raise ValueError("segment_fidelity_selected_point_not_retained_in_pre_stage")
            post_modifier=post.modifiers[index]
            if armature_flags(post,post_modifier,rig)["supported_linear_cpu"] is not True:
                raise ValueError("segment_fidelity_duplicate_armature_flags_differ")
            post_modifier.show_viewport=False
            try:
                bpy.context.view_layer.update()
                same_pre=snapshot_duplicate(bpy,post,rig,raw_count,before["id_topology_sha256"],audit,clip+"_post_armature_disabled",path)
            finally:
                post_modifier.show_viewport=True
                bpy.context.view_layer.update()
            same_residual=verify_same_pre_input(before,same_pre)
            after=snapshot_duplicate(bpy,post,rig,raw_count,before["id_topology_sha256"],audit,clip+"_post",path)
            if set(before["points"])!=set(after["points"]):
                raise ValueError("segment_fidelity_armature_changed_retained_point_ids")
            source_world=body.matrix_world
            if (proof.matrix_error(Matrix(before["matrix_world"]),source_world)>1e-7
                    or proof.matrix_error(Matrix(after["matrix_world"]),source_world)>1e-7):
                raise ValueError("segment_fidelity_mesh_world_spaces_differ")
            evaluated_rig=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            result=cpu_compare(evaluated_rig,source_world,before,after,ids)
            result.update({"clip":clip,"frame":frame,"pre_stage_input_max_residual":same_residual,
                "pre_id_topology_sha256":before["id_topology_sha256"],"post_id_topology_sha256":after["id_topology_sha256"]})
            current_weights={r["point_id"]:[(v["group_index"],v["group"],v["weight"],v["native_eligible"])
                for v in r["contributors"]] for r in result["samples"]}
            mappings={(r["point_id"],v["group"]):(v["segment_index"],v["blend_next"])
                for r in result["samples"] for v in r["contributors"] if v["native_eligible"] and v["segments"]>1}
            if first_weights is None:
                first_weights=current_weights
                first_mappings=mappings
                first_post={i:after["points"][i]["co"] for i in ids}
            else:
                weights_stable=weights_stable and current_weights==first_weights
                if set(mappings)!=set(first_mappings):
                    indices_stable=False
                for key,value in mappings.items():
                    reference=first_mappings.get(key)
                    if reference is None or value[0]!=reference[0]:
                        indices_stable=False
                    if reference is not None:
                        maximum_blend_change=max(maximum_blend_change,abs(value[1]-reference[1]))
                maximum_native_point_motion=max(maximum_native_point_motion,
                    max((Vector(after["points"][i]["co"])-Vector(first_post[i])).length for i in ids))
            result["including_temporary_driver_invalid_count"]=soft.driver_summary(helper,bpy)["active_invalid"]
            # Temporary Key drivers are present until cleanup; no claim about original-only global counts here.
            audit["frames"].append(result)
            checkpoint(path,audit)
            if not result["passed"]:
                raise ValueError("segment_fidelity_cpu_native_error_exceeded")
        audit["observed_static_full_weights"]=weights_stable
        audit["observed_segment_indices_stable"]=indices_stable
        audit["observed_segment_blend_max_change"]=maximum_blend_change
        audit["observed_segment_mapping_stable"]=indices_stable and maximum_blend_change<=1e-6
        audit["selected_native_vertex_motion_mesh_m"]=maximum_native_point_motion
        audit["static_export_weights_approved"]=False
        if maximum_native_point_motion<=1e-6:
            raise ValueError("segment_fidelity_selected_native_mesh_motion_not_observed")
        audit["sampled_linear_fidelity_passed"]=True
    except Exception as error:
        original_error=error
        raise
    finally:
        try:
            cleanup_owned(bpy,owned,original_ids)
            audit["temporary_ids_removed"]=id_inventory(bpy)==original_ids
            checkpoint(path,audit)
            if not audit["temporary_ids_removed"]:
                raise ValueError("segment_fidelity_temporary_id_inventory_not_restored")
        except Exception as cleanup_error:
            if original_error is None:
                raise
            audit["temporary_cleanup_error_type"]=type(cleanup_error).__name__[:80]
            print("SNOW_SEGMENT_FIDELITY_TEMP_CLEANUP_FAILED "+json.dumps({"error_type":type(cleanup_error).__name__[:80]}),flush=True)

def main():
    parser=argparse.ArgumentParser()
    for name in ("source-root","derivative-blend","config","out"):
        parser.add_argument("--"+name,required=True)
    args=parser.parse_args()
    root=Path(args.source_root).resolve(strict=True)
    source=root/"snow/original/Snow/snow_v4.2.blend"
    candidate=Path(args.derivative_blend).resolve(strict=True)
    producer_file=candidate.with_name("native-clips-audit.json")
    out=Path(args.out).resolve()
    if out.is_relative_to(root) or out.is_relative_to(candidate.parent) or source.is_relative_to(out) or candidate.is_relative_to(out):
        raise ValueError("segment_fidelity_output_overlaps_input")
    if sha(source)!=SOURCE_SHA or sha(candidate)!=INPUT_SHA or candidate.stat().st_size!=INPUT_BYTES:
        raise ValueError("segment_fidelity_frozen_input_hash_mismatch")
    config_raw=Path(args.config).read_bytes()
    if blob(config_raw)!=CONFIG_BLOB:
        raise ValueError("segment_fidelity_config_hash_mismatch")
    config=json.loads(config_raw)
    if config["poses"]!={"neutral":[]} or producer_file.stat().st_size>2097152:
        raise ValueError("segment_fidelity_config_or_producer_size_mismatch")
    producer=json.loads(producer_file.read_text(encoding="utf-8"))
    if (producer["source_sha256"]!=SOURCE_SHA or producer["input_sha256"]!=PARENT_SHA
            or producer["derivative"]["sha256"]!=INPUT_SHA or producer["derivative"]["bytes"]!=INPUT_BYTES
            or producer["derivative"]["file"]!="snow-native-clips-candidate.blend"
            or not all(producer[k] for k in ("numeric_native_clip_candidate_verified","reopen_verification_passed",
                "preservation_passed","candidate_completed"))):
        raise ValueError("segment_fidelity_native_producer_identity_mismatch")
    out.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        file=out/"credits"/relative
        file.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/relative,file)
        credits.append({"file":str(file.relative_to(out)),"bytes":file.stat().st_size,"sha256":sha(file)})
    audit={"purpose":"One actually weighted moving Snow body B-Bone; duplicate-only sampled native linear fidelity",
        "source_sha256":SOURCE_SHA,"input_sha256":INPUT_SHA,"input_bytes":INPUT_BYTES,
        "producer_sha256":sha(producer_file),"producer_parent_input_sha256":PARENT_SHA,
        "reviewed_native_functions_blob":NATIVE_BLOB,"credits":credits,"used_textures":[],
        "renders":0,"models_saved":0,"glb_exports":0,"geometry_edits_to_input":False,
        "input_driver_mute_or_action_detach_performed":False,"static_export_weights_approved":False,
        "overall_art_approved":False,"browser_animation_approved":False,"production_glb_approved":False,
        "limits":["One body B-Bone and at most 32 selected retained vertices across idle0/wave24/celebrate24.",
            "All positive contributors retained; aggregate native contribution >0.0001 threshold only.",
            "CPU comparison requires actual linear vertex-group skinning; no DQ/envelope/mask/multi override.",
            "Stable POINT/INT IDs checked at each evaluated stage; legitimate upstream retained subsets are reported.",
            "Pre/post comparison isolates this Armature only, not downstream CorrectiveSmooth/Mask/Subdivision/render.",
            "B-Bone index/blend stability is measured at three poses only; no static export-weight proof.",
            "Public ordinary-bone matrix equivalence is tested by native comparison, not assumed export fidelity.",
            "Source/file IDs preserved after temporary object/Mesh/Key cleanup and original action/frame restoration."]}
    path=out/"segment-fidelity-audit.json"
    checkpoint(path,audit)
    failure=None
    rig=None
    initial_binding=None
    initial_ids=None
    initial_invariants=None
    modules=None
    source_actions=None
    def file_recheck():
        count=0
        match=True
        for record in audit["used_textures"]:
            for item in record["files"]:
                file=source.parent/"textures"/item["file"]
                count+=1
                match=match and file.is_file() and sha(file)==item["sha256"]
        expected=audit.get("expected_texture_images")
        ready=sum(r.get("size_guard_passed",False) for r in audit["used_textures"])
        complete=(expected is not None and expected>0 and expected==len(audit["used_textures"])==ready
            and count==audit.get("expected_texture_files") and count>0)
        audit["file_hash_recheck"]={"source_unchanged":sha(source)==SOURCE_SHA,
            "candidate_unchanged":sha(candidate)==INPUT_SHA,"producer_unchanged":sha(producer_file)==audit["producer_sha256"],
            "texture_checked_files":count,"texture_expected_files":audit.get("expected_texture_files"),
            "texture_ready_images":ready,"texture_expected_images":expected,"texture_complete":complete,
            "all_checked_textures_unchanged":match if count else None}
        return all(audit["file_hash_recheck"][k] for k in ("source_unchanged","candidate_unchanged","producer_unchanged")) and complete and match
    try:
        modules=load_reviewed()
        native,natural,face,proof,soft,pair,helper=modules
        import bpy
        if sys.version_info[:2]!=(3,11) or tuple(bpy.app.version)!=(4,5,9):
            raise ValueError("requires_verified_python_3_11_bpy_4_5_9")
        bpy.context.preferences.filepaths.use_scripts_auto_execute=False
        bpy.ops.wm.open_mainfile(filepath=str(candidate),load_ui=False,use_scripts=False)
        rig=bpy.data.objects.get("RIG-Snow")
        body=bpy.data.objects.get("GEO-snow-body")
        if rig is None or rig.type!="ARMATURE" or rig.data.pose_position!="POSE" or body is None or body.type!="MESH":
            raise ValueError("segment_fidelity_saved_rig_or_body_missing")
        ad=rig.animation_data
        if ad is None or ad.action is None or ad.action_slot is None or len(ad.nla_tracks)!=0:
            raise ValueError("segment_fidelity_initial_action_slot_missing")
        initial_binding={"action":ad.action.name,"slot_identifier":ad.action_slot.identifier,
            "frame":int(bpy.context.scene.frame_current)}
        audit["initial_binding"]=initial_binding
        audit["saved_native_policy_preserved_without_detach"]=True
        scene=bpy.context.scene
        materials=pair.used_materials([o for o in scene.objects if o.type=="MESH" and not o.hide_render])
        images=pair.collect_images(materials)
        references={r["image"]:r for r in producer["used_textures"]}
        if len(references)!=len(producer["used_textures"]) or not images:
            raise ValueError("segment_fidelity_texture_manifest_invalid")
        expected_files=0
        for image in images:
            reference=references.get(image.name)
            filename=str(image.filepath).replace("\\","/").split("/")[-1]
            if reference is None or image.source!=reference["source"] or filename!=reference["filename"] or not reference["size_guard_passed"]:
                raise ValueError("segment_fidelity_used_texture_identity_mismatch")
            expected_files+=len(reference["files"])
        audit["expected_texture_images"]=len(images)
        audit["expected_texture_files"]=expected_files
        material_graph_before_reload=proof.material_graph_hash(bpy,pair)
        pair.relink_and_reload(images,source.parent/"textures",audit["used_textures"],lambda:checkpoint(path,audit))
        for record in audit["used_textures"]:
            if record["files"]!=references[record["image"]]["files"]:
                raise ValueError("segment_fidelity_used_texture_hash_mismatch")
        audit["material_graph_before_verified_relink"]=material_graph_before_reload
        audit["material_graph_after_verified_relink"]=proof.material_graph_hash(bpy,pair)
        audit["verified_texture_path_relink_intentional"]=True
        # Immutable full graph baseline is captured AFTER trusted path/buffer relink and file guards.
        if not file_recheck():
            raise ValueError("segment_fidelity_initial_file_verification_failed")
        source_actions=[a.name for a in bpy.data.actions]
        initial_ids=id_inventory(bpy)
        initial_invariants=native.invariants(bpy,natural,face,proof,soft,pair,helper,rig,source_actions)
        audit["input_id_counts"]={k:len(v) for k,v in initial_ids.items()}
        audit["input_action_count"]=len(source_actions)
        audit["input_native_clip_names"]={clip:producer["clips"][clip]["action_descriptor"]["action"] for clip,frame in SAMPLES}
        audit["input_preservation_before"]=initial_invariants
        audit["input_driver_before"]=soft.driver_summary(helper,bpy)
        audit["input_key_count_before"]=len(proof.key_values(bpy))
        checkpoint(path,audit)
        if audit["input_driver_before"]["active_invalid"]!=0:
            raise ValueError("segment_fidelity_input_native_driver_invalid")
        probe(bpy,native,natural,face,proof,soft,pair,helper,rig,body,producer,out,audit,path)
        audit["probe_completed"]=True
    except Exception as error:
        failure=error
        code=error.args[0] if isinstance(error,ValueError) and len(error.args)==1 and isinstance(error.args[0],str) else None
        if not code or len(code)>100 or not all(c.islower() or c=="_" for c in code):
            code=None
        audit["failure"]={"error_type":type(error).__name__,"error_code":code}
        raise
    finally:
        try:
            if rig is not None and initial_binding is not None and modules is not None:
                native,natural,face,proof,soft,pair,helper=modules
                restore_binding(bpy,native,rig,initial_binding)
                audit["original_action_slot_frame_restored"]=(rig.animation_data.action.name==initial_binding["action"]
                    and rig.animation_data.action_slot.identifier==initial_binding["slot_identifier"]
                    and int(bpy.context.scene.frame_current)==initial_binding["frame"])
                if initial_ids is not None and initial_invariants is not None:
                    audit["input_id_inventory_preserved"]=id_inventory(bpy)==initial_ids
                    after=native.invariants(bpy,natural,face,proof,soft,pair,helper,rig,source_actions)
                    audit["input_preservation_after"]=after
                    audit["input_preservation_passed"]=after==initial_invariants
                    audit["input_driver_after"]=soft.driver_summary(helper,bpy)
                    audit["input_key_count_after"]=len(proof.key_values(bpy))
            readonly=file_recheck()
            final=(readonly and audit.get("original_action_slot_frame_restored",False)
                and audit.get("input_id_inventory_preserved",False) and audit.get("input_preservation_passed",False)
                and audit.get("input_driver_after",{}).get("active_invalid") == 0)
            audit["readonly_and_cleanup_passed"]=final
            audit["proof_completed"]=failure is None and final and audit.get("sampled_linear_fidelity_passed",False)
            checkpoint(path,audit)
            marker={"proof_completed":audit["proof_completed"],"failure":audit.get("failure"),"active_probe":audit.get("active_probe"),
                "actual_armature_flags":audit.get("actual_armature_flags"),"unsupported_reasons":audit.get("unsupported_reasons"),
                "selected_weighted_bbone":audit.get("selected_weighted_bbone"),"selected_vertex_count":audit.get("selected_vertex_count",0),
                "body_weight_summary":{k:audit.get("body_positive_weight_inventory",{}).get(k) for k in (
                    "vertices","positive_entries","positive_contributor_histogram","maximum_positive_contributors")},
                "frames":[{k:r.get(k) for k in ("clip","frame","sample_count","maximum_world_error","rms_world_error","passed",
                    "pre_stage_input_max_residual","pre_id_topology_sha256","post_id_topology_sha256")} for r in audit.get("frames",[])],
                "id_mapping_checks":audit.get("id_mapping_checks",[]),
                "observed_static_full_weights":audit.get("observed_static_full_weights"),
                "observed_segment_mapping_stable":audit.get("observed_segment_mapping_stable"),
                "observed_segment_blend_max_change":audit.get("observed_segment_blend_max_change"),
                "selected_native_vertex_motion_mesh_m":audit.get("selected_native_vertex_motion_mesh_m"),
                "temporary_ids_removed":audit.get("temporary_ids_removed"),"original_binding_restored":audit.get("original_action_slot_frame_restored"),
                "input_id_inventory_preserved":audit.get("input_id_inventory_preserved"),"input_preservation_passed":audit.get("input_preservation_passed"),
                "input_driver_before":audit.get("input_driver_before"),"input_driver_after":audit.get("input_driver_after"),
                "input_key_counts":[audit.get("input_key_count_before"),audit.get("input_key_count_after")],
                "file_hash_recheck":audit.get("file_hash_recheck"),"readonly_and_cleanup_passed":final,
                "renders":0,"models_saved":0,"glb_exports":0,"static_export_weights_approved":False,
                "overall_art_approved":False,"browser_animation_approved":False,"production_glb_approved":False}
            if len(encoded(marker))>24000:
                raise ValueError("segment_fidelity_stdout_byte_budget_exceeded")
            print("SNOW_SEGMENT_FIDELITY_PROOF "+encoded(marker).decode().strip(),flush=True)
            if failure is None and not final:
                raise ValueError("segment_fidelity_final_input_preservation_failed")
        except Exception as cleanup_error:
            if failure is None:
                raise
            audit["final_cleanup_error_type"]=type(cleanup_error).__name__[:80]
            try:
                checkpoint(path,audit)
            except Exception:
                pass
            print("SNOW_SEGMENT_FIDELITY_CLEANUP_FAILED "+json.dumps({"error_type":type(cleanup_error).__name__[:80]}),flush=True)

if __name__=="__main__":
    main()
