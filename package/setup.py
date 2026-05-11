#!/usr/bin/env python3
"""Version-injection shim; static metadata lives in pyproject.toml."""

import os

from setuptools import setup

setup(version=os.environ.get("AELTRA_DISTRO_TOOLS_VERSION", "0.0.0"))
