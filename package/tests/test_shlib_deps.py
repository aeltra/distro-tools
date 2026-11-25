# -*- encoding: utf-8 -*-
#
# The files whose dependencies are looked for.

import struct

from aeltra.package.aeltrapack.binarypackage import BinaryPackage
from aeltra.package.aeltrapack.filestats import FileStats


def elf(machine):
    """The headers of a shared library."""
    return b"\x7fELF\x02\x01\x01".ljust(16, b"\0") + struct.pack(
        "<HHIQQQIHHHHHH", 3, machine, 1, 0, 64, 0, 0, 64, 56, 1, 64, 0, 0
    ) + b"\0" * 200


class Package:

    host_type      = "none"
    install_prefix = "/usr"

    def __init__(self, basedir):
        self.basedir          = str(basedir)
        self.tools_references = []
        self.calls            = []
        self.contents         = {
            src: BinaryPackage.EntryAttributes({
                "stats": FileStats.detect_from_filename(str(basedir) + src)
            }) for src in ["/guile.go", "/lib.so"]
        }

    def run_program(self, cmd, src):
        self.calls.append(src)
        return ""


def test_files_for_no_machine_have_no_dependencies(tmp_path):
    (tmp_path / "guile.go").write_bytes(elf(0))
    (tmp_path / "lib.so").write_bytes(elf(183))
    package = Package(tmp_path)
    BinaryPackage.shlib_deps(package, {}, [])
    assert package.calls == ["/lib.so"]
