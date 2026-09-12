"""Lossless, exclusive-create R4 shards; incomplete streams are never repaired.

Array format: gzip(JSON header + LF + contiguous C-order rows). Header records
dtype, full shape and version; reads require exact length and a valid gzip CRC.
No pickle, precision reduction, content replacement or raw-file deletion.
"""
from contextlib import contextmanager
import gzip
import hashlib
import json
from pathlib import Path

from .r4_families import encode


class _GuardedFile:
    def __init__(self, path, progress):
        self.path, self.progress = Path(path), progress
        self.handle = self.path.open("xb")

    def write(self, raw):
        if self.progress:
            self.progress({"phase": "compressed_write", "file": self.path.name, "reserve_bytes": len(raw)})
        return self.handle.write(raw)

    def flush(self):
        self.handle.flush()


@contextmanager
def compressed_writer(path, progress=None):
    target = _GuardedFile(path, progress)
    try:
        with gzip.GzipFile(filename="", fileobj=target, mode="wb", compresslevel=6, mtime=0) as stream:
            yield stream
    finally:
        target.handle.close()


def write_json(path, value, progress=None):
    # Iteration bounds temporary memory and calls the byte guard on compressed
    # writes; float repr round-trips the original Python binary64 values.
    with compressed_writer(path, progress) as stream:
        encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), allow_nan=False)
        buffer = bytearray()
        for token in encoder.iterencode(value):
            buffer.extend(token.encode("utf-8"))
            if len(buffer) >= 65536:
                stream.write(buffer)
                buffer.clear()
        stream.write(buffer)
        stream.write(b"\n")


def read_json(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def file_record(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing or symbolic-link artifact")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return {"bytes": path.stat().st_size, "sha256": hasher.hexdigest()}


class LosslessArray:
    """Sequential disk rows plus RAM indexing for saved-state rendering only."""
    def __init__(self, path, shape, dtype, progress=None):
        import numpy as np
        self.dtype = np.dtype(dtype).newbyteorder("<")
        self.shape = tuple(shape)
        if not self.shape or any(type(n) is not int or n <= 0 for n in self.shape) or self.dtype.hasobject:
            raise ValueError("invalid array shape/dtype")
        self.values = np.empty(self.shape, dtype=self.dtype)
        self.rows, self.closed = 0, False
        self.context = compressed_writer(path, progress)
        self.stream = self.context.__enter__()
        self.stream.write(encode({"version": "r4-array-v1", "shape": list(shape), "dtype": self.dtype.str}))

    def __setitem__(self, index, value):
        if self.closed or type(index) is not int or index != self.rows or index >= self.shape[0]:
            raise ValueError("array rows must be appended once in order")
        self.values[index] = value
        self.stream.write(self.values[index].tobytes(order="C"))
        self.rows += 1

    def __getitem__(self, index):
        if index == -1:
            index = self.rows - 1
        if not 0 <= index < self.rows:
            raise ValueError("read outside saved array prefix")
        return self.values[index]

    def flush(self):
        if not self.closed:
            self.stream.flush()

    def close(self):
        if not self.closed:
            self.closed = True
            self.context.__exit__(None, None, None)


def array_summary(path):
    """Streaming byte/CRC verification; no scientific computation or dtype cast."""
    import math
    with gzip.open(path, "rb") as stream:
        header = json.loads(stream.readline(4096))
        if set(header) != {"version", "shape", "dtype"} or header["version"] != "r4-array-v1":
            raise ValueError("invalid array header")
        sizes = {"|u1": 1, "<f8": 8, "<f4": 4, "<i8": 8}
        if header["dtype"] not in sizes or not header["shape"] or any(type(n) is not int or n <= 0 for n in header["shape"]):
            raise ValueError("unsupported dtype/shape")
        expected = math.prod(header["shape"]) * sizes[header["dtype"]]
        size, hasher = 0, hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            if size > expected:
                raise ValueError("extra array bytes")
            hasher.update(chunk)
        if size != expected:
            raise ValueError("incomplete array prefix: preserve, never repair")
    return {**header, "raw_bytes": size, "raw_sha256": hasher.hexdigest()}


def inventory(directory):
    directory = Path(directory)
    return {p.relative_to(directory).as_posix(): file_record(p)
            for p in sorted(directory.rglob("*")) if p.is_file()}
