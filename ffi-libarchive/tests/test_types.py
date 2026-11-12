# -*- encoding: utf-8 -*-

import stat

import pytest

from aeltra.ffi import libarchive
from aeltra.ffi.libarchive import (
    ArchiveEntry, ArchiveFileReader, ArchiveFileWriter
)

# 2242, and before 1970: neither fits a 32-bit int.
TIMES = [2 ** 33 + 5, -1000]


@pytest.mark.parametrize("value", TIMES)
@pytest.mark.parametrize("field", ["atime", "ctime", "mtime"])
def test_times_beyond_32_bits(field, value):
    with ArchiveEntry() as entry:
        setattr(entry, field, value)
        assert getattr(entry, field) == value
    #end with


@pytest.mark.parametrize("field, value", [
    ("size", 6 * 2 ** 30),
    ("gid", 2 ** 40),
    ("inode", 2 ** 40),
    ("dev", 2 ** 40),
])
def test_64_bit_fields(field, value):
    with ArchiveEntry() as entry:
        setattr(entry, field, value)
        assert getattr(entry, field) == value
    #end with


def test_mode_and_filetype():
    with ArchiveEntry() as entry:
        entry.mode = stat.S_IFREG | 0o4755
        assert entry.mode == 0o4755
        assert entry.filetype == stat.S_IFREG
    #end with


def test_a_time_beyond_2038_survives_an_archive(tmp_path):
    path = str(tmp_path / "a.tar")

    with ArchiveFileWriter(path, libarchive.FORMAT_TAR_PAX_RESTRICTED) \
            as archive:
        with ArchiveEntry() as entry:
            entry.pathname = "f"
            entry.filetype = stat.S_IFREG
            entry.mode = stat.S_IFREG | 0o644
            entry.mtime = TIMES[0]
            archive.write_entry(entry)
        #end with
    #end with

    with ArchiveFileReader(path) as archive:
        assert [e.mtime for e in archive] == [TIMES[0]]
