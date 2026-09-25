"""D-224 / S2-05 tests: the run-pass entry runs each pass at its registered arm and configuration (ruling 68).

Pinned: the calibration pass is LOW only; the fit pass is TAF at the ELU-P rollout theta_a with no
gate; DAgger round 0 is ELU-P at the rollout_config plus the registered fitted quantities (null while
the fit pass has not run); round 1 and the development table run the learned arms and the rule arms
at the S2-05 development configurations; an arm outside a pass and a differing configuration are what
the entry refuses.  CPU only, seconds after the import.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_development as entry  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_development as dev  # noqa: E402


class TestRegisteredPassConfigurations(unittest.TestCase):
    def test_each_pass_names_its_arms(self):
        self.assertEqual(entry.PASS_ARMS["calibration"], ("LOW",))
        self.assertEqual(entry.PASS_ARMS["elu_p_fit"], ("TAF",))
        self.assertEqual(entry.PASS_ARMS["dagger_round_0"], ("ELU-P",))
        self.assertEqual(entry.PASS_ARMS["dagger_round_1"], ("VSMT-lean", "AssocOnly"))
        self.assertEqual(set(entry.PASS_ARMS["development_table"]), set(dev.DEVELOPMENT_ARMS) - {"ELU-P"})
        self.assertEqual(set(entry.PASS_ARMS), set(dev.PASSES))

    def test_the_fit_and_round_0_configurations_come_from_the_rollout_config(self):
        self.assertEqual(entry.expected_pass_config("elu_p_fit", "TAF"), {"theta_a": arms.ROLLOUT_CONFIG["theta_a"], "d_a": None})
        round_0 = entry.expected_pass_config("dagger_round_0", "ELU-P")
        self.assertEqual({name: round_0[name] for name in arms.ROLLOUT_CONFIG_PARAMETERS}, arms.ROLLOUT_CONFIG)
        self.assertIsNone(round_0["d_a"])
        self.assertEqual(set(round_0), set(arms.GRID_PARAMETERS["ELU-P"]) | set(arms.ELU_P_FITTED))
        # the fitted quantities are whatever S0-05 registers: null until the fit pass lands them
        fitted = entry.load_json(entry.S0_05_CONTRACT)["arms"]["ELU-P"]["fitted"]
        self.assertEqual({name: round_0[name] for name in arms.ELU_P_FITTED}, fitted)

    def test_round_1_and_the_table_use_the_development_configurations(self):
        for pass_name in ("dagger_round_1", "development_table"):
            for arm, config in dev.DEVELOPMENT_CONFIGURATIONS.items():
                with self.subTest(pass_name=pass_name, arm=arm):
                    self.assertEqual(entry.expected_pass_config(pass_name, arm), config)
        self.assertIsNone(entry.expected_pass_config("calibration", "LOW"))  # the calibration check is its own rule
        self.assertIsNone(entry.expected_pass_config("elu_p_fit", "LOW"))


if __name__ == "__main__":
    unittest.main()
