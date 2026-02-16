#!/usr/bin/env python3

"""Aeltra miscellaneous Python modules."""

import os

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

VERSION = os.environ.get("AELTRA_DISTRO_TOOLS_VERSION", "0.0.0")

setup(
    name='aeltra-misc',
    version=VERSION,
    url='https://github.com/aeltra/aeltra-distro-tools',
    author='Tobias Koch',
    author_email='tobias.koch@gmail.com',
    license='MIT',
    packages=[
        'aeltra',
        'aeltra.miscellaneous',
    ],
    package_dir={'': 'lib'},
    platforms=['Linux'],

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Cool Kids',
        'Topic :: Admin :: Configuration',
        'Programming Language :: Python :: 3'
    ],

    keywords='Aeltra OS shared modules',
    description='Python modules shared between Aeltra OS Python projects',
    long_description='Python modules shared between Aeltra OS Python projects',
)
