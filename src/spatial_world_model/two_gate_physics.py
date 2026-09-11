"""Server-only SH04-R2 physics, real sensors, and saved-state visibility audit.

No learner, filtering, parameter search, or privileged model-input construction.
The old SH-02 module is deliberately not imported or modified.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zlib

import mujoco as mj
import numpy as np


STATE = mj.mjtState.mjSTATE_INTEGRATION
WORLD_NAMES = ("LL", "LR", "RL", "RR")


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _notify(progress, phase, **fields):
    if progress is not None:
        progress({"phase": phase, **fields})


def _save_json(path, value, progress=None):
    raw = encode(value)
    _notify(progress, "write", file=Path(path).name, reserve_bytes=len(raw))
    with Path(path).open("xb") as handle:
        handle.write(raw)


def _numbers(values):
    return " ".join(format(float(value), ".17g") for value in values)


def save_png(path, rgb, *, progress=None):
    """Save original uint8 sensor pixels losslessly, without annotations."""
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("expected original HxWx3 uint8 RGB")
    height, width, _ = rgb.shape

    def chunk(kind, raw):
        return struct.pack(">I", len(raw)) + kind + raw + struct.pack(">I", zlib.crc32(kind + raw))

    rows = b"".join(b"\0" + row.tobytes() for row in rgb)
    raw = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    _notify(progress, "write", file=Path(path).name, reserve_bytes=len(raw))
    with Path(path).open("xb") as handle:
        handle.write(raw)


def _required(tree, path):
    node = tree.find(path)
    if node is None:
        raise ValueError("reference XML is missing " + path)
    return node


def build_xml(reference_xml_text, config, world_name):
    """Copy declared physics; replace the old scene with four gate wall pieces."""
    if world_name not in WORLD_NAMES:
        raise ValueError("unknown two-gate world")
    g, o = config["geometry"], config["observation"]
    if len(g["gate_y_m"]) != 2 or g["gate_clear_width_m"] <= 0:
        raise ValueError("two positive-width gates are required")
    if g["visual_occlusion_screen"]:
        raise ValueError("R2 uses finite field of view, not an occlusion screen")
    tree = ET.fromstring(reference_xml_text)
    tree.set("model", "sh04-r2-two-gate-engineering")
    world = _required(tree, "worldbody")
    # Only these known SH-02 static obstacles are removed. Bodies and their
    # joint/actuator definitions stay under the pinned reference physics.
    for name in ("screen", "wall"):
        world.remove(_required(tree, "./worldbody/geom[@name='" + name + "']"))
    _required(tree, "option").set("timestep", str(config["simulator"]["timestep_s"]))
    _required(tree, "./default/geom").set("friction", _numbers(g["friction"]))
    # Fixed across all four worlds: renderer clipping must not inherit a
    # layout-dependent automatic model statistic.
    statistic = _required(tree, "statistic")
    statistic.set("extent", "4")
    statistic.set("center", "0 1.3 0")
    visual = _required(tree, "./visual/global")
    height, width = o["resolution"]
    visual.set("offheight", str(height))
    visual.set("offwidth", str(width))
    _required(tree, "./visual/quality").set("offsamples", "0")
    low_x, high_x = g["cross_wall_outer_x_m"]
    if [low_x, high_x] != g["side_wall_inner_x_m"]:
        raise ValueError("cross walls must meet side-wall inner surfaces")
    half_z, half_y = g["wall_height_m"] / 2, g["wall_thickness_m"] / 2
    for gate_index, side in enumerate(world_name):
        center = g["gate_center_x_m"][side]
        left, right = center - g["gate_clear_width_m"] / 2, center + g["gate_clear_width_m"] / 2
        if not low_x < left < right < high_x:
            raise ValueError("gate opening must be inside both wall ends")
        for label, a, b in (("left", low_x, left), ("right", right, high_x)):
            ET.SubElement(world, "geom", {
                "name": f"gate_{gate_index}_{label}", "type": "box",
                "pos": _numbers(((a + b) / 2, g["gate_y_m"][gate_index], half_z)),
                "size": _numbers(((b - a) / 2, half_y, half_z)),
                "rgba": "0.85 0.2 0.1 1",
            })
    side_y0, side_y1 = g["side_wall_y_bounds_m"]
    side_half = g["side_wall_thickness_m"] / 2
    if side_y1 <= side_y0 or side_half <= 0:
        raise ValueError("invalid side walls")
    for name, x in (("left", low_x - side_half), ("right", high_x + side_half)):
        ET.SubElement(world, "geom", {
            "name": "side_" + name, "type": "box",
            "pos": _numbers((x, (side_y0 + side_y1) / 2, half_z)),
            "size": _numbers((side_half, (side_y1 - side_y0) / 2, half_z)),
            "rgba": "0.55 0.55 0.55 1",
        })
    _required(tree, "./worldbody/body[@name='object']").set("pos", _numbers(g["object_initial_position_m"]))
    obj = _required(tree, "./worldbody/body/geom[@name='object']")
    obj.set("size", _numbers((g["object_radius_m"], g["object_half_height_m"])))
    obj.set("mass", str(g["object_mass_kg"]))
    _required(tree, "./worldbody/body[@name='pusher']").set("pos", _numbers(g["pusher_initial_position_m"]))
    pusher = _required(tree, "./worldbody/body/geom[@name='pusher']")
    pusher.set("size", _numbers(g["pusher_half_size_m"]))
    pusher.set("mass", str(g["pusher_mass_kg"]))
    for name in ("vx", "vy"):
        actuator = _required(tree, "./actuator/velocity[@name='" + name + "']")
        actuator.set("kv", str(g["velocity_servo_kv"]))
        actuator.set("ctrlrange", _numbers((-g["control_limit_per_axis_mps"], g["control_limit_per_axis_mps"])))
        actuator.set("forcerange", _numbers((-g["force_limit_per_axis_n"], g["force_limit_per_axis_n"])))
    rig = _required(tree, "./worldbody/body[@name='camera_rig']")
    rig.set("pos", _numbers((o["camera_x_m"], o["camera_segments"][0]["y_m"][0], o["camera_height_m"])))
    rig.set("quat", _numbers(o["camera_mujoco_quat_wxyz"]))
    camera = _required(tree, "./worldbody/body/camera[@name='ego']")
    camera.set("quat", "1 0 0 0")
    camera.set("fovy", str(o["camera_fovy_degrees"]))
    # Privileged artifact review only. observe/history/sensor arrays always use
    # ego; this fixed camera does not add a mocap body or integration inputs.
    ET.SubElement(world, "camera", {"name": "review", "pos": "0 1.3 3.2",
                                  "quat": "1 0 0 0", "fovy": "65"})
    return ET.tostring(tree, encoding="unicode")


def expand_controls(config, action_name):
    """Compatibility accessor; the contract owns the only expansion algorithm."""
    from .two_gate_contract import expand_controls as contract_controls
    if action_name not in WORLD_NAMES:
        raise ValueError("unknown control sequence")
    return contract_controls(config)[action_name]


class TwoGateScene:
    def __init__(self, xml, config):
        versions = config["simulator"]
        if mj.__version__ != versions["mujoco"] or np.__version__ != versions["numpy"]:
            raise ValueError("pinned MuJoCo/NumPy version mismatch")
        self.xml, self.config = xml, deepcopy(config)
        self.model = mj.MjModel.from_xml_string(xml)
        self.data = mj.MjData(self.model)
        if not math.isclose(self.model.opt.timestep, versions["timestep_s"], abs_tol=1e-15):
            raise ValueError("physics timestep mismatch")
        height, width = config["observation"]["resolution"]
        self.renderer = mj.Renderer(self.model, height=height, width=width)
        self.camera_id = self.model.camera("ego").id
        self.mocap_id = int(self.model.body("camera_rig").mocapid[0])
        self.geom_ids = {self.model.geom(i).name: i for i in range(self.model.ngeom)}
        self.refresh()

    def close(self):
        self.renderer.close()

    def state(self):
        value = np.empty(mj.mj_stateSize(self.model, STATE), dtype=np.float64)
        mj.mj_getState(self.model, self.data, value, STATE)
        return value

    def refresh(self):
        value = self.state()
        mj.mj_forward(self.model, self.data)
        mj.mj_setState(self.model, self.data, value, STATE)

    def snapshot(self):
        return {"xml_sha256": sha(self.xml.encode("utf-8")), "state_spec": int(STATE),
                "state": self.state().tolist()}

    def digest(self, snapshot=None):
        return sha(encode(self.snapshot() if snapshot is None else snapshot))

    def _restore_state(self, value):
        value = np.asarray(value, dtype=np.float64)
        if value.shape != self.state().shape or not np.isfinite(value).all():
            raise ValueError("invalid complete integration state")
        mj.mj_setState(self.model, self.data, value, STATE)
        self.refresh()
        if not np.array_equal(self.state(), value):
            raise ValueError("state restoration changed integration inputs")

    def restore(self, snapshot, digest):
        if set(snapshot) != {"xml_sha256", "state_spec", "state"}:
            raise ValueError("invalid snapshot schema")
        if self.digest(snapshot) != digest or snapshot["xml_sha256"] != sha(self.xml.encode("utf-8")):
            raise ValueError("snapshot digest/model mismatch")
        if snapshot["state_spec"] != int(STATE):
            raise ValueError("wrong snapshot state specification")
        self._restore_state(snapshot["state"])

    def steps_for(self, seconds):
        count = round(seconds / self.model.opt.timestep)
        if count <= 0 or not math.isclose(count * self.model.opt.timestep, seconds, abs_tol=1e-12):
            raise ValueError("duration must be a positive integral physics-step count")
        return count

    def camera_y_at(self, seconds):
        o = self.config["observation"]
        if not math.isfinite(seconds) or not 0 <= seconds <= o["history_duration_s"]:
            raise ValueError("camera time outside the registered history")
        for segment in o["camera_segments"]:
            t0, t1 = segment["time_s"]
            if t0 <= seconds <= t1:
                u = (seconds - t0) / (t1 - t0)
                a, b = segment["y_m"]
                return a + (b - a) * u * u * (3 - 2 * u)
        raise ValueError("camera path has an uncovered time")

    def set_camera(self, y):
        if not math.isfinite(y):
            raise ValueError("nonfinite camera position")
        o = self.config["observation"]
        self.data.mocap_pos[self.mocap_id] = [o["camera_x_m"], y, o["camera_height_m"]]
        self.data.mocap_quat[self.mocap_id] = o["camera_mujoco_quat_wxyz"]
        self.refresh()

    def velocity(self, name):
        value = np.empty(6)
        mj.mj_objectVelocity(self.model, self.data, mj.mjtObj.mjOBJ_BODY,
                            self.model.body(name).id, value, 0)
        return value[3:].tolist()

    def render(self, kind="rgb", *, camera="ego"):
        self.renderer.disable_depth_rendering()
        self.renderer.disable_segmentation_rendering()
        if kind == "depth":
            self.renderer.enable_depth_rendering()
        elif kind == "segmentation":
            self.renderer.enable_segmentation_rendering()
        elif kind != "rgb":
            raise ValueError("unknown sensor kind")
        self.renderer.update_scene(self.data, camera=camera)
        for flag in (mj.mjtRndFlag.mjRND_SHADOW, mj.mjtRndFlag.mjRND_REFLECTION):
            self.renderer.scene.flags[flag] = False
        return self.renderer.render().copy()

    def visibility(self):
        image = self.render("segmentation")
        geom = image[:, :, 1] == int(mj.mjtObj.mjOBJ_GEOM)
        return {name: int(np.count_nonzero(geom & (image[:, :, 0] == index)))
                for name, index in self.geom_ids.items()}

    def observe(self, previous=(0, 0, 0)):
        rgb, depth = self.render(), self.render("depth")
        height, width = self.config["observation"]["resolution"]
        rotation = self.data.cam_xmat[self.camera_id].reshape(3, 3) @ np.diag([1., -1., -1.])
        quat = np.empty(4)
        mj.mju_mat2Quat(quat, rotation.ravel())
        focal = height / (2 * math.tan(math.radians(float(self.model.cam_fovy[self.camera_id])) / 2))
        return {"time_s": float(self.data.time), "width": width, "height": height,
                "rgb": rgb.ravel().tolist(), "depth_m": depth.ravel().tolist(),
                "camera_position_m": self.data.cam_xpos[self.camera_id].tolist(),
                "camera_xyzw": quat[[1, 2, 3, 0]].tolist(),
                "intrinsics": [focal, focal, (width - 1) / 2, (height - 1) / 2],
                "ee_position_m": self.data.body("pusher").xpos.tolist(),
                "ee_velocity_mps": self.velocity("pusher"),
                "previous_velocity_mps": list(previous)}

    def step(self, control):
        control = np.asarray(control, dtype=np.float64)
        limit = self.config["geometry"]["control_limit_per_axis_mps"]
        if control.shape != (3,) or not np.isfinite(control).all() or control[2] != 0 or np.max(np.abs(control)) > limit:
            raise ValueError("invalid planar velocity command")
        self.data.ctrl[:] = control[:2]
        mj.mj_step(self.model, self.data)
        self.refresh()
        if not np.isfinite(self.state()).all() or any(warning.number for warning in self.data.warning):
            raise ValueError("simulator warning/nonfinite state; preserve this run")

    def history(self, *, progress=None):
        o = self.config["observation"]
        self.set_camera(self.camera_y_at(0.0))
        for index in range(self.steps_for(o["settle_before_history_s"])):
            self.step([0, 0, 0])
            if index % 50 == 0:
                _notify(progress, "settle", physics_step=index)
        frames, visible = [self.observe()], [self.visibility()]
        stride = self.steps_for(o["sample_s"])
        count = self.steps_for(o["history_duration_s"])
        for index in range(1, count + 1):
            self.set_camera(self.camera_y_at(index * self.model.opt.timestep))
            self.step([0, 0, 0])
            if index % stride == 0:
                frames.append(self.observe())
                visible.append(self.visibility())
                _notify(progress, "history", frame_index=len(frames) - 1, physics_step=index)
        if len(frames) != o["history_frame_count"]:
            raise ValueError("history frame count mismatch")
        return frames, visible

    def contacts(self):
        """Every raw MuJoCo contact, including zero-force/separated contacts."""
        result = []
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            force = np.empty(6)
            mj.mj_contactForce(self.model, self.data, index, force)
            result.append({"geoms": sorted(self.model.geom(int(g)).name for g in contact.geom),
                           "distance_m": float(contact.dist), "normal_force_n": float(force[0])})
        return result

    def _sample(self, index, start_time):
        return {"step_index": index, "time_s": float(self.data.time) - start_time,
                "object_position_m": self.data.body("object").xpos.tolist(),
                "object_axis_world": self.data.body("object").xmat.reshape(3, 3)[:, 2].tolist(),
                "object_linear_velocity_mps": self.velocity("object"),
                "pusher_position_m": self.data.body("pusher").xpos.tolist(),
                "actuator_force_n": self.data.actuator_force.tolist(),
                "contacts": self.contacts(), "object_visible_pixels": None}

    def rollout(self, snapshot, controls, directory, *, world_name, assessor, progress=None):
        """Stream actual states/sensors, then observe saved states without stepping.

        The assessor is the separately reviewed pure contract function. Its first
        pass requests real segmentation samples; its second pass uses those
        observations. No success matrix is assumed here.
        """
        if world_name not in WORLD_NAMES:
            raise ValueError("unknown two-gate world")
        for index, side in enumerate(world_name):
            left = self.geom_ids[f"gate_{index}_left"]
            right = self.geom_ids[f"gate_{index}_right"]
            opening_left = self.model.geom_pos[left, 0] + self.model.geom_size[left, 0]
            opening_right = self.model.geom_pos[right, 0] - self.model.geom_size[right, 0]
            expected = self.config["geometry"]["gate_center_x_m"][side]
            if not math.isclose((opening_left + opening_right) / 2, expected, abs_tol=1e-12):
                raise ValueError("audit world label does not match the actual gate geometry")
        c = self.config["controls"]
        if len(controls) != c["control_steps"] or any(
                row["duration_s"] != c["sample_s"] for row in controls):
            raise ValueError("rollout requires the registered full control horizon")
        base_digest = self.digest(snapshot)
        self.restore(snapshot, base_digest)
        expected_y = self.config["observation"]["future_camera_y_m"]
        if not math.isclose(float(self.data.mocap_pos[self.mocap_id, 1]), expected_y, abs_tol=1e-12):
            raise ValueError("decision camera is not at the registered final position")
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        stride = self.steps_for(c["sample_s"])
        total = len(controls) * stride
        start_time = float(self.data.time)
        first_rgb, first_depth = self.render(), self.render("depth")
        state_width = len(self.state())
        arrays = {}
        allocation = {
            "integration.npy": ((total + 1, state_width), np.dtype("float64")),
            "rgb.npy": ((len(controls) + 1, *first_rgb.shape), first_rgb.dtype),
            "depth.npy": ((len(controls) + 1, *first_depth.shape), first_depth.dtype),
            "sensor_times.npy": ((len(controls) + 1,), np.dtype("float64")),
            "sensor_step_indices.npy": ((len(controls) + 1,), np.dtype("int64")),
        }
        completed = 0
        valid_state_rows = 0
        valid_sensor_rows = 0
        written_rows = 0
        interval_rows = []
        visibility_records = {}
        try:
            for name, (shape, dtype) in allocation.items():
                size = math.prod(shape) * dtype.itemsize + 4096
                _notify(progress, "allocate", file=name, reserve_bytes=size)
                arrays[name] = np.lib.format.open_memmap(directory / name, mode="w+", dtype=dtype, shape=shape)
            arrays["rgb.npy"][0] = first_rgb
            arrays["depth.npy"][0] = first_depth
            arrays["sensor_times.npy"][0] = 0
            arrays["sensor_step_indices.npy"][0] = 0
            valid_sensor_rows = 1
            arrays["integration.npy"][0] = self.state()
            valid_state_rows = 1
            initial = self._sample(0, start_time)
            visibility_records[0] = self.visibility()
            initial["object_visible_pixels"] = visibility_records[0]["object"]
            with (directory / "trace_raw.jsonl").open("xb") as stream:
                raw = encode(initial)
                _notify(progress, "write", file="trace_raw.jsonl", reserve_bytes=len(raw))
                stream.write(raw)
                written_rows = 1
                for interval, control in enumerate(controls):
                    _notify(progress, "control", control_index=interval)
                    interval_rows = []
                    for _ in range(stride):
                        self.step(control["ee_velocity_mps"])
                        completed += 1
                        arrays["integration.npy"][completed] = self.state()
                        valid_state_rows = completed + 1
                        sample = self._sample(completed, start_time)
                        if completed % stride == 0:
                            sensor = completed // stride
                            arrays["rgb.npy"][sensor] = self.render()
                            arrays["depth.npy"][sensor] = self.render("depth")
                            arrays["sensor_times.npy"][sensor] = sample["time_s"]
                            arrays["sensor_step_indices.npy"][sensor] = completed
                            valid_sensor_rows = sensor + 1
                            visibility_records[completed] = self.visibility()
                            sample["object_visible_pixels"] = visibility_records[completed]["object"]
                        interval_rows.append(encode(sample))
                    raw = b"".join(interval_rows)
                    _notify(progress, "write", file="trace_raw.jsonl", reserve_bytes=len(raw))
                    stream.write(raw)
                    written_rows += len(interval_rows)
                    interval_rows = []
                    stream.flush()
            end_snapshot = self.snapshot()
            for array in arrays.values():
                array.flush()
            with (directory / "trace_raw.jsonl").open("rb") as handle:
                samples = [json.loads(line) for line in handle]
            preliminary = assessor(samples, self.config, world_name=world_name)
            indices = preliminary["required_visibility_indices"]
            if any(type(index) is not int or not 0 <= index <= total for index in indices):
                raise ValueError("assessor requested an invalid saved-state index")
            for order, index in enumerate(sorted(set(indices))):
                if order % 25 == 0:
                    _notify(progress, "visibility", audited=order, requested=len(indices))
                if index not in visibility_records:
                    self._restore_state(arrays["integration.npy"][index])
                    before = self.state()
                    visibility_records[index] = self.visibility()
                    if not np.array_equal(before, self.state()):
                        raise ValueError("segmentation observation changed saved integration state")
                samples[index]["object_visible_pixels"] = visibility_records[index]["object"]
            self.restore(end_snapshot, self.digest(end_snapshot))
            assessment = assessor(samples, self.config, world_name=world_name)
            _notify(progress, "write", file="trajectory.jsonl", reserve_bytes=(directory / "trace_raw.jsonl").stat().st_size + 65536)
            with (directory / "trajectory.jsonl").open("xb") as stream:
                for index, sample in enumerate(samples):
                    if index % 250 == 0:
                        _notify(progress, "trajectory", physics_step=index)
                    stream.write(encode(sample))
            _notify(progress, "write", file="visibility.jsonl", reserve_bytes=len(visibility_records) * 1024)
            with (directory / "visibility.jsonl").open("xb") as stream:
                for index, counts in sorted(visibility_records.items()):
                    stream.write(encode({"step_index": index, "counts": counts}))
            _save_json(directory / "end_snapshot.json", end_snapshot, progress)
            save_png(directory / "final_ego.png", np.asarray(arrays["rgb.npy"][-1]), progress=progress)
            save_png(directory / "private_overview.png", self.render(camera="review"), progress=progress)
            if self.snapshot() != end_snapshot:
                raise ValueError("private review rendering changed integration state")
            files = {}
            for path in sorted(directory.iterdir()):
                if path.is_file():
                    digest = hashlib.sha256()
                    with path.open("rb") as handle:
                        for block in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(block)
                    files[path.name] = {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}
            result = {"base_snapshot_sha256": base_digest, "control_sha256": sha(encode(controls)),
                      "end_snapshot": end_snapshot, "state_spec": int(STATE),
                      "state_shape": [total + 1, state_width], "step_count": total,
                      "sensor_count": len(controls) + 1, "assessment": assessment, "files": files}
            _save_json(directory / "rollout.json", result, progress)
            return result
        except Exception as error:
            # No retry or replacement. Even preallocated arrays retain their
            # valid-prefix boundary, and failed-current-state bytes are kept.
            if arrays:
                with (directory / "failed_current_state.f64").open("xb") as handle:
                    handle.write(self.state().tobytes())
            if interval_rows:
                # At most one 0.1-second batch; use the reserved failure space.
                # This is separate evidence, not a repair/overwrite of rawtrace.
                with (directory / "pending_actual_samples.jsonl").open("xb") as handle:
                    handle.write(b"".join(interval_rows))
            _save_json(directory / "failure.json", {"completed_physics_steps": completed,
                       "valid_state_rows": valid_state_rows,
                       "valid_sensor_rows": valid_sensor_rows,
                       "trace_rows_written": written_rows,
                       "pending_actual_sample_rows": len(interval_rows),
                       "error_type": type(error).__name__, "error": str(error)}, None)
            raise
        finally:
            for array in arrays.values():
                array.flush()
