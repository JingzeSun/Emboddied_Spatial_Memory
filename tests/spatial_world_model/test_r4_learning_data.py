import unittest

from spatial_world_model import r4_learning_data as data


class LearningDataValueTests(unittest.TestCase):
    def test_registered_identity_constants(self):
        self.assertEqual(data.WORLDS, ("LL", "LR", "RL", "RR"))
        self.assertEqual(len(data.ACTIONS), 9)

    def test_bad_index_and_slot_are_rejected_before_file_access(self):
        index = {"schema_version": data.VERSION, "seals": {}}
        with self.assertRaises(ValueError):
            data.load_branch(index, "r4-39", "LL", 0, include_auxiliary_rgbd=False)
        index["seals"]["r4-39"] = {"data_root": "unused"}
        with self.assertRaises(ValueError):
            data.load_branch(index, "r4-39", "LL", 9, include_auxiliary_rgbd=False)

    def test_index_requires_external_seals(self):
        with self.assertRaises(ValueError):
            data.branch_index({"r4-39": "unused"}, {})

    def test_audit_only_names_are_not_model_fields(self):
        model_fields = ("history", "controls", "goal", "domain_spec")
        self.assertNotIn("family_id", model_fields)
        self.assertNotIn("world", model_fields)
        self.assertNotIn("action", model_fields)


if __name__ == "__main__":
    unittest.main()
