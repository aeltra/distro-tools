# -*- encoding: utf-8 -*-
#
# What a maintainer script knows about the package.

from lxml import etree

from aeltra.package.aeltrapack.binarypackage import BinaryPackage


class Package:

    _script_header = BinaryPackage._script_header

    name           = "a"
    install_prefix = "/tools"
    host_type      = "x86_64-tools-linux-musl"
    target_type    = "aarch64-linux-musl"


def header():
    return Package()._script_header(etree.fromstring("<postinst/>"))


def test_first_line():
    assert header().startswith("#!/bin/sh\n\nset -e\n")


def test_variables():
    lines = header().splitlines()
    assert 'export AELTRA_INSTALL_PREFIX="/tools"' in lines
    assert 'export AELTRA_HOST_TYPE="x86_64-tools-linux-musl"' in lines
    assert 'export AELTRA_TARGET_TYPE="aarch64-linux-musl"' in lines
