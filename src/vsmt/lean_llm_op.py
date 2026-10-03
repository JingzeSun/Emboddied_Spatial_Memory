"""Ruling 105 (2026-10-04): the LLM-op appendix arm against the DeepSeek API -- contract, prices, calls, archive and scorer.

LLM-op asks a frozen general LLM to make the five-atom decisions from the same sealed feature tables every arm reads
(S0-05 ``appendix_arm``, METHOD section 8).  Ruling 105 fixed how: DeepSeek ``deepseek-flash`` (served as V4.1-Flash on
2026-10-04) in its default thinking mode, two calls per frame (association, then existence after the solve; the
rendering, the two instructions and the strict parsers live in ``lean_controls``), at most three answers per call and
then the fallback, every request and response appended to an archive that a rerun replays without calling the API, one
model name per run, a train pilot of 200 frames before anything else, a $150 cap and a $200 safety stop, validation
only for the runs of record.  This module holds the parts that touch the network or keep state across calls:

1. **The stage contract** (``configs/vsmt/lean_s3_03_llm_op_v1.json``): every value above, bound to the constants here
   and to the instruction digest in ``lean_controls``; the authorization bits open only by a ruling named in
   ``activation_policy`` (the S2 pattern), so code that has not been reviewed cannot spend money.
2. **Prices** (USD per million tokens, read off the pricing page on 2026-10-04): input cache hit 0.003, cache miss
   0.15, output 0.6; twice that from 01:00 to 04:00 and from 06:00 to 10:00 UTC, Monday to Friday.  DeepSeek also
   charges the off-peak price on Chinese public holidays; the ledger does not model holidays, so it can only overstate.
3. **The key**: from ``DEEPSEEK_API_KEY`` or from the file ``DEEPSEEK_API_KEY_FILE`` names (default
   ``/root/.config/vsmt/deepseek.env``, a line ``DEEPSEEK_API_KEY=...``, readable by its owner only).  It goes into one
   request header and nowhere else: not argv, not the archive, not a log, not an exception.
4. **The caller**: one request body per call (model, the two messages, thinking enabled, nothing else -- effort,
   output limit and sampling stay at the provider's defaults), retried with exponential backoff on 408 / 429 / 5xx,
   a network error, an unparseable body or a ``finish_reason`` of ``insufficient_system_resource`` / ``aborted``
   (none of which is an answer); any other 4xx stops the run.  Every response is appended to the archive with its
   usage and cost before it is used; a record already in the archive is replayed (its request digest must match).
5. **The scorer** the S2-01 runner calls: ``association_and_birth_logits`` (the learned-arm interface) and
   ``existence_decisions``; each call takes at most three answers, an answer is invalid when it is empty, truncated,
   filtered or unparseable, and the third invalid one sends the frame to the fallback.  Counts, tokens, cost and
   latency per call kind go into the run's payload.

白话：附录臂 LLM-op 让一个冻结的通用大模型，直接看和其他臂完全相同的封存特征表来做五原子决定。裁决 105 定了怎么调：
DeepSeek ``deepseek-flash``（2026-10-04 实际是 V4.1-Flash），默认推理模式；每帧问两次（先关联、求解后再判存在）；每次
最多要三个回答，三次都无效就回退；每个请求和回答先存档再用，重跑从存档回放、不再花钱；一趟只认一个模型名；先在 train
上试点 200 帧；费用到 150 美元不再开新 episode，到 200 美元全部停；正式运行只在 validation 上。本模块管合同、计价、
密钥、网络调用、存档和给 runner 的打分器。例如某帧关联回答被截断，就同一请求再问；第三次还不行，这一帧的色块全记
BIRTH 并计一次回退。它不训练、不读私有数据，密钥只进请求头。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cpmt.hashing import canonical_json

from vsmt import lean_arms as arms
from vsmt import lean_controls as lc

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "configs" / "vsmt" / "lean_s3_03_llm_op_v1.json"
SCHEMA_VERSION = "vsmt-lean-s3-03-llm-op-v1"
STAGE_ID = "S3-03-LLM-op"
RULING = "105"
ARM = arms.APPENDIX_ARM

#: 105-1: both front ends, each against its own cache and ReID head.
FRONTS = {"instance": "simulator_instance_masks", "sam2": "sam2"}
#: 105-2: fifteen validation episodes, the same for both front ends, in the order of sha256(salt + episode id).
EPISODES_PER_FRONT = 15
DRAW_SALT = "vsmt-lean-llm-op-105-2|"
#: 105-3 / 105-7: the request.
ENDPOINT = "https://api.deepseek.com/chat/completions"
MODELS_ENDPOINT = "https://api.deepseek.com/models"
MODEL = "deepseek-flash"
THINKING = {"type": "enabled"}
NOT_SENT = ("reasoning_effort", "max_tokens", "temperature", "top_p", "presence_penalty", "frequency_penalty", "response_format")
#: 105-6: answers, retries and the fallback.
ATTEMPTS_PER_CALL = 3
FORMAT_UNRELIABLE_FALLBACK_RATE = 0.02
INVALID_FINISH = {"length": "truncated", "content_filter": "content_filter", "tool_calls": "tool_calls"}
SERVICE_FINISH = ("insufficient_system_resource", "aborted")
BACKOFF_FIRST_S = 2.0
BACKOFF_MAX_S = 300.0
SERVICE_RETRY_LIMIT_S = 6 * 3600.0
REQUEST_TIMEOUT_S = 1800.0
#: 105-8: the pilot, the cap and the safety stop.
PILOT_SPLIT = "train"
PILOT_FRAMES = 200
CAP_USD = 150.0
SAFETY_STOP_USD = 200.0
#: Prices in USD per million tokens, off peak (2026-10-04, https://api-docs.deepseek.com/quick_start/pricing).
PRICES_OFF_PEAK = {"input_cache_hit": 0.003, "input_cache_miss": 0.15, "output": 0.6}
PEAK_MULTIPLIER = 2.0
PEAK_WINDOWS_UTC = (("01:00", "04:00"), ("06:00", "10:00"))
PEAK_WEEKDAYS = (0, 1, 2, 3, 4)
#: The share of a week's hours at the peak price (5 days x 7 hours / 168 hours), for the pilot's projection.
EXPECTED_PEAK_FACTOR = 1.0 + (PEAK_MULTIPLIER - 1.0) * (len(PEAK_WEEKDAYS) * 7.0) / 168.0
#: 105-10: the key never leaves the request header.
KEY_ENV = "DEEPSEEK_API_KEY"
KEY_FILE_ENV = "DEEPSEEK_API_KEY_FILE"
DEFAULT_KEY_FILE = "/root/.config/vsmt/deepseek.env"
#: Files in a run root the processes share.
STOP_FILE = "STOP"
MODEL_FILE = "model.json"
#: Exit codes of an LLM-op process (the driver tells a stop from a failure by them).
EXIT_STOPPED = 75
EXIT_MODEL_CHANGED = 76
EXIT_API_FATAL = 77
EXIT_SERVICE_UNAVAILABLE = 78
EXIT_ARCHIVE = 79
AUTHORIZATION_BITS = ("pilot_run", "validation_run")


class LlmOpError(ValueError):
    """Raised with a short machine-readable code."""


class LlmOpStop(RuntimeError):
    """A condition that stops the process with its own exit code; the run stays resumable from the archive."""

    exit_code = 1

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class Stopped(LlmOpStop):
    exit_code = EXIT_STOPPED


class ModelChanged(LlmOpStop):
    exit_code = EXIT_MODEL_CHANGED


class ApiFatal(LlmOpStop):
    exit_code = EXIT_API_FATAL


class ServiceUnavailable(LlmOpStop):
    exit_code = EXIT_SERVICE_UNAVAILABLE


class ArchiveProblem(LlmOpStop):
    exit_code = EXIT_ARCHIVE


class TransportError(RuntimeError):
    """A request that got no HTTP answer (network, timeout); the message names the error type only."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LlmOpError(code)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# --------------------------------------------------------------------------
