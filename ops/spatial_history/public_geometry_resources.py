"""Read-only Linux capacity checks for E0's explicitly requested worker count.

Only the process affinity and visible cgroup hierarchy are inspected. Hidden
host ancestors cannot be measured from a container; this is a conservative
preflight, not a reservation or a guarantee against later resource contention.
Unrecognised mounts, membership, controllers, or missing non-root interfaces
are rejected rather than interpreted as unlimited capacity.
"""
import os
from pathlib import Path, PurePosixPath
import re


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _read_text(path):
    return Path(path).read_text(encoding="utf-8")


def _optional_text(path):
    try:
        return _read_text(path)
    except FileNotFoundError:
        return None


def _path(value):
    _require(value.startswith("/") and "\x00" not in value
             and all(part not in (".", "..") for part in value.split("/")), "invalid cgroup path")
    return PurePosixPath(value)


def _unescape(value):
    # mountinfo escapes whitespace and backslashes with octal sequences.
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def _memberships(text):
    rows = []
    for line in text.splitlines():
        fields = line.split(":", 2)
        _require(len(fields) == 3 and fields[0].isdigit(), "unrecognised /proc/self/cgroup")
        controllers = fields[1].split(",") if fields[1] else []
        _require((fields[0] == "0") == (not controllers), "unsupported cgroup membership")
        rows.append({"version": 2 if not controllers else 1, "controllers": controllers,
                     "path": str(_path(fields[2]))})
    _require(rows, "missing cgroup membership")
    return rows


def _mounts(text):
    rows = []
    for line in text.splitlines():
        parts = line.split(" - ")
        _require(len(parts) == 2, "unrecognised mountinfo")
        left, right = parts[0].split(), parts[1].split()
        _require(len(left) >= 6 and len(right) == 3, "unrecognised mountinfo fields")
        if right[0] not in ("cgroup", "cgroup2"):
            continue
        rows.append({"version": 2 if right[0] == "cgroup2" else 1,
                     "root": str(_path(_unescape(left[3]))),
                     "mountpoint": str(_path(_unescape(left[4]))),
                     "controllers": right[2].split(",")})
    _require(rows, "no supported cgroup mount is visible")
    return rows


def _hierarchy(controller, memberships, mounts):
    selected = [row for row in memberships if controller in row["controllers"]]
    if not selected:
        selected = [row for row in memberships if row["version"] == 2]
    _require(len(selected) == 1, "missing or ambiguous " + controller + " cgroup membership")
    member = selected[0]
    matches = []
    for mount in mounts:
        if mount["version"] != member["version"]:
            continue
        if member["version"] == 1 and controller not in mount["controllers"]:
            continue
        root, point, membership = map(PurePosixPath, (mount["root"], mount["mountpoint"], member["path"]))
        relatives = []
        if membership.is_relative_to(root):
            relatives.append((membership.relative_to(root), "mount_root_relative"))
        # A cgroup namespace may report membership relative to its own root
        # while mountinfo still exposes the mount's underlying subtree root.
        if root != PurePosixPath("/"):
            relatives.append((membership.relative_to("/"), "namespace_relative"))
        seen = set()
        for relative, mapping in relatives:
            current = point / relative
            if str(current) in seen:
                continue
            seen.add(str(current))
            raw = _optional_text(str(current / "cgroup.procs"))
            if raw is None:
                continue
            fields = raw.split()
            _require(all(field.isdigit() for field in fields), "invalid cgroup.procs")
            if str(os.getpid()) not in fields:
                continue
            matches.append({**mount, "membership": member["path"], "current": str(current),
                            "mapping": mapping, "membership_pid_verified": True})
    _require(matches, "cannot verify " + controller + " cgroup mount/member mapping")
    # A root-most visible mount exposes the most ancestor constraints. Equal
    # mount roots are aliases; both map to the membership confirmed above.
    matches.sort(key=lambda item: (len(PurePosixPath(item["root"]).parts), item["mountpoint"]))
    selected = matches[0]
    current, point = PurePosixPath(selected["current"]), PurePosixPath(selected["mountpoint"])
    ancestors = []
    while True:
        ancestors.append(str(current))
        if current == point:
            break
        _require(current.is_relative_to(point) and current != current.parent, "cgroup path escaped mount")
        current = current.parent
    selected["ancestors"] = ancestors
    selected["scope"] = "all identifiable ancestors through the selected visible mount; hidden host ancestors unobservable"
    if selected["version"] == 2:
        visible = _read_text(str(point / "cgroup.controllers")).split()
        _require(controller in visible, "required v2 controller is not visible: " + controller)
    return selected


def _integer(text, description, *, minimum=0):
    value = text.strip()
    _require(re.fullmatch(r"-?[0-9]+", value) is not None, "invalid " + description)
    value = int(value)
    _require(value >= minimum, "invalid " + description)
    return value


