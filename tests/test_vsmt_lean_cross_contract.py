"""D-224 / S0-06 cross-contract consistency checks over the S0 and S1-01 contracts.

S0-06 is the user's review of S0-01 to S0-05.  This module is the machine
part of that review: every contract validates against its own module, and
the facts the contracts share (arm names, atoms, states, feature names the
arms read, the two-seal rule, the candidate states, the all-false
authorisation bits and the still-null policy values) agree across files.
Since D-224-X the live contracts are the ``_v2`` files; the reviewed ``_v1``
bytes stay in the tree frozen, and this module pins their digests so a
silent edit of a reviewed contract is caught.  S1-01 is checked here too:
it consumes S0-02 and S0-03, and nothing else verifies that the simulator
and descriptor identities it registers are the ones those contracts assume.
Nothing here is a result and nothing here approves a contract.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import canonical_json  # noqa: E402

from vsmt import (  # noqa: E402
    lean_arms, lean_assets, lean_assignment, lean_development, lean_evaluation, lean_frontend_cache,
    lean_intervention, lean_memory,
    lean_pilot, lean_runner, lean_teacher,
)


CONFIG_DIR = PROJECT_ROOT / "configs" / "vsmt"
CONTRACTS = {
    "S0-01": ("lean_s0_entity_memory_v2.json", lean_memory, lean_memory.validate_entity_memory_contract),
    "S0-02": ("lean_s0_intervention_data_v3.json", lean_intervention, lean_intervention.validate_intervention_data_contract),
    "S0-03": ("lean_s0_assignment_v2.json", lean_assignment, lean_assignment.validate_assignment_contract),
    "S0-04": ("lean_s0_teacher_metrics_v2.json", lean_teacher, lean_teacher.validate_teacher_contract),
    "S0-05": ("lean_s0_arms_v2.json", lean_arms, lean_arms.validate_arms_contract),
}

#: The reviewed v1 contracts, frozen by content (D-224-X: 追加 v2 不改已审字节).
#: Digests are taken over LF-normalised bytes so they mean the same thing on
#: every platform.  .gitattributes stores every .json with LF, so a Windows
#: working tree can hold CRLF while the repository and every Linux checkout
#: hold LF; hashing the raw bytes pinned that artefact instead of the content
#: and fired on the server, where the real runs happen.
FROZEN_V1_SHA256 = {
    "lean_s0_entity_memory_v1.json": "b9d23c33a63dffcc722584ac9d3db700bfe3bbfc054f90390e505775292d8220",
    "lean_s0_intervention_data_v1.json": "ca951ff941abc1fa920f52b292902a3904fb751aa7a39ff4328cd6be576dddd8",
    "lean_s0_assignment_v1.json": "e6d8e3808365e4bd2f99b15d7394c4b13399e311f85d41e0ade30443861db6ca",
    "lean_s0_teacher_metrics_v1.json": "cf2b4426dab8e5d7a4e19859b5e6a44ef2b6d4403740335fed47d0a19d17c32c",
    "lean_s0_arms_v1.json": "498f063b5ba3920d7771ed36a96443678f67d04d0f5dc982ee7448c47738a203",
    "lean_s1_assets_capacity_v1.json": "3414efef90a6f354b0a6c600626371b0ab6b3da92faddb77176fb19bfa12eff8",
    "lean_s1_02a_pilot_v1.json": "c44db4e46bc29b9d4288560b36d20868783b5eaff34d5d8957958aed8dc7f8ff",
}


def reviewed_digest_of_bytes(raw: bytes) -> str:
    """Digest contract bytes by content, ignoring line endings."""

    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def reviewed_digest(path: Path) -> str:
    """Digest a reviewed contract by content, ignoring line endings."""

    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


#: S1-01 is not one of the five S0 contracts and does not share their
#: all-false rule, so it is loaded separately rather than added to CONTRACTS.
S1_01_CONTRACT = "lean_s1_assets_capacity_v2.json"


def load_s1_01() -> dict[str, Any]:
    return json.loads((CONFIG_DIR / S1_01_CONTRACT).read_text(encoding="utf-8"))


#: S1-02a carries the frozen split values.  S0-02 defines the split rule but
#: deliberately keeps its value slots null: a method-level contract should
#: not carry one run's seed.
S1_02A_CONTRACT = "lean_s1_02a_pilot_v2.json"


def load_s1_02a() -> dict[str, Any]:
    return json.loads((CONFIG_DIR / S1_02A_CONTRACT).read_text(encoding="utf-8"))


def load(stage: str) -> dict[str, Any]:
    return json.loads((CONFIG_DIR / CONTRACTS[stage][0]).read_text(encoding="utf-8"))


def lookup(contract: dict[str, Any], path: str) -> Any:
    """Follow a dotted path; a bare key (S0-01 style) is searched for anywhere in the tree."""

    if "." in path:
        node: Any = contract
        for part in path.split("."):
            node = node[part]
        return node
    hits: list[Any] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == path:
                    hits.append(item)
                walk(item)

    walk(contract)
    if len(hits) != 1:
        raise KeyError(f"{path}: found {len(hits)} times")
    return hits[0]


#: v1 file per stage; the v1 list of open slots is the registration of record.
FROZEN_V1_NAME = {
    "S0-01": "lean_s0_entity_memory_v1.json",
    "S0-02": "lean_s0_intervention_data_v1.json",
    "S0-03": "lean_s0_assignment_v1.json",
    "S0-04": "lean_s0_teacher_metrics_v1.json",
    "S0-05": "lean_s0_arms_v1.json",
    "S1-01": "lean_s1_assets_capacity_v1.json",
    "S1-02a": "lean_s1_02a_pilot_v1.json",
    "S1-03": "lean_s1_03_frontend_cache_v1.json",
    "S1-04": "lean_s1_04_frontend_diagnostics_v1.json",
    "S2-01": "lean_s2_01_runner_v1.json",
    "S2-04": "lean_s2_04_evaluation_v1.json",
    "S2-05": "lean_s2_05_development_v1.json",
}

#: Live contract per stage, including the S1 and S2 contracts.
LIVE_CONTRACT = {
    "S0-01": "lean_s0_entity_memory_v2.json",
    "S0-02": "lean_s0_intervention_data_v3.json",
    "S0-03": "lean_s0_assignment_v2.json",
    "S0-04": "lean_s0_teacher_metrics_v2.json",
    "S0-05": "lean_s0_arms_v2.json",
    "S1-01": "lean_s1_assets_capacity_v2.json",
    "S1-02a": "lean_s1_02a_pilot_v2.json",
    "S1-03": "lean_s1_03_frontend_cache_v1.json",
    "S1-04": "lean_s1_04_frontend_diagnostics_v1.json",
    "S2-01": "lean_s2_01_runner_v1.json",
    "S2-04": "lean_s2_04_evaluation_v1.json",
    "S2-05": "lean_s2_05_development_v1.json",
}


def load_stage(stage: str) -> dict[str, Any]:
    return json.loads((CONFIG_DIR / LIVE_CONTRACT[stage]).read_text(encoding="utf-8"))

# ----------------------------------------------------------------------------
# Value-freeze governance (D-224-S1 ruling 24).
#
# A reviewed contract is a set of RULES plus registered VALUE SLOTS that were
# null at review time and are filled later by ruling.  Filling a slot is the
# contract doing what it said it would; changing a rule is a revision.  The
# two used to share one file digest, so every fill staled every pointer.
# Here the rule digest masks the slots and the bookkeeping, and a separate
# ledger holds every value ever frozen, which may then never change.
# ----------------------------------------------------------------------------

#: Top-level keys that record process, not rules.
BOOKKEEPING_KEYS = frozenset({
    "status", "policy_values_without_defaults", "registered_value_slots", "user_rulings",
    "pending_user_rulings", "supersedes_contract", "supersedes_contract_v2",
    "activation_policy", "known_conflicts", "review_history",
})
#: Keys anywhere in the tree that only say when/by whom a value was frozen.
FREEZE_META_KEYS = frozenset({"is_the_single_registered_location"})
FREEZE_META_SUFFIXES = ("frozen_by", "frozen_on")
#: Prose keys: explanation, not machine-checked rules.
PROSE_SUFFIX = "_zh"
#: List items are addressed by one of these id fields in a dotted path.
LIST_ID_FIELDS = ("asset_id", "conflict_id", "arm", "name", "id")


def registered_value_slots(stage: str) -> tuple[str, ...]:
    """The slots a contract registered as open at v1: fixed for all time."""

    v1 = json.loads((CONFIG_DIR / FROZEN_V1_NAME[stage]).read_text(encoding="utf-8"))
    # A contract whose v1 is still the live file loses its open list as slots freeze, so it
    # records the slots it registered at v1 under ``registered_value_slots`` (S1-04, 2026-09-22).
    return tuple(v1.get("registered_value_slots") or v1["policy_values_without_defaults"])


def _resolve(node: Any, part: str) -> tuple[Any, Any]:
    """Return (container, key) for one path segment, handling id-addressed lists."""

    if isinstance(node, dict) and part in node:
        return node, part
    if isinstance(node, list):
        for index, item in enumerate(node):
            if isinstance(item, dict) and any(item.get(f) == part for f in LIST_ID_FIELDS):
                return node, index
    raise KeyError(part)


def _null_slot(tree: Any, path: str) -> None:
    if "." in path:
        node = tree
        parts = path.split(".")
        for part in parts[:-1]:
            container, key = _resolve(node, part)
            node = container[key]
        container, key = _resolve(node, parts[-1])
        container[key] = None
        return
    hits: list[tuple[Any, str]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == path:
                    hits.append((value, key))
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(tree)
    if len(hits) != 1:
        raise KeyError(f"{path}: found {len(hits)} times")
    container, key = hits[0]
    container[key] = None


def _strip(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in FREEZE_META_KEYS or key.endswith(FREEZE_META_SUFFIXES):
                continue
            if key.endswith(PROSE_SUFFIX):
                continue
            out[key] = _strip(item)
        return out
    if isinstance(value, list):
        return [_strip(item) for item in value]
    return value


def rule_digest(stage: str, contract: dict[str, Any]) -> str:
    """Digest the rules of a contract: slots nulled, bookkeeping and prose gone."""

    tree = copy.deepcopy(contract)
    for key in BOOKKEEPING_KEYS:
        tree.pop(key, None)
    for slot in registered_value_slots(stage):
        _null_slot(tree, slot)
    return hashlib.sha256(canonical_json(_strip(tree)).encode("utf-8")).hexdigest()


def lookup_slot(contract: dict[str, Any], path: str) -> Any:
    tree = copy.deepcopy(contract)
    if "." in path:
        node = tree
        for part in path.split("."):
            container, key = _resolve(node, part)
            node = container[key]
        return node
    return lookup(tree, path)


#: The rules of each live contract, pinned.  A change here is a revision of
#: the rules and needs a ruling recorded in DECISIONS plus a review; it is
#: made in place (ruling 24: no version cascade).  A value freeze does not
#: touch it.  S0-02 was re-pinned for rulings 25-32 (2026-09-20) and again for
#: rulings 33-38 (2026-09-21, twin control, best-frame seal, move minimum, salted null draw)
#: and for ruling 40 (2026-09-21, maximum_actions 4000 as a scope boundary, 2000 superseded),
#: and for rulings 39/41 (2026-09-21, dry-run destinations per object m=8, control proportion reported).
#: 2026-09-22, rulings 45/46/47 (LOG-241): S0-02 re-pinned for the per-episode private object
#: geometry table (ruling 45); S0-04 for the truth-box source (ruling 45); S0-03 for the recall
#: freeze-after-the-S1-04-curve rule (ruling 46) and the ReID 30/12 hold-out rule (ruling 47).
#: The two ReID values themselves went to the ledger below, not into the digest.
FROZEN_RULE_SHA256 = {
    # S0-01 re-pinned 2026-09-24 for ruling 56 continued (LOG-244 continued): the entity box is the union of the
    # fragment boxes attached in the latest observed frame; a later frame replaces it, merge unions only
    # same-frame records (cross-frame accumulation widened boxes with depth noise).  76f505da -> 4818d6ac.
    # Re-pinned 2026-09-25 for ruling 68 (LOG-256 sequel): the three *_superseded records beside the dedup
    # slots (cosine 0.9 -> 0.8, distance 0.25 -> 0.5 m, IoU 0.3 -> 0.05) enter the digest as bookkeeping-by-
    # precedent (S0-02, ruling 40); the values themselves are slots and do not.  4818d6ac -> 10c223a6.
    "S0-01": "10c223a65d9cb4a8b30c82fc85403402990d6104e7991c3b0493c34e849313fe",
    # S0-02 re-pinned 2026-09-23 for ruling 52 (LOG-243 supplement): the eligible object's receptacle is the
    # first non-Floor entry of parentReceptacles (entry 0 is the room floor for anything on low
    # furniture, which had hidden 99 of 987 eligible objects as sources), a Floor-only object is
    # not eligible, and the full list goes to provenance/object_table.json.  Re-pinned again the same
    # day for ruling 53: the unobservable window is the last 30 frames of the transition (the whole
    # transition rendered every container of a small house at least once; a U-turn segment re-scanned
    # the rooms just left), the leave segment is excluded from U, a short transition fails the house.
    "S0-02": "73f5144f11339c5c92c376623def22c89f3a8075b3c782efe700f4e59c80b547",
    # S0-03 re-pinned 2026-09-24 for S1-05 (LOG-245): the reid_adapter_head gains a selection_result block
    # recording the outcome the contract delegated to that stage -- the ruling-47 rule applied to the
    # S1-04 report picks reid_projection:vitb14 (gain 0.093 over the 0.05 margin on the 9 selection
    # houses), frozen ViT-B/14 is the baseline reported alongside, the weights digest is pinned and the
    # choice may not change.  A new block, not a slot fill, hence a re-pin.  1becb7e3 -> 37d56a90.
    "S0-03": "37d56a9079f90bd8db94bd68234919d7f42511b7e63214889d8a45bad5c2408a",
    # S0-04 re-pinned 2026-09-24 for ruling 56 continued: the truth node scope excludes the four ProcTHOR
    # structural types door, room, wall and window (65% of the S1-04 gate rows, unmatchable by any box or
    # centroid rule).  585e3660 -> 9bf1059d.
    # Re-pinned 2026-09-24 for ruling 69 (LOG-253): Ceiling_room joins the structural types and the
    # spawned-after-reload rule (a spawn-tagged key outside the geometry table is present, out of scope,
    # boxless and counted) is registered under node_prf1.  9bf1059d -> 7a3d661b.
    # Re-pinned 2026-09-24 for ruling 70 (LOG-255): the secondary node column node_prf1_centroid (same
    # sets and matcher, centroid distance within the frozen delta_moved_m, weight 1/(1+d), never the
    # selection metric nor a main-gate metric) joins the metric names, reported fields and rules.
    # 7a3d661b -> 126fdd34.
    # Re-pinned 2026-09-25 for ruling 68 (5) (LOG-256 sequel): nuisance_probe.scope -- the maximum advantage
    # is judged over the pooled rows of one split and the per-episode largest_advantage is reported only
    # (frame_index clusters statuses within an episode; path, seed and house index only discriminate
    # once houses are pooled).  The 0.05 itself is a slot.  126fdd34 -> c5d66505.
    # Re-pinned 2026-09-25 for ruling 72 (B) (ruling 70 -> (b)): node_prf1 now matches on the centroid within
    # delta_moved_m (primary column, the selection metric, bound role and Dyn-THOR relation "same matching
    # mechanism, different overlap test"); the IoU 0.3 test moves to node_prf1_iou (secondary, iou_min and the
    # D-224-C frozen-constant path with it); node_prf1_centroid is retired.  c5d66505 -> b831a3a4.
    "S0-04": "b831a3a40f47471b0b140af12ef0e94b5c28edc96a6b05b6161a4404984d7901",
    # S0-05 re-pinned 2026-09-25 for ruling 68 (LOG-256 sequel): every grid's values (at most twelve
    # configurations per method, a no-gate member in every rule arm), the ELU-P rollout_config
    # (0.7, 1.0, 0.0) and the should_be_visible_min_ratio_superseded record enter the digest; the
    # weight_decay, seeds and should-be-visible values are slots and do not.  c5354b1e -> 4e285050.
    "S0-05": "4e285050e0f10358d75908f5932fbac4444c89c7fd4e5f6ebd4f25ee4c879da5",
    "S1-01": "4f139e631388c05e4006fd12ffad8b611d2e7811fb7f9a830ce9f7c63fdecd84",
    "S1-02a": "997cabe5105ca304269b0d8d9dd34038ff096df7a79c875c577a2629866ccc64",
    # S1-03 re-pinned 2026-09-22 for ruling 49 (LOG-242): the public_pose_correction block -- every
    # reader restores the pitch sign of the S1-02 public quaternion for episodes from the two
    # registered pre-ruling generator commits, refuses unregistered commits, never rewrites the
    # generated files; --masks-from reads recovered masks instead of running SAM.
    # Re-pinned again the same day for ruling 51: the fragment_masks block -- the frame's admitted
    # masks are written during generation in cache fragment order, a consumer re-digests them from
    # their pixels, and the SAM-only recovery pass is no longer part of the flow (kept for caches
    # generated before this ruling).  082e1c02 -> ee591bec.
    # Re-pinned 2026-09-23 when the ruling-50 regeneration finished: its generator commit 7c10d2c
    # writes Ry(yaw)*Rx(+pitch), so it joins correct_encoder_since_code_commits and every reader
    # takes its episodes as written.  ee591bec -> 03bfd56d.
    # Re-pinned once more the same day: one fragment_masks key was named *_sha256 while holding a
    # boolean, which the config digest-shape guard rightly refused; renaming it to
    # no_new_seal_because_the_frame_seal_already_binds_every_mask_digest changes no rule.
    # 03bfd56d -> 2a17546f.
    # Re-pinned 2026-09-23 when the ruling-53 regeneration (LOG-243 续四) was accepted: its
    # generator commit 5f9aa71 leaves the camera_pose encoder of 7c10d2c untouched, so it joins
    # correct_encoder_since_code_commits and the 39 succeeded episodes are read as written.
    # 2a17546f -> c7318cd5.
    # Re-pinned 2026-09-25 for ruling 72: the mask_source block (simulator_instance_masks for the main table,
    # sam2 as the robustness appendix; the instance source reads only the five listed private items and
    # exposes mask geometry only; admission unchanged; one source per cache root) and the seal rule (a
    # non-sam2 source enters the episode seal payload, a sam2 seal keeps its pre-ruling bytes; the private
    # read before the seal happens only under the instance source, and the one private-derived value a
    # cache may hold is that anonymised, digest-ordered mask geometry); receipts name the source.
    # c7318cd5 -> f354863c.
    "S1-03": "f354863c65de95a2f6db4874ff08efd7b3152a5dbd611c077c278c85a134c959",
    # S1-04 v1 (2026-09-22, rulings 45/46/47): first pinned with every bit closed
    # (2fff2d19...); re-pinned the same day when ruling 48 and the user's code review opened
    # all six bits by name in activation_policy (the bits are rules of who may run what, as
    # for S1-03) and froze the five ReID training values into the ledger below.
    # Checked at re-pin time: with the six bits set back to false the digest is the first pin
    # again, so the bits are the only rule that moved.
    "S1-04": "293358618d0d9a8f86449148ec567051d84f9f17a9914caea7de501b135220a7",
    # S2-01 v1 (2026-09-24, LOG-246): the common runner -- the eight frame steps in order, the
    # entity-geometry sampling rule over the public volumes (its resolution is the one registered
    # value slot, null until ruled), the illegal-program fallback to an empty program, the descriptor
    # choice bound to the S1-05 freeze, and the truth-table scope rules (observable = a private mask
    # of at least 196 pixels once; structural keys present and out of scope without a box).  Both
    # authorisation bits closed.  First pinned e1060695...
    # Re-pinned 2026-09-24 after the user's S2 review (LOG-248): an illegal program now rolls back
    # the arm's temporal state with the frame, a new bound claim under frame_step.arm_state.
    # Ruling 60 (samples_per_axis = 4) is a slot fill and ruling 61 (activation_policy) is
    # bookkeeping; checked at re-pin time that with the new claim removed the digest is e1060695
    # again, so that claim is the only rule that moved.  e1060695 -> 09fc1a4a.
    # Re-pinned 2026-09-24 when rulings 64/67 and the S2-05 review opened both bits by name in
    # activation_policy (the bits are rules of who may run what, as for S1-03 / S1-04); checked at
    # re-pin time that with the bits set back to false the digest is 09fc1a4a again.  -> 36b9fbc6.
    # Re-pinned 2026-09-24 for ruling 69: the truth-table key rule names Ceiling_room among the structural
    # keys and gives spawned-after-reload keys a present / out-of-scope / boxless / counted row.  36b9fbc6 -> d07f141c.
    "S2-01": "d07f141cc6b6aff227f42c53501a9c71e62f9b85f184d260713d634f33036068",
    # S2-04 v1 (2026-09-24, LOG-249): the teacher and evaluator wiring -- the derivation rules for the
    # S0-04 inputs (place observability by the S2-01 sampled-box test at the S0-05 minimum, old and new
    # places from the S1-04 tracker at the window edges, recovery place per intervention kind, carriers
    # before a move, first labelled re-observation, evidence map by S0-04 dominance, present-by-structure
    # existence labels, MRR headline at the last frame, eligible-rows training records), the policy
    # sources, the headline fields and the closed bits.  It owns no value slot.  First pinned 40d96cf0;
    # re-pinned 2026-09-24 when rulings 64/67 and the S2-05 review opened both bits by name (with the
    # bits set back to false the digest is 40d96cf0 again).  -> f4511a34.
    # Re-pinned 2026-09-24 for ruling 69: the structural_existence rule also labels a candidate resolving to a
    # spawned-after-reload key as present.  f4511a34 -> eaac36bd.
    # Re-pinned 2026-09-24 for ruling 70: headline_fields gains node_prf1_centroid -> node_f1.  eaac36bd -> 0ff1fbe9.
    # Re-pinned 2026-09-25 for ruling 72 (B): headline_fields node_prf1_centroid -> node_prf1_iou and the iou_min
    # source path -> S0-04 metrics.node_prf1_iou.iou_min.  0ff1fbe9 -> d1645593.
    "S2-04": "d1645593bf4fd76e355af2177bf4b8aed92dd4a26bff0f006dd37945321bd7e5",
    # S2-05 v1 (2026-09-24, LOG-251): the development table -- the five passes in order (calibration
    # with LOW and no gate, the ELU-P fit with TAF at the rollout theta_a, DAgger rounds 0 and 1, the
    # table), the episode set, the calibration series and quantiles, the ELU-P count rules, the
    # sharding and merge order, the table rules, the gate after ruling 66, and eight development
    # configuration slots (null until ruled).  First pinned 38314ce2 with both bits closed; re-pinned
    # 2026-09-24 when rulings 64/67 and the S2-05 review opened both bits by name (with the bits set
    # back to false the digest is 38314ce2 again).  -> 859208ee.
    # Re-pinned 2026-09-24 for ruling 70: table.better gains node_prf1_centroid = higher.  859208ee -> 0d3cf50c.
    # Re-pinned 2026-09-25 for ruling 72 (B): table.better node_prf1_centroid -> node_prf1_iou = higher.  0d3cf50c -> 57dc753d.
    "S2-05": "57dc753d731e114372e484c885d99c3461780e3ad83387321b141fbb5c2ab635",
}

#: Every registered slot that has been frozen, and the value it froze at.
#: An entry may be added by a reviewed edit of this file.  It changes only by a user ruling,
#: and then the old value moves to SUPERSEDED_VALUES with the ruling that retired it, so no
#: value ever disappears from the record.
FROZEN_VALUES: dict[str, dict[str, Any]] = {
    "S0-01": {
        # D-224-S1 ruling 67 (2026-09-24, 原话「S2-05 审过；裁决 67 八个值全按推荐」): the shared dormancy
        # and dedup values every arm runs with; a conservative dedup (all three must hold) so the
        # development passes rarely merge; the calibration pass may supersede them by ruling 68.
        "dormancy_missed_opportunity_limit": 3,
        "shared_dedup.period_ticks": 10,
        # D-224-S1 ruling 68 (2026-09-25, LOG-256 sequel): the dedup triple re-frozen from the 39-episode
        # calibration quantiles (same-object cosine p50 0.78, box IoU p50 0.012, 35% of same-object pairs
        # within 0.5 m); the ruling-67 triple is in SUPERSEDED_VALUES below.
        "shared_dedup.descriptor_cosine_min": 0.8,
        "shared_dedup.centroid_distance_max_m": 0.5,
        "shared_dedup.aabb_iou_min": 0.05
    },
    "S0-04": {
        # D-224-S1 ruling 67 (2026-09-24): the strict-majority dominance share S1-04 labelled with, and
        # METHOD's proposed displacement bound (moves are >= 0.6 m, drift of untouched objects <= 0.16 m).
        "labels.fragment_dominance.dominance_min_share": 0.5,
        "labels.existence.delta_moved_m": 0.5,
        # D-224-S1 ruling 68 (2026-09-25): the nuisance probe's largest admissible advantage, judged over the
        # pooled rows of one split (the scope rule string beside it); per-episode values are reported only.
        "nuisance_probe.maximum_advantage": 0.05
    },
    "S0-05": {
        # D-224-S1 ruling 67 (2026-09-24) froze the should-be-visible minimum at 0.5 (half of the 64 cell
        # centres); ruling 68 (2026-09-25, LOG-256 sequel) superseded it with 1/64: the cache's visible
        # volume lies before the depth surface and entity boxes are surface shells, so 0.5 admitted 0.2
        # percent of entity-frames (2,068 existence candidates in 44,097 frames).
        "shared.should_be_visible_min_ratio": 0.015625,
        # D-224-S1 ruling 68 (2026-09-25): the two training values METHOD proposed.
        "arms.VSMT-lean.training.weight_decay": 0.0001,
        "arms.VSMT-lean.training.seeds": [7, 19, 31, 43, 59]
    },
    "S1-04": {
        # D-224-S1 ruling 48 / S1-04 code review (2026-09-22): the ReID head's training values,
        # frozen at the proposed numbers before any training run.
        "reid_training.temperature": 0.07,
        "reid_training.epochs": 20,
        "reid_training.batch_fragments": 512,
        "reid_training.learning_rate": 0.001,
        "reid_training.seed": 20260922
    },
    "S0-03": {
        # D-224-S1 ruling 47 (2026-09-22): 128 is D-224-E's own number; 0.05 cosine is the
        # minimum median cross-view separation gain the projection must show on the 12
        # selection houses over the best frozen descriptor to be chosen in S1-05.
        "reid_adapter_head.output_dimension": 128,
        "reid_adapter_head.selection_rule_threshold": 0.05,
        # D-224-S1 ruling 57 (2026-09-24): recall values from the S1-04 curve (LOG-244);
        # 2.0% recall miss for ViT-B/14 at most 8 candidates per fragment.
        "recall_rule.local_count": 5,
        "recall_rule.global_count": 3,
        "recall_rule.local_radius_m": 3.0,
        # D-224-S1 ruling 58 (2026-09-24): the fourth recall value, from the S1-04 birth neighbourhood counts.
        "recall_rule.birth_neighbourhood_radius_m": 1.0,
        # D-224-S1 ruling 68 (2026-09-25): the tau_r reference value (the runner takes tau_r from each S0-05
        # configuration; nothing reads this slot) and the reference-score seed of the invariance stand-in.
        "cost_matrix.existence_threshold_tau_r": 0.5,
        "seal.reference_score_seed": 224
    },
    "S0-02": {
        "route.translation_m": 0.25,
        "route.rotation_degrees": 90,
        "route.look_degrees": 30,
        "route.maximum_actions": 4000,
        "intervention_window.maximum_interventions_per_episode": 6,
        "intervention_window.minimum_yield": 0.6
    },
    "S1-01": {
        "worker_rule.headroom_fraction": 0.2
    },
    "S1-02a": {
        "split_freeze.seed": 20260920,
        "split_freeze.validation_houses": 50,
        "split_freeze.test_houses": 100
    },
    "S2-01": {
        # D-224-S1 ruling 60 (2026-09-24): cell centres per axis of the entity box for the two
        # geometry ratios; 64 points per entity, ratio granularity 1/64.
        "entity_geometry.samples_per_axis": 4
    },
    "S2-05": {
        # D-224-S1 ruling 68 (3) (2026-09-25): the one configuration each development arm runs at, every
        # one a member of the S0-05 grid; "no_gate" is the frozen spelling of no distance gate.
        "development_configurations.TAF.theta_a": 0.7,
        "development_configurations.TAF.d_a.distance_gate_m": "no_gate",
        "development_configurations.RAC.theta_a": 0.7,
        "development_configurations.RAC.d_a.distance_gate_m": "no_gate",
        "development_configurations.RAC.rho_rac": 0.7,
        "development_configurations.RAC.n_rac": 3,
        "development_configurations.LOW.d_low.distance_gate_m": 1.0,
        "development_configurations.VSMT-lean.tau_r": 0.5
    }
}


#: Values a ruling retired: slot -> list of {value, frozen_by, superseded_by, on}.  Each entry
#: must differ from the live ledger value and name the ruling; the contract carries the same
#: supersede record next to the slot.
SUPERSEDED_VALUES: dict[str, dict[str, list[dict[str, Any]]]] = {
    "S0-05": {
        "shared.should_be_visible_min_ratio": [
            {"value": 0.5, "frozen_by": "D-224-S1 ruling 67", "superseded_by": "D-224-S1 ruling 68", "on": "2026-09-25"},
        ],
    },
    "S0-01": {
        "shared_dedup.descriptor_cosine_min": [
            {"value": 0.9, "frozen_by": "D-224-S1 ruling 67", "superseded_by": "D-224-S1 ruling 68", "on": "2026-09-25"},
        ],
        "shared_dedup.centroid_distance_max_m": [
            {"value": 0.25, "frozen_by": "D-224-S1 ruling 67", "superseded_by": "D-224-S1 ruling 68", "on": "2026-09-25"},
        ],
        "shared_dedup.aabb_iou_min": [
            {"value": 0.3, "frozen_by": "D-224-S1 ruling 67", "superseded_by": "D-224-S1 ruling 68", "on": "2026-09-25"},
        ],
    },
    "S0-02": {
        "route.maximum_actions": [
            {"value": 2000, "frozen_by": "D-224-S1 rulings 23/24", "superseded_by": "D-224-S1 ruling 40", "on": "2026-09-21"},
        ],
    },
}


class TestS103BindsTheFrozenFrontend(unittest.TestCase):
    """S1-03 must reuse the frozen frontend and the S0-03 field lists, not restate them by hand."""

    def setUp(self) -> None:
        self.s1_03 = load_stage("S1-03")

    def test_it_passes_its_own_validator_and_names_its_stage(self) -> None:
        checked = lean_frontend_cache.validate_contract(self.s1_03)
        self.assertEqual(checked["stage_id"], "S1-03")

    def test_the_view_it_produces_is_exactly_what_s0_03_validates(self) -> None:
        self.assertEqual(tuple(self.s1_03["assignment_view"]["produces"]),
                         lean_assignment.CACHE_FRAME_FIELDS)
        self.assertEqual(tuple(self.s1_03["assignment_view"]["fragment_fields"]),
                         ("fragment_id", "descriptor", "centroid_m", "aabb_min_m",
                          "aabb_max_m", "pixel_count", "depth_valid_ratio", "supported_by"))

    def test_the_cache_never_stores_the_per_arm_entity_geometry(self) -> None:
        self.assertNotIn("entity_geometry", self.s1_03["cache_frame_fields"])
        self.assertTrue(self.s1_03["assignment_view"]
                        ["entity_geometry_is_injected_by_the_s2_runner_not_stored"])
        self.assertEqual(tuple(load_stage("S0-03")["entity_geometry_fields"]),
                         lean_assignment.ENTITY_GEOMETRY_FIELDS)

    def test_rho_free_is_resolved_as_subsumed_not_left_null(self) -> None:
        volumes = self.s1_03["volumes"]
        self.assertEqual(volumes["free_space_reliability_gate_rho_free"],
                         "subsumed_by_the_bound_d223_free_space_configuration")
        self.assertEqual(volumes["rho_free_resolution"]["implied_gate_value"], 1.0)
        self.assertNotIn("volumes.free_space_reliability_gate_rho_free",
                         self.s1_03["policy_values_without_defaults"])

    def test_the_descriptor_sets_are_the_assets_s1_01_registered(self) -> None:
        registry = {row["asset_id"]: row for row in load_stage("S1-01")["asset_registry"]}
        for key in ("primary", "optional_upgrade"):
            asset_id = self.s1_03["descriptor_sets"][key]["asset_id"]
            self.assertIn(asset_id, registry, key)
            self.assertEqual(registry[asset_id]["required_by"], "S1-03")

    def test_the_sam_assets_it_binds_are_the_ones_s1_01_registered(self) -> None:
        registry = {row["asset_id"]: row for row in load_stage("S1-01")["asset_registry"]}
        bound = self.s1_03["bound_frozen_frontend"]
        self.assertEqual(registry["sam2_checkpoint"]["sha256"], bound["sam2_checkpoint_sha256"])
        self.assertEqual(registry["sam2_repository"]["pinned_ref"], bound["sam2_repository_commit"])

    def test_every_open_bit_was_opened_by_a_ruling_and_unfrozen_values_stay_open(self) -> None:
        policy = self.s1_03["activation_policy"]
        self.assertTrue(policy["opened_by"].startswith("D-224"))
        for name, value in self.s1_03["authorization"].items():
            if value:
                self.assertIn(name, policy["active_true_authorizations"], name)
        for slot in self.s1_03["policy_values_without_defaults"]:
            node = self.s1_03
            for part in slot.split("."):
                node = node[part]
            self.assertIsNone(node, slot)


class TestSupersededValues(unittest.TestCase):
    def test_every_superseded_entry_names_a_ruling_and_differs_from_the_live_value(self) -> None:
        for stage, slots in SUPERSEDED_VALUES.items():
            for slot, history in slots.items():
                self.assertIn(slot, FROZEN_VALUES[stage])
                self.assertIn(slot, registered_value_slots(stage))
                for entry in history:
                    with self.subTest(stage=stage, slot=slot, value=entry["value"]):
                        self.assertNotEqual(entry["value"], FROZEN_VALUES[stage][slot])
                        self.assertTrue(entry["superseded_by"].startswith("D-224"))
                        self.assertRegex(entry["on"], r"^\d{4}-\d{2}-\d{2}$")

    def test_the_contract_carries_the_same_supersede_record(self) -> None:
        contract = load_stage("S0-02")
        rec = contract["route"]["maximum_actions_superseded"]
        self.assertEqual(rec["value"], SUPERSEDED_VALUES["S0-02"]["route.maximum_actions"][-1]["value"])
        self.assertEqual(rec["superseded_by"], SUPERSEDED_VALUES["S0-02"]["route.maximum_actions"][-1]["superseded_by"])
        self.assertTrue(contract["route"]["maximum_actions_is_a_scope_boundary_not_a_budget"])
        # every other superseded slot carries its record next to the slot too (ruling 68)
        for stage, slots in SUPERSEDED_VALUES.items():
            if stage == "S0-02":
                continue
            contract = load_stage(stage)
            for slot, entries in slots.items():
                with self.subTest(stage=stage, slot=slot):
                    rec = lookup_slot(contract, slot + "_superseded")
                    self.assertEqual(rec["value"], entries[-1]["value"])
                    self.assertEqual(rec["superseded_by"], entries[-1]["superseded_by"])
                    self.assertEqual(rec["frozen_by"], entries[-1]["frozen_by"])


class TestEveryContractValidates(unittest.TestCase):
    def test_each_contract_passes_its_own_validator_and_names_its_stage(self) -> None:
        for stage, (_, module, validator) in CONTRACTS.items():
            contract = load(stage)
            validator(contract)
            self.assertEqual(contract["decision_id"], "D-224", stage)
            self.assertEqual(contract["stage_id"], stage, stage)
            self.assertEqual(contract["schema_version"], module.CONTRACT_SCHEMA_VERSION, stage)

    def test_every_authorisation_bit_is_false_everywhere(self) -> None:
        for stage in CONTRACTS:
            bits = load(stage)["authorization"]
            self.assertTrue(bits, stage)
            self.assertTrue(all(value is False for value in bits.values()), stage)

    def test_every_open_policy_value_is_null_and_a_fully_frozen_contract_is_ledgered(self) -> None:
        for stage in CONTRACTS:
            contract = load(stage)
            paths = contract["policy_values_without_defaults"]
            if not paths:  # every registered slot froze (S0-01 by ruling 67): each must be in the ledger
                self.assertEqual(set(registered_value_slots(stage)), set(FROZEN_VALUES[stage]), stage)
            for path in paths:
                self.assertIsNone(lookup(contract, path), f"{stage}:{path}")

    def test_pure_core_paths_exist(self) -> None:
        for stage in CONTRACTS:
            relative = load(stage)["pure_core_relative_path"]
            self.assertTrue((PROJECT_ROOT / relative).is_file(), f"{stage}:{relative}")


class TestReviewedV1BytesAreFrozen(unittest.TestCase):
    def test_each_v1_contract_still_has_its_reviewed_digest(self) -> None:
        for name, expected in FROZEN_V1_SHA256.items():
            with self.subTest(contract=name):
                self.assertEqual(reviewed_digest(CONFIG_DIR / name), expected, name)

    def test_each_v2_contract_names_its_frozen_v1(self) -> None:
        for stage in CONTRACTS:
            contract = load(stage)
            supersedes = contract["supersedes_contract"]
            v1_name = Path(supersedes["path"]).name
            self.assertIn(v1_name, FROZEN_V1_SHA256, stage)
            self.assertEqual(supersedes["v1_sha256"], FROZEN_V1_SHA256[v1_name], stage)
            self.assertTrue(supersedes["v1_bytes_frozen"], stage)
            # Not pinned to "-v2": a contract gains a version whenever a
            # registered value is frozen, so the live one drifts forward.
            self.assertRegex(contract["schema_version"], r"-v[2-9]$", stage)

    def test_the_two_s1_contracts_name_their_frozen_v1_too(self) -> None:
        for contract in (load_s1_01(), load_s1_02a()):
            supersedes = contract["supersedes_contract"]
            v1_name = Path(supersedes["path"]).name
            with self.subTest(contract=v1_name):
                self.assertIn(v1_name, FROZEN_V1_SHA256)
                self.assertEqual(supersedes["v1_sha256"], FROZEN_V1_SHA256[v1_name])
                self.assertTrue(supersedes["v1_bytes_frozen"])

    def test_a_digest_means_the_same_thing_on_every_platform(self) -> None:
        # .gitattributes stores every .json with LF, so a Windows working
        # tree can hold CRLF while the repository and every Linux checkout
        # hold LF.  Hashing the raw bytes pinned that artefact rather than
        # the content, and fired on the server, where the real runs happen.
        for name in FROZEN_V1_SHA256:
            raw = (CONFIG_DIR / name).read_bytes()
            as_lf = raw.replace(b"\r\n", b"\n")
            as_crlf = as_lf.replace(b"\n", b"\r\n")
            with self.subTest(contract=name):
                self.assertEqual(reviewed_digest_of_bytes(as_crlf),
                                 reviewed_digest_of_bytes(as_lf))
                self.assertEqual(reviewed_digest(CONFIG_DIR / name),
                                 reviewed_digest_of_bytes(as_lf))

class TestSharedFacts(unittest.TestCase):
    def test_atoms_states_and_birth_prefix_agree_across_modules(self) -> None:
        self.assertEqual(lean_memory.ATOMS, lean_arms.ATOMS)
        self.assertEqual(lean_memory.ENTITY_STATES, lean_teacher.ENTITY_STATES)
        self.assertEqual(lean_memory.ENTITY_STATES, lean_arms.ENTITY_STATES)
        self.assertEqual(lean_assignment.BIRTH_COLUMN_PREFIX, lean_teacher.BIRTH_COLUMN_PREFIX)
        self.assertEqual(lean_assignment.BIRTH_COLUMN_PREFIX, lean_arms.BIRTH_COLUMN_PREFIX)
        self.assertEqual(tuple(load("S0-01")["entity_states"]), lean_memory.ENTITY_STATES)

    def test_arm_names_agree_between_the_evaluator_and_the_arms_contract(self) -> None:
        self.assertEqual(lean_teacher.METHOD_ARM, lean_arms.METHOD_ARM)
        self.assertEqual(lean_teacher.CONTROL_ARMS, lean_arms.CONTROL_ARMS)
        self.assertEqual(lean_teacher.ABLATION_ARMS, lean_arms.ABLATION_ARMS)
        self.assertEqual(lean_teacher.APPENDIX_ARM, lean_arms.APPENDIX_ARM)
        self.assertEqual(lean_teacher.OPTIONAL_ARM, lean_arms.OPTIONAL_ARM)
        self.assertEqual(lean_teacher.DECOMPOSITION, lean_arms.DECOMPOSITION)
        statistics = load("S0-04")["statistics"]
        arms = load("S0-05")["arms"]
        self.assertEqual(statistics["method_arm"], arms["method"])
        self.assertEqual(list(statistics["controls"]), list(arms["controls"]))
        self.assertEqual(list(statistics["ablations"]), list(load("S0-05")["ablations"]["names"]))
        self.assertEqual(statistics["appendix_arm"], load("S0-05")["appendix_arm"]["name"])
        self.assertEqual(statistics["optional_arm"], load("S0-05")["optional_arm"]["name"])
        self.assertIn("AssocOnly", arms["main_table"])

    def test_the_arms_read_only_features_the_assignment_contract_freezes(self) -> None:
        s03 = load("S0-03")
        association = set(s03["association_feature_order"])
        existence = set(s03["existence_feature_order"])
        for name in ("cosine_to_descriptor_mean", "centroid_distance_m", "state_is_retracted"):
            self.assertIn(name, association, name)
        for name in ("should_be_visible_ratio", "free_space_coverage_ratio", "state_is_retracted"):
            self.assertIn(name, existence, name)
        self.assertEqual(tuple(s03["association_feature_order"]), lean_assignment.ASSOCIATION_FEATURES)
        self.assertEqual(tuple(s03["existence_feature_order"]), lean_assignment.EXISTENCE_FEATURES)

    def test_the_two_seal_rule_is_stated_on_both_sides(self) -> None:
        self.assertEqual(load("S0-03")["seal"]["teacher_may_open_private_only_after"], "both_stage_seals_exist")
        self.assertTrue(load("S0-03")["seal"]["two_stage"])
        self.assertTrue(load("S0-04")["private_gate"]["requires_both_stage_seals"])
        self.assertTrue(load("S0-03")["seal"]["teacher_assignment_must_not_feed_existence_features"])
        self.assertTrue(load("S0-04")["private_gate"]["teacher_uses_current_policy_assignment_not_its_own"])

    def test_existence_candidates_are_the_same_states_for_the_teacher_and_the_arms(self) -> None:
        self.assertEqual(tuple(load("S0-04")["labels"]["existence"]["candidate_states"]), ("active", "dormant"))
        self.assertEqual(lean_teacher.EXISTENCE_CANDIDATE_STATES, ("active", "dormant"))
        order = list(lean_assignment.EXISTENCE_FEATURES)
        rows = []
        for state in lean_memory.ENTITY_STATES:
            features = [0.0] * len(order)
            features[order.index("should_be_visible_ratio")] = 1.0
            features[order.index(f"state_is_{state}")] = 1.0
            rows.append({"entity_id": f"entity:{state}", "features": features})
        kept = lean_arms.eligible_existence_rows(rows, order, visible_min_ratio=0.5)
        self.assertEqual([row["entity_id"] for row in kept["eligible"]], ["entity:active", "entity:dormant"])
        self.assertEqual(kept["excluded_retracted"], ["entity:retracted"])
        self.assertTrue(load("S0-05")["shared"]["existence_candidates_are_active_or_dormant_and_should_be_visible"])

    def test_the_not_applicable_rule_matches_the_arm_vocabularies(self) -> None:
        """Review correction (LOG-225): false_retract_rate is not applicable to arms without RETRACT."""

        rule = load("S0-04")["statistics"]["metric_not_applicable_rule"]
        self.assertEqual(rule, {"false_retract_rate": "arms_whose_vocabulary_lacks_RETRACT"})
        self.assertEqual(rule, lean_teacher.METRIC_NOT_APPLICABLE_RULE)
        never = lean_arms.arms_without_atom("RETRACT")
        self.assertEqual(never, ("TAF", "LOW", "AssocOnly"))
        for arm in never:
            self.assertFalse(load("S0-05")["arms"].get(arm, load("S0-05")["ablations"].get(arm, {})).get("retracts", False), arm)
        houses = {f"h{i}": {"VSMT-lean": 0.1, "ELU-P": 0.2, "TAF": None, "LOW": None, "AssocOnly": None} for i in range(3)}
        self.assertEqual(lean_teacher.undefined_houses(houses, arms=list(houses["h0"]), not_applicable=never), [])
        self.assertEqual(len(lean_teacher.undefined_houses(houses, arms=list(houses["h0"]))), 3)

    def test_the_assoc_only_counterfactual_is_stated_consistently(self) -> None:
        self.assertEqual(lean_arms.VOCABULARY["AssocOnly"], ("BIND", "BIRTH"))
        self.assertTrue(load("S0-05")["ablations"]["AssocOnly"]["reported_in_main_table"])
        self.assertTrue(load("S0-04")["statistics"]["assoc_only_reported_in_main_table"])
        self.assertTrue(load("S0-03")["recall_rule"]["global_channel_covers_every_state"])
        self.assertTrue(load("S0-03")["recall_rule"]["identical_for_all_five_arms"])
        # D-224-X ruling X3: the counterfactual retrains, it does not reuse weights.
        self.assertTrue(load("S0-05")["ablations"]["AssocOnly"]["retrained_not_weight_reuse"])
        self.assertTrue(load("S0-05")["ablations"]["AssocOnly"]["existence_loss_term_removed"])

    def test_the_selection_metric_is_a_reported_metric_and_not_a_main_gate_metric(self) -> None:
        metric = load("S0-05")["budget"]["selection_metric"]
        fields = load("S0-04")["metrics"]["reported_fields"]
        self.assertIn(metric, fields["node_prf1"])
        self.assertNotIn(metric, {name for name, _direction in lean_teacher.MAIN_GATE})

    def test_the_shared_dormancy_and_visibility_values_are_registered_once_each(self) -> None:
        # frozen by D-224-S1 ruling 67 (2026-09-24); each lives in exactly one contract and binds one constant
        self.assertEqual(load("S0-01")["shared_dormancy"]["dormancy_missed_opportunity_limit"], lean_memory.DORMANCY_MISSED_OPPORTUNITY_LIMIT)
        self.assertEqual(load("S0-05")["shared"]["should_be_visible_min_ratio"], lean_arms.SHOULD_BE_VISIBLE_MIN_RATIO)
        for stage in ("S0-02", "S0-03", "S0-04"):
            text = json.dumps(load(stage))
            self.assertNotIn("should_be_visible_min_ratio", text, stage)


class TestD224XRulingsAgreeAcrossContracts(unittest.TestCase):
    """The v2 changes touch more than one contract; the shared facts must line up."""

    def test_lifecycle_version_count_excludes_exactly_the_bind_versions_s0_01_defines(self) -> None:
        opened_by = tuple(load("S0-01")["version_record"]["opened_by_values"])
        self.assertEqual(opened_by, lean_memory.VERSION_OPENED_BY)
        excludes = tuple(load("S0-04")["metrics"]["size_and_cost"]["lifecycle_version_excludes"])
        self.assertEqual(excludes, lean_teacher.LIFECYCLE_VERSION_EXCLUDES)
        self.assertTrue(set(excludes) < set(opened_by))
        self.assertIn("lifecycle_version_count", load("S0-04")["metrics"]["reported_fields"]["size_and_cost"])

    def test_the_duplicate_status_is_a_registered_association_status(self) -> None:
        statuses = tuple(load("S0-04")["labels"]["association_statuses"])
        self.assertEqual(statuses, lean_teacher.ASSOCIATION_STATUSES)
        self.assertIn("duplicate_of_labelled", statuses)
        self.assertEqual(load("S0-04")["labels"]["same_frame_duplicates"]["others_status"], "duplicate_of_labelled")
        # S0-01 is what makes the duplicate structural: one fragment per entity per frame.
        self.assertTrue(load("S0-01")["frame_program"]["each_entity_at_most_once"])

    def test_the_rollout_config_is_an_elu_p_grid_shape_with_the_gate_left_out(self) -> None:
        s05 = load("S0-05")
        rollout = s05["arms"]["ELU-P"]["rollout_config"]
        grid = s05["arms"]["ELU-P"]["grid"]
        self.assertEqual(set(rollout) | {lean_arms.ROLLOUT_CONFIG_GATE_PARAMETER}, set(grid))
        self.assertEqual(s05["arms"]["VSMT-lean"]["training"]["dagger_round_0_memory_source"], lean_arms.ROLLOUT_CONFIG_ARM)
        self.assertEqual(s05["ablations"]["HeuristicLabel"]["label_source_arm"], lean_arms.ROLLOUT_CONFIG_ARM)

    def test_the_split_prefix_order_puts_train_last(self) -> None:
        self.assertEqual(tuple(load("S0-02")["split_rule"]["prefix_assignment"]), ("test", "validation", "train"))
        self.assertEqual(lean_intervention.SPLIT_PREFIX_ORDER, ("test", "validation", "train"))

    def test_the_solver_and_evaluator_rewrites_are_declared_equivalent(self) -> None:
        self.assertTrue(load("S0-03")["solver"]["columns_identical_to_v1_canonicalisation"])
        self.assertTrue(load("S0-03")["solver"]["canonicalisation_never_re_solves_the_matrix"])
        self.assertTrue(load("S0-04")["metrics"]["evaluator_matching_per_component_equals_dense_solve"])

    def test_every_v2_contract_carries_the_d224x_rulings_it_implements(self) -> None:
        for stage, keys in (("S0-01", ("X6_version_opened_by", "X6_dedup_fold")), ("S0-02", ("X6_split_order",))):
            rulings = load(stage)["user_rulings"]
            self.assertEqual(rulings["decision_id"], "D-224-X", stage)
            for key in keys:
                self.assertIn(key, rulings, f"{stage}:{key}")
        self.assertEqual(load("S0-04")["user_rulings_v2"]["decision_id"], "D-224-X")
        self.assertEqual(load("S0-05")["user_rulings_v2"]["decision_id"], "D-224-X")
        self.assertEqual(load("S0-03")["review_history"][-1]["decision_id"], "D-224-X")


class TestS1ConsumesTheS0Contracts(unittest.TestCase):
    """S1-01 registers the assets S0-02 and S0-03 assume.  Nothing else checks
    that the two sides still name the same simulator, dataset and weights."""

    def setUp(self) -> None:
        self.s1 = load_s1_01()
        self.registry = {row["asset_id"]: row for row in self.s1["asset_registry"]}

    def test_s1_01_passes_its_own_validator(self) -> None:
        checked = lean_assets.validate_assets_capacity_contract(self.s1)
        self.assertEqual(checked["stage_id"], "S1-01")
        self.assertEqual(checked["decision_id"], "D-224")

    def test_s1_01_consumes_a_reviewed_contract_not_a_frozen_v1(self) -> None:
        # S1-01 must not point at a v1, whose bytes are frozen precisely
        # because they are superseded.  It is allowed to lag the live
        # version by one: freezing a registered value mints a new version
        # of the upstream contract, and chasing that through every
        # downstream pointer would mint a new version of each of them too.
        # The lag is recorded rather than hidden; see LOG-230.
        depends = self.s1["depends_on"]
        for stage, key in (("S0-02", "s0_02_contract"), ("S0-03", "s0_03_contract")):
            referenced = Path(depends[key]).name
            with self.subTest(stage=stage):
                self.assertFalse(referenced.endswith("_v1.json"), stage)
                self.assertTrue((CONFIG_DIR / referenced).exists(), stage)
                live = CONTRACTS[stage][0]
                self.assertEqual(referenced.rsplit("_v", 1)[0],
                                 live.rsplit("_v", 1)[0], stage)

    def test_the_live_s0_02_contract_is_the_newest_one_present(self) -> None:
        # Whatever S1-01 points at, the cross-contract module itself must
        # read the newest version in the tree, or these checks would be
        # verifying a superseded file.
        versions = sorted(p.name for p in CONFIG_DIR.glob("lean_s0_intervention_data_v*.json"))
        self.assertEqual(CONTRACTS["S0-02"][0], versions[-1])

    def test_the_simulator_s1_registers_is_the_one_s0_02_pins(self) -> None:
        source = load("S0-02")["source"]
        ai2thor = self.registry["ai2thor"]
        self.assertEqual(source["simulator"], "AI2-THOR")
        # S0-02 pins the version; S1-01 pins the tag that version resolves to.
        self.assertIn(source["simulator_version"], ai2thor["pinned_path"])
        self.assertEqual(self.registry["procthor_10k_dataset"]["role"], "house_pool")
        self.assertIn(source["dataset"].split("-")[0].lower(),
                      self.registry["procthor_10k_dataset"]["source_url"])

    def test_the_frozen_descriptors_s1_registers_match_d215(self) -> None:
        d215 = json.loads((CONFIG_DIR / "vm04_d215_frontend_freeze_v1.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(self.registry["sam2_checkpoint"]["sha256"],
                         d215["sam2"]["checkpoint_sha256"])
        self.assertEqual(self.registry["sam2_repository"]["pinned_ref"],
                         d215["sam2"]["repository_commit"])

    def test_both_descriptor_sizes_s0_03_may_choose_between_are_registered(self) -> None:
        # S0-03 registers a ReID head over the frozen descriptor and leaves the
        # choice to S1-05, so both candidates must exist as registered assets.
        reid = load("S0-03")["reid_adapter_head"]
        self.assertEqual(reid["input"], "frozen_dinov2_descriptor")
        self.assertEqual(reid["selection_stage"], "S1-05")
        for asset_id in ("dinov2_vit_s14_checkpoint", "dinov2_vit_b14_checkpoint"):
            row = self.registry[asset_id]
            self.assertIsNotNone(row["sha256"], asset_id)
            self.assertIsNotNone(row["bytes"], asset_id)

    def test_generation_is_closed_on_both_sides(self) -> None:
        # S1-01 may not generate episodes, and S0-02 has not been authorised
        # to either; if one side opened, the other would be stale.
        self.assertIn("route_or_episode_generation", self.s1["must_remain_false"])
        self.assertIs(load("S0-02")["authorization"]["episode_generation"], False)

    def test_the_occupancy_measurement_is_owned_by_the_stage_that_can_run(self) -> None:
        self.assertEqual(self.s1["worker_rule"]["measurement_stage"], "S1-02a")
        self.assertNotIn("single_worker_occupancy_measurement", self.s1["authorization"])

    def test_s1_01_keeps_no_open_policy_value_behind(self) -> None:
        self.assertEqual(self.s1["policy_values_without_defaults"], [])
        self.assertEqual(self.s1["worker_rule"]["headroom_fraction"], 0.2)


class TestTheSplitIsFrozenInExactlyOnePlace(unittest.TestCase):
    """S0-02 defines how the split works; S1-02a records which split this
    run uses.  Two registered copies of a seed is the failure mode worth
    preventing, because nothing would say which one generated the data."""

    def setUp(self) -> None:
        self.s0_02 = load("S0-02")
        self.s1_02a = load_s1_02a()

    def test_s1_02a_passes_its_own_validator(self) -> None:
        checked = lean_pilot.validate_pilot_contract(self.s1_02a)
        self.assertEqual(checked["stage_id"], "S1-02a")

    def test_s0_02_keeps_its_value_slots_null(self) -> None:
        rule = self.s0_02["split_rule"]
        for name in ("seed", "validation_houses", "test_houses", "train_houses"):
            self.assertIsNone(rule[name], name)

    def test_s1_02a_declares_itself_the_single_registered_location(self) -> None:
        freeze = self.s1_02a["split_freeze"]
        self.assertIs(freeze["is_the_single_registered_location"], True)
        for name in lean_pilot.FROZEN_BEFORE_GENERATION:
            self.assertIsNotNone(freeze[name], name)

    def test_the_frozen_split_satisfies_the_s0_02_rule(self) -> None:
        rule = self.s0_02["split_rule"]
        freeze = self.s1_02a["split_freeze"]
        self.assertIs(rule["test_and_validation_sizes_and_seed_frozen_before_first_generation"],
                      True)
        self.assertIs(freeze["frozen_before_first_episode"], True)
        self.assertIs(rule["train_size_may_only_decrease_after_registration"], True)
        self.assertIs(freeze["train_size_may_only_decrease_afterwards"], True)
        self.assertIs(rule["development_houses_are_the_first_houses_of_the_train_block"],
                      True)
        self.assertIs(freeze["development_houses_are_the_first_of_the_train_block"], True)

    def test_both_sides_allocate_test_then_validation_then_train(self) -> None:
        self.assertEqual(list(self.s0_02["split_rule"]["prefix_assignment"]),
                         ["test", "validation", "train"])

    def test_the_pilot_selection_uses_the_frozen_values_end_to_end(self) -> None:
        pool = [f"house-{index:04d}" for index in range(400)]
        selected = lean_pilot.select_pilot_houses(pool, self.s1_02a["split_freeze"])
        split = lean_intervention.assign_split(
            pool,
            seed=self.s1_02a["split_freeze"]["seed"],
            train=len(pool) - 150,
            validation=self.s1_02a["split_freeze"]["validation_houses"],
            test=self.s1_02a["split_freeze"]["test_houses"],
        )
        self.assertEqual(selected, split["train"][:4])
        self.assertFalse(set(selected) & set(split["test"]))

    def test_s1_02a_reuses_the_s1_01_worker_derivation(self) -> None:
        self.assertIs(lean_pilot.derive_worker_count, lean_assets.derive_worker_count)

    def test_s1_02a_reuses_the_s0_02_failure_reasons(self) -> None:
        self.assertEqual(tuple(self.s1_02a["failure_reasons"]),
                         lean_intervention.FAILURE_REASONS)

    def test_generation_stays_closed_on_every_side(self) -> None:
        self.assertIs(self.s0_02["authorization"]["episode_generation"], False)
        self.assertIs(self.s1_02a["authorization"]["episode_generation"], True)  # opened for the pilot by ruling 24
        self.assertIn("route_or_episode_generation", load_s1_01()["must_remain_false"])


class TestRulesArePinnedAndValuesAreLedgered(unittest.TestCase):
    """Ruling 24: rules change only by revision; values change only by ledger."""

    def test_each_live_contract_has_the_pinned_rule_digest(self) -> None:
        for stage, expected in FROZEN_RULE_SHA256.items():
            with self.subTest(stage=stage):
                self.assertEqual(rule_digest(stage, load_stage(stage)), expected)

    def test_every_filled_slot_is_in_the_ledger_with_the_same_value(self) -> None:
        # A slot that is filled but not ledgered is a silent freeze.
        for stage in FROZEN_RULE_SHA256:
            contract = load_stage(stage)
            for slot in registered_value_slots(stage):
                value = lookup_slot(contract, slot)
                with self.subTest(stage=stage, slot=slot):
                    if value is None:
                        self.assertNotIn(slot, FROZEN_VALUES.get(stage, {}))
                        self.assertIn(slot, contract["policy_values_without_defaults"])
                    else:
                        self.assertIn(slot, FROZEN_VALUES.get(stage, {}))
                        self.assertEqual(value, FROZEN_VALUES[stage][slot])
                        self.assertNotIn(slot, contract["policy_values_without_defaults"])

    def test_every_ledger_entry_is_a_registered_slot_of_that_stage(self) -> None:
        for stage, values in FROZEN_VALUES.items():
            slots = set(registered_value_slots(stage))
            for slot in values:
                with self.subTest(stage=stage, slot=slot):
                    self.assertIn(slot, slots)

    def test_filling_a_slot_does_not_move_the_rule_digest(self) -> None:
        # The whole point: a value freeze is not a revision.
        for stage in FROZEN_RULE_SHA256:
            contract = load_stage(stage)
            slots = registered_value_slots(stage)
            if not slots:
                continue
            altered = copy.deepcopy(contract)
            container, key = _resolve_path(altered, slots[0])
            container[key] = 424242
            with self.subTest(stage=stage, slot=slots[0]):
                self.assertEqual(rule_digest(stage, altered), rule_digest(stage, contract))

    def test_changing_a_rule_does_move_the_rule_digest(self) -> None:
        for stage in FROZEN_RULE_SHA256:
            contract = load_stage(stage)
            altered = copy.deepcopy(contract)
            altered["authorization"] = dict(altered["authorization"])
            altered["authorization"]["__injected_rule__"] = True
            with self.subTest(stage=stage):
                self.assertNotEqual(rule_digest(stage, altered), rule_digest(stage, contract))

    def test_prose_and_freeze_metadata_are_not_rules(self) -> None:
        for stage in FROZEN_RULE_SHA256:
            contract = load_stage(stage)
            altered = copy.deepcopy(contract)
            altered["plain_language_zh"] = "edited explanation"
            altered["__frozen_by"] = "x"
            with self.subTest(stage=stage):
                self.assertEqual(rule_digest(stage, altered), rule_digest(stage, contract))


class TestTheS105SelectionIsRecordedOnceAndAgreesWithItsReceipt(unittest.TestCase):
    """S1-05 froze the descriptor by applying the ruling-47 rule to the S1-04 report.  The contract
    records the outcome, the module binds it, and the committed receipt is the evidence; the three
    must agree, and the receipt must point at the S1-04 report bytes that are in the tree."""

    def setUp(self) -> None:
        self.result = load("S0-03")["reid_adapter_head"]["selection_result"]
        self.receipt_path = PROJECT_ROOT / self.result["receipt"]
        self.receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))

    def test_the_receipt_named_by_the_contract_exists_and_froze_the_same_descriptor(self) -> None:
        frozen = self.receipt["frozen"]
        self.assertEqual(self.receipt["stage"], "S1-05")
        self.assertEqual(frozen["selected_descriptor"], self.result["selected"])
        self.assertEqual(frozen["source_descriptor_set"], self.result["source_descriptor_set"])
        self.assertEqual(frozen["frozen_descriptor_baseline"], self.result["frozen_descriptor_baseline"])
        self.assertEqual(frozen["projection"]["weights_sha256"], self.result["weights_sha256"])
        self.assertEqual(frozen["projection"]["weights_file"], self.result["weights_file"])
        self.assertEqual(frozen["unselected_dropped_from_the_assignment_view"],
                         self.result["unselected_sets_dropped_from_the_assignment_view"])
        self.assertTrue(frozen["no_further_descriptor_change"] and self.result["no_further_descriptor_change"])

    def test_the_receipt_and_the_contract_point_at_the_committed_s1_04_report(self) -> None:
        report_path = PROJECT_ROOT / self.result["input_report"]
        digest = reviewed_digest(report_path)  # by content: a CRLF working tree must not change it
        self.assertEqual(digest, self.result["input_report_sha256"])
        self.assertEqual(self.receipt["input"]["s1_04_report"], self.result["input_report"])
        self.assertEqual(self.receipt["input"]["s1_04_report_sha256"], digest)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["reid"]["selection_rule"]["chosen"], self.result["selected"])
        self.assertEqual(report["reid"]["by_set"][self.result["source_descriptor_set"]]["weights_sha256"],
                         self.result["weights_sha256"])

    def test_the_selection_used_the_registered_rule_and_recorded_the_shortfall(self) -> None:
        head = load("S0-03")["reid_adapter_head"]
        selection = self.receipt["selection"]
        self.assertEqual(self.receipt["rule"]["selection_rule_threshold"], head["selection_rule_threshold"])
        self.assertGreaterEqual(selection["projection_gain_over_best_frozen"], head["selection_rule_threshold"])
        self.assertTrue(selection["matches_the_report_block"])
        shortfall = self.receipt["selection_shortfall"]
        self.assertEqual(shortfall["registered_selection_houses"], head["holdout"]["selection_houses"])
        self.assertEqual(shortfall["selection_houses_used"], self.result["selection_houses_used"])
        self.assertEqual(shortfall["shortfall"], self.result["selection_shortfall"])
        self.assertEqual(shortfall["selection_houses_used"] + shortfall["shortfall"], head["holdout"]["selection_houses"])
        self.assertTrue(head["holdout"]["a_house_without_a_cache_is_skipped_and_counted_never_replaced"])

    def test_the_module_binds_the_recorded_selection(self) -> None:
        self.assertEqual(lean_assignment.SELECTED_DESCRIPTOR, self.result["selected"])
        self.assertEqual(lean_assignment.SELECTED_DESCRIPTOR_SOURCE_SET, self.result["source_descriptor_set"])
        self.assertEqual(lean_assignment.FROZEN_DESCRIPTOR_BASELINE, self.result["frozen_descriptor_baseline"])
        self.assertEqual(lean_assignment.SELECTED_REID_WEIGHTS_SHA256, self.result["weights_sha256"])
        # The S1-03 cache stores both sets and the S1-03 contract says the choice is made in S1-05, not there.
        sets = load_stage("S1-03")["descriptor_sets"]
        self.assertIn(self.result["source_descriptor_set"], {sets["primary"]["name"], sets["optional_upgrade"]["name"]})
        self.assertTrue(sets["both_extracted_in_s1_one_selected_in_s1_05"])
        self.assertTrue(sets["unselected_set_is_dropped_after_s1_05"])


class TestS201RunnerContractBindsItsUpstreams(unittest.TestCase):
    """S2-01 reuses S0-01, S0-03, S0-05 and the S1-05 freeze; it may not restate or drift from them."""

    def setUp(self) -> None:
        self.contract = load_stage("S2-01")

    def test_the_contract_passes_its_validator_with_both_bits_closed(self) -> None:
        checked = lean_runner.validate_runner_contract(self.contract)
        self.assertEqual(checked["stage_id"], "S2-01")
        self.assertEqual(set(checked["authorization"]), {"episode_run", "server_run"})
        self.assertTrue(all(value is False or name in checked["activation_policy"]["active_true_authorizations"]
                            for name, value in checked["authorization"].items()))
        for key, path in checked["depends_on"].items():
            if key.endswith("_contract"):
                with self.subTest(key=key):
                    self.assertTrue((PROJECT_ROOT / path).is_file(), path)
                    self.assertFalse(path.endswith("_v1.json") and key.startswith("s0_"), "S2-01 must consume the live S0 contracts")

    def test_the_descriptor_block_is_the_s1_05_freeze(self) -> None:
        result = load("S0-03")["reid_adapter_head"]["selection_result"]
        descriptor = self.contract["descriptor"]
        self.assertEqual(descriptor["selected"], result["selected"])
        self.assertEqual(descriptor["source_set"], result["source_descriptor_set"])
        self.assertEqual(descriptor["frozen_baseline"], result["frozen_descriptor_baseline"])
        self.assertEqual(descriptor["weights_sha256"], result["weights_sha256"])
        self.assertEqual(list(descriptor["choices"]), [result["selected"], result["frozen_descriptor_baseline"]])

    def test_the_runner_reads_its_policy_values_from_the_contracts_that_own_them(self) -> None:
        sources = self.contract["frame_step"]["policy_input_sources"]
        s0_01 = load("S0-01")
        # ruling 67 froze every value the runner reads; each is in the ledger and no longer listed as open
        self.assertEqual(s0_01["policy_values_without_defaults"], [])
        self.assertEqual(s0_01["shared_dormancy"]["dormancy_missed_opportunity_limit"], FROZEN_VALUES["S0-01"]["dormancy_missed_opportunity_limit"])
        self.assertTrue(all(s0_01["shared_dedup"][name] == FROZEN_VALUES["S0-01"][f"shared_dedup.{name}"]
                            for name in ("period_ticks", "descriptor_cosine_min", "centroid_distance_max_m", "aabb_iou_min")))
        self.assertEqual(load("S0-05")["shared"]["should_be_visible_min_ratio"], FROZEN_VALUES["S0-05"]["shared.should_be_visible_min_ratio"])
        self.assertTrue(sources["dormancy_missed_opportunity_limit"].startswith("S0-01"))
        self.assertTrue(sources["should_be_visible_min_ratio"].startswith("S0-05"))
        self.assertEqual(self.contract["policy_values_without_defaults"], [])
        self.assertEqual(registered_value_slots("S2-01"), ("entity_geometry.samples_per_axis",))
        self.assertEqual(self.contract["entity_geometry"]["samples_per_axis"], 4)  # D-224-S1 ruling 60
        self.assertEqual(self.contract["entity_geometry"]["samples_per_axis"], lean_runner.ENTITY_GEOMETRY_SAMPLES_PER_AXIS)
        self.assertEqual(tuple(self.contract["entity_geometry"]["fields"]), lean_assignment.ENTITY_GEOMETRY_FIELDS)

    def test_the_truth_table_rules_agree_with_s0_04_and_s0_02(self) -> None:
        truth = self.contract["truth_table"]
        self.assertEqual(tuple(truth["structural_types_out_of_scope"]), lean_teacher.STRUCTURAL_TYPES_EXCLUDED)
        self.assertEqual(truth["observable_min_pixels"], lean_frontend_cache.MINIMUM_VISIBLE_PIXELS)
        node = load("S0-04")["metrics"]["node_prf1"]
        self.assertEqual(list(node["structural_types_excluded_from_scope"]), list(truth["structural_types_out_of_scope"]))
        self.assertTrue(node["truth_table_carries_in_scope_flag"])

    def test_the_runnable_arms_are_the_s0_05_arms_without_the_appendix_arm(self) -> None:
        step = self.contract["frame_step"]
        self.assertEqual(tuple(step["runnable_arms"]), tuple(arm for arm in lean_arms.ALL_ARMS if arm != lean_arms.APPENDIX_ARM))
        self.assertEqual(step["appendix_arm_refused_here"], lean_arms.APPENDIX_ARM)
        self.assertEqual(load("S0-05")["appendix_arm"]["name"], lean_arms.APPENDIX_ARM)


class TestS204EvaluationContractBindsItsUpstreams(unittest.TestCase):
    """S2-04 wires S0-04, S0-05, S2-01 and S1-04 together; it registers derivations, never a rule or value of its own."""

    def setUp(self) -> None:
        self.contract = load_stage("S2-04")

    def test_the_contract_passes_its_validator_with_both_bits_closed_and_owns_no_value_slot(self) -> None:
        checked = lean_evaluation.validate_evaluation_contract(self.contract)
        self.assertEqual(checked["stage_id"], "S2-04")
        self.assertEqual(set(checked["authorization"]), {"label_generation_run", "server_run"})
        self.assertTrue(all(value is False or name in checked["activation_policy"]["active_true_authorizations"]
                            for name, value in checked["authorization"].items()))
        self.assertEqual(registered_value_slots("S2-04"), ())
        for key, path in checked["depends_on"].items():
            if key.endswith("_contract"):
                with self.subTest(key=key):
                    self.assertTrue((PROJECT_ROOT / path).is_file(), path)
                    self.assertFalse(path.endswith("_v1.json") and key.startswith("s0_"), "S2-04 must consume the live S0 contracts")

    def test_its_policy_sources_are_registered_slots_of_the_contracts_that_own_them(self) -> None:
        sources = self.contract["policy_input_sources"]
        s0_04 = load("S0-04")
        for name, path in (("dominance_min_share", "labels.fragment_dominance.dominance_min_share"),
                           ("delta_moved_m", "labels.existence.delta_moved_m")):
            self.assertTrue(sources[name].startswith("S0-04"))
            self.assertEqual(lookup(s0_04, path), FROZEN_VALUES["S0-04"][path])  # frozen by ruling 67
            self.assertNotIn(path, s0_04["policy_values_without_defaults"])
        self.assertEqual(load("S0-05")["shared"]["should_be_visible_min_ratio"], FROZEN_VALUES["S0-05"]["shared.should_be_visible_min_ratio"])
        self.assertEqual(registered_value_slots("S2-01"), ("entity_geometry.samples_per_axis",))
        self.assertEqual(s0_04["metrics"]["node_prf1_iou"]["iou_min"], lean_teacher.IOU_MIN)

    def test_headline_fields_and_report_fields_are_the_s0_04_ones(self) -> None:
        fields = load("S0-04")["metrics"]["reported_fields"]
        for metric, field in self.contract["headline_fields"].items():
            self.assertIn(field, fields[metric], metric)
        self.assertEqual(set(self.contract["headline_fields"]), set(lean_teacher.METRICS) - {"size_and_cost"})

    def test_the_structural_and_scope_rules_agree_with_s0_04_and_s2_01(self) -> None:
        rules = self.contract["derivation_rules"]
        self.assertIn("structural", rules["structural_existence"])
        self.assertEqual(tuple(load_stage("S2-01")["truth_table"]["structural_types_out_of_scope"]), lean_teacher.STRUCTURAL_TYPES_EXCLUDED)
        self.assertEqual(tuple(rules["missing_residual_kinds"]), ("remove", "move"))
        self.assertEqual(tuple(rules["identity_continuity_kinds"]), ("move",))


class TestS205DevelopmentContractBindsItsUpstreams(unittest.TestCase):
    """S2-05 composes S2-01, S2-04, S0-05 and S0-04; its own slots are the development configurations only."""

    def setUp(self) -> None:
        self.contract = load_stage("S2-05")

    def test_the_contract_passes_its_validator_with_every_slot_frozen_at_the_ledger_value(self) -> None:
        checked = lean_development.validate_development_contract(self.contract)
        self.assertEqual(checked["stage_id"], "S2-05")
        self.assertTrue(all(value is False or name in checked["activation_policy"]["active_true_authorizations"]
                            for name, value in checked["authorization"].items()))
        # ruling 68 (3) froze the eight development-configuration slots; none is open any more
        self.assertEqual(checked["policy_values_without_defaults"], [])
        self.assertEqual(set(registered_value_slots("S2-05")), set(FROZEN_VALUES["S2-05"]))
        for slot in registered_value_slots("S2-05"):
            self.assertEqual(lookup_slot(checked, slot), FROZEN_VALUES["S2-05"][slot], slot)
        for key, path in checked["depends_on"].items():
            if key.endswith("_contract"):
                with self.subTest(key=key):
                    self.assertTrue((PROJECT_ROOT / path).is_file(), path)

    def test_the_development_arms_and_passes_agree_with_s0_05(self) -> None:
        s0_05 = load("S0-05")
        arms_ = self.contract["development_arms"]
        self.assertEqual(set(arms_), set(s0_05["arms"]["main_table"]) | {"NoVersion"})
        self.assertNotIn(s0_05["appendix_arm"]["name"], arms_)
        calibration = self.contract["passes"]["calibration_arm"]
        self.assertEqual(calibration["arm"], "LOW")
        self.assertEqual(set(calibration["config"]), set(lean_arms.GRID_PARAMETERS["LOW"]))
        self.assertIsNone(calibration["config"][lean_arms.NO_GATE_PARAMETER["LOW"]])
        self.assertTrue(self.contract["passes"]["dagger"]["elu_p_table_row_is_the_round_0_pass"])
        self.assertEqual(s0_05["arms"]["VSMT-lean"]["training"]["dagger_round_0_memory_source"], "ELU-P")
        for arm in ("TAF", "RAC", "LOW", "VSMT-lean"):
            self.assertEqual(set(self.contract["development_configurations"][arm]), set(lean_arms.GRID_PARAMETERS[arm]), arm)

    def test_the_table_rules_are_the_s2_04_and_s0_04_ones(self) -> None:
        better = self.contract["table"]["better"]
        self.assertEqual(set(better), set(load_stage("S2-04")["headline_fields"]))
        self.assertEqual(set(better), set(lean_teacher.METRICS) - {"size_and_cost"})
        self.assertEqual(dict(better), lean_development.BETTER)
        self.assertEqual(load("S0-04")["statistics"]["metric_not_applicable_rule"]["false_retract_rate"], "arms_whose_vocabulary_lacks_RETRACT")
        self.assertEqual(self.contract["continue_gate"]["design_revisions_go_through_a_ruling_before_s3_01"], True)


def _resolve_path(tree: Any, path: str) -> tuple[Any, Any]:
    node = tree
    parts = path.split(".") if "." in path else [path]
    if len(parts) == 1:
        hits: list[tuple[Any, str]] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == path:
                        hits.append((value, key))
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(tree)
        assert len(hits) == 1, path
        return hits[0]
    for part in parts[:-1]:
        container, key = _resolve(node, part)
        node = container[key]
    return _resolve(node, parts[-1])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
