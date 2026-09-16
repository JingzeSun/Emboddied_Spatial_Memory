from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import seal_graph  # noqa: E402
from tests.test_vm04_observation_runner import _route  # noqa: E402
from tests.test_vsmt_public_candidates import graph_fixture  # noqa: E402
from vsmt.vm04_online_plan_seal import (  # noqa: E402
    OnlineProgramPlanSealError,
    make_online_program_plan_request,
    seal_online_program_construction_plan,
    validate_online_program_plan_seal,
)


CODE_SHA = "c" * 64
MATCHER_SHA = "b" * 64


def memory():
    value = graph_fixture()
    return seal_graph({
        **{key: item for key, item in value.items() if key != "graph_hash"},
        "nodes": [
            node for node in value["nodes"]
            if node["node_id"] not in {"entity-a", "entity-b", "entity-d"}
        ],
        "edges": [],
    })


def request(route):
    return make_online_program_plan_request(
        episode_id=route["episode_id"], family_id="family:001",
        program="BIRTH", route_plan_sha256=route["route_plan_sha256"],
        terminal_observation_index=route["terminal_reobservation_indices"][-1],
        precondition_refs={
            "reveal_locus_public_ref": "locus:001",
            "absence_scope_sha256": "d" * 64,
        },
        visibility_subject_seal_sha256=
            route["visibility_subject_seal_sha256"],
        matcher_config_sha256=MATCHER_SHA,
    )


class OnlineProgramPlanSealTests(unittest.TestCase):
    def test_seal_binds_prior_immediately_before_terminal(self):
        route = _route("BIRTH")
        prior = memory()
        registered = request(route)
        result = seal_online_program_construction_plan(
            request=registered, route_plan=route, prior_memory=prior,
            last_completed_observation_index=
                route["terminal_reobservation_indices"][-1] - 1,
            materializer_code_sha256=CODE_SHA,
        )
        receipt = result["temporal_receipt"]
        self.assertEqual(receipt["matcher_prior_memory_sha256"],
                         prior["graph_hash"])
        self.assertFalse(receipt["terminal_public_frame_opened_before_seal"])
        self.assertFalse(receipt["terminal_private_frame_opened_before_seal"])
        self.assertFalse(receipt[
            "request_provenance_established_by_parent_stage"
        ])
        self.assertFalse(receipt["clears_episode_temporal_seal_pending"])
        self.assertEqual(validate_online_program_plan_seal(
            result, request=registered, route_plan=route,
            materializer_code_sha256=CODE_SHA,
        ), result)

    def test_wrong_boundary_or_tampered_receipt_is_rejected(self):
        route = _route("BIRTH")
        registered = request(route)
        with self.assertRaisesRegex(
                OnlineProgramPlanSealError, "immediately before terminal"):
            seal_online_program_construction_plan(
                request=registered, route_plan=route, prior_memory=memory(),
                last_completed_observation_index=0,
                materializer_code_sha256=CODE_SHA,
            )
        result = seal_online_program_construction_plan(
            request=registered, route_plan=route, prior_memory=memory(),
            last_completed_observation_index=
                route["terminal_reobservation_indices"][-1] - 1,
            materializer_code_sha256=CODE_SHA,
        )
        changed = copy.deepcopy(result)
        changed["temporal_receipt"][
            "terminal_public_frame_opened_before_seal"
        ] = True
        with self.assertRaises(OnlineProgramPlanSealError):
            validate_online_program_plan_seal(
                changed, request=registered, route_plan=route,
                materializer_code_sha256=CODE_SHA,
            )

    def test_schema_accepts_request_and_receipt(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is unavailable")
        route = _route("BIRTH")
        registered = request(route)
        result = seal_online_program_construction_plan(
            request=registered, route_plan=route, prior_memory=memory(),
            last_completed_observation_index=
                route["terminal_reobservation_indices"][-1] - 1,
            materializer_code_sha256=CODE_SHA,
        )
        schema = json.loads((
            ROOT / "schemas/vsmt_vm04_online_program_plan_seal.schema.json"
        ).read_text(encoding="utf-8"))
        jsonschema.validate(registered, schema)
        jsonschema.validate(result["temporal_receipt"], schema)


if __name__ == "__main__":
    unittest.main()
