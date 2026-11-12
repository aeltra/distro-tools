# -*- encoding: utf-8 -*-

import io
import os
import stat
import tarfile

import pytest

from aeltra.ffi.libarchive import ArchiveError, ArchiveFileReader


def member(name, type=tarfile.REGTYPE, mode=0o644, data=b"", **kwargs):
    info = tarfile.TarInfo(name)
    info.type  = type
    info.mode  = mode
    info.mtime = 1700000000
    if type == tarfile.REGTYPE:
        info.size = len(data)
    for key, value in kwargs.items():
        setattr(info, key, value)
    return info, (io.BytesIO(data) if type == tarfile.REGTYPE else None)


def make_tar(path, members):
    with tarfile.open(str(path), "w", format=tarfile.PAX_FORMAT) as t:
        for info, data in members:
            t.addfile(info, data)
    return str(path)


def unpack(path, base_dir, **kwargs):
    with ArchiveFileReader(path) as archive:
        archive.unpack_to_disk(str(base_dir), **kwargs)


def mode_of(path):
    return stat.S_IMODE(os.lstat(str(path)).st_mode)


@pytest.fixture
def tree(tmp_path):
    """Where the archive goes, with a sibling it mustn't reach."""
    os.umask(0o022)
    (tmp_path / "out").mkdir()
    (tmp_path / "outside").mkdir()
    return tmp_path


def nothing_outside(tree):
    return os.listdir(str(tree / "outside")) == []


def test_a_source_tree_is_unpacked_with_exact_modes(tree):
    path = make_tar(tree / "src.tar", [
        member("pkg-1.0/", tarfile.DIRTYPE, 0o755),
        member("pkg-1.0/configure", mode=0o775, data=b"#!/bin/sh\n"),
        member("pkg-1.0/README", mode=0o664, data=b"hello\n"),
        member("pkg-1.0/link", tarfile.SYMTYPE, linkname="README"),
    ])
    unpack(path, tree / "out", strip_components=1)

    out = tree / "out"
    assert (out / "README").read_bytes() == b"hello\n"
    assert os.readlink(str(out / "link")) == "README"
    # Not subject to the umask.
    assert mode_of(out / "configure") == 0o775
    assert mode_of(out / "README") == 0o664
    assert os.lstat(str(out / "README")).st_mtime == 1700000000


def test_sane_file_modes(tree):
    path = make_tar(tree / "src.tar", [
        member("d/", tarfile.DIRTYPE, 0o500),
        member("d/f", mode=0o000, data=b"x"),
    ])
    unpack(path, tree / "out")
    assert mode_of(tree / "out" / "d") == 0o700
    assert mode_of(tree / "out" / "d" / "f") == 0o600

    path = make_tar(tree / "src2.tar", [member("g", mode=0o444, data=b"x")])
    unpack(path, tree / "out", sane_file_modes=False)
    assert mode_of(tree / "out" / "g") == 0o444


def test_setuid_setgid_and_sticky_bits_are_dropped(tree):
    path = make_tar(tree / "src.tar", [
        member("suid", mode=0o4755, data=b"x"),
        member("sgid", mode=0o2755, data=b"x"),
        member("sticky", tarfile.DIRTYPE, 0o1777),
    ])
    unpack(path, tree / "out")
    assert mode_of(tree / "out" / "suid") == 0o755
    assert mode_of(tree / "out" / "sgid") == 0o755
    assert mode_of(tree / "out" / "sticky") == 0o777


@pytest.mark.parametrize("members", [
    [member("pkg/../../outside/f", data=b"x")],
    [
        member("pkg/link", tarfile.SYMTYPE, linkname="../../outside"),
        member("pkg/link/f", data=b"x"),
    ],
    [
        member("pkg/link", tarfile.SYMTYPE, linkname="/"),
        member("pkg/link/tmp/f", data=b"x"),
    ],
])
def test_nothing_is_written_outside_base_dir(tree, members):
    path = make_tar(tree / "evil.tar", members)
    with pytest.raises(ArchiveError):
        unpack(path, tree / "out")
    assert nothing_outside(tree)


def test_a_symlink_already_in_base_dir_is_not_followed(tree):
    os.symlink(str(tree / "outside"), str(tree / "out" / "link"))
    path = make_tar(tree / "evil.tar", [member("link/f", data=b"x")])
    with pytest.raises(ArchiveError):
        unpack(path, tree / "out")
    assert nothing_outside(tree)


def test_absolute_names_are_unpacked_below_base_dir(tree):
    path = make_tar(tree / "src.tar", [member("/etc/f", data=b"x")])
    unpack(path, tree / "out")
    assert (tree / "out" / "etc" / "f").read_bytes() == b"x"


@pytest.mark.parametrize("kind", [
    member("fifo", tarfile.FIFOTYPE),
    member("chr", tarfile.CHRTYPE, devmajor=1, devminor=3),
    member("hard", tarfile.LNKTYPE, linkname="f"),
])
def test_other_kinds_of_entries_are_refused(tree, kind):
    path = make_tar(tree / "src.tar", [member("f", data=b"x"), kind])
    with pytest.raises(ArchiveError, match="special file type"):
        unpack(path, tree / "out")
    assert not os.path.lexists(str(tree / "out" / kind[0].name))


def test_base_dir_may_be_reached_through_a_symlink(tree):
    os.symlink(str(tree / "out"), str(tree / "via"))
    path = make_tar(tree / "src.tar", [
        member("d/", tarfile.DIRTYPE, 0o755),
        member("d/f", data=b"x"),
    ])
    unpack(path, tree / "via")
    assert (tree / "out" / "d" / "f").read_bytes() == b"x"


def test_unpacking_over_an_existing_tree_replaces_files(tree):
    # As deb2aeltra does: the Debian tarball goes over the orig tarball.
    first = make_tar(tree / "a.tar", [
        member("d/", tarfile.DIRTYPE, 0o755),
        member("d/f", data=b"old"),
        member("d/l", tarfile.SYMTYPE, linkname="f"),
    ])
    second = make_tar(tree / "b.tar", [
        member("d/", tarfile.DIRTYPE, 0o755),
        member("d/f", data=b"new"),
        member("d/l", tarfile.SYMTYPE, linkname="g"),
    ])
    unpack(first, tree / "out")
    unpack(second, tree / "out")
    assert (tree / "out" / "d" / "f").read_bytes() == b"new"
    assert os.readlink(str(tree / "out" / "d" / "l")) == "g"


def test_entries_above_the_stripped_components_are_skipped(tree):
    path = make_tar(tree / "src.tar", [
        member("./", tarfile.DIRTYPE, 0o700),
        member("top", data=b"x"),
        member("pkg/f", data=b"y"),
    ])
    unpack(path, tree / "out", strip_components=1)
    assert os.listdir(str(tree / "out")) == ["f"]
    # The archive's "./" doesn't change base_dir's own mode.
    assert mode_of(tree / "out") == 0o755
