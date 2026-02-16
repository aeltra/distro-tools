#!/usr/bin/env python3

"""Aeltra OS repository index generator."""

import os

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

VERSION = os.environ.get("AELTRA_DISTRO_TOOLS_VERSION", "0.0.0")

setup(
    name='aeltra-repository',
    version=VERSION,
    url='https://github.com/aeltra/distro-tools',
    author='Tobias Koch',
    author_email='tobias.koch@gmail.com',
    license='MIT',
    packages=[
        'aeltra.repository',
    ],
    package_dir={'': 'lib'},
    data_files=[
        ('bin', [
            'bin/aeltra-repo-index',
        ]),
    ],
    platforms=['Linux'],

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3'
    ],

    keywords='Aeltra OS package repository index',
    description='Aeltra OS package repository index generator',
    long_description='Aeltra OS package repository index generator',
)
