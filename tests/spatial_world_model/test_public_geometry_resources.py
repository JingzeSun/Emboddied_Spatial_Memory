"""Server-only resource checks using small text fixtures; no physical queries."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops/spatial_history"))
import public_geometry_resources as resources


GIB = 1024 ** 3


class PublicGeometryResourcesTests(unittest.TestCase):
    def v2(self, *, root="/", member="/tenant/job", point="/sys/fs/cgroup"):
        files = {"/proc/self/cgroup": "0::" + member + "\n",
                 "/proc/self/mountinfo": f"20 1 0:20 {root} {point} rw - cgroup2 cgroup rw\n",
                 "/proc/meminfo": f"MemAvailable: {32 * GIB // 1024} kB\n",
                 point + "/cgroup.controllers": "cpu memory io\n"}
        relative = member[len(root):] if root != "/" and member.startswith(root + "/") else member
        if member == root:
            relative = "/"
        current = point.rstrip("/") + (relative if relative != "/" else "")
        while True:
            files[current + "/cgroup.procs"] = "123\n" if current == point + relative.rstrip("/") else "\n"
            files[current + "/cpu.max"] = "max 100000\n"
            files[current + "/memory.max"] = "max\n"
            files[current + "/memory.current"] = "0\n"
            if current == point:
                break
            current = current.rsplit("/", 1)[0]
        # Handle membership equal to the mount root without a trailing slash.
        actual = point.rstrip("/") + (relative if relative != "/" else "")
        files[actual + "/cgroup.procs"] = "123\n"
        return files

    def invoke(self, files, workers=4, *, affinity=16):
        def read(path):
            if str(path) not in files:
                raise FileNotFoundError(str(path))
            return files[str(path)]
        with patch.object(resources, "_read_text", side_effect=read), \
                patch.object(resources.os, "sched_getaffinity", return_value=set(range(affinity))), \
                patch.object(resources.os, "getpid", return_value=123):
            return resources.capacity(workers)

    def test_four_eight_sixteen_workers_keep_requested_count_and_budget(self):
        for workers in (4, 8, 16):
            with self.subTest(workers=workers):
                result = self.invoke(self.v2(), workers)
                self.assertEqual(result["workers"], workers)
                self.assertEqual(result["tree_rss_limit_bytes"], (workers + 1) * GIB // 2)
                self.assertEqual(result["required_available_memory_bytes"], (workers + 2) * GIB // 2)
                self.assertEqual(result["cpu_capacity"], 16)

    def test_tighter_ancestor_cpu_and_memory_constraints_win(self):
        files = self.v2()
        files["/sys/fs/cgroup/cpu.max"] = "800000 100000\n"
        files["/sys/fs/cgroup/tenant/cpu.max"] = "450000 100000\n"
        files["/sys/fs/cgroup/tenant/memory.max"] = str(5 * GIB)
        files["/sys/fs/cgroup/tenant/memory.current"] = str(GIB)
        result = self.invoke(files)
        self.assertEqual(result["cpu_capacity"], 4.5)
        self.assertEqual(result["available_memory_bytes"], 4 * GIB)
        self.assertEqual(len(result["cpu_constraints"]), 3)
        with self.assertRaisesRegex(ValueError, "insufficient CPU"):
            self.invoke(files, 8)

    def test_fractional_quota_and_affinity_cannot_be_rounded_up(self):
        files = self.v2()
        files["/sys/fs/cgroup/tenant/cpu.max"] = "350000 100000\n"
        with self.assertRaisesRegex(ValueError, "insufficient CPU"):
            self.invoke(files)
        with self.assertRaisesRegex(ValueError, "insufficient CPU"):
            self.invoke(self.v2(), affinity=3)

    def test_invalid_workers_rejected_before_any_resource_read(self):
        for workers in (0, -1, 17, 4.0, True, "4"):
            with self.subTest(workers=workers), patch.object(resources, "_read_text") as read, \
                    self.assertRaisesRegex(ValueError, "workers"):
                resources.capacity(workers)
            read.assert_not_called()

    def test_host_or_ancestor_memory_insufficient_stops_without_downgrade(self):
        for location in ("host", "ancestor"):
            files = self.v2()
            if location == "host":
                files["/proc/meminfo"] = f"MemAvailable: {2 * GIB // 1024} kB\n"
            else:
                files["/sys/fs/cgroup/tenant/memory.max"] = str(4 * GIB)
                files["/sys/fs/cgroup/tenant/memory.current"] = str(2 * GIB)
            with self.subTest(location=location), self.assertRaisesRegex(ValueError, "insufficient memory"):
                self.invoke(files)

    def test_unrecognised_mount_or_missing_controller_fails_closed(self):
        for kind in ("mount", "controller", "mapping", "interface"):
            files = self.v2()
            if kind == "mount":
                files["/proc/self/mountinfo"] = "20 1 0:20 / /unrelated rw - tmpfs tmpfs rw\n"
            elif kind == "controller":
                files["/sys/fs/cgroup/cgroup.controllers"] = "io\n"
            elif kind == "mapping":
                files["/sys/fs/cgroup/tenant/job/cgroup.procs"] = "999\n"
            else:
                del files["/sys/fs/cgroup/tenant/cpu.max"]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.invoke(files)

    def test_mount_subtree_and_namespace_relative_mapping_are_verified(self):
        for member in ("/tenant/job", "/job"):
            files = self.v2(root="/tenant", member=member)
            result = self.invoke(files)
            self.assertEqual(result["cpu_hierarchy"]["current"], "/sys/fs/cgroup/job")
            self.assertEqual(result["cpu_hierarchy"]["ancestors"], ["/sys/fs/cgroup/job", "/sys/fs/cgroup"])
            self.assertTrue(result["cpu_hierarchy"]["membership_pid_verified"])

    def test_v1_split_controller_mounts_check_all_ancestors(self):
        files = {"/proc/self/cgroup": "2:cpu,cpuacct:/tenant/job\n3:memory:/tenant/job\n",
                 "/proc/self/mountinfo": "20 1 0:20 / /cg/cpu rw - cgroup cgroup rw,cpu,cpuacct\n"
                                         "21 1 0:21 / /cg/memory rw - cgroup cgroup rw,memory\n",
                 "/proc/meminfo": f"MemAvailable: {32 * GIB // 1024} kB\n"}
        for suffix in ("", "/tenant", "/tenant/job"):
            cpu, memory = "/cg/cpu" + suffix, "/cg/memory" + suffix
            files[cpu + "/cgroup.procs"] = "123\n" if suffix == "/tenant/job" else "\n"
            files[memory + "/cgroup.procs"] = "123\n" if suffix == "/tenant/job" else "\n"
            files[cpu + "/cpu.cfs_quota_us"] = "-1\n"
            files[cpu + "/cpu.cfs_period_us"] = "100000\n"
            files[memory + "/memory.limit_in_bytes"] = str(32 * GIB)
            files[memory + "/memory.usage_in_bytes"] = "0\n"
        files["/cg/cpu/tenant/cpu.cfs_quota_us"] = "400000\n"
        files["/cg/memory/tenant/memory.limit_in_bytes"] = str(4 * GIB)
        files["/cg/memory/tenant/memory.usage_in_bytes"] = str(GIB)
        result = self.invoke(files)
        self.assertEqual(result["cpu_capacity"], 4)
        self.assertEqual(result["available_memory_bytes"], 3 * GIB)
        self.assertEqual(result["memory_hierarchy"]["version"], 1)

    def test_invalid_quota_usage_or_memavailable_is_rejected(self):
        changes = {"/sys/fs/cgroup/tenant/cpu.max": "max 0",
                   "/sys/fs/cgroup/tenant/memory.current": "-1",
                   "/proc/meminfo": "MemAvailable: 32000000 bytes"}
        for path, text in changes.items():
            files = self.v2()
            files[path] = text
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.invoke(files)

    def test_mountinfo_octal_escape_is_used_for_actual_paths(self):
        files = self.v2(point="/cg space")
        files["/proc/self/mountinfo"] = "20 1 0:20 / /cg\\040space rw - cgroup2 cgroup rw\n"
        result = self.invoke(files)
        self.assertEqual(result["cpu_hierarchy"]["mountpoint"], "/cg space")

    def test_global_v2_root_without_local_limit_files_is_explicit(self):
        files = self.v2(member="/")
        del files["/sys/fs/cgroup/cpu.max"]
        del files["/sys/fs/cgroup/memory.max"]
        result = self.invoke(files)
        self.assertIsNone(result["cpu_constraints"][0]["capacity"])
        self.assertIsNone(result["memory_constraints"][0]["available_bytes"])
        self.assertIn("root", result["cpu_constraints"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
