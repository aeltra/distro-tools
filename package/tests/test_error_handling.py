# -*- encoding: utf-8 -*-
#
# What goes wrong stops the build, with a message that says what it was.

import os
import stat

import pytest

from aeltra.error import AeltraError, PackagingError, UnmetDependency
from aeltra.miscellaneous.platform import Platform
from aeltra.package.aeltrapack import packagecontrol
from aeltra.package.aeltrapack.binarypackage import BinaryPackage
from aeltra.package.aeltrapack.packagecontrol import PackageControl
from aeltra.package.aeltrapack.sourcepackage import SourcePackage


# Programs

def test_output_is_returned():
    assert BinaryPackage.run_program(["sh", "-c", "echo a; echo b >&2"], "/f")\
        == "a\nb\n"


def test_failure_names_program_file_and_reason():
    with pytest.raises(PackagingError) as e:
        BinaryPackage.run_program(["sh", "-c", "echo reason >&2; exit 3"],
                                  "/usr/bin/f")
    assert str(e.value) == \
        "'sh' failed for '/usr/bin/f' with exit code 3: reason"


def test_program_that_is_not_there():
    with pytest.raises(PackagingError, match="unable to run 'nonexistent'"):
        BinaryPackage.run_program(["/none/nonexistent"], "/f")


def test_output_that_is_not_text():
    out = BinaryPackage.run_program(["printf", "\\377"], "/f")
    assert out == "\ufffd"


def test_program_has_no_input():
    assert BinaryPackage.run_program(["cat"], "/f") == ""


# Packages

class Stats:

    is_file = is_elf_binary = True
    is_symbolic_link = False
    arch_word_size   = 64
    machine          = "x86-64"
    device = inode   = 1
    mode = 0o644

    def restat(self, path):
        pass


class Attributes:

    stats = Stats()


class Package:

    STRIP_ARCHIVE_OPTIONS = BinaryPackage.STRIP_ARCHIVE_OPTIONS

    run_program = staticmethod(BinaryPackage.run_program)

    host_type = target_type = "none"
    install_prefix = "/usr"

    def __init__(self, basedir, src):
        self.basedir          = str(basedir)
        self.contents         = {src: Attributes()}
        self.tools_references = []


@pytest.fixture
def program(tmp_path, monkeypatch):
    path = tmp_path / "bin"
    path.mkdir()
    monkeypatch.setenv("PATH", "%s:%s" % (path, os.environ["PATH"]))

    def make(name, script):
        (path / name).write_text("#!/bin/sh\n" + script)
        (path / name).chmod(stat.S_IRWXU)

    return make


def test_failure_of_objdump(tmp_path, program):
    program("none-objdump", "echo 'file truncated' >&2\nexit 1\n")
    with pytest.raises(PackagingError, match="'none-objdump' failed for '/f'"):
        BinaryPackage.shlib_deps(Package(tmp_path, "/f"), {}, [])


@pytest.mark.parametrize("script", [
    "exit 1\n",
    "echo \"strip: Unable to recognise the format of the input file\" >&2\n",
])
def test_library_that_is_not_stripped(tmp_path, program, script):
    program("none-strip", script)
    (tmp_path / "l.a").write_bytes(b"!<arch>\n")
    with pytest.raises(PackagingError, match="/l.a"):
        BinaryPackage.strip_static_libraries(Package(tmp_path, "/l.a"))


def test_other_output_of_strip_is_shown(tmp_path, program, caplog):
    program("none-strip", "echo 'some remark' >&2\n")
    (tmp_path / "l.a").write_bytes(b"!<arch>\n")
    BinaryPackage.strip_static_libraries(Package(tmp_path, "/l.a"))
    assert [r.getMessage() for r in caplog.records] == ["some remark"]


class FakePackage:

    def __init__(self, reference=None, unmet=False):
        self.contents         = {}
        self.tools_references = []
        self.reference        = reference
        self.unmet            = unmet

    def prepare(self):
        pass

    strip_debug_symbols_and_unarm_rpath = strip_static_libraries = prepare

    def find_tools_interpreters(self):
        if self.reference:
            self.tools_references.append(self.reference)

    def shlib_deps(self, shlib_cache, bin_pkgs):
        if self.unmet:
            raise UnmetDependency("libx")


class Control:

    defines = {"AELTRA_INSTALL_PREFIX": "/usr"}

    _report_tools_references = PackageControl._report_tools_references

    def __init__(self, *bin_pkgs):
        self.bin_pkgs = bin_pkgs


def test_unmet_dependency_does_not_hide_the_rest(monkeypatch, caplog):
    class Cache:
        def __init__(self, prefix):
            pass

        def overlay_package(self, pkg):
            pass

    monkeypatch.setattr(packagecontrol, "ShlibCache", Cache)

    with pytest.raises(UnmetDependency):
        PackageControl.package(
            Control(FakePackage(unmet=True), FakePackage(reference="found"))
        )
    assert [r.getMessage() for r in caplog.records] == ["found"]


# Rules

class Source:

    _load_helpers = SourcePackage._load_helpers

    AELTRA_HELPERS_DIR = SourcePackage.AELTRA_HELPERS_DIR

    def __init__(self, script):
        self.rules = {"build": script}

    def _update_env(self, env):
        return dict(env, PATH=os.environ["PATH"])


# More than a shell reads at once.
LONG = ("# " + "x" * 70 + "\n") * 500


@pytest.mark.parametrize("script", [
    "false\n",
    "false\necho\n",
    LONG + "false\n",
    # reads from standard input
    "cat > /dev/null\n" + LONG + "false\n",
    "nonexistent-program\n",
])
def test_rules_fail(script):
    with pytest.raises(PackagingError, match="failed to build"):
        SourcePackage.run_action(Source(script), "build")


def test_rules_have_no_input(tmp_path):
    out = tmp_path / "out"
    SourcePackage.run_action(
        Source("cat > '%s'\n" % out + LONG + "echo end >> '%s'\n" % out),
        "build"
    )
    assert out.read_text() == "end\n"


# Number of jobs

@pytest.mark.parametrize("jobs", ["many", "-1", "1.5"])
def test_number_of_jobs(monkeypatch, jobs):
    monkeypatch.setenv("AELTRA_PARALLEL_JOBS", jobs)
    with pytest.raises(AeltraError, match="not a number"):
        Platform.parallel_jobs()
