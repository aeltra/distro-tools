# -*- encoding: utf-8 -*-
#
# The tests import the source tree rather than an installed
# python3-aeltra-ffi-libarchive, which would otherwise come first.

import os
import sys

TREE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")
)

sys.path[:0] = [TREE]

for name in list(sys.modules):
    if name == "aeltra" or name.startswith("aeltra."):
        del sys.modules[name]
