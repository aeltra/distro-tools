# -*- encoding: utf-8 -*-
#
# bh_python_install calls the build backend of a project directly.

import os
import subprocess
import sys

import pytest

import aeltra.package.aeltrapack as aeltrapack

HELPER = os.path.join(
    os.path.dirname(os.path.abspath(aeltrapack.__file__)),
    "helpers", "python.sh"
)

BACKEND = """\
import os

def build_wheel(wheel_directory):
    open(os.path.join(wheel_directory, "{}.whl"), "w").close()
"""


@pytest.fixture
def build(tmp_path):
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin" / "python3").symlink_to(sys.executable)

    # What is installed, as far as the project is concerned.
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / "backend.py").write_text(BACKEND.format("installed"))

    project = tmp_path / "project"
    project.mkdir()

    def run(pyproject):
        (project / "pyproject.toml").write_text(pyproject)
        subprocess.run(
            ["sh", "-e", "-c", '. "$0"; bh_python_install --build', HELPER],
            cwd=project,
            env={
                "PATH": os.environ["PATH"],
                "PYTHONPATH": str(installed),
                "AELTRA_INSTALL_PREFIX": str(prefix),
            },
            check=True
        )
        return sorted(p.name for p in (project / "dist").iterdir())

    run.project = project
    return run


def test_project_does_not_hide_installed_module(build):
    (build.project / "backend.py").write_text(BACKEND.format("project"))
    assert build('[build-system]\nbuild-backend = "backend"\n') == \
        ["installed.whl"]


def test_backend_path_leads_to_the_project(build):
    (build.project / "backend.py").write_text(BACKEND.format("project"))
    assert build(
        '[build-system]\n'
        'build-backend = "backend"\n'
        'backend-path = ["."]\n'
    ) == ["project.whl"]


def test_backend_object(build):
    (build.project / "in_tree.py").write_text(
        "class Backend:\n"
        "    @staticmethod\n"
        "    def build_wheel(wheel_directory):\n"
        "        open(wheel_directory + '/object.whl', 'w').close()\n"
    )
    assert build(
        '[build-system]\n'
        'build-backend = "in_tree:Backend"\n'
        'backend-path = ["."]\n'
    ) == ["object.whl"]
