"""Exact config construction tests for the VM-04 materializer."""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
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
    load_verified_dinov2,
    validate_vm04_materializer_assets_receipt,
    validate_vm04_materializer_config,
    verify_vm04_materializer_assets,
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


def asset_receipt(raw):
    receipt = {
        "schema_version": "vsmt-vm04-materializer-assets-receipt-v1",
        "materializer_config_sha256": raw["config_sha256"],
        "model_id": raw["model"]["model_id"],
        "repository_commit": raw["model"]["repository_commit"],
        "repository_worktree_clean": True,
        "checkpoint_sha256": raw["model"]["checkpoint_sha256"],
        "network_access_required": False,
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        canonical_json(receipt).encode("utf-8")
    ).hexdigest()
    return receipt


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

    def test_model_repository_and_checkpoint_are_verified_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "dinov2"
            repository.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "fixture@example.invalid"],
                cwd=repository, check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Fixture"],
                cwd=repository, check=True,
            )
            (repository / "model.py").write_text("MODEL = 'v1'\n", encoding="utf-8")
            subprocess.run(["git", "add", "model.py"], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "fixture"],
                cwd=repository, check=True,
            )
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            checkpoint = root / "model.pth"
            checkpoint.write_bytes(b"sealed checkpoint fixture")
            checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            raw = fixture()
            raw["model"]["repository_commit"] = commit
            raw["model"]["checkpoint_sha256"] = checkpoint_sha
            raw = _seal({key: value for key, value in raw.items()
                         if key != "config_sha256"})
            parsed = validate_vm04_materializer_config(raw)
            receipt = verify_vm04_materializer_assets(
                parsed, repository_root=repository,
                checkpoint_path=checkpoint,
            )
            self.assertTrue(receipt["repository_worktree_clean"])
            self.assertFalse(receipt["network_access_required"])
            self.assertEqual(
                validate_vm04_materializer_assets_receipt(
                    receipt, parsed=parsed,
                ),
                receipt,
            )
            schema = json.loads((ROOT / (
                "schemas/vsmt_vm04_materializer_assets_receipt.schema.json"
            )).read_text(encoding="utf-8"))
            self.assertEqual(set(receipt), set(schema["required"]))
            class Parameter:
                requires_grad = True

            class Model:
                def __init__(self):
                    self.training = True
                    self.parameter = Parameter()
                    self.device = None
                    self.strict = None

                def load_state_dict(self, state, strict):
                    self.strict = strict
                    self.state = state

                def requires_grad_(self, value):
                    self.parameter.requires_grad = value
                    return self

                def eval(self):
                    self.training = False
                    return self

                def to(self, device):
                    self.device = device
                    return self

                def parameters(self):
                    return [self.parameter]

            class Cuda:
                @staticmethod
                def is_available():
                    return True

            class Torch:
                cuda = Cuda()

                @staticmethod
                def load(path, *, map_location, weights_only):
                    self.assertEqual(Path(path), checkpoint)
                    self.assertEqual(map_location, "cpu")
                    self.assertTrue(weights_only)
                    return {"sealed": "state"}

            def factory(*, pretrained):
                self.assertFalse(pretrained)
                return Model()

            model, loaded_assets = load_verified_dinov2(
                parsed,
                repository_root=repository,
                checkpoint_path=checkpoint,
                model_factory=factory,
                torch_module=Torch,
            )
            self.assertEqual(loaded_assets, receipt)
            self.assertTrue(model.strict)
            self.assertEqual(model.device, "cuda")
            self.assertFalse(model.training)
            self.assertFalse(model.parameter.requires_grad)
            changed = deepcopy(receipt)
            changed["checkpoint_sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "different config or model"):
                validate_vm04_materializer_assets_receipt(
                    changed, parsed=parsed,
                )
            (repository / "model.py").write_text("MODEL = 'changed'\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "worktree is not clean"):
                verify_vm04_materializer_assets(
                    parsed, repository_root=repository,
                    checkpoint_path=checkpoint,
                )


if __name__ == "__main__":
    unittest.main()