# 1. the stage contract
# --------------------------------------------------------------------------

def expected_contract_values() -> dict[str, Any]:
    """The values the contract must carry, path by path, from the constants of this module and ``lean_controls``."""

    return {
        "schema_version": SCHEMA_VERSION,
        "stage_id": STAGE_ID,
        "ruling": RULING,
        "arm": ARM,
        "fronts": dict(FRONTS),
        "validation_scope.episodes_per_front": EPISODES_PER_FRONT,
        "validation_scope.draw_salt": DRAW_SALT,
        "validation_scope.same_episodes_for_both_fronts": True,
        "request.endpoint": ENDPOINT,
        "request.model": MODEL,
        "request.thinking": dict(THINKING),
        "request.stream": False,
        "request.not_sent": list(NOT_SENT),
        "request.repeats": 1,
        "input.instruction_sha256": lc.INSTRUCTION_SHA256,
        "input.rendering_rule": lc.RENDERING_RULE,
        "input.text_decimals": lc.TEXT_DECIMALS,
        "input.calls_per_frame": list(lc.CALL_KINDS),
        "input.skip_a_call_without_rows": True,
        "input.few_shot": False,
        "answers.attempts_per_call": ATTEMPTS_PER_CALL,
        "answers.fallback.association": "BIRTH for every fragment of the frame",
        "answers.fallback.existence": "NOOP for every eligible entity of the frame",
        "answers.format_unreliable_fallback_rate": FORMAT_UNRELIABLE_FALLBACK_RATE,
        "answers.invalid_finish_reasons": dict(INVALID_FINISH),
        "answers.service_finish_reasons": list(SERVICE_FINISH),
        "answers.backoff_s": [BACKOFF_FIRST_S, BACKOFF_MAX_S],
        "answers.service_retry_limit_s": SERVICE_RETRY_LIMIT_S,
        "record.one_model_name_per_run": True,
        "record.replay_never_calls_the_api": True,
        "pilot.split": PILOT_SPLIT,
        "pilot.frames": PILOT_FRAMES,
        "pilot.episodes": 1,
        "pilot.computes_metrics": False,
        "cost.cap_usd": CAP_USD,
        "cost.safety_stop_usd": SAFETY_STOP_USD,
        "cost.prices_off_peak_usd_per_million_tokens": dict(PRICES_OFF_PEAK),
        "cost.peak_multiplier": PEAK_MULTIPLIER,
        "cost.peak_windows_utc": [list(window) for window in PEAK_WINDOWS_UTC],
        "cost.peak_weekdays": list(PEAK_WEEKDAYS),
        "secrets.key_env": KEY_ENV,
        "secrets.key_file_env": KEY_FILE_ENV,
        "secrets.default_key_file": DEFAULT_KEY_FILE,
        "secrets.never_in_argv_log_or_archive": True,
    }


