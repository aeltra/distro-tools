# -*- encoding: utf-8 -*-
#
# What is packaged for the target must not need the tools folder.

import shutil
import subprocess

import pytest

from aeltra.error import PackagingError, UnmetDependency
from aeltra.package.aeltrapack.basepackage import BasePackage
from aeltra.package.aeltrapack.binarypackage import BinaryPackage
from aeltra.package.aeltrapack.filestats import FileStats
from aeltra.package.aeltrapack.packagecontrol import PackageControl


RPATH = "'/m' is for the target and has the RPATH '%s'."


class Package:

    run_program = staticmethod(BinaryPackage.run_program)

    _find_and_register_dependency = \
        BinaryPackage._find_and_register_dependency

    def __init__(self, basedir, *files, prefix="/usr", name="a"):
        self.basedir        = str(basedir)
        self.install_prefix = prefix
        self.host_type      = "none"
        self.name           = name
        self.version        = "1.0-1"
        self.relations      = {}
        self.tools_references = []
        self.contents       = {
            src: BinaryPackage.EntryAttributes({
                "stats": FileStats.detect_from_filename(str(basedir) + src)
            }) for src in files
        }


INTERPRETER = "'/%s' is for the target and has the interpreter '%s'."


def interpreters(package):
    BinaryPackage.find_tools_interpreters(package)
    return package.tools_references


def rpaths(package):
    BinaryPackage.shlib_deps(package, {}, [])
    return package.tools_references


@pytest.mark.parametrize("first_line, expected", [
    (b"#!/tools/bin/perl -w", "/tools/bin/perl"),
    (b"#! /tools/bin/busybox sh", "/tools/bin/busybox"),
    (b"#!/tools/bin/python3", "/tools/bin/python3"),
    (b"#!/tools/bin/something", "/tools/bin/something"),
    (b"#!/usr/bin/perl", None),
    (b"#!/usr/bin/env python3", None),
    (b"#!/toolsX/bin/perl", None),
    (b"# /tools/bin/perl", None),
    (b"#!/bin/sh /tools/a", None),
    (b"#!/bin/sh\necho /tools/a", None),
    (b"", None),
    (b"#!", None),
    (b"#!\xff\xfe", None),
])
def test_script(tmp_path, first_line, expected):
    (tmp_path / "s").write_bytes(first_line + b"\necho\n")
    assert interpreters(Package(tmp_path, "/s")) == \
        ([INTERPRETER % ("s", expected)] if expected else [])


def test_tools_may_need_tools(tmp_path):
    (tmp_path / "s").write_text("#!/tools/bin/perl\n")
    assert interpreters(Package(tmp_path, "/s", prefix="/tools")) == []


def test_links_and_folders_are_not_read(tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "l").symlink_to("/tools/bin/nothing")
    assert interpreters(Package(tmp_path, "/d", "/l")) == []


@pytest.mark.parametrize("description, expected", [
    ("ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV), "
     "dynamically linked, interpreter /usr/lib/ld-musl-aarch64.so.1, "
     "BuildID[sha1]=7, stripped", "/usr/lib/ld-musl-aarch64.so.1"),
    ("ELF 64-bit LSB executable, x86-64, dynamically linked, "
     "interpreter /tools/lib/ld.so", "/tools/lib/ld.so"),
    ("ELF 64-bit LSB shared object, ARM aarch64, stripped", None),
    ("POSIX shell script, ASCII text executable", None),
])
def test_interpreter(description, expected):
    class Magic:
        name = description

    assert FileStats(Magic(), None).interpreter == expected


needs_compiler = pytest.mark.skipif(
    not (shutil.which("cc") and shutil.which("objdump")),
    reason="no compiler"
)


@pytest.fixture
def program(tmp_path):
    def make(*options):
        (tmp_path / "m.c").write_text("int main() { return 0; }\n")
        subprocess.run(
            ["cc", "m.c", "-nostdlib", "-Wl,-e,main", "-o", "m", *options],
            cwd=tmp_path, check=True, capture_output=True
        )
        return "/m"
    return make


