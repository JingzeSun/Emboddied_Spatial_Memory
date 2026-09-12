"""Server-only synthetic input boundary checks; no physics or learning."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spatial_world_model.public_reader import MAX_PUBLIC_BYTES, load_query
from spatial_world_model.two_gate_contract import make_public, model_input
from test_two_gate_contract import configuration, history


class PublicReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "public.json"
        self.public = make_public(history(), configuration())
        self.save(self.public)

    def save(self, value):
        self.raw = json.dumps(value, allow_nan=False).encode()
        self.path.write_bytes(self.raw)

    def query(self, **kwargs):
        args = dict(expected_sha256=hashlib.sha256(self.raw).hexdigest(),
                    expected_bytes=len(self.raw), action_name="LR")
        args.update(kwargs)
        return load_query(self.path, **args)

    def test_matches_reviewed_contract_and_returns_no_provenance(self):
        for action in ("LL", "LR", "RL", "RR"):
            for indices in (None, [25, 65, 119, 120], [119, 120]):
                with self.subTest(action=action, indices=indices):
                    q = self.query(action_name=action, history_indices=indices)
                    self.assertEqual(q, model_input(self.public, action, indices))
                    self.assertEqual(set(q), {"history", "controls", "goal"})
                    self.assertEqual(len(q["controls"]), 200)

    def test_missing_or_wrong_manifest_never_accepts_file(self):
        for override in ({"expected_sha256": "0" * 64}, {"expected_sha256": "bad"},
                         {"expected_bytes": len(self.raw) - 1},
                         {"expected_bytes": len(self.raw) + 1}, {"expected_bytes": True},
                         {"expected_bytes": MAX_PUBLIC_BYTES + 1}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.query(**override)

    def test_mutated_bytes_rejected_even_if_json_remains_valid(self):
        self.path.write_bytes(self.raw + b" ")
        with self.assertRaises(ValueError):
            self.query()

    def test_private_top_level_fields_rejected_with_matching_digest(self):
        for name in ("world", "layout_truth", "snapshots", "future", "task_outcomes"):
            value = deepcopy(self.public)
            value[name] = {}
            self.save(value)
            with self.subTest(field=name), self.assertRaises(ValueError):
                self.query(history_indices=[119, 120])

    def test_unselected_frame_and_control_contamination_rejected(self):
        value = deepcopy(self.public)
        value["history"][0]["future_object_position_m"] = [0, 0, 0]
        self.save(value)
        with self.assertRaises(ValueError):
            self.query(history_indices=[119, 120])
        value = deepcopy(self.public)
        value["actions"]["RR"][0]["actual_robot_motion"] = [0, 0, 0]
        self.save(value)
        with self.assertRaises(ValueError):
            self.query(action_name="LL")

    def test_duplicate_top_level_and_nested_json_fields_rejected(self):
        for old, new in ((b'"schema_version":', b'"schema_version": "ignored", "schema_version":'),
                         (b'"time_s":', b'"time_s": 99, "time_s":')):
            self.raw = json.dumps(self.public).encode().replace(old, new, 1)
            self.path.write_bytes(self.raw)
            with self.subTest(field=old), self.assertRaises(ValueError):
                self.query()

    def test_nonfinite_or_future_public_value_rejected(self):
        for token in (b"NaN", b"Infinity", b"1e999", b"99.0"):
            self.raw = json.dumps(self.public).encode().replace(b'"time_s": 0.5', b'"time_s": ' + token, 1)
            self.path.write_bytes(self.raw)
            with self.subTest(token=token), self.assertRaises(ValueError):
                self.query(history_indices=[119, 120])

    def test_selector_errors_do_not_silently_change_history(self):
        for indices in ([True], [], [121], [65, 25], [25, 25]):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                self.query(history_indices=indices)
        with self.assertRaises(ValueError):
            self.query(action_name=0)

    def test_only_explicit_public_file_is_opened(self):
        original = Path.open
        opened = []

        def guarded(path, *args, **kwargs):
            self.assertEqual(path, self.path)
            self.assertEqual(args, ("rb",))
            opened.append(path)
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", guarded):
            self.query()
        self.assertEqual(opened, [self.path])

    def test_neighbor_labels_and_path_names_do_not_enter_query(self):
        before = self.query()
        for name in ("snapshot.json", "world.xml", "result.json"):
            self.path.with_name(name).write_text("private answer changed", encoding="utf-8")
        self.assertEqual(before, self.query())
        self.path = self.path.with_name("unrelated-name.json")
        self.path.write_bytes(self.raw)
        self.assertEqual(before, self.query())

    def test_symlink_file_and_parent_rejected(self):
        link = self.path.with_name("link.json")
        link.symlink_to(self.path)
        original = self.path
        self.path = link
        with self.assertRaises(ValueError):
            self.query()
        folder = original.parent / "linked-directory"
        folder.symlink_to(original.parent, target_is_directory=True)
        self.path = folder / original.name
        with self.assertRaises(ValueError):
            self.query()

    def test_query_mutation_does_not_change_later_read(self):
        query = self.query()
        query["history"][0]["rgb"][0] = 255
        query["controls"][0]["ee_velocity_mps"][0] = 99
        self.assertEqual(self.query(), model_input(self.public, "LR"))
