# -*- encoding: utf-8 -*-
#
# Symbolic links that lead to nothing in any package are reported.

import pytest

from aeltra.package.aeltrapack.packagecontrol import PackageControl

WORK = "/home/user/build"


class Stats:

    def __init__(self, target):
        self.is_symbolic_link = target is not None
        self.link_target      = target or ""


class Attributes:

    def __init__(self, target):
        self.stats = Stats(target)


class Package:

    def __init__(self, **contents):
        self.contents = {}

    @classmethod
    def make(cls, *files, **links):
        pkg = cls()
        for f in files:
            pkg.contents[f] = Attributes(None)
        for src, target in links.get("links", {}).items():
            pkg.contents[src] = Attributes(target)
        return pkg


class Control:
    """What dangling_links() uses of a PackageControl object."""

    def __init__(self, *bin_pkgs, prefix="/usr"):
        self.bin_pkgs = bin_pkgs
        self.defines  = {
            "AELTRA_INSTALL_PREFIX": prefix,
            "AELTRA_WORK_DIR": WORK,
        }


def dangling(*args, **kwargs):
    return PackageControl.dangling_links(Control(*args, **kwargs))


def test_target_in_the_same_package():
    pkg = Package.make("/usr/share/a", links={"/usr/share/b": "a",
                                              "/usr/bin/c": "../share/a"})
    assert dangling(pkg) == []


def test_target_in_another_package_of_the_build():
    assert dangling(
        Package.make("/usr/lib/liba.so.1.0"),
        Package.make(links={"/usr/lib/liba.so.1": "liba.so.1.0"}),
    ) == []


def test_target_is_a_folder_or_a_link():
    assert dangling(
        Package.make("/usr/share/a", links={"/usr/share/b": "a",
                                            "/usr/share/c": "b"}),
    ) == []


def test_dangling_link_is_reported():
    pkg = Package.make("/usr/share/terminfo/c/cygwin",
                       links={"/usr/share/terminfo/a/ansi": "../c/cons25"})
    assert dangling(pkg) == [("/usr/share/terminfo/a/ansi", "../c/cons25")]


@pytest.mark.parametrize("src, target, prefix", [
    # out of the prefix
    ("/var/lock", "../run/lock", "/usr"),
    ("/tools/etc", "../etc", "/tools"),
    # to a file of another package
    ("/tools/lib/ssl/certs", "/etc/ssl/certs", "/tools"),
    ("/usr/lib/ssl/certs", "/etc/ssl/certs", "/usr"),
    # checked while looking for dependencies
    ("/usr/lib/liba.so", "liba.so.1", "/usr"),
])
def test_not_reported(src, target, prefix):
    assert dangling(Package.make(links={src: target}), prefix=prefix) == []


def test_link_into_the_build_is_reported():
    target = WORK + "/install/usr/bin/a"
    assert dangling(Package.make("/usr/bin/a", links={"/usr/bin/b": target}))\
        == [("/usr/bin/b", target)]
