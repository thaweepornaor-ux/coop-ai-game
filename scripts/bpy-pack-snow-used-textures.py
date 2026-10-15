"""Pack only verified used Snow textures, then prove embedded decode in a fresh process.
No geometry, pose authoring, rendering, GLB/PBR conversion or full-scene portability claim.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import traceback
import numpy as np

BASE_BLOB="cd7c8bd2fc7d4e4c6507808b3b4b3e1dbfa34b25"
SOURCE_SHA="80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
INPUT_SHA="b22306981a809bdb2e537c52087efe8d503bc30a0efe73573a51bb6200aeffa3"
INPUT_BYTES=8297412
PRODUCER_SHA="5c271962723af2b09bf331bd85d7f6e363f5334df6256265ee3ee4c983410518"
CONFIG_BLOB="f0612039b320e8dac77587ec4aecdc2c84618843"
WHEEL_SHA="0bca32fe0658388f5ef669631220d7147fc2544bb0103a0042603519552b6b6a"
SOURCE_ZIP_SHA="1d6054aad6deccaff326f750ec82bba75bee83c4253e4dcb75da6ce842d503d8"
FILE_CAP=32*1024*1024
BLEND_CAP=128*1024*1024
PART_BYTES=64*1024*1024
JSON_CAP=1024*1024
PACK_BYTES=97102085
DRIVER_VALUE_TOL=1e-4

def require(condition,code):
    if not condition:
        raise ValueError("packed_native_"+code)

def encoded(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n").encode("utf-8")

def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def sha(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file,"sha256").hexdigest()

def blob(path):
    raw=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def write_json(path,value):
    payload=encoded(value)
    require(len(payload)<=JSON_CAP,"json_budget")
    Path(path).write_bytes(payload)

def load_modules():
    path=Path(__file__).with_name("bpy-prototype-snow-glb-correctives.py")
    require(blob(path)==BASE_BLOB,"base_helper_pin")
    spec=importlib.util.spec_from_file_location("packed_reviewed_base",path)
    base=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    modules=(base,*base.load_reviewed())
    for filename,pin in (("bpy-proof-snow-bent-elbows.py","49ca4d50be3a2c03300db2fa47980104f27455ab"),
            ("bpy-prototype-snow-crewneck.py","059fad9611e95ece356ff6911a9de879dcb3d363")):
        require(blob(Path(__file__).with_name(filename))==pin,"transitive_helper_pin")
    return modules

def validate_runtime(bpy):
    require(sys.version_info[:2]==(3,11) and tuple(bpy.app.version)==(4,5,9)
        and np.__version__=="1.26.4","runtime_version")
    runtime=Path("bpy-proof/bpy-runtime.json")
    require(runtime.is_file() and runtime.stat().st_size<=JSON_CAP,"runtime_report")
    data=json.loads(runtime.read_text())
    require(data["ok"] and data["wheel_sha256"]==WHEEL_SHA and not data["autoexec_enabled"]
        and data["blender_version"].startswith("4.5.9"),"runtime_pin")
    require(not bpy.context.preferences.filepaths.use_scripts_auto_execute,"autoexec")

def binding_state(bpy,rig):
    ad=rig.animation_data
    require(ad is not None and ad.action is not None and ad.action_slot is not None
        and len(ad.nla_tracks)==0,"binding_layout")
    return {"action":ad.action.name,"slot_identifier":ad.action_slot.identifier,
        "frame":int(bpy.context.scene.frame_current),"subframe":float(bpy.context.scene.frame_subframe)}

def bind_reference(bpy,native,rig):
    action=bpy.data.actions.get("COOP_SNOW_NATIVE_IDLE_CANDIDATE")
    require(action is not None,"idle_action_missing")
    slots=[s for s in action.slots if s.identifier=="OBRIG-Snow"]
    require(len(slots)==1,"idle_slot_missing")
    native.assign_action(rig,action,slots[0])
    bpy.context.scene.frame_set(0,subframe=0.0)
    bpy.context.view_layer.update()
    return binding_state(bpy,rig)

def restore_binding(bpy,native,rig,state):
    action=bpy.data.actions.get(state["action"])
    require(action is not None,"saved_action_missing")
    slots=[s for s in action.slots if s.identifier==state["slot_identifier"]]
    require(len(slots)==1,"saved_slot_missing")
    native.assign_action(rig,action,slots[0])
    bpy.context.scene.frame_set(state["frame"],subframe=state["subframe"])
    bpy.context.view_layer.update()
    require(binding_state(bpy,rig)==state,"binding_restore")

def used_images(bpy,pair):
    objects=[o for o in bpy.context.scene.objects if o.type=="MESH" and not o.hide_render]
    return sorted(pair.collect_images(pair.used_materials(objects)),key=lambda image:image.name)

def driver_records(bpy):
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
                for fc in ad.drivers:
                    d=fc.driver
                    variables=[]
                    for v in d.variables:
                        targets=[]
                        for t in v.targets:
                            target={}
                            for field in ("bone_target","data_path","transform_type","transform_space",
                                    "rotation_mode","context_property","id_type","use_fallback_value","fallback_value"):
                                val=getattr(t,field,None)
                                if isinstance(val,(str,int,float,bool)):
                                    target[field]=val
                            pointer=getattr(t,"id",None)
                            target["id"]=None if pointer is None else [pointer.bl_rna.identifier,pointer.name]
                            targets.append(target)
                        variables.append({"name":v.name,"type":v.type,"targets":targets})
                    mods=[]
                    for mod in fc.modifiers:
                        values={}
                        for prop in mod.bl_rna.properties:
                            if prop.identifier=="rna_type" or prop.type in ("POINTER","COLLECTION"):
                                continue
                            val=getattr(mod,prop.identifier)
                            if isinstance(val,(str,bool,int,float)):
                                values[prop.identifier]=val
                            elif prop.is_array:
                                values[prop.identifier]=list(val)
                        mods.append({"type":mod.type,"properties":values})
                    resolved=item.path_resolve(fc.data_path)
                    if isinstance(resolved,(float,int,bool)):
                        value=float(resolved)
                        require(fc.array_index==0,"scalar_driver_index")
                    else:
                        value=float(resolved[fc.array_index])
                    require(math.isfinite(value),"driver_value_nonfinite")
                    record={"owner":[item.bl_rna.identifier,item.name],"path":fc.data_path,
                        "index":int(fc.array_index),"mute":bool(fc.mute),"type":d.type,
                        "expression":d.expression,"use_self":bool(d.use_self),
                        "variables":variables,"modifiers":mods}
                    records.append((record,value))
    records.sort(key=lambda row:(row[0]["owner"],row[0]["path"],row[0]["index"]))
    return records

def numeric_values(bpy,modules,rig):
    base,native,natural,face,proof,soft,pair,helper=modules
    values={"drivers":[v for record,v in driver_records(bpy)],"keys":proof.key_values(bpy),
        "face":native.held_face_state(proof,rig)}
    encoded(values)
    return values

def compare_values(actual,expected):
    require(len(actual["drivers"])==len(expected["drivers"])>0,"driver_value_count")
    require(len(actual["keys"])==len(expected["keys"])>0,"key_value_count")
    require([(r["data"],r["key"]) for r in actual["keys"]]==
        [(r["data"],r["key"]) for r in expected["keys"]],"key_value_identity")
    driver_error=max(abs(a-b) for a,b in zip(actual["drivers"],expected["drivers"]))
    key_error=max(abs(a["value"]-b["value"]) for a,b in zip(actual["keys"],expected["keys"]))
    face_error=max(abs(actual["face"]["properties"][s][k]-expected["face"]["properties"][s][k])
        for s in ("L","R") for k in ("Up","Wide"))
    jaw_error=float(np.max(np.abs(np.asarray(actual["face"]["jaw_matrix"])-
        np.asarray(expected["face"]["jaw_matrix"]))))
    report={"driver_count":len(actual["drivers"]),"key_count":len(actual["keys"]),
        "maximum_driver_value_abs_difference":driver_error,"driver_value_tolerance":DRIVER_VALUE_TOL,
        "maximum_native_key_value_abs_difference":key_error,"key_values_finite_in_rna_hard_range":True,
        "maximum_face_up_wide_abs_difference":face_error,"maximum_jaw_component_difference":jaw_error,
        "raw_held_face_channels_equal":actual["face"]["channels"]==expected["face"]["channels"],
        "native_key_values_not_coordinate_data":True}
    report["passed"]=(driver_error<=DRIVER_VALUE_TOL and face_error<=1e-4 and jaw_error<=1e-6
        and report["raw_held_face_channels_equal"])
    require(all(math.isfinite(x) for x in (driver_error,key_error,face_error,jaw_error)),"comparison_nonfinite")
    return report

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
        "driver_policy_sha256":hashlib.sha256(encoded(sorted(records))).hexdigest(),
        "action_detach_calls":0,"driver_mute_writes":0,"embedded_text_executed":False}
    if report["autoexec_enabled"] or report["non_native_unmuted"] or report["muted"]:
        raise ValueError("packed_native_saved_policy_unsupported")
    return report


def material_graph_without_image_paths(bpy,pair):
    trees,seen=[],set()
    def visit(tree):
        if tree is None or tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        nodes=[]
        for node in tree.nodes:
            if node.type=="SCRIPT":
                raise ValueError("script_shader_not_allowed")
            data={"name":node.name,"type":node.bl_idname,
                "inputs":[{"id":s.identifier,"linked":s.is_linked,"value":pair.primitive_default(s)}
                          for s in node.inputs]}
            for key in ("operation","blend_type","data_type","uv_map","space","invert",
                        "interpolation","projection","extension"):
                value=getattr(node,key,None)
                if isinstance(value,(str,bool,int,float)):
                    data[key]=value
            image=getattr(node,"image",None)
            if image:
                data["image"]={"name":image.name,"filepath":None,
                    "colorspace":image.colorspace_settings.name,"alpha_mode":image.alpha_mode}
            child=getattr(node,"node_tree",None)
            if child:
                data["group"]=child.name
                visit(child)
            nodes.append(data)
        trees.append({"name":tree.name,"nodes":sorted(nodes,key=lambda v:v["name"]),
            "links":sorted([l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier]
                           for l in tree.links)})
    materials=[]
    for material in bpy.data.materials:
        materials.append({"name":material.name,"use_nodes":material.use_nodes,
                          "diffuse_color":list(material.diffuse_color)})
        visit(material.node_tree)
    for world in bpy.data.worlds:
        visit(world.node_tree)
    for light in bpy.data.lights:
        visit(light.node_tree)
    return digest({"materials":sorted(materials,key=lambda v:v["name"]),
                   "node_trees":sorted(trees,key=lambda v:v["name"])})



def capture_state(bpy,modules,rig,action_names):
    base,native,natural,face,proof,soft,pair,helper=modules
    current_names=sorted(a.name for a in bpy.data.actions)
    require(current_names==sorted(action_names),"action_inventory")
    invariants=native.invariants(bpy,natural,face,proof,soft,pair,helper,rig,action_names)
    # Exact copy of reviewed graph snapshot, replacing ONLY image filepath with None.
    # Each used image path is checked separately against the explicit intentional missing path.
    invariants["materials"]=material_graph_without_image_paths(bpy,pair)
    policy=saved_native_policy(bpy)
    summary=soft.driver_summary(helper,bpy)
    require(summary["active_invalid"]==0 and summary["muted"]==0 and summary["count"]==1291
        and policy["driver_count"]==1291,"native_driver_status")
    defs=driver_records(bpy)
    keys=proof.key_values(bpy)
    image_names={image.name for image in used_images(bpy,pair)}
    held=native.held_face_state(proof,rig)
    return {"stable_inventory":{kind:sorted(item.name for item in getattr(bpy.data,kind))
            for kind in ("objects","meshes","shape_keys","actions")},
        "invariants":invariants,"native_policy":policy,"driver_status":summary,
        "driver_definition_sha256":digest([r for r,v in defs]),
        "key_count":len(keys),"held_control_channels_sha256":digest(held["channels"]),
        "unpacked_image_paths":{image.name:image.filepath for image in bpy.data.images if image.name not in image_names},
        "binding":binding_state(bpy,rig),
        "material_graph_exception":"Only filepath field intentionally omitted; packed/unused paths checked separately"}

def closure_report(bpy,pair,images):
    objects=[o for o in bpy.context.scene.objects if o.type=="MESH" and not o.hide_render]
    materials=pair.used_materials(objects)
    visited=set()
    dependencies=[]
    def check(block):
        if block is None:
            return
        key=(block.bl_rna.identifier,block.name,int(block.as_pointer()))
        if key in visited:
            return
        visited.add(key)
        require(getattr(block,"library",None) is None and getattr(block,"override_library",None) is None,
            "referenced_linked_or_override_id")
        dependencies.append([block.bl_rna.identifier,block.name])
    def visit(tree):
        if tree is None or ("tree",int(tree.as_pointer())) in visited:
            return
        visited.add(("tree",int(tree.as_pointer())))
        check(tree)
        for node in tree.nodes:
            require(node.type!="SCRIPT","script_shader")
            for prop in node.bl_rna.properties:
                if prop.type=="STRING" and prop.subtype in ("FILE_PATH","DIR_PATH"):
                    require(not getattr(node,prop.identifier),"unsupported_node_external_path")
            child=getattr(node,"node_tree",None)
            if child:
                visit(child)
            check(getattr(node,"image",None))
    for obj in objects:
        check(obj);check(obj.data)
        for modifier in obj.modifiers:
            require(getattr(modifier,"cache_file",None) is None,"referenced_cache_file")
    for mat in materials:
        check(mat);visit(mat.node_tree)
    for image in images:
        check(image)
    return {"render_mesh_material_image_closure_checked":True,"referenced_ids":sorted(dependencies),
        "libraries_present":[library.filepath for library in bpy.data.libraries],
        "full_scene_portable":False,
        "scope":"Declared render-visible mesh material image closure only; other scene dependency classes not certified",
        "unproved_classes":["world/light/compositor and nonimage scene external-resource closure"]}

def image_identity(image):
    require(image.source in ("FILE","TILED") and not image.is_dirty and not image.use_multiview,
        "image_source_dirty_or_multiview")
    require(image.library is None and image.override_library is None,"image_linked_or_override")
    return {"name":image.name,"source":image.source,"colorspace":image.colorspace_settings.name,
        "alpha_mode":image.alpha_mode,"tiles":sorted(int(tile.number) for tile in image.tiles)}

def buffer_descriptor(image,tile_number):
    if image.source=="TILED":
        matching=[tile for tile in image.tiles if int(tile.number)==tile_number]
        require(len(matching)==1,"tile_missing_or_duplicate")
        tile=matching[0]
        size=list(tile.size)  # This getter actually acquires ImageUser.tile=tile_number.
        channels=int(tile.channels)
    else:
        size=list(image.size)  # Positive acquisition BEFORE has_data.
        channels=int(image.channels)
        require(image.has_data,"file_image_buffer")
    require(len(size)==2 and all(isinstance(v,int) and 0<v<=8192 for v in size)
        and 1<=channels<=4,"image_buffer_dimensions_or_channels")
    return size,channels

def prepare_image_rows(bpy,images,producer,texture_root,missing_root):
    references={record["image"]:record for record in producer["used_textures"]}
    require(len(references)==len(producer["used_textures"])==len(images)==22,"image_manifest_count")
    require(not missing_root.exists() and missing_root.is_absolute(),"missing_root_exists")
    rows=[]
    seen=set()
    total=0
    for image in images:
        identity=image_identity(image)
        require(len(image.packed_files)==0,"input_image_already_packed")
        ref=references.get(image.name)
        filename=str(image.filepath).replace("\\","/").split("/")[-1]
        require(ref is not None and ref["source"]==image.source and filename==ref["filename"]
            and ref["size_guard_passed"],"image_manifest_identity")
        require(filename not in ("",".","..") and "/" not in filename and "\\" not in filename,
            "image_filename")
        require((image.source=="TILED")==("<UDIM>" in filename),"image_udim_pattern")
        require(image_identity(image)["tiles"] and
            (image.source=="TILED" or image_identity(image)["tiles"]==[1001]),"image_tile_layout")
        expected_files={f["file"]:f for f in ref["files"]}
        require(len(expected_files)==len(ref["files"]),"duplicate_image_source_file")
        files=[]
        for tile in identity["tiles"]:
            concrete=filename.replace("<UDIM>",str(tile))
            f=expected_files.get(concrete)
            require(f is not None and concrete not in seen,"image_tile_file_correspondence")
            path=(texture_root/concrete).resolve(strict=True)
            require(path.parent==texture_root and path.is_file() and not path.is_symlink()
                and 0<path.stat().st_size<=FILE_CAP and path.stat().st_size==f["bytes"]
                and sha(path)==f["sha256"],"source_texture_pin")
            size,channels=buffer_descriptor(image,tile)
            require(not image.is_dirty,"decoded_source_became_dirty")
            seen.add(concrete);total+=f["bytes"]
            files.append({"view":0,"tile_number":tile,"file":concrete,"bytes":f["bytes"],
                "sha256":f["sha256"],"size":size,"channels":channels,
                "missing_path":str(missing_root/concrete)})
        require(len(files)==len(expected_files),"image_file_coverage")
        rows.append({**identity,"missing_pattern":str(missing_root/filename),"files":files})
    require(len(seen)==30 and total==PACK_BYTES and
        sum(r["source"]=="FILE" for r in rows)==18 and sum(r["source"]=="TILED" for r in rows)==4,
        "texture_total_preflight")
    return rows

def packed_state(bpy,images,expected_rows,missing_root,decode=False):
    missing_root=Path(missing_root)
    require(missing_root.is_absolute() and not missing_root.exists(),"isolation_root_not_absent")
    require([im.name for im in images]==[r["name"] for r in expected_rows],"packed_image_inventory")
    records=[];file_buffers=tile_buffers=total=0
    for image,row in zip(images,expected_rows):
        identity=image_identity(image)
        require(identity=={k:row[k] for k in identity},"packed_image_metadata")
        require(image.filepath_raw==row["missing_pattern"] and
            Path(row["missing_pattern"]).parent==missing_root,"missing_image_path_metadata")
        entries={}
        for entry in image.packed_files:
            key=(int(entry.view),int(entry.tile_number))
            require(key not in entries,"duplicate_packed_entry")
            entries[key]=entry
        require(set(entries)=={(f["view"],f["tile_number"]) for f in row["files"]},"packed_entry_coverage")
        for f in row["files"]:
            require(Path(f["missing_path"]).parent==missing_root and not Path(f["missing_path"]).exists(),
                "external_source_not_absent")
            entry=entries[(f["view"],f["tile_number"])]
            require(entry.filepath==f["missing_path"],"packed_entry_missing_path")
            packed=entry.packed_file
            require(packed is not None and packed.size==f["bytes"] and 0<packed.size<=FILE_CAP,
                "packed_entry_bytes")
            data=packed.data
            require(isinstance(data,bytes) and len(data)==f["bytes"]
                and hashlib.sha256(data).hexdigest()==f["sha256"],"packed_bytes_sha")
            del data
            if decode:
                size,channels=buffer_descriptor(image,f["tile_number"])
                require(size==f["size"] and channels==f["channels"],"packed_decoded_buffer_mismatch")
                if image.source=="TILED":
                    tile_buffers+=1
                else:
                    file_buffers+=1
                data=packed.data
                require(len(data)==f["bytes"] and hashlib.sha256(data).hexdigest()==f["sha256"],
                    "packed_bytes_changed_after_decode")
                del data
            total+=f["bytes"]
            records.append({"image":image.name,"view":f["view"],"tile_number":f["tile_number"],
                "bytes":f["bytes"],"sha256":f["sha256"],"size":f["size"],"channels":f["channels"]})
    require(len(images)==22 and len(records)==30 and total==PACK_BYTES,"packed_total")
    if decode:
        require(file_buffers==18 and tile_buffers==12,"decoded_buffer_coverage")
    return {"images":len(images),"packed_entries":len(records),"packed_bytes":total,
        "decoded_file_buffers":file_buffers,"decoded_tile_buffers":tile_buffers,
        "external_paths_all_missing":True,"records":records,"all_passed":True}

def verify_originals(root):
    manifest_path=root/"restore-manifest.json"
    require(manifest_path.is_file() and manifest_path.stat().st_size<=JSON_CAP,"original_manifest")
    manifest=json.loads(manifest_path.read_text())
    require(manifest["ok"] and manifest["archive_file_count"]==68
        and manifest["archive_file_bytes"]==180849901 and manifest["source_file_count"]==60
        and manifest["original_archive"]["sha256"]==SOURCE_ZIP_SHA
        and manifest["all_restored_hashes_and_crc_rechecked"] and manifest["originals_readonly"]
        and not manifest["archive_files_executed"],"original_manifest_provenance")
    originals=root/"originals"
    require(len(manifest["entries"])==68,"original_manifest_entries")
    files={}
    for r in manifest["entries"]:
        relative=PurePosixPath(r["path"])
        require(not relative.is_absolute() and ".." not in relative.parts,"original_path")
        path=originals.joinpath(*relative.parts)
        require(not path.is_symlink() and path.resolve(strict=True).is_relative_to(originals)
            and stat.S_ISREG(path.stat().st_mode) and not path.stat().st_mode&0o222
            and path.stat().st_size==r["bytes"] and sha(path)==r["sha256"],"original_file_changed")
        require(r["path"] not in files,"original_duplicate_path")
        files[r["path"]]={"bytes":r["bytes"],"sha256":r["sha256"]}
    actual={p.relative_to(originals).as_posix() for p in originals.rglob("*") if p.is_file()}
    require(actual==set(files),"original_inventory_changed")
    return {"files":68,"bytes":sum(r["bytes"] for r in files.values()),"manifest_sha256":sha(manifest_path),
        "all_files_sha256":digest(files),"all_readonly":True}

def error_record(error):
    code=error.args[0] if isinstance(error,ValueError) and len(error.args)==1 else None
    if not isinstance(code,str) or len(code)>160 or not code.replace("_","").isalnum():
        code=None
    return {"error_type":type(error).__name__,"error_code":code,
        "frames":[{"file":Path(f.filename).name,"line":f.lineno,"function":f.name}
            for f in traceback.extract_tb(error.__traceback__)[-6:]]}

def create_transport(candidate,parts_dir,work):
    require(0<candidate.stat().st_size<=BLEND_CAP,"saved_blend_budget")
    parts_dir.mkdir(exist_ok=False)
    chunks=[]
    whole=sha(candidate)
    with candidate.open("rb") as source:
        index=0
        while True:
            data=source.read(PART_BYTES)
            if not data:
                break
            require(index<2,"transport_part_count")
            part=parts_dir/("snow-packed-native.part-"+str(index).zfill(3)+".bin")
            part.write_bytes(data)
            record={"file":part.name,"index":index,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
            require(sha(part)==record["sha256"],"written_part_hash")
            chunks.append(record);index+=1
    joined=work/"snow-packed-native-rejoined.blend"
    with joined.open("xb") as output:
        for record in chunks:
            path=parts_dir/record["file"]
            require(path.stat().st_size==record["bytes"] and sha(path)==record["sha256"],"join_part_pin")
            with path.open("rb") as file:
                shutil.copyfileobj(file,output,length=1024*1024)
    require(joined.stat().st_size==candidate.stat().st_size and sha(joined)==whole,"transport_join_hash")
    return joined,{"schema_version":1,"candidate_file":candidate.name,"bytes":candidate.stat().st_size,
        "sha256":whole,"part_size_cap":PART_BYTES,"parts":chunks,"same_job_join_sha256_verified":True,
        "part_files_are_binary_chunks_not_standalone_blend":True}

def main():
    parser=argparse.ArgumentParser()
    for name in ("original-root","derivative-blend","config","out"):
        parser.add_argument("--"+name,required=True)
    args=parser.parse_args()
    original_root=Path(args.original_root).resolve(strict=True)
    source_root=original_root/"originals/sources/assets/characters"
    source=source_root/"snow/original/Snow/snow_v4.2.blend"
    candidate_input=Path(args.derivative_blend).resolve(strict=True)
    producer_path=candidate_input.with_name("native-clips-audit.json")
    config_path=Path(args.config).resolve(strict=True)
    out=Path(args.out).resolve()
    require(not out.is_relative_to(original_root) and not original_root.is_relative_to(out)
        and not candidate_input.is_relative_to(out) and not out.is_relative_to(candidate_input.parent),
        "output_input_overlap")
    out.mkdir(parents=True,exist_ok=True)
    snow=out/"snow";snow.mkdir(exist_ok=False)
    work=out/"work";work.mkdir(exist_ok=False)
    missing_root=out/"intentionally-missing-used-textures"
    require(not missing_root.exists(),"isolation_path_exists")
    audit={"purpose":"One native packed-used-textures candidate with fresh-process embedded decode",
        "candidate_complete":False,"packed_used_textures_verified":False,"full_scene_portable":False,
        "renders":0,"models_saved":0,"glb_written":False,"geometry_edits":False,
        "native_poses_captured":0,"overall_art_approved":False,"production_glb_approved":False,
        "browser_animation_approved":False,"limits":["Not a PBR/UDIM atlas or GLB conversion",
            "Native key VALUES may respond; coordinate DATA and definitions must remain unchanged",
            "Only used render-mesh material texture closure certified; full scene external dependencies not certified"]}
    audit_path=snow/"packed-textures-audit.json"
    failure=None;modules=rig=saved=snapshot=reference_values=None
    source_snapshot=None;file_pins={};worker_report=None
    try:
        require(source.is_file() and sha(source)==SOURCE_SHA and candidate_input.stat().st_size==INPUT_BYTES
            and sha(candidate_input)==INPUT_SHA and sha(producer_path)==PRODUCER_SHA
            and blob(config_path)==CONFIG_BLOB,"frozen_input_pins")
        producer=json.loads(producer_path.read_text())
        require(producer["derivative"]["sha256"]==INPUT_SHA and producer["derivative"]["bytes"]==INPUT_BYTES
            and producer["source_sha256"]==SOURCE_SHA and producer["input_sha256"]==
                "572897f5416f256950134e408ead8d77ecf53c0accbe5f7912be976c3c763ea4"
            and all(producer[k] for k in ("numeric_native_clip_candidate_verified","reopen_verification_passed",
                "preservation_passed","candidate_completed")),"native_producer_identity")
        source_snapshot=verify_originals(original_root)
        credit_pins={"LICENSES.md":"21ffbcb7404ceeb59a8038da34ad28df24ee3f390d33f9c16bac04952cbab71c",
            "snow/ATTRIBUTION.txt":"cf280b50c86fc5b1518643f4bb8be5befba91b29bdfeb5311ad3f98b65fddc9d",
            "rain/ATTRIBUTION.txt":"41d2a5693de42c5ee60dafaea599dfadd5a34ede8554a4d8a7c98af0cd008f24"}
        audit["credits"]=[]
        for relative,pin in credit_pins.items():
            file=snow/"credits"/relative;file.parent.mkdir(parents=True,exist_ok=True)
            require(sha(source_root/relative)==pin,"original_credit_pin")
            shutil.copyfile(source_root/relative,file)
            require(sha(file)==pin,"copied_credit_pin")
            audit["credits"].append({"file":str(file.relative_to(snow)),"bytes":file.stat().st_size,"sha256":pin})
        modules=load_modules()
        base,native,natural,face,proof,soft,pair,helper=modules
        worker=Path(__file__).with_name("bpy-verify-snow-packed-textures.py").resolve(strict=True)
        paths=[Path(__file__).resolve(),worker,config_path,candidate_input,producer_path,
            Path("bpy-proof/bpy-runtime.json").resolve()]
        paths.extend(Path(m.__file__).resolve() for m in modules)
        for filename in ("bpy-proof-snow-bent-elbows.py","bpy-prototype-snow-crewneck.py"):
            paths.append(Path(__file__).with_name(filename).resolve())
        file_pins={str(p):{"sha256":sha(p),"bytes":p.stat().st_size} for p in paths}
        audit["input_files"]=file_pins
        audit["originals_before"]=source_snapshot
        import bpy
        bpy.context.preferences.filepaths.use_scripts_auto_execute=False
        validate_runtime(bpy)
        bpy.ops.wm.open_mainfile(filepath=str(candidate_input),load_ui=False,use_scripts=False)
        rig=bpy.data.objects.get("RIG-Snow")
        require(rig is not None and rig.type=="ARMATURE" and rig.data.pose_position=="POSE"
            and rig.name in bpy.context.scene.objects,"native_rig_missing")
        saved=binding_state(bpy,rig)
        audit["saved_binding"]=saved
        reference=bind_reference(bpy,native,rig)
        images=used_images(bpy,pair)
        audit["closure"]=closure_report(bpy,pair,images)
        audit["used_textures"]=[]
        pair.relink_and_reload(images,source.parent/"textures",audit["used_textures"],
            lambda:write_json(audit_path,audit))
        rows=prepare_image_rows(bpy,images,producer,(source.parent/"textures").resolve(strict=True),missing_root)
        audit["texture_preflight"]={"used_images":len(rows),"file_records":sum(len(r["files"]) for r in rows),
            "compressed_source_file_bytes":PACK_BYTES,"source_blend_bytes":INPUT_BYTES,
            "nominal_source_plus_embedded_bytes":INPUT_BYTES+PACK_BYTES,
            "metadata_and_blend_overhead_allowance":16*1024*1024,"candidate_hard_cap":BLEND_CAP,
            "individual_source_file_cap":FILE_CAP,"part_bytes":PART_BYTES,
            "actual_saved_size_not_yet_known":True}
        require(INPUT_BYTES+PACK_BYTES+16*1024*1024<=BLEND_CAP,"packed_blend_preflight")
        action_names=sorted(action.name for action in bpy.data.actions)
        snapshot=capture_state(bpy,modules,rig,action_names)
        reference_values=numeric_values(bpy,modules,rig)
        require({k:len(v) for k,v in snapshot["stable_inventory"].items()}==
            {"objects":59,"meshes":50,"shape_keys":8,"actions":59},"native_id_count")
        require(snapshot["key_count"]==120,"native_current_key_count")
        audit["reference_snapshot"]=snapshot
        audit["reference_binding"]=reference
        audit["source_material_graph_with_original_paths"]=proof.material_graph_hash(bpy,pair)
        write_json(audit_path,audit)
        for image,row in zip(images,rows):
            image.pack()  # No data= route, no dirty re-encoding, no global pack_all.
            entries={(int(p.view),int(p.tile_number)):p for p in image.packed_files}
            require(len(entries)==len(image.packed_files)==len(row["files"]),"partial_pack_collection")
            for file in row["files"]:
                entry=entries.get((file["view"],file["tile_number"]))
                require(entry is not None and Path(entry.filepath).name==file["file"]
                    and entry.packed_file is not None and entry.packed_file.size==file["bytes"],
                    "packed_source_identity")
                data=entry.packed_file.data
                require(isinstance(data,bytes) and len(data)==file["bytes"]
                    and hashlib.sha256(data).hexdigest()==file["sha256"],"new_packed_source_sha")
                del data
                entry.filepath=file["missing_path"]
            image.filepath_raw=row["missing_pattern"]
        audit["in_memory_packed"]=packed_state(bpy,images,rows,missing_root,decode=False)
        require(capture_state(bpy,modules,rig,action_names)==snapshot,"packing_preservation")
        audit["in_memory_value_comparison"]=compare_values(numeric_values(bpy,modules,rig),reference_values)
        require(audit["in_memory_value_comparison"]["passed"],"packing_values")
        restore_binding(bpy,native,rig,saved)
        require(binding_state(bpy,rig)==saved,"before_save_binding")
        candidate=work/"snow-packed-used-textures-candidate.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(candidate),check_existing=False,compress=True,relative_remap=False)
        audit["models_saved"]=1
        audit["derivative"]={"file":candidate.name,"bytes":candidate.stat().st_size,"sha256":sha(candidate)}
        require(candidate.is_file() and 0<candidate.stat().st_size<=BLEND_CAP,"candidate_size")
        joined,transport=create_transport(candidate,out/"parts",work)
        audit["transport"]=transport
        write_json(snow/"packed-transport-manifest.json",transport)
        expected={"schema_version":1,"wrapper_blob":blob(Path(__file__)),"worker_blob":blob(worker),
            "blend_sha256":transport["sha256"],"blend_bytes":transport["bytes"],"snapshot":snapshot,
            "snapshot_sha256":digest(snapshot),"reference_binding":reference,"saved_binding":saved,
            "action_names":action_names,"images":rows,"missing_root":str(missing_root),
            "reference_values":reference_values}
        expected_path=snow/"packed-reopen-expectations.json"
        write_json(expected_path,expected)
        write_json(audit_path,audit)
        process=subprocess.run([sys.executable,str(worker),"--blend",str(joined),"--expected",str(expected_path),
            "--expected-sha",sha(expected_path),"--out",str(snow)],capture_output=True,text=True,timeout=360)
        require(len(process.stdout.encode())<=65536 and len(process.stderr.encode())<=65536,"worker_output_budget")
        audit["worker_exit_code"]=process.returncode
        audit["worker_stdout_tail"]=process.stdout[-24000:]
        audit["worker_stderr_tail"]=process.stderr[-4000:]
        report_path=snow/"packed-reopen-audit.json"
        require(report_path.is_file() and report_path.stat().st_size<=JSON_CAP,"worker_report_missing")
        worker_report=json.loads(report_path.read_text())
        audit["reopen_report"]={"file":report_path.name,"bytes":report_path.stat().st_size,"sha256":sha(report_path)}
        audit["reopen_verified"]=bool(process.returncode==0 and worker_report.get("passed") is True)
        require(audit["reopen_verified"],"fresh_process_reopen_failed")
    except Exception as error:
        failure=error
        audit["failure"]=error_record(error)
    finally:
        try:
            if rig is not None and modules is not None and saved is not None:
                base,native,natural,face,proof,soft,pair,helper=modules
                restore_binding(bpy,native,rig,saved)
                audit["original_binding_restored"]=binding_state(bpy,rig)==saved
                if snapshot is not None:
                    bind_reference(bpy,native,rig)
                    audit["final_snapshot_preserved"]=capture_state(bpy,modules,rig,
                        sorted(action.name for action in bpy.data.actions))==snapshot
                    audit["final_value_comparison"]=compare_values(numeric_values(bpy,modules,rig),reference_values)
                    restore_binding(bpy,native,rig,saved)
            audit["originals_after"]=verify_originals(original_root)
            audit["all_68_original_hashes_unchanged"]=audit["originals_after"]==source_snapshot
            audit["input_file_recheck"]={path:(Path(path).is_file()
                and Path(path).stat().st_size==pin["bytes"] and sha(path)==pin["sha256"])
                for path,pin in file_pins.items()}
            audit["input_files_unchanged"]=bool(file_pins) and all(audit["input_file_recheck"].values())
            complete=(failure is None and audit.get("reopen_verified",False)
                and audit.get("final_snapshot_preserved",False)
                and audit.get("final_value_comparison",{}).get("passed") is True
                and audit.get("original_binding_restored",False)
                and audit["all_68_original_hashes_unchanged"] and audit["input_files_unchanged"])
            audit["packed_used_textures_verified"]=bool(complete)
            audit["candidate_complete"]=bool(complete)
            write_json(audit_path,audit)
            summary={key:audit.get(key) for key in ("candidate_complete","failure","texture_preflight",
                "derivative","transport","reopen_report","reopen_verified","original_binding_restored",
                "final_snapshot_preserved","in_memory_value_comparison","final_value_comparison",
                "all_68_original_hashes_unchanged","input_files_unchanged","packed_used_textures_verified",
                "full_scene_portable","renders","models_saved","glb_written","overall_art_approved",
                "production_glb_approved","browser_animation_approved")}
            require(len(encoded(summary))<=24000,"summary_budget")
            print("SNOW_PACKED_USED_TEXTURES "+encoded(summary).decode().strip(),flush=True)
        except Exception as final_error:
            audit["finalization_failure"]=error_record(final_error)
            audit["candidate_complete"]=False
            try:
                write_json(audit_path,audit)
            except Exception:
                pass
            print("SNOW_PACKED_USED_TEXTURES_FINAL_FAILED "+encoded(error_record(final_error)).decode().strip(),flush=True)
            if failure is None:
                failure=final_error
    return 0 if audit.get("candidate_complete") and failure is None else 1

if __name__=="__main__":
    raise SystemExit(main())
