#!/usr/bin/env python3

"""Aeltra OS image generator tool."""

import os

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

VERSION = os.environ.get("AELTRA_DISTRO_TOOLS_VERSION", "0.0.0")

setup(
    name='aeltra-image',
    version=VERSION,
    url='https://github.com/aeltra/image-generator',
    author='Tobias Koch',
    author_email='tobias.koch@gmail.com',
    license='MIT',
    packages=[
        'aeltra.osimage',
    ],
    package_dir={'': 'lib'},
    data_files=[
        ('bin', ['bin/aeltra-image']),
    ],
    package_data={
        'aeltra.osimage': [
            "customize/pasteur/build-essential",
            "customize/pasteur/minimal",
            "package/common/tarball",
        ],
    },
    platforms=['Linux'],

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3'
    ],

    keywords='Aeltra OS image generator',
    description='Aeltra OS image generator tool',
    long_description='Aeltra OS image generator tool',
)
