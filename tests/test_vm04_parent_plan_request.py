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

from tests.test_vm04_observation_runner import _contract, _route  # noqa: E402
from tests.test_vm04_program_construction import memory  # noqa: E402
from vsmt.vm04_observation_runner import public_route_projection  # noqa: E402
from vsmt.vm04_parent_plan_request import (  # noqa: E402
    ParentPlanRequestError,
    derive_parent_online_program_plan_request,
    make_parent_program_request_spec,
    validate_parent_online_program_plan_request,
)


MATCHER_SHA = "b" * 64
CODE_SHA = "c" * 64


def selectors(program):
    return {
        "NOOP": {"current_observation_rule_sha256": "1" * 64},
        "BIND": {
            "open_node_id": "entity-a", "prior_evidence_sha256": "1" * 64,
            "current_region_selection_rule_sha256": "2" * 64,
        },
        "BIRTH": {"absence_scope_sha256": "1" * 64},
        "REACTIVATE": {
            "dormant_node_id": "entity-d", "prior_evidence_sha256": "1" * 64,
        },
        "RELINK": {
            "entity_node_id": "entity-a", "old_place_node_id": "place-a",
            "new_place_public_ref": "place-public:P2",
        },
        "RETRACT": {
            "entity_node_id": "entity-a", "prior_evidence_sha256": "1" * 64,
            "absence_rule_sha256": "2" * 64,
        },
        "SPLIT": {
            "undersegmented_node_id": "entity-a", "artifact_plan_sha256": "3" * 64,
        },
        "MERGE": {
            "first_node_id": "entity-a", "second_node_id": "entity-b",
            "artifact_plan_sha256": "4" * 64,
        },
        "REPLACE": {
            "old_entity_node_id": "entity-a",
            "new_identity_absence_scope_sha256": "5" * 64,
        },
    }[program]


def inputs(program):
    route = public_route_projection(_route(program), contract=_contract())
    spec = make_parent_program_request_spec(
        public_route=route, family_id="family:001", program=program,
        selector_inputs=selectors(program), matcher_config_sha256=MATCHER_SHA,
    )
    return route, spec


class ParentPlanRequestTests(unittest.TestCase):
    def test_all_nine_programs_derive_version_refs_from_public_memory(self):
        graph = memory()
        for program in (
            "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
            "SPLIT", "MERGE", "REPLACE",
        ):
            with self.subTest(program=program):
                route, spec = inputs(program)
                result = derive_parent_online_program_plan_request(
                    spec=spec, public_route=route, prior_memory=graph,
                    last_completed_observation_index=4,
                    parent_stage_code_sha256=CODE_SHA,
                )
                receipt = result["provenance_receipt"]
                self.assertTrue(receipt[
                    "precondition_refs_derived_deterministically_from_public_memory"
                ])
                self.assertFalse(receipt["caller_supplied_precondition_refs_used"])
                self.assertFalse(receipt[
                    "episode_root_or_raw_path_argument_available"
                ])
                self.assertFalse(receipt[
                    "terminal_public_or_private_frame_opened"
                ])
                self.assertTrue(receipt[
                    "request_provenance_established_by_parent_core"
                ])
                self.assertFalse(receipt[
                    "selector_spec_pre_terminal_registration_established"
                ])
                self.assertFalse(receipt["consumed_by_D202_temporal_receipt"])
                self.assertFalse(receipt["clears_D201_temporal_seal_pending"])
                self.assertEqual(validate_parent_online_program_plan_request(
                    result, spec=spec, public_route=route, prior_memory=graph,
                    parent_stage_code_sha256=CODE_SHA,
                ), result)

    def test_relink_is_derived_from_unique_open_public_edge(self):
        route, spec = inputs("RELINK")
        result = derive_parent_online_program_plan_request(
            spec=spec, public_route=route, prior_memory=memory(),
            last_completed_observation_index=4,
            parent_stage_code_sha256=CODE_SHA,
        )
        refs = result["online_request"]["precondition_refs"]
        self.assertEqual(refs["open_entity_node_version_id"], "entity-a@v0")
        self.assertEqual(refs["old_place_node_version_id"], "place-a@v0")
        self.assertEqual(refs["old_located_at_edge_version_id"],
                         "edge:located@v0")

    def test_caller_version_ids_wrong_boundary_and_tamper_are_rejected(self):
        route, spec = inputs("BIND")
        changed = copy.deepcopy(spec)
        changed["selector_inputs"] = {
            "open_node_version_id": "entity-a@v0",
            "prior_evidence_sha256": "1" * 64,
            "current_region_selection_rule_sha256": "2" * 64,
        }
        with self.assertRaisesRegex(
                ParentPlanRequestError, "selector inputs"):
            make_parent_program_request_spec(
                public_route=route, family_id="family:001", program="BIND",
                selector_inputs=changed["selector_inputs"],
                matcher_config_sha256=MATCHER_SHA,
            )
        with self.assertRaisesRegex(
                ParentPlanRequestError, "immediately before terminal"):
            derive_parent_online_program_plan_request(
                spec=spec, public_route=route, prior_memory=memory(),
                last_completed_observation_index=3,
                parent_stage_code_sha256=CODE_SHA,
            )
        result = derive_parent_online_program_plan_request(
            spec=spec, public_route=route, prior_memory=memory(),
            last_completed_observation_index=4,
            parent_stage_code_sha256=CODE_SHA,
        )
        result["provenance_receipt"]["terminal_public_or_private_frame_opened"] = True
        with self.assertRaises(ParentPlanRequestError):
            validate_parent_online_program_plan_request(
                result, spec=spec, public_route=route, prior_memory=memory(),
                parent_stage_code_sha256=CODE_SHA,
            )

    def test_schema_accepts_spec_and_receipt(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is unavailable")
        route, spec = inputs("BIRTH")
        result = derive_parent_online_program_plan_request(
            spec=spec, public_route=route, prior_memory=memory(),
            last_completed_observation_index=4,
            parent_stage_code_sha256=CODE_SHA,
        )
        schema = json.loads((
            ROOT / "schemas/vsmt_vm04_parent_program_request.schema.json"
        ).read_text(encoding="utf-8"))
        jsonschema.validate(spec, schema)
        jsonschema.validate(result["provenance_receipt"], schema)


if __name__ == "__main__":
    unittest.main()
