"""SH-02: one fixed engineering pair, actual controls, snapshots and sensors.

Server-only MuJoCo adapter. No learner, dataset sampling or success filtering.
Private segmentation/contact/trajectory records are audit evidence, not inputs.
Physical constants and the fixed candidate sequences live in configs/.
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


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save_json(path, value):
    with Path(path).open("xb") as handle:
        handle.write(encode(value))


def save_png(path, rgb):
    """Lossless raw sensor preview; no annotation or image generation."""
    height, width, _ = rgb.shape
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\0" + row.tobytes() for row in rgb)
    raw = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    with Path(path).open("xb") as handle:
        handle.write(raw)


class Scene:
    def __init__(self, xml, config):
        if mj.__version__ != config["mujoco"] or np.__version__ != config["numpy"]:
            raise ValueError("pinned MuJoCo/NumPy version mismatch")
        self.xml, self.config = xml, deepcopy(config)
        self.model = mj.MjModel.from_xml_string(xml)
        self.data = mj.MjData(self.model)
        self.renderer = mj.Renderer(self.model, height=config["resolution"], width=config["resolution"])
        self.camera_id = self.model.camera("ego").id
        self.geom_ids = {name: self.model.geom(name).id for name in ("object", "pusher", "wall", "screen")}
        self.refresh()

    def close(self):
        self.renderer.close()

    def state(self):
        state = np.empty(mj.mj_stateSize(self.model, STATE))
        mj.mj_getState(self.model, self.data, state, STATE)
        return state

    def refresh(self):
        # Forward refreshes derived poses/contacts but also solver warmstart.
        # Restore all integration inputs so observing cannot change a rollout.
        state = self.state()
        mj.mj_forward(self.model, self.data)
        mj.mj_setState(self.model, self.data, state, STATE)

    def snapshot(self):
        return {"xml_sha256": sha(self.xml.encode()), "state_spec": int(STATE), "state": self.state().tolist()}

    def restore(self, snapshot, digest):
        if sha(encode(snapshot)) != digest or snapshot["xml_sha256"] != sha(self.xml.encode()):
            raise ValueError("snapshot digest/model mismatch")
        state = np.asarray(snapshot["state"], dtype=np.float64)
        if snapshot["state_spec"] != int(STATE) or state.shape != self.state().shape or not np.isfinite(state).all():
            raise ValueError("invalid integration state")
        mj.mj_setState(self.model, self.data, state, STATE)
        self.refresh()
        if self.snapshot() != snapshot:
            raise ValueError("restore changed integration state")

    def camera_at(self, fraction):
        theta = math.pi * fraction
        c = self.config
        pos = np.array([c["camera_radius_m"] * math.sin(theta),
                        c["camera_radius_m"] * math.cos(theta), c["camera_height_m"]])
        back = pos - np.asarray(c["camera_target_m"])
        back /= np.linalg.norm(back)
        right = np.cross([0, 0, 1], back)
        right /= np.linalg.norm(right)
        up = np.cross(back, right)
        quat = np.empty(4)
        mj.mju_mat2Quat(quat, np.column_stack((right, up, back)).ravel())
        self.data.mocap_pos[0] = pos
        self.data.mocap_quat[0] = quat
        self.refresh()

    def velocity(self, body):
        value = np.empty(6)
        mj.mj_objectVelocity(self.model, self.data, mj.mjtObj.mjOBJ_BODY, self.model.body(body).id, value, 0)
        return value[3:].tolist()

    def render(self, kind="rgb"):
        self.renderer.disable_depth_rendering()
        self.renderer.disable_segmentation_rendering()
        if kind == "depth":
            self.renderer.enable_depth_rendering()
        elif kind == "segmentation":
            self.renderer.enable_segmentation_rendering()
        elif kind != "rgb":
            raise ValueError("unknown render kind")
        self.renderer.update_scene(self.data, camera="ego")
        for flag in (mj.mjtRndFlag.mjRND_SHADOW, mj.mjtRndFlag.mjRND_REFLECTION):
            self.renderer.scene.flags[flag] = False
        return self.renderer.render().copy()

    def visibility(self):
        seg = self.render("segmentation")
        geom = seg[:, :, 1] == int(mj.mjtObj.mjOBJ_GEOM)
        return {name: int(np.count_nonzero(geom & (seg[:, :, 0] == idx)))
                for name, idx in self.geom_ids.items()}

    def observe(self, previous=(0, 0, 0)):
        rgb, depth = self.render(), self.render("depth")
        rotation = self.data.cam_xmat[self.camera_id].reshape(3, 3) @ np.diag([1., -1., -1.])
        quat = np.empty(4)
        mj.mju_mat2Quat(quat, rotation.ravel())
        n = self.config["resolution"]
        focal = n / (2 * math.tan(math.radians(float(self.model.cam_fovy[self.camera_id])) / 2))
        return {"time_s": float(self.data.time), "width": n, "height": n,
                "rgb": rgb.ravel().tolist(), "depth_m": depth.ravel().tolist(),
                "camera_position_m": self.data.cam_xpos[self.camera_id].tolist(),
                "camera_xyzw": quat[[1, 2, 3, 0]].tolist(), "intrinsics": [focal, focal, (n-1)/2, (n-1)/2],
                "ee_position_m": self.data.body("pusher").xpos.tolist(),
                "ee_velocity_mps": self.velocity("pusher"), "previous_velocity_mps": list(previous)}

    def step(self, control):
        velocity = np.asarray(control, dtype=float)
        if velocity.shape != (3,) or not np.isfinite(velocity).all() or velocity[2] != 0 or np.max(np.abs(velocity)) > 0.5:
            raise ValueError("expected finite planar velocity within +/-0.5 m/s")
        self.data.ctrl[:] = velocity[:2]
        mj.mj_step(self.model, self.data)
        self.refresh()
        if not np.isfinite(self.state()).all() or any(w.number for w in self.data.warning):
            raise ValueError("simulator nonfinite state/warning; preserve this run")

    def steps_for(self, seconds):
        steps = round(seconds / self.model.opt.timestep)
        if steps <= 0 or not math.isclose(steps * self.model.opt.timestep, seconds, abs_tol=1e-12):
            raise ValueError("duration must be a positive integral physics-step count")
        return steps

    def history(self):
        c = self.config
        self.camera_at(0)
        for _ in range(self.steps_for(c["settle_s"])):
            self.step([0, 0, 0])
        frames, visible = [self.observe()], [self.visibility()]
        samples, steps = c["history_arc_samples"], self.steps_for(c["sample_s"])
        for sample in range(1, samples + c["recent_frames"]):
            for sub in range(1, steps + 1):
                fraction = min((sample - 1 + sub / steps) / (samples - 1), 1.)
                self.camera_at(fraction)
                self.step([0, 0, 0])
            frames.append(self.observe())
            visible.append(self.visibility())
        return frames, visible

    def contacts(self):
        result = []
        for index, contact in enumerate(self.data.contact):
            force = np.empty(6)
            mj.mj_contactForce(self.model, self.data, index, force)
            if contact.dist <= 0 and force[0] > self.config["contact_force_min_n"]:
                names = sorted(self.model.geom(int(g)).name for g in contact.geom)
                result.append({"geoms": names, "normal_force_n": float(force[0]), "distance_m": float(contact.dist)})
        return result

    def rollout(self, snapshot, controls):
        digest = sha(encode(snapshot))
        self.restore(snapshot, digest)
        future, trace, rgb, depth = [], [], [], []
        for control in controls:
            interval_contact = False
            for _ in range(self.steps_for(control["duration_s"])):
                self.step(control["ee_velocity_mps"])
                contacts = self.contacts()
                hidden_contact = any("object" in c["geoms"] and any(g in c["geoms"] for g in ("wall", "screen")) for c in contacts)
                interval_contact |= hidden_contact
                rotation = self.data.body("object").xmat.reshape(3, 3)
                trace.append({"time_s": float(self.data.time), "qpos": self.data.qpos.tolist(),
                              "qvel": self.data.qvel.tolist(), "object_position_m": self.data.body("object").xpos.tolist(),
                              "object_tilt_rad": math.acos(float(np.clip(rotation[2, 2], -1, 1))),
                              "ee_position_m": self.data.body("pusher").xpos.tolist(),
                              "ee_velocity_mps": self.velocity("pusher"), "command_mps": list(control["ee_velocity_mps"]),
                              "actuator_force_n": self.data.actuator_force.tolist(), "contacts": contacts,
                              "contact_visibility": self.visibility() if hidden_contact else None})
            future.append({"time_s": float(self.data.time), "object_position_m": self.data.body("object").xpos.tolist(),
                           "contact": bool(interval_contact)})
            rgb.append(self.render())
            depth.append(self.render("depth"))
        return {"base_snapshot_sha256": digest, "future": future, "trace": trace,
                "end_snapshot": self.snapshot()}, np.stack(rgb), np.stack(depth)


def generate_fixture(directory, config_path, xml_path):
    """Write all four branches and reverse-order independent replays, no filtering."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    template = Path(xml_path).read_text(encoding="utf-8")
    save_json(directory / "config.json", config)
    actions = []
    for sign in (1, -1):
        action = []
        for phase in config["left_control_phases"]:
            vx, vy, vz = phase["ee_velocity_mps"]
            action.extend({"duration_s": config["sample_s"], "ee_velocity_mps": [sign * vx, vy, vz]}
                          for _ in range(phase["samples"]))
        actions.append(action)
    pair = {"schema_version": "spatial-history-pair-v1", "pair_id": "sh02-fixed-engineering-pair",
            "family_id": "sh02-engineering-only", "split": "development", "recent_frames": config["recent_frames"],
            "control_kind": "ee_velocity_world_mps", "goal": config["goal"], "actions": actions, "worlds": [],
            "provenance": {"kind": "simulator_export", "simulator": "MuJoCo " + mj.__version__, "seed": config["seed"],
                           "code_sha256": sha(Path(__file__).read_bytes()),
                           "config_sha256": sha(encode({"config": config, "xml": template}))}}
    evidence = {"history_visibility": [], "replay_equal": [], "observation_preserves_snapshot": [],
                "nonlayout_integration_equal": False, "branches": []}
    snapshots = []
    for world_index, sign in enumerate((-1, 1)):
        tree = ET.fromstring(template)
        wall = tree.find("./worldbody/geom[@name='wall']")
        pos = [float(x) for x in wall.attrib["pos"].split()]
        pos[0] = sign * abs(pos[0])
        wall.set("pos", " ".join(map(str, pos)))
        xml = ET.tostring(tree, encoding="unicode")
        (directory / f"world-{world_index}.xml").write_text(xml, encoding="utf-8")
        scene = Scene(xml, config)
        try:
            print(f"SH-02 world={world_index} recording history", flush=True)
            history, visible = scene.history()
            snapshot = scene.snapshot()
            snapshots.append(snapshot)
            save_json(directory / f"world-{world_index}-snapshot.json", snapshot)
            scene.observe()
            scene.visibility()
            evidence["observation_preserves_snapshot"].append(scene.snapshot() == snapshot)
            extent = [float(x) for x in wall.attrib["size"].split()]
            world = {"history": history, "initial_state": {
                "object_position_m": scene.data.body("object").xpos.tolist(), "object_velocity_mps": scene.velocity("object"),
                "ee_position_m": history[-1]["ee_position_m"], "ee_velocity_mps": history[-1]["ee_velocity_mps"]},
                "hidden_obstacles": [[pos[i] - extent[i] for i in range(3)] + [pos[i] + extent[i] for i in range(3)]], "branches": []}
            evidence["history_visibility"].append(visible)
            for label, frame in (("early", history[0]), ("recent", history[-1])):
                save_png(directory / f"world-{world_index}-{label}.png", np.asarray(frame["rgb"], dtype=np.uint8).reshape(config["resolution"], config["resolution"], 3))
            originals = []
            for action_index, controls in enumerate(actions):
                print(f"SH-02 world={world_index} action={action_index} primary rollout", flush=True)
                result, rgb, depth = scene.rollout(snapshot, controls)
                prefix = f"world-{world_index}-action-{action_index}"
                save_json(directory / f"{prefix}-trace.json", result)
                np.savez_compressed(directory / f"{prefix}-sensors.npz", rgb=rgb, depth_m=depth)
                save_png(directory / f"{prefix}-final.png", rgb[-1])
                world["branches"].append({"action_index": action_index, "base_snapshot_sha256": result["base_snapshot_sha256"], "future": result["future"]})
                originals.append((sha(encode(result)), sha(rgb.tobytes()), sha(depth.tobytes())))
                trace = result["trace"]
                hits = [t for t in trace if t["contact_visibility"] is not None]
                evidence["branches"].append({"world_index": world_index, "action_index": action_index,
                    "final_object_position_m": result["future"][-1]["object_position_m"],
                    "hidden_contact_steps": len(hits), "max_contact_object_pixels": max((t["contact_visibility"]["object"] for t in hits), default=None),
                    "wall_contact_steps": sum(any(c["geoms"] == ["object", "wall"] for c in t["contacts"]) for t in trace),
                    "screen_contact_steps": sum(any(c["geoms"] == ["object", "screen"] for c in t["contacts"]) for t in trace),
                    "object_z_range_m": [min(t["object_position_m"][2] for t in trace), max(t["object_position_m"][2] for t in trace)],
                    "max_tilt_rad": max(t["object_tilt_rad"] for t in trace),
                    "max_actuator_force_n": max(abs(f) for t in trace for f in t["actuator_force_n"])})
            pair["worlds"].append(world)
            save_json(directory / f"world-{world_index}-record.json", world)
        finally:
            scene.close()
        # Fresh model and data, disk-loaded integration state, opposite order.
        replay = Scene((directory / f"world-{world_index}.xml").read_text(encoding="utf-8"), config)
        try:
            restored = json.loads((directory / f"world-{world_index}-snapshot.json").read_text())
            for action_index in (1, 0):
                print(f"SH-02 world={world_index} action={action_index} independent replay", flush=True)
                result, rgb, depth = replay.rollout(restored, actions[action_index])
                actual = (sha(encode(result)), sha(rgb.tobytes()), sha(depth.tobytes()))
                prefix = f"world-{world_index}-action-{action_index}-replay"
                save_json(directory / f"{prefix}-trace.json", result)
                np.savez_compressed(directory / f"{prefix}-sensors.npz", rgb=rgb, depth_m=depth)
                save_json(directory / f"world-{world_index}-action-{action_index}-replay.json", {"expected_hashes": originals[action_index], "actual_hashes": actual})
                evidence["replay_equal"].append(actual == originals[action_index])
        finally:
            replay.close()
    evidence["nonlayout_integration_equal"] = snapshots[0]["state"] == snapshots[1]["state"]
    evidence["final_separation_m_by_action"] = [float(np.linalg.norm(
        np.asarray(pair["worlds"][0]["branches"][a]["future"][-1]["object_position_m"])
        - np.asarray(pair["worlds"][1]["branches"][a]["future"][-1]["object_position_m"]))) for a in range(2)]
    save_json(directory / "pair.json", pair)
    save_json(directory / "evidence.json", evidence)
    return pair, evidence
