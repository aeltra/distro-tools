# -*- encoding: utf-8 -*-

import contextlib

import pytest

from aeltra.distro.config.distroinfo import DistroInfo
from aeltra.osimage import cli as cli_module
from aeltra.osimage.cli import ImageGenCli


@pytest.fixture
def release(monkeypatch):
    """A release "ollie" with the repositories core and extended."""
    monkeypatch.setattr(DistroInfo, "latest_release", lambda self: "ollie")
    monkeypatch.setattr(
        DistroInfo, "release_exists", lambda self, name: name == "ollie"
    )
    monkeypatch.setattr(
        DistroInfo, "is_supported_libc", lambda self, release, libc: True
    )
    monkeypatch.setattr(
        DistroInfo, "is_supported_arch",
        lambda self, release, arch, libc="musl": True
    )
    monkeypatch.setattr(
        DistroInfo, "repository_names",
        lambda self, *, release: ["core", "extended"]
    )


@pytest.fixture
def generator(monkeypatch):
    """Replace the generator, recording what the commands asked of it."""
    record = []

    class Generator:
        def __init__(self, **kwargs):
            record.append(("init", kwargs))

        def prepare(self, sysroot):
            record.append(("prepare",))

        def customize(self, sysroot, specfile):
            record.append(("customize", specfile))

        def cleanup(self, sysroot, repositories=None):
            record.append(("cleanup", repositories))

    monkeypatch.setattr(cli_module, "ImageGenerator", Generator)
    monkeypatch.setattr(
        cli_module, "Sysroot", lambda sysroot: contextlib.nullcontext()
    )
    monkeypatch.setattr(
        cli_module.ImageGeneratorUtils, "collect_specfiles",
        staticmethod(lambda release, libc, arch, *specs: list(specs))
    )
    for what in ("release", "libc", "arch"):
        monkeypatch.setattr(
            cli_module.ImageGeneratorUtils, "determine_target_" + what,
            staticmethod(
                lambda sysroot, what=what:
                    {"release": "ollie", "libc": "musl",
                     "arch": "aarch64"}[what]
            )
        )
    monkeypatch.setattr(cli_module.os, "geteuid", lambda: 0)
    return record


def run(*args):
    ImageGenCli().execute_command(*args)


def test_bootstrap_takes_the_sources_from_the_specs(
        release, generator, tmp_path):
    run("bootstrap", "-a", "aarch64", str(tmp_path), "a.spec")

    init = generator[0][1]
    assert "repositories" not in init
    assert generator[1:] == [("prepare",), ("customize", "a.spec")]


@pytest.mark.parametrize("option", [
    ["--repo", "extended"], ["--repo-base", "https://mine/dists"],
])
def test_bootstrap_takes_no_repository_option(
        release, generator, tmp_path, option):
    with pytest.raises(ImageGenCli.Error, match="error parsing command line"):
        run("bootstrap", "-a", "aarch64", *option, str(tmp_path), "a.spec")

    assert generator == []


def test_cleanup_gives_the_image_more_repositories(
        release, generator, tmp_path):
    run("cleanup", "--repo", "extended", str(tmp_path))

    assert generator[-1] == ("cleanup", ["extended"])


def test_cleanup_without_repo_needs_no_release_data(
        release, generator, tmp_path, monkeypatch):
    def offline(self, *, release):
        raise AssertionError("cleanup looked up the release data")

    monkeypatch.setattr(DistroInfo, "repository_names", offline)

    run("cleanup", str(tmp_path))

    assert generator[-1] == ("cleanup", [])


def test_cleanup_refuses_a_repository_the_release_lacks(
        release, generator, tmp_path):
    with pytest.raises(
            ImageGenCli.Error,
            match='has no repository "nope", it has: core, extended'):
        run("cleanup", "--repo", "nope", str(tmp_path))

    assert generator == []
