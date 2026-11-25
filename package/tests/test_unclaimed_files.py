# -*- encoding: utf-8 -*-
#
# What was installed but is in no package is reported.

import pytest

from aeltra.package.aeltrapack.packagecontrol import PackageControl


class Package:

    def __init__(self, basedir, *contents):
        self.basedir  = str(basedir)
        self.contents = dict.fromkeys(contents)


class Control:
    """What unclaimed_files() uses of a PackageControl object."""

    UNCLAIMED_IGNORE = PackageControl.UNCLAIMED_IGNORE
    UNCLAIMED_MANY   = PackageControl.UNCLAIMED_MANY

    def __init__(self, install_dir, *bin_pkgs, prefix="/usr"):
        self.bin_pkgs = bin_pkgs
        self.defines  = {
            "AELTRA_INSTALL_DIR": str(install_dir),
            "AELTRA_INSTALL_PREFIX": prefix,
        }


def unclaimed(*args, **kwargs):
    return PackageControl.unclaimed_files(Control(*args, **kwargs))


@pytest.fixture
def install(tmp_path):
    def make(*files):
        for f in files:
            path = tmp_path / f.lstrip("/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
        return tmp_path
    return make


def test_everything_is_claimed(install):
    root = install("/usr/bin/a", "/usr/lib/b")
    assert unclaimed(root, Package(root, "/usr", "/usr/bin/a"),
                     Package(root, "/usr/lib/b")) == []


def test_file_is_reported(install):
    root = install("/usr/lib/liba.so", "/usr/lib/pkgconfig/a.pc",
                   "/usr/lib/pkgconfig/b.pc")
    assert unclaimed(root, Package(root, "/usr/lib/liba.so",
                                   "/usr/lib/pkgconfig/a.pc")) == \
        ["/usr/lib/pkgconfig/b.pc"]


def test_folder_is_reported_in_place_of_many_files(install):
    many = ["/usr/lib/x/y/%d" % i for i in range(Control.UNCLAIMED_MANY + 1)]
    root = install("/usr/bin/a", "/usr/lib/b", *many)
    assert unclaimed(root, Package(root, "/usr/bin/a")) == \
        ["/usr/lib/b", "/usr/lib/x/y/"]


def test_few_files_are_reported_one_by_one(install):
    few  = ["/usr/lib/x/%d" % i for i in range(Control.UNCLAIMED_MANY)]
    root = install("/usr/bin/a", *few)
    assert unclaimed(root, Package(root, "/usr/bin/a")) == few


def test_folder_with_packaged_files_is_not_reported(install):
    many = ["/usr/lib/x/%d" % i for i in range(Control.UNCLAIMED_MANY + 1)]
    root = install("/usr/lib/x/a", *many)
    assert unclaimed(root, Package(root, "/usr/lib/x/a")) == many


def test_symbolic_link_is_reported(install):
    root = install("/usr/lib/liba.so.1")
    (root / "usr/lib/liba.so").symlink_to("liba.so.1")
    (root / "usr/lib/d").symlink_to(".")
    assert unclaimed(root, Package(root, "/usr/lib/liba.so.1")) == \
        ["/usr/lib/d", "/usr/lib/liba.so"]


def test_empty_folder_is_not_reported(install):
    root = install("/usr/bin/a")
    (root / "usr/lib/empty").mkdir(parents=True)
    assert unclaimed(root, Package(root, "/usr/bin/a")) == []


def test_folders_of_packages(install):
    root = install("/a/usr/bin/a", "/b/usr/bin/a", "/rest/usr/bin/b")
    assert unclaimed(root, Package(root / "a", "/usr/bin/a"),
                     Package(root / "b", "/usr/bin/a")) == \
        ["/rest/usr/bin/b"]


def test_copies_in_the_folders_of_packages(install):
    root = install("/usr/bin/a", "/usr/lib/b", "/usr/lib/pkgconfig/b.pc",
                   "/usr/lib/c", "/a/usr/bin/a", "/sub/b/usr/lib/b")
    assert unclaimed(root, Package(root / "a", "/usr/bin/a"),
                     Package(root / "sub/b", "/usr/lib/b")) == \
        ["/usr/lib/c", "/usr/lib/pkgconfig/b.pc"]


def test_same_name_in_another_folder_is_reported(install):
    root = install("/usr/bin/a", "/usr/lib/a")
    assert unclaimed(root, Package(root, "/usr/bin/a")) == ["/usr/lib/a"]


@pytest.mark.parametrize("path", [
    "/usr/share/doc/a/README",
    "/usr/share/info/a.info",
    "/usr/share/man/man1/a.1",
    "/usr/share/gtk-doc/html/a.html",
    "/usr/lib/liba.la",
    "/usr/lib/python3/dist-packages/__pycache__/a.cpython-314.pyc",
    "/usr/lib/perl5/perllocal.pod",
    "/usr/lib/perl5/auto/A/.packlist",
    # made while packaging
    "/usr/lib/debug/.build-id/00/11.debug",
])
def test_not_expected_in_a_package(install, path):
    for prefix in ("", "/all"):
        root = install("/usr/bin/a", prefix + path)
    assert unclaimed(root, Package(root, "/usr/bin/a")) == []


@pytest.mark.parametrize("prefix, expected", [
    ("/usr", ["/etc/a.conf", "/var/lib/a/b"]),
    # shared with the target
    ("/tools", []),
])
def test_etc_and_var(install, prefix, expected):
    root = install(prefix + "/bin/a", "/etc/a.conf", "/var/lib/a/b")
    assert unclaimed(root, Package(root, prefix + "/bin/a"),
                     prefix=prefix) == expected
