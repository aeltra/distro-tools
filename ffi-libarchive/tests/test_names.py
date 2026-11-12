# -*- encoding: utf-8 -*-

import io
import json
import os
import subprocess
import sys
import tarfile

import pytest

from aeltra.ffi.libarchive import ArchiveFileReader

LIB_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")
)


def pax_tar(path):
    """UTF-8 names in pax headers, as current tar implementations write."""
    with tarfile.open(str(path), "w", format=tarfile.PAX_FORMAT) as t:
        info = tarfile.TarInfo("café")
        info.size  = 1
        info.uname = "jürgen"
        info.gname = "users"
        t.addfile(info, io.BytesIO(b"x"))

        info = tarfile.TarInfo("link")
        info.type     = tarfile.SYMTYPE
        info.linkname = "café"
        t.addfile(info)
    #end with
    return str(path)


def raw_tar(path, name, v7=False):
    """
    A name of raw bytes in a plain ustar header, or a v7 header, which
    has no owner names at all.
    """
    info = tarfile.TarInfo("x" * len(name))
    info.size  = 1
    info.uname = "" if v7 else "tobias"
    info.gname = "" if v7 else "tobias"

    header = bytearray(info.tobuf(format=tarfile.USTAR_FORMAT))
    header[0:len(name)] = name
    if v7:
        # No "ustar" magic, version, owner names or device numbers.
        header[257:500] = bytes(243)
    header[148:156] = b" " * 8
    header[148:156] = b"%06o\0 " % sum(header)

    with open(str(path), "wb") as f:
        f.write(bytes(header) + b"x".ljust(512, b"\0") + bytes(1024))
    return str(path)


def entries(path):
    with ArchiveFileReader(path) as archive:
        return [
            (e.pathname, e.uname, e.gname,
                e.symlink if e.is_symbolic_link else None, e.hardlink)
            for e in archive
        ]


def test_utf8_names(tmp_path):
    assert entries(pax_tar(tmp_path / "a.tar")) == [
        ("café", "jürgen", "users", None, None),
        ("link", "", "", "café", None),
    ]


def test_names_that_are_not_utf8_keep_their_bytes(tmp_path):
    name = entries(raw_tar(tmp_path / "a.tar", b"caf\xe9"))[0][0]
    assert name.encode("utf-8", "surrogateescape") == b"caf\xe9"


def test_a_v7_header_has_no_owner_names(tmp_path):
    assert entries(raw_tar(tmp_path / "a.tar", b"f", v7=True)) \
        == [("f", None, None, None, None)]


def test_names_that_are_not_utf8_are_unpacked_as_they_are(tmp_path):
    path = raw_tar(tmp_path / "a.tar", b"caf\xe9")
    (tmp_path / "out").mkdir()
    with ArchiveFileReader(path) as archive:
        archive.unpack_to_disk(str(tmp_path / "out"))
    assert os.listdir(os.fsencode(str(tmp_path / "out"))) == [b"caf\xe9"]


@pytest.mark.parametrize("unpack", [False, True])
def test_utf8_names_in_the_c_locale(tmp_path, unpack):
    # Where libarchive converts names to ASCII and warns that it can't.
    path = pax_tar(tmp_path / "a.tar")
    (tmp_path / "out").mkdir()

    script = """if True:
        import json, os, sys, types
        aeltra = types.ModuleType("aeltra")
        aeltra.__path__ = [os.path.join(sys.argv[1], "aeltra")]
        sys.modules["aeltra"] = aeltra
        from aeltra.ffi.libarchive import ArchiveFileReader
        with ArchiveFileReader(sys.argv[2]) as archive:
            if sys.argv[3] == "unpack":
                archive.unpack_to_disk(sys.argv[4])
                print(json.dumps(sorted(os.listdir(sys.argv[4]))))
            else:
                print(json.dumps([[e.pathname, e.uname] for e in archive]))
    """
    env = dict(os.environ, LC_ALL="C")
    out = subprocess.run(
        [sys.executable, "-I", "-c", script, LIB_DIR, path,
            "unpack" if unpack else "list", str(tmp_path / "out")],
        env=env, check=True, stdout=subprocess.PIPE
    ).stdout

    if unpack:
        assert json.loads(out) == ["café", "link"]
    else:
        assert json.loads(out) == [["café", "jürgen"], ["link", ""]]
