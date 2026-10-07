"""S3-07 (rulings 111-4, 111-5): a scan's annotated mesh rendered at the 224 x 224 target camera -- instance image and depth.

白话：实例列的色块与两列共用的深度都从这里来。输入是一次扫描自己的标注网格（``labels.instances.annotated.v2.ply``：顶点、三角面、
逐顶点 ``objectId``）、该帧的原始相机位姿和目标相机内参；输出是 224×224 的 16 位实例图（像素值＝``objectId``，0＝没打到网格或
打到未标注处）与米制轴向深度（没打到记 0.0，在冻结的 [0.05, 20] m 之外即无效）。结果等于“从相机光心穿过每个像素中心发一条射线，
取最近的交点”：完全在相机前方的三角面用像素中心覆盖加深度缓冲做光栅化（与逐像素求交同一结果，快得多），跨过相机平面的少数面
逐面对全部像素做精确的射线–三角求交（Möller–Trumbore）；交点的标签取该三角面三个顶点里离交点最近的那个（裁决 111-4）。例如一张
面向相机、离相机 2 m 的桌面，打到它的像素深度都是 2 m、标签都是桌子的 objectId。全部是逐元素的 float64 运算，不走 BLAS，换主机
逐位相同；并列（同一像素、同一深度）取面编号小者。它不读传感器深度、不读另一次扫描、不读变化标注；它不是真值物体表（那由转换器
从 OBB 写），也不是 SAM 2.1 的色块。
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from vsmt import lean_s3_07_3rscan as r3

#: a face with every vertex at least this far in front of the camera is rasterised; any other face that reaches in front is
#: intersected ray by ray, so a face crossing the camera plane is rendered exactly as ray casting would
RASTER_NEAR_M = 1e-3
#: below this |determinant| a ray runs parallel to a face and does not hit it
RAY_PARALLEL_EPSILON = 1e-12
BACKGROUND_LABEL = 0
#: candidate pixels are generated face by face in chunks of at most this many, a memory guard, not a result rule
CANDIDATE_CHUNK = 4_000_000
LABEL_RULE = "nearest_vertex_of_the_hit_face"
COVERAGE_RULE = "pixel_centre_ray_first_hit; ties to the smaller face index"
PLY_FORMATS = ("ascii", "binary_little_endian")


class LeanS307RenderError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanS307RenderError(code)


def check_contract(contract: Mapping[str, Any]) -> None:
    """The contract's ``render`` block must state this module's rules (validated after ``lean_s3_07_3rscan.validate_contract``)."""

    render = contract["render"]
    _require(render["raster_near_m"] == RASTER_NEAR_M, "contract_render_near_mismatch")
    _require(render["label_rule"] == LABEL_RULE and render["coverage_rule"] == COVERAGE_RULE, "contract_render_rule_mismatch")
    _require(render["background_label"] == BACKGROUND_LABEL, "contract_render_background_mismatch")
    _require(render["mesh"] == "labels.instances.annotated.v2.ply", "contract_render_mesh_mismatch")


# --------------------------------------------------------------------------
# PLY
# --------------------------------------------------------------------------

_PLY_TYPES = {"char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1", "short": "i2", "int16": "i2", "ushort": "u2",
              "uint16": "u2", "int": "i4", "int32": "i4", "uint": "u4", "uint32": "u4", "float": "f4", "float32": "f4",
              "double": "f8", "float64": "f8"}


def read_ply(data: bytes) -> dict[str, np.ndarray]:
    """An annotated 3RScan PLY (ascii or binary little-endian) -> vertices (N, 3) float64, objectId (N,) int64, faces (F, 3) int64.

    Only triangles are accepted; the vertex element must carry x, y, z and objectId.
    """

    end = data.find(b"end_header")
    _require(data.startswith(b"ply") and end > 0, "ply_header_invalid")
    body_start = data.index(b"\n", end) + 1
    header = data[:end].decode("ascii").splitlines()
    fmt = None
    elements: list[dict[str, Any]] = []
    for line in header:
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "format":
            fmt = parts[1]
        elif parts[0] == "element":
            elements.append({"name": parts[1], "count": int(parts[2]), "properties": []})
        elif parts[0] == "property":
            _require(bool(elements), "ply_property_before_element")
            if parts[1] == "list":
                elements[-1]["properties"].append(("list", parts[2], parts[3], parts[4]))
            else:
                elements[-1]["properties"].append(("scalar", parts[1], parts[2]))
    _require(fmt in PLY_FORMATS, "ply_format_unsupported")
    names = [element["name"] for element in elements]
    _require(names[:2] == ["vertex", "face"], "ply_elements_unexpected")
    vertex, face = elements[0], elements[1]
    _require(all(kind == "scalar" for kind, *_ in vertex["properties"]), "ply_vertex_list_property")
    vertex_names = [prop[2] for prop in vertex["properties"]]
    for required in ("x", "y", "z", "objectId"):
        _require(required in vertex_names, "ply_vertex_property_missing:" + required)
    _require(len(face["properties"]) == 1 and face["properties"][0][0] == "list", "ply_face_property_unexpected")
    _kind, count_type, index_type, _name = face["properties"][0]
    n_vertices, n_faces = vertex["count"], face["count"]
    if fmt == "ascii":
        tokens = data[body_start:].split()
        width = len(vertex_names)
        _require(len(tokens) >= n_vertices * width, "ply_body_short")
        table = np.asarray(tokens[:n_vertices * width], dtype=np.float64).reshape(n_vertices, width)
        rest = tokens[n_vertices * width:]
        if len(rest) != 4 * n_faces:
            # not "3 a b c" per face: find the first face whose corner count is not 3, else the body length is wrong
            position = 0
            for _face in range(n_faces):
                _require(position < len(rest), "ply_body_short")
                _require(int(rest[position]) == 3, "ply_face_not_triangle")
                position += 4
            raise LeanS307RenderError("ply_body_size_mismatch")
        face_tokens = np.asarray(rest, dtype=np.int64).reshape(n_faces, 4)
        _require(bool((face_tokens[:, 0] == 3).all()), "ply_face_not_triangle")
        columns = {name: table[:, i] for i, name in enumerate(vertex_names)}
        faces = face_tokens[:, 1:].copy()
    else:
        vertex_dtype = np.dtype([(prop[2], "<" + _PLY_TYPES[prop[1]]) for prop in vertex["properties"]])
        vertex_bytes = n_vertices * vertex_dtype.itemsize
        record = np.frombuffer(data, dtype=vertex_dtype, count=n_vertices, offset=body_start)
        columns = {name: record[name].astype(np.float64) for name in vertex_names}
        face_dtype = np.dtype([("n", "<" + _PLY_TYPES[count_type]), ("i", "<" + _PLY_TYPES[index_type], (3,))])
        _require(len(data) - body_start - vertex_bytes == n_faces * face_dtype.itemsize, "ply_body_size_mismatch")
        face_record = np.frombuffer(data, dtype=face_dtype, count=n_faces, offset=body_start + vertex_bytes)
        _require(bool((face_record["n"] == 3).all()), "ply_face_not_triangle")
        faces = face_record["i"].astype(np.int64)
    vertices = np.column_stack((columns["x"], columns["y"], columns["z"])).astype(np.float64)
    object_ids = columns["objectId"].astype(np.int64)
    _require(bool(np.isfinite(vertices).all()), "ply_vertex_not_finite")
    _require(n_faces == 0 or (int(faces.min()) >= 0 and int(faces.max()) < n_vertices), "ply_face_index_out_of_range")
    _require(bool((object_ids >= 0).all()) and int(object_ids.max(initial=0)) <= 65535, "ply_object_id_out_of_range")
    return {"vertices": vertices, "object_ids": object_ids, "faces": faces}


# --------------------------------------------------------------------------
# camera
# --------------------------------------------------------------------------

def world_to_camera(pose_raw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(Rc, tc) with camera = Rc . scan point + tc, in the target camera's project convention (x right, y up, z forward).

    The inverse of ``lean_s3_07_3rscan.camera_pose`` taken in the scan's own frame (no alignment, no axes swap): rendering a
    rescan frame needs only that scan's mesh and pose.  Rc = S . Q . R^T, tc = -Rc . t, with R made orthonormal as ``camera_pose`` does.
    """

    matrix, _residual = r3.orthonormal_rigid(np.asarray(pose_raw, dtype=np.float64))
    rc = r3.matmul(r3.matmul(r3.S, r3.Q), matrix[:3, :3].T)
    t = matrix[:3, 3]
    tc = np.asarray([-(rc[i, 0] * t[0] + rc[i, 1] * t[1] + rc[i, 2] * t[2]) for i in range(3)])
    return rc, tc