def _lookup(tree: Mapping[str, Any], path: str) -> Any:
    node: Any = tree
    for part in path.split("."):
        _require(isinstance(node, Mapping) and part in node, f"contract_path_missing:{path}")
        node = node[part]
    return node


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Every registered value equals the code's; an authorization bit is true only when the activation policy names it."""

    _require(isinstance(contract, Mapping), "contract_not_object")
    for path, expected in expected_contract_values().items():
        _require(_lookup(contract, path) == expected, f"contract_value_mismatch:{path}")
    bits = contract.get("authorization")
    _require(isinstance(bits, Mapping) and tuple(bits) == AUTHORIZATION_BITS, "contract_authorization_bits_mismatch")
    policy = contract.get("activation_policy")
    opened = set(policy.get("active_true_authorizations") or ()) if isinstance(policy, Mapping) else set()
    if opened:
        _require(isinstance(policy.get("opened_by"), str) and bool(policy["opened_by"]), "contract_activation_policy_names_no_ruling")
    for name, value in bits.items():
        _require(type(value) is bool, f"contract_authorization_not_boolean:{name}")
        _require(value is False or name in opened, f"contract_bit_opened_without_a_ruling:{name}")
    return json.loads(json.dumps(contract))


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return validate_contract(json.loads(Path(path).read_text(encoding="utf-8")))


def authorized(contract: Mapping[str, Any], bit: str) -> bool:
    _require(bit in AUTHORIZATION_BITS, f"authorization_bit_unknown:{bit}")
    return contract["authorization"][bit] is True


# --------------------------------------------------------------------------
# 2. prices
# --------------------------------------------------------------------------

