# -*- encoding: utf-8 -*-
#
# Packages are compressed with threads, how many must not matter.

import os
import random

import pytest

from aeltra.ffi import libarchive
from aeltra.ffi.libarchive import ArchiveEntry, ArchiveFileWriter
from aeltra.miscellaneous.platform import Platform
from aeltra.package.aeltrapack.debianpackage import DebianPackage


class Package:

    def __init__(self, parallel_jobs):
        self.parallel_jobs = parallel_jobs


def options(parallel_jobs):
    return DebianPackage.zstd_options.fget(Package(parallel_jobs))


@pytest.mark.parametrize("jobs, threads", [
    ("1", "1"), ("12", "12"), (3, "3"),
    # "0" would be one for each CPU, and no thread at all has another result
    ("0", "1"), ("-1", "1"),
])
def test_threads(jobs, threads):
    assert ("zstd", "threads", threads) in options(jobs)


@pytest.fixture(scope="module")
def data():
    # More than one job of zstd (32 MiB), hard enough to compress.
    rnd   = random.Random(1)
    words = [rnd.randbytes(rnd.randint(3, 12)) for i in range(5000)]
    return b"".join(rnd.choices(words, k=5000000))


def test_result_does_not_depend_on_the_threads(tmp_path, data):
    assert len(data) > 32 * 1024 * 1024

    def write(jobs):
        path = tmp_path / ("archive%s" % jobs)
        # A lower level has smaller jobs and is faster.
        opts = [("zstd", "compression-level", "3"), options(jobs)[1]]

        with ArchiveFileWriter(str(path), libarchive.FORMAT_TAR_USTAR,
                libarchive.COMPRESSION_ZSTD, options=opts) as archive:
            with ArchiveEntry() as entry:
                entry.clear()
                entry.pathname = "data"
                entry.mode = 0o100644
                entry.size = len(data)
                archive.write_entry(entry)
                archive.write_data(data)

        return path.read_bytes()

    result = write(1)
    assert len(result) < len(data)
    for jobs in (2, 3, 8):
        assert write(jobs) == result


def test_parallel_jobs(monkeypatch):
    monkeypatch.delenv("AELTRA_PARALLEL_JOBS", raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    assert Platform.parallel_jobs() == "12"
    assert Platform.parallel_jobs("2") == "2"
    monkeypatch.setattr(os, "cpu_count", lambda: 1)
    assert Platform.parallel_jobs() == "1"
    monkeypatch.setenv("AELTRA_PARALLEL_JOBS", "5")
    assert Platform.parallel_jobs() == "5"
    assert Platform.parallel_jobs("2") == "5"
