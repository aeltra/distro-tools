# -*- encoding: utf-8 -*-
#
# The modes that files and directories get in a package when the package
# file states none.

import logging
import os

import pytest

from aeltra.package.aeltrapack.binarypackage import BinaryPackage
from aeltra.package.aeltrapack.filestats import FileStats


def make_file(tmp_path, name, mode):
    path = tmp_path / name
    path.write_text("content\n")
    os.chmod(path, mode)
    return FileStats.detect_from_filename(str(path))


def make_dir(tmp_path, name, mode):
    path = tmp_path / name
    path.mkdir()
    os.chmod(path, mode)
    return FileStats.detect_from_filename(str(path))


@pytest.mark.parametrize("on_disk, expected", [
    (0o644, 0o644),
    # What a umask of 002 or 077 leaves behind is not kept.
    (0o664, 0o644),
    (0o666, 0o644),
    # The owner can always read and write.
    (0o444, 0o644),
    (0o755, 0o755),
    (0o775, 0o755),
    (0o555, 0o755),
    # Executable for some means executable for all.
    (0o744, 0o755),
    (0o654, 0o755),
])
def test_file_gets_default_mode(tmp_path, on_disk, expected):
    stats = make_file(tmp_path, "file", on_disk)
    assert BinaryPackage.default_mode("/usr/share/tool/file", stats) == \
        expected


@pytest.mark.parametrize("on_disk", [0o755, 0o775, 0o777, 0o555])
def test_directory_gets_0755(tmp_path, on_disk):
    stats = make_dir(tmp_path, "dir", on_disk)
    assert BinaryPackage.default_mode("/usr/share/tool/dir", stats) == \
        0o755


@pytest.mark.parametrize("on_disk, expected", [
    # A setuid or setgid bit is dropped.
    (0o4755, 0o755),
    (0o2755, 0o755),
    (0o6755, 0o755),
    (0o4111, 0o755),
    # What group and others cannot read is opened to them.
    (0o600, 0o644),
    (0o640, 0o644),
    (0o604, 0o644),
    (0o700, 0o755),
    (0o750, 0o755),
])
def test_file_with_unusual_mode_gets_default_mode(tmp_path, on_disk,
        expected):
    stats = make_file(tmp_path, "file", on_disk)
    assert BinaryPackage.default_mode("/usr/share/tool/file", stats) == \
        expected


@pytest.mark.parametrize("on_disk", [
    0o1777, 0o2775, 0o1755, 0o700, 0o750, 0o710, 0o754,
])
def test_directory_with_unusual_mode_gets_0755(tmp_path, on_disk):
    stats = make_dir(tmp_path, "dir", on_disk)
    assert BinaryPackage.default_mode("/usr/share/tool/dir", stats) == \
        0o755


class Prefix:
    install_prefix = "/usr"


def apply(contents):
    # apply_default_modes() uses nothing else of the object it is called
    # on.
    BinaryPackage.apply_default_modes(Prefix(), contents)


