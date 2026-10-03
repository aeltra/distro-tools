# -*- encoding: utf-8 -*-

import json

import pytest

from aeltra.distro.config.distroinfo import DistroInfo, Source
from aeltra.osimage import generator as generator_module
from aeltra.osimage.generator import ImageGenerator
from aeltra.osimage.specfile import PackageBatch

# What the fake release offers: core with every pocket, extended without
# cross-tools.
POCKETS_OF = {
    "core": ["main", "tools", "cross-tools"],
    "extended": ["main", "tools"],
    "raspi": ["main"],
}


@pytest.fixture
def calls(monkeypatch):
    """Fake the release data and record the commands run."""
    recorded = {"sources": [], "run": []}

    def sources(self, **kwargs):
        recorded["sources"].append(kwargs)
        return [
            Source("{}-{}".format(r, p), r, p, "https://m/{}/{}".format(r, p))
            for r in kwargs["repositories"]
            for p in DistroInfo.POCKETS
            if p in kwargs["pockets"] and p in POCKETS_OF[r]
        ]

    def run(sysroot, prog, cmd, **kwargs):
        recorded["run"].append(cmd)

    monkeypatch.setattr(DistroInfo, "repository_sources", sources)
    monkeypatch.setattr(generator_module.Subprocess, "run", staticmethod(run))
    monkeypatch.setattr(PackageBatch, "apply", lambda self, *a, **kw: None)
    return recorded


@pytest.fixture
def sysroot(tmp_path):
    root = tmp_path / "sysroot"
    (root / "etc" / "aept").mkdir(parents=True)
    return root


@pytest.fixture
def generator():
    return ImageGenerator(release="ollie", arch="aarch64")


def conf(sysroot):
    return (sysroot / "etc" / "aept" / "aept.conf").read_text()


def source_names(sysroot):
    return [
        line.split()[1] for line in conf(sysroot).splitlines()
        if line.startswith("src/gz ")
    ]


def ledger(sysroot):
    path = sysroot / "var" / "lib" / "image-gen" / "sources"
    return [json.loads(line) for line in path.read_text().splitlines()]


def apply_spec(generator, sysroot, tmp_path, name, text):
    spec = tmp_path / name
    spec.write_text(text)
    generator.customize(str(sysroot), str(spec))
    return str(spec)


# ── each spec gets its own sources ───────────────────────────────────

def test_a_spec_without_a_preamble_gets_core_and_main(
        calls, generator, sysroot, tmp_path):
    apply_spec(generator, sysroot, tmp_path, "a.spec", "+base-files\n")

    assert source_names(sysroot) == ["core-main"]
    assert "arch tools" not in conf(sysroot)


def test_the_preamble_adds_repositories_and_pockets(
        calls, generator, sysroot, tmp_path):
    apply_spec(
        generator, sysroot, tmp_path, "a.spec",
        "@repositories extended\n@pockets tools cross-tools\n+gcc\n"
    )

    assert source_names(sysroot) == [
        "core-main", "core-tools", "core-cross-tools",
        "extended-main", "extended-tools",
    ]
    assert "arch tools" in conf(sysroot)


def test_the_lists_are_updated_on_the_host_when_the_sources_change(
        calls, generator, sysroot, tmp_path):
    apply_spec(generator, sysroot, tmp_path, "a.spec", "+a\n")
    apply_spec(generator, sysroot, tmp_path, "b.spec", "+b\n")
    apply_spec(
        generator, sysroot, tmp_path, "c.spec", "@pockets tools\n+c\n"
    )

    update = ["aept", "-o", str(sysroot), "update"]
    assert calls["run"] == [update, update]


def test_a_spec_does_not_inherit_what_an_earlier_one_used(
        calls, generator, sysroot, tmp_path):
    apply_spec(
        generator, sysroot, tmp_path, "a.spec",
        "@repositories extended\n@pockets tools\n+a\n"
    )
    apply_spec(generator, sysroot, tmp_path, "b.spec", "+b\n")

    assert source_names(sysroot) == ["core-main"]


def test_each_spec_run_is_recorded_with_its_sources_only(
        calls, generator, sysroot, tmp_path):
    apply_spec(
        generator, sysroot, tmp_path, "a.spec", "@pockets tools\n+a\n"
    )
    apply_spec(generator, sysroot, tmp_path, "b.spec", "+b\n")

    entries = ledger(sysroot)
    assert entries == [
        {"sources": [
            {"name": "core-main", "repository": "core", "pocket": "main",
             "url": "https://m/core/main"},
            {"name": "core-tools", "repository": "core", "pocket": "tools",
             "url": "https://m/core/tools"},
        ]},
        {"sources": [
            {"name": "core-main", "repository": "core", "pocket": "main",
             "url": "https://m/core/main"},
        ]},
    ]


