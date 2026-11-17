# -*- encoding: utf-8 -*-

import hashlib
import json
import os

import pytest

from aeltra.distro.config.distroinfo import DistroInfo
from aeltra.distro.config.error import DistroInfoError
from aeltra.distro.config.v1 import distroinfo as v1_module
from aeltra.miscellaneous import downloader as downloader_module

LOCAL_URL = "http://127.0.0.1:8080/config/v1"


def folder_for(tmp_path, url):
    tag = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
    return tmp_path / "config" / tag


@pytest.fixture
def fetched(monkeypatch, tmp_path):
    """Records the downloads DistroInfo asks for and answers each with a
    list naming the location it was fetched from."""
    calls = []

    def download_tagged_file(self, url, filename, **kwargs):
        calls.append((url, filename))
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({"fetched-from": {"status": "unstable", "url": url}}, f)

    monkeypatch.setattr(
        downloader_module.Downloader, "download_tagged_file",
        download_tagged_file
    )
    monkeypatch.setattr(
        v1_module.UserInfo, "config_folder", lambda: str(tmp_path)
    )
    monkeypatch.delenv("AELTRA_CONFIG_URL", raising=False)
    return calls


def test_the_archive_is_the_default(fetched, tmp_path):
    DistroInfo().refresh(releases=True, mirrors=True)

    assert fetched == [
        ("https://archive.aeltra.eu/config/v1/releases.json",
         str(tmp_path / "releases.json")),
        ("https://archive.aeltra.eu/config/v1/mirrors.json",
         str(tmp_path / "mirrors.json")),
    ]


def test_another_location_gets_a_folder_of_its_own(
        fetched, monkeypatch, tmp_path):
    monkeypatch.setenv("AELTRA_CONFIG_URL", LOCAL_URL)

    DistroInfo().refresh(releases=True, mirrors=True)

    folder = folder_for(tmp_path, LOCAL_URL)
    assert fetched == [
        (LOCAL_URL + "/releases.json", str(folder / "releases.json")),
        (LOCAL_URL + "/mirrors.json", str(folder / "mirrors.json")),
    ]


def test_the_folder_is_named_after_eight_characters_of_the_hash(
        fetched, monkeypatch, tmp_path):
    monkeypatch.setenv("AELTRA_CONFIG_URL", LOCAL_URL)

    DistroInfo().refresh(releases=True)

    assert [len(name) for name in os.listdir(tmp_path / "config")] == [8]


def test_a_trailing_slash_names_the_same_location(
        fetched, monkeypatch, tmp_path):
    monkeypatch.setenv("AELTRA_CONFIG_URL", LOCAL_URL + "/")

    DistroInfo().refresh(releases=True)

    assert fetched == [(
        LOCAL_URL + "/releases.json",
        str(folder_for(tmp_path, LOCAL_URL) / "releases.json"),
    )]


def test_an_empty_value_means_the_archive(fetched, monkeypatch, tmp_path):
    monkeypatch.setenv("AELTRA_CONFIG_URL", "")

    DistroInfo().refresh(releases=True)

    assert fetched == [(
        "https://archive.aeltra.eu/config/v1/releases.json",
        str(tmp_path / "releases.json"),
    )]


def test_two_locations_do_not_share_a_folder(fetched, monkeypatch, tmp_path):
    other_url = "http://127.0.0.1:8081/config/v1"

    monkeypatch.setenv("AELTRA_CONFIG_URL", LOCAL_URL)
    DistroInfo().refresh(releases=True)
    monkeypatch.setenv("AELTRA_CONFIG_URL", other_url)
    DistroInfo().refresh(releases=True)

    assert folder_for(tmp_path, LOCAL_URL) != folder_for(tmp_path, other_url)
    assert sorted(os.listdir(tmp_path / "config")) == sorted([
        folder_for(tmp_path, LOCAL_URL).name,
        folder_for(tmp_path, other_url).name,
    ])


def test_the_regular_lists_are_left_alone(fetched, monkeypatch, tmp_path):
    (tmp_path / "releases.json").write_text(json.dumps({"regular": {}}))
    monkeypatch.setenv("AELTRA_CONFIG_URL", LOCAL_URL)

    releases = DistroInfo().list(unstable=True)

    assert [r["version_codename"] for r in releases] == ["fetched-from"]
    assert releases[0]["url"] == LOCAL_URL + "/releases.json"
    assert json.loads((tmp_path / "releases.json").read_text()) == \
        {"regular": {}}


def test_the_lists_of_another_location_are_fetched_when_missing(
        fetched, monkeypatch, tmp_path):
    (tmp_path / "releases.json").write_text(json.dumps({"regular": {}}))
    monkeypatch.setenv("AELTRA_CONFIG_URL", LOCAL_URL)

    DistroInfo().list(unstable=True)

    assert [url for url, _ in fetched] == [LOCAL_URL + "/releases.json"]


@pytest.mark.parametrize("spelling", [
    "HTTP://127.0.0.1:8080/config/v1",
    "http://127.0.0.1:8080//config/v1//",
    "  http://127.0.0.1:8080/config/v1\n",
])
def test_spellings_of_one_location_share_a_folder(
        fetched, monkeypatch, tmp_path, spelling):
    monkeypatch.setenv("AELTRA_CONFIG_URL", spelling)

    DistroInfo().refresh(releases=True)

    assert fetched == [(
        LOCAL_URL + "/releases.json",
        str(folder_for(tmp_path, LOCAL_URL) / "releases.json"),
    )]


@pytest.mark.parametrize("spelling", [
    "https://archive.aeltra.eu/config/v1/",
    "https://archive.aeltra.eu:443/config/v1",
    "HTTPS://Archive.Aeltra.EU/config/v1",
])
def test_spellings_of_the_archive_use_the_regular_folder(
        fetched, monkeypatch, tmp_path, spelling):
    monkeypatch.setenv("AELTRA_CONFIG_URL", spelling)

    DistroInfo().refresh(releases=True)

    assert fetched == [(
        "https://archive.aeltra.eu/config/v1/releases.json",
        str(tmp_path / "releases.json"),
    )]


def test_the_scheme_and_port_tell_locations_apart(
        fetched, monkeypatch, tmp_path):
    monkeypatch.setenv("AELTRA_CONFIG_URL", "http://archive.aeltra.eu/config/v1")

    DistroInfo().refresh(releases=True)

    assert fetched[0][1] != str(tmp_path / "releases.json")


@pytest.mark.parametrize("value", [
    "/srv/archive/config/v1",
    "file:///srv/archive/config/v1",
    "127.0.0.1:8080/config/v1",
    "http:///config/v1",
    "http://127.0.0.1:port/config/v1",
    "http://127.0.0.1:8080/config/v1?x=1",
])
def test_an_unusable_value_is_refused(fetched, monkeypatch, value):
    monkeypatch.setenv("AELTRA_CONFIG_URL", value)

    with pytest.raises(DistroInfoError, match="AELTRA_CONFIG_URL"):
        DistroInfo().refresh(releases=True)

    assert fetched == []


def test_the_default_location_is_normalized(fetched, monkeypatch, tmp_path):
    monkeypatch.setattr(
        v1_module.DistroInfo, "base_url",
        "HTTPS://Archive.Aeltra.EU:443/config/v1/"
    )
    monkeypatch.setenv(
        "AELTRA_CONFIG_URL", "https://archive.aeltra.eu/config/v1"
    )

    DistroInfo().refresh(releases=True)

    assert fetched == [(
        "https://archive.aeltra.eu/config/v1/releases.json",
        str(tmp_path / "releases.json"),
    )]
