"""Independent, bounded reader for the fixed 48 Hz factor-chain corrective GLB pilot.

No bpy, writer, exporter, or project helper imports. Geometry is computed only
from the bytes read here, then compared with separately captured native NPZ
references. This is a diagnostic CPU check, not a browser/material acceptance.
validate() never prints: write its full report as JSON and print only "summary".
"""
from pathlib import Path
import hashlib
import json
import math
import struct
import zipfile
import numpy as np

MAX_GLB = 32 * 1024 * 1024
MAX_REFERENCE_JSON = 1024 * 1024
MAX_REFERENCE_EXPANDED = 256 * 1024 * 1024
MAX_REPORT = 1024 * 1024
MAX_SUMMARY = 24 * 1024
CLIPS = ("idle", "wave", "celebrate")
AUTHORED_TOL = 0.0001
FRACTIONAL_TOL = 0.001
JOINT_TOL = 0.0001
FRACTIONAL_JOINT_TOL = 0.001
CONDITION_CAP = 1000000.0
CONTRACT = "coop-armature-factor-correctives-48hz-v1"
SOURCE_CONTRACT = "coop-armature-correctives-v1"
SOURCE_GLB_BYTES = 15845580
SOURCE_GLB_SHA256 = "4a91efd3b9e69e0549180b0b1c348ef35effc0b13ab561909ee5b8ebb1215f90"
FROZEN_JSON_BYTES = 143763
FROZEN_JSON_SHA256 = "83471e5eb420f716ef024b04e660ba29ba975f6e13a52835f65498c964fecb9d"
FROZEN_NPZ_BYTES = 31443671
FROZEN_NPZ_SHA256 = "6dca400a201b003e7ed81c8556d06cfa5afde07edad30705e2bf22ee487d9f94"
NATIVE_JOINTS, PALETTE_SIZE, COMMON_ROOT = 186, 187, 187
LOCAL_TRS_TOL = 0.00001
SOURCE_FPS, SAMPLE_RATE, KEY_COUNT = 24, 48, 97
TARGET_COUNT, HOLDOUT_COUNT, NATIVE_POSE_COUNT = 291, 24, 315
QUARTER_FRAMES = (0.25, 0.75, 12.25, 12.75, 24.25, 24.75, 36.25, 36.75)
CACHED_HALF_FRAMES = (0.5, 12.5, 24.5, 36.5)
COMPONENTS = {5121: np.dtype("u1"), 5123: np.dtype("<u2"),
              5125: np.dtype("<u4"), 5126: np.dtype("<f4")}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def fail(code):
    raise ValueError("avatar_glb_reader_" + code)


def integer(value, minimum=0, maximum=2**31-1):
    if type(value) is not int or not minimum <= value <= maximum:
        fail("integer_out_of_bounds")
    return value


def finite(array):
    if not np.isfinite(array).all():
        fail("nonfinite_values")
    return array


def json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def quaternion(value):
    q = finite(np.asarray(value, dtype=np.float64))
    if q.shape != (4,):
        fail("quaternion_shape")
    norm = float(np.linalg.norm(q))
    if norm <= 1e-12 or abs(norm - 1.0) > 0.0001:
        fail("quaternion_not_unit")
    return q / norm


