"""Read-only comparison of the raw Snow collar, never a renderer or garment editor.
Blender source triangulation is cached once; all geometry comparisons use Python
float64 cross products. Raw/custom/corner normals are not evaluated shading proof.
"""
import argparse
from collections import deque
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

SOURCE_SHA = "80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
DERIVATIVE_SHA = "9ee52d1c40d56c4909cc255873dddb08aa9fc627e4ce1bc30af12ea99bacb94c"
DERIVATIVE_BYTES = 8450445
HELPER_BLOB = "a64c4f14e977a6ae720fb57b01ffa9f69d5703f8"
CONFIG_BLOB = "f0612039b320e8dac77587ec4aecdc2c84618843"
NECK = [930,931,936,937,945,984,1569,1561,1560,1555,1554,1566,1565,1564,1563,1562,1589,1747,1748,1590,1568,1567,1559,1558,1557,1556,983,932,933,934,935,943,944,966,1341,1340,965,938,939,940,941,942]
CENTRAL = [945,984,1245,1246,1248,1315,1316,1569,1689,1690,1692]
REPORT_LIMIT, STDOUT_LIMIT = 1048576, 24000

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()

def vector(value):
    result = [float(x) for x in value]
    if not all(math.isfinite(x) for x in result):
        raise ValueError("nonfinite_geometry_data")
    return result

def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

def subtract(a, b):
    return [x-y for x,y in zip(a,b)]

def geometric_normal(indices, coordinates):
    origin = coordinates[indices[0]]
    value = [0.0, 0.0, 0.0]
    for i in range(1, len(indices)-1):
        part = cross(subtract(coordinates[indices[i]], origin),
                     subtract(coordinates[indices[i+1]], origin))
        value = [a+b for a,b in zip(value,part)]
    length = math.sqrt(sum(x*x for x in value))
    return [x/length for x in value] if length > 1e-12 else None

def angle(a, b):
    if a is None or b is None:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x*y for x,y in zip(a,b))))))

