"""The board's claims as the toolkit's committed claim-evidence document.

`design/rules.py` owns the engineering - every evaluator, every number,
every datasheet citation. This module only adapts its results into the
toolkit's claim-evidence shape and writes `generated/claims.json`, so the
claims the test suite exercises and the claims `CLAIM.MATRIX`,
`CLAIM.POLICY` and `release-check` judge are the same records by
construction. The manifest registers this file as the document's
generator, so `PROV.DERIVED_DOCUMENTS` re-runs it and refuses a stale or
hand-edited commit, and `run.py regenerate` refreshes it in place.
"""
from __future__ import annotations

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLKIT_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
if TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, TOOLKIT_ROOT)

from pcbqa import evidence, headless  # noqa: E402

headless.suppress_blocking_ui()

from . import layout, rules  # noqa: E402

DEFAULT_PATH = os.path.join(REPO_ROOT, "generated", "claims.json")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def results():
    """Every claim the rules produce, in the toolkit's result shape.

    Identities are the rules' own claim identities; ids are their slugs,
    suffixed deterministically where one identity yields several claims.
    """
    rows, seen = [], {}
    for record in rules.claims(rules.evaluate_all(layout)):
        identity = record["scope"]["identity"]
        base = _slug(identity)
        count = seen.get(base, 0)
        seen[base] = count + 1
        result_id = base if count == 0 else "{}_{}".format(base, count + 1)
        rows.append(evidence.claim_result(result_id, identity, record))
    return rows


def document():
    return evidence.claim_document(results())


def write(path=None):
    target = path or os.environ.get("PCBQA_OUT") or DEFAULT_PATH
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    return evidence.write_document(target, document())


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
