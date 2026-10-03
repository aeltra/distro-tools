# -*- encoding: utf-8 -*-
#
# The tests import the source tree, including the misc tree, which brings
# aeltra/__init__.py. That makes aeltra a regular package wherever the
# tests run -- with the host's python3-aeltra-misc installed or in a bare
# virtualenv alike -- and a regular package sees other trees only through
# its __path__, so they are added there.

import os
import sys

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
TREES = [
    os.path.join(ROOT, sub, "lib")
    for sub in ("misc", "distro-info", "image-gen")
]

sys.path[:0] = TREES

for name in list(sys.modules):
    if name == "aeltra" or name.startswith("aeltra."):
        del sys.modules[name]

import aeltra  # noqa: E402

aeltra.__path__[:] = [os.path.join(tree, "aeltra") for tree in TREES]
