# -*- encoding: utf-8 -*-

import urllib.request

import pytest

from aeltra.miscellaneous.downloader import Downloader


class Response:

    def __init__(self, headers):
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def getheader(self, name, default=None):
        return self.headers.get(name, default)


@pytest.fixture
def served(monkeypatch):
    """Answers every request with the headers set for its URL."""
    headers = {}

    def urlopen(request, timeout=None):
        return Response(headers[request.full_url])

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return headers


def test_a_tag_is_stable(served):
    served["http://host/releases.json"] = {"Last-Modified": "Tue"}

    downloader = Downloader()
    assert downloader.tag("http://host/releases.json") \
        == downloader.tag("http://host/releases.json")


def test_a_changed_file_gets_another_tag(served):
    downloader = Downloader()

    served["http://host/releases.json"] = {"Last-Modified": "Tue"}
    old_tag = downloader.tag("http://host/releases.json")
    served["http://host/releases.json"] = {"Last-Modified": "Wed"}

    assert downloader.tag("http://host/releases.json") != old_tag


def test_two_files_with_the_same_headers_get_different_tags(served):
    served["http://host/releases.json"] = {"Last-Modified": "Tue"}
    served["http://host/mirrors.json"] = {"Last-Modified": "Tue"}

    downloader = Downloader()
    assert downloader.tag("http://host/releases.json") \
        != downloader.tag("http://host/mirrors.json")