def test_a_spec_is_recorded_before_its_parts_run(
        calls, generator, sysroot, tmp_path, monkeypatch):
    def fail(self, *args, **kwargs):
        raise RuntimeError("install failed")

    monkeypatch.setattr(PackageBatch, "apply", fail)

    # What a failing spec installed before it failed must stay updatable.
    with pytest.raises(RuntimeError, match="install failed"):
        apply_spec(
            generator, sysroot, tmp_path, "a.spec", "@pockets tools\n+a\n"
        )

    assert [s["name"] for s in ledger(sysroot)[0]["sources"]] \
        == ["core-main", "core-tools"]


def test_prepare_starts_with_the_defaults(calls, generator, tmp_path):
    root = tmp_path / "fresh"
    root.mkdir()

    generator.prepare(str(root))

    assert source_names(root) == ["core-main"]
    assert calls["run"] == [["aept", "-o", str(root), "update"]]
    # Only specs are recorded; every one of them uses core-main anyway.
    assert not (root / "var" / "lib" / "image-gen" / "sources").exists()


# ── the finished image gets the union ────────────────────────────────

def test_the_finished_image_gets_every_source_used(
        calls, generator, sysroot, tmp_path):
    apply_spec(
        generator, sysroot, tmp_path, "a.spec",
        "@pockets tools cross-tools\n+a\n"
    )
    apply_spec(
        generator, sysroot, tmp_path, "b.spec",
        "@repositories extended\n+b\n"
    )

    generator.finalize_aept_config(str(sysroot))

    # The pairs actually used: extended was used without tools.
    assert source_names(sysroot) == [
        "core-main", "core-tools", "core-cross-tools", "extended-main",
    ]
    assert "arch tools" in conf(sysroot)


def test_the_union_needs_no_release_data(calls, generator, sysroot, tmp_path):
    apply_spec(
        generator, sysroot, tmp_path, "a.spec", "@pockets tools\n+a\n"
    )
    asked = len(calls["sources"])

    generator.finalize_aept_config(str(sysroot))

    assert len(calls["sources"]) == asked
    assert "src/gz core-tools https://m/core/tools" in conf(sysroot)


def test_more_repositories_get_the_pockets_the_image_uses(
        calls, generator, sysroot, tmp_path):
    apply_spec(
        generator, sysroot, tmp_path, "a.spec",
        "@pockets tools cross-tools\n+a\n"
    )

    generator.finalize_aept_config(
        str(sysroot), repositories=["extended", "raspi", "core"]
    )

    # extended has no cross-tools and raspi only main: they are skipped.
    assert source_names(sysroot) == [
        "core-main", "core-tools", "core-cross-tools",
        "extended-main", "extended-tools", "raspi-main",
    ]


def test_more_repositories_get_only_main_in_a_main_only_image(
        calls, generator, sysroot, tmp_path):
    apply_spec(generator, sysroot, tmp_path, "a.spec", "+a\n")

    generator.finalize_aept_config(str(sysroot), repositories=["extended"])

    assert source_names(sysroot) == ["core-main", "extended-main"]


def test_without_a_ledger_the_image_gets_the_defaults(
        calls, generator, sysroot):
    generator.finalize_aept_config(str(sysroot))

    assert source_names(sysroot) == ["core-main"]


def test_a_malformed_ledger_is_an_error(calls, generator, sysroot):
    path = sysroot / "var" / "lib" / "image-gen" / "sources"
    path.parent.mkdir(parents=True)
    path.write_text("not json\n")

    with pytest.raises(ImageGenerator.Error, match="malformed entry"):
        generator.finalize_aept_config(str(sysroot))


def test_cleanup_writes_the_union_with_more_repositories(
        calls, generator, sysroot, tmp_path):
    apply_spec(
        generator, sysroot, tmp_path, "a.spec", "@pockets tools\n+a\n"
    )
    for d in ("tmp", "var/tmp"):
        (sysroot / d).mkdir(parents=True, exist_ok=True)

    # A new process, as "aeltra-image cleanup" is: the ledger is all it has.
    ImageGenerator(release="ollie", arch="aarch64").cleanup(
        str(sysroot), repositories=["extended"]
    )

    assert source_names(sysroot) == [
        "core-main", "core-tools", "extended-main", "extended-tools",
    ]
