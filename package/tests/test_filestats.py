# -*- encoding: utf-8 -*-
#
# What FileStats says about files, and which ones libmagic gets to see.

import os
import struct

import pytest

from aeltra.package.aeltrapack import filestats
from aeltra.package.aeltrapack.filestats import FileStats


def elf(machine, big_endian=False, bits=64):
    """The headers of a shared library."""
    order = ">" if big_endian else "<"
    word  = "Q" if bits == 64 else "I"
    size  = 64 if bits == 64 else 52
    ident = b"\x7fELF" + bytes(
        [2 if bits == 64 else 1, 2 if big_endian else 1, 1]
    )
    return ident.ljust(16, b"\0") + struct.pack(
        order + "HHI" + 3 * word + "IHHHHHH",
        3, machine, 1, 0, size, 0, 0, size, 56, 0, 64, 0, 0
    ) + b"\0" * 200


def detect(tmp_path, content):
    path = tmp_path / "f"
    path.write_bytes(content)
    return FileStats.detect_from_filename(str(path))


@pytest.mark.parametrize("machine, big_endian, bits, name", [
    (183, False, 64, "ARM aarch64"),
    (62, False, 64, "x86-64"),
    (22, True, 64, "IBM S/390"),
    (3, False, 32, "Intel"),
    (0, False, 64, "no machine"),
    (0, True, 64, "no machine"),
])
def test_elf(tmp_path, machine, big_endian, bits, name):
    stats = detect(tmp_path, elf(machine, big_endian, bits))
    assert stats.is_file
    assert stats.is_elf_binary
    assert not stats.is_script
    assert stats.arch_word_size == str(bits)
    assert stats.machine.startswith(name)


@pytest.mark.parametrize("content", [
    b"", b"\x7f", b"\x7fEL", b"\x7fELF", b"\x7fELG" + b"\0" * 100,
    b"text\n", b"!<arch>\n", b"\0" * 100,
])
def test_not_elf(tmp_path, content):
    stats = detect(tmp_path, content)
    assert stats.is_file
    assert not stats.is_elf_binary
    assert not stats.is_dynamically_linked
    assert not stats.is_script
    assert stats.is_stripped
    assert stats.machine is None
    assert stats.arch_word_size is None
    assert stats.interpreter is None
    assert stats.build_id is None


@pytest.mark.parametrize("content, expected", [
    (b"#!/bin/sh\n", True), (b"#!", True), (b"#! /bin/sh", True),
    (b"#", False), (b" #!/bin/sh", False), (b"", False),
])
def test_script(tmp_path, content, expected):
    stats = detect(tmp_path, content)
    assert stats.is_script == expected
    assert not stats.is_elf_binary


def test_only_elf_files_go_to_libmagic(tmp_path, monkeypatch):
    class Magic:
        calls = []

        def detect_from_filename(self, filename):
            self.calls.append(os.path.basename(filename))
            return filestats.FileMagic(mime_type="", encoding="", name="")

    monkeypatch.setattr(filestats, "magic", Magic())

    for name, content in [("a", b"text"), ("b", elf(62)), ("c", b"#!/b")]:
        (tmp_path / name).write_bytes(content)
        FileStats.detect_from_filename(str(tmp_path / name))

    assert Magic.calls == ["b"]


def test_not_regular_files(tmp_path):
    (tmp_path / "e").write_bytes(elf(62))
    (tmp_path / "d").mkdir()
    (tmp_path / "l").symlink_to("e")
    (tmp_path / "x").symlink_to("nowhere")
    os.mkfifo(tmp_path / "p")

    for name in "dlxp":
        stats = FileStats.detect_from_filename(str(tmp_path / name))
        assert not stats.is_file
        assert not stats.is_elf_binary
        assert not stats.is_script

    assert stats.is_fifo

    with pytest.raises(ValueError):
        FileStats.detect_from_filename(str(tmp_path / "none"))


@pytest.mark.skipif(os.getuid() == 0, reason="root may read everything")
def test_file_that_can_not_be_read(tmp_path):
    (tmp_path / "f").write_bytes(elf(62))
    (tmp_path / "f").chmod(0)
    stats = FileStats.detect_from_filename(str(tmp_path / "f"))
    assert stats.is_file and not stats.is_elf_binary
