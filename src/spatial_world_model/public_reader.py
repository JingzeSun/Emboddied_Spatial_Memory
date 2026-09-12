"""Read one digest-bound R2 public file and return only a numerical query.

No directory discovery, private result loading, model, or simulator. This is an
input API boundary, not an operating-system sandbox. See docs/DATA.md.
"""
import hashlib
import json
from pathlib import Path

from .pair_contract import digest, require
from .two_gate_contract import model_input


MAX_PUBLIC_BYTES = 32 * 1024 * 1024


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON field")
        value[key] = item
    return value


def _invalid_constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def load_query(public_path, *, expected_sha256, expected_bytes, action_name,
               history_indices=None):
    """Verify exact file bytes, validate ALL frames, then select a query.

    The caller supplies a trusted manifest entry separately. Neither the path,
    digest, action name, nor history selector is included in the returned dict.
    The reader does not find or open receipts, labels, XML, or adjacent files.
    """
    digest(expected_sha256, "public file")
    require(type(expected_bytes) is int and 0 < expected_bytes <= MAX_PUBLIC_BYTES,
            "public file size outside reader limit")
    path = Path(public_path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)),
            "symlink public path is not supported")
    require(path.is_file(), "explicit regular public file required")
    with path.open("rb") as handle:
        raw = handle.read(expected_bytes + 1)
    require(len(raw) == expected_bytes, "public file byte count differs from manifest")
    require(hashlib.sha256(raw).hexdigest() == expected_sha256,
            "public file digest differs from manifest")
    public = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                        parse_constant=_invalid_constant)
    return model_input(public, action_name, history_indices)
