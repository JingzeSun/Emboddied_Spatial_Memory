"""Ruling 105 tests: the LLM-op module (lean_llm_op) on the DeepSeek API, without the network.

Pinned here: the stage contract binds every registered value to the code and opens no bit without a ruling; the price of a
call follows the peak windows; the key comes from the environment or its owner-only file and never reaches a repr; a live
answer is archived before it is used and a replay answers from the archive alone (a changed or missing request is refused);
service errors back off and never count as answers, a fatal 4xx and a STOP file stop the call, a changed model stops live
and in replay, a cut-off archive line is dropped and recorded; the scorer re-asks invalid answers at most three times and
then falls back (every fragment BIRTH, every entity NOOP) and guards the split (validation; the train pilot of at most 200
frames); the runner drives LLM-op and a replay reproduces its trajectory with no call.  The node-audit entry and the driver
are tested in test_vsmt_lean_llm_op_driver.  Every request goes to a scripted transport that answers from the request's own
tables.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from typing import Any, Mapping
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt", PROJECT_ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_node_audit as audit_module  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_controls as lc  # noqa: E402
from vsmt import lean_llm_op as llm  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402
from test_vsmt_lean_controls import stage_a_and_rows  # noqa: E402
from test_vsmt_lean_runner import POLICY, scenario  # noqa: E402

#: The reviewed bytes of the LLM-op contract (CRLF folded to LF); both bits closed until the user's code review.
REVIEWED_CONTRACT_SHA256 = "1e4db7d41dc2c76f075cfe50f3cb1e7f4edaad8266c8050ff12062ab8e7eeae0"
SERVED = "deepseek-v4.1-flash"
SATURDAY_NOON = dt.datetime(2026, 10, 3, 12, 0, tzinfo=dt.timezone.utc)


def response(content: str, *, model: str = SERVED, finish: str = "stop", usage: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"id": "r-1", "model": model, "system_fingerprint": "fp",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content, "reasoning_content": "thinking ..."},
                         "finish_reason": finish}],
            "usage": dict(usage or {"prompt_tokens": 1000, "prompt_cache_hit_tokens": 800, "prompt_cache_miss_tokens": 200,
                                    "completion_tokens": 300, "completion_tokens_details": {"reasoning_tokens": 250}, "total_tokens": 1300})}


def scripted_answer(messages: list[Mapping[str, str]]) -> str:
    """A deterministic stand-in for the model, reading only the tables it was sent: the most similar candidate at a cosine of
    at least 0.8, else BIRTH; RETRACT when the free-space coverage is at least 0.9, else NOOP."""

    lines = messages[1]["content"].splitlines()
    if lines[0] == "CANDIDATES":
        at = lines[1].split(",").index("cosine_to_descriptor_mean")
        best: dict[str, tuple[str, float]] = {}
        index = 2
        while lines[index]:
            cells = lines[index].split(",")
            if float(cells[at]) >= 0.8 and (cells[0] not in best or float(cells[at]) > best[cells[0]][1]):
                best[cells[0]] = (cells[1], float(cells[at]))
            index += 1
        fragments = [row.split(",")[0] for row in lines[index + 3:] if row]
        return "\n".join(f"{f} -> {best[f][0] if f in best else lc.BIRTH_WORD}" for f in fragments) + "\n"
    at = lines[1].split(",").index("free_space_coverage_ratio")
    return "\n".join(f"{row.split(',')[0]} -> {'RETRACT' if float(row.split(',')[at]) >= 0.9 else 'NOOP'}" for row in lines[2:] if row) + "\n"


class ScriptedTransport:
    """Answers from the request's tables; ``script`` items (status, payload) or exceptions are served first."""

    def __init__(self, script: list[Any] | None = None, *, model: str = SERVED) -> None:
        self.script = list(script or [])
        self.bodies: list[dict[str, Any]] = []
        self.model = model

    def post(self, body: Mapping[str, Any]) -> tuple[int, str]:
        self.bodies.append(json.loads(json.dumps(body)))
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, BaseException):
                raise item
            status, payload = item
            return status, payload if isinstance(payload, str) else json.dumps(payload)
        return 200, json.dumps(response(scripted_answer(body["messages"]), model=self.model))


