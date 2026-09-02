from __future__ import annotations

import hashlib
import json
import os
import sys

from . import layout

sys.path.insert(0, os.path.join(layout.REPO_ROOT, "tooling",
                                "PCBA_AutoDesignAndTest"))

from pcbqa import extract, headless  # noqa: E402
from pcbqa.fabricators.store import CatalogStore  # noqa: E402

REPO_ROOT = layout.REPO_ROOT
REQUIREMENTS_PATH = os.path.join(REPO_ROOT, "fab", "requirements.json")
PHYSICAL_PATH = os.path.join(REPO_ROOT, "fab", "physical_inputs.json")
DIELECTRIC_PATH = os.path.join(REPO_ROOT, "fab", "dielectric.json")
CATALOG_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest",
                            "profiles", "jlcpcb")


def _approved():
    approved = CatalogStore(CATALOG_ROOT).approved()
    if approved is None:
        raise RuntimeError(
            "no approved fabricator catalog, so no physical input can be "
            "resolved from evidence")
    return approved


def _requirements():
    with open(REQUIREMENTS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def resolve():
    """Finished copper and board thickness, from the approved catalog.

    Resolved here rather than in a gate: validation must not be able to
    reach the fabricator package, and so cannot reach the network by
    accident. Each value comes out as a parameter record carrying its
    source type and the catalog's digest, so what a gate later reads is
    checkable without the catalog being present.
    """
    import pcbnew

    headless.suppress_blocking_ui()
    with open(REQUIREMENTS_PATH, "rb") as handle:
        raw = handle.read()
    requirements = json.loads(raw.decode("utf-8"))
    board = pcbnew.LoadBoard(layout.BOARD_PATH)
    stack = [board.GetLayerName(layer)
             for layer in board.GetEnabledLayers().CuStack()]
    approved = _approved()
    return {
        "copper_thickness_mm": extract.approved_finished_copper(
            approved,
            extract.copper_assignments_from_requirements(requirements, stack)),
        "board_thickness_mm": extract.requirements_board_thickness(
            requirements, hashlib.sha256(raw).hexdigest()),
    }


def verify(document=None):
    """Every approved-evidence parameter still agrees with the catalog."""
    if document is None:
        with open(PHYSICAL_PATH, encoding="utf-8") as handle:
            document = json.load(handle)
    approved = _approved()
    problems = []
    records = dict(document["copper_thickness_mm"])
    records["board_thickness_mm"] = document["board_thickness_mm"]
    for label, record in sorted(records.items()):
        if record["source_type"] != "approved-evidence":
            continue
        try:
            extract.verify_approved_parameter(record, approved)
        except extract.ExtractionError as exc:
            problems.append({"parameter": label, "issue": str(exc)})
    return problems


DIELECTRIC_KINDS = ("core", "prepreg")


def applicable_dielectric_records(materials, layers):
    """Every stated Dk that could describe the laminate this board is built
    from, keyed by the catalog identity it was stated under.

    A record whose stated scope excludes this layer count describes some
    other build and is not a bound on this one. A record that states no
    scope is the source's general statement and is kept: leaving it out
    could only lower the maximum, and the maximum is what the capacitance
    claim leans on.
    """
    applicable = {}
    for identity, record in sorted(materials.items()):
        if not isinstance(record, dict):
            continue
        if record.get("kind") not in DIELECTRIC_KINDS:
            continue
        if not isinstance(record.get("dk"), (int, float)):
            continue
        applies = record.get("applies") or {}
        low, high = applies.get("min_layers"), applies.get("max_layers")
        if low is not None and layers < low:
            continue
        if high is not None and layers > high:
            continue
        applicable[identity] = record["dk"]
    return applicable


def highest_dielectric_constant():
    """The largest Dk the approved catalog states for a laminate this board
    could be built from.

    Capacitance rises with permittivity, so the largest applicable value is
    the conservative one for a bus-capacitance budget, and taking it as a
    maximum is what lets the capacitance claim be an upper bound rather
    than an estimate.

    The maximum is only a bound over the set it ranges across, so the set
    has to be the records that can describe this board. The fabricator
    states a dielectric constant for a two-layer laminate specifically; a
    maximum that could not see it would be a bound over other people's
    materials that happened to sit above this board's.
    """
    approved = _approved()
    layers = _requirements()["copper_layers"]
    applicable = applicable_dielectric_records(
        approved["normalized"]["materials"], layers)
    if not applicable:
        raise RuntimeError(
            "the approved catalog states no dielectric constant for a "
            "%d-layer build, so none can be frozen from evidence" % layers)
    source = max(applicable, key=lambda identity: (applicable[identity],
                                                   identity))
    return {"relative_permittivity_max": {
        "value": applicable[source],
        "units": "1",
        "source": source,
        "source_type": "approved-evidence",
        "digest": approved["normalized_sha256"],
        "considered": dict(sorted(applicable.items())),
        "applicability": "the largest permittivity the approved fabricator "
                         "catalog states for any laminate a %d-layer board "
                         "can be built from; used only where a larger "
                         "permittivity is the conservative choice" % layers,
    }}


def write_dielectric():
    document = highest_dielectric_constant()
    os.makedirs(os.path.dirname(DIELECTRIC_PATH), exist_ok=True)
    with open(DIELECTRIC_PATH, "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return DIELECTRIC_PATH


def write():
    document = resolve()
    os.makedirs(os.path.dirname(PHYSICAL_PATH), exist_ok=True)
    with open(PHYSICAL_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return PHYSICAL_PATH


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
    sys.stdout.write(write_dielectric() + "\n")
