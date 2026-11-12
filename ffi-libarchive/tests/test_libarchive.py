# -*- encoding: utf-8 -*-

import gc
import os
import stat

import pytest

from aeltra.ffi import libarchive
from aeltra.ffi.libarchive import (
    ArchiveEntry, ArchiveError, ArchiveFileReader, ArchiveFileWriter
)


DATA = [
    ("./usr/", None),
    ("./usr/bin/", None),
    ("./usr/bin/hello", b"#!/bin/sh\necho hello\n"),
    ("./usr/share/doc/hello/big", os.urandom(1024 * 1024)),
]


def write_member(archive, name, payload):
    with ArchiveEntry() as entry:
        entry.pathname = name
        entry.filetype = stat.S_IFREG
        entry.mode = stat.S_IFREG | 0o644
        entry.size = len(payload)
        archive.write_entry(entry)
        archive.write_data(payload)
    #end with


def make_tarball(path, compression):
    with ArchiveFileWriter(str(path), libarchive.FORMAT_TAR_USTAR,
            compression) as archive:
        for name, payload in DATA:
            with ArchiveEntry() as entry:
                entry.pathname = name
                if payload is None:
                    entry.filetype = stat.S_IFDIR
                    entry.mode = stat.S_IFDIR | 0o755
                else:
                    entry.filetype = stat.S_IFREG
                    entry.mode = stat.S_IFREG | 0o755
                    entry.size = len(payload)
                archive.write_entry(entry)
                if payload is not None:
                    archive.write_data(payload)
            #end with
        #end for
    #end with
    return path.read_bytes()


@pytest.fixture(params=[
    ("xz", libarchive.COMPRESSION_XZ),
    ("zst", libarchive.COMPRESSION_ZSTD),
])
def deb(request, tmp_path):
    """A .deb with an xz- or zstd-compressed data.tar."""
    suffix, compression = request.param

    control = make_tarball(tmp_path / "control.tar.gz",
        libarchive.COMPRESSION_GZIP)
    data = make_tarball(tmp_path / "data.tar", compression)

    path = tmp_path / "hello.deb"
    with ArchiveFileWriter(str(path), libarchive.FORMAT_AR_SVR4,
            libarchive.COMPRESSION_NONE) as archive:
        write_member(archive, "debian-binary", b"2.0\n")
        write_member(archive, "control.tar.gz", control)
        write_member(archive, "data.tar." + suffix, data)
    #end with
    return path


def scan(outer):
    result = {}
    for entry in outer:
        if entry.pathname.startswith("data.tar."):
            with ArchiveFileReader(outer) as inner:
                for e in inner:
                    result[e.pathname] = (e.is_directory, e.size)
    return result


EXPECTED = {
    name: (payload is None, len(payload or b"")) for name, payload in DATA
}


def test_nested_from_a_file(deb):
    with ArchiveFileReader(str(deb)) as outer:
        assert scan(outer) == EXPECTED


def test_nested_from_a_memfd(deb):
    fd = os.memfd_create("deb")
    try:
        os.write(fd, deb.read_bytes())
        os.lseek(fd, 0, os.SEEK_SET)

        with ArchiveFileReader(fd) as outer:
            assert scan(outer) == EXPECTED

        # Left open for the caller.
        os.fstat(fd)
    finally:
        os.close(fd)


def test_the_inner_data_can_be_read(deb):
    with ArchiveFileReader(str(deb)) as outer:
        for entry in outer:
            if not entry.pathname.startswith("data.tar."):
                continue
            with ArchiveFileReader(outer) as inner:
                for e in inner:
                    if e.pathname == "./usr/share/doc/hello/big":
                        assert inner.read_data() == DATA[3][1]
    #end with


def test_moving_the_outer_reader_on_closes_the_inner(deb):
    with ArchiveFileReader(str(deb)) as outer:
        outer.next_entry()
        outer.next_entry()
        inner = ArchiveFileReader(outer)
        outer.next_entry()

        with pytest.raises(ArchiveError, match="closed"):
            inner.next_entry()
    #end with


def test_closing_the_outer_reader_closes_the_inner(deb):
    outer = ArchiveFileReader(str(deb))
    outer.next_entry()
    outer.next_entry()
    inner = ArchiveFileReader(outer)
    outer.close()

    with pytest.raises(ArchiveError, match="closed"):
        inner.next_entry()
    with pytest.raises(ArchiveError, match="closed"):
        ArchiveFileReader(outer)


def test_the_inner_reader_keeps_the_outer_alive(deb):
    def open_inner():
        outer = ArchiveFileReader(str(deb))
        for entry in outer:
            if entry.pathname.startswith("data.tar."):
                return ArchiveFileReader(outer)

    inner = open_inner()
    gc.collect()
    assert len(list(e.pathname for e in inner)) == len(DATA)


def test_a_corrupt_inner_archive_raises(tmp_path):
    path = tmp_path / "bad.deb"
    with ArchiveFileWriter(str(path), libarchive.FORMAT_AR_SVR4,
            libarchive.COMPRESSION_NONE) as archive:
        write_member(archive, "data.tar.xz",
            b"\xfd7zXZ\x00" + os.urandom(4096))
    #end with

    with ArchiveFileReader(str(path)) as outer:
        outer.next_entry()
        with pytest.raises(ArchiveError):
            with ArchiveFileReader(outer) as inner:
                for e in inner:
                    pass
    #end with
