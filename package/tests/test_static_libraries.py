# -*- encoding: utf-8 -*-
#
# The debug information of static libraries is not packaged.

import os
import shutil
import subprocess

import pytest

from aeltra.package.aeltrapack.binarypackage import BinaryPackage
from aeltra.package.aeltrapack.filestats import FileStats

HOST   = "x86_64-tools-linux-musl"
TARGET = "aarch64-linux-musl"


class Package:
    """What strip_static_libraries() uses of a package."""

    STRIP_ARCHIVE_OPTIONS = BinaryPackage.STRIP_ARCHIVE_OPTIONS

    run_program = staticmethod(BinaryPackage.run_program)

    def __init__(self, basedir, *files, target_type=HOST):
        self.basedir     = str(basedir)
        self.host_type   = HOST
        self.target_type = target_type
        self.contents    = {}

        for src in files:
            self.contents[src] = BinaryPackage.EntryAttributes({
                "stats": FileStats.detect_from_filename(str(basedir) + src)
            })


@pytest.fixture
def stripped(tmp_path, monkeypatch):
    """Put programs into the path that write down how they were called."""
    log  = tmp_path / "calls"
    path = tmp_path / "bin"
    path.mkdir()

    for name in [HOST + "-strip", TARGET + "-strip"]:
        script = path / name
        script.write_text(
            '#!/bin/sh\n'
            'for LAST; do true; done\n'
            'echo "%s $LAST" >> "%s"\n' % (name, log)
        )
        script.chmod(0o755)

    monkeypatch.setenv("PATH", "%s:%s" % (path, os.environ["PATH"]))

    def run(package):
        BinaryPackage.strip_static_libraries(package)
        if not log.exists():
            return []
        return [
            line.replace(package.basedir, "")
            for line in log.read_text().splitlines()
        ]

    return run


def archive(basedir, src, content=b"!<arch>\n"):
    path = basedir / src.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return src


def test_archive_is_stripped(tmp_path, stripped):
    root = tmp_path / "root"
    a = archive(root, "/usr/lib/liba.a")
    assert stripped(Package(root, a)) == [HOST + "-strip /usr/lib/liba.a"]


def test_other_files_are_left_alone(tmp_path, stripped):
    root  = tmp_path / "root"
    files = [
        archive(root, "/usr/lib/script.a", b"INPUT(-lc)\n"),
        archive(root, "/usr/lib/thin.a", b"!<thin>\n"),
        archive(root, "/usr/lib/empty.a", b""),
        archive(root, "/usr/lib/archive.lib"),
    ]
    (root / "usr/lib/link.a").symlink_to("archive.lib")
    files.append("/usr/lib/link.a")
    assert stripped(Package(root, *files)) == []


def test_hard_link_is_stripped_once(tmp_path, stripped):
    root = tmp_path / "root"
    a = archive(root, "/usr/lib/a.a")
    os.link(root / "usr/lib/a.a", root / "usr/lib/b.a")
    assert len(stripped(Package(root, a, "/usr/lib/b.a"))) == 1


def test_cross_compiler(tmp_path, stripped):
    root  = tmp_path / "root"
    files = [
        archive(root, "/tools/%s/lib/libb.a" % TARGET),
        archive(root, "/tools/lib/gcc/%s/16.2.0/libc.a" % TARGET),
    ]
    assert stripped(Package(root, *files, target_type=TARGET)) == [
        TARGET + "-strip /tools/%s/lib/libb.a" % TARGET,
        TARGET + "-strip /tools/lib/gcc/%s/16.2.0/libc.a" % TARGET,
    ]


@pytest.mark.skipif(
    not (shutil.which("cc") and shutil.which("ar")), reason="no compiler"
)
@pytest.mark.parametrize("mode", [0o644, 0o444])
def test_with_a_compiler(tmp_path, mode):
    def run(*cmd):
        return subprocess.run(
            cmd, cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout

    (tmp_path / "f.c").write_text("int f(void) { return 1; }\n")
    (tmp_path / "m.c").write_text("int f(void); int main() "
                                  "{ return f() - 1; }\n")
    run("cc", "-g", "-c", "f.c")
    run("ar", "rc", "libf.a", "f.o")
    assert ".debug_info" in run("readelf", "-SW", "libf.a")
    os.chmod(tmp_path / "libf.a", mode)

    package = Package(tmp_path, "/libf.a")
    size    = package.contents["/libf.a"].stats.st_size
    BinaryPackage.strip_static_libraries(package)

    assert ".debug_info" not in run("readelf", "-SW", "libf.a")
    assert package.contents["/libf.a"].stats.st_size < size
    run("cc", "m.c", "libf.a", "-o", "m")
    run("./m")