def load_helper():
    path = Path(__file__).with_name("bpy-inspect-avatar-garments.py")
    if git_blob(path.read_bytes()) != HELPER_BLOB:
        raise ValueError("reviewed_helper_hash_mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_snow_raw_inspector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def numeric_default(socket):
    value = getattr(socket, "default_value", None)
    if isinstance(value, (int, float, bool)):
        return value if not isinstance(value, float) or math.isfinite(value) else None
    if value is not None and not isinstance(value, str):
        try:
            items = list(value)
            if len(items) <= 4 and all(isinstance(x,(int,float,bool)) and math.isfinite(x) for x in items):
                return items
        except (TypeError, ValueError):
            pass
    return None

def material_graph(material):
    if material is None:
        return None
    result = {"name": material.name, "use_nodes": material.use_nodes, "trees": [],
              "truncated": False, "max_nodes": 96, "max_links": 192, "max_depth": 3,
              "scope": "upstream material output plus normal/bump seeds; no code/Text/expression contents"}
    remaining = {"nodes": 96, "links": 192}
    seen = set()
    def visit(tree, path, depth):
        if tree is None or tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        nodes, links = [], []
        stack = [n for n in tree.nodes if n.type in ("OUTPUT_MATERIAL","GROUP_OUTPUT","BUMP","NORMAL_MAP")]
        selected = set()
        while stack:
            node = stack.pop()
            if node.as_pointer() in selected:
                continue
            if remaining["nodes"] <= 0:
                result["truncated"] = True
                break
            selected.add(node.as_pointer())
            remaining["nodes"] -= 1
            record = {"name": node.name, "type": node.bl_idname}
            inputs = {}
            for socket in node.inputs:
                if socket.name in ("Strength","Distance","Height","Normal","Base Color","Color","Scale","Fac"):
                    value = numeric_default(socket)
                    if value is not None:
                        inputs[socket.name] = value
                for link in socket.links:
                    if remaining["links"] <= 0:
                        result["truncated"] = True
                        continue
                    remaining["links"] -= 1
                    links.append({"from_node": link.from_node.name, "from_socket": link.from_socket.name,
                                  "to_node": link.to_node.name, "to_socket": link.to_socket.name})
                    stack.append(link.from_node)
            if inputs:
                record["numeric_inputs"] = inputs
            image = getattr(node, "image", None)
            if image:
                filename = str(image.filepath).replace("\\","/").split("/")[-1]
                record["image"] = {"name": image.name, "filename": filename.split("?")[0].split("#")[0],
                                   "source": image.source}
            for field in ("uv_map","space","invert"):
                value = getattr(node, field, None)
                if isinstance(value, (str,bool)):
                    record[field] = value
            child = getattr(node, "node_tree", None)
            if child:
                record["node_group"] = child.name
                if depth < 3:
                    visit(child, path + "/" + node.name, depth+1)
                else:
                    result["truncated"] = True
            nodes.append(record)
        result["trees"].append({"path": path, "nodes": nodes, "links": links})
    visit(material.node_tree, material.name, 0)
    return result

def rings_from_edges(edges):
    adjacent = {}
    for a,b in edges:
        adjacent.setdefault(a,set()).add(b)
        adjacent.setdefault(b,set()).add(a)
    hops = {i:0 for i in NECK}
    queue = deque(NECK)
    while queue:
        vertex = queue.popleft()
        if hops[vertex] == 2:
            continue
        for neighbor in sorted(adjacent.get(vertex,())):
            if neighbor not in hops:
                hops[neighbor] = hops[vertex]+1
                queue.append(neighbor)
    return hops

def front_arc(component):
    adjacent = {}
    for a,b in component["edges"]:
        adjacent.setdefault(a,set()).add(b)
        adjacent.setdefault(b,set()).add(a)
    candidates = []
    for next_vertex in sorted(adjacent[966]):
        path, previous, current = [966], 966, next_vertex
        while current != 1590:
            if current in path:
                raise ValueError("neck_arc_cycle_before_side_anchor")
            path.append(current)
            choices = adjacent[current] - {previous}
            if len(choices) != 1:
                raise ValueError("neck_arc_branch")
            previous,current = current,next(iter(choices))
        path.append(1590)
        if 984 in path:
            candidates.append(path)
    if len(candidates) != 1:
        raise ValueError("front_arc_not_unique")
    return candidates[0]

def snapshot(bpy, helper, path, reference=None):
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    policy = helper.disable_animation_and_scripts(bpy)
    policy_summary = {
        "automatic_python_execution": False, "embedded_text_executed": False,
        "native_drivers_retained": sum(r["native_drivers_retained"] for r in policy),
        "complex_python_drivers_muted": sum(r["complex_python_drivers_muted"] for r in policy),
        "actions_detached": sum(r["detached_action"] is not None for r in policy),
        "nla_tracks_detached": sum(r["removed_nla_tracks"] for r in policy),
        "drivers_evaluated_by_this_inspector": False,
    }
    del policy
    obj = bpy.data.objects.get("GEO-snow-shirt")
    if obj is None or obj.type != "MESH":
        raise ValueError("snow_shirt_missing")
    mesh = obj.data
    if len(mesh.vertices) != 1839 or mesh.shape_keys is None or len(mesh.shape_keys.key_blocks) != 10:
        raise ValueError("frozen_shirt_counts_mismatch")
    boundaries = helper.inspect_garment_boundaries(obj)
    matches = [c for c in boundaries["boundary_components"]
               if c["closed"] and set(c["vertex_indices"]) == set(NECK)]
    if len(matches) != 1:
        raise ValueError("exact_neck_boundary_not_found")
    local = [vector(v.co) for v in mesh.vertices]
    world = [vector(obj.matrix_world @ v.co) for v in mesh.vertices]
    edges = [list(e.vertices) for e in mesh.edges]
    polygons = [list(p.vertices) for p in mesh.polygons]
    loop_vertices = [loop.vertex_index for loop in mesh.loops]
    topology_hash = hashlib.sha256(encoded([edges,polygons,loop_vertices])).hexdigest()
    if reference and topology_hash != reference["topology_sha256"]:
        raise ValueError("source_derivative_topology_mismatch")
    hops = rings_from_edges(edges)
    vertices = set(hops) | set(CENTRAL)
    face_ids = {p.index for p in mesh.polygons if any(i in vertices for i in p.vertices)}
    central_faces = {p.index for p in mesh.polygons if any(i in CENTRAL for i in p.vertices)}
    selected_edges = {e.index for e in mesh.edges if any(i in vertices for i in e.vertices)}
    # Only source cache triangulation is requested; never refresh/evaluate normals.
    if reference is None:
        mesh.calc_loop_triangles()
        triangles = [{"vertices":list(t.vertices),"loops":list(t.loops),"polygon":t.polygon_index}
                     for t in mesh.loop_triangles]
    else:
        triangles = reference["_triangles"]
    normals = [geometric_normal(ids,world) for ids in polygons]
    tri_normals = [geometric_normal(t["vertices"],world) for t in triangles]
    face_edges = {}
    for p in mesh.polygons:
        for key in p.edge_keys:
            face_edges.setdefault(tuple(sorted(key)),[]).append(p.index)
    tri_edges = {}
    for i,t in enumerate(triangles):
        a,b,c = t["vertices"]
        for pair in ((a,b),(b,c),(c,a)):
            tri_edges.setdefault(tuple(sorted(pair)),[]).append(i)
    uv_layers = {}
    for layer in mesh.uv_layers:
        uv_layers[layer.name] = {p.index:[[li, *vector(layer.data[li].uv)] for li in p.loop_indices]
                                 for p in mesh.polygons if p.index in face_ids}
    raw_faces = {p.index:{"vertices":list(p.vertices),"loops":list(p.loop_indices),
                         "material_slot":p.material_index,"smooth":p.use_smooth,
                         "normal":normals[p.index]} for p in mesh.polygons if p.index in face_ids}
    raw_edges = {}
    for edge in mesh.edges:
        if edge.index not in selected_edges:
            continue
        key = tuple(sorted(edge.vertices))
        faces = face_edges.get(key,[])
        raw_edges[edge.index] = {"vertices":list(edge.vertices),"faces":faces,
            "seam":edge.use_seam,"sharp":getattr(edge,"use_edge_sharp",None),
            "dihedral_degrees":angle(normals[faces[0]],normals[faces[1]]) if len(faces)==2 else None}
    custom = {"has_custom_normals":getattr(mesh,"has_custom_normals",None),
              "normal_attributes":[{"name":a.name,"domain":a.domain,"data_type":a.data_type}
                                   for a in mesh.attributes if "normal" in a.name.lower()],
              "corner_normal_freshness":"unverified",
              "corner_normal_scope":"RNA diagnostic data; not proof of authored custom normals"}
    samples = []
    try:
        corner = getattr(mesh,"corner_normals",None)
        if corner is not None and len(corner)==len(mesh.loops):
            for face in sorted(central_faces)[:24]:
                for li in mesh.polygons[face].loop_indices:
                    if len(samples)>=96:
                        break
                    samples.append({"face":face,"loop":li,"vector":vector(corner[li].vector)})
        custom["corner_normals_sample"] = samples
        custom["corner_normals_sample_limit"] = 96
        custom["explicit_normal_cache_refresh_requested"] = False
    except Exception as error:
        custom["corner_normals_read_status"] = type(error).__name__
    material_indices = sorted({raw_faces[i]["material_slot"] for i in face_ids})
    graphs = {}
    for index in material_indices:
        mat = obj.material_slots[index].material if index<len(obj.material_slots) else None
        graphs[index] = material_graph(mat)
    result = {
        "filename":path.name,"policy":policy_summary,"vertex_count":len(mesh.vertices),
        "shape_keys":[{"name":k.name,"point_count":len(k.data),"value":float(k.value),
                       "mute":k.mute} for k in mesh.shape_keys.key_blocks],
        "matrix_world":[vector(row) for row in obj.matrix_world],
        "raw_vertex_count":len(mesh.vertices),"evaluated_vertex_count":None,
        "evaluated_vertex_count_status":"not measured; this inspector never obtains a depsgraph",
        "raw_to_evaluated_vertex_mapping":"unproven; no evaluated vertex indices are inferred",
        "modifier_stack":[{
            "order":index,"name":modifier.name,"type":modifier.type,
            "show_viewport":modifier.show_viewport,"show_render":modifier.show_render,
            "is_bound":getattr(modifier,"is_bound",None),
            "object":getattr(getattr(modifier,"object",None),"name",None),
            "target":getattr(getattr(modifier,"target",None),"name",None),
            "dependencies":[{
                "field":field,"name":dependency.name,"type":dependency.type,
                "raw_vertex_count":len(dependency.data.vertices) if dependency.type=="MESH" else None,
                "linked_in_active_scene":dependency.name in bpy.context.scene.objects,
                "hide_render":dependency.hide_render,
            } for field in ("object","target")
              for dependency in [getattr(modifier,field,None)]
              if isinstance(dependency,bpy.types.Object)],
        } for index,modifier in enumerate(obj.modifiers)],
        "local":local,"world":world,"hops":hops,"face_ids":sorted(face_ids),
        "central_faces":sorted(central_faces),"faces":raw_faces,"edges":raw_edges,
        "uv_layers":uv_layers,"custom_normals":custom,"materials":graphs,
        "topology_sha256":topology_hash,"front_arc":front_arc(matches[0]),
        "_triangles":triangles,"_triangle_normals":tri_normals,
        "_triangle_edges":[{"vertices":list(pair),"triangles":ids} for pair,ids in tri_edges.items()],
    }
    # Every retained value is a Python scalar/list/dict, never a bpy/RNA handle.
    encoded(result)
    return result

def combined_report(source, derivative, credits, hashes):
    hops = source["hops"]
    vertices = sorted(set(hops)|set(CENTRAL))
    vertex_records = []
    for i in vertices:
        vertex_records.append({"id":i,"hop":hops.get(i),"central":i in CENTRAL,
            "source_local":source["local"][i],"derivative_local":derivative["local"][i],
            "source_world":source["world"][i],"derivative_world":derivative["world"][i],
            "world_delta":subtract(derivative["world"][i],source["world"][i])})
    faces = []
    for i in source["face_ids"]:
        a,b=source["faces"][i],derivative["faces"][i]
        uva={name:values[i] for name,values in source["uv_layers"].items()}
        uvb={name:values[i] for name,values in derivative["uv_layers"].items()}
        row={"id":i,"vertices":a["vertices"],"loops":a["loops"],
             "source_normal":a["normal"],"derivative_normal":b["normal"],
             "normal_rotation_degrees":angle(a["normal"],b["normal"]),
             "material_slot_before":a["material_slot"],"material_slot_after":b["material_slot"],
             "smooth_before":a["smooth"],"smooth_after":b["smooth"],
             "uv_corners_by_layer":uva,"derivative_uv_matches_source":uva==uvb}
        if uva!=uvb:
            row["derivative_uv_corners_by_layer"]=uvb
        faces.append(row)
    edges=[]
    for i,a in source["edges"].items():
        b=derivative["edges"][i]
        before,after=a["dihedral_degrees"],b["dihedral_degrees"]
        edges.append({"id":i,"vertices":a["vertices"],"faces":a["faces"],
            "source_dihedral_degrees":before,"derivative_dihedral_degrees":after,
            "dihedral_delta_degrees":after-before if before is not None and after is not None else None,
            "seam_before":a["seam"],"seam_after":b["seam"],
            "sharp_before":a["sharp"],"sharp_after":b["sharp"]})
    triangles=[]
    selected=set(vertices)
    for i,t in enumerate(source["_triangles"]):
        if not any(v in selected for v in t["vertices"]):
            continue
        a,b=source["_triangle_normals"][i],derivative["_triangle_normals"][i]
        triangles.append({"id":i,**t,"source_normal":a,"derivative_normal":b,
                          "normal_rotation_degrees":angle(a,b)})
    tri_adjacency=[]
    for adjacency in source["_triangle_edges"]:
        pair,ids=adjacency["vertices"],adjacency["triangles"]
        if len(ids)!=2 or not any(i in selected for i in pair):
            continue
        a,b=ids
        before=angle(source["_triangle_normals"][a],source["_triangle_normals"][b])
        after=angle(derivative["_triangle_normals"][a],derivative["_triangle_normals"][b])
        tri_adjacency.append({"vertices":list(pair),"triangles":ids,"source_angle":before,
            "derivative_angle":after,
            "angle_delta":after-before if before is not None and after is not None else None})
    materials=[]
    for i,a in source["materials"].items():
        b=derivative["materials"].get(i)
        row={"slot":i,"source_graph":a,"derivative_graph_matches_source":a==b}
        if a!=b:
            row["derivative_graph"]=b
        materials.append(row)
    return {
        "schema_version":1,"purpose":"Raw collar comparison only; no causal or art acceptance",
        "files":hashes,"credits":credits,"neck_indices":NECK,"central_vertex_indices":CENTRAL,
        "front_arc_indices":source["front_arc"],
        "ring_definition":"Shortest raw mesh-edge distance from exact 42 neck vertices; disjoint hop0/hop1/hop2",
        "ring_membership":{str(n):sorted(i for i,h in hops.items() if h==n) for n in range(3)},
        "selection_definition":"Faces/edges incident to any hop0-2 or requested central vertex; face corners can be outside ring2",
        "topology_sha256":source["topology_sha256"],
        "topology_matches":source["topology_sha256"]==derivative["topology_sha256"],
        "vertices":vertex_records,"faces":faces,"edges":edges,"source_reference_triangles":triangles,
        "triangle_adjacency":tri_adjacency,"materials":materials,
        "custom_normals":{"source":source["custom_normals"],"derivative":derivative["custom_normals"]},
        "shape_keys":{"source":source["shape_keys"],"derivative":derivative["shape_keys"]},
        "object_matrices":{"source":source["matrix_world"],"derivative":derivative["matrix_world"]},
        "modifier_stacks":{"source":source["modifier_stack"],"derivative":derivative["modifier_stack"]},
        "vertex_counts":{"source_raw":source["raw_vertex_count"],"derivative_raw":derivative["raw_vertex_count"],
                         "source_evaluated":None,"derivative_evaluated":None},
        "raw_to_evaluated_mapping":"unproven; evaluated mesh was not requested",
        "native_policy":{"source":source["policy"],"derivative":derivative["policy"]},
        "geometric_normal_source":"raw_coordinates_cross_sum",
        "rendered_images":0,"models_saved":0,"geometry_edits_performed":False,
        "garment_art_approved":False,"production_glb_approved":False,"animation_approved":False,
        "limits":[
            "Raw polygons and source cached triangulation only; no depsgraph/modifier/render evaluation.",
            "Derivative triangle comparisons reuse source vertex/loop IDs; derivative retessellation is not assumed.",
            "Geometric normals are independent float64 cross sums; RNA corner normal freshness is unverified.",
            "Angles are unsigned 0..180 degrees; they do not prove folds, intersections or shaded appearance.",
            "UVs belong to the recorded actual polygon loop indices, not inferred anatomical labels.",
            "Shader traversal is bounded; missing/truncated graphs cannot exclude a material cause.",
            "No bone, Text, script or driver-expression contents are dumped; no shader code is executed.",
        ]}

def stdout_summary(report, source):
    central=set(CENTRAL)
    faces=[row for row in report["faces"] if any(v in central for v in row["vertices"])]
    edges=[row for row in report["edges"] if any(v in central for v in row["vertices"])]
    edges.sort(key=lambda row:abs(row["dihedral_delta_degrees"] or 0),reverse=True)
    shader=[]
    for mat in report["materials"]:
        graph=mat["source_graph"]
        if graph is None:
            continue
        shader.append({"slot":mat["slot"],"material":graph["name"],
            "graphs_match":mat["derivative_graph_matches_source"],"truncated":graph["truncated"],
            "nodes":[{"tree":tree["path"],**node} for tree in graph["trees"] for node in tree["nodes"]
                     if node["type"] in ("ShaderNodeBump","ShaderNodeNormalMap","ShaderNodeTexImage","ShaderNodeGroup")][:20],
            "normal_links":[{"tree":tree["path"],**link} for tree in graph["trees"] for link in tree["links"]
                            if link["to_socket"] in ("Normal","Height")][:20]})
    value={"files":report["files"],"ring_counts":{n:len(v) for n,v in report["ring_membership"].items()},
        "front_arc_indices":report["front_arc_indices"],
        "central_vertices":[v for v in report["vertices"] if v["central"]],
        "central_face_count":len(faces),"central_edge_count":len(edges),
        "central_faces":[{k:v for k,v in row.items() if k not in ("uv_corners_by_layer","derivative_uv_corners_by_layer")}
                         for row in faces[:24]],
        "largest_central_dihedral_changes":edges[:24],"material_normal_bump_identifiers":shader,
        "uv_assignments_unchanged":all(f["derivative_uv_matches_source"] for f in report["faces"]),
        "material_graphs_unchanged":all(m["derivative_graph_matches_source"] for m in report["materials"]),
        "has_custom_normals_before":report["custom_normals"]["source"]["has_custom_normals"],
        "has_custom_normals_after":report["custom_normals"]["derivative"]["has_custom_normals"],
        "corner_normal_freshness":"unverified","geometry_normal_source":"raw_coordinates_cross_sum",
        "modifier_stacks":report["modifier_stacks"],"vertex_counts":report["vertex_counts"],
        "raw_to_evaluated_mapping":"unproven; no evaluated mesh requested",
        "source_and_derivative_unchanged":True,"rendered_images":0,"models_saved":0,
        "garment_art_approved":False,"production_glb_approved":False,"animation_approved":False}
    while len(encoded(value))>STDOUT_LIMIT-512:
        if len(value["central_faces"])>8:
            value["central_faces"]=value["central_faces"][:-1]
        elif len(value["largest_central_dihedral_changes"])>8:
            value["largest_central_dihedral_changes"]=value["largest_central_dihedral_changes"][:-1]
        else:
            value["material_normal_bump_identifiers"]=[]
            break
    value["stdout_sample_limits"]={"faces":len(value["central_faces"]),
        "edges":len(value["largest_central_dihedral_changes"]),"full_bounded_report":"collar-inspection.json"}
    if len(encoded(value))>STDOUT_LIMIT:
        raise ValueError("stdout_budget_exceeded")
    print("SNOW_COLLAR_INSPECTION " + encoded(value).decode().strip(),flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-blend",required=True)
    parser.add_argument("--derivative-blend",required=True)
    parser.add_argument("--config",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    source=Path(args.source_blend).resolve(strict=True)
    derivative=Path(args.derivative_blend).resolve(strict=True)
    destination=Path(args.out).resolve()
    if (source==derivative or destination.is_relative_to(source.parents[3])
            or destination.is_relative_to(derivative.parent)
            or source.is_relative_to(destination) or derivative.is_relative_to(destination)):
        raise ValueError("inspection_output_overlaps_inputs")
    config_path=Path(args.config)
    raw_config=config_path.read_bytes()
    config=json.loads(raw_config)
    if (git_blob(raw_config)!=CONFIG_BLOB or config["model"]!="snow"
            or config["prototype"]["neck_boundary_indices"]!=NECK
            or config["prototype"]["vertex_count"]!=1839
            or config["prototype"]["shape_key_count"]!=10):
        raise ValueError("reviewed_collar_config_mismatch")
    if digest(source)!=SOURCE_SHA:
        raise ValueError("original_source_hash_mismatch")
    if derivative.stat().st_size!=DERIVATIVE_BYTES or digest(derivative)!=DERIVATIVE_SHA:
        raise ValueError("frozen_derivative_hash_or_size_mismatch")
    destination.mkdir(parents=True,exist_ok=False)
    credits=[]
    for relative in ("LICENSES.md","rain/ATTRIBUTION.txt","snow/ATTRIBUTION.txt"):
        original=source.parents[3]/relative
        target=destination/"credits"/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(original,target)
        credits.append({"path":str(target.relative_to(destination)),"sha256":digest(target),
                        "bytes":target.stat().st_size})
    helper=load_helper()
    import bpy
    if sys.version_info[:2]!=(3,11) or tuple(bpy.app.version)!=(4,5,9):
        raise ValueError("requires_verified_python_3_11_bpy_4_5_9")
    original=snapshot(bpy,helper,source)
    adapted=snapshot(bpy,helper,derivative,reference=original)
    if digest(source)!=SOURCE_SHA or digest(derivative)!=DERIVATIVE_SHA:
        raise ValueError("readonly_input_hash_changed")
    hashes={"source":{"file":source.name,"sha256":SOURCE_SHA,"bytes":source.stat().st_size},
            "derivative":{"file":derivative.name,"sha256":DERIVATIVE_SHA,"bytes":DERIVATIVE_BYTES},
            "helper_git_blob":HELPER_BLOB,"config_git_blob":CONFIG_BLOB,
            "both_input_hashes_rechecked":True}
    report=combined_report(original,adapted,credits,hashes)
    data=encoded(report)
    if len(data)>REPORT_LIMIT:
        failure={"error_code":"full_report_budget_exceeded","attempted_report_bytes":len(data),
                 "limit":REPORT_LIMIT,"ring_counts":{n:len(v) for n,v in report["ring_membership"].items()},
                 "source_and_derivative_unchanged":True,"rendered_images":0,"models_saved":0,
                 "garment_art_approved":False,"production_glb_approved":False,"animation_approved":False}
        (destination/"inspection-failure.json").write_bytes(encoded(failure))
        print("SNOW_COLLAR_INSPECTION_FAILED "+encoded(failure).decode().strip(),flush=True)
        raise ValueError("full_report_budget_exceeded")
    (destination/"collar-inspection.json").write_bytes(data)
    stdout_summary(report,original)
    print("SNOW_COLLAR_INSPECTION_COMPLETE "+json.dumps({
        "report_bytes":len(data),"report_sha256":hashlib.sha256(data).hexdigest(),
        "ring_counts":{n:len(v) for n,v in report["ring_membership"].items()},
        "vertices":len(report["vertices"]),"faces":len(report["faces"]),"edges":len(report["edges"]),
        "triangles":len(report["source_reference_triangles"]),
        "source_and_derivative_unchanged":True,"rendered_images":0,"models_saved":0,
        "garment_art_approved":False,"production_glb_approved":False,"animation_approved":False}),flush=True)

if __name__=="__main__":
    main()
