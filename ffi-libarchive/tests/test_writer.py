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


def write_entry(archive, name, size, filetype=stat.S_IFREG, **kwargs):
    with ArchiveEntry() as entry:
        entry.pathname = name
        entry.filetype = filetype
        entry.mode = filetype | 0o644
        entry.size = size
        for key, value in kwargs.items():
            setattr(entry, key, value)
        archive.write_entry(entry)
    #end with


@pytest.mark.parametrize("archive_format", [
    libarchive.FORMAT_TAR_USTAR,
    libarchive.FORMAT_AR_SVR4,
])
def test_more_data_than_the_size_raises(tmp_path, archive_format):
    with pytest.raises(ArchiveError, match="'f' .* more data .* 3 bytes"):
        with ArchiveFileWriter(str(tmp_path / "a"), archive_format) \
                as archive:
            write_entry(archive, "f", 3)
            archive.write_data(b"ab")
            archive.write_data(b"cd")
    #end with


def test_less_data_than_the_size_raises_at_the_next_entry(tmp_path):
    archive = ArchiveFileWriter(str(tmp_path / "a.tar"),
        libarchive.FORMAT_TAR_USTAR)
    write_entry(archive, "f", 3)
    archive.write_data(b"ab")

    with pytest.raises(ArchiveError, match="'f' .* missing 1 of its 3"):
        write_entry(archive, "g", 0)
    with pytest.raises(ArchiveError, match="'f' .* missing 1 of its 3"):
        archive.close()
    #end with


def test_less_data_than_the_size_raises_when_closing(tmp_path):
    with pytest.raises(ArchiveError, match="'f' .* missing 3 of its 3"):
        with ArchiveFileWriter(str(tmp_path / "a.tar"),
                libarchive.FORMAT_TAR_USTAR) as archive:
            write_entry(archive, "f", 3)
    #end with


def test_data_for_an_entry_that_has_none_raises(tmp_path):
    with pytest.raises(ArchiveError, match="more data"):
        with ArchiveFileWriter(str(tmp_path / "a.tar"),
                libarchive.FORMAT_TAR_USTAR) as archive:
            write_entry(archive, "d", 0, filetype=stat.S_IFDIR)
            archive.write_data(b"x")
    #end with


def test_a_hardlink_entry_needs_no_data(tmp_path):
    # As aeltrapack writes the second name of a file.
    path = str(tmp_path / "a.tar")

    with ArchiveFileWriter(path, libarchive.FORMAT_TAR_USTAR) as archive:
        write_entry(archive, "f", 3, nlink=2, inode=7)
        archive.write_data(b"abc")
        write_entry(archive, "g", 3, nlink=2, inode=7)
    #end with

    with ArchiveFileReader(path) as archive:
        assert [(e.pathname, e.hardlink) for e in archive] \
            == [("f", None), ("g", "f")]


def test_the_raw_format_takes_data_without_a_size(tmp_path):
    # As repoindexer writes Packages.gz.
    path = str(tmp_path / "Packages.gz")

    with ArchiveFileWriter(path, libarchive.FORMAT_RAW,
            libarchive.COMPRESSION_GZIP) as archive:
        with ArchiveEntry() as entry:
            entry.filetype = stat.S_IFREG
            archive.write_entry(entry)
        archive.write_data(b"Package: a\n")
        archive.write_data(b"Version: 1\n")
    #end with

    with ArchiveFileReader(path, raw=True) as archive:
        next(iter(archive))
        assert archive.read_data() == b"Package: a\nVersion: 1\n"


def test_a_writer_that_cant_be_opened_reports_why(tmp_path):
    with pytest.raises(ArchiveError, match="(?i)no such file|failed"):
        ArchiveFileWriter(str(tmp_path / "missing" / "a.tar"),
            libarchive.FORMAT_TAR_USTAR)
