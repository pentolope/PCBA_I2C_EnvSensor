from __future__ import annotations

import json
import os
import sys

from . import layout, netlist

REPO_ROOT = layout.REPO_ROOT
SIM_DIR = os.path.join(REPO_ROOT, "sim")
PARAMETERS_PATH = os.path.join(REPO_ROOT, "components", "parameters.json")

#: The name the manifest registers the extracted copper model under. The
#: measured identity embeds the board digest, so only an alias can be
#: written into a stored scenario.
EXTRACTED_MODEL_ALIAS = "rail_copper"

INTERCONNECT_COVERAGE = ("geometry-derived", "quasi-static-extracted",
                         "full-wave-extracted", "measured")


def parameters():
    with open(PARAMETERS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def spec(params, reference):
    """The frozen parameters of whatever part the netlist selects.

    Keyed through the netlist rather than by a literal MPN, so replacing
    a part is one edit in one place and cannot leave a stale key here.
    """
    return params["parts"][netlist.PARTS[reference]["mpn"]]


def _value(record):
    return record["value"]


def receiver_vih_factor(params):
    """The strictest high-level threshold any bus receiver declares."""
    factors = []
    for reference in netlist.ADDRESS_STRAPS:
        inputs = spec(params, reference)["digital_inputs"]
        for pin in _bus_pins(reference):
            if pin in inputs:
                factors.append(inputs[pin]["vih_min"]["factor_of_supply"])
    return max(factors)


def driver_vol_max(params):
    """The highest low level any bus driver may present."""
    levels = [params["i2c"]["vol_max_v"]["value"]]
    for reference in netlist.ADDRESS_STRAPS:
        outputs = spec(params, reference)["digital_outputs"]
        for pin in _bus_pins(reference):
            if pin in outputs:
                levels.append(_value(outputs[pin]["vol_max"]))
    return max(levels)


def _bus_pins(reference):
    pins = []
    for net in netlist.BUS_NETS:
        for pin_ref in netlist.NETS[net]:
            head, _, number = pin_ref.partition(".")
            if head == reference:
                pins.append(number)
    return pins


def pull_up_ohms(params):
    return _value(spec(params, "R1")["resistance_ohms"])


def rail_damping_ohms(params):
    return _value(
        spec(params, netlist.RAIL_DAMPING_REFERENCE)["resistance_ohms"])


def bulk_capacitance_f(params):
    """Every rail capacitor at its worst-case low value."""
    total = 0.0
    for reference in netlist.BULK_CAPACITOR_REFERENCES:
        record = spec(params, reference)
        total += (_value(record["capacitance_f"])
                  * (1.0 - _value(record["capacitance_tolerance"])))
    return total


def board_current_a(params):
    """Every fitted part's largest declared supply current, summed.

    A part whose datasheet states no maximum contributes its typical,
    which is what makes this an approximate budget rather than a bound.
    """
    total = 0.0
    approximate = False
    for reference, part in sorted(netlist.PARTS.items()):
        if not part["mpn"]:
            continue
        record = params["parts"][part["mpn"]]
        maximum = record.get("supply_current_max_a")
        if maximum is not None and "value" in maximum:
            total += maximum["value"]
            continue
        typical = record.get("supply_current_typ_a")
        if typical is None:
            continue
        total += typical["value"]
        approximate = True
    for reference, net in netlist.PULL_UP_REFERENCES.items():
        total += (netlist.RAILS["3V3"]["max_v"]
                  / _value(spec(params, reference)["resistance_ohms"]))
    return total, approximate


def lowest_supply_abs_max_v(params):
    values = []
    for part in netlist.PARTS.values():
        if not part["mpn"]:
            continue
        supply = params["parts"][part["mpn"]].get("supply") or {}
        record = supply.get("abs_max_v")
        if record and "value" in record:
            values.append(record["value"])
    return min(values)


def highest_supply_min_v(params):
    values = []
    for part in netlist.PARTS.values():
        if not part["mpn"]:
            continue
        supply = params["parts"][part["mpn"]].get("supply") or {}
        record = supply.get("characterised_min_v")
        if record and "value" in record:
            values.append(record["value"])
    return max(values)


def _ideal(records):
    return {name: {"stands_in_for": detail,
                   "accepted_for_design_decision": True}
            for name, detail in records.items()}


def _measurement(name, kind, node, op, value):
    return {"name": name, "kind": kind, "node": node,
            "assertion": {"op": op, "value": value}}


def bus_rise_time_scenario(params):
    """The specification's rise time, measured where it is defined.

    t_r runs from 0.3 VDD to 0.7 VDD, so the transient starts with the
    line already at 0.3 VDD: the source's first pulse level is the DC
    operating point, which charges the bus capacitance to it before
    t=0. The stop time is the limit itself, so the final value passing
    0.7 VDD IS the statement that the edge fits inside the limit.
    """
    supply = netlist.RAILS["3V3"]["max_v"]
    mode = params["i2c"]["modes"]["standard"]
    limit_s = _value(mode["max_rise_time_s"])
    capacitance = _value(mode["max_bus_capacitance_f"])
    resistance = pull_up_ohms(params)
    return {
        "name": "i2c_rise_time_at_the_capacitance_budget",
        "elements": [
            {"kind": "vsource_pulse", "name": "RELEASE",
             "nodes": ["rail", "0"],
             "pulse": {"v1": 0.3 * supply, "v2": supply, "delay_s": 0.0,
                       "rise_s": 1e-12, "fall_s": 1e-12,
                       "width_s": 10.0 * limit_s,
                       "period_s": 20.0 * limit_s}},
            {"kind": "resistor", "name": "RPULLUP", "nodes": ["rail", "bus"],
             "value": resistance},
            {"kind": "capacitor", "name": "CBUS", "nodes": ["bus", "0"],
             "value": capacitance},
        ],
        "analyses": [{"kind": "tran", "step_s": limit_s / 1000.0,
                      "stop_s": limit_s}],
        "measurements": [
            _measurement("bus_level_at_the_rise_time_limit",
                         "tran_final_voltage", "bus", ">=", 0.7 * supply),
        ],
        "assumptions": _ideal({
            "RELEASE": "the open-drain sink letting go of the line, as an "
                       "ideal source stepping from the 0.3 VDD threshold "
                       "the rise time is measured from",
            "RPULLUP": "one on-board pull-up at its nominal value; the pod "
                       "carries the only pull-ups, so this is the weakest "
                       "the bus can be pulled up and the slowest edge",
            "CBUS": "the whole bus - pod, cable and host - as one ideal "
                    "capacitance at the specification's maximum, with no "
                    "distributed delay",
        }),
    }


def receiver_high_level_scenario(params):
    """The strictest receiver sees a valid high inside the clock's high
    period, starting from the highest low level a driver may leave."""
    supply = netlist.RAILS["3V3"]["min_v"]
    mode = params["i2c"]["modes"]["standard"]
    capacitance = _value(mode["max_bus_capacitance_f"])
    resistance = pull_up_ohms(params)
    high_period_s = 0.4 / _value(mode["max_scl_hz"])
    threshold = receiver_vih_factor(params) * supply
    return {
        "name": "receiver_high_level_within_the_clock_high_period",
        "elements": [
            {"kind": "vsource_pulse", "name": "RELEASE",
             "nodes": ["rail", "0"],
             "pulse": {"v1": driver_vol_max(params), "v2": supply,
                       "delay_s": 0.0, "rise_s": 1e-12, "fall_s": 1e-12,
                       "width_s": 10.0 * high_period_s,
                       "period_s": 20.0 * high_period_s}},
            {"kind": "resistor", "name": "RPULLUP", "nodes": ["rail", "bus"],
             "value": resistance},
            {"kind": "capacitor", "name": "CBUS", "nodes": ["bus", "0"],
             "value": capacitance},
        ],
        "analyses": [{"kind": "tran", "step_s": high_period_s / 1000.0,
                      "stop_s": high_period_s}],
        "measurements": [
            _measurement("receiver_level_at_the_end_of_the_high_period",
                         "tran_final_voltage", "bus", ">=", threshold),
        ],
        "assumptions": _ideal({
            "RELEASE": "the sink letting go from the highest low level any "
                       "bus device may present, into a supply at its "
                       "minimum",
            "RPULLUP": "one on-board pull-up at its nominal value",
            "CBUS": "the whole bus as one ideal capacitance at the "
                    "specification's maximum",
        }),
    }


def rail_mating_scenario(params, model_identity=None):
    """Live mating: the cable's inductance into the pod's capacitance.

    The peak is what decides whether a device survives being plugged in,
    and it rises as the loop is less damped. With the extracted model
    substituted the series resistance is a LOWER bound - the extraction
    omits via barrel resistance - and less resistance can only raise the
    peak, so the simulated peak bounds the true one from ABOVE, which is
    the direction a "stays under the absolute maximum" claim needs.
    """
    supply = netlist.RAILS["3V3_IN"]["max_v"]
    contract = netlist.HOST_CONTRACT
    current, _approximate = board_current_a(params)
    extracted = model_identity is not None
    settle_s = 5e-5
    elements = [
        {"kind": "vsource_pulse", "name": "MATE", "nodes": ["host", "0"],
         "pulse": {"v1": 0.0, "v2": supply, "delay_s": settle_s / 100.0,
                   "rise_s": 1e-9, "fall_s": 1e-9,
                   "width_s": 10.0 * settle_s, "period_s": 20.0 * settle_s}},
        {"kind": "inductor", "name": "LCABLE", "nodes": ["host", "cable"],
         "value": contract["cable_inductance_h"]},
        {"kind": "resistor", "name": "RCABLE", "nodes": ["cable", "conn"],
         "value": contract["cable_resistance_ohm"]},
        {"kind": "resistor", "name": "RDAMP",
         "nodes": ["conn", "feed" if extracted else "rail"],
         "value": rail_damping_ohms(params)},
    ]
    if extracted:
        elements.append({"kind": "model_instance", "name": "COPPER",
                         "nodes": ["feed", "rail"], "model": model_identity})
    elements.extend([
        {"kind": "capacitor", "name": "CBULK", "nodes": ["rail", "0"],
         "value": bulk_capacitance_f(params)},
        {"kind": "resistor", "name": "RLOAD", "nodes": ["rail", "0"],
         "value": supply / current},
    ])
    peak = _measurement("rail_peak_on_mating", "tran_max_voltage", "rail",
                        "<=", lowest_supply_abs_max_v(params))
    settled = _measurement("rail_settled", "tran_final_voltage", "rail",
                           ">=", highest_supply_min_v(params))
    ideal = {
        "MATE": "the connector's supply contact closing on a live host, as "
                "an ideal step; a slower contact can only reduce the "
                "transient this measures",
        "LCABLE": "one metre of ordinary four-way cable as a single lumped "
                  "inductance",
        "RCABLE": "the cable conductors and the mated contacts as one "
                  "lumped resistance",
        "RDAMP": "the rail damping resistor at its nominal value",
        "CBULK": "every rail capacitor as one ideal capacitance at its "
                 "worst-case low value, with no ESR and no DC bias "
                 "derating; less capacitance is the less damped case",
        "RLOAD": "the whole board's supply current as a fixed resistance",
    }
    scenario = {
        "name": ("rail_mating_transient_over_extracted_copper" if extracted
                 else "rail_mating_transient_over_ideal_copper"),
        "elements": elements,
        "analyses": [{"kind": "tran", "step_s": settle_s / 20000.0,
                      "stop_s": settle_s}],
        "assumptions": _ideal(ideal),
    }
    if not extracted:
        scenario["measurements"] = [peak, settled]
        return scenario
    bound = {
        "kind": "upper_bound",
        "basis": {
            "kind": "assumed",
            "detail": "the extracted supply copper resistance is not an "
                      "exact value, and the mating peak falls monotonically "
                      "with series resistance, so the simulated peak bounds "
                      "the true one from above",
        },
    }
    peak["knowledge"] = bound
    scenario["measurements"] = [
        peak,
        {"name": "rail_settled", "kind": "tran_final_voltage", "node": "rail",
         "knowledge": bound},
    ]
    scenario["required_coverage"] = {
        "interconnect_dc": list(INTERCONNECT_COVERAGE)}
    return scenario


def _write(path, document):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def write():
    params = parameters()
    written = []
    for name, document in (
            ("pre_layout_bus_rise_time.json",
             bus_rise_time_scenario(params)),
            ("pre_layout_receiver_high_level.json",
             receiver_high_level_scenario(params)),
            ("pre_layout_rail_mating.json", rail_mating_scenario(params)),
            ("post_layout_rail_mating.json",
             rail_mating_scenario(params, EXTRACTED_MODEL_ALIAS))):
        written.append(_write(os.path.join(SIM_DIR, name), document))
    return written


if __name__ == "__main__":
    for written in write():
        sys.stdout.write(written + "\n")
