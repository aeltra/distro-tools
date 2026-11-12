# -*- encoding: utf-8 -*-

import base64
import logging
import os

import pytest

from aeltra.miscellaneous.authfile import AuthFile
from aeltra.miscellaneous.downloader import Downloader


SECRET = "aeltra_api_s3cr#t"


def parse(text):
    return AuthFile.parse(text.splitlines(keepends=True))


def test_an_entry_on_one_line():
    auth = parse(
        "machine archive.aeltra.eu login token password {}\n".format(SECRET)
    )
    assert auth.find("https://archive.aeltra.eu/dists/x") \
        == ("token", SECRET)


def test_an_entry_across_lines_with_comments():
    auth = parse(
        "# Aeltra\n"
        "machine archive.aeltra.eu  # the public archive\n"
        "  login token\n"
        "  password {}\n".format(SECRET)
    )
    assert auth.find("https://archive.aeltra.eu/") == ("token", SECRET)


def test_a_value_may_start_with_a_hash():
    auth = parse(
        "machine archive.aeltra.eu login token password #s3cret # comment\n"
    )
    assert auth.find("https://archive.aeltra.eu/") == ("token", "#s3cret")


def test_only_https_urls_match():
    auth = parse("machine archive.aeltra.eu login a password b")
    assert auth.find("http://archive.aeltra.eu/dists") is None
    assert auth.find("ftp://archive.aeltra.eu/dists") is None


def test_host_matching_ignores_case_and_the_default_port():
    auth = parse("machine https://Archive.Aeltra.EU:443 login a password b")
    assert auth.find("HTTPS://archive.aeltra.eu/x") == ("a", "b")
    assert auth.find("https://archive.aeltra.eu:443/x") == ("a", "b")
    assert auth.find("https://archive.aeltra.eu:8443/x") is None


def test_the_host_must_match_exactly():
    auth = parse("machine aeltra.eu login a password b")
    assert auth.find("https://archive.aeltra.eu/") is None
    assert auth.find("https://aeltra.eu.example/") is None


def test_a_path_prefix_ends_at_a_segment_boundary():
    auth = parse("machine archive.aeltra.eu/dists/ login a password b")
    assert auth.find("https://archive.aeltra.eu/dists") == ("a", "b")
    assert auth.find("https://archive.aeltra.eu/dists/x") == ("a", "b")
    assert auth.find("https://archive.aeltra.eu/dists?x") == ("a", "b")
    assert auth.find("https://archive.aeltra.eu/distsx") is None
    assert auth.find("https://archive.aeltra.eu/config/") is None


def test_the_first_matching_entry_wins():
    auth = parse(
        "machine archive.aeltra.eu/dists login first password 1\n"
        "machine archive.aeltra.eu login second password 2\n"
    )
    assert auth.find("https://archive.aeltra.eu/dists/x") == ("first", "1")
    assert auth.find("https://archive.aeltra.eu/pool/x") == ("second", "2")


def test_a_url_with_credentials_of_its_own_gets_none():
    auth = parse("machine archive.aeltra.eu login a password b")
    assert auth.find("https://u:p@archive.aeltra.eu/") is None


def test_other_schemes_and_incomplete_entries_are_skipped(caplog):
    caplog.set_level(logging.WARNING)
    auth = parse(
        "machine http://archive.aeltra.eu login a password {}\n"
        "machine archive.aeltra.eu login a\n"
        "bogus\n"
        "machine archive.aeltra.eu password\n".format(SECRET)
    )
    assert auth.find("https://archive.aeltra.eu/") is None
    assert len(caplog.records) == 5
    assert SECRET not in caplog.text


def test_entries_do_not_show_their_secrets():
    auth = parse(
        "machine archive.aeltra.eu login a password {}".format(SECRET)
    )
    assert SECRET not in repr(auth._entries)


def test_load_warns_about_a_world_readable_file(tmp_path, caplog):
    path = tmp_path / "auth.conf"
    path.write_text("machine archive.aeltra.eu login a password b\n")

    os.chmod(path, 0o640)
    caplog.set_level(logging.WARNING)
    assert AuthFile.load(str(path)).find("https://archive.aeltra.eu/") \
        == ("a", "b")
    assert not caplog.records

    os.chmod(path, 0o644)
    AuthFile.load(str(path))
    assert "accessible by other users" in caplog.text


def test_load_of_a_missing_file_fails(tmp_path):
    with pytest.raises(AuthFile.Error):
        AuthFile.load(str(tmp_path / "missing.conf"))


def test_the_downloader_sends_basic_auth_only_where_it_matches():
    auth = parse("machine archive.aeltra.eu login token password {}"
        .format(SECRET))
    downloader = Downloader(auth_file=auth)

    request  = downloader._request("https://archive.aeltra.eu/dists/x")
    expected = "Basic " + base64.b64encode(
        "token:{}".format(SECRET).encode("utf-8")
    ).decode("ascii")

    # Not among the headers urllib copies to the target of a redirect.
    assert request.unredirected_hdrs["Authorization"] == expected
    assert "Authorization" not in request.headers

    request = downloader._request("https://deb.debian.org/debian/x")
    assert not request.has_header("Authorization")

    request = Downloader()._request("https://archive.aeltra.eu/dists/x")
    assert not request.has_header("Authorization")


def test_the_downloader_authenticates_the_head_request_too():
    auth = parse("machine archive.aeltra.eu login a password b")
    request = Downloader(auth_file=auth)._request(
        "https://archive.aeltra.eu/x", method="HEAD"
    )
    assert request.get_method() == "HEAD"
    assert request.has_header("Authorization")
