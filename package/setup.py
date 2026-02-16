#!/usr/bin/env python3

"""Aeltra OS packaging scripts and tools."""

import os

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

VERSION = os.environ.get("AELTRA_DISTRO_TOOLS_VERSION", "0.0.0")

setup(
    name='aeltra-package',
    version=VERSION,
    url='https://github.com/aeltra/aeltra-distro-tools',
    author='Tobias Koch',
    author_email='tobias.koch@gmail.com',
    license='MIT',

    packages=[
        'aeltra.package',
        'aeltra.package.aeltrapack',
        'aeltra.package.deb2aeltra',
    ],
    data_files=[
        ('bin', [
            'bin/aeltra-pack',
            'bin/deb2aeltra',
        ]),
    ],
    package_data={
        'aeltra.package.aeltrapack': [
            "helpers/python.sh",
            "helpers/arch.sh",
            "relaxng/package.rng.xml",
        ],
    },
    package_dir={'': 'lib'},

    platforms=['Linux'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3'
    ],

    keywords='Aeltra OS packaging development',
    description='Aeltra OS packaging scripts and tools',
    long_description='Aeltra OS packaging scripts and tools',
)