@needs_compiler
def test_program_interpreter(tmp_path, program):
    src = program("-Wl,--dynamic-linker=/tools/lib/ld.so", "-Wl,-pie",
                  "-Wl,--no-as-needed", "-Wl,-rpath,/usr/lib")
    assert interpreters(Package(tmp_path, src)) == \
        [INTERPRETER % ("m", "/tools/lib/ld.so")]


@needs_compiler
@pytest.mark.parametrize("rpath, prefix, reported", [
    ("/tools/aarch64-linux-musl/lib/../lib", "/usr", True),
    ("/usr/lib/a:/tools/lib", "/usr", True),
    ("/tools", "/usr", True),
    ("/usr/lib/a", "/usr", False),
    ("/usr/tools/lib", "/usr", False),
    ("/tools/lib", "/tools", False),
])
@pytest.mark.parametrize("tag", ["--enable-new-dtags", "--disable-new-dtags"])
def test_rpath(tmp_path, program, rpath, prefix, reported, tag):
    src = program("-Wl,-pie", "-Wl," + tag, "-Wl,-rpath," + rpath)
    assert rpaths(Package(tmp_path, src, prefix=prefix)) == \
        ([RPATH % rpath] if reported else [])


class Cache(dict):

    def get(self, name, default, fallback=None):
        return default


@pytest.fixture
def libdir(tmp_path):
    path = tmp_path / "usr" / "lib"
    path.mkdir(parents=True)
    (path / "liba.so").symlink_to("liba.so.1")
    return path


def test_dependency_on_a_package_of_the_build(tmp_path, libdir):
    (libdir / "liba.so.1").write_text("")

    dev = Package(tmp_path, "/usr/lib/liba.so", name="liba-dev")
    lib = Package(tmp_path, "/usr/lib/liba.so.1", name="liba1")
    BinaryPackage.shlib_deps(dev, Cache(), [dev, lib])

    requires = dev.relations["requires"]
    assert isinstance(requires, BasePackage.DependencySpecification)
    assert str(requires) == "liba1 (= 1.0-1)"


def test_missing_dependency_is_an_error(tmp_path, libdir):
    dev = Package(tmp_path, "/usr/lib/liba.so", name="liba-dev")
    with pytest.raises(UnmetDependency):
        BinaryPackage.shlib_deps(dev, Cache(), [dev])


class Control:
    """What package() uses of a PackageControl object."""

    parms   = {"enable_packages": [], "disable_packages": ["x"]}
    defines = {"AELTRA_INSTALL_PREFIX": "/usr"}

    _report_tools_references = PackageControl._report_tools_references

    def build_references(self):
        return []

    def __init__(self, *bin_pkgs):
        self.bin_pkgs = bin_pkgs


class FakePackage:

    def __init__(self, interpreter=None, rpath=None):
        self.contents         = {}
        self.tools_references = []
        self.interpreter      = interpreter
        self.rpath            = rpath
        self.packed           = False

    def prepare(self):
        pass

    strip_debug_symbols_and_unarm_rpath = strip_static_libraries = prepare

    def find_tools_interpreters(self):
        if self.interpreter:
            self.tools_references.append(self.interpreter)

    def shlib_deps(self, shlib_cache, bin_pkgs):
        if self.rpath:
            self.tools_references.append(self.rpath)

    def do_pack(self):
        self.packed = True


@pytest.fixture
def no_cache(monkeypatch):
    class Cache:
        def __init__(self, prefix):
            pass

        def overlay_package(self, pkg):
            pass

    monkeypatch.setattr(
        "aeltra.package.aeltrapack.packagecontrol.ShlibCache", Cache
    )


def test_build_stops_after_all_are_reported(no_cache, caplog):
    pkgs = [FakePackage("a", "b"), FakePackage(), FakePackage(rpath="c")]

    with pytest.raises(PackagingError):
        PackageControl.package(Control(*pkgs))

    assert caplog.messages == ["a", "b", "c"]
    assert not any(p.packed for p in pkgs)


def test_packages_are_made(no_cache, caplog):
    pkgs = [FakePackage(), FakePackage()]
    PackageControl.package(Control(*pkgs))
    assert caplog.messages == []
    assert all(p.packed for p in pkgs)
