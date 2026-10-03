# -*- encoding: utf-8 -*-

import io

import pytest

from aeltra.osimage.specfile import PackageBatch, Script, SpecfileParser


def load(text):
    repositories, pockets, parts = SpecfileParser.load(io.StringIO(text))
    return repositories, pockets, [p for _, _, p in parts]


def test_the_preamble_comes_apart_from_the_parts():
    repositories, pockets, parts = load(
        "= header\n"
        "@repositories extended\n"
        "@pockets tools cross-tools\n"
        "\n"
        "+base-files\n"
    )

    assert repositories == ["extended"]
    assert pockets == ["tools", "cross-tools"]
    assert len(parts) == 1
    assert isinstance(parts[0], PackageBatch)


def test_several_lines_are_merged_and_defaults_are_allowed():
    repositories, pockets, parts = load(
        "@repositories core extended\n"
        "@repositories extended raspi\n"
        "@pockets main tools\n"
        "@pockets tools\n"
        "#!/bin/sh\n"
        "true\n"
    )

    assert repositories == ["core", "extended", "raspi"]
    assert pockets == ["main", "tools"]
    assert isinstance(parts[0], Script)


def test_a_spec_without_a_preamble_asks_for_nothing_more():
    repositories, pockets, parts = load("+base-files\n")

    assert (repositories, pockets) == ([], [])
    assert len(parts) == 1


def test_repository_names_are_checked_when_the_spec_is_applied():
    # They depend on the release, which the parser does not know.
    repositories, _, _ = load("@repositories whatever\n")

    assert repositories == ["whatever"]


@pytest.mark.parametrize("text, message", [
    ("+foo\n@pockets tools\n", "line 2: \"@\" directives must come before"),
    ("+foo\n=\n@repositories x\n", "line 3: \"@\" directives must come"),
    ("#!/bin/sh\ntrue\n=\n@pockets tools\n", "line 4: \"@\" directives"),
    ("@pocket tools\n", "unknown directive \"@pocket\""),
    ("@pockets tool\n", "unknown pocket \"tool\""),
    ("@pockets\n", "@pockets needs at least one name"),
    ("@repositories\n", "@repositories needs at least one name"),
])
def test_bad_directives_are_syntax_errors(text, message):
    with pytest.raises(SpecfileParser.SyntaxError, match=message):
        load(text)