def _minutes(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def is_peak(when: dt.datetime) -> bool:
    """Whether DeepSeek charges the peak price at this instant (Chinese public holidays are not modelled)."""

    _require(when.tzinfo is not None, "time_without_zone")
    utc = when.astimezone(dt.timezone.utc)
    if utc.weekday() not in PEAK_WEEKDAYS:
        return False
    minute = utc.hour * 60 + utc.minute
    return any(_minutes(start) <= minute < _minutes(end) for start, end in PEAK_WINDOWS_UTC)


def usage_tokens(usage: Mapping[str, Any] | None) -> dict[str, int]:
    """Input split into cache hit and miss (a response without the split counts every input token as a miss), output, reasoning."""

    usage = usage or {}
    hit = int(usage.get("prompt_cache_hit_tokens") or 0)
    miss = int(usage.get("prompt_cache_miss_tokens") or 0)
    if hit + miss == 0:
        miss = int(usage.get("prompt_tokens") or 0)
    details = usage.get("completion_tokens_details") or {}
    return {"input_cache_hit": hit, "input_cache_miss": miss, "output": int(usage.get("completion_tokens") or 0),
            "reasoning": int(details.get("reasoning_tokens") or 0) if isinstance(details, Mapping) else 0}


def off_peak_cost_usd(tokens: Mapping[str, int]) -> float:
    return sum(float(tokens[name]) * PRICES_OFF_PEAK[name] for name in PRICES_OFF_PEAK) / 1.0e6


def call_cost_usd(usage: Mapping[str, Any] | None, when: dt.datetime) -> float:
    """What one response costs at the price of the instant it was asked (reasoning tokens are part of the output)."""

    return off_peak_cost_usd(usage_tokens(usage)) * (PEAK_MULTIPLIER if is_peak(when) else 1.0)


# --------------------------------------------------------------------------
# 3. the key
# --------------------------------------------------------------------------

def load_api_key(environ: Mapping[str, str] | None = None) -> str:
    """The API key from the environment or from its owner-only file; a refusal never quotes the key."""

    environ = os.environ if environ is None else environ
    value = (environ.get(KEY_ENV) or "").strip()
    if value:
        return value
    path = Path(environ.get(KEY_FILE_ENV) or DEFAULT_KEY_FILE)
    _require(path.is_file(), "api_key_missing")
    if os.name == "posix":
        _require(path.stat().st_mode & 0o077 == 0, "api_key_file_readable_by_others")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if line.startswith(f"{KEY_ENV}="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if key:
                return key
    raise LlmOpError("api_key_missing")


# --------------------------------------------------------------------------
# 4. requests, the transport, the archive and the caller
# --------------------------------------------------------------------------

def request_body(messages: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    """Ruling 105-3: the model, the messages and thinking enabled; everything else stays at the provider's default."""

    return {"model": MODEL, "messages": [{"role": str(m["role"]), "content": str(m["content"])} for m in messages],
            "thinking": dict(THINKING), "stream": False}


def request_sha256(body: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(dict(body)).encode("utf-8")).hexdigest()


class HttpTransport:
    """POST and GET against the API with the key in one header; nothing else of the request is logged anywhere."""

    def __init__(self, *, api_key: str, endpoint: str = ENDPOINT, timeout_s: float = REQUEST_TIMEOUT_S,
                 opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        _require(bool(api_key), "api_key_missing")
        self._key = api_key
        self.endpoint = endpoint
        self.timeout_s = float(timeout_s)
        self._opener = opener

    def __repr__(self) -> str:  # the key never reaches a repr either
        return f"HttpTransport(endpoint={self.endpoint!r})"

    def _send(self, request: urllib.request.Request) -> tuple[int, str]:
        try:
            with self._opener(request, timeout=self.timeout_s) as response:
                return int(response.status), response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            try:
                text = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 -- an unreadable error body is just empty
                text = ""
            return int(exc.code), text
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise TransportError(type(exc).__name__) from None

    def post(self, body: Mapping[str, Any]) -> tuple[int, str]:
        request = urllib.request.Request(self.endpoint, data=json.dumps(body).encode("utf-8"), method="POST", headers={
            "Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {self._key}"})
        return self._send(request)

    def get(self, url: str) -> tuple[int, str]:
        request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json", "Authorization": f"Bearer {self._key}"})
        return self._send(request)


class CallArchive:
    """Append-only JSON lines for one (front end, episode) or one pilot: every response before it is used, every service error.

    A ``call`` record is keyed by (kind, tick, attempt) and replayed by that key when its request digest matches; a
    ``service_error`` record only accounts for time and money.  A line cut off by a killed process is dropped on the next
    open and the drop is itself recorded.  ``<archive>.ledger.json`` keeps the running cost for the driver to read cheaply.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.calls: dict[tuple[str, int, int], dict[str, Any]] = {}
        self.cost_usd = 0.0
        self.records = 0
        self.service_errors = 0
        self.last_tick: int | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = None
        try:  # one process per archive: a second run of the same episode would interleave its lines
            import fcntl
        except ImportError:  # not POSIX (the local tests): no lock to take
            fcntl = None
        if fcntl is not None:
            self._lock = open(self.path.with_name(self.path.name + ".lock"), "a")
            try:
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self._lock.close()
                raise ArchiveProblem(f"archive_in_use:{self.path.name}") from None
        if self.path.exists():
            raw = self.path.read_bytes()
            keep = raw if raw.endswith(b"\n") or not raw else raw[: raw.rfind(b"\n") + 1]
            if len(keep) != len(raw):
                with open(self.path, "r+b") as handle:
                    handle.truncate(len(keep))
            for number, line in enumerate(keep.decode("utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    raise ArchiveProblem(f"archive_line_unreadable:{self.path.name}:{number}") from None
                self._index(record)
            if len(keep) != len(raw):
                self.append({"type": "repair", "dropped_bytes": len(raw) - len(keep), "utc": utc_now().isoformat()})

    def _index(self, record: Mapping[str, Any]) -> None:
        self.records += 1
        self.cost_usd += float(record.get("cost_usd") or 0.0)
        if record.get("type") == "call":
            key = (str(record["kind"]), int(record["tick"]), int(record["attempt"]))
            if key in self.calls:
                raise ArchiveProblem(f"archive_call_repeated:{key}")
            self.calls[key] = dict(record)
            self.last_tick = int(record["tick"]) if self.last_tick is None else max(self.last_tick, int(record["tick"]))
        elif record.get("type") == "service_error":
            self.service_errors += 1

    def lookup(self, kind: str, tick: int, attempt: int) -> dict[str, Any] | None:
        return self.calls.get((str(kind), int(tick), int(attempt)))

    def close(self) -> None:
        """Release the archive's lock (a flock binds the open file, so a second open in the same process waits for this)."""

        if self._lock is not None:
            self._lock.close()
            self._lock = None

    def append(self, record: Mapping[str, Any]) -> None:
        line = json.dumps(dict(record), sort_keys=True, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._index(record)
        ledger = {"archive": self.path.name, "cost_usd": round(self.cost_usd, 6), "records": self.records, "calls": len(self.calls),
                  "service_errors": self.service_errors, "last_tick": self.last_tick, "updated_utc": utc_now().isoformat()}
        tmp = self.path.with_name(self.path.name + ".ledger.json.tmp")
        tmp.write_text(json.dumps(ledger), encoding="utf-8")
        tmp.replace(self.path.with_name(self.path.name + ".ledger.json"))


def _error_text(text: str) -> str:
    try:
        payload = json.loads(text)
        message = payload.get("error", {}).get("message") if isinstance(payload, Mapping) else None
    except ValueError:
        message = None
    return str(message or text or "")[:200].replace("\n", " ")


class LlmCaller:
    """One answer per ``ask``: replayed from the archive when there, else asked live (``mode="live"``) and archived first."""

    def __init__(self, *, archive: CallArchive, mode: str, transport: Any = None, expected_model: str | None = None,
                 stop_path: Path | None = None, sleep: Callable[[float], None] = time.sleep,
                 now: Callable[[], dt.datetime] = utc_now, clock: Callable[[], float] = time.monotonic) -> None:
        _require(mode in ("live", "replay"), f"caller_mode_unknown:{mode}")
        _require(mode == "replay" or transport is not None, "live_caller_without_transport")
        self.archive = archive
        self.mode = mode
        self.transport = transport
        self.expected_model = expected_model
        self.stop_path = Path(stop_path) if stop_path is not None else None
        self._sleep, self._now, self._clock = sleep, now, clock
        self.models_seen: set[str] = set()

    def close(self) -> None:
        self.archive.close()

    def _check_stop(self) -> None:
        if self.stop_path is not None and self.stop_path.exists():
            raise Stopped(f"stop_file:{self.stop_path.read_text(encoding='utf-8', errors='replace').strip()[:200]}")

    def _check_model(self, name: Any) -> None:
        self.models_seen.add(str(name))
        if self.expected_model is not None and str(name) != self.expected_model:
            raise ModelChanged(f"model_changed:{name}:expected:{self.expected_model}")

    def ask(self, kind: str, tick: int, attempt: int, messages: Sequence[Mapping[str, str]]) -> dict[str, Any]:
        _require(kind in lc.CALL_KINDS, f"call_kind_unknown:{kind}")
        body = request_body(messages)
        digest = request_sha256(body)
        record = self.archive.lookup(kind, tick, attempt)
        if record is not None:
            if record["request_sha256"] != digest:
                raise ArchiveProblem(f"archive_request_mismatch:{kind}:{tick}:{attempt}")
            self._check_model(record["response"]["model"])
            return {**record, "replayed": True}
        if self.mode == "replay":
            raise ArchiveProblem(f"replay_miss:{kind}:{tick}:{attempt}")
        waited, delay = 0.0, BACKOFF_FIRST_S
        while True:
            self._check_stop()
            when, started = self._now(), self._clock()
            failure: dict[str, Any] = {}
            try:
                status, text = self.transport.post(body)
            except TransportError as exc:
                status, text, failure = None, "", {"transport_error": str(exc)}
            latency = round(self._clock() - started, 3)
            if status == 200:
                try:
                    payload = json.loads(text)
                    choice = payload["choices"][0]
                    message = choice.get("message") or {}
                    finish = choice.get("finish_reason")
                    usage = payload.get("usage") or {}
                except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                    failure = {"unparseable_body": len(text)}
                else:
                    cost = call_cost_usd(usage, when)
                    if finish in SERVICE_FINISH:
                        failure = {"finish_reason": finish, "usage": usage, "cost_usd": cost}
                    else:
                        record = {
                            "type": "call", "kind": kind, "tick": int(tick), "attempt": int(attempt), "request_sha256": digest,
                            "utc": when.isoformat(), "peak": is_peak(when), "latency_s": latency, "http_status": 200, "cost_usd": cost,
                            "response": {"id": payload.get("id"), "model": payload.get("model"),
                                         "system_fingerprint": payload.get("system_fingerprint"), "finish_reason": finish,
                                         "content": message.get("content") or "", "reasoning_content": message.get("reasoning_content") or "",
                                         "usage": usage},
                        }
                        self.archive.append(record)  # paid for and kept before anything checks or uses it
                        self._check_model(payload.get("model"))
                        return {**record, "replayed": False}
            elif status is not None and status != 408 and status != 429 and status < 500:
                self.archive.append({"type": "service_error", "kind": kind, "tick": int(tick), "attempt": int(attempt), "utc": when.isoformat(),
                                     "http_status": status, "error": _error_text(text), "cost_usd": 0.0, "fatal": True})
                raise ApiFatal(f"http_{status}:{_error_text(text)}")
            elif status is not None:
                failure = {"http_status": status, "error": _error_text(text)}
            self.archive.append({"type": "service_error", "kind": kind, "tick": int(tick), "attempt": int(attempt), "utc": when.isoformat(),
                                 "latency_s": latency, "wait_s": delay, "cost_usd": float(failure.pop("cost_usd", 0.0)), **failure})
            if waited >= SERVICE_RETRY_LIMIT_S:
                raise ServiceUnavailable(f"service_unavailable:{kind}:{tick}:{attempt}:{int(waited)}s")
            self._sleep(delay)
            waited += delay
            delay = min(delay * 2.0, BACKOFF_MAX_S)


# --------------------------------------------------------------------------
# 5. the scorer the S2-01 runner calls
# --------------------------------------------------------------------------

def invalid_reason(response: Mapping[str, Any]) -> str | None:
    """Why an answer cannot be used before it is parsed: a cut-off, filtered or tool-call answer, or no text at all."""

    finish = response.get("finish_reason")
    if finish in INVALID_FINISH:
        return INVALID_FINISH[finish]
    if finish != "stop":
        return f"finish_{finish}"
    if not str(response.get("content") or "").strip():
        return "empty"
    return None


def _percentile(values: Sequence[float], share: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return float(ordered[min(len(ordered) - 1, int(share * (len(ordered) - 1) + 0.5))])


class LlmOpScorer:
    """LLM-op's decisions for ``lean_runner``: association logits through the learned-arm interface, existence decisions directly.

    白话：runner 每帧先调 ``association_and_birth_logits``（没有色块就不问），求解后再调 ``existence_decisions``（没有可判定实体
    就不问）。每次调用最多三个回答，无效（空、截断、被过滤、解析不了）就同一请求再问，第三次仍无效就按裁决 105-6 回退并计数。
    split 守卫：正式运行只许 validation；试点只许 train、至多 200 帧。它没有跨帧状态，整帧回滚时无需回滚它。
    """

    def __init__(self, caller: LlmCaller, *, split: str, pilot: bool = False, frames: int | None = None) -> None:
        if pilot:
            _require(split == PILOT_SPLIT, f"pilot_split_not_allowed:{split}")
            _require(frames is not None and 0 < int(frames) <= PILOT_FRAMES, "pilot_frames_not_allowed")
        else:
            arms.assert_split_allowed(ARM, split)
        self.caller = caller
        self.split = split
        self.pilot = bool(pilot)
        self.tick: int | None = None
        self.stats = {kind: {"frames": 0, "calls": 0, "skipped_without_rows": 0, "attempts": 0, "replayed_attempts": 0,
                             "invalid": {}, "fallbacks": 0, "fallback_ticks": [], "rows": 0,
                             "tokens": {"input_cache_hit": 0, "input_cache_miss": 0, "output": 0, "reasoning": 0},
                             "cost_usd": 0.0, "latencies_s": []} for kind in lc.CALL_KINDS}

    def association_and_birth_logits(self, stage_a: Mapping[str, Any]) -> dict[str, Any]:
        self.tick = int(stage_a["tick"])
        stats = self.stats["association"]
        stats["frames"] += 1
        if not stage_a["rows"]:
            stats["skipped_without_rows"] += 1
            return {"association_logits": {}, "birth_logits": {}}
        stats["rows"] += len(stage_a["rows"]) + len(stage_a["association_rows"])
        choices = self._ask("association", lc.association_messages(stage_a),
                            parse=lambda text: lc.parse_association_answer(text, stage_a),
                            fallback=lambda: lc.fallback_association(stage_a))
        return lc.choices_to_logits(choices, stage_a)

    def existence_decisions(self, eligible: Sequence[Mapping[str, Any]], order: Sequence[str]) -> dict[str, str]:
        _require(self.tick is not None, "existence_asked_before_association")
        stats = self.stats["existence"]
        stats["frames"] += 1
        ids = [str(row["entity_id"]) for row in eligible]
        if not ids:
            stats["skipped_without_rows"] += 1
            return {}
        stats["rows"] += len(ids)
        return self._ask("existence", lc.existence_messages(eligible, order),
                         parse=lambda text: lc.parse_existence_answer(text, ids), fallback=lambda: lc.fallback_existence(ids))

    def _ask(self, kind: str, messages: list[dict[str, str]], *, parse: Callable[[str], dict[str, str]],
             fallback: Callable[[], dict[str, str]]) -> dict[str, str]:
        stats = self.stats[kind]
        stats["calls"] += 1
        for attempt in range(1, ATTEMPTS_PER_CALL + 1):
            record = self.caller.ask(kind, int(self.tick), attempt, messages)
            stats["attempts"] += 1
            stats["replayed_attempts"] += int(bool(record.get("replayed")))
            for name, value in usage_tokens(record["response"].get("usage")).items():
                stats["tokens"][name] += value
            stats["cost_usd"] += float(record.get("cost_usd") or 0.0)
            stats["latencies_s"].append(float(record.get("latency_s") or 0.0))
            reason = invalid_reason(record["response"])
            if reason is None:
                try:
                    return parse(str(record["response"]["content"]))
                except lc.LeanControlsError as exc:
                    reason = "unparseable:" + str(exc).split(":")[1] if str(exc).count(":") >= 1 else "unparseable"
            stats["invalid"][reason] = stats["invalid"].get(reason, 0) + 1
        stats["fallbacks"] += 1
        stats["fallback_ticks"].append(int(self.tick))
        return fallback()

    def close(self) -> None:
        self.caller.close()

    def summary(self) -> dict[str, Any]:
        """Per call kind: frames, calls, attempts, invalid answers by reason, fallbacks, tokens, cost and latency."""

        out: dict[str, Any] = {"split": self.split, "pilot": self.pilot, "models_seen": sorted(self.caller.models_seen),
                               "expected_model": self.caller.expected_model, "mode": self.caller.mode}
        total = 0.0
        for kind, stats in self.stats.items():
            latencies = stats["latencies_s"]
            out[kind] = {**{k: v for k, v in stats.items() if k != "latencies_s"},
                         "invalid": dict(sorted(stats["invalid"].items())), "cost_usd": round(stats["cost_usd"], 6),
                         "fallback_rate": (stats["fallbacks"] / stats["calls"]) if stats["calls"] else None,
                         "latency_s": {"p50": _percentile(latencies, 0.5), "p90": _percentile(latencies, 0.9),
                                       "max": max(latencies) if latencies else None}}
            total += stats["cost_usd"]
        out["cost_usd"] = round(total, 6)
        return out


def make_caller(*, archive_path: Path, mode: str, run_root: Path | None, expected_model: str | None,
                environ: Mapping[str, str] | None = None) -> LlmCaller:
    """The caller an entry builds: live with the key and the run's STOP file, or replay with neither."""

    archive = CallArchive(Path(archive_path))
    if mode == "replay":
        return LlmCaller(archive=archive, mode="replay", expected_model=expected_model)
    _require(run_root is not None, "live_caller_without_run_root")
    transport = HttpTransport(api_key=load_api_key(environ))
    return LlmCaller(archive=archive, mode="live", transport=transport, expected_model=expected_model,
                     stop_path=Path(run_root) / STOP_FILE)


def registered_model(run_root: Path) -> str | None:
    """The model name the pilot registered for this run (``model.json``), or None before the pilot."""

    path = Path(run_root) / MODEL_FILE
    if not path.exists():
        return None
    name = json.loads(path.read_text(encoding="utf-8")).get("model")
    _require(isinstance(name, str) and bool(name), "model_file_invalid")
    return name


# --------------------------------------------------------------------------
# 6. the draw and the projection
# --------------------------------------------------------------------------

def draw_order(episode_ids: Sequence[str]) -> list[str]:
    """Ruling 105-2: ascending sha256(salt + episode id); no outcome, length or content enters the order."""

    return sorted({str(e) for e in episode_ids}, key=lambda e: hashlib.sha256((DRAW_SALT + e).encode("utf-8")).hexdigest())


def project_cost(pilot: Mapping[str, Any], *, planned_frames: int, rows_per_frame: Mapping[str, float]) -> dict[str, Any]:
    """Ruling 105-8: the pilot's tokens per table row, times the rows a full frame carries, times the planned frames.

    The first 200 frames of an episode hold a small memory, so their per-frame cost understates a whole episode's; the
    projection therefore prices rows, not frames: input and output tokens per association row (each candidate row and each
    NEW row) and per existence row, measured in the pilot, applied to ``rows_per_frame`` (association rows assume all 8
    recalled candidates, an upper bound, and existence rows the registered per-frame mean), at off-peak prices and again
    with the expected share of peak hours.
    """

    out: dict[str, Any] = {"planned_frames": int(planned_frames), "rows_per_frame": dict(rows_per_frame), "by_kind": {}}
    per_frame = 0.0
    for kind, rows_key in (("association", "association_rows"), ("existence", "existence_rows")):
        stats = pilot[kind]
        rows = int(stats["rows"])
        tokens = stats["tokens"]
        if rows == 0:
            out["by_kind"][kind] = {"rows": 0, "usd_per_row": None}
            continue
        usd_per_row = off_peak_cost_usd(tokens) / rows
        frame_rows = float(rows_per_frame[rows_key])
        out["by_kind"][kind] = {"rows": rows, "usd_per_row": usd_per_row, "rows_per_frame": frame_rows,
                                "usd_per_frame": usd_per_row * frame_rows}
        per_frame += usd_per_row * frame_rows
    out["usd_per_frame_off_peak"] = per_frame
    out["projected_usd_off_peak"] = per_frame * int(planned_frames)
    out["projected_usd_expected"] = out["projected_usd_off_peak"] * EXPECTED_PEAK_FACTOR
    out["expected_peak_factor"] = EXPECTED_PEAK_FACTOR
    return out


__all__ = [
    "ARM", "ATTEMPTS_PER_CALL", "AUTHORIZATION_BITS", "ApiFatal", "ArchiveProblem", "CAP_USD", "CONTRACT_PATH", "CallArchive",
    "DEFAULT_KEY_FILE", "DRAW_SALT", "ENDPOINT", "EPISODES_PER_FRONT", "EXIT_API_FATAL", "EXIT_ARCHIVE", "EXIT_MODEL_CHANGED",
    "EXIT_SERVICE_UNAVAILABLE", "EXIT_STOPPED", "EXPECTED_PEAK_FACTOR", "FORMAT_UNRELIABLE_FALLBACK_RATE", "FRONTS", "HttpTransport",
    "KEY_ENV", "KEY_FILE_ENV", "LlmCaller", "LlmOpError", "LlmOpScorer", "LlmOpStop", "MODEL", "MODELS_ENDPOINT", "MODEL_FILE",
    "ModelChanged", "PILOT_FRAMES", "PILOT_SPLIT", "PRICES_OFF_PEAK", "SAFETY_STOP_USD", "STAGE_ID", "STOP_FILE", "ServiceUnavailable",
    "Stopped", "TransportError", "authorized", "call_cost_usd", "draw_order", "expected_contract_values", "invalid_reason", "is_peak",
    "load_api_key", "load_contract", "make_caller", "off_peak_cost_usd", "project_cost", "registered_model", "request_body",
    "request_sha256", "usage_tokens", "utc_now", "validate_contract",
]
