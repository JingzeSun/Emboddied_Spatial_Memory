"""Exact config construction tests for the VM-04 materializer."""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from tests.test_vm04_public_frontend import config as frontend_config  # noqa: E402
from tests.test_vm04_public_frontend_sequence import (  # noqa: E402
    bootstrap_config,
    context_bundle,
    tokens,
)
from vsmt.vm04_materializer_config import (  # noqa: E402
    build_vm04_public_frontend_sequence,
    validate_vm04_materializer_config,
)
from vsmt.vm04_public_frontend_sequence import Vm04PublicFrontendSequence  # noqa: E402


def _seal(value):
    value["config_sha256"] = hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()
    return value


def fixture():
    frontend = asdict(frontend_config())
    frontend["place"]["grid_origin_m"] = list(
        frontend["place"]["grid_origin_m"]
    )
    frontend["free_space"]["block_widths_in_tiles"] = list(
        frontend["free_space"]["block_widths_in_tiles"]
    )
    return _seal({
        "schema_version": "vsmt-vm04-materializer-config-v1",
        "status": "frozen_executable",
        "frontend": frontend,
        "bootstrap": asdict(bootstrap_config()),
        "model": {
            "model_id": "dinov2.vits14",
            "architecture": "dinov2_vits14_without_registers",
            "repository_commit": "7" * 40,
            "checkpoint_sha256": "8" * 64,
            "patch_token_output_key": "x_norm_patchtokens",
            "input_image_height": 224,
            "input_image_width": 224,
            "patch_size_pixels": 14,
            "patch_token_dimension": 4,
            "evaluation_mode": True,
            "parameters_frozen": True,
        },
        "public_constants": {
            "coordinate_frame": "map",
            "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "l1.oracle-mask.public-depth.v1",
        },
        "builder_code_sha256": "9" * 64,
    })


class Vm04MaterializerConfigTests(unittest.TestCase):
    def test_complete_sealed_config_constructs_all_typed_sections(self):
        raw = fixture()
        parsed = validate_vm04_materializer_config(raw)
        self.assertEqual(parsed.config_sha256, raw["config_sha256"])
        self.assertEqual(parsed.frontend.mask.minimum_visible_pixels, 196)
        self.assertEqual(parsed.frontend.place.grid_origin_m, (0.0, 0.0, 0.0))
        self.assertEqual(
            parsed.frontend.free_space.block_widths_in_tiles,
            (1, 2, 4, 8, 16),
        )
        self.assertEqual(parsed.bootstrap.builder_revision, "fixture.v1")
        callback, digest = build_vm04_public_frontend_sequence(
            raw,
            public_frame_context_bundle=context_bundle(),
            private_frame_roles=["old", "new"],
            patch_token_extractor=tokens,
        )
        self.assertIsInstance(callback, Vm04PublicFrontendSequence)
        self.assertEqual(digest, raw["config_sha256"])
        schema = json.loads((
            ROOT / "schemas/vsmt_vm04_materializer_config.schema.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(set(raw), set(schema["required"]))
        self.assertEqual(
            set(raw["frontend"]),
            set(schema["$defs"]["frontend"]["required"]),
        )

    def test_null_or_unsealed_scientific_section_is_rejected(self):
        raw = fixture()
        raw["bootstrap"] = None
        with self.assertRaisesRegex(ValueError, "bootstrap must contain exactly"):
            validate_vm04_materializer_config(_seal({
                key: value for key, value in raw.items()
                if key != "config_sha256"
            }))
        review = fixture()
        review["status"] = "review_template"
        with self.assertRaisesRegex(ValueError, "not frozen executable"):
            validate_vm04_materializer_config(_seal({
                key: value for key, value in review.items()
                if key != "config_sha256"
            }))

    def test_digest_extra_field_and_model_alias_are_rejected(self):
        changed = fixture()
        changed["frontend"]["mask"]["minimum_visible_pixels"] = 197
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            validate_vm04_materializer_config(changed)
        extra = fixture()
        extra["frontend"]["mask"]["private_target_id"] = "forbidden"
        extra = _seal({key: value for key, value in extra.items()
                       if key != "config_sha256"})
        with self.assertRaisesRegex(ValueError, "mask must contain exactly"):
            validate_vm04_materializer_config(extra)
        alias = deepcopy(fixture())
        alias["public_constants"]["descriptor_model_id"] = "another.model"
        alias = _seal({key: value for key, value in alias.items()
                       if key != "config_sha256"})
        with self.assertRaisesRegex(ValueError, "does not bind"):
            validate_vm04_materializer_config(alias)
        shape = fixture()
        shape["model"]["patch_token_dimension"] = 384
        shape = _seal({key: value for key, value in shape.items()
                       if key != "config_sha256"})
        with self.assertRaisesRegex(ValueError, "shape does not match"):
            validate_vm04_materializer_config(shape)


if __name__ == "__main__":
    unittest.main()