def opened_contract() -> dict[str, Any]:
    contract = json.loads(llm.CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["authorization"] = {"pilot_run": True, "validation_run": True}
    contract["activation_policy"] = {"opened_by": "test ruling", "active_true_authorizations": ["pilot_run", "validation_run"]}
    return llm.validate_contract(contract)


def caller(tmp: Path, *, transport: Any = None, mode: str = "live", expected: str | None = None, sleeps: list | None = None,
           name: str = "a.jsonl") -> llm.LlmCaller:
    return llm.LlmCaller(archive=llm.CallArchive(tmp / name), mode=mode, transport=transport, expected_model=expected,
                         stop_path=tmp / llm.STOP_FILE, sleep=(sleeps.append if sleeps is not None else (lambda s: None)),
                         now=lambda: SATURDAY_NOON)


class TempDir(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class ContractTests(unittest.TestCase):
    def test_the_contract_validates_with_both_bits_closed_and_its_bytes_are_the_reviewed_ones(self) -> None:
        contract = llm.load_contract()
        self.assertEqual(contract["authorization"], {"pilot_run": False, "validation_run": False})
        self.assertFalse(llm.authorized(contract, "pilot_run"))
        self.assertEqual(hashlib.sha256(llm.CONTRACT_PATH.read_bytes().replace(b"\r\n", b"\n")).hexdigest(), REVIEWED_CONTRACT_SHA256)
        self.assertEqual(contract["input"]["instruction_sha256"], lc.INSTRUCTION_SHA256)

    def test_a_changed_value_or_a_bit_opened_without_a_ruling_is_refused(self) -> None:
        base = json.loads(llm.CONTRACT_PATH.read_text(encoding="utf-8"))
        for path, value, code in (("cost.cap_usd", 151.0, "contract_value_mismatch:cost.cap_usd"),
                                  ("request.model", "deepseek-v4-pro", "contract_value_mismatch:request.model"),
                                  ("validation_scope.draw_salt", "x|", "contract_value_mismatch:validation_scope.draw_salt"),
                                  ("input.instruction_sha256", "0" * 64, "contract_value_mismatch:input.instruction_sha256")):
            changed = copy.deepcopy(base)
            node = changed
            *parents, leaf = path.split(".")
            for part in parents:
                node = node[part]
            node[leaf] = value
            with self.subTest(path=path), self.assertRaises(llm.LlmOpError) as caught:
                llm.validate_contract(changed)
            self.assertEqual(str(caught.exception), code)
        opened = copy.deepcopy(base)
        opened["authorization"]["validation_run"] = True
        with self.assertRaises(llm.LlmOpError) as caught:
            llm.validate_contract(opened)
        self.assertEqual(str(caught.exception), "contract_bit_opened_without_a_ruling:validation_run")
        self.assertTrue(llm.authorized(opened_contract(), "validation_run"))


class PriceTests(unittest.TestCase):
    def test_the_peak_windows_are_weekday_utc_hours(self) -> None:
        monday = dt.datetime(2026, 10, 5, tzinfo=dt.timezone.utc)
        for hour, minute, peak in ((0, 59, False), (1, 0, True), (3, 59, True), (4, 0, False), (6, 0, True), (9, 59, True), (10, 0, False)):
            with self.subTest(hour=hour, minute=minute):
                self.assertEqual(llm.is_peak(monday.replace(hour=hour, minute=minute)), peak)
        self.assertFalse(llm.is_peak(SATURDAY_NOON.replace(hour=2)))
        sydney = dt.timezone(dt.timedelta(hours=11))
        self.assertTrue(llm.is_peak(dt.datetime(2026, 10, 5, 13, 0, tzinfo=sydney)))  # 02:00 UTC on the Monday
        with self.assertRaises(llm.LlmOpError):
            llm.is_peak(dt.datetime(2026, 10, 5, 2, 0))

    def test_a_call_costs_its_tokens_at_the_price_of_its_instant(self) -> None:
        usage = {"prompt_cache_hit_tokens": 1_000_000, "prompt_cache_miss_tokens": 1_000_000, "completion_tokens": 1_000_000}
        self.assertAlmostEqual(llm.call_cost_usd(usage, SATURDAY_NOON), 0.003 + 0.15 + 0.6)
        self.assertAlmostEqual(llm.call_cost_usd(usage, dt.datetime(2026, 10, 5, 2, 0, tzinfo=dt.timezone.utc)), 2 * (0.003 + 0.15 + 0.6))
        self.assertEqual(llm.usage_tokens({"prompt_tokens": 7, "completion_tokens": 3})["input_cache_miss"], 7)
        self.assertAlmostEqual(llm.EXPECTED_PEAK_FACTOR, 1.0 + 35.0 / 168.0)


class KeyAndTransportTests(TempDir):
    def test_the_key_comes_from_the_environment_or_its_owner_only_file_and_is_never_shown(self) -> None:
        self.assertEqual(llm.load_api_key({llm.KEY_ENV: " sk-env "}), "sk-env")
        path = self.tmp / "deepseek.env"
        path.write_text("# key\nexport DEEPSEEK_API_KEY='sk-file'\n", encoding="utf-8")
        os.chmod(path, 0o600)
        self.assertEqual(llm.load_api_key({llm.KEY_FILE_ENV: str(path)}), "sk-file")
        with self.assertRaises(llm.LlmOpError) as caught:
            llm.load_api_key({llm.KEY_FILE_ENV: str(self.tmp / "missing.env")})
        self.assertEqual(str(caught.exception), "api_key_missing")
        if os.name == "posix":
            os.chmod(path, 0o644)
            with self.assertRaises(llm.LlmOpError) as caught:
                llm.load_api_key({llm.KEY_FILE_ENV: str(path)})
            self.assertEqual(str(caught.exception), "api_key_file_readable_by_others")
        transport = llm.HttpTransport(api_key="sk-secret", opener=lambda request, timeout: None)
        self.assertNotIn("sk-secret", repr(transport))

    def test_the_transport_posts_the_body_with_the_key_in_one_header_and_maps_errors(self) -> None:
        seen: list[Any] = []

        class Reply:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"ok": true}'

        def opener(request, timeout):
            seen.append((request, timeout))
            return Reply()

        body = llm.request_body([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}])
        self.assertEqual(body, {"model": llm.MODEL, "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                                "thinking": {"type": "enabled"}, "stream": False})
        for name in llm.NOT_SENT:
            self.assertNotIn(name, body)
        status, text = llm.HttpTransport(api_key="sk-k", opener=opener).post(body)
        self.assertEqual((status, text), (200, '{"ok": true}'))
        request = seen[0][0]
        self.assertEqual((request.get_method(), request.full_url), ("POST", llm.ENDPOINT))
        self.assertEqual(request.get_header("Authorization"), "Bearer sk-k")
        self.assertEqual(json.loads(request.data), body)

        def http_error(request, timeout):
            raise urllib.error.HTTPError(llm.ENDPOINT, 503, "busy", {}, None)

        self.assertEqual(llm.HttpTransport(api_key="sk-k", opener=http_error).post(body)[0], 503)

        def offline(request, timeout):
            raise urllib.error.URLError("no route")

        with self.assertRaises(llm.TransportError) as caught:
            llm.HttpTransport(api_key="sk-k", opener=offline).post(body)
        self.assertEqual(str(caught.exception), "URLError")


class CallerTests(TempDir):
    MESSAGES = [{"role": "system", "content": "instruction"}, {"role": "user", "content": "table"}]

    def test_a_live_answer_is_archived_before_use_and_a_replay_needs_no_api(self) -> None:
        transport = ScriptedTransport([(200, response("f1 -> BIRTH\n"))])
        record = caller(self.tmp, transport=transport).ask("association", 7, 1, self.MESSAGES)
        self.assertFalse(record["replayed"])
        self.assertEqual(record["response"]["content"], "f1 -> BIRTH\n")
        self.assertEqual(record["request_sha256"], llm.request_sha256(llm.request_body(self.MESSAGES)))
        self.assertAlmostEqual(record["cost_usd"], (800 * 0.003 + 200 * 0.15 + 300 * 0.6) / 1e6)
        lines = (self.tmp / "a.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["type"] for line in lines], ["call"])
        ledger = json.loads((self.tmp / "a.jsonl.ledger.json").read_text(encoding="utf-8"))
        self.assertEqual((ledger["calls"], ledger["last_tick"]), (1, 7))
        self.assertNotIn("instruction", lines[0])  # the archive keeps the request digest, not the request
        replay = caller(self.tmp, mode="replay", name="a.jsonl").ask("association", 7, 1, self.MESSAGES)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["response"], record["response"])
        with self.assertRaises(llm.ArchiveProblem) as caught:
            caller(self.tmp, mode="replay", name="a.jsonl").ask("association", 7, 2, self.MESSAGES)
        self.assertEqual(caught.exception.detail, "replay_miss:association:7:2")
        with self.assertRaises(llm.ArchiveProblem) as caught:
            caller(self.tmp, mode="replay", name="a.jsonl").ask("association", 7, 1, [self.MESSAGES[0], {"role": "user", "content": "other"}])
        self.assertEqual(caught.exception.detail, "archive_request_mismatch:association:7:1")

    def test_service_errors_back_off_are_archived_and_never_count_as_answers(self) -> None:
        sleeps: list[float] = []
        transport = ScriptedTransport([(429, {"error": {"message": "slow down"}}), (503, "busy"), llm.TransportError("TimeoutError"),
                                       (200, "not json"), (200, response("", finish="insufficient_system_resource")),
                                       (200, response("f1 -> BIRTH\n"))])
        record = caller(self.tmp, transport=transport, sleeps=sleeps).ask("association", 3, 1, self.MESSAGES)
        self.assertEqual(record["response"]["content"], "f1 -> BIRTH\n")
        self.assertEqual(sleeps, [2.0, 4.0, 8.0, 16.0, 32.0])
        rows = [json.loads(line) for line in (self.tmp / "a.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["type"] for row in rows], ["service_error"] * 5 + ["call"])
        self.assertEqual(rows[0]["error"], "slow down")
        self.assertEqual(rows[2]["transport_error"], "TimeoutError")
        self.assertGreater(rows[4]["cost_usd"], 0.0)  # a cut-short answer is paid for and accounted
        with mock.patch.object(llm, "SERVICE_RETRY_LIMIT_S", 3.0):
            with self.assertRaises(llm.ServiceUnavailable):
                caller(self.tmp, transport=ScriptedTransport([(500, "x")] * 5), name="b.jsonl").ask("existence", 3, 1, self.MESSAGES)

    def test_a_fatal_answer_or_a_stop_file_stops_and_a_changed_model_stops_live_and_in_replay(self) -> None:
        with self.assertRaises(llm.ApiFatal) as caught:
            caller(self.tmp, transport=ScriptedTransport([(402, {"error": {"message": "Insufficient Balance"}})])).ask("association", 1, 1, self.MESSAGES)
        self.assertEqual(caught.exception.detail, "http_402:Insufficient Balance")
        self.assertEqual(caught.exception.exit_code, llm.EXIT_API_FATAL)
        (self.tmp / llm.STOP_FILE).write_text("safety_stop_usd:200", encoding="utf-8")
        transport = ScriptedTransport()
        with self.assertRaises(llm.Stopped):
            caller(self.tmp, transport=transport, name="c.jsonl").ask("association", 1, 1, self.MESSAGES)
        self.assertEqual(transport.bodies, [])
        (self.tmp / llm.STOP_FILE).unlink()
        with self.assertRaises(llm.ModelChanged):
            caller(self.tmp, transport=ScriptedTransport([(200, response("x", model="deepseek-v4.2-flash"))]), expected=SERVED,
                   name="d.jsonl").ask("association", 1, 1, self.MESSAGES)
        self.assertEqual(len(llm.CallArchive(self.tmp / "d.jsonl").calls), 1)  # paid for, so kept
        with self.assertRaises(llm.ModelChanged):
            caller(self.tmp, mode="replay", expected=SERVED, name="d.jsonl").ask("association", 1, 1, self.MESSAGES)

    def test_a_cut_off_line_is_dropped_and_recorded_and_a_repeated_call_is_refused(self) -> None:
        caller(self.tmp, transport=ScriptedTransport([(200, response("f -> BIRTH\n"))])).ask("association", 1, 1, self.MESSAGES)
        path = self.tmp / "a.jsonl"
        with open(path, "a", encoding="utf-8") as handle:
            handle.write('{"type": "call", "kind": "assoc')
        archive = llm.CallArchive(path)
        self.assertEqual(len(archive.calls), 1)
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[-1]["type"], "repair")
        self.assertGreater(rows[-1]["dropped_bytes"], 0)
        good = path.read_text(encoding="utf-8").splitlines()[0]
        (self.tmp / "e.jsonl").write_text(good + "\n" + good + "\n", encoding="utf-8")
        with self.assertRaises(llm.ArchiveProblem):
            llm.CallArchive(self.tmp / "e.jsonl")


class ScriptedCaller:
    """A caller that hands the scorer prepared answers (to count attempts and fallbacks without an archive)."""

    def __init__(self, answers: list[tuple[str, str]]) -> None:
        self.answers = list(answers)
        self.asked: list[tuple[str, int, int]] = []
        self.models_seen = {SERVED}
        self.expected_model = None
        self.mode = "live"

    def ask(self, kind: str, tick: int, attempt: int, messages: Any) -> dict[str, Any]:
        self.asked.append((kind, tick, attempt))
        content, finish = self.answers.pop(0)
        return {"response": {"content": content, "finish_reason": finish, "usage": {}}, "cost_usd": 0.001, "latency_s": 1.0,
                "replayed": False}


class ScorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stage_a, self.rows, self.order, self.ids = stage_a_and_rows()
        self.good = "".join(f"{f} -> BIRTH\n" for f in self.stage_a["rows"])

    def test_the_split_guard_allows_validation_and_the_train_pilot_of_at_most_200_frames(self) -> None:
        llm.LlmOpScorer(ScriptedCaller([]), split="validation")
        llm.LlmOpScorer(ScriptedCaller([]), split="train", pilot=True, frames=200)
        for kwargs, code in (({"split": "train"}, "split_not_allowed:LLM-op:train"), ({"split": "test"}, "split_not_allowed:LLM-op:test"),
                             ({"split": "train", "pilot": True, "frames": 201}, "pilot_frames_not_allowed"),
                             ({"split": "validation", "pilot": True, "frames": 10}, "pilot_split_not_allowed:validation")):
            with self.subTest(kwargs=kwargs), self.assertRaises((arms.LeanArmsError, llm.LlmOpError)) as caught:
                llm.LlmOpScorer(ScriptedCaller([]), **kwargs)
            self.assertEqual(str(caught.exception), code)

    def test_invalid_answers_are_asked_again_and_the_third_falls_back(self) -> None:
        scripted = ScriptedCaller([("", "stop"), ("half", "length"), (self.good, "stop")])
        scorer = llm.LlmOpScorer(scripted, split="validation")
        logits = scorer.association_and_birth_logits(self.stage_a)
        self.assertEqual([a[2] for a in scripted.asked], [1, 2, 3])
        self.assertEqual(logits["birth_logits"], {f: 0.0 for f in self.stage_a["rows"]})
        stats = scorer.summary()["association"]
        self.assertEqual((stats["calls"], stats["attempts"], stats["fallbacks"], stats["invalid"]), (1, 3, 0, {"empty": 1, "truncated": 1}))
        scripted.answers = [("nonsense", "stop"), ("f -> e", "content_filter"), ("", "stop")]
        mug = self.ids["mug"]
        decisions = scorer.existence_decisions([r for r in self.rows if r["entity_id"] == mug], self.order)
        self.assertEqual(decisions, {mug: "NOOP"})
        stats = scorer.summary()["existence"]
        self.assertEqual((stats["fallbacks"], stats["fallback_ticks"], stats["fallback_rate"]), (1, [int(self.stage_a["tick"])], 1.0))
        self.assertEqual(stats["invalid"], {"content_filter": 1, "empty": 1, "unparseable:line": 1})

    def test_a_call_without_rows_is_not_asked_and_existence_comes_after_association(self) -> None:
        scripted = ScriptedCaller([])
        scorer = llm.LlmOpScorer(scripted, split="validation")
        with self.assertRaises(llm.LlmOpError):
            scorer.existence_decisions(self.rows, self.order)
        empty = {**self.stage_a, "rows": [], "association_rows": [], "birth_rows": [], "recall": {}}
        self.assertEqual(scorer.association_and_birth_logits(empty), {"association_logits": {}, "birth_logits": {}})
        self.assertEqual(scorer.existence_decisions([], self.order), {})
        self.assertEqual(scripted.asked, [])
        self.assertEqual(scorer.summary()["association"]["skipped_without_rows"], 1)


class ProjectionTests(unittest.TestCase):
    def test_the_projection_prices_rows_not_frames(self) -> None:
        pilot = {"association": {"rows": 100, "tokens": {"input_cache_hit": 0, "input_cache_miss": 1_000_000, "output": 0, "reasoning": 0}},
                 "existence": {"rows": 50, "tokens": {"input_cache_hit": 0, "input_cache_miss": 0, "output": 1_000_000, "reasoning": 0}}}
        projection = llm.project_cost(pilot, planned_frames=1000, rows_per_frame={"association_rows": 90.0, "existence_rows": 36.0})
        per_frame = 0.15 / 100 * 90 + 0.6 / 50 * 36
        self.assertAlmostEqual(projection["usd_per_frame_off_peak"], per_frame)
        self.assertAlmostEqual(projection["projected_usd_expected"], per_frame * 1000 * llm.EXPECTED_PEAK_FACTOR)


class RunnerIntegrationTests(TempDir):
    def test_llm_op_runs_through_the_runner_and_a_replay_reproduces_its_trajectory_without_a_call(self) -> None:
        def run(call: llm.LlmCaller) -> tuple[list[dict[str, Any]], llm.LlmOpScorer]:
            scorer = llm.LlmOpScorer(call, split="validation")
            steps = list(lr.run_episode(scenario(), episode_id="ep-0001", arm=llm.ARM, config={}, policy=POLICY,
                                        descriptor=la.FROZEN_DESCRIPTOR_BASELINE, scorer=scorer))
            return [s["receipt"] for s in steps], scorer

        transport = ScriptedTransport()
        live, scorer = run(caller(self.tmp, transport=transport, expected=SERVED))
        atoms = {atom: sum(r["program"]["atom_counts"][atom] for r in live) for atom in arms.ATOMS}
        self.assertEqual(atoms["BIRTH"], 2)
        self.assertGreater(atoms["BIND"], 0)
        self.assertGreater(atoms["NOOP"] + atoms["RETRACT"], 0)
        self.assertTrue(all(r["illegal_program"] is None for r in live))
        summary = scorer.summary()
        self.assertEqual(summary["association"]["calls"], 5)
        self.assertEqual(len(transport.bodies), summary["association"]["attempts"] + summary["existence"]["attempts"])
        self.assertEqual(summary["models_seen"], [SERVED])
        for body in transport.bodies:  # only the registered instruction and the frame's tables are sent
            self.assertIn(body["messages"][0]["content"], (lc.ASSOCIATION_INSTRUCTION, lc.EXISTENCE_INSTRUCTION))
            self.assertIn(body["messages"][1]["content"].splitlines()[0], ("CANDIDATES", "ENTITIES"))
        scorer.close()  # on Linux the archive's flock would otherwise refuse the replay's own open
        replayed, again = run(caller(self.tmp, mode="replay", expected=SERVED))
        self.assertEqual(audit_module.trajectory_sha256(replayed), audit_module.trajectory_sha256(live))
        self.assertEqual(again.summary()["association"]["replayed_attempts"], again.summary()["association"]["attempts"])


if __name__ == "__main__":
    unittest.main()
