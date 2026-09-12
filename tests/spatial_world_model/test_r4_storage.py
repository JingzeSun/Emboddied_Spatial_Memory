"""Small artificial byte roundtrips only; no physical data or fitted model."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

from spatial_world_model.r4_storage import LosslessArray, array_summary, file_record, write_json, read_json


class R4StorageTests(unittest.TestCase):
    def test_f64_signed_zero_extremes_roundtrip_exact_bytes(self):
        values = np.array([[0.0, -0.0, np.nextafter(1.0, 2.0)], [1e-200, 1e200, np.pi]], dtype="<f8")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "a.gz"
            array = LosslessArray(path, values.shape, values.dtype)
            for i, row in enumerate(values):
                array[i] = row
            array.close()
            summary = array_summary(path)
            self.assertEqual(summary["raw_sha256"], hashlib.sha256(values.tobytes()).hexdigest())
            self.assertEqual(summary["raw_bytes"], values.nbytes)

    def test_uint8_and_scalar_index_arrays(self):
        with tempfile.TemporaryDirectory() as temp:
            for dtype, shape in (("uint8", (2, 4, 3)), ("int64", (2,))):
                path = Path(temp) / (dtype + ".gz")
                a = LosslessArray(path, shape, dtype)
                for i in range(2):
                    a[i] = i
                a.close()
                self.assertEqual(array_summary(path)["shape"], list(shape))

    def test_equal_writes_have_equal_compressed_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = [Path(temp) / n for n in ("first.gz", "different-name.gz")]
            for path in paths:
                a = LosslessArray(path, (2, 3), "float64")
                a[0], a[1] = [1, 2, 3], [4, 5, 6]
                a.close()
            self.assertEqual(file_record(paths[0]), file_record(paths[1]))

    def test_incomplete_prefix_is_preserved_but_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "partial.gz"
            a = LosslessArray(path, (3, 2), "float64")
            a[0] = [1, 2]
            a.close()
            before = file_record(path)
            with self.assertRaises(ValueError):
                array_summary(path)
            self.assertEqual(before, file_record(path))

    def test_out_of_order_and_overwrite_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data.gz"
            a = LosslessArray(path, (2, 2), "float64")
            with self.assertRaises(ValueError):
                a[1] = [0, 0]
            a.close()
            with self.assertRaises(FileExistsError):
                LosslessArray(path, (2, 2), "float64")

    def test_crc_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data.gz"
            a = LosslessArray(path, (1, 2), "float64")
            a[0] = [1, 2]
            a.close()
            raw = bytearray(path.read_bytes())
            raw[-8] ^= 1
            path.write_bytes(raw)
            with self.assertRaises((OSError, EOFError)):
                array_summary(path)

    def test_json_float_and_rgb_roundtrip(self):
        value = {"depth": [0.0, -0.0, 1.0000000000000002], "rgb": [0, 128, 255]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "public.gz"
            write_json(path, value)
            actual = read_json(path)
            self.assertEqual(json.dumps(actual, sort_keys=True), json.dumps(value, sort_keys=True))

    def test_writer_guard_failure_keeps_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "stopped.gz"
            def refuse(event):
                raise ValueError("budget")
            with self.assertRaises(ValueError):
                write_json(path, {"x": 1}, refuse)
            self.assertTrue(path.exists())
