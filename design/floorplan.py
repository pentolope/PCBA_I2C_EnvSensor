from __future__ import annotations

import json
import os
import sys

from . import layout, netlist

REPO_ROOT = layout.REPO_ROOT
INTENT_PATH = os.path.join(REPO_ROOT, "board", "floorplan.json")

#: The placer reads and writes board coordinates, so every rectangle here
#: is stated in them.
def _rect(x0, y0, x1, y1):
    left, top = layout.to_board(min(x0, x1), max(y0, y1))
    right, bottom = layout.to_board(max(x0, x1), min(y0, y1))
    return [round(left, 4), round(top, 4), round(right, 4), round(bottom, 4)]


def envelope_rect():
    xs = [point[0] for point in layout.outline_points()]
    ys = [point[1] for point in layout.outline_points()]
    return _rect(min(xs), min(ys), max(xs), max(ys))


def _island_zone():
    _low, high = layout.NOTCH_Y_MM
    return _rect(-layout.BOARD_HALF_WIDTH_MM, high,
                 layout.BOARD_HALF_WIDTH_MM, layout.BOARD_LENGTH_MM)


def _neck_keepout():
    low, high = layout.NOTCH_Y_MM
    return _rect(-layout.BOARD_HALF_WIDTH_MM, low,
                 layout.BOARD_HALF_WIDTH_MM, high)


def _connector_zone():
    return _rect(-layout.BOARD_HALF_WIDTH_MM, 0.0,
                 layout.BOARD_HALF_WIDTH_MM, layout.CONNECTOR_ZONE_TOP_MM)


def _sensor_zone():
    return _rect(-layout.BOARD_HALF_WIDTH_MM, layout.CONNECTOR_ZONE_TOP_MM,
                 layout.BOARD_HALF_WIDTH_MM, layout.NECK_ENTRY_Y_MM - 0.5)


def intent(parameters):
    document = {
        "schema": 1,
        "kind": "floorplan-intent",
        "min_reader": 2,
        "units": "mm",
        "board": netlist.PROJECT_NAME + ".kicad_pcb",
        "envelope": {"rect": envelope_rect(), "tolerance_mm": 0.5},
        "defaults": {"zone_tolerance_mm": 0.5},
        "blocks": [
            {"name": "host_interface",
             "refs": ["J1", "D1", "D2", "R3", "C1"],
             "zone": _connector_zone(),
             "side": "F",
             "note": "protection and rail damping at the mating face",
             "context": {"why": "the ESD device has to sit between the "
                                "connector and everything it protects, and "
                                "the damping resistor between the connector "
                                "and the bulk capacitance it damps"}},
            {"name": "bus_and_sensors",
             "refs": ["R1", "R2", "U2", "U3", "C3", "C4"],
             "zone": _sensor_zone(),
             "side": "F",
             "note": "pull-ups, pressure and light sensors",
             "context": {"why": "the pressure port and the optical aperture "
                                "only need to be clear, so this block is the "
                                "search space"}},
            {"name": "isolated_island",
             "refs": ["U1", "C2"],
             "zone": _island_zone(),
             "side": "F",
             "exclusive": True,
             "note": "temperature and humidity sensor, across the neck",
             "context": {"why": "the island exists to hold this sensor away "
                                "from every part that dissipates"}},
        ],
        "keepouts": [
            {"name": "isolation_neck",
             "rect": _neck_keepout(),
             "sides": ["F", "B"],
             "note": "only the four island nets cross here",
             "context": {"why": "copper and parts in the neck are the "
                                "conduction path the neck exists to break"}},
        ],
        "edge_connectors": [
            {"ref": "J1",
             "edge": "south",
             "center_on_edge": {"tolerance_mm": 0.5},
             "context": {"why": "the cable leaves the board in its own plane, "
                                "so a pull is reacted by the through-hole "
                                "retention and not by a solder fillet"}},
        ],
        "decaps": {"max_distance_mm": 2.5, "exempt": ["C1"],
                   "pin_functions": ["3V3"]},
        "must_lock": sorted(layout.LOCKED_REFERENCES),
        #: Three courtyards leave the outline on purpose: the declared
        #: edge connector's, which is where the mating half goes, and the
        #: two mounting holes' screw-head keepouts. Each hole itself keeps
        #: 0.9 mm of material to the edge.
        "legality_budget": {"overlap_area": 0.0, "oob_count": 3},
    }
    return document


def write(parameters=None):
    if parameters is None:
        from . import rules

        parameters = rules.load_parameters()
    document = intent(parameters)
    os.makedirs(os.path.dirname(INTENT_PATH), exist_ok=True)
    with open(INTENT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return INTENT_PATH


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