# What dh_fixperms does by the place and the name of a file. Each line:
# the path in the package, the mode on disk, the mode in the package.
LOCATION_RULES = [
    # Documentation is not executable, examples are left alone.
    ("/usr/share/doc/tool/README",             0o755, 0o644),
    ("/usr/share/doc/tool/html/index.html",    0o775, 0o644),
    ("/usr/share/doc/tool/examples/run.sh",    0o755, 0o755),
    ("/usr/share/doc/tool/examples/data.txt",  0o644, 0o644),
    # Only the examples folder right below the folder of the package.
    ("/usr/share/doc/tool/sub/examples/run",   0o755, 0o644),
    # Manual pages, headers, desktop files, themes.
    ("/usr/share/man/man1/tool.1",             0o755, 0o644),
    ("/usr/include/tool/tool.h",               0o755, 0o644),
    ("/usr/share/applications/tool.desktop",   0o755, 0o644),
    ("/usr/share/lintian/overrides/tool",      0o755, 0o644),
    ("/usr/share/themes/Tool/gtk.css",         0o755, 0o644),
    # Perl modules.
    ("/usr/share/perl5/Tool.pm",               0o755, 0o644),
    ("/usr/lib/perl5/Tool/XS.pm",              0o755, 0o644),
    ("/usr/share/tool/Tool.pm",                0o755, 0o755),
    ("/usr/share/perl5/tool.pl",               0o755, 0o755),
    # Libraries and other files by their names.
    ("/usr/lib/libtool.so.1.2.3",              0o755, 0o644),
    ("/usr/lib/libtool.so",                    0o755, 0o644),
    ("/usr/lib/libtool.a",                     0o755, 0o644),
    ("/usr/lib/libtool.la",                    0o755, 0o644),
    ("/usr/lib/security/pam_tool.so",          0o755, 0o644),
    ("/usr/share/tool/www/tool.js",            0o755, 0o644),
    ("/usr/share/tool/www/tool.css",           0o755, 0o644),
    ("/usr/share/tool/www/logo.png",           0o755, 0o644),
    ("/usr/lib/ocaml/tool.cmxs",               0o755, 0o644),
    ("/usr/lib/tool/binding.node",             0o755, 0o644),
    ("/usr/lib/tool/helper",                   0o755, 0o755),
    # Programs are executable, also when their name says library.
    ("/usr/bin/tool",                          0o644, 0o755),
    ("/usr/sbin/toold",                        0o644, 0o755),
    ("/bin/tool",                              0o644, 0o755),
    ("/sbin/toold",                            0o644, 0o755),
    ("/usr/games/tool",                        0o644, 0o755),
    ("/usr/libexec/tool/helper",               0o644, 0o755),
    ("/usr/libexec/tool/plugin.so",            0o755, 0o755),
    ("/usr/bin/tool.js",                       0o755, 0o755),
    ("/etc/init.d/tool",                       0o644, 0o755),
    ("/usr/share/tool/bin/tool",               0o644, 0o644),
    # The .ali files of Ada are read-only.
    ("/usr/lib/ada/adalib/tool/tool.ali",      0o644, 0o444),
    ("/usr/share/tool/tool.ali",               0o644, 0o644),
    # The programs of a package for Node.js.
    ("/usr/lib/nodejs/tool/cli.js",            0o644, 0o755),
    ("/usr/lib/nodejs/tool/sub/bin.js",        0o644, 0o755),
    ("/usr/lib/nodejs/tool/index.js",          0o755, 0o644),
    # sudo refuses a file that others can read.
    ("/etc/sudoers.d/tool",                    0o644, 0o440),
    ("/etc/sudoers.d/tool",                    0o440, 0o440),
]


@pytest.mark.parametrize("src, on_disk, expected", LOCATION_RULES)
def test_mode_by_place_and_name(tmp_path, src, on_disk, expected):
    stats = make_file(tmp_path, "file", on_disk)
    assert BinaryPackage.default_mode(src, stats) == expected


@pytest.mark.parametrize("src, on_disk, expected", [
    ("/tools/bin/tool",              0o644, 0o755),
    ("/tools/lib/libtool.so.1",      0o755, 0o644),
    ("/tools/include/tool.h",        0o755, 0o644),
    ("/tools/share/doc/tool/README", 0o755, 0o644),
    # Not a folder for programs with this prefix.
    ("/usr/bin/tool",                0o644, 0o644),
])
def test_places_follow_the_install_prefix(tmp_path, src, on_disk, expected):
    stats = make_file(tmp_path, "file", on_disk)
    assert BinaryPackage.default_mode(src, stats, "/tools") == expected


def test_no_warning_for_sudoers_file_that_stays_0440(tmp_path, caplog):
    contents = {
        "/etc/sudoers.d/tool": BinaryPackage.EntryAttributes({
            "stats": make_file(tmp_path, "tool", 0o440),
        }),
    }

    with caplog.at_level(logging.WARNING):
        apply(contents)

    assert contents["/etc/sudoers.d/tool"].mode == 0o440
    assert caplog.records == []


def test_stated_mode_is_kept(tmp_path):
    contents = {
        "/usr/bin/su": BinaryPackage.EntryAttributes({
            "mode":  "4755",
            "stats": make_file(tmp_path, "su", 0o755),
        }),
        "/etc/secret": BinaryPackage.EntryAttributes({
            "mode":  "0600",
            "stats": make_file(tmp_path, "secret", 0o664),
        }),
        "/tmp": BinaryPackage.EntryAttributes({
            "deftype": "dir",
            "mode":    "1777",
            "stats":   FileStats.default_dir_stats(),
        }),
    }

    apply(contents)

    assert contents["/usr/bin/su"].mode == 0o4755
    assert contents["/etc/secret"].mode == 0o600
    assert contents["/tmp"].mode == 0o1777


