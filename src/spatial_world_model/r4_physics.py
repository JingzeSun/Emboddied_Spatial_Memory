"""R4 MuJoCo adapter: independent gates and directly streamed lossless shards.

History, sensors, state restore, controller and contact extraction inherit the
pinned D-071 scene. The rollout is a source-visible copy with only per-gate
lookup and storage replacements, so no old scientific source bytes change.
"""
import gzip
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import json
import numpy as np
from .two_gate_physics import (TwoGateScene, build_xml as base_xml, _numbers,
                               _notify, _save_json, save_png, encode, sha, STATE, WORLD_NAMES)
from .r4_families import legacy_view, validate_family_config
from .r4_storage import LosslessArray, compressed_writer


def build_xml(reference, config, world_name):
    validate_family_config(config)
    tree = ET.fromstring(base_xml(reference, legacy_view(config), world_name))
    tree.set("model", "sh04-r4-continuous-family")
    g = config["geometry"]
    low, high = g["cross_wall_outer_x_m"]
    for index, side in enumerate(world_name):
        center, width = g["gate_centers_x_m"][index][side], g["gate_widths_m"][index]
        for label, a, b in (("left", low, center - width / 2), ("right", center + width / 2, high)):
            node = tree.find(f"./worldbody/geom[@name='gate_{index}_{label}']")
            node.set("pos", _numbers(((a + b) / 2, g["gate_y_m"][index], g["wall_height_m"] / 2)))
            node.set("size", _numbers(((b - a) / 2, g["wall_thickness_m"] / 2, g["wall_height_m"] / 2)))
    return ET.tostring(tree, encoding="unicode")


class R4Scene(TwoGateScene):
    def history(self, *, progress=None, frame_sink=None):
        """Same D-071 stepping/observation order; append each captured prefix."""
        o = self.config["observation"]
        self.set_camera(self.camera_y_at(0.0))
        for index in range(self.steps_for(o["settle_before_history_s"])):
            self.step([0, 0, 0])
            if index % 50 == 0:
                _notify(progress, "settle", physics_step=index)
        frames, visible = [], []
        def capture():
            observation, visibility = self.observe(), self.visibility()
            if frame_sink is not None:
                frame_sink({"frame_index": len(frames), "observation": observation,
                            "visibility": visibility, "snapshot": self.snapshot()})
            frames.append(observation)
            visible.append(visibility)
        capture()
        stride = self.steps_for(o["sample_s"])
        for index in range(1, self.steps_for(o["history_duration_s"]) + 1):
            self.set_camera(self.camera_y_at(index * self.model.opt.timestep))
            self.step([0, 0, 0])
            if index % stride == 0:
                capture()
                _notify(progress, "history", frame_index=len(frames) - 1, physics_step=index)
        if len(frames) != o["history_frame_count"]:
            raise ValueError("history frame count mismatch")
        return frames, visible

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
            expected = self.config["geometry"]["gate_centers_x_m"][index][side]
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
            "depth.npy": ((len(controls) + 1, *first_depth.shape), np.dtype("float64")),
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
                arrays[name] = LosslessArray(directory / (name + ".gz"), shape, dtype, progress)
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
            with compressed_writer(directory / "trace_raw.jsonl.gz", progress) as stream:
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
            with gzip.open(directory / "trace_raw.jsonl.gz", "rb") as handle:
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
            _notify(progress, "write", file="trajectory.jsonl", reserve_bytes=65536)
            with compressed_writer(directory / "trajectory.jsonl.gz", progress) as stream:
                for index, sample in enumerate(samples):
                    if index % 250 == 0:
                        _notify(progress, "trajectory", physics_step=index)
                    stream.write(encode(sample))
            _notify(progress, "write", file="visibility.jsonl", reserve_bytes=len(visibility_records) * 1024)
            with compressed_writer(directory / "visibility.jsonl.gz", progress) as stream:
                for index, counts in sorted(visibility_records.items()):
                    stream.write(encode({"step_index": index, "counts": counts}))
            _save_json(directory / "end_snapshot.json", end_snapshot, progress)
            save_png(directory / "final_ego.png", np.asarray(arrays["rgb.npy"][-1]), progress=progress)
            save_png(directory / "private_overview.png", self.render(camera="review"), progress=progress)
            if self.snapshot() != end_snapshot:
                raise ValueError("private review rendering changed integration state")
            for array in arrays.values():
                array.close()
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
        except BaseException as error:
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
                array.close()
