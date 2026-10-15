"""Independent, bounded reader for the native-epsilon rotation-only CUBICSPLINE GLB pilot.

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
SOURCE_CONTRACT = CONTRACT
ROTATION_CONTRACT = "native_eps1024_rotation_cubic_v1"
SOURCE_GLB_BYTES = 30598112
SOURCE_GLB_SHA256 = "7308349db07a0542b54b3ec29949f2610562a2b3501ceaa51633ad0930571c06"
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
PLAN_BYTES = 125813
PLAN_SHA256 = "b96456634d1f79b130c1cc17a0e5dc31ab15f4a7e00d5cfe0a6943bb4c0033af"
PLAN_CONTRACT = "snow_native_rotation_derivative_eps1024_split_v1"
CAPTURE_BLOB = "42dd79d6e6f9c7d3c4590011f8e7793f454ef60d"
PACKET_FILES = (
    {"npz": (3582712, "1a8f65768e5e888da102e2dd121a45d28a89687732a0db1966e230e1bdd5ef56"),
     "json": (128234, "898cce9b009af6388bfc719aa3eea673d33e47319963c96cea1d59c3f92b5e8d"),
     "audit": (166149, "a12d9ede526bee8e42e181c8cd57694f2231564c09d1a8ab51c1610f9b874bb6")},
    {"npz": (1226442, "7215408b76bc1fb344d908ca9c271b1d0dc22d7d55c6f4422fe8fb398947b150"),
     "json": (122328, "1c620a0baf06202155b8455d3ec1e5e39fef7ee22c359704aaa210ff6e808d6b"),
     "audit": (160280, "ab92e7c057e941d550c851cc925d75154804a940e9e65b0c567871276c1452e2")},
)
FRESH_FRAMES = (0.125, 0.375, 12.125, 12.375, 24.125, 24.375, 36.125, 36.375)
EPSILON_FRAMES, DIFFERENCE_SECONDS = 1/1024, 1/24576

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
        cubic = self.doc["asset"].get("extras", {}).get("coop_native_rotation_derivative_contract")
        if cubic not in (None, ROTATION_CONTRACT):
            fail("rotation_derivative_contract")
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
                target = channel.get("target", {})
                node = integer(target.get("node"), 0, len(self.nodes)-1)
                if node not in self.reachable:
                    fail("animation_target_not_in_scene")
                path = target.get("path")
                if path not in ("translation", "rotation", "scale", "weights"):
                    fail("animation_target_path")
                interpolation = sampler.get("interpolation", "LINEAR")
                expected_interpolation = "CUBICSPLINE" if cubic and path == "rotation" else "LINEAR"
                if interpolation != expected_interpolation:
                    fail("rotation_only_interpolation_contract")
                if path in tracks.setdefault(node, {}):
                    fail("duplicate_animation_channel")
                inputs = self.read(sampler.get("input"), "SCALAR", (5126,), tight=True)
                self.bounds(sampler["input"], inputs)
                times = inputs[:, 0].astype(np.float64)
                if len(times) != KEY_COUNT or not np.all(np.diff(times) > 0) or not np.allclose(
                        times, np.arange(KEY_COUNT)/SAMPLE_RATE, atol=1e-7, rtol=0):
                    fail("animation_97_times")
                kind = "SCALAR" if path == "weights" else ("VEC4" if path == "rotation" else "VEC3")
                data = self.read(sampler.get("output"), kind, (5126,), tight=True).astype(np.float64)
                track = {"times": times, "rotation": path == "rotation", "interpolation": interpolation}
                if path == "weights":
                    if node not in mesh_by_node:
                        fail("weights_target_not_mesh")
                    count = mesh_by_node[node]["target_count"]
                    if data.shape != (KEY_COUNT*count, 1):
                        fail("animation_morph_output_shape")
                    data = data.reshape(KEY_COUNT, count)
                elif interpolation == "CUBICSPLINE":
                    if data.shape != (KEY_COUNT*3, 4):
                        fail("rotation_cubic_output_shape")
                    triplets = data.reshape(KEY_COUNT, 3, 4)
                    track["in_tangents"], data, track["out_tangents"] = (
                        triplets[:, 0], triplets[:, 1], triplets[:, 2])
                elif data.shape[0] != KEY_COUNT:
                    fail("animation_trs_output_shape")
                if path == "rotation":
                    for q in data:
                        quaternion(q)
                track["values"] = data
                tracks[node][path] = track
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
    left = int(np.searchsorted(times, time, side="right"))-1
    dt = float(times[left+1]-times[left])
    u = float((time-times[left])/dt)
    if track.get("interpolation") == "CUBICSPLINE":
        # glTF Hermite tangents are derivatives per SECOND, not per key/frame.
        q = finite((2*u**3-3*u**2+1)*data[left] +
                   (u**3-2*u**2+u)*dt*track["out_tangents"][left] +
                   (-2*u**3+3*u**2)*data[left+1] +
                   (u**3-u**2)*dt*track["in_tangents"][left+1])
        norm = float(np.linalg.norm(q))
        if not math.isfinite(norm) or norm <= 1e-12:
            fail("cubic_quaternion_zero_or_nonfinite")
        return q/norm
    return slerp(data[left], data[left+1], u) if track["rotation"] else (
        (1-u)*data[left]+u*data[left+1])


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
    """The current 7308 baseline is an immutable, complete factor48 source, not old147."""
    source = Glb(source_path, expected_contract=SOURCE_CONTRACT)
    if len(source.raw) != SOURCE_GLB_BYTES or hashlib.sha256(source.raw).hexdigest() != SOURCE_GLB_SHA256:
        fail("genuine_source_glb_pin")
    if source.doc["asset"].get("extras", {}).get("coop_native_rotation_derivative_contract") is not None:
        fail("source_must_be_linear_factor48")
    if glb.doc["asset"].get("extras", {}).get("coop_native_rotation_derivative_contract") != ROTATION_CONTRACT:
        fail("new_rotation_contract_missing")
    old_meshes, old_joints = read_meshes(source, reference)
    for mesh in old_meshes:
        mesh["joint_nodes"] = old_joints
    old_animations = source.animations(old_meshes)
    old_graph = validate_common_factor_graph(source, reference, old_joints, old_meshes, old_animations)
    if (old_graph["factored"] != {183} or old_graph["helpers"] != set(range(188, 194))
            or len(source.nodes) != 196):
        fail("frozen_factor183_mapping")
    # Preserve every ID and graph/default/material/skin/mesh field. Only the
    # derivative tag, rotation interpolation/count/bounds, and packed offsets change.
    a, b = json.loads(json_bytes(source.doc)), json.loads(json_bytes(glb.doc))
    if b["asset"]["extras"].pop("coop_native_rotation_derivative_contract", None) != ROTATION_CONTRACT:
        fail("rotation_contract_marker")
    if len(a["accessors"]) != len(b["accessors"]) or len(a["bufferViews"]) != len(b["bufferViews"]):
        fail("immutable_accessor_view_inventory")
    q_accessors = set()
    for old_anim, new_anim in zip(a["animations"], b["animations"]):
        if old_anim["name"] != new_anim["name"] or old_anim["channels"] != new_anim["channels"]:
            fail("immutable_animation_channel_ids")
        for channel in old_anim["channels"]:
            si = channel["sampler"]
            if channel["target"]["path"] == "rotation":
                old_sampler, new_sampler = old_anim["samplers"][si], new_anim["samplers"][si]
                if new_sampler.get("interpolation") != "CUBICSPLINE":
                    fail("all_rotations_must_be_cubic")
                new_sampler["interpolation"] = old_sampler.get("interpolation", "LINEAR")
                q_accessors.add(old_sampler["output"])
    if len(q_accessors) != 3*193:
        fail("fixed_579_rotation_accessors")
    q_views = set()
    changed_bytes = 0
    for index, (old, new) in enumerate(zip(a["accessors"], b["accessors"])):
        if (old.get("byteOffset", 0) != 0 or "sparse" in old
                or "byteStride" in a["bufferViews"][old["bufferView"]]):
            fail("frozen_exclusive_tight_layout")
        if index in q_accessors:
            if (old["type"] != "VEC4" or old["componentType"] != 5126 or old["count"] != KEY_COUNT
                    or new["count"] != KEY_COUNT*3 or new["type"] != "VEC4"
                    or new["componentType"] != 5126 or new["bufferView"] != old["bufferView"]):
                fail("immutable_rotation_accessor_identity")
            q_views.add(old["bufferView"])
            if "min" in new or "max" in new:
                glb.bounds(index, glb.read(index))
            value = glb.read(index).reshape(KEY_COUNT, 3, 4)[:, 1]
            if value.tobytes(order="C") != source.read(index).tobytes(order="C"):
                fail("stored_rotation_value_bytes_changed")
            new["count"] = old["count"]
            for key in ("min", "max"):
                old.pop(key, None)
                new.pop(key, None)
        elif glb.read(index).tobytes(order="C") != source.read(index).tobytes(order="C"):
            fail("nonrotation_accessor_value_bytes_changed")
    if (len(q_views) != len(q_accessors) or len(a["accessors"]) != len(a["bufferViews"])
            or len({v["bufferView"] for v in a["accessors"]}) != len(a["accessors"])):
        fail("frozen_one_accessor_per_view_required")
    cursor = 0
    for index, (old, new) in enumerate(zip(a["bufferViews"], b["bufferViews"])):
        aligned = cursor+(-cursor) % 4
        if any(glb.bin[cursor:aligned]):
            fail("repack_alignment_padding_not_zero")
        cursor = aligned
        actual = glb.views[index]
        if actual.get("byteOffset", 0) != cursor:
            fail("repack_offsets_not_canonical")
        start, length = actual.get("byteOffset", 0), actual["byteLength"]
        if index in q_views:
            if new["byteLength"] != old["byteLength"]*3:
                fail("rotation_view_not_tripled")
            changed_bytes += new["byteLength"]-old["byteLength"]
            new["byteLength"] = old["byteLength"]
        else:
            old_start = source.views[index].get("byteOffset", 0)
            if glb.bin[start:start+length] != source.bin[old_start:old_start+old["byteLength"]]:
                fail("nonrotation_view_bytes_changed")
        old.pop("byteOffset", None)
        new.pop("byteOffset", None)
        cursor += length
    if glb.buffer_length != cursor or any(glb.bin[glb.buffer_length:]):
        fail("repack_unowned_binary_or_padding")
    a["buffers"][0]["byteLength"] = b["buffers"][0]["byteLength"] = 0
    if a != b:
        fail("immutable_document_fields_changed")
    signs = []
    for node in range(NATIVE_JOINTS):
        kind, values = source.base[node]
        if kind != "trs" or np.any(np.abs(values[2]) <= 1e-8):
            fail("source_bind_scale_sign")
        signs.append(np.sign(values[2]))
    payload = {"source_glb_sha256": SOURCE_GLB_SHA256, "source_glb_bytes": SOURCE_GLB_BYTES,
               "all_nonrotation_views_value_bytes_unchanged": True,
               "all_291_rotation_value_bytes_unchanged": True,
               "all_input_time_bytes_and_accessor_sampler_ids_unchanged": True,
               "nodes_defaults_skins_meshes_targets_ibm_all_influence_sets_unchanged": True,
               "only_rotation_outputs_tripled": True, "rotation_accessors": len(q_accessors),
               "rotation_added_binary_bytes": changed_bytes, "source_is_current_factor48": True}
    return {"bind_signs": np.asarray(signs, dtype=np.float64), "summary": payload,
            "source": source, "meshes": old_meshes, "animations": old_animations}


def frozen_file(path, size, digest):
    path = Path(path)
    if not path.is_file() or path.stat().st_size != size:
        fail("frozen_packet_file_size")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        fail("frozen_packet_file_hash")
    return raw


def captured_json_bytes(value):
    # The native capture used this serialization for its envelope hash.
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)+"\n").encode()


def load_rotation_packets(reference, packet0_root, packet1_root, plan_path):
    plan_raw = frozen_file(plan_path, PLAN_BYTES, PLAN_SHA256)
    plan = json.loads(plan_raw.decode("utf-8"))
    if (plan.get("contract") != PLAN_CONTRACT or plan.get("contains_captured_pose_data") is not False
            or plan.get("source_fps") != SOURCE_FPS or plan.get("source_epsilon_frames") != EPSILON_FRAMES
            or plan.get("seconds_per_difference") != DIFFERENCE_SECONDS
            or plan.get("epsilon_rational_source_frames") != [1, 1024]
            or plan.get("difference_rational_seconds") != [1, 24576]
            or plan.get("reference_npz_sha256") != FROZEN_NPZ_SHA256
            or plan.get("reference_metadata_sha256") != FROZEN_JSON_SHA256
            or plan.get("source_glb_sha256") != SOURCE_GLB_SHA256
            or plan.get("clip_order") != list(CLIPS) or plan.get("side_order") != ["incoming", "outgoing"]
            or plan.get("phase_b_requires_both_complete_packets") is not True):
        fail("locked_derivative_plan")
    # Regenerate the fixed schedule rather than trusting matching record counts.
    epsilon, fresh = [], []
    for ci, clip in enumerate(CLIPS):
        for key in range(KEY_COUNT):
            for side in ("incoming", "outgoing"):
                if key == 0 and side == "incoming" or key == KEY_COUNT-1 and side == "outgoing":
                    continue
                index = len(epsilon)
                epsilon.append({"id": index, "packet": index//288, "clip": clip,
                                "key_index": key, "authored_row": ci*KEY_COUNT+key, "key_frame": key/2,
                                "side": side, "sample_frame": key/2+(-EPSILON_FRAMES if side == "incoming" else EPSILON_FRAMES)})
        for frame in FRESH_FRAMES:
            fresh.append({"id": len(fresh), "packet": 0, "clip": clip, "sample_frame": frame,
                          "role": "fresh_geometry_and_joint_validation"})
    if (plan.get("epsilon_joint_only_samples") != epsilon or plan.get("fresh_validation_samples") != fresh
            or len(epsilon) != 576 or len(fresh) != 24):
        fail("derivative_plan_registry")
    frozen_tuples = {(r["clip"], float(r["frame"])) for r in reference["frames"]+reference["fractional_frames"]}
    samples = {(r["clip"], r["sample_frame"]) for r in epsilon+fresh}
    if len(samples) != 600 or samples & frozen_tuples:
        fail("new_sample_union_overlap_or_missing")
    packets, registries, envelopes = [], [], []
    for number, root in enumerate((packet0_root, packet1_root)):
        root, pins = Path(root), PACKET_FILES[number]
        files = {kind: frozen_file(root/("capture-audit.json" if kind == "audit" else
                 "native-rotation-packet-"+str(number)+"."+kind), *pin) for kind, pin in pins.items()}
        meta, audit = json.loads(files["json"]), json.loads(files["audit"])
        count = 24 if number == 0 else 0
        if (meta.get("schema_version") != 1 or meta.get("packet_id") != number
                or meta.get("contract") != PLAN_CONTRACT or meta.get("sampling_plan_sha256") != PLAN_SHA256
                or meta.get("capture_complete") is not True or meta.get("readonly_cleanup_passed") is not True
                or meta.get("epsilon_matrices_are_not_geometry_proof") is not True
                or meta.get("production_glb_approved") is not False or meta.get("joints") != reference["joints"]):
            fail("frozen_packet_contract")
        for flag in ("capture_complete", "readonly_cleanup_passed", "data_capture_and_saved_readback_passed",
                     "original_binding_restored", "input_id_inventory_preserved", "input_preservation_passed"):
            if audit.get(flag) is not True:
                fail("frozen_packet_native_cleanup")
        if audit.get("failure") is not None or audit.get("packet_id") != number:
            fail("frozen_packet_native_failure")
        policy = audit.get("native_policy_before", {})
        if (policy != audit.get("native_policy_after") or policy.get("autoexec_enabled") is not False
                or policy.get("muted") != 0 or policy.get("non_native_unmuted") != 0
                or policy.get("driver_mute_writes") != 0 or policy.get("action_detach_calls") != 0
                or policy.get("embedded_text_executed") is not False
                or policy.get("driver_count") != 1291 or policy.get("native_unmuted") != 1291
                or audit.get("input_driver_before") != audit.get("input_driver_after")
                or audit.get("input_driver_after", {}).get("active_invalid") != 0):
            fail("frozen_packet_native_policy")
        if meta.get("proof_counts") != {
                "epsilon_joint_only_this_packet": 288, "epsilon_geometry_proofs": 0,
                "fresh_geometry_this_packet": count, "unique_new_this_packet": 288+count,
                "sentinel_unique": 0, "geometry_inherited": 315,
                "geometry_verified_from_baseline_plus_this_packet": 315+count}:
            fail("frozen_packet_proof_counts")
        guards = meta.get("native_sample_guards", {})
        if (guards.get("native_invalid_count") != 0 or guards.get("zero_binding_count") != 792
                or guards.get("full_raw_clone_eval_memberships_for_geometry") is not True
                or guards.get("source_point_ids_and_palette_exact") is not True
                or native_error(guards.get("maximum_zero_pre_armature_world_error_m")) > 1e-6
                or type(guards.get("maximum_held_face_property_drift")) not in (int, float)
                or not math.isfinite(guards["maximum_held_face_property_drift"])
                or not 0 <= guards["maximum_held_face_property_drift"] <= 1e-4):
            fail("frozen_packet_sample_guards")
        sentinel = meta.get("overlap_sentinel", {})
        if (sentinel.get("clip") != "wave" or sentinel.get("frame") != 12.5
                or sentinel.get("passed") is not True or sentinel.get("adds_unique_pose") is not False
                or native_error(sentinel.get("maximum_joint_matrix_abs_error")) > 1e-6
                or native_error(sentinel.get("maximum_position_world_error_m")) > 1e-6
                or native_error(sentinel.get("maximum_zero_pre_armature_world_error_m")) > 1e-6):
            fail("frozen_packet_overlap_sentinel")
        envelope = meta.get("provenance_envelope", {})
        digest = hashlib.sha256(captured_json_bytes(envelope)).hexdigest()
        if (set(envelope) != set(plan["packet_envelope_must_bind"])
                or digest != meta.get("provenance_envelope_sha256")
                or envelope != audit.get("provenance_envelope")
                or digest != audit.get("provenance_envelope_sha256")
                or envelope.get("sampling_plan_sha256") != PLAN_SHA256
                or envelope.get("capture_wrapper_git_blob_sha") != CAPTURE_BLOB
                or envelope.get("source_glb_sha256") != SOURCE_GLB_SHA256
                or envelope.get("reference_npz_sha256") != FROZEN_NPZ_SHA256
                or envelope.get("reference_metadata_sha256") != FROZEN_JSON_SHA256
                or envelope.get("source_native_blend_sha256") != "b22306981a809bdb2e537c52087efe8d503bc30a0efe73573a51bb6200aeffa3"
                or envelope.get("source_native_producer_audit_sha256") != "5c271962723af2b09bf331bd85d7f6e363f5334df6256265ee3ee4c983410518"
                or envelope.get("original_snow_sha256") != "80fd0a81bca90f0efdcdcb98422df0e198ae57f4a1c239e13fb795922779b1fc"
                or envelope.get("bpy_version_and_wheel_sha256") != {
                    "version": [4, 5, 9], "official_wheel_sha256":
                    "0bca32fe0658388f5ef669631220d7147fc2544bb0103a0042603519552b6b6a"}):
            fail("frozen_packet_envelope")
        envelopes.append(envelope)
        expected = []
        eps_records = epsilon[number*288:(number+1)*288]
        fresh_records = fresh if number == 0 else []
        for kind, records in (("epsilon_joint_only", eps_records), ("fresh_geometry", fresh_records)):
            for local, record in enumerate(records):
                expected.append({"kind": kind, "local_row": local, **record,
                                 "native_driver_invalid": 0, "held_face_passed": True,
                                 "finite_key_values_passed": True, "geometry_proved": kind == "fresh_geometry",
                                 "maximum_zero_world_error_m": None if kind == "epsilon_joint_only" else 0.0})
        actual = meta.get("pose_registry", [])
        if len(actual) != len(expected) or actual != audit.get("pose_registry"):
            fail("frozen_packet_pose_registry")
        for got, want in zip(actual, expected):
            if want["kind"] == "fresh_geometry":
                error = native_error(got.get("maximum_zero_world_error_m"))
                if error > 1e-6:
                    fail("fresh_zero_membership_proof")
                want["maximum_zero_world_error_m"] = error
            if got != want:
                fail("frozen_packet_pose_identity_or_guards")
        shapes = {"epsilon_joint_world": (288, PALETTE_SIZE, 4, 4),
                  "fresh_joint_world": (count, PALETTE_SIZE, 4, 4),
                  "fresh_mesh0_positions": (count, reference["meshes"][0]["vertex_count"], 3),
                  "fresh_mesh1_positions": (count, reference["meshes"][1]["vertex_count"], 3)}
        npz_path = root/("native-rotation-packet-"+str(number)+".npz")
        payload = meta.get("packet_payload", {})
        if (payload.get("file") != npz_path.name or payload.get("bytes") != pins["npz"][0]
                or payload.get("sha256") != pins["npz"][1]
                or payload.get("reopened_all_arrays_byte_values_equal") is not True
                or payload.get("sha256_recheck") is not True):
            fail("frozen_packet_payload_identity")
        descriptors = {k: {"shape": list(shape), "dtype": "float64", "finite": True}
                       for k, shape in shapes.items()}
        if payload.get("arrays") != descriptors:
            fail("frozen_packet_array_descriptors")
        with zipfile.ZipFile(npz_path) as archive:
            infos = archive.infolist()
            if (len(infos) != 4 or {r.filename for r in infos} != {k+".npy" for k in shapes}
                    or len({r.filename for r in infos}) != 4
                    or sum(r.file_size for r in infos) > 16*1024*1024
                    or any(r.flag_bits & 1 or r.compress_type not in (0, 8)
                           or r.file_size > 8*1024*1024 for r in infos)):
                fail("frozen_packet_npz_budget")
            if archive.testzip() is not None:
                fail("frozen_packet_npz_crc")
        data = {}
        with np.load(npz_path, allow_pickle=False) as archive:
            if set(archive.files) != set(shapes):
                fail("frozen_packet_npz_keys")
            for key, shape in shapes.items():
                values = archive[key]
                if values.dtype != np.dtype("float64") or values.shape != shape:
                    fail("frozen_packet_npz_dtype_shape")
                data[key] = finite(values)
        for key in ("epsilon_joint_world", "fresh_joint_world"):
            values = data[key]
            if (not np.allclose(values[:, :, 3], (0, 0, 0, 1), atol=1e-7, rtol=0)
                    or not np.array_equal(values[:, 186], np.broadcast_to(np.eye(4), (len(values), 4, 4)))):
                fail("frozen_packet_affine_or_auxiliary")
        packets.append(data)
        registries.append(actual)
    if envelopes[0] != envelopes[1]:
        fail("packets_do_not_share_provenance")
    eps_array = finite(np.concatenate([p["epsilon_joint_world"] for p in packets], axis=0))
    if eps_array.shape != (576, PALETTE_SIZE, 4, 4):
        fail("complete_epsilon_union_shape")
    return {"plan": plan, "epsilon": eps_array, "epsilon_records": epsilon,
            "fresh": packets[0], "fresh_records": fresh,
            "summary": {"sampling_plan_sha256": PLAN_SHA256,
                        "provenance_envelope_sha256": hashlib.sha256(captured_json_bytes(envelopes[0])).hexdigest(),
                        "packet_npz_sha256": [r["npz"][1] for r in PACKET_FILES],
                        "packet_json_sha256": [r["json"][1] for r in PACKET_FILES],
                        "both_complete_and_same_envelope": True, "epsilon_joint_only_count": 576,
                        "fresh_geometry_count": 24, "new_unique_count": 600,
                        "disjoint_from_frozen315": True, "sentinel_adds_unique": False,
                        "native_policy_cleanup_and_membership_provenance_checked": True,
                        "raw_captured_matrices_not_writer_derivatives": True}}


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
    coefficients = finite(column.astype(np.float64)*expected_sign)
    target = finite(np.asarray(target, dtype=np.float64))
    magnitude = abs(witness)
    residual = finite(coefficients*magnitude-target)
    def feasible(error):
        low, high = 1e-8-magnitude, float("inf")
        for c, value in zip(coefficients, residual):
            if c == 0:
                if abs(float(value)) > error:
                    return None
            else:
                left, right = (-error-value)/c, (error-value)/c
                low, high = max(low, min(left, right)), min(high, max(left, right))
        return (low, high) if low <= high and math.isfinite(low) and math.isfinite(high) else None
    low = 0.0
    high = float(np.max(np.abs(residual)))
    best = feasible(high)
    if best is None or not best[0] <= 0 <= best[1]:
        fail("classifier_centered_scale_initial_interval")
    for _ in range(64):
        trial = (low+high)*0.5
        interval = feasible(trial)
        if interval is None:
            low = trial
        else:
            high, best = trial, interval
    offset = best[0]+(best[1]-best[0])*0.5
    result = np.float32(expected_sign*(magnitude+offset))
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
    return {"algorithm": "proper_polar_f32_quaternion_signed_witness_centered_chebyshev64",
            "native_keys_checked": TARGET_COUNT, "native_joint_count": NATIVE_JOINTS,
            "local_tolerance": LOCAL_TRS_TOL, "uses_holdout_rows": False,
            "recomputed_independently": True, "exact_helper_set_match": True,
            "factored_native_palette_indices": sorted(expected),
            "maximum_ordinary_local_error": float(np.max(maxima)),
            "ordinary_joint_maximum_local_error": max((float(maxima[i]) for i in range(NATIVE_JOINTS)
                                                       if i not in expected), default=0.0)}


def native_quaternion64(matrix):
    """Locked explicit trace/first-largest-diagonal arithmetic; one FLOAT64 normalization."""
    r = finite(np.asarray(matrix, dtype=np.float64))
    if (r.shape != (3, 3) or np.max(np.abs(r.T@r-np.eye(3))) > 1e-10
            or abs(float(np.linalg.det(r))-1) > 1e-10):
        fail("native_rotation_field_not_proper")
    trace = float(np.trace(r))
    if trace > 0:
        divisor = 2*math.sqrt(trace+1)
        q = np.array(((r[2, 1]-r[1, 2])/divisor, (r[0, 2]-r[2, 0])/divisor,
                      (r[1, 0]-r[0, 1])/divisor, divisor/4), dtype=np.float64)
    else:
        diagonal = int(np.argmax(np.diag(r)))
        if diagonal == 0:
            divisor = 2*math.sqrt(1+r[0, 0]-r[1, 1]-r[2, 2])
            q = np.array((divisor/4, (r[0, 1]+r[1, 0])/divisor,
                          (r[0, 2]+r[2, 0])/divisor, (r[2, 1]-r[1, 2])/divisor), dtype=np.float64)
        elif diagonal == 1:
            divisor = 2*math.sqrt(1+r[1, 1]-r[0, 0]-r[2, 2])
            q = np.array(((r[0, 1]+r[1, 0])/divisor, divisor/4,
                          (r[1, 2]+r[2, 1])/divisor, (r[0, 2]-r[2, 0])/divisor), dtype=np.float64)
        else:
            divisor = 2*math.sqrt(1+r[2, 2]-r[0, 0]-r[1, 1])
            q = np.array(((r[0, 2]+r[2, 0])/divisor, (r[1, 2]+r[2, 1])/divisor,
                          divisor/4, (r[1, 0]-r[0, 1])/divisor), dtype=np.float64)
    norm = float(np.linalg.norm(finite(q)))
    if not math.isfinite(norm) or norm <= 1e-12:
        fail("native_rotation_field_zero")
    return finite(q/norm)


def native_rotation_field(reference, world, bind_signs, factor_bind_sign):
    """No stored F32 values enter the KEY or EPS field construction."""
    local = native_local_matrices(reference, world)
    result = {}
    for index, matrix in enumerate(local):
        a = finite(matrix[:3, :3])
        signs = bind_signs[index]
        determinant = float(np.linalg.det(a))
        if (not math.isfinite(determinant) or abs(determinant) <= 1e-12
                or math.copysign(1, determinant) != (factor_bind_sign if index == 183 else float(np.prod(signs)))):
            fail("native_rotation_field_reflection_sign")
        if index != 183:
            u, singular, vt = np.linalg.svd(a*signs[np.newaxis, :])
            if np.min(singular) <= 1e-8 or np.max(singular)/np.min(singular) > CONDITION_CAP:
                fail("native_rotation_field_singular")
            result[index] = native_quaternion64(u@vt)
            continue
        # Fixed six-helper affine chain: q nodes188..193 then native tail183.
        first = float(np.linalg.norm(a[:, 0]))
        if first <= 1e-8:
            fail("native_rotation_field_qr_first")
        axis0 = a[:, 0]/first
        v = a[:, 1]-np.dot(axis0, a[:, 1])*axis0
        second = float(np.linalg.norm(v))
        if second <= 1e-8:
            fail("native_rotation_field_qr_second")
        axis1 = v/second
        q = finite(np.column_stack((axis0, axis1, np.cross(axis0, axis1))))
        upper = finite(q.T@a)
        diagonal = np.diag(upper).copy()
        if (np.max(np.abs(np.tril(upper, -1))) > 1e-10
                or np.max(np.abs(q@upper-a)) > 1e-10
                or np.any(np.abs(diagonal) <= 1e-8)
                or not np.array_equal(np.sign(diagonal), [1, 1, factor_bind_sign])):
            fail("native_rotation_field_qr_domain")
        result[188] = native_quaternion64(q)
        x, y, z = upper[0, 1]/diagonal[0], upper[0, 2]/diagonal[0], upper[1, 2]/diagonal[1]
        nodes = iter((189, 190, 191, 192, 193, 183))
        for axis_a, axis_b, shear in ((0, 1, x), (0, 2, y-x*z), (1, 2, z)):
            if not math.isfinite(float(shear)):
                fail("native_rotation_field_shear_nonfinite")
            plus, minus = math.exp(math.asinh(shear/2)), math.exp(-math.asinh(shear/2))
            if (not math.isfinite(plus) or not math.isfinite(minus) or plus <= 1e-8 or minus <= 1e-8):
                fail("native_rotation_field_shear_scale")
            for angle in (math.pi/4-.5*math.atan(shear/2), -math.pi/4-.5*math.atan(shear/2)):
                r = np.eye(3)
                c, s = math.cos(angle), math.sin(angle)
                r[axis_a, axis_a] = r[axis_b, axis_b] = c
                r[axis_a, axis_b], r[axis_b, axis_a] = -s, s
                result[next(nodes)] = native_quaternion64(r)
    result[186] = np.array((0, 0, 0, 1), dtype=np.float64)
    expected_nodes = set(range(PALETTE_SIZE)) | set(range(188, 194))
    if set(result) != expected_nodes:
        fail("native_rotation_field_mapping")
    return result


def align_native_quaternion(value, anchor):
    dot = float(np.dot(value, anchor))
    if not math.isfinite(dot) or dot == 0:
        fail("native_rotation_field_hemisphere_ambiguous")
    return -value if dot < 0 else value


def verify_native_tangents(reference, arrays, packets, genuine, animations):
    source_animations, signs = genuine["animations"], genuine["bind_signs"]
    bind_local = native_local_matrices(reference, arrays["joint_world"][0])[183]
    bind_determinant = float(np.linalg.det(bind_local[:3, :3]))
    if not math.isfinite(bind_determinant) or abs(bind_determinant) <= 1e-12:
        fail("native_factor_bind_determinant")
    factor_bind_sign = math.copysign(1, bind_determinant)
    nodes = set(range(PALETTE_SIZE)) | set(range(188, 194))
    if len(nodes) != 193:
        fail("fixed_rotation_track_count")
    # KEY64 is derived independently, then sign-aligned. Stored key bytes are
    # only anchors/proof, never subtracted from EPS64.
    keys = []
    for row, record in enumerate(reference["frames"]):
        field = native_rotation_field(reference, arrays["joint_world"][row], signs, factor_bind_sign)
        for node in nodes:
            anchor = source_animations[record["clip"]][node]["rotation"]["values"][row % KEY_COUNT]
            q = align_native_quaternion(field[node], quaternion(anchor))
            if not np.array_equal(q.astype(np.float32), anchor.astype(np.float32)):
                fail("native_key64_does_not_round_to_stored_key")
            field[node] = q
        keys.append(field)
    incoming = {clip: {node: np.zeros((KEY_COUNT, 4), dtype=np.float32) for node in nodes} for clip in CLIPS}
    outgoing = {clip: {node: np.zeros((KEY_COUNT, 4), dtype=np.float32) for node in nodes} for clip in CLIPS}
    for record, world in zip(packets["epsilon_records"], packets["epsilon"]):
        field = native_rotation_field(reference, world, signs, factor_bind_sign)
        key = keys[record["authored_row"]]
        output = incoming if record["side"] == "incoming" else outgoing
        for node in nodes:
            value = align_native_quaternion(field[node], key[node])
            stored_key = source_animations[record["clip"]][node]["rotation"]["values"][record["key_index"]]
            if float(np.dot(value, stored_key)) <= 0:
                fail("native_epsilon_stored_key_hemisphere")
            delta = key[node]-value if record["side"] == "incoming" else value-key[node]
            tangent = finite(delta*24576.0)
            stored = finite(tangent.astype(np.float32))
            output[record["clip"]][node][record["key_index"]] = stored
    for clip in CLIPS:
        actual_nodes = {node for node, tracks in animations[clip].items() if "rotation" in tracks}
        if actual_nodes != nodes:
            fail("exact_193_rotation_nodes_required")
        for node in nodes:
            track = animations[clip][node]["rotation"]
            if (track["interpolation"] != "CUBICSPLINE"
                    or not np.array_equal(track["in_tangents"].astype(np.float32), incoming[clip][node])
                    or not np.array_equal(track["out_tangents"].astype(np.float32), outgoing[clip][node])
                    or not np.array_equal(track["in_tangents"][0], np.zeros(4))
                    or not np.array_equal(track["out_tangents"][-1], np.zeros(4))):
                fail("serialized_native_tangents_not_exact_f32_derivatives")
            if node == 186 and (np.any(track["in_tangents"]) or np.any(track["out_tangents"])):
                fail("auxiliary_identity_tangents_nonzero")
    return {"passed": True, "rotation_nodes_per_clip": 193, "rotation_tracks": 579,
            "key64_fields_checked": 291, "epsilon64_fields_checked": 576,
            "source_epsilon_frames": EPSILON_FRAMES, "difference_seconds": DIFFERENCE_SECONDS,
            "algorithm": "explicit_trace_first_argmax_single_float64_normalization_native_one_sided",
            "stored_key_value_bytes_unchanged": True, "stored_key_used_for_sign_anchor_only": True,
            "f32_key_minus_f64_epsilon_used": False, "tangents_exact_f32_readback": True,
            "tangent_projection_or_parameter_fit": False, "unused_and_auxiliary_tangents_zero": True,
            "seconds_scaled_component_hermite_then_quaternion_normalize": True}


def baseline_regression(genuine, reference, arrays):
    source, animations, meshes = genuine["source"], genuine["animations"], genuine["meshes"]
    expected = {("wave", 12.25), ("wave", 12.75), ("celebrate", 12.25),
                ("celebrate", 12.75), ("celebrate", 36.25), ("celebrate", 36.75)}
    failed, mesh_passed, maximum = set(), True, 0.0
    for record in reference["fractional_frames"]:
        row, clip, time = record["row"], record["clip"], float(record["time"])
        world, morph = source.worlds(animations[clip], time)
        actual = np.stack(world[:PALETTE_SIZE])
        error = float(np.max(np.abs(actual-arrays["fractional_joint_world"][row])))
        maximum = max(maximum, error)
        if error > FRACTIONAL_JOINT_TOL:
            failed.add((clip, float(record["frame"])))
        for mesh in meshes:
            positions, condition = pose_mesh(mesh, world, morph)
            target = arrays[mesh["reference"]["fractional_position_key"]][row]
            mesh_passed = bool(mesh_passed and condition["condition_passed"] and
                               np.max(np.linalg.norm(positions-target, axis=1)) <= FRACTIONAL_TOL)
    if failed != expected or not mesh_passed:
        fail("frozen_baseline_six_joint_failures_or_mesh_gate_changed")
    return {"old_quarter_frames_checked": 24, "old_quarter_mesh_passed": True,
            "old_quarter_joint_passed": False, "old_quarter_joint_failures": len(failed),
            "old_quarter_maximum_joint_matrix_abs_error": maximum,
            "failed_samples": [{"clip": c, "frame": f} for c, f in sorted(failed)],
            "known_regression_cases_not_blind_validation": True}


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


def validate(path, reference_json_path, reference_npz_path, source_glb_path,
             packet0_root, packet1_root, plan_path):
    """Return a JSON-only report. Numeric fidelity failures return passed=False."""
    glb = Glb(path)
    reference, arrays = load_reference(reference_json_path, reference_npz_path)
    packets = load_rotation_packets(reference, packet0_root, packet1_root, plan_path)
    capture = validate_capture_registry(reference)
    identity = validate_identity_reference(reference, arrays)
    meshes, joint_nodes = read_meshes(glb, reference)
    validate_identity_bindings(meshes, identity)
    for mesh in meshes:
        mesh["joint_nodes"] = joint_nodes
    animations = glb.animations(meshes)
    graph = validate_common_factor_graph(glb, reference, joint_nodes, meshes, animations)
    genuine = validate_genuine_source(glb, reference, source_glb_path)
    if graph["factored"] != {183} or graph["helpers"] != set(range(188, 194)):
        fail("current_fixed_factor183_graph_required")
    tangent_proof = verify_native_tangents(reference, arrays, packets, genuine, animations)
    regression = baseline_regression(genuine, reference, arrays)
    classifier = classify_key_only(reference, arrays, genuine["bind_signs"], graph)
    validate_identity_node(glb, reference, joint_nodes, identity, animations)
    motion = real_joint_motion(animations, reference, joint_nodes, meshes, glb)
    local_max, chains_passed, worst_local = 0.0, True, None
    authored_rows, fractional_rows, fresh_rows = [], [], []
    fresh_records = [{"row": r["id"], "clip": r["clip"], "frame": r["sample_frame"],
                      "time": r["sample_frame"]/SOURCE_FPS} for r in packets["fresh_records"]]
    arrays["fresh_joint_world"] = packets["fresh"]["fresh_joint_world"]
    for mesh in reference["meshes"]:
        key = "fresh_mesh"+str(mesh["index"])+"_positions"
        mesh["fresh_position_key"] = key
        arrays[key] = packets["fresh"][key]
    stats = {mesh["name"]: {phase: {"maximum_world_error": 0.0, "squared_error_sum": 0.0,
                                   "vertex_samples": 0, "maximum_skin_condition": 0.0,
                                   "skin_condition_passed": True}
                                  for phase in ("authored", "fractional", "fresh")} for mesh in meshes}
    overall = {"authored": True, "fractional": True, "fresh": True}
    joint_max = {"authored": 0.0, "fractional": 0.0, "fresh": 0.0}
    clip_first, clip_motion = {}, {c: {m["name"]: 0.0 for m in meshes} for c in CLIPS}
    for phase, records, joint_key, pos_key, tolerance, joint_tolerance, output in (
        ("authored", reference["frames"], "joint_world", "position_key", AUTHORED_TOL, JOINT_TOL, authored_rows),
        ("fractional", reference["fractional_frames"], "fractional_joint_world",
         "fractional_position_key", FRACTIONAL_TOL, FRACTIONAL_JOINT_TOL, fractional_rows),
        ("fresh", fresh_records, "fresh_joint_world", "fresh_position_key",
         FRACTIONAL_TOL, FRACTIONAL_JOINT_TOL, fresh_rows)):
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
                           "worst_joint": worst_detail if phase != "authored" else None,
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
        for phase in ("authored", "fractional", "fresh"):
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
    passed = bool(overall["authored"] and overall["fractional"] and overall["fresh"] and bind_passed
                  and actual_motion_passed and joint_motion_passed and chains_passed)
    summary = {"passed": passed, "glb_sha256": hashlib.sha256(glb.raw).hexdigest(),
               "glb_bytes": len(glb.raw), "authored_frames_checked": len(authored_rows),
               "fractional_frames_checked": len(fractional_rows),
               "fresh_frames_checked": len(fresh_rows), "fresh_passed": bool(overall["fresh"]),
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
               "native_rotation_derivatives": tangent_proof,
               "native_rotation_packet_provenance": packets["summary"],
               "pinned_source_known_regressions": regression,
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
    report = {"reader": "independent_serialized_native_eps_rotation_cubic_v1",
              "coordinate_system": reference["coordinate_system"], "stage": reference["stage"],
              "computation": "float64 CPU from serialized float32 GLB data; morph before all-set skin; no weight renormalization",
              "summary": summary, "authored_frames": authored_rows, "fractional_frames": fractional_rows,
              "fresh_validation_frames": fresh_rows,
              "limits": ["Two ARMATURE_ONLY meshes, 193 native-derived CUBIC rotation tracks/clip; T/S/weights remain LINEAR, 97 times/clip, 291 targets.",
                         "Frozen315 references and complete576EPS+fresh24 packets are hash-pinned; native memberships remain capture provenance, not independently recomputed from bpy.",
                         "CPU float64 readback does not certify GPU float32 execution, mobile memory, normals or materials.",
                         "More than four influences are read and evaluated, but the active game adapter remains incompatible.",
                         "The old24 quarter rows are known regression cases. Only the predeclared disjoint packet0 fresh24 rows are fresh validation.",
                         "Six export-only transform helpers per factored native joint are not bones or skin influences.",
                          "Current7308 source graph/common-root and all nonrotation bytes/key VALUE bytes are independently preserved.",
                          "No continuous-time, arbitrary-motion or crossfade guarantee.",
                         "No activation, art, final modifier, appearance-preset or browser acceptance."]}
    if len(json_bytes(summary)) > MAX_SUMMARY or len(json_bytes(report)) > MAX_REPORT:
        fail("report_budget")
    return report


def measured_frozen_input_hashes(reference_json, npz, source_glb, packet0_root, packet1_root, plan):
    tracked = [("source_glb", Path(source_glb)), ("reference_json", Path(reference_json)),
               ("reference_npz", Path(npz)), ("sampling_plan", Path(plan))]
    for index, root in enumerate((packet0_root, packet1_root)):
        root = Path(root)
        for suffix in ("npz", "json"):
            tracked.append(("packet"+str(index)+"_"+suffix,
                            root/("native-rotation-packet-"+str(index)+"."+suffix)))
        tracked.append(("packet"+str(index)+"_capture_audit", root/"capture-audit.json"))
    measured = {}
    for label, path in tracked:
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_GLB:
            fail("hash_recheck_file_budget")
        with path.open("rb") as file:
            digest = hashlib.file_digest(file, "sha256").hexdigest()
        measured[label] = {"bytes": path.stat().st_size, "sha256": digest}
    return measured


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Independent serialized rotation-cubic proof; no native capture.")
    for name in ("glb", "reference-json", "native-npz", "source-glb", "packet0-root",
                 "packet1-root", "plan", "out"):
        parser.add_argument("--"+name, required=True)
    args = parser.parse_args()
    out = Path(args.out)
    audit_path = out/"native-rotation-reader-audit.json"
    try:
        if sys.version_info[:2] != (3, 11) or np.__version__ != "1.26.4":
            fail("python_numpy_version_pin")
        out.mkdir(parents=True, exist_ok=True)
        if audit_path.exists():
            fail("reader_audit_already_exists")
        before = measured_frozen_input_hashes(
            args.reference_json, args.native_npz, args.source_glb, args.packet0_root, args.packet1_root, args.plan)
        report = validate(args.glb, args.reference_json, args.native_npz, args.source_glb,
                          args.packet0_root, args.packet1_root, args.plan)
        after, hash_error = None, None
        try:
            after = measured_frozen_input_hashes(
                args.reference_json, args.native_npz, args.source_glb, args.packet0_root, args.packet1_root, args.plan)
            candidate = Path(args.glb)
            if not 20 <= candidate.stat().st_size <= MAX_GLB:
                fail("candidate_hash_recheck_budget")
            with candidate.open("rb") as file:
                candidate_after = hashlib.file_digest(file, "sha256").hexdigest()
        except Exception as error:
            candidate_after = None
            hash_error = type(error).__name__
        unchanged = before == after and after is not None
        npz_unchanged = after is not None and before["reference_npz"] == after["reference_npz"]
        candidate_unchanged = candidate_after == report["summary"]["glb_sha256"]
        report["summary"].update({
            "reference_npz_sha256_before": before["reference_npz"]["sha256"],
            "reference_npz_sha256_after": after["reference_npz"]["sha256"] if after else None,
            "reference_npz_unchanged_during_readback": bool(npz_unchanged),
            "all_frozen_input_hashes_before": before, "all_frozen_input_hashes_after": after,
            "all_frozen_source_reference_plan_packet_files_unchanged": bool(unchanged),
            "candidate_glb_sha256_after": candidate_after,
            "candidate_glb_unchanged_during_readback": bool(candidate_unchanged),
            "hash_recheck_error_type": hash_error})
        report["summary"]["passed"] = bool(report["summary"]["passed"] and unchanged and candidate_unchanged)
        payload = json_bytes(report)+b"\n"
        small = json_bytes(report["summary"])
        if len(payload) > MAX_REPORT or len(small) > MAX_SUMMARY:
            fail("report_or_summary_budget")
        with audit_path.open("xb") as file:
            file.write(payload)
        print("SNOW_NATIVE_ROTATION_INDEPENDENT_READER "+small.decode("utf-8"), flush=True)
        return 0 if report["summary"]["passed"] else 1
    except Exception as error:
        # Never dump raw exception text, DOM/data, source lines, locals or paths.
        frames, trace = [], error.__traceback__
        while trace is not None:
            frames.append({"file": Path(trace.tb_frame.f_code.co_filename).name[:128],
                           "line": trace.tb_lineno,
                           "function": trace.tb_frame.f_code.co_name[:128]})
            frames = frames[-6:]
            trace = trace.tb_next
        failure = {"passed": False, "structural_failure": True,
                   "error_type": type(error).__name__, "frames": frames,
                   "production_glb_approved": False, "browser_fidelity_approved": False}
        if (isinstance(error, ValueError) and len(error.args) == 1
                and isinstance(error.args[0], str)
                and error.args[0].startswith("avatar_glb_reader_")
                and len(error.args[0]) <= 160
                and all(c.isascii() and (c.isalnum() or c == "_") for c in error.args[0])):
            failure["error_code"] = error.args[0]
        if not audit_path.exists():
            try:
                out.mkdir(parents=True, exist_ok=True)
                audit_path.write_bytes(json_bytes({"summary": failure})+b"\n")
            except OSError:
                pass
        print("SNOW_NATIVE_ROTATION_READER_FAILED "+json.dumps(failure, sort_keys=True), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