def rotation_matrix(q):
    x, y, z, w = quaternion(q)
    return np.array(((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
                     (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
                     (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y))),
                    dtype=np.float64)


def slerp(a, b, factor):
    a, b = quaternion(a), quaternion(b)
    dot = float(np.dot(a, b))
    if dot < 0:
        b, dot = -b, -dot
    dot = min(1.0, max(0.0, dot))
    if dot > 1.0 - 1e-12:
        result = (1-factor)*a + factor*b
    else:
        theta = math.acos(dot)
        result = (math.sin((1-factor)*theta)*a +
                  math.sin(factor*theta)*b) / math.sin(theta)
    return finite(result / np.linalg.norm(result))


def affine_matrix(value):
    matrix = finite(np.asarray(value, dtype=np.float64))
    if matrix.shape != (4, 4) or not np.allclose(matrix[3], (0, 0, 0, 1),
                                                atol=1e-7, rtol=0):
        fail("matrix_not_affine")
    return matrix


def trs(translation, rotation, scale):
    t = finite(np.asarray(translation, dtype=np.float64))
    s = finite(np.asarray(scale, dtype=np.float64))
    if t.shape != (3,) or s.shape != (3,):
        fail("trs_shape")
    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = rotation_matrix(rotation) * s[np.newaxis, :]
    result[:3, 3] = t
    return finite(result)


class Glb:
    def __init__(self, path, expected_contract=CONTRACT):
        if expected_contract not in (CONTRACT, SOURCE_CONTRACT):
            fail("unsupported_expected_contract")
        path = Path(path)
        size = path.stat().st_size
        if not 20 <= size <= MAX_GLB:
            fail("glb_size")
        self.raw = path.read_bytes()
        magic, version, declared = struct.unpack_from("<III", self.raw)
        if magic != 0x46546C67 or version != 2 or declared != len(self.raw):
            fail("header")
        chunks, cursor = [], 12
        while cursor < len(self.raw):
            if cursor + 8 > len(self.raw):
                fail("chunk_header_bounds")
            length, kind = struct.unpack_from("<II", self.raw, cursor)
            cursor += 8
            if length % 4 or cursor + length > len(self.raw):
                fail("chunk_bounds_or_alignment")
            chunks.append((kind, self.raw[cursor:cursor+length]))
            cursor += length
        if cursor != len(self.raw) or len(chunks) != 2 or [
                c[0] for c in chunks] != [0x4E4F534A, 0x004E4942]:
            fail("pilot_requires_json_and_bin")
        if len(chunks[0][1]) > 8 * 1024 * 1024:
            fail("glb_json_budget")
        self.doc = json.loads(chunks[0][1].decode("utf-8"))
        self.bin = chunks[1][1]
        d = self.doc
        if d.get("asset", {}).get("version") != "2.0":
            fail("asset_version")
        if d.get("asset", {}).get("extras", {}).get("coop_corrective_contract") != expected_contract:
            fail("asset_contract")
        if d.get("extensionsRequired") or d.get("extensionsUsed"):
            fail("pilot_extensions_not_supported")
        buffers = d.get("buffers", [])
        if len(buffers) != 1 or "uri" in buffers[0]:
            fail("pilot_buffer_layout")
        self.buffer_length = integer(buffers[0].get("byteLength"), 1, MAX_GLB)
        if not self.buffer_length <= len(self.bin) <= self.buffer_length + 3:
            fail("bin_declared_length")
        self.views, self.accessors = d.get("bufferViews", []), d.get("accessors", [])
        if not 1 <= len(self.views) <= 32768 or not 1 <= len(self.accessors) <= 32768:
            fail("accessor_budget")
        for view in self.views:
            if view.get("buffer") != 0:
                fail("buffer_view_buffer")
            offset = integer(view.get("byteOffset", 0), 0, self.buffer_length)
            length = integer(view.get("byteLength"), 1, self.buffer_length)
            if offset + length > self.buffer_length:
                fail("buffer_view_bounds")
            if "byteStride" in view:
                stride = integer(view["byteStride"], 4, 252)
                if stride % 4 or stride > length:
                    fail("buffer_view_stride")
        self.cache = {}
        for i in range(len(self.accessors)):
            self.read(i)
        self.nodes = d.get("nodes", [])
        if not 1 <= len(self.nodes) <= 4096:
            fail("node_budget")
        self.parents = [-1] * len(self.nodes)
        self.names = {}
        for i, node in enumerate(self.nodes):
            name = node.get("name")
            if not isinstance(name, str) or not name or len(name) > 256 or name in self.names:
                fail("node_name_not_unique")
            self.names[name] = i
            for child in node.get("children", []):
                integer(child, 0, len(self.nodes)-1)
                if child == i or self.parents[child] != -1:
                    fail("node_multiple_parent_or_self")
                self.parents[child] = i
        scenes = d.get("scenes", [])
        scene_index = integer(d.get("scene", 0), 0, len(scenes)-1)
        roots = scenes[scene_index].get("nodes", [])
        if not roots or len(set(roots)) != len(roots):
            fail("scene_roots")
        self.reachable = set()
        def walk(index, ancestry):
            integer(index, 0, len(self.nodes)-1)
            if index in ancestry or len(ancestry) > 256:
                fail("node_cycle_or_depth")
            self.reachable.add(index)
            for child in self.nodes[index].get("children", []):
                walk(child, ancestry | {index})
        for root in roots:
            if self.parents[integer(root, 0, len(self.nodes)-1)] != -1:
                fail("scene_root_has_parent")
            walk(root, set())
        # Also reject unreachable cyclic components.
        for index in range(len(self.nodes)):
            visited, p = set(), index
            while p != -1:
                if p in visited:
                    fail("node_cycle")
                visited.add(p)
                p = self.parents[p]
        self.base = []
        for node in self.nodes:
            if "matrix" in node:
                if any(k in node for k in ("translation", "rotation", "scale")):
                    fail("matrix_and_trs")
                matrix = np.asarray(node["matrix"], dtype=np.float64)
                if matrix.shape != (16,):
                    fail("node_matrix_shape")
                self.base.append(("matrix", affine_matrix(matrix.reshape(4, 4).T)))
            else:
                self.base.append(("trs", (
                    finite(np.asarray(node.get("translation", (0, 0, 0)), dtype=np.float64)),
                    quaternion(node.get("rotation", (0, 0, 0, 1))),
                    finite(np.asarray(node.get("scale", (1, 1, 1)), dtype=np.float64)))))
                trs(*self.base[-1][1])

    def read(self, index, expected_type=None, component=None, vertex=False, tight=False):
        integer(index, 0, len(self.accessors)-1)
        accessor = self.accessors[index]
        if accessor.get("sparse") is not None or accessor.get("normalized", False):
            fail("pilot_sparse_or_normalized_not_supported")
        kind, ct = accessor.get("type"), accessor.get("componentType")
        if kind not in WIDTHS or ct not in COMPONENTS:
            fail("accessor_type_not_supported")
        if expected_type is not None and kind != expected_type:
            fail("accessor_semantic_type")
        if component is not None and ct not in component:
            fail("accessor_semantic_component")
        view_index = integer(accessor.get("bufferView"), 0, len(self.views)-1)
        view = self.views[view_index]
        dtype, width = COMPONENTS[ct], WIDTHS[kind]
        count = integer(accessor.get("count"), 1, 50000000)
        offset = integer(accessor.get("byteOffset", 0), 0, view["byteLength"])
        base = view.get("byteOffset", 0)
        element = dtype.itemsize * width
        stride = view.get("byteStride", element)
        if offset % dtype.itemsize or base % dtype.itemsize:
            fail("accessor_component_alignment")
        if vertex and (offset % 4 or base % 4 or stride % 4):
            fail("vertex_alignment")
        if tight and "byteStride" in view:
            fail("nonvertex_stride")
        if stride < element or offset + (count-1)*stride + element > view["byteLength"]:
            fail("accessor_bounds")
        key = index
        if key not in self.cache:
            array = np.ndarray((count, width), dtype=dtype, buffer=self.bin,
                               offset=base+offset, strides=(stride, dtype.itemsize))
            if ct == 5126:
                finite(array)
            self.cache[key] = array
        return self.cache[key]

    def bounds(self, index, array):
        accessor = self.accessors[index]
        dtype = COMPONENTS[accessor["componentType"]]
        low_json = finite(np.asarray(accessor.get("min"), dtype=np.float64))
        high_json = finite(np.asarray(accessor.get("max"), dtype=np.float64))
        # glTF bounds are interpreted in their component type, including FLOAT rounding.
        low = finite(low_json.astype(dtype)).astype(np.float64)
        high = finite(high_json.astype(dtype)).astype(np.float64)
        actual_low = np.min(array.astype(np.float64), axis=0)
        actual_high = np.max(array.astype(np.float64), axis=0)
        if (low.shape != actual_low.shape or high.shape != actual_high.shape
                or not np.array_equal(low, actual_low) or not np.array_equal(high, actual_high)):
            fail("accessor_min_max_missing_or_inaccurate")

    def worlds(self, animation, time):
        local, morph = [], {}
        for index, (kind, value) in enumerate(self.base):
            changes = animation.get(index, {})
            if kind == "matrix":
                if any(k != "weights" for k in changes):
                    fail("animated_matrix_node")
                local.append(value)
            else:
                t, q, s = value
                t = sample(changes["translation"], time) if "translation" in changes else t
                q = sample(changes["rotation"], time) if "rotation" in changes else q
                s = sample(changes["scale"], time) if "scale" in changes else s
                local.append(trs(t, q, s))
            if "weights" in changes:
                morph[index] = sample(changes["weights"], time)
        result = [None] * len(self.nodes)
        def global_matrix(index):
            if result[index] is None:
                parent = self.parents[index]
                result[index] = finite(local[index] if parent == -1
                                       else global_matrix(parent) @ local[index])
            return result[index]
        for index in range(len(self.nodes)):
            global_matrix(index)
        return result, morph

    def animations(self, meshes):
        values = self.doc.get("animations", [])
        if len(values) != 3 or {v.get("name") for v in values} != set(CLIPS):
            fail("three_named_animations_required")
        mesh_by_node = {m["node"]: m for m in meshes}
        result = {}
        for animation in values:
            samplers = animation.get("samplers", [])
            if not samplers or len(samplers) > 16384:
                fail("animation_sampler_budget")
            tracks = {}
            for channel in animation.get("channels", []):
                si = integer(channel.get("sampler"), 0, len(samplers)-1)
                sampler = samplers[si]
                if sampler.get("interpolation", "LINEAR") != "LINEAR":
                    fail("pilot_requires_linear_interpolation")
                target = channel.get("target", {})
                node = integer(target.get("node"), 0, len(self.nodes)-1)
                if node not in self.reachable:
                    fail("animation_target_not_in_scene")
                path = target.get("path")
                if path not in ("translation", "rotation", "scale", "weights"):
                    fail("animation_target_path")
                if path in tracks.setdefault(node, {}):
                    fail("duplicate_animation_channel")
                input_array = self.read(sampler.get("input"), "SCALAR", (5126,), tight=True)
                self.bounds(sampler["input"], input_array)
                times = input_array[:, 0].astype(np.float64)
                if len(times) != KEY_COUNT or not np.all(np.diff(times) > 0) or not np.allclose(
                        times, np.arange(KEY_COUNT)/SAMPLE_RATE, atol=1e-7, rtol=0):
                    fail("animation_97_times")
                expected = "SCALAR" if path == "weights" else ("VEC4" if path == "rotation" else "VEC3")
                data = self.read(sampler.get("output"), expected, (5126,), tight=True).astype(np.float64)
                if path == "weights":
                    if node not in mesh_by_node:
                        fail("weights_target_not_mesh")
                    count = mesh_by_node[node]["target_count"]
                    if data.shape != (KEY_COUNT*count, 1):
                        fail("animation_morph_output_shape")
                    data = data.reshape(KEY_COUNT, count)
                elif data.shape[0] != KEY_COUNT:
                    fail("animation_trs_output_shape")
                if path == "rotation":
                    for q in data:
                        quaternion(q)
                tracks[node][path] = {"times": times, "values": data, "rotation": path == "rotation"}
            if any("weights" not in tracks.get(m["node"], {}) for m in meshes):
                fail("mesh_corrective_animation_missing")
            result[animation["name"]] = tracks
        return result


def sample(track, time):
    times, data = track["times"], track["values"]
    if time <= times[0]:
        return data[0].copy()
    if time >= times[-1]:
        return data[-1].copy()
    left = int(np.searchsorted(times, time, side="right")) - 1
    factor = float((time-times[left])/(times[left+1]-times[left]))
    return slerp(data[left], data[left+1], factor) if track["rotation"] else (
        (1-factor)*data[left] + factor*data[left+1])


def load_reference(path, npz_path):
    path, npz_path = Path(path), Path(npz_path)
    if (path.stat().st_size != FROZEN_JSON_BYTES
            or hashlib.sha256(path.read_bytes()).hexdigest() != FROZEN_JSON_SHA256
            or npz_path.stat().st_size != FROZEN_NPZ_BYTES):
        fail("frozen315_reference_bytes_changed")
    with npz_path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != FROZEN_NPZ_SHA256:
            fail("frozen315_npz_hash_changed")
    if not 1 <= path.stat().st_size <= MAX_REFERENCE_JSON:
        fail("reference_json_budget")
    reference = json.loads(path.read_text(encoding="utf-8"))
    required = {"schema_version": 1, "coordinate_system": "RH_Y_UP_METERS",
                "axis_conversion": "BLENDER_Z_UP_TO_GLTF_Y_UP_X_Z_NEGY",
                "stage": "ARMATURE_ONLY", "position_space": "MESH_LOCAL_IDENTITY_WORLD",
                "fps": SOURCE_FPS, "export_sample_rate": SAMPLE_RATE,
                "sampling_contract": "native48hz_keys291_holdouts24_v1",
                "authored_tolerance_world_m": AUTHORED_TOL,
                "fractional_tolerance_world_m": FRACTIONAL_TOL,
                "joint_matrix_tolerance": JOINT_TOL,
                "fractional_joint_matrix_tolerance": FRACTIONAL_JOINT_TOL}
    for key, value in required.items():
        if reference.get(key) != value:
            fail("reference_contract_" + key)
    frames, fractional = reference.get("frames", []), reference.get("fractional_frames", [])
    expected_frames = [(c, k/2.0) for c in CLIPS for k in range(KEY_COUNT)]
    if len(frames) != TARGET_COUNT:
        fail("reference_authored_frame_count")
    for index, (row, (clip, frame)) in enumerate(zip(frames, expected_frames)):
        if (type(row.get("row")) is not int or row["row"] != index or row.get("clip") != clip
                or type(row.get("frame")) not in (int, float) or row["frame"] != frame
                or type(row.get("time")) not in (int, float) or not math.isfinite(row["time"])
                or abs(row["time"]-frame/SOURCE_FPS) > 1e-10):
            fail("reference_authored_frame_mapping")
    if len(fractional) != HOLDOUT_COUNT:
        fail("reference_fractional_frame_count")
    for index, row in enumerate(fractional):
        frame, time = row.get("frame"), row.get("time")
        if (type(row.get("row")) is not int or row["row"] != index or row.get("clip") not in CLIPS
                or type(frame) not in (int, float) or not math.isfinite(frame)
                or frame not in QUARTER_FRAMES or type(time) not in (int, float)
                or not math.isfinite(time) or abs(time-frame/SOURCE_FPS) > 1e-10):
            fail("reference_fractional_frame_mapping")
    if any(sorted(float(row["frame"]) for row in fractional if row["clip"] == c) !=
           list(QUARTER_FRAMES) for c in CLIPS):
        fail("reference_fractional_clip_times")
    meshes, joints = reference.get("meshes", []), reference.get("joints", [])
    if len(meshes) != 2 or not 1 <= len(joints) <= 4096:
        fail("reference_mesh_or_joint_count")
    for index, mesh in enumerate(meshes):
        if mesh.get("index") != index or not isinstance(mesh.get("node_name"), str):
            fail("reference_mesh_mapping")
        count = integer(mesh.get("vertex_count"), 1, 20000)
        ids = mesh.get("source_point_ids", [])
        if (len(ids) != count or any(type(v) is not int or v < 1 for v in ids)
                or len(set(ids)) != count):
            fail("reference_source_point_ids")
    if len({j.get("node_name") for j in joints}) != len(joints):
        fail("reference_joint_names")
    for index, joint in enumerate(joints):
        if joint.get("index") != index or not isinstance(joint.get("node_name"), str):
            fail("reference_joint_mapping")
        parent = integer(joint.get("parent_index"), -1, len(joints)-1)
        if parent == index:
            fail("reference_joint_parent")
    needed = {"joint_world", "fractional_joint_world"}
    for mesh in meshes:
        needed.update((mesh["position_key"], mesh["fractional_position_key"]))
    if len(needed) != 6:
        fail("reference_npz_keys_not_independent")
    if not 1 <= npz_path.stat().st_size <= MAX_REFERENCE_EXPANDED:
        fail("reference_npz_compressed_budget")
    if "reference_npz_bytes" in reference and reference["reference_npz_bytes"] != npz_path.stat().st_size:
        fail("reference_npz_size_mismatch")
    if "reference_npz_sha256" in reference:
        with npz_path.open("rb") as source:
            actual_hash = hashlib.file_digest(source, "sha256").hexdigest()
        if reference["reference_npz_sha256"] != actual_hash:
            fail("reference_npz_hash_mismatch")
    with zipfile.ZipFile(npz_path) as archive:
        infos = archive.infolist()
        if (len(infos) != 6 or len({i.filename for i in infos}) != 6
                or sum(i.file_size for i in infos) > MAX_REFERENCE_EXPANDED
                or any(i.file_size > MAX_REFERENCE_EXPANDED//2 for i in infos)
                or {i.filename for i in infos} != {key+".npy" for key in needed}):
            fail("reference_npz_budget_or_members")
    arrays = {}
    with np.load(npz_path, allow_pickle=False) as archive:
        if set(archive.files) != needed:
            fail("reference_npz_keys")
        for key in needed:
            array = archive[key]
            if array.dtype.kind != "f" or array.dtype.itemsize not in (4, 8):
                fail("reference_npz_dtype")
            arrays[key] = finite(array)
    shapes = {"joint_world": (TARGET_COUNT, len(joints), 4, 4),
              "fractional_joint_world": (HOLDOUT_COUNT, len(joints), 4, 4)}
    for mesh in meshes:
        shapes[mesh["position_key"]] = (TARGET_COUNT, mesh["vertex_count"], 3)
        shapes[mesh["fractional_position_key"]] = (HOLDOUT_COUNT, mesh["vertex_count"], 3)
    if any(arrays[key].shape != shape for key, shape in shapes.items()):
        fail("reference_npz_shape")
    for key in ("joint_world", "fractional_joint_world"):
        if not np.allclose(arrays[key][:, :, 3, :], (0, 0, 0, 1), atol=1e-7, rtol=0):
            fail("reference_joint_matrix_affine")
    return reference, arrays


def native_error(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1e-6:
        fail("capture_native_error_bounds")
    return float(value)


def validate_capture_registry(reference):
    """Check writer-native capture metadata; do not re-evaluate source bpy or weights."""
    proof = reference.get("identity_proof")
    if not isinstance(proof, dict):
        fail("capture_identity_proof_missing")
    registry = proof.get("pose_registry")
    if not isinstance(registry, list) or len(registry) != NATIVE_POSE_COUNT:
        fail("capture_pose_registry_count")
    provenance = reference.get("provenance")
    if not isinstance(provenance, dict):
        fail("capture_provenance_missing")
    required = {"cached_run": 38688634504, "inherited_pose_count": 159,
                "newly_captured_pose_count": 156, "old_half_validation_reclassified_as_keys": 12}
    for name, expected in required.items():
        if type(provenance.get(name)) is not int or provenance[name] != expected:
            fail("capture_provenance_" + name)
    sentinel = provenance.get("overlap_sentinel")
    if (not isinstance(sentinel, dict) or sentinel.get("clip") != "wave"
            or type(sentinel.get("frame")) not in (int, float) or sentinel["frame"] != 12.5
            or sentinel.get("passed") is not True
            or sentinel.get("source_mapping_signatures_match") is not True
            or sentinel.get("native_membership_passed") is not True):
        fail("capture_overlap_sentinel")
    sentinel_errors = {name: native_error(sentinel.get(name)) for name in (
        "maximum_position_error", "maximum_joint_matrix_error",
        "zero_pre_armature_maximum_world_error")}
    expected = {}
    for phase, rows in (("authored", reference["frames"]), ("fractional", reference["fractional_frames"])):
        for row in rows:
            frame, clip = float(row["frame"]), row["clip"]
            if phase == "fractional":
                origin = "new_quarter"
            elif frame.is_integer():
                origin = "cached_integer"
            elif frame in CACHED_HALF_FRAMES:
                origin = "cached_half"
            else:
                origin = "new_half"
            key = (clip, frame)
            if key in expected:
                fail("capture_reference_pose_duplicate")
            expected[key] = (phase, row["row"], origin)
    if len(expected) != NATIVE_POSE_COUNT:
        fail("capture_reference_pose_count")
    seen, counts, maximum = set(), {
        "cached_integer": 0, "cached_half": 0, "new_half": 0, "new_quarter": 0}, 0.0
    for item in registry:
        if not isinstance(item, dict) or item.get("clip") not in CLIPS:
            fail("capture_registry_record")
        frame = item.get("frame")
        if type(frame) not in (int, float) or not math.isfinite(frame):
            fail("capture_registry_frame")
        key = (item["clip"], float(frame))
        if key in seen or key not in expected or type(item.get("row")) is not int:
            fail("capture_registry_pose_mapping")
        actual = (item.get("phase"), item["row"], item.get("origin"))
        if actual != expected[key] or item.get("membership_passed") is not True:
            fail("capture_registry_provenance_or_membership")
        maximum = max(maximum, native_error(item.get("zero_pre_armature_maximum_world_error")))
        seen.add(key)
        counts[item["origin"]] += 1
    if seen != set(expected) or counts != {
            "cached_integer": 147, "cached_half": 12, "new_half": 132, "new_quarter": 24}:
        fail("capture_registry_not_disjoint_exhaustive")
    return {"native_pose_count": len(seen), "per_pose_registry_checked": True,
            "origin_counts": counts, "cached_run": required["cached_run"],
            "inherited_pose_count": 159, "newly_captured_pose_count": 156,
            "old_half_validation_reclassified_as_keys": 12,
            "registry_zero_pre_armature_maximum_world_error": maximum,
            "overlap_sentinel": {"clip": "wave", "frame": 12.5, "passed": True,
                                 "source_mapping_signatures_match": True,
                                 "native_membership_passed": True, **sentinel_errors},
            "sentinel_is_additional_registry_pose": False,
            "classification_provenance": "writer-native guarded cached/new metadata",
            "native_capture_and_source_membership_independently_recomputed": False}


def validate_identity_reference(reference, arrays):
    """Validate writer-native-guarded zero-binding provenance, not source bpy data."""
    joints = reference["joints"]
    kinds = [joint.get("kind") for joint in joints]
    if any(kind not in ("native", "auxiliary_identity") for kind in kinds):
        fail("joint_kind_missing_or_unknown")
    auxiliary = [i for i, kind in enumerate(kinds) if kind == "auxiliary_identity"]
    if len(auxiliary) > 1 or not any(kind == "native" for kind in kinds):
        fail("identity_joint_count")
    if not auxiliary:
        if reference.get("identity_proof") is not None:
            fail("identity_proof_without_helper")
        return {"index": None, "meshes": {}, "summary": {
            "auxiliary_identity_joint_count": 0, "native_joint_count": len(joints),
            "classification_provenance": "not_applicable",
            "independently_decoded_source_weights": False}}
    index = auxiliary[0]
    if (index != len(joints)-1 or joints[index]["parent_index"] != -1
            or joints[index]["node_name"] != "exportaux_identityjoint"
            or any(joint["parent_index"] == index for joint in joints)):
        fail("identity_joint_not_explicit_last_root")
    proof = reference.get("identity_proof")
    if not isinstance(proof, dict) or proof.get("schema") != "coop-armature-zero-identity-v1" or proof.get("joint_index") != index:
        fail("identity_proof_schema")
    membership, pre = proof.get("membership", {}), proof.get("pre_armature", {})
    if (membership.get("raw_source_raw_clone_evaluated_equal") is not True
            or membership.get("full_membership_compared") is not True
            or membership.get("poses_checked") != NATIVE_POSE_COUNT
            or pre.get("poses_checked") != NATIVE_POSE_COUNT
            or pre.get("tolerance_world_m") != 1e-6
            or pre.get("all_zero_eligible_vertices_compared") is not True):
        fail("identity_provenance_guards_missing")
    error = pre.get("maximum_world_error")
    if type(error) not in (int, float) or not math.isfinite(error) or not 0 <= error <= 1e-6:
        fail("identity_pre_armature_error_exceeded")
    proofs = proof.get("meshes", [])
    if not isinstance(proofs, list) or len(proofs) != len(reference["meshes"]):
        fail("identity_mesh_proofs_missing")
    by_mesh, compact = {}, []
    for item in proofs:
        mesh_index = integer(item.get("index"), 0, len(reference["meshes"])-1)
        if mesh_index in by_mesh:
            fail("identity_mesh_proof_duplicate")
        ref = reference["meshes"][mesh_index]
        ids = item.get("source_point_ids", [])
        if not isinstance(ids, list) or any(type(v) is not int or not 1 <= v <= 0xffffffff for v in ids):
            fail("identity_source_point_ids")
        count = integer(item.get("zero_eligible_count"), 0, ref["vertex_count"])
        if len(ids) != count or len(set(ids)) != count or not set(ids).issubset(ref["source_point_ids"]):
            fail("identity_source_point_ids_correspondence")
        packed = struct.pack("<" + str(len(ids)) + "I", *ids) if ids else b""
        ids_hash = hashlib.sha256(packed).hexdigest()
        if item.get("ids_hash_encoding") != "uint32_le" or item.get("ids_sha256") != ids_hash:
            fail("identity_source_point_ids_hash")
        hashes = [item.get(key) for key in ("raw_source_sha256", "raw_clone_sha256", "evaluated_sha256")]
        if (any(not isinstance(value, str) or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value) for value in hashes)
                or len(set(hashes)) != 1):
            fail("identity_full_membership_hashes")
        by_mesh[mesh_index] = set(ids)
        compact.append({"mesh_index": mesh_index, "zero_eligible_count": count,
                        "source_point_ids_sha256": ids_hash,
                        "full_membership_sha256": hashes[0]})
    if sum(len(ids) for ids in by_mesh.values()) == 0:
        fail("identity_helper_without_zero_vertices")
    for key in ("joint_world", "fractional_joint_world"):
        if not np.array_equal(arrays[key][:, index], np.broadcast_to(np.eye(4), arrays[key][:, index].shape)):
            fail("identity_native_reference_not_identity")
    return {"index": index, "meshes": by_mesh, "summary": {
        "auxiliary_identity_joint_count": 1, "native_joint_count": len(joints)-1,
        "classification_provenance": "writer-native-guarded full membership and pre-Armature comparison",
        "independently_decoded_source_weights": False,
        "native_pre_armature_comparison_independently_recomputed": False,
        "writer_membership_poses_checked": NATIVE_POSE_COUNT,
        "writer_pre_armature_poses_checked": NATIVE_POSE_COUNT,
        "writer_pre_armature_tolerance_world_m": 1e-6,
        "writer_pre_armature_maximum_world_error": float(error), "meshes": compact}}


def validate_identity_node(glb, reference, joint_nodes, identity, animations):
    index = identity["index"]
    marked = [i for i, node in enumerate(glb.nodes)
              if node.get("extras", {}).get("coop_joint_kind") == "auxiliary_identity"]
    if index is None:
        if marked:
            fail("unreferenced_identity_node")
        return
    node_index = joint_nodes[index]
    node = glb.nodes[node_index]
    if (marked != [node_index] or glb.parents[node_index] != COMMON_ROOT or node.get("children")
            or "mesh" in node or "skin" in node):
        fail("identity_node_not_explicit_common_root_leaf")
    kind, base = glb.base[node_index]
    if kind != "trs" or not np.array_equal(trs(*base), np.eye(4)):
        fail("identity_node_default_not_static_identity_trs")
    for clip in CLIPS:
        for path, track in animations[clip].get(node_index, {}).items():
            values = track["values"]
            if path == "translation":
                valid = np.array_equal(values, np.zeros_like(values))
            elif path == "scale":
                valid = np.array_equal(values, np.ones_like(values))
            elif path == "rotation":
                valid = all(np.array_equal(rotation_matrix(q), np.eye(3)) for q in values)
            else:
                valid = False
            if not valid:
                fail("identity_node_animation_not_static_identity")


def validate_identity_bindings(meshes, identity):
    index = identity["index"]
    if index is None:
        return
    for mesh in meshes:
        if not np.array_equal(mesh["ibm"][index], np.eye(4)):
            fail("identity_inverse_bind_not_identity")
        proven_ids = identity["meshes"][mesh["reference"]["index"]]
        zero = np.array([pid in proven_ids for pid in mesh["reference"]["source_point_ids"]], dtype=bool)
        helper = mesh["joints"] == index
        helper_weights = np.where(helper, mesh["weights"], 0.0).sum(axis=1)
        if (not np.array_equal(helper_weights[zero], np.ones(int(np.count_nonzero(zero))))
                or np.any(mesh["weights"][zero][~helper[zero]] != 0)
                or np.any(helper_weights[~zero] != 0)):
            fail("identity_weights_not_exact_proved_zero_binding")


def read_meshes(glb, reference):
    d = glb.doc
    meshes, skins = d.get("meshes", []), d.get("skins", [])
    if len(meshes) != 2 or len(skins) != 2:
        fail("pilot_mesh_skin_count")
    joint_nodes = []
    for joint in reference["joints"]:
        if joint["node_name"] not in glb.names:
            fail("reference_joint_node_missing")
        node = glb.names[joint["node_name"]]
        if node not in glb.reachable:
            fail("joint_not_in_scene")
        joint_nodes.append(node)
    palette = {node: index for index, node in enumerate(joint_nodes)}
    for index, node in enumerate(joint_nodes):
        p = glb.parents[node]
        while p != -1 and p not in palette:
            p = glb.parents[p]
        if (palette[p] if p != -1 else -1) != reference["joints"][index]["parent_index"]:
            fail("joint_parent_correspondence")
    result = []
    for ref in reference["meshes"]:
        if ref["node_name"] not in glb.names:
            fail("mesh_node_missing")
        node_index = glb.names[ref["node_name"]]
        node = glb.nodes[node_index]
        if node_index not in glb.reachable or node.get("mesh") != ref["index"]:
            fail("mesh_node_correspondence")
        skin_index = integer(node.get("skin"), 0, len(skins)-1)
        skin = skins[skin_index]
        if skin.get("joints") != joint_nodes:
            fail("skin_palette_correspondence")
        if skin.get("skeleton") != COMMON_ROOT:
            fail("skin_requires_known_common_root")
        ancestor = integer(skin["skeleton"], 0, len(glb.nodes)-1)
        for j in joint_nodes:
            p = j
            while p != -1 and p != ancestor:
                p = glb.parents[p]
            if p == -1:
                fail("skin_skeleton_not_common_ancestor")
        ib = glb.read(skin.get("inverseBindMatrices"), "MAT4", (5126,), tight=True)
        if len(ib) != len(joint_nodes):
            fail("inverse_bind_count")
        ib = ib[:len(joint_nodes)].astype(np.float64).reshape(-1, 4, 4).transpose(0, 2, 1)
        if (not np.allclose(ib[:, 3, :], (0, 0, 0, 1), atol=0, rtol=0)
                or np.any(np.abs(np.linalg.det(ib)) <= 1e-12)):
            fail("inverse_bind_affine_or_invertible")
        primitives = meshes[ref["index"]].get("primitives", [])
        if len(primitives) != 1:
            fail("pilot_one_primitive_per_mesh")
        primitive = primitives[0]
        if primitive.get("mode", 4) != 4 or primitive.get("extensions"):
            fail("pilot_triangles_only")
        attrs = primitive.get("attributes", {})
        position = glb.read(attrs.get("POSITION"), "VEC3", (5126,), vertex=True).astype(np.float64)
        glb.bounds(attrs["POSITION"], position)
        count = ref["vertex_count"]
        if position.shape != (count, 3):
            fail("position_reference_count")
        indices = glb.read(primitive.get("indices"), "SCALAR", (5123, 5125), tight=True)[:, 0]
        if len(indices) % 3 or int(np.max(indices)) >= count:
            fail("triangle_indices")
        sets = sorted(int(k[7:]) for k in attrs if k.startswith("JOINTS_") and k[7:].isdigit())
        weight_sets = sorted(int(k[8:]) for k in attrs if k.startswith("WEIGHTS_") and k[8:].isdigit())
        if not sets or sets != list(range(len(sets))) or weight_sets != sets or len(sets) > 16:
            fail("joint_weight_set_layout")
        joints = np.concatenate([glb.read(attrs["JOINTS_"+str(i)], "VEC4", (5121, 5123), vertex=True)
                                 for i in sets], axis=1).astype(np.int64)
        weights = np.concatenate([glb.read(attrs["WEIGHTS_"+str(i)], "VEC4", (5126,), vertex=True)
                                  for i in sets], axis=1).astype(np.float64)
        if (joints.shape != weights.shape or len(joints) != count
                or np.min(joints) < 0 or np.max(joints) >= len(joint_nodes)
                or np.min(weights) < 0):
            fail("joint_weight_values")
        nonzero = np.count_nonzero(weights, axis=1)
        sums = weights.sum(axis=1)
        if np.any(nonzero == 0) or np.any(np.abs(sums-1.0) > np.maximum(2e-7*nonzero, 2e-7)):
            fail("weight_sum_not_normalized")
        for js, ws in zip(joints, weights):
            ids = js[ws > 0]
            if len(set(int(v) for v in ids)) != len(ids):
                fail("positive_joint_index_repeated")
        targets = primitive.get("targets", [])
        if len(targets) != TARGET_COUNT:
            fail("pilot_291_correctives_required")
        morphs = []
        for target in targets:
            if set(target) != {"POSITION"}:
                fail("pilot_position_only_corrective")
            morph = glb.read(target["POSITION"], "VEC3", (5126,), vertex=True)
            if morph.shape != (count, 3):
                fail("morph_position_count")
            glb.bounds(target["POSITION"], morph)
            morphs.append(morph)
        default = node.get("weights", meshes[ref["index"]].get("weights", [0]*TARGET_COUNT))
        default = finite(np.asarray(default, dtype=np.float64))
        if default.shape != (TARGET_COUNT,):
            fail("default_morph_weights")
        result.append({"name": ref["node_name"], "node": node_index, "reference": ref,
                       "position": position, "morphs": morphs, "target_count": TARGET_COUNT,
                       "default": default, "joints": joints, "weights": weights,
                       "ibm": ib, "sets": len(sets),
                       "max_influences": int(np.max(nonzero)),
                       "weight_sum_max_error": float(np.max(np.abs(sums-1.0)))})
    return result, joint_nodes


def pose_mesh(mesh, worlds, morph_weights):
    world = worlds[mesh["node"]]
    if float(np.max(np.abs(world-np.eye(4)))) > 1e-7:
        fail("pilot_mesh_world_not_identity")
    values = morph_weights.get(mesh["node"], mesh["default"])
    pre = mesh["position"].copy()
    for index in np.flatnonzero(values):
        pre += mesh["morphs"][int(index)].astype(np.float64)*float(values[index])
    globals_ = np.stack([worlds[int(node)] for node in mesh["joint_nodes"]])
    joint = np.matmul(globals_, mesh["ibm"])
    # Use every stored set as-is. No weight renormalization or homogeneous divide.
    matrix = np.einsum("nk,nkij->nij", mesh["weights"], joint[mesh["joints"]])
    predicted = finite(np.einsum("nij,nj->ni", matrix[:, :3, :3], pre)+matrix[:, :3, 3])
    singular = np.linalg.svd(matrix[:, :3, :3], compute_uv=False)
    smallest = singular[:, -1]
    condition = np.divide(singular[:, 0], smallest,
                          out=np.full_like(smallest, np.inf), where=smallest > 0)
    condition_passed = bool(np.isfinite(condition).all() and np.max(condition) <= CONDITION_CAP)
    finite_conditions = condition[np.isfinite(condition)]
    maximum = float(np.max(finite_conditions)) if len(finite_conditions) else None
    return predicted, {"maximum_finite_condition": maximum,
                       "nonfinite_condition_count": int(np.count_nonzero(~np.isfinite(condition))),
                       "condition_passed": condition_passed}



def validate_common_factor_graph(glb, reference, joint_nodes, meshes, animations):
    """Validate the serialized, non-skin ownership graph without trusting writer metadata."""
    if (len(reference["joints"]) != PALETTE_SIZE or joint_nodes != list(range(PALETTE_SIZE))
            or [j["kind"] for j in reference["joints"]] != ["native"]*NATIVE_JOINTS+["auxiliary_identity"]
            or identity_index(reference) != NATIVE_JOINTS):
        fail("factor_fixed_native_palette")
    nodes = glb.nodes
    if len(nodes) < PALETTE_SIZE+3:
        fail("factor_node_inventory")
    root = nodes[COMMON_ROOT]
    marked_roots = [i for i, n in enumerate(nodes)
                    if n.get("extras", {}).get("coop_export_common_root") is True]
    if (marked_roots != [COMMON_ROOT] or root.get("name") != "COOP_Export_CommonRoot"
            or root.get("extras") != {"coop_export_common_root": True}
            or glb.parents[COMMON_ROOT] != -1
            or any(k in root for k in ("mesh", "skin", "weights"))
            or any(COMMON_ROOT in animations[c] for c in CLIPS)):
        fail("factor_common_root_identity_or_ownership")
    kind, value = glb.base[COMMON_ROOT]
    matrix = value if kind == "matrix" else trs(*value)
    if not np.array_equal(matrix, np.eye(4)):
        fail("factor_common_root_not_static_identity")
    owners, tail_markers = {}, {}
    for index, node in enumerate(nodes):
        extras = node.get("extras", {})
        if "coop_affine_factor" in extras:
            data = extras["coop_affine_factor"]
            if (not isinstance(data, dict) or set(data) != {"native_palette_index", "stage"}
                    or extras != {"coop_affine_factor": data}):
                fail("factor_helper_marker_shape")
            owner = integer(data["native_palette_index"], 0, NATIVE_JOINTS-1)
            stage = integer(data["stage"], 0, 5)
            if (index < COMMON_ROOT+1 or index >= len(nodes)-2
                    or stage in owners.setdefault(owner, {})
                    or any(k in node for k in ("mesh", "skin", "weights"))
                    or glb.base[index][0] != "trs"):
                fail("factor_helper_owner_or_kind")
            owners[owner][stage] = index
        if "coop_native_affine_tail" in extras:
            owner = integer(extras["coop_native_affine_tail"], 0, NATIVE_JOINTS-1)
            if index != owner or extras != {"coop_native_affine_tail": owner} or owner in tail_markers:
                fail("factor_native_tail_marker")
            tail_markers[owner] = index
    if set(owners) != set(tail_markers):
        fail("factor_helper_tail_owner_mismatch")
    paths = {}
    owned = set()
    for index in range(NATIVE_JOINTS):
        stages = owners.get(index)
        if stages is not None:
            if set(stages) != set(range(6)):
                fail("factor_requires_exact_six_stages")
            prefix = [stages[k] for k in range(6)]
            owned.update(prefix)
        else:
            prefix = []
        paths[index] = prefix+[index]
    expected_helpers = set(range(COMMON_ROOT+1, len(nodes)-2))
    if (owned != expected_helpers or len(owned) != len(owners)*6
            or len(nodes) != PALETTE_SIZE+1+len(owned)+2):
        fail("factor_unowned_or_extra_node")
    expected_parent = [-1]*len(nodes)
    for index in range(NATIVE_JOINTS):
        parent = reference["joints"][index]["parent_index"]
        if parent != -1:
            integer(parent, 0, NATIVE_JOINTS-1)
        prior = COMMON_ROOT if parent == -1 else parent
        for node in paths[index]:
            expected_parent[node] = prior
            prior = node
    expected_parent[NATIVE_JOINTS] = COMMON_ROOT
    if glb.parents != expected_parent:
        fail("factor_exact_parent_chain")
    for index, node in enumerate(nodes):
        expected_children = {i for i, p in enumerate(expected_parent) if p == index}
        actual_children = node.get("children", [])
        if len(actual_children) != len(set(actual_children)) or set(actual_children) != expected_children:
            fail("factor_exact_children")
    mesh_nodes = [m["node"] for m in meshes]
    if mesh_nodes != [len(nodes)-2, len(nodes)-1]:
        fail("factor_mesh_nodes_must_be_last")
    scenes = glb.doc["scenes"]
    scene = scenes[glb.doc.get("scene", 0)]
    if (set(scene["nodes"]) != {COMMON_ROOT, *mesh_nodes} or len(scene["nodes"]) != 3
            or glb.reachable != set(range(len(nodes)))):
        fail("factor_selected_scene_inventory")
    for index in range(NATIVE_JOINTS):
        if glb.base[index][0] != "trs" or any(k in nodes[index] for k in ("mesh", "skin", "weights")):
            fail("factor_native_node_kind")
    for clip in CLIPS:
        for index in set(range(PALETTE_SIZE)) | owned:
            if set(animations[clip].get(index, {})) != {"translation", "rotation", "scale"}:
                fail("factor_all_trs_channels_required")
        for mesh in meshes:
            node = mesh["node"]
            if (glb.parents[node] != -1 or nodes[node].get("skin") != mesh["reference"]["index"]
                    or set(animations[clip].get(node, {})) != {"weights"}):
                fail("factor_mesh_scene_or_animation")
            kind, value = glb.base[node]
            if not np.array_equal(value if kind == "matrix" else trs(*value), np.eye(4)):
                fail("factor_mesh_default_identity")
    for skin in glb.doc["skins"]:
        if skin.get("skeleton") != COMMON_ROOT or skin.get("joints") != list(range(PALETTE_SIZE)):
            fail("factor_skin_common_ancestor")
        for joint in skin["joints"]:
            current, visited = joint, set()
            while current != COMMON_ROOT:
                if current == -1 or current in visited or current not in glb.reachable:
                    fail("factor_skin_common_ancestor_or_cycle")
                visited.add(current)
                current = glb.parents[current]
    return {"paths": paths, "factored": set(owners), "helpers": owned,
            "summary": {"common_root_node": COMMON_ROOT, "common_root_name": root["name"],
                        "common_root_static_identity": True, "all_skin_joints_common_scene_ancestor": True,
                        "native_palette_size": PALETTE_SIZE, "native_joint_count": NATIVE_JOINTS,
                        "affine_helper_count": len(owned), "factored_native_joint_count": len(owners),
                        "factored_native_palette_indices": sorted(owners),
                        "auxiliary_identity_joint_count": 1, "helper_nodes_in_skin_palette": False,
                        "fixed_graph_all_clips": True, "all_nodes_owned_reachable_acyclic": True}}


def identity_index(reference):
    found = [i for i, j in enumerate(reference["joints"]) if j.get("kind") == "auxiliary_identity"]
    return found[0] if len(found) == 1 else None


def validate_genuine_source(glb, reference, source_path):
    """Read only the pinned legacy container, not its invalid common-ancestor layout."""
    source = Glb(source_path, expected_contract=SOURCE_CONTRACT)
    if len(source.raw) != SOURCE_GLB_BYTES or hashlib.sha256(source.raw).hexdigest() != SOURCE_GLB_SHA256:
        fail("genuine_source_glb_pin")
    if len(source.nodes) != PALETTE_SIZE+2:
        fail("genuine_source_node_inventory")
    for index, joint in enumerate(reference["joints"]):
        if (source.names.get(joint["node_name"]) != index or glb.names.get(joint["node_name"]) != index
                or source.parents[index] != joint["parent_index"]):
            fail("genuine_source_palette_name_or_native_parent")
    if len(source.doc.get("skins", [])) != 2 or len(source.doc.get("meshes", [])) != 2:
        fail("genuine_source_skin_mesh_inventory")
    payloads = []
    bind_signs = []
    for index in range(NATIVE_JOINTS):
        kind, value = source.base[index]
        if kind != "trs":
            fail("genuine_source_bind_trs")
        scales = finite(np.asarray(value[2], dtype=np.float64))
        if scales.shape != (3,) or np.any(np.abs(scales) <= 1e-8):
            fail("genuine_source_bind_scale_sign")
        bind_signs.append(np.sign(scales))
    for ref in reference["meshes"]:
        old_node = source.names.get(ref["node_name"])
        new_node = glb.names.get(ref["node_name"])
        if old_node != PALETTE_SIZE+ref["index"] or new_node != len(glb.nodes)-2+ref["index"]:
            fail("genuine_source_mesh_node_mapping")
        old = source.nodes[old_node]
        new = glb.nodes[new_node]
        if old.get("mesh") != ref["index"] or new.get("mesh") != ref["index"]:
            fail("genuine_source_mesh_index")
        for container, node in ((source, old), (glb, new)):
            skin = container.doc["skins"][integer(node.get("skin"), 0, 1)]
            if skin.get("joints") != list(range(PALETTE_SIZE)):
                fail("genuine_source_skin_palette")
        old_primitives = source.doc["meshes"][ref["index"]].get("primitives", [])
        new_primitives = glb.doc["meshes"][ref["index"]].get("primitives", [])
        if len(old_primitives) != 1 or len(new_primitives) != 1:
            fail("genuine_source_primitive_inventory")
        a, b = old_primitives[0], new_primitives[0]
        if a.get("mode", 4) != 4 or b.get("mode", 4) != 4:
            fail("genuine_source_triangle_mode")
        attrs, new_attrs = a.get("attributes", {}), b.get("attributes", {})
        if (set(attrs) != set(new_attrs) or "POSITION" not in attrs
                or any(k != "POSITION" and not (
                    k.startswith("JOINTS_") and k[7:].isdigit() or
                    k.startswith("WEIGHTS_") and k[8:].isdigit()) for k in attrs)):
            fail("genuine_source_attribute_sets_changed")
        components = []
        for label in sorted(attrs)+["indices"]:
            old_accessor = a.get("indices") if label == "indices" else attrs[label]
            new_accessor = b.get("indices") if label == "indices" else new_attrs[label]
            old_data, new_data = source.read(old_accessor), glb.read(new_accessor)
            old_meta, new_meta = source.accessors[old_accessor], glb.accessors[new_accessor]
            if (any(old_meta.get(k) != new_meta.get(k) for k in ("componentType", "type", "count"))
                    or old_data.shape != new_data.shape or old_data.dtype != new_data.dtype
                    or old_data.tobytes(order="C") != new_data.tobytes(order="C")):
                fail("genuine_source_value_bytes_changed")
            components.append({"semantic": label, "bytes": old_data.nbytes,
                               "sha256": hashlib.sha256(old_data.tobytes(order="C")).hexdigest()})
        payloads.append({"mesh_index": ref["index"], "components": components})
    return {"bind_signs": np.asarray(bind_signs, dtype=np.float64), "summary": {
        "source_glb_sha256": SOURCE_GLB_SHA256, "source_glb_bytes": SOURCE_GLB_BYTES,
        "base_position_all_joint_weight_sets_triangle_value_bytes_unchanged": True,
        "native_palette_and_logical_parent_names_unchanged": True, "meshes": payloads,
        "legacy_source_checked_as_pinned_payload_only": True,
        "legacy_source_common_ancestor_schema_conformance_claimed": False}}


def native_local_matrices(reference, world):
    out = np.empty((NATIVE_JOINTS, 4, 4), dtype=np.float64)
    for index in range(NATIVE_JOINTS):
        parent = reference["joints"][index]["parent_index"]
        try:
            out[index] = world[index] if parent == -1 else np.linalg.solve(world[parent], world[index])
        except np.linalg.LinAlgError:
            fail("native_local_parent_inverse")
    return finite(out)


def quaternion_from_proper_matrix(matrix):
    """Independent trace/first-largest-diagonal conversion; F32 storage precedes composition."""
    trace = float(np.trace(matrix))
    if trace > 0:
        divisor = 2*math.sqrt(trace+1)
        q = np.array(((matrix[2, 1]-matrix[1, 2])/divisor,
                      (matrix[0, 2]-matrix[2, 0])/divisor,
                      (matrix[1, 0]-matrix[0, 1])/divisor, divisor/4), dtype=np.float64)
    else:
        i = int(np.argmax(np.diag(matrix)))
        j, k = (i+1) % 3, (i+2) % 3
        divisor = 2*math.sqrt(1+matrix[i, i]-matrix[j, j]-matrix[k, k])
        q = np.zeros(4, dtype=np.float64)
        q[i] = divisor/4
        q[j] = (matrix[i, j]+matrix[j, i])/divisor
        q[k] = (matrix[i, k]+matrix[k, i])/divisor
        q[3] = (matrix[k, j]-matrix[j, k])/divisor
    norm = float(np.linalg.norm(q))
    if not math.isfinite(norm) or norm <= 1e-12:
        fail("classifier_rotation_quaternion")
    return (q/norm).astype(np.float32)


def fit_scalar_chebyshev(column, target, witness, expected_sign):
    if (not math.isfinite(witness) or abs(witness) <= 1e-8
            or math.copysign(1, witness) != expected_sign):
        fail("classifier_scale_witness_sign")
    coefficients = column.astype(np.float64)*expected_sign
    def feasible(error):
        low, high = 1e-8, float("inf")
        for c, value in zip(coefficients, target):
            if c == 0:
                if abs(float(value)) > error:
                    return None
            else:
                left, right = (value-error)/c, (value+error)/c
                low, high = max(low, min(left, right)), min(high, max(left, right))
        return (low, high) if low <= high and math.isfinite(low) and math.isfinite(high) else None
    low = 0.0
    high = float(np.max(np.abs(column*witness-target)))
    best = feasible(high)
    if best is None:
        fail("classifier_scale_initial_interval")
    for _ in range(64):
        trial = (low+high)*0.5
        interval = feasible(trial)
        if interval is None:
            low = trial
        else:
            high, best = trial, interval
    result = np.float32(expected_sign*(best[0]+(best[1]-best[0])*0.5))
    if not math.isfinite(float(result)) or abs(float(result)) <= 1e-8 or np.sign(result) != expected_sign:
        fail("classifier_stored_scale")
    return result


def classify_key_only(reference, arrays, bind_signs, graph):
    """Recompute the declared proper-polar/F32/Cheb64 predicate from291 native keys only."""
    maxima = np.zeros(NATIVE_JOINTS, dtype=np.float64)
    for world in arrays["joint_world"]:
        locals_ = native_local_matrices(reference, world)
        for index, local in enumerate(locals_):
            a, signs = local[:3, :3], bind_signs[index]
            determinant = float(np.linalg.det(a))
            if (not math.isfinite(determinant) or abs(determinant) <= 1e-12
                    or math.copysign(1, determinant) != float(np.prod(signs))):
                fail("classifier_native_determinant_sign")
            u, singular, vt = np.linalg.svd(a*signs[np.newaxis, :])
            if np.min(singular) <= 1e-8 or np.max(singular)/np.min(singular) > CONDITION_CAP:
                fail("classifier_ordinary_degenerate")
            proper = finite(u @ vt)
            if (np.max(np.abs(proper.T @ proper-np.eye(3))) > 1e-10
                    or abs(float(np.linalg.det(proper))-1) > 1e-10):
                fail("classifier_polar_not_proper")
            q = quaternion_from_proper_matrix(proper)
            rotation = rotation_matrix(q)
            scale = np.empty(3, dtype=np.float32)
            for column in range(3):
                witness = float(np.dot(rotation[:, column], a[:, column]))
                scale[column] = fit_scalar_chebyshev(rotation[:, column], a[:, column], witness, signs[column])
            prediction = trs(local[:3, 3].astype(np.float32), q, scale)
            maxima[index] = max(maxima[index], float(np.max(np.abs(prediction-local))))
    expected = {i for i, value in enumerate(maxima) if value > LOCAL_TRS_TOL}
    if expected != graph["factored"]:
        fail("key_only_classifier_helper_set_mismatch")
    return {"algorithm": "proper_polar_f32_quaternion_signed_chebyshev64",
            "native_keys_checked": TARGET_COUNT, "native_joint_count": NATIVE_JOINTS,
            "local_tolerance": LOCAL_TRS_TOL, "uses_holdout_rows": False,
            "recomputed_independently": True, "exact_helper_set_match": True,
            "factored_native_palette_indices": sorted(expected),
            "maximum_ordinary_local_error": float(np.max(maxima)),
            "ordinary_joint_maximum_local_error": max((float(maxima[i]) for i in range(NATIVE_JOINTS)
                                                       if i not in expected), default=0.0)}


def serialized_local_at(glb, animation, node, time):
    kind, values = glb.base[node]
    if kind != "trs":
        fail("factor_animated_node_not_trs")
    tracks = animation[node]
    return trs(*(sample(tracks[name], time) for name in ("translation", "rotation", "scale")))


def check_local_products(glb, animation, time, graph, native_locals):
    maximum, worst = 0.0, None
    for index, native in enumerate(native_locals):
        product = np.eye(4, dtype=np.float64)
        for node in graph["paths"][index]:
            product = product @ serialized_local_at(glb, animation, node, time)
        difference = finite(np.abs(product-native))
        error = float(np.max(difference))
        if worst is None or error > maximum:
            maximum = error
            component = [int(v) for v in np.unravel_index(int(np.argmax(difference)), difference.shape)]
            worst = {"palette_index": index, "name": glb.nodes[index]["name"],
                     "matrix_component_row_column": component, "factor_node_count": len(graph["paths"][index]),
                     "native_local_matrix": native.tolist(), "glb_chain_product": product.tolist()}
    return maximum, worst


def real_joint_motion(animations, reference, joint_nodes, meshes, glb):
    """Only actual native palette world/logical-local motion counts, never helper channels."""
    useful = {int(i) for mesh in meshes for i in mesh["joints"][mesh["weights"] > 0]
              if reference["joints"][int(i)]["kind"] == "native"}
    for index in list(useful):
        parent = reference["joints"][index]["parent_index"]
        while parent != -1:
            useful.add(parent)
            parent = reference["joints"][parent]["parent_index"]
    useful = sorted(i for i in useful if reference["joints"][i]["parent_index"] != -1)
    counts = {}
    for clip in CLIPS:
        first_world, first_local = None, None
        world_motion, local_motion = np.zeros(NATIVE_JOINTS), np.zeros(NATIVE_JOINTS)
        for k in range(KEY_COUNT):
            worlds, _ = glb.worlds(animations[clip], k/SAMPLE_RATE)
            actual = np.stack([worlds[n] for n in joint_nodes])
            local = native_local_matrices(reference, actual)
            if first_world is None:
                first_world, first_local = actual[:NATIVE_JOINTS], local
            else:
                world_motion = np.maximum(world_motion, np.max(np.abs(actual[:NATIVE_JOINTS]-first_world), axis=(1, 2)))
                local_motion = np.maximum(local_motion, np.max(np.abs(local-first_local), axis=(1, 2)))
        moving = [i for i in useful if world_motion[i] > 1e-7 and local_motion[i] > 1e-7]
        counts[clip] = {"moving_useful_nonroot_joints": len(moving), "passed": bool(moving),
                        "examples": [reference["joints"][i]["node_name"] for i in moving[:12]],
                        "measurement": "native_palette_world_and_nearest_native_parent_local",
                        "helper_channels_alone_cannot_pass": True}
    return counts


def validate(path, reference_json_path, reference_npz_path, source_glb_path):
    """Return a JSON-only report. Numeric fidelity failures return passed=False."""
    glb = Glb(path)
    reference, arrays = load_reference(reference_json_path, reference_npz_path)
    capture = validate_capture_registry(reference)
    identity = validate_identity_reference(reference, arrays)
    meshes, joint_nodes = read_meshes(glb, reference)
    validate_identity_bindings(meshes, identity)
    for mesh in meshes:
        mesh["joint_nodes"] = joint_nodes
    animations = glb.animations(meshes)
    graph = validate_common_factor_graph(glb, reference, joint_nodes, meshes, animations)
    genuine = validate_genuine_source(glb, reference, source_glb_path)
    classifier = classify_key_only(reference, arrays, genuine["bind_signs"], graph)
    validate_identity_node(glb, reference, joint_nodes, identity, animations)
    motion = real_joint_motion(animations, reference, joint_nodes, meshes, glb)
    local_max, chains_passed, worst_local = 0.0, True, None
    authored_rows, fractional_rows = [], []
    stats = {mesh["name"]: {phase: {"maximum_world_error": 0.0, "squared_error_sum": 0.0,
                                   "vertex_samples": 0, "maximum_skin_condition": 0.0,
                                   "skin_condition_passed": True}
                                  for phase in ("authored", "fractional")} for mesh in meshes}
    overall = {"authored": True, "fractional": True}
    joint_max = {"authored": 0.0, "fractional": 0.0}
    clip_first, clip_motion = {}, {c: {m["name"]: 0.0 for m in meshes} for c in CLIPS}
    for phase, records, joint_key, pos_key, tolerance, joint_tolerance, output in (
        ("authored", reference["frames"], "joint_world", "position_key", AUTHORED_TOL, JOINT_TOL, authored_rows),
        ("fractional", reference["fractional_frames"], "fractional_joint_world",
         "fractional_position_key", FRACTIONAL_TOL, FRACTIONAL_JOINT_TOL, fractional_rows)):
        for record in records:
            row, clip, time = record["row"], record["clip"], float(record["time"])
            worlds, morph = glb.worlds(animations[clip], time)
            if identity["index"] is not None and not np.array_equal(
                    worlds[joint_nodes[identity["index"]]], np.eye(4)):
                fail("identity_world_not_identity_at_sample")
            actual_joint = np.stack([worlds[node] for node in joint_nodes])
            joint_difference = np.abs(actual_joint-arrays[joint_key][row])
            joint_error = float(np.max(joint_difference))
            worst_joint, worst_r, worst_c = (int(x) for x in np.unravel_index(
                int(np.argmax(joint_difference)), joint_difference.shape))
            worst_detail = {"palette_index": worst_joint,
                            "name": glb.nodes[joint_nodes[worst_joint]]["name"],
                            "matrix_component_row_column": [worst_r, worst_c],
                            "native_matrix": arrays[joint_key][row, worst_joint].tolist(),
                            "glb_matrix": actual_joint[worst_joint].tolist()}
            joint_max[phase] = max(joint_max[phase], joint_error)
            passed = joint_error <= joint_tolerance
            local_error, local_detail = None, None
            if phase == "authored":
                local_error, local_detail = check_local_products(
                    glb, animations[clip], time, graph, native_local_matrices(reference, arrays[joint_key][row]))
                if worst_local is None or local_error > local_max:
                    local_max = local_error
                    worst_local = {"clip": clip, "frame": record["frame"], **local_detail}
                chains_passed = chains_passed and local_error <= LOCAL_TRS_TOL
                passed = passed and local_error <= LOCAL_TRS_TOL
            errors = []
            for mesh in meshes:
                predicted, condition = pose_mesh(mesh, worlds, morph)
                target = arrays[mesh["reference"][pos_key]][row]
                distances = finite(np.linalg.norm(predicted-target, axis=1))
                maximum, rms = float(np.max(distances)), float(np.sqrt(np.mean(distances*distances)))
                worst = int(np.argmax(distances))
                local_passed = maximum <= tolerance and condition["condition_passed"]
                passed = passed and local_passed
                errors.append({"mesh": mesh["name"], "maximum_world_error": maximum,
                               "rms_world_error": rms, "passed": local_passed,
                               "worst_vertex": worst,
                               "worst_source_point_id": mesh["reference"]["source_point_ids"][worst],
                               **condition})
                s = stats[mesh["name"]][phase]
                s["maximum_world_error"] = max(s["maximum_world_error"], maximum)
                s["squared_error_sum"] += float(np.sum(distances*distances))
                s["vertex_samples"] += len(distances)
                s["maximum_skin_condition"] = max(s["maximum_skin_condition"],
                                                   condition["maximum_finite_condition"] or 0.0)
                s["skin_condition_passed"] = s["skin_condition_passed"] and condition["condition_passed"]
                if phase == "authored":
                    key = (clip, mesh["name"])
                    if key not in clip_first:
                        clip_first[key] = predicted.copy()
                    else:
                        clip_motion[clip][mesh["name"]] = max(
                            clip_motion[clip][mesh["name"]],
                            float(np.max(np.linalg.norm(predicted-clip_first[key], axis=1))))
            output.append({"clip": clip, "frame": record["frame"], "time": time,
                           "joint_matrix_max_abs_error": joint_error,
                           "joint_matrix_passed": joint_error <= joint_tolerance,
                           "worst_joint": worst_detail if phase == "fractional" else None,
                           "native_local_chain_max_abs_error": local_error,
                           "native_local_chain_passed": local_error <= LOCAL_TRS_TOL if local_error is not None else None,
                           "meshes": errors, "passed": bool(passed)})
            overall[phase] = overall[phase] and bool(passed)
    bind_world, _ = glb.worlds(animations["idle"], 0.0)
    bind_error = max(float(np.max(np.abs(
        np.matmul(np.stack([bind_world[node] for node in joint_nodes]), mesh["ibm"])-np.eye(4))))
                     for mesh in meshes)
    bind_passed = bind_error <= JOINT_TOL
    actual_motion_passed = all(value > 1e-5 for values in clip_motion.values() for value in values.values())
    mesh_summary = []
    for mesh in meshes:
        phases = {}
        for phase in ("authored", "fractional"):
            value = stats[mesh["name"]][phase]
            phases[phase] = {"maximum_world_error": value["maximum_world_error"],
                             "rms_world_error": math.sqrt(value["squared_error_sum"]/value["vertex_samples"]),
                             "maximum_skin_condition": value["maximum_skin_condition"],
                             "skin_condition_passed": value["skin_condition_passed"]}
        mesh_summary.append({"mesh": mesh["name"], "vertices": len(mesh["position"]),
                             "joint_weight_sets": mesh["sets"],
                             "maximum_actual_nonzero_influences": mesh["max_influences"],
                             "float32_weight_sum_max_error": mesh["weight_sum_max_error"],
                             "corrective_position_targets": mesh["target_count"], **phases})
    influence_limit_satisfied = all(m["sets"] == 1 and m["max_influences"] <= 4 for m in meshes)
    joint_motion_passed = all(value["passed"] for value in motion.values())
    passed = bool(overall["authored"] and overall["fractional"] and bind_passed
                  and actual_motion_passed and joint_motion_passed and chains_passed)
    summary = {"passed": passed, "glb_sha256": hashlib.sha256(glb.raw).hexdigest(),
               "glb_bytes": len(glb.raw), "authored_frames_checked": len(authored_rows),
               "fractional_frames_checked": len(fractional_rows),
               "authored_passed": bool(overall["authored"]),
               "fractional_passed": bool(overall["fractional"]),
               "authored_tolerance_world_m": AUTHORED_TOL,
               "fractional_tolerance_world_m": FRACTIONAL_TOL,
               "joint_matrix_tolerance": JOINT_TOL,
               "fractional_joint_matrix_tolerance": FRACTIONAL_JOINT_TOL,
               "joint_matrix_max_abs_error": joint_max, "bind_idle0_max_abs_error": bind_error,
               "bind_idle0_passed": bind_passed, "skin_condition_cap": CONDITION_CAP,
               "real_joint_motion": motion, "real_joint_motion_passed": joint_motion_passed,
               "zero_binding_identity": identity["summary"],
               "factor_graph": graph["summary"], "genuine_payload": genuine["summary"],
               "key_only_classifier": classifier,
               "native_local_chain_tolerance": LOCAL_TRS_TOL,
               "native_local_chain_max_abs_error": local_max,
               "native_local_chain_passed": bool(chains_passed),
               "worst_native_local_chain": worst_local,
               "sampling_contract": "native48hz_keys291_holdouts24_v1",
               "source_fps": SOURCE_FPS, "export_sample_rate": SAMPLE_RATE,
               "native_capture_provenance": capture,
               "actual_mesh_clip_motion_m": clip_motion,
               "actual_mesh_clip_motion_passed": actual_motion_passed,
               "meshes": mesh_summary,
               "current_four_influence_limit_satisfied": influence_limit_satisfied,
               "current_adapter_ready": False,
               "extra_joint_sets_present": any(m["sets"] > 1 for m in meshes),
               "production_glb_approved": False, "browser_fidelity_approved": False,
               "normal_material_final_modifier_fidelity_approved": False}
    report = {"reader": "independent_serialized_glb_factor48_correctives_v1",
              "coordinate_system": reference["coordinate_system"], "stage": reference["stage"],
              "computation": "float64 CPU from serialized float32 GLB data; morph before all-set skin; no weight renormalization",
              "summary": summary, "authored_frames": authored_rows, "fractional_frames": fractional_rows,
              "limits": ["Two ARMATURE_ONLY identity-world meshes, three fixed 48 Hz LINEAR clips, 291 POSITION targets.",
                         "Native reference provenance is supplied by the caller; no bpy or writer arrays are imported.",
                         "CPU float64 readback does not certify GPU float32 execution, mobile memory, normals or materials.",
                         "More than four influences are read and evaluated, but the active game adapter remains incompatible.",
                         "Only the 24 fresh quarter-frame samples are validation; the 12 former half-frame holdouts are keys.",
                         "Six export-only transform helpers per factored native joint are not bones or skin influences.",
                          "The pinned legacy source supplies immutable genuine payload only; its common-root conformance is not claimed.",
                          "No continuous-time, arbitrary-motion or crossfade guarantee.",
                         "No activation, art, final modifier, appearance-preset or browser acceptance."]}
    if len(json_bytes(summary)) > MAX_SUMMARY or len(json_bytes(report)) > MAX_REPORT:
        fail("report_budget")
    return report
