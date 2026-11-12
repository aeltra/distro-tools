# -*- encoding: utf-8 -*-

import stat

import pytest

from aeltra.ffi import libarchive
from aeltra.ffi.libarchive import (
    ArchiveEntry, ArchiveFileReader, ArchiveFileWriter
)


def test_uid():
    with ArchiveEntry() as entry:
        entry.uid = 1000
        assert entry.uid == 1000
    #end with


def test_a_clone_is_a_copy_of_its_own():
    entry = ArchiveEntry()
    entry.pathname = "f"
    entry.mode = stat.S_IFREG | 0o644
    entry.size = 3

    clone = entry.clone()
    assert (clone.pathname, clone.mode, clone.size) == ("f", 0o644, 3)

    clone.pathname = "g"
    assert entry.pathname == "f"

    entry.free()
    assert clone.pathname == "g"
    clone.free()


@pytest.mark.parametrize("func, make", [
    ("archive_entry_new", lambda tmp_path: ArchiveEntry()),
    ("archive_entry_clone", lambda tmp_path: ArchiveEntry().clone()),
    ("archive_read_new",
        lambda tmp_path: ArchiveFileReader(str(tmp_path / "a"))),
    ("archive_write_new",
        lambda tmp_path: ArchiveFileWriter(str(tmp_path / "a"),
            libarchive.FORMAT_TAR_USTAR)),
])
def test_a_failed_allocation_raises(monkeypatch, tmp_path, func, make):
    # What libarchive returns when it runs out of memory.
    monkeypatch.setattr(libarchive.lib, func, lambda *args: None)
    with pytest.raises(MemoryError):
        make(tmp_path)
