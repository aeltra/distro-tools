#!/usr/bin/env python3

"""Aeltra OS distro info."""

import os

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

VERSION = os.environ.get("AELTRA_DISTRO_TOOLS_VERSION", "0.0.0")

setup(
    name='aeltra-distro-info',
    version=VERSION,
    url='https://github.com/aeltra/aeltra-distro-tools',
    author='Tobias Koch',
    author_email='tobias.koch@gmail.com',
    license='MIT',
    packages=[
        'aeltra.distro.config',
        'aeltra.distro.config.v1',
    ],
    package_dir={'': 'lib'},
    data_files=[
        ('bin', [
            'bin/aeltra-distro-info',
        ]),
    ],
    platforms=['Linux'],

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Cool Kids',
        'Topic :: Admin :: Configuration',
        'Programming Language :: Python :: 3'
    ],

    keywords='Aeltra OS distro versions releases mirrors',
    description='Aeltra OS distro info',
    long_description='Aeltra OS distro info',
)
