# -*- encoding: utf-8 -*-

import os
import stat

import pytest

from aeltra.ffi import libarchive
from aeltra.ffi.libarchive import (
    ArchiveEntry, ArchiveError, ArchiveFileReader, ArchiveFileWriter
)

# Every write to it fails with ENOSPC.
FULL = "/dev/full"

needs_dev_full = pytest.mark.skipif(
    not os.path.exists(FULL), reason="no /dev/full"
)


def write_small_file(archive):
    # Far less than libarchive's 10 KiB block: nothing reaches the file
    # before the archive is closed.
    with ArchiveEntry() as entry:
        entry.pathname = "f"
        entry.filetype = stat.S_IFREG
        entry.mode = stat.S_IFREG | 0o644
        entry.size = 3
        archive.write_entry(entry)
        archive.write_data(b"abc")
    #end with


@needs_dev_full
@pytest.mark.parametrize("compression", [
    libarchive.COMPRESSION_NONE,
    libarchive.COMPRESSION_GZIP,
    libarchive.COMPRESSION_XZ,
])
def test_a_failure_when_closing_is_raised(compression):
    with pytest.raises(ArchiveError, match="/dev/full.*No space left"):
        with ArchiveFileWriter(FULL, libarchive.FORMAT_TAR_USTAR,
                compression) as archive:
            write_small_file(archive)
    #end with


@needs_dev_full
def test_close_raises_and_can_be_called_again():
    archive = ArchiveFileWriter(FULL, libarchive.FORMAT_TAR_USTAR)
    write_small_file(archive)

    with pytest.raises(ArchiveError):
        archive.close()

    archive.close()


@needs_dev_full
def test_an_error_in_the_block_is_not_replaced_by_one_from_closing():
    with pytest.raises(KeyError):
        with ArchiveFileWriter(FULL, libarchive.FORMAT_TAR_USTAR) \
                as archive:
            write_small_file(archive)
            raise KeyError("the original error")
    #end with


def test_a_complete_archive_closes_without_error(tmp_path):
    path = str(tmp_path / "a.tar.gz")

    with ArchiveFileWriter(path, libarchive.FORMAT_TAR_USTAR,
            libarchive.COMPRESSION_GZIP) as archive:
        write_small_file(archive)
    #end with

    with ArchiveFileReader(path) as archive:
        assert [e.pathname for e in archive] == ["f"]


def test_a_writer_that_cant_be_opened_reports_why(tmp_path):
    with pytest.raises(ArchiveError, match="(?i)no such file|failed"):
        ArchiveFileWriter(str(tmp_path / "missing" / "a.tar"),
            libarchive.FORMAT_TAR_USTAR)