def test_stated_mode_makes_special_bit_on_disk_acceptable(tmp_path):
    contents = {
        "/usr/bin/su": BinaryPackage.EntryAttributes({
            "mode":  "4755",
            "stats": make_file(tmp_path, "su", 0o4755),
        }),
    }

    apply(contents)

    assert contents["/usr/bin/su"].mode == 0o4755


def test_entries_without_mode_get_the_default(tmp_path):
    contents = {
        "/usr": BinaryPackage.EntryAttributes({
            "deftype": "dir",
            "stats":   make_dir(tmp_path, "usr", 0o775),
        }),
        "/usr/bin/tool": BinaryPackage.EntryAttributes({
            "stats": make_file(tmp_path, "tool", 0o775),
        }),
        "/etc/tool.conf": BinaryPackage.EntryAttributes({
            "stats": make_file(tmp_path, "tool.conf", 0o664),
        }),
        "/var/lib/tool": BinaryPackage.EntryAttributes({
            "deftype": "dir",
            "stats":   FileStats.default_dir_stats(),
        }),
    }

    apply(contents)

    assert contents["/usr"].mode == 0o755
    assert contents["/usr/bin/tool"].mode == 0o755
    assert contents["/etc/tool.conf"].mode == 0o644
    assert contents["/var/lib/tool"].mode == 0o755


def test_symbolic_link_is_left_alone(tmp_path):
    (tmp_path / "target").write_text("content\n")
    link = tmp_path / "link"
    link.symlink_to("target")

    contents = {
        "/usr/bin/link": BinaryPackage.EntryAttributes({
            "stats": FileStats.detect_from_filename(str(link)),
        }),
    }

    apply(contents)

    assert contents["/usr/bin/link"].mode is None


@pytest.mark.parametrize("on_disk, in_package", [
    (0o4755, 0o755),
    (0o2755, 0o755),
    (0o600,  0o644),
    (0o640,  0o644),
    (0o700,  0o755),
])
def test_warning_for_file_names_path_and_modes(tmp_path, caplog, on_disk,
        in_package):
    contents = {
        "/usr/lib/tool/su": BinaryPackage.EntryAttributes({
            "stats": make_file(tmp_path, "su", on_disk),
        }),
    }

    with caplog.at_level(logging.WARNING):
        apply(contents)

    assert contents["/usr/lib/tool/su"].mode == in_package
    assert len(caplog.records) == 1
    assert "'/usr/lib/tool/su' has mode %04o on disk and gets %04o" % \
        (on_disk, in_package) in caplog.text
    assert "state its mode in the package file" in caplog.text


@pytest.mark.parametrize("on_disk", [0o1777, 0o2775, 0o750, 0o700])
def test_warning_for_directory(tmp_path, caplog, on_disk):
    contents = {
        "/var/spool/tool": BinaryPackage.EntryAttributes({
            "deftype": "dir",
            "stats":   make_dir(tmp_path, "tool", on_disk),
        }),
    }

    with caplog.at_level(logging.WARNING):
        apply(contents)

    assert contents["/var/spool/tool"].mode == 0o755
    assert "'/var/spool/tool' has mode %04o on disk and gets 0755" % \
        on_disk in caplog.text


@pytest.mark.parametrize("on_disk", [0o644, 0o664, 0o444, 0o755, 0o775])
def test_no_warning_for_what_the_umask_leaves(tmp_path, caplog, on_disk):
    contents = {
        "/usr/bin/tool": BinaryPackage.EntryAttributes({
            "stats": make_file(tmp_path, "tool", on_disk),
        }),
    }

    with caplog.at_level(logging.WARNING):
        apply(contents)

    assert caplog.records == []


def test_no_warning_when_the_mode_is_stated(tmp_path, caplog):
    contents = {
        "/usr/bin/su": BinaryPackage.EntryAttributes({
            "mode":  "4755",
            "stats": make_file(tmp_path, "su", 0o4755),
        }),
        "/etc/secret": BinaryPackage.EntryAttributes({
            "mode":  "0600",
            "stats": make_file(tmp_path, "secret", 0o600),
        }),
    }

    with caplog.at_level(logging.WARNING):
        apply(contents)

    assert caplog.records == []