def _cpu_constraints(hierarchy):
    rows = []
    for directory in hierarchy["ancestors"]:
        point = PurePosixPath(directory)
        if hierarchy["version"] == 2:
            filename = str(point / "cpu.max")
            raw = _optional_text(filename)
            if raw is None:
                _require(directory == hierarchy["mountpoint"] and hierarchy["root"] == "/",
                         "cannot verify CPU quota interface: " + filename)
                rows.append({"path": filename, "quota_us": None, "period_us": None,
                             "capacity": None, "reason": "v2 hierarchy root has no local quota interface"})
                continue
            fields = raw.split()
            _require(len(fields) == 2, "invalid cpu.max")
            period = _integer(fields[1], "CPU period", minimum=1)
            quota = None if fields[0] == "max" else _integer(fields[0], "CPU quota", minimum=1)
        else:
            filename = str(point / "cpu.cfs_quota_us")
            raw = _integer(_read_text(filename), "CPU quota", minimum=-1)
            _require(raw != 0, "zero CPU quota is invalid")
            quota = None if raw == -1 else raw
            period = _integer(_read_text(str(point / "cpu.cfs_period_us")), "CPU period", minimum=1)
        rows.append({"path": filename, "quota_us": quota, "period_us": period,
                     "capacity": None if quota is None else quota / period})
    return rows


def _memory_constraints(hierarchy):
    rows = []
    for directory in hierarchy["ancestors"]:
        point = PurePosixPath(directory)
        if hierarchy["version"] == 2:
            filename = str(point / "memory.max")
            raw = _optional_text(filename)
            if raw is None:
                _require(directory == hierarchy["mountpoint"] and hierarchy["root"] == "/",
                         "cannot verify memory limit interface: " + filename)
                rows.append({"path": filename, "limit_bytes": None, "used_bytes": None,
                             "available_bytes": None, "reason": "v2 hierarchy root has no local memory limit interface"})
                continue
            limit = None if raw.strip() == "max" else _integer(raw, "memory limit")
            usage = _integer(_read_text(str(point / "memory.current")), "memory usage")
        else:
            filename = str(point / "memory.limit_in_bytes")
            limit = _integer(_read_text(filename), "memory limit")
            usage = _integer(_read_text(str(point / "memory.usage_in_bytes")), "memory usage")
        rows.append({"path": filename, "limit_bytes": limit, "used_bytes": usage,
                     "available_bytes": None if limit is None else max(0, limit - usage)})
    return rows


def capacity(workers, process_limit_bytes=512 * 1024 ** 2, reserve_bytes=512 * 1024 ** 2):
    """Validate capacity without silently changing workers or reserving RAM."""
    _require(type(workers) is int and 1 <= workers <= 16, "workers must be an integer in 1..16")
    _require(type(process_limit_bytes) is int and process_limit_bytes > 0, "invalid process memory budget")
    _require(type(reserve_bytes) is int and reserve_bytes >= 0, "invalid memory reserve")
    affinity = sorted(os.sched_getaffinity(0))
    _require(affinity and all(type(cpu) is int and cpu >= 0 for cpu in affinity), "cannot verify CPU affinity")
    memory_lines = [line.split() for line in _read_text("/proc/meminfo").splitlines()
                    if line.startswith("MemAvailable:")]
    _require(len(memory_lines) == 1 and len(memory_lines[0]) == 3 and memory_lines[0][2] == "kB",
             "cannot verify MemAvailable")
    host_available = _integer(memory_lines[0][1], "MemAvailable") * 1024
    memberships = _memberships(_read_text("/proc/self/cgroup"))
    mounts = _mounts(_read_text("/proc/self/mountinfo"))
    cpu_hierarchy = _hierarchy("cpu", memberships, mounts)
    memory_hierarchy = _hierarchy("memory", memberships, mounts)
    cpu_rows, memory_rows = _cpu_constraints(cpu_hierarchy), _memory_constraints(memory_hierarchy)
    cpu_capacity = min([float(len(affinity))] + [row["capacity"] for row in cpu_rows if row["capacity"] is not None])
    available = min([host_available] + [row["available_bytes"] for row in memory_rows
                                      if row["available_bytes"] is not None])
    tree_limit = (workers + 1) * process_limit_bytes
    _require(cpu_capacity >= workers,
             f"insufficient CPU capacity for workers={workers}: available={cpu_capacity}; no automatic downgrade")
    _require(available >= tree_limit + reserve_bytes,
             f"insufficient memory for workers={workers}: available={available}, required={tree_limit + reserve_bytes}")
    return {"workers": workers, "cpu_capacity": cpu_capacity, "available_memory_bytes": available,
            "tree_rss_limit_bytes": tree_limit, "process_as_limit_bytes": process_limit_bytes,
            "reserve_bytes": reserve_bytes, "required_available_memory_bytes": tree_limit + reserve_bytes,
            "affinity_cpu_ids": affinity, "host_mem_available_bytes": host_available,
            "cpu_constraints": cpu_rows, "memory_constraints": memory_rows,
            "cpu_hierarchy": cpu_hierarchy, "memory_hierarchy": memory_hierarchy,
            "scope": "read-only preflight of visible constraints; no resource reservation or guaranteed peak"}
