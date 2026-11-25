# -*- encoding: utf-8 -*-
#
# Text files that mention the folder of the build are reported.

import pytest

from aeltra.package.aeltrapack.binarypackage import BinaryPackage
from aeltra.package.aeltrapack.filestats import FileStats
from aeltra.package.aeltrapack.packagecontrol import PackageControl

WORK = "/home/user/build/pkg-1"


class Package:

    def __init__(self, basedir, *files):
        self.basedir  = str(basedir)
        self.contents = {
            src: BinaryPackage.EntryAttributes({
                "stats": FileStats.detect_from_filename(str(basedir) + src)
            }) for src in files
        }


class Control:
    """What build_references() uses of a PackageControl object."""

    def __init__(self, *bin_pkgs):
        self.bin_pkgs = bin_pkgs
        self.defines  = {"AELTRA_WORK_DIR": WORK}


def references(*bin_pkgs):
    return PackageControl.build_references(Control(*bin_pkgs))


@pytest.mark.parametrize("content, expected", [
    (b"CFLAGS=-ffile-prefix-map=" + WORK.encode() + b"=.\n", True),
    (b"cd " + WORK.encode() + b"/sources\n", True),
    (b"cd '" + WORK.encode() + b"'", True),
    (b"\xff\xfe " + WORK.encode(), True),
    (b"cd " + WORK.encode() + b"0/sources\n", False),
    (b"cd " + WORK.encode() + b"-2\n", False),
    (b"cd /home/user\n", False),
    (b"\0" + WORK.encode(), False),
    (b"", False),
])
def test_content(tmp_path, content, expected):
    (tmp_path / "f").write_bytes(content)
    assert references(Package(tmp_path, "/f")) == \
        (["/f"] if expected else [])


def test_all_packages_are_checked(tmp_path):
    for name in "abc":
        (tmp_path / name).write_text("no")
    (tmp_path / "b").write_text(WORK)
    (tmp_path / "c").write_text(WORK)

    assert references(
        Package(tmp_path, "/a", "/b"), Package(tmp_path, "/c")
    ) == ["/b", "/c"]


def test_links_and_folders_are_not_read(tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "l").symlink_to(WORK)
    assert references(Package(tmp_path, "/d", "/l")) == []