PACKAGE_XML = """\
<package name="tool" version="1.0" revision="1" maintainer="Jane Doe"
        email="jane@example.org" source="tool" architecture="aarch64"
        date="2026-01-01 00:00:00+00:00" section="utils">
    <description>
        <summary>A tool</summary>
        <p>A tool.</p>
    </description>
    <contents>
        <file src="${prefix}/bin"/>
        <file src="${prefix}/bin/su" mode="4755"/>
        <file src="/etc/tool.conf"/>
        <dir src="/var/lib/tool" mode="0750"/>
    </contents>
</package>
"""


def make_tree(tmp_path):
    # The folder a build installs into may have any mode, the one of a
    # temporary folder for example.
    os.chmod(tmp_path, 0o700)
    old_umask = os.umask(0o002)

    try:
        (tmp_path / "usr" / "bin").mkdir(parents=True)
        (tmp_path / "etc").mkdir()

        for name in ("tool", "su"):
            path = tmp_path / "usr" / "bin" / name
            path.write_text("#!/bin/sh\n")
            os.chmod(path, 0o775)

        (tmp_path / "etc" / "tool.conf").write_text("setting\n")
    finally:
        os.umask(old_umask)

    return tmp_path


@pytest.fixture
def package(tmp_path):
    pkg = BinaryPackage(PACKAGE_XML, debug_pkgs=False)
    pkg.basedir = str(make_tree(tmp_path))
    return pkg


def test_file_list_of_a_package(package):
    package.prepare()

    modes = {src: attr.mode for src, attr in package.contents.items()}

    assert modes == {
        "/":              0o755,
        "/etc":           0o755,
        "/etc/tool.conf": 0o644,
        "/usr":           0o755,
        "/usr/bin":       0o755,
        "/usr/bin/su":    0o4755,
        "/usr/bin/tool":  0o755,
        "/var/lib/tool":  0o750,
    }


def test_stated_mode_wins_over_the_rule_for_libraries(tmp_path):
    # As for libc.so of musl, which is the dynamic loader too.
    xml = PACKAGE_XML.replace(
        '<file src="/etc/tool.conf"/>',
        '<file src="${prefix}/lib/libc.so" mode="0755"/>\n'
        '        <file src="${prefix}/lib/*.so*"/>'
    )
    pkg = BinaryPackage(xml, debug_pkgs=False)
    pkg.basedir = str(make_tree(tmp_path))

    libdir = tmp_path / "usr" / "lib"
    libdir.mkdir()
    for name in ("libc.so", "libtool.so.1"):
        (libdir / name).write_text("content\n")
        os.chmod(libdir / name, 0o755)

    pkg.prepare()

    assert pkg.contents["/usr/lib/libc.so"].mode == 0o755
    assert pkg.contents["/usr/lib/libtool.so.1"].mode == 0o644


def test_file_list_drops_unstated_setuid_bit(package, caplog):
    os.chmod(os.path.join(package.basedir, "usr", "bin", "tool"), 0o4755)

    with caplog.at_level(logging.WARNING):
        package.prepare()

    assert package.contents["/usr/bin/tool"].mode == 0o755
    assert "'/usr/bin/tool' has mode 4755 on disk and gets 0755" in \
        caplog.text


def test_no_warning_for_the_install_folder(package, caplog):
    # make_tree() gives it mode 0700.
    with caplog.at_level(logging.WARNING):
        package.prepare()

    assert package.contents["/"].mode == 0o755
    assert caplog.records == []


def test_tools_package_ignores_modes_below_etc(tmp_path):
    xml = PACKAGE_XML.replace('architecture="aarch64"',
        'architecture="tools"')
    pkg = BinaryPackage(xml, debug_pkgs=False, build_for="tools")
    pkg.basedir = str(make_tree(tmp_path))

    # /etc and /var are not part of a package for the tools folder.
    os.chmod(os.path.join(pkg.basedir, "etc", "tool.conf"), 0o600)

    pkg.prepare()

    assert "/etc/tool.conf" not in pkg.contents
    assert pkg.contents["/usr/bin/tool"].mode == 0o755
