"""D-224 / S1-02a: read-only checks for the four-worker pilot.

S1-02a exists because of a circularity.  S1-01 requires the worker count
to be derived from measured single-worker occupancy, and those numbers can
only be read off a real episode run, which S1-01 is not allowed to do
(D-224-S1 ruling 14).  The pilot breaks it: four workers take one house
each, the pipeline runs end to end, and the occupancy those four runs
expose feeds the S1-01 formula so S1-02b can scale to the remaining
houses.

This module holds the rules that decide whether such a pilot is
admissible and whether its measured occupancy may be used for the
derivation.  It starts no simulator, generates no episode, writes no data
plane, reads no private file and imports nothing heavier than the two
modules it deliberately reuses.  Passing its checks does not show that the
pilot runs.

Beyond the pilot, ``train_block`` fixes the train-block order the S1-02
generator (``ops/vsmt/lean_s1_02a_pilot.py``) uses for the development
houses (positions 0-49) and the ruling-81 confirmation set (positions
50-99).  ``lean_s3_manifests`` derives the S3-01 lists from the same
``split_freeze`` with the same ``assign_split`` (it does not call this
module), so its S3 train positions 100-399 continue that order.

Four rules carry the S1-02a continue gate:

1. **The split is frozen before the first episode.**  S0-02 v2 allocates
   test, then validation, then train, so the seed and the test/validation
   sizes fix where the train block starts.  Choosing them after seeing a
   result would move every development house.
2. **The pilot houses are recomputed, never chosen.**  They are the head
   of the train block under the registered split, and this module rebuilds
   that head with S0-02's own ``assign_split`` rather than a second copy.
3. **The four pilot episodes count towards the fifty.**  Generating them,
   looking at the result and regenerating the same houses would be
   selecting samples on their outcome, so it is refused.
4. **Occupancy is complete, peak and measured under the real workload**
   before anything is derived from it, and the concurrency it was verified
   at is recorded separately from whatever count comes out.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from cpmt.hashing import clone_json
from vsmt.lean_assets import derive_worker_count
from vsmt.lean_intervention import FAILURE_REASONS, assign_split


CONTRACT_SCHEMA_VERSION = "vsmt-lean-s1-02a-pilot-v2"

#: The pilot shape the user fixed: four workers, one house each.
PILOT_WORKERS = 4
PILOT_HOUSES_PER_WORKER = 1
PILOT_TOTAL_HOUSES = PILOT_WORKERS * PILOT_HOUSES_PER_WORKER

#: The split parameters that must be frozen before the first episode.
#: ``train_houses`` may still be open here: it was designed to be registered
#: at S3-01 and to only ever decrease, which trims the tail of the train
#: block and moves no house in test or validation.  S3-01 left it null:
#: ruling 102-8 takes train positions 100-399 instead (``lean_s3_manifests``).
SPLIT_FREEZE_FIELDS = ("seed", "validation_houses", "test_houses", "train_houses")
FROZEN_BEFORE_GENERATION = ("seed", "validation_houses", "test_houses")

#: What a pilot run must report.
PILOT_RECEIPT_FIELDS = (
    "split_seed", "split_sizes", "selected_house_ids", "planned", "succeeded",
    "failed", "failure_receipts", "wall_clock_seconds", "exit_codes",
    "code_commit",
)

#: What the occupancy measurement must report.  The first five feed the
#: S1-01 derivation; the rest say how they were obtained.
OCCUPANCY_RECEIPT_FIELDS = (
    "concurrency_verified_at", "cpu_cores_per_worker", "ram_gb_per_worker",
    "vram_gb_per_worker", "disk_gb_per_worker", "simulator_concurrency_limit",
    "statistic", "workload", "failures",
)

#: Peak, not average: a worker count provisioned from averages runs out of
#: memory at the peak.
REQUIRED_STATISTIC = "peak_not_average"

#: A full episode, not a synthetic micro-benchmark: simulator start and
#: rendering dominate, and a micro-benchmark would miss both.
REQUIRED_WORKLOAD = "a_full_episode_including_three_plane_write"

#: Bits that stay closed whatever else is opened.
MUST_REMAIN_FALSE = (
    "sample_replacement_on_failure",
    "regeneration_after_inspection",
    "house_selection_by_hand",
    "private_plane_read_for_selection",
    "test_split_read",
    "frontend_cache_generation",
    "reid_adapter_head_training",
    "model_training",
    "route_template_change_after_first_episode",
)


class LeanPilotError(ValueError):
    """Raised for any inadmissible split freeze, pilot plan or receipt."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanPilotError(code)


