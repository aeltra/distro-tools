# -*- encoding: utf-8 -*-

import json

import pytest

from aeltra.distro.config import distroinfo as wrapper_module
from aeltra.distro.config.distroinfo import DistroInfo
from aeltra.distro.config.error import DistroInfoError
from aeltra.distro.config.v1 import distroinfo as v1_module


@pytest.fixture
def info(monkeypatch, tmp_path):
    """A DistroInfo reading releases.json and mirrors.json from tmp."""
    releases = {
        "ollie": {
            "repositories": {
                "core": {"mirrors": ["primary"]},
                "overlay": {"mirrors": ["other"], "pockets": ["main"]},
            }
        }
    }
    mirrors = {
        "primary": {"master": ["https://primary.example/dists"]},
        "other": {"master": ["https://other.example/dists"]},
    }
    (tmp_path / "releases.json").write_text(json.dumps(releases))
    (tmp_path / "mirrors.json").write_text(json.dumps(mirrors))

    monkeypatch.setattr(
        v1_module.UserInfo, "config_folder", lambda: str(tmp_path)
    )
    return DistroInfo()


def full_sources(info, repositories, pockets):
    return info.repository_sources(
        release="ollie", repositories=repositories, arch="aarch64",
        libc="musl", host_arch="x86_64", pockets=pockets
    )


def sources(info, repositories, pockets):
    return [(s.name, s.url) for s in full_sources(info, repositories, pockets)]


def test_the_pockets_are_shared_with_the_wrapper():
    assert wrapper_module.DistroInfo.POCKETS \
        == ["main", "tools", "cross-tools"]


def test_repository_names(info):
    assert info.repository_names(release="ollie") == ["core", "overlay"]


def test_a_repository_has_every_pocket_by_convention(info):
    assert info.repository_pockets(release="ollie", repository="core") \
        == ["main", "tools", "cross-tools"]


def test_a_repository_may_list_its_own_pockets(info):
    assert info.repository_pockets(release="ollie", repository="overlay") \
        == ["main"]


def test_sources_follow_the_archive_layout(info):
    assert sources(info, ["core"], ["main", "tools", "cross-tools"]) == [
        ("core-main",
         "https://primary.example/dists/ollie/core/aarch64/musl/main"),
        ("core-tools",
         "https://primary.example/dists/ollie/core/aarch64/musl/tools/x86_64"),
        ("core-cross-tools",
         "https://primary.example/dists/ollie/core/aarch64/musl/"
         "cross-tools/x86_64"),
    ]


def test_a_source_names_its_repository_and_pocket(info):
    source, = full_sources(info, ["overlay"], ["main"])

    assert (source.name, source.repository, source.pocket) \
        == ("overlay-main", "overlay", "main")


def test_each_repository_uses_its_own_mirror(info):
    assert sources(info, ["core", "overlay"], ["main"]) == [
        ("core-main",
         "https://primary.example/dists/ollie/core/aarch64/musl/main"),
        ("overlay-main",
         "https://other.example/dists/ollie/overlay/aarch64/musl/main"),
    ]


def test_a_repository_without_a_pocket_is_skipped_for_it(info):
    found = sources(info, ["core", "overlay"], ["main", "tools"])
    names = [n for n, _ in found]
    assert names == ["core-main", "core-tools", "overlay-main"]


def test_a_pocket_no_repository_has_is_skipped_too(info):
    found = sources(info, ["overlay"], ["main", "tools", "cross-tools"])
    assert [n for n, _ in found] == ["overlay-main"]


def test_an_unknown_pocket_is_an_error(info):
    with pytest.raises(DistroInfoError, match="unknown pocket 'tool'"):
        sources(info, ["core"], ["main", "tool"])


def test_an_unknown_repository_names_the_known_ones(info):
    with pytest.raises(
            DistroInfoError,
            match="has no repository 'nope', it has: core, overlay"):
        sources(info, ["core", "nope"], ["main"])


def test_the_command_line_lists_the_repositories(info, capsys):
    from aeltra.distro.config.cli import Cli

    Cli({"api_version": 1}).repositories("ollie")

    assert capsys.readouterr().out == "core\noverlay\n"