def _apply(rc: np.ndarray, tc: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Rc . p + tc written out element by element (no BLAS, the same bits on every host)."""

    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    return np.column_stack([rc[i, 0] * x + rc[i, 1] * y + rc[i, 2] * z + tc[i] for i in range(3)])


def _nearest_vertex_labels(hit: np.ndarray, corners: np.ndarray, corner_labels: np.ndarray) -> np.ndarray:
    """Per hit point, the label of the closest of its face's three corners (ties to the first corner in face order)."""

    d = [((hit - corners[:, k, :]) ** 2).sum(axis=1) for k in range(3)]
    distances = np.column_stack(d)
    return corner_labels[np.arange(len(hit)), np.argmin(distances, axis=1)]


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _raster_candidates(camera: np.ndarray, faces: np.ndarray, face_ids: np.ndarray, labels: np.ndarray,
                       intrinsics: Mapping[str, float], size: int) -> tuple[np.ndarray, ...]:
    fx, fy, cx, cy = (float(intrinsics[k]) for k in ("fx", "fy", "cx", "cy"))
    tri = camera[faces]                               # (M, 3 corners, 3 coords)
    z = tri[:, :, 2]
    u = fx * tri[:, :, 0] / z + cx
    v = cy - fy * tri[:, :, 1] / z
    u_lo = np.maximum(np.ceil(u.min(axis=1)), 0).astype(np.int64)
    u_hi = np.minimum(np.floor(u.max(axis=1)), size - 1).astype(np.int64)
    v_lo = np.maximum(np.ceil(v.min(axis=1)), 0).astype(np.int64)
    v_hi = np.minimum(np.floor(v.max(axis=1)), size - 1).astype(np.int64)
    area = (u[:, 1] - u[:, 0]) * (v[:, 2] - v[:, 0]) - (u[:, 2] - u[:, 0]) * (v[:, 1] - v[:, 0])
    keep = (u_lo <= u_hi) & (v_lo <= v_hi) & (area != 0.0)
    width = np.where(keep, u_hi - u_lo + 1, 0)
    height = np.where(keep, v_hi - v_lo + 1, 0)
    count = width * height
    out: list[tuple[np.ndarray, ...]] = []
    order = np.flatnonzero(count)
    cumulative = np.cumsum(count[order])
    start = 0
    while start < len(order):
        base = int(cumulative[start - 1]) if start else 0
        stop = max(int(np.searchsorted(cumulative, base + CANDIDATE_CHUNK, side="right")), start + 1)
        chunk = order[start:stop]
        start = stop
        n = count[chunk]
        owner = np.repeat(chunk, n)
        local = np.arange(int(n.sum()), dtype=np.int64) - np.repeat(np.cumsum(n) - n, n)
        px = (u_lo[owner] + local % width[owner]).astype(np.float64)
        py = (v_lo[owner] + local // width[owner]).astype(np.float64)
        u0, u1, u2 = u[owner, 0], u[owner, 1], u[owner, 2]
        v0, v1, v2 = v[owner, 0], v[owner, 1], v[owner, 2]
        a = area[owner]
        l0 = ((u1 - px) * (v2 - py) - (u2 - px) * (v1 - py)) / a
        l1 = ((u2 - px) * (v0 - py) - (u0 - px) * (v2 - py)) / a
        l2 = ((u0 - px) * (v1 - py) - (u1 - px) * (v0 - py)) / a
        inside = (l0 >= 0.0) & (l1 >= 0.0) & (l2 >= 0.0)
        owner, px, py, l0, l1, l2 = owner[inside], px[inside], py[inside], l0[inside], l1[inside], l2[inside]
        zc = z[owner]
        w0, w1, w2 = l0 / zc[:, 0], l1 / zc[:, 1], l2 / zc[:, 2]
        inverse = w0 + w1 + w2
        depth = 1.0 / inverse
        corners = tri[owner]
        hit = (w0[:, None] * corners[:, 0, :] + w1[:, None] * corners[:, 1, :] + w2[:, None] * corners[:, 2, :]) / inverse[:, None]
        hit_labels = _nearest_vertex_labels(hit, corners, labels[faces[owner]])
        pixel = py.astype(np.int64) * size + px.astype(np.int64)
        out.append((pixel, depth, face_ids[owner], hit_labels))
    return _concatenate(out)


def _ray_candidates(camera: np.ndarray, faces: np.ndarray, face_ids: np.ndarray, labels: np.ndarray,
                    intrinsics: Mapping[str, float], size: int) -> tuple[np.ndarray, ...]:
    """Exact ray-triangle intersection (Moller-Trumbore) of every pixel-centre ray with each given face."""

    fx, fy, cx, cy = (float(intrinsics[k]) for k in ("fx", "fy", "cx", "cy"))
    rows, cols = np.mgrid[0:size, 0:size]
    dx = ((cols.reshape(-1).astype(np.float64)) - cx) / fx
    dy = (cy - rows.reshape(-1).astype(np.float64)) / fy
    pixels = np.arange(size * size, dtype=np.int64)
    out: list[tuple[np.ndarray, ...]] = []
    for k in range(len(faces)):
        p0, p1, p2 = camera[faces[k, 0]], camera[faces[k, 1]], camera[faces[k, 2]]
        e1, e2 = p1 - p0, p2 - p0
        # pvec = d x e2 with d = (dx, dy, 1)
        pv0 = dy * e2[2] - e2[1]
        pv1 = e2[0] - dx * e2[2]
        pv2 = dx * e2[1] - dy * e2[0]
        det = e1[0] * pv0 + e1[1] * pv1 + e1[2] * pv2
        ok = np.abs(det) > RAY_PARALLEL_EPSILON
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = -p0                                            # ray origin is the camera centre
        a = (tv[0] * pv0 + tv[1] * pv1 + tv[2] * pv2) * inv
        qv = np.asarray([tv[1] * e1[2] - tv[2] * e1[1], tv[2] * e1[0] - tv[0] * e1[2], tv[0] * e1[1] - tv[1] * e1[0]])
        b = (dx * qv[0] + dy * qv[1] + qv[2]) * inv
        t = (e2[0] * qv[0] + e2[1] * qv[1] + e2[2] * qv[2]) * inv
        hit = ok & (a >= 0.0) & (b >= 0.0) & (a + b <= 1.0) & (t > 0.0)
        if not hit.any():
            continue
        th = t[hit]
        points = np.column_stack((th * dx[hit], th * dy[hit], th))
        corners = np.broadcast_to(np.stack((p0, p1, p2))[None], (len(th), 3, 3))
        hit_labels = _nearest_vertex_labels(points, corners, np.broadcast_to(labels[faces[k]][None], (len(th), 3)))
        out.append((pixels[hit], th, np.full(len(th), face_ids[k], dtype=np.int64), hit_labels))
    return _concatenate(out)


def _concatenate(parts: list[tuple[np.ndarray, ...]]) -> tuple[np.ndarray, ...]:
    if not parts:
        return (np.zeros(0, np.int64), np.zeros(0, np.float64), np.zeros(0, np.int64), np.zeros(0, np.int64))
    return tuple(np.concatenate([part[i] for part in parts]) for i in range(4))


def render(mesh: Mapping[str, np.ndarray], pose_raw: np.ndarray, intrinsics: Mapping[str, float], *,
           size: int = r3.TARGET_SIZE) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    """One frame: (instance uint16 (size, size), depth float32 (size, size), counts) of the nearest mesh surface per pixel centre."""

    vertices, faces, object_ids = mesh["vertices"], mesh["faces"], mesh["object_ids"]
    rc, tc = world_to_camera(pose_raw)
    camera = _apply(rc, tc, np.asarray(vertices, dtype=np.float64))
    face_z = camera[faces][:, :, 2] if len(faces) else np.zeros((0, 3))
    front = (face_z >= RASTER_NEAR_M).all(axis=1)
    crossing = ~front & (face_z > 0.0).any(axis=1)
    face_ids = np.arange(len(faces), dtype=np.int64)
    raster = _raster_candidates(camera, faces[front], face_ids[front], object_ids, intrinsics, size)
    rays = _ray_candidates(camera, faces[crossing], face_ids[crossing], object_ids, intrinsics, size)
    pixel, depth, face, label = (np.concatenate((raster[i], rays[i])) for i in range(4))
    instance = np.full(size * size, BACKGROUND_LABEL, dtype=np.uint16)
    depth_map = np.full(size * size, r3.INVALID_DEPTH_M, dtype=np.float32)
    if len(pixel):
        order = np.lexsort((face, depth, pixel))
        pixel, depth, label = pixel[order], depth[order], label[order]
        first = np.ones(len(pixel), dtype=bool)
        first[1:] = pixel[1:] != pixel[:-1]
        instance[pixel[first]] = label[first].astype(np.uint16)
        depth_map[pixel[first]] = depth[first].astype(np.float32)
    lo, hi = r3.FROZEN_DEPTH_VALID_RANGE_M
    counts = {"faces": int(len(faces)), "faces_rasterised": int(front.sum()), "faces_ray_cast": int(crossing.sum()),
              "pixels_hit": int((depth_map > 0).sum()), "pixels_labelled": int((instance != BACKGROUND_LABEL).sum()),
              "pixels_depth_below_frozen_min": int(((depth_map > 0) & (depth_map < lo)).sum()),
              "pixels_depth_above_frozen_max": int((depth_map > hi).sum())}
    return instance.reshape(size, size), depth_map.reshape(size, size), counts