def _int(value: Any, code: str, *, minimum: int | None = None) -> int:
    _require(type(value) is int and type(value) is not bool, code)
    if minimum is not None:
        _require(value >= minimum, code)
    return value


def _number(value: Any, code: str, *, minimum: float | None = None) -> float:
    _require(type(value) in (int, float) and type(value) is not bool, code)
    if minimum is not None:
        _require(float(value) >= minimum, code)
    return float(value)


# --------------------------------------------------------------------------
# the split freeze
# --------------------------------------------------------------------------

def validate_split_freeze(freeze: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the split parameters are frozen tightly enough to generate.

    Returns a copy and refuses a seed or test/validation size that is still
    null, negative or not an integer (e.g. a first episode before the seed is
    fixed).  ``train_houses`` may stay null: it was left for S3-01 and may only
    decrease once set (S3-01 kept it null, ruling 102-8).  Whether the pool
    holds enough houses is checked by ``select_pilot_houses``.
    """

    _require(type(freeze) is dict, "split_freeze_not_object")
    missing = sorted(set(SPLIT_FREEZE_FIELDS) - set(freeze.keys()))
    _require(not missing, f"split_freeze_missing:{','.join(missing)}")
    for name in FROZEN_BEFORE_GENERATION:
        _require(freeze[name] is not None, f"split_freeze_still_open:{name}")
    _int(freeze["seed"], "split_seed_invalid", minimum=0)
    _int(freeze["validation_houses"], "validation_size_invalid", minimum=1)
    _int(freeze["test_houses"], "test_size_invalid", minimum=1)
    if freeze["train_houses"] is not None:
        _int(freeze["train_houses"], "train_size_invalid", minimum=PILOT_TOTAL_HOUSES)
    return clone_json(dict(freeze))


def train_block(house_ids: Sequence[str], freeze: Mapping[str, Any]) -> list[str]:
    """Return the train block under the registered split, in split order.

    Changing the seed or a test/validation size moves the start of this list,
    which is why they are frozen first.  It calls S0-02's ``assign_split``
    rather than a second split implementation.
    """

    checked = validate_split_freeze(freeze)
    train = checked["train_houses"]
    if train is None:
        # While it is null (S3-01 kept it null, ruling 102-8), the train block
        # is simply everything the test and validation blocks did not take.
        train = len(house_ids) - checked["validation_houses"] - checked["test_houses"]
        _require(train >= PILOT_TOTAL_HOUSES, "house_pool_too_small_for_the_pilot")
    split = assign_split(
        list(house_ids),
        seed=checked["seed"],
        train=train,
        validation=checked["validation_houses"],
        test=checked["test_houses"],
    )
    return list(split["train"])


def select_pilot_houses(
    house_ids: Sequence[str], freeze: Mapping[str, Any],
) -> list[str]:
    """Return the four pilot houses: the head of the train block.

    The houses are not chosen: the same pool and parameters give the same four
    on every machine, and a swapped house is caught by the recomputation.
    Whether they load is not checked.
    """

    block = train_block(house_ids, freeze)
    _require(len(block) >= PILOT_TOTAL_HOUSES, "train_block_too_small_for_the_pilot")
    return block[:PILOT_TOTAL_HOUSES]


# --------------------------------------------------------------------------
# the pilot plan and its receipt
# --------------------------------------------------------------------------

def validate_pilot_plan(
    plan: Mapping[str, Any], house_ids: Sequence[str], freeze: Mapping[str, Any],
) -> dict[str, Any]:
    """Check a pilot plan against the recomputed selection.

    Returns a copy and refuses a worker count other than 4, other than one
    house per worker, duplicate houses, or houses that differ from the
    recomputation (e.g. the fourth house swapped for a "cleaner-looking" one).
    """

    _require(type(plan) is dict, "pilot_plan_not_object")
    _require(plan.get("workers") == PILOT_WORKERS, "pilot_worker_count_changed")
    _require(plan.get("houses_per_worker") == PILOT_HOUSES_PER_WORKER,
             "pilot_houses_per_worker_changed")
    houses = plan.get("house_ids")
    _require(type(houses) is list, "pilot_house_ids_invalid")
    _require(len(houses) == PILOT_TOTAL_HOUSES, "pilot_house_count_changed")
    _require(len(set(houses)) == len(houses), "pilot_house_ids_duplicated")
    _require(list(houses) == select_pilot_houses(house_ids, freeze),
             "pilot_houses_do_not_match_the_recomputed_head")
    return clone_json(dict(plan))


def validate_pilot_receipt(
    receipt: Mapping[str, Any],
    *,
    already_generated: Sequence[str] = (),
) -> dict[str, Any]:
    """Check a pilot run receipt and refuse a regeneration.

    Returns a copy and refuses missing fields, planned != succeeded + failed, a
    failure-receipt count that does not match, an unregistered failure reason,
    or a house in ``already_generated`` (a regeneration).  E.g. 4 planned, 3
    succeeded and no failure receipt means one episode was silently dropped.
    """

    _require(type(receipt) is dict, "pilot_receipt_not_object")
    _require(tuple(receipt.keys()) == PILOT_RECEIPT_FIELDS,
             "pilot_receipt_fields_mismatch")
    planned = _int(receipt["planned"], "pilot_planned_invalid", minimum=0)
    succeeded = _int(receipt["succeeded"], "pilot_succeeded_invalid", minimum=0)
    failed = _int(receipt["failed"], "pilot_failed_invalid", minimum=0)
    _require(planned == PILOT_TOTAL_HOUSES, "pilot_planned_is_not_four")
    _require(planned == succeeded + failed, "pilot_planned_not_equal_to_outcomes")

    failure_receipts = receipt["failure_receipts"]
    _require(type(failure_receipts) is list, "pilot_failure_receipts_invalid")
    _require(len(failure_receipts) == failed, "pilot_failure_receipt_count_mismatch")
    for failure in failure_receipts:
        _require(failure.get("reason") in FAILURE_REASONS, "pilot_failure_reason_unknown")
        _require(failure.get("house_id") in receipt["selected_house_ids"],
                 "pilot_failure_names_an_unselected_house")

    repeated = sorted(set(receipt["selected_house_ids"]) & set(already_generated))
    _require(not repeated, f"pilot_regenerates_an_existing_house:{','.join(repeated)}")
    return clone_json(dict(receipt))


# --------------------------------------------------------------------------
# occupancy
# --------------------------------------------------------------------------

def validate_occupancy_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the occupancy reading is complete, peak and honestly scoped.

    Returns a copy and refuses a missing value of the five, an average instead
    of a peak, a synthetic micro-benchmark instead of a full episode, or a
    reading that does not state its concurrency.  A worker count provisioned
    from average memory overloads the machine at the peak.
    """

    _require(type(receipt) is dict, "occupancy_receipt_not_object")
    _require(tuple(receipt.keys()) == OCCUPANCY_RECEIPT_FIELDS,
             "occupancy_receipt_fields_mismatch")
    _require(receipt["statistic"] == REQUIRED_STATISTIC, "occupancy_statistic_not_peak")
    _require(receipt["workload"] == REQUIRED_WORKLOAD, "occupancy_workload_not_an_episode")
    _int(receipt["concurrency_verified_at"], "occupancy_concurrency_invalid", minimum=1)
    _require(receipt["concurrency_verified_at"] == PILOT_WORKERS,
             "occupancy_concurrency_is_not_the_pilot_width")
    for name in ("cpu_cores_per_worker", "ram_gb_per_worker", "vram_gb_per_worker",
                 "disk_gb_per_worker"):
        _number(receipt[name], f"occupancy_{name}_invalid", minimum=0.0)
    _int(receipt["simulator_concurrency_limit"], "occupancy_limit_invalid", minimum=1)
    _require(type(receipt["failures"]) is list, "occupancy_failures_not_list")
    return clone_json(dict(receipt))


def plan_scale_up(
    occupancy_receipt: Mapping[str, Any],
    measurements: Mapping[str, Any],
    *,
    headroom_fraction: float,
) -> dict[str, Any]:
    """Derive the S1-02b worker count and say whether it is an extrapolation.

    Returns the worker count of the S1-01 formula (``lean_assets.derive_worker_count``,
    not reimplemented), its binding constraint and ``is_extrapolation``: True
    when the count exceeds the measured concurrency (e.g. a pilot verified at 4
    while the formula gives 9, extrapolated from single-worker costs).
    """

    checked = validate_occupancy_receipt(occupancy_receipt)
    occupancy = {name: checked[name] for name in (
        "cpu_cores_per_worker", "ram_gb_per_worker", "vram_gb_per_worker",
        "disk_gb_per_worker", "simulator_concurrency_limit")}
    plan = derive_worker_count(measurements, occupancy,
                               headroom_fraction=headroom_fraction)
    verified = checked["concurrency_verified_at"]
    plan["concurrency_verified_at"] = verified
    plan["is_extrapolation"] = plan["worker_count"] > verified
    return plan


# --------------------------------------------------------------------------
# contract
# --------------------------------------------------------------------------

def validate_pilot_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S1-02a machine contract agrees with this implementation.

    Returns a copy and refuses a contract whose pilot shape, occupancy rule,
    receipt fields, failure reasons, closed-bit list or authorization bits
    disagree with this implementation (e.g. average instead of peak, or the 4
    pilot episodes not counted towards the 50).  Values that are still null are
    not checked.
    """

    _require(type(contract) is dict, "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION,
             "contract_schema_version_invalid")
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == "S1-02a", "contract_stage_id_invalid")

    required = {
        "split_freeze", "pilot", "occupancy_measurement", "receipts",
        "failure_reasons", "failure_rules", "stop_conditions", "authorization",
        "must_remain_false", "policy_values_without_defaults", "continue_gate",
        "supersedes_contract",
    }
    missing = sorted(required - set(contract.keys()))
    _require(not missing, f"contract_missing_sections:{','.join(missing)}")

    pilot = contract["pilot"]
    _require(pilot["workers"] == PILOT_WORKERS, "contract_pilot_width_changed")
    _require(pilot["houses_per_worker"] == PILOT_HOUSES_PER_WORKER,
             "contract_pilot_houses_per_worker_changed")
    _require(pilot["total_houses"] == PILOT_TOTAL_HOUSES, "contract_pilot_total_changed")
    for name in ("selection_is_deterministic_not_chosen",
                 "counts_toward_the_development_fifty",
                 "regeneration_after_inspection_forbidden"):
        _require(pilot[name] is True, f"contract_pilot_{name}_weakened")

    occupancy = contract["occupancy_measurement"]
    _require(tuple(occupancy["values"]) == OCCUPANCY_RECEIPT_FIELDS[1:6],
             "contract_occupancy_values_mismatch")
    _require(occupancy["statistic"] == REQUIRED_STATISTIC, "contract_statistic_changed")
    _require(occupancy["workload"] == REQUIRED_WORKLOAD, "contract_workload_changed")
    _require(occupancy["measured_under_concurrency"] == PILOT_WORKERS,
             "contract_occupancy_concurrency_changed")
    for name in ("concurrency_verified_at_is_not_the_derived_count",
                 "derived_count_above_verified_concurrency_must_be_declared_an_extrapolation",
                 "synthetic_microbenchmark_forbidden"):
        _require(occupancy[name] is True, f"contract_occupancy_{name}_weakened")

    _require(tuple(contract["receipts"]["pilot_receipt_fields"]) == PILOT_RECEIPT_FIELDS,
             "contract_pilot_receipt_fields_mismatch")
    _require(tuple(contract["receipts"]["occupancy_receipt_fields"])
             == OCCUPANCY_RECEIPT_FIELDS,
             "contract_occupancy_receipt_fields_mismatch")
    _require(tuple(contract["failure_reasons"]) == FAILURE_REASONS,
             "contract_failure_reasons_diverged_from_s0_02")
    _require(tuple(contract["must_remain_false"]) == MUST_REMAIN_FALSE,
             "contract_must_remain_false_mismatch")

    for section, names in (
        ("split_freeze", ("frozen_before_first_episode",
                          "test_and_validation_membership_is_final",
                          "train_size_may_only_decrease_afterwards",
                          "development_houses_are_the_first_of_the_train_block",
                          "recomputable_from_manifest")),
        ("failure_rules", ("failed_house_keeps_a_receipt",
                           "failed_house_is_never_replaced",
                           "kept_prefix_is_preserved",
                           "planned_equals_succeeded_plus_failed",
                           "pilot_failure_is_not_grounds_for_retrying_until_good")),
        ("receipts", ("receipt_is_written_even_on_failure",)),
        ("continue_gate", ("split_is_frozen_before_the_first_episode",
                           "pilot_houses_are_recomputed_not_chosen",
                           "pilot_episodes_count_toward_the_fifty",
                           "occupancy_is_complete_before_any_derivation",
                           "failures_are_kept_and_counted")),
    ):
        for name in names:
            _require(contract[section][name] is True, f"contract_{section}_{name}_weakened")

    for name, action in contract["stop_conditions"].items():
        if name in ("may_replace_a_failed_house", "may_pick_houses_by_hand"):
            _require(action is False, f"contract_stop_escape_open:{name}")
        elif name != "plain_language_zh":
            _require(action == "stop_and_report_verbatim",
                     f"contract_stop_action_weakened:{name}")

    # The three values are either all still open or all frozen together.
    # Half-frozen is the dangerous state: it looks decided, yet filling the
    # missing one still moves where the train block starts.
    freeze = contract["split_freeze"]
    open_values = contract["policy_values_without_defaults"]
    frozen = [name for name in FROZEN_BEFORE_GENERATION if freeze[name] is not None]
    _require(len(frozen) in (0, len(FROZEN_BEFORE_GENERATION)),
             "contract_split_half_frozen")
    if not frozen:
        for name in FROZEN_BEFORE_GENERATION:
            _require(f"split_freeze.{name}" in open_values,
                     f"contract_{name}_not_registered_as_open")
    else:
        validate_split_freeze(freeze)
        frozen_by = freeze.get("frozen_by")
        _require(type(frozen_by) is str and frozen_by != "",
                 "contract_split_frozen_without_naming_the_ruling")
        _require(freeze.get("is_the_single_registered_location") is True,
                 "contract_split_not_declared_the_single_location")
        for name in FROZEN_BEFORE_GENERATION:
            _require(f"split_freeze.{name}" not in open_values,
                     f"contract_{name}_frozen_but_still_listed_as_open")
    # train_houses was left for S3-01 (which kept it null, ruling 102-8), so it stays open either way.
    _require("split_freeze.train_houses" in open_values
             or freeze["train_houses"] is not None,
             "contract_train_size_neither_open_nor_registered")

    supersedes = contract["supersedes_contract"]
    _require(type(supersedes) is dict, "contract_supersedes_not_object")
    _require(supersedes["v1_bytes_frozen"] is True,
             "contract_superseded_bytes_not_frozen")
    _require(type(supersedes["path"]) is str
             and supersedes["path"].endswith("_v1.json"),
             "contract_superseded_path_invalid")
    _require(type(supersedes["v1_sha256"]) is str
             and len(supersedes["v1_sha256"]) == 64,
             "contract_superseded_digest_invalid")

    policy = contract.get("activation_policy")
    opened = set(policy["active_true_authorizations"]) if policy else set()
    if policy:
        _require(type(policy.get("opened_by")) is str and bool(policy["opened_by"]),
                 "contract_activation_unbound")
    for name, value in contract["authorization"].items():
        _require(type(value) is bool, "contract_authorization_not_boolean")
        _require(value is False or name in opened, f"contract_bit_opened_without_a_ruling:{name}")
    return clone_json(dict(contract))


__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "FROZEN_BEFORE_GENERATION",
    "MUST_REMAIN_FALSE",
    "OCCUPANCY_RECEIPT_FIELDS",
    "PILOT_HOUSES_PER_WORKER",
    "PILOT_RECEIPT_FIELDS",
    "PILOT_TOTAL_HOUSES",
    "PILOT_WORKERS",
    "REQUIRED_STATISTIC",
    "REQUIRED_WORKLOAD",
    "SPLIT_FREEZE_FIELDS",
    "LeanPilotError",
    "plan_scale_up",
    "select_pilot_houses",
    "train_block",
    "validate_occupancy_receipt",
    "validate_pilot_contract",
    "validate_pilot_plan",
    "validate_pilot_receipt",
    "validate_split_freeze",
]
