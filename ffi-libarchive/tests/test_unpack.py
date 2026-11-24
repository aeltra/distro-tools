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


def make_cpio(path, members):
    """members: name, mode with type, inode, data; same inode, hard link"""
    with open(str(path), "wb") as f:
        for name, mode, inode, data in members + [("TRAILER!!!", 0, 0, b"")]:
            name   = name.encode("utf-8") + b"\0"
            fields = [inode, mode, 0, 0, 2 if inode else 1, 1700000000,
                len(data), 8, 1, 0, 0, len(name), 0]
            header = b"070701" + b"".join(b"%08X" % n for n in fields) + name
            for part in (header, data):
                f.write(part + b"\0" * (-len(part) % 4))
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


LNK = tarfile.LNKTYPE


def same_file(a, b):
    a, b = os.lstat(str(a)), os.lstat(str(b))
    return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


@pytest.mark.parametrize("linkname", [
    "pkg/d/f", "./pkg/d/f", "/pkg/d/f", "pkg//d/./f",
])
def test_hard_links_are_unpacked(tree, linkname):
    path = make_tar(tree / "src.tar", [
        member("pkg/d/f", mode=0o640, data=b"x"),
        # The mode is the file's, whatever the entry says.
        member("pkg/e/l", LNK, mode=0o4777, linkname=linkname),
        # To a link, which is a name of the file like the first one.
        member("./pkg/e/m", LNK, linkname="pkg/e/l"),
    ])
    unpack(path, tree / "out", strip_components=1)

    out = tree / "out"
    assert same_file(out / "d" / "f", out / "e" / "l")
    assert same_file(out / "d" / "f", out / "e" / "m")
    assert (out / "e" / "l").read_bytes() == b"x"
    assert mode_of(out / "d" / "f") == 0o640
    assert os.lstat(str(out / "d" / "f")).st_mtime == 1700000000


@pytest.mark.parametrize("strip", [0, 1])
@pytest.mark.parametrize("linkname", [
    "pkg/missing",                   # not in the archive
    "pkg/late",                      # only after the link
    "pkg/hard",                      # the link itself
    "pkg/d",                         # a folder
    "pkg/sym",                       # a symbolic link
    "pkg/dirsym/secret",             # through a symbolic link
    "pkg/there",                     # only in base_dir
    "there",
    "pkg",                           # nothing left of it when stripped
    "../outside/secret",
    "pkg/../../outside/secret",
    "pkg/d/../f",                    # inside, but not a plain path
    "@OUTSIDE@/secret",              # absolute
])
def test_hard_links_to_anything_else_are_refused(tree, strip, linkname):
    outside = str(tree / "outside")
    secret  = tree / "outside" / "secret"
    secret.write_bytes(b"secret")
    (tree / "out" / "there").write_bytes(b"there")
    (tree / "out" / "pkg").mkdir()
    (tree / "out" / "pkg" / "there").write_bytes(b"there")

    path = make_tar(tree / "evil.tar", [
        member("pkg/f", data=b"x"),
        member("pkg/d/", tarfile.DIRTYPE, 0o755),
        member("pkg/sym", tarfile.SYMTYPE, linkname=outside + "/secret"),
        member("pkg/dirsym", tarfile.SYMTYPE, linkname=outside),
        member("pkg/hard", LNK,
            linkname=linkname.replace("@OUTSIDE@", outside)),
        member("pkg/late", data=b"x"),
    ])
    with pytest.raises(ArchiveError, match="hard link"):
        unpack(path, tree / "out", strip_components=strip)

    for base in (tree / "out", tree / "out" / "pkg"):
        assert not os.path.lexists(str(base / "hard"))
    assert secret.read_bytes() == b"secret"
    assert os.lstat(str(secret)).st_nlink == 1


def test_a_hard_link_does_not_lead_to_what_replaced_a_file(tree):
    secret = tree / "outside" / "secret"
    secret.write_bytes(b"secret")
    path = make_tar(tree / "evil.tar", [
        member("f", data=b"x"),
        member("f", tarfile.SYMTYPE, linkname=str(secret)),
        member("hard", LNK, linkname="f"),
    ])
    with pytest.raises(ArchiveError, match="hard link"):
        unpack(path, tree / "out")
    assert not os.path.lexists(str(tree / "out" / "hard"))


def test_a_hard_link_is_not_written_through_a_symlink(tree):
    path = make_tar(tree / "evil.tar", [
        member("f", data=b"x"),
        member("link", tarfile.SYMTYPE, linkname=str(tree / "outside")),
        member("link/hard", LNK, linkname="f"),
    ])
    with pytest.raises(ArchiveError):
        unpack(path, tree / "out")
    assert nothing_outside(tree)


def test_a_hard_link_replaces_what_is_there(tree):
    secret = tree / "outside" / "secret"
    secret.write_bytes(b"secret")
    os.symlink(str(secret), str(tree / "out" / "a"))
    (tree / "out" / "b").write_bytes(b"old")
    path = make_tar(tree / "src.tar", [
        member("f", data=b"x"),
        member("a", LNK, linkname="f"),
        member("b", LNK, linkname="f"),
    ])
    unpack(path, tree / "out")
    for name in ("a", "b"):
        assert same_file(tree / "out" / "f", tree / "out" / name)
    assert secret.read_bytes() == b"secret"


def test_replacing_one_name_of_a_file_leaves_the_other_alone(tree):
    first = make_tar(tree / "a.tar", [
        member("f", data=b"old"),
        member("hard", LNK, linkname="f"),
    ])
    second = make_tar(tree / "b.tar", [member("hard", data=b"new")])
    unpack(first, tree / "out")
    unpack(second, tree / "out")
    assert (tree / "out" / "f").read_bytes() == b"old"
    assert (tree / "out" / "hard").read_bytes() == b"new"


def test_a_hard_link_with_data_is_refused(tree):
    path = make_cpio(tree / "src.cpio", [
        ("f", stat.S_IFREG | 0o644, 5, b"old"),
        ("hard", stat.S_IFREG | 0o644, 5, b"new"),
    ])
    with pytest.raises(ArchiveError, match="hard link"):
        unpack(path, tree / "out")
    assert (tree / "out" / "f").read_bytes() == b"old"


@pytest.mark.parametrize("data", [b"", b"evil"])
@pytest.mark.parametrize("mode", [
    stat.S_IFREG | 0o666,
    stat.S_IFDIR | 0o777,
    stat.S_IFLNK | 0o777,
    stat.S_IFIFO | 0o666,
])
def test_a_hard_link_of_any_type_stays_below_base_dir(tree, mode, data):
    # The first name is absolute and unpacked below base_dir, the link made
    # by libarchive would lead to the file outside.
    secret = tree / "outside" / "secret"
    secret.write_bytes(b"secret")
    os.chmod(str(secret), 0o600)
    path = make_cpio(tree / "evil.cpio", [
        (str(secret), stat.S_IFREG | 0o644, 5, b"x"),
        ("hard", mode, 5, data),
    ])
    out = tree / "out"
    if stat.S_ISREG(mode) and not data:
        unpack(path, out)
        assert same_file(out / str(secret).lstrip("/"), out / "hard")
    else:
        with pytest.raises(ArchiveError, match="hard link"):
            unpack(path, out)
        assert not os.path.lexists(str(out / "hard"))
    assert secret.read_bytes() == b"secret"
    assert mode_of(secret) == 0o600
    assert os.lstat(str(secret)).st_nlink == 1
