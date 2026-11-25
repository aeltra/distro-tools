# -*- encoding: utf-8 -*-
#
# The folder of a build must not end up in what is built.

import os

import pytest

from aeltra.miscellaneous.platform import Platform


@pytest.fixture(autouse=True)
def not_debian(monkeypatch):
    exists = os.path.exists
    monkeypatch.setattr(
        os.path, "exists",
        lambda p: False if p == "/etc/debian_version" else exists(p)
    )


@pytest.mark.parametrize("env, expected", [
    # Sources and build folder are below the work folder.
    ({"AELTRA_WORK_DIR": "/w", "AELTRA_BUILD_DIR": "/w/build"}, "/w"),
    ({"AELTRA_BUILD_DIR": "/w/build"}, "/w/build"),
])
def test_file_prefix_map(env, expected):
    env = dict(env, AELTRA_HOST_TYPE="aarch64-linux-musl")
    flags = Platform.build_flags(env)

    for name in ["CFLAGS", "CXXFLAGS", "FCFLAGS", "FFLAGS", "OBJCFLAGS",
                 "OBJCXXFLAGS"]:
        assert "-ffile-prefix-map=%s=." % expected in flags[name].split()


def test_without_folders():
    flags = Platform.build_flags({"AELTRA_HOST_TYPE": "aarch64-linux-musl"})
    assert "prefix-map" not in flags["CFLAGS"]
