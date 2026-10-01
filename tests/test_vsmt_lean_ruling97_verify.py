"""D-224 / S2-R tests: the ruling 97 (a) check of the frozen confirmation inputs, on a temporary tree.

Head files whose digests equal the frozen ones, the registered rule-arm configurations, an unchanged house list and the expected
number of houses with episode, cache and geometry directories pass (exit 0) and yield the group plan and the episode list; a head
with a different digest, a changed house list or a missing cache directory each fail the check (exit 3).  CPU only.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    sys.path.insert(0, str(item))

import lean_s2_05_development as dev  # noqa: E402
import ruling97_verify as verify  # noqa: E402
from vsmt import lean_model as model  # noqa: E402

HOUSES = ["h-a", "h-b", "h-c"]


def build(tmp: Path, *, wrong_digest: bool = False, changed_list: bool = False, drop_cache: str | None = None) -> list[str]:
    autodl, repo = tmp / "autodl", tmp / "repo"
    payloads = {}
    for group, assoc_only, seed in (("GROUPED", False, 1), ("ASSOC", True, 2)):
        payload = model.weights_payload(model.make_heads(assoc_only=assoc_only, seed=seed), training={})
        path = autodl / "heads" / f"{group}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        payloads[group] = payload["sha256"]
    for root in ("episodes", "cache", "geometry"):
        for house in HOUSES:
            if not (root == "cache" and house == drop_cache):
                (autodl / root / house).mkdir(parents=True, exist_ok=True)
    (repo / "list.json").parent.mkdir(parents=True, exist_ok=True)
    (repo / "list.json").write_text(json.dumps({"houses": HOUSES, "houses_sha256": "abc"}), encoding="utf-8")
    freeze = {"confirmation_houses": {"file": "list.json", "houses_sha256": "abd" if changed_list else "abc", "expected_evaluated": 3},
              "data_roots": {"episodes": "episodes", "cache": "cache", "geometry": "geometry"},
              "arms": {"grouped": {"arm": "VSMT-lean", "config": {"tau_r": 0.5}, "group": "GROUPED",
                                   "heads": {"7": {"path": "heads/GROUPED.json", "sha256": "0" * 64 if wrong_digest else payloads["GROUPED"]}}},
                       "assoc": {"arm": "AssocOnly", "config": {}, "group": "ASSOC",
                                 "heads": {"7": {"path": "heads/ASSOC.json", "sha256": payloads["ASSOC"]}}},
                       "rule arms": {"RAC": dev.expected_pass_config("development_table", "RAC"),
                                     "ELU-P": dev.expected_pass_config("dagger_round_0", "ELU-P")}}}
    (tmp / "freeze.json").write_text(json.dumps(freeze), encoding="utf-8")
    return ["--freeze", str(tmp / "freeze.json"), "--autodl-root", str(autodl), "--repo-root", str(repo),
            "--plan", str(tmp / "plan.tsv"), "--episodes", str(tmp / "episodes.txt"), "--output", str(tmp / "out.json")]


class Ruling97VerifyTests(unittest.TestCase):
    def run_verify(self, **kwargs):
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            code = verify.main(build(tmp, **kwargs))
            out = json.loads((tmp / "out.json").read_text(encoding="utf-8"))
            plan = (tmp / "plan.tsv").read_text(encoding="utf-8").splitlines()
            episodes = (tmp / "episodes.txt").read_text(encoding="utf-8").split()
            return code, out, plan, episodes

    def test_frozen_inputs_pass_and_yield_the_plan_and_the_episodes(self) -> None:
        code, out, plan, episodes = self.run_verify()
        self.assertEqual(code, 0)
        self.assertEqual(out["problems"], [])
        self.assertEqual(episodes, HOUSES)
        self.assertEqual([row.split("\t")[0] for row in plan], ["GROUPED-A7", "ASSOC-A7", "RULE-RAC", "RULE-ELU-P"])
        rac = plan[2].split("\t")
        self.assertEqual(json.loads(rac[2]), {"theta_a": 0.7, "d_a": None, "rho_rac": 0.7, "n_rac": 3})
        self.assertEqual(rac[3], "")

    def test_a_different_digest_a_changed_list_or_a_missing_cache_each_fail(self) -> None:
        for kwargs, problem in (({"wrong_digest": True}, "digest_differs:GROUPED-A7"), ({"changed_list": True}, "confirmation_list_changed"),
                                ({"drop_cache": "h-b"}, "evaluated_episodes:2_expected:3")):
            code, out, _, episodes = self.run_verify(**kwargs)
            self.assertEqual(code, 3, kwargs)
            self.assertIn(problem, out["problems"])
        self.assertEqual(episodes, ["h-a", "h-c"])
        self.assertEqual(out["missing_houses"], ["h-b"])


if __name__ == "__main__":
    unittest.main()
