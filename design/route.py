"""Regenerate the placed board, then hand routing to the toolkit.

The candidate search this file used to run privately - attempt loop,
tidy passes, junction bonding, canonical serialization, acceptance
gating, provenance record - is owned by the toolkit's `run.py route`,
driven by the routing.search and routing.transforms declarations in
board/manifest.json. `--adopt` is the toolkit's one sanctioned
promotion of an accepted candidate into the tree, digest-verified
against its record.
"""
from __future__ import annotations

import os
import subprocess
import sys

from . import layout


def run():
    layout.write()
    proc = subprocess.run(
        [sys.executable,
         os.path.join("tooling", "PCBA_AutoDesignAndTest", "run.py"),
         "route", os.path.join("board", "manifest.json"), "--adopt"],
        cwd=layout.REPO_ROOT, check=False)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    run()
