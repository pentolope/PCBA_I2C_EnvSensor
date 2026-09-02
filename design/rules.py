from __future__ import annotations

import json
import math
import os
import sys

from . import netlist

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMETERS_PATH = os.path.join(REPO_ROOT, "components", "parameters.json")
TOOLKIT_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
FOOTPRINT_ROOT = "/usr/share/kicad/footprints"

if TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, TOOLKIT_ROOT)

from pcbqa import claim  # noqa: E402

DIRECT = "direct"
ASSUMED = "assumed"
DERIVED = "derived"

EVIDENCE_CLASSES = {
    DIRECT: "datasheet-behavioral",
    ASSUMED: "assumed-behavioral",
    DERIVED: "design-source",
}

#: Sensirion's SHT4x thermal table is the junction-to-ambient figure for
#: the package alone; the board it sits on is the rest of the path, and
#: that part is geometry this repository owns.
FR4_CONDUCTIVITY_W_PER_M_K = 0.3
COPPER_CONDUCTIVITY_W_PER_M_K = 400.0
COPPER_THICKNESS_M = 35e-6

#: Still air over a small board: natural convection plus radiation from
#: both faces, as one combined coefficient. Assumed, and assumed LOW -
#: less cooling is more rise - so the temperature this yields bounds the
#: real one from above.
STILL_AIR_COEFFICIENT_MIN_W_PER_M2_K = 5.0

#: What a part whose datasheet publishes no maximum supply current is
#: charged, as a multiple of its typical. Assumed, and assumed high, so
#: the current budget it feeds is an upper bound.
UNPUBLISHED_CURRENT_DERATING = 4.0

#: Board thickness is the microstrip height only because the reference
#: plane is the far layer of a two-layer board.
DIELECTRIC_PATH = os.path.join(REPO_ROOT, "fab", "dielectric.json")
PHYSICAL_INPUTS_PATH = os.path.join(REPO_ROOT, "fab",
                                    "physical_inputs.json")
SPEED_OF_LIGHT_M_PER_S = 299792458.0

#: A track on the plane's own layer runs between two coplanar edges of
#: pour instead of over a plane, which is the more capacitive geometry.
#: Charging it this multiple of the microstrip value is assumed, and
#: assumed high, so the total stays an upper bound.
COPLANAR_CAPACITANCE_MULTIPLE = 4.0

#: What "small against the sensor's own accuracy" is taken to mean.
THERMAL_RISE_FRACTION_OF_ACCURACY = 0.25

#: The measurement duty the current and thermal budgets are evaluated at.
MEASUREMENTS_PER_SECOND = netlist.SAMPLE_RATE_HZ


def load_parameters():
    with open(PARAMETERS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _spec(parameters, reference):
    mpn = netlist.PARTS[reference]["mpn"]
    return parameters["parts"].get(mpn) if mpn else None


def _documents(*records):
    seen = []
    for record in records:
        if isinstance(record, dict):
            document = record.get("document")
            if document and document not in seen:
                seen.append(document)
    return seen


def _evidence(basis, documents, assumptions=(), omissions=(),
              phenomenon="device_electrical"):
    provenance = {"source": "components/parameters.json",
                  "documents": list(documents)}
    return claim.evidence(
        phenomenon, EVIDENCE_CLASSES.get(basis, "design-source"),
        provenance, assumptions=list(assumptions),
        omitted_contributions=list(omissions))


def _requirement(name, op, value):
    return claim.requirement(name, "BRIEF.md", {"op": op, "value": value})


def _claim(identity, units, significance, value, basis, documents,
           requirement, knowledge=claim.EXACT, scope_level="net",
           assumptions=(), omissions=(), phenomenon="device_electrical"):
    evidence = _evidence(basis, documents, assumptions, omissions, phenomenon)
    if value is None:
        return claim.claim(scope_level, identity, units, claim.UNKNOWN, {},
                           evidence, significance, None, requirement)
    knowledge_basis = None
    if knowledge != claim.EXACT:
        knowledge_basis = claim.knowledge_basis(
            claim.DERIVED if basis == DERIVED else claim.ASSUMED,
            "datasheet_limit" if basis == DIRECT else basis)
    return claim.claim(scope_level, identity, units, knowledge,
                       {"value": value}, evidence, significance,
                       knowledge_basis, requirement)


def _structural(identity, significance, violations, requirement_name):
    return _claim(identity, "violations", significance, float(len(violations)),
                  DERIVED, ["design-source"],
                  _requirement(requirement_name, "<=", 0.0))


# ---------------------------------------------------------------------------
# addressing
# ---------------------------------------------------------------------------

def _strap_level(reference, pin):
    """Which rail a device's address pin is strapped to, from the netlist."""
    if pin is None:
        return None
    net = netlist.pin_to_net().get("%s.%s" % (reference, pin))
    if net in ("GND", "3V3"):
        return net
    return net


def shipped_addresses(parameters):
    """{reference: address} for every device the board can reach at once."""
    addresses = {}
    for reference, strap in sorted(netlist.ADDRESS_STRAPS.items()):
        spec = _spec(parameters, reference)
        declared = spec["i2c_addresses"]
        level = _strap_level(reference, strap["pin"])
        if strap["pin"] is None:
            addresses[reference] = declared["fixed"]["value"]
            continue
        addresses[reference] = declared[level]["value"]
    return addresses


def evaluate_address_uniqueness(parameters):
    addresses = shipped_addresses(parameters)
    duplicates = []
    for reference, address in sorted(addresses.items()):
        others = [other for other, value in addresses.items()
                  if other != reference and value == address]
        if others:
            duplicates.append({"reference": reference, "address": address,
                               "collides_with": sorted(others)})
    return {
        "addresses": addresses,
        "claim": _structural(
            "i2c_address_uniqueness",
            "every device the board ships with answers at its own address",
            duplicates, "no two reachable devices share a 7-bit address"),
        "violations": duplicates,
    }


# ---------------------------------------------------------------------------
# bus electrical
# ---------------------------------------------------------------------------

def _bus_pins(reference):
    pins = []
    for net in netlist.BUS_NETS:
        for pin_ref in netlist.NETS[net]:
            head, _, number = pin_ref.partition(".")
            if head == reference:
                pins.append((net, number))
    return pins


def bus_devices():
    return tuple(sorted(
        {pin_ref.split(".", 1)[0]
         for net in netlist.BUS_NETS for pin_ref in netlist.NETS[net]
         if netlist.PARTS[pin_ref.split(".", 1)[0]]["mpn"]}))


def total_pull_up_ohms(parameters):
    """Pod pull-up in parallel with the weakest host pull-up permitted."""
    pod = _spec(parameters, "R1")["resistance_ohms"]["value"]
    host = netlist.HOST_CONTRACT["min_host_pullup_ohms"]
    return pod * host / (pod + host), pod


def evaluate_sink_current(parameters):
    """Pull-up current at each driver's low level, against its rating."""
    combined, pod_only = total_pull_up_ohms(parameters)
    supply = netlist.RAILS["3V3"]["max_v"]
    spec_limit = parameters["i2c"]["iol_a"]
    claims, violations = [], []
    for reference in bus_devices():
        spec = _spec(parameters, reference)
        for _net, pin in _bus_pins(reference):
            output = (spec.get("digital_outputs") or {}).get(pin)
            if not output:
                continue
            vol = output["vol_max"]
            limit = output["vol_max"].get("iol_a", spec_limit["value"])
            current = (supply - vol["value"]) / combined
            identity = "%s.%s sink current at its low level" % (reference, pin)
            claims.append(_claim(
                identity, "A",
                "the current the pull-ups push into this pin while it holds "
                "the bus low, against the current its low level is "
                "specified at",
                current, DERIVED,
                _documents(vol, spec_limit) + ["design-source"],
                _requirement("open-drain sink current within the device's "
                             "specified low-level current", "<=", limit),
                scope_level="measurement"))
            if current > limit:
                violations.append({"pin": "%s.%s" % (reference, pin),
                                   "current_a": current, "limit_a": limit})
    return {"combined_pull_up_ohms": combined, "pod_pull_up_ohms": pod_only,
            "claims": claims, "violations": violations}


def evaluate_rise_time(parameters):
    """The specification's rise time at the specification's bus load."""
    _combined, pod_only = total_pull_up_ohms(parameters)
    factor = parameters["i2c"]["rise_time_rc_factor"]
    results = []
    for mode in sorted(netlist.HOST_CONTRACT["declared_bus_modes"]):
        record = parameters["i2c"]["modes"][mode]
        capacitance = record["max_bus_capacitance_f"]
        limit = record["max_rise_time_s"]
        rise = factor["value"] * pod_only * capacitance["value"]
        results.append({
            "mode": mode,
            "rise_time_s": rise,
            "limit_s": limit["value"],
            "claim": _claim(
                "bus rise time in %s mode at the maximum bus capacitance"
                % mode, "s",
                "how long the weakest pull-up on the bus takes to carry the "
                "line from 0.3 to 0.7 of the supply at the specification's "
                "maximum load",
                rise, DERIVED,
                _documents(factor, capacitance, limit) + ["design-source"],
                _requirement("bus rise time within the mode's limit",
                             "<=", limit["value"])),
        })
    return results


def pod_bus_capacitance(parameters):
    """What this board adds to the one bus-capacitance budget."""
    contributions = {}
    documents = []
    for reference in bus_devices():
        spec = _spec(parameters, reference)
        for _net, pin in _bus_pins(reference):
            record = (spec.get("digital_inputs") or {}).get(pin)
            if record is None:
                continue
            capacitance = record["input_capacitance_f"]
            contributions["%s.%s" % (reference, pin)] = capacitance["value"]
            documents.extend(_documents(capacitance))
    for reference in ("D1",):
        spec = _spec(parameters, reference)
        record = spec["line_capacitance_max_f"]
        for pin in spec["protected_pins"]:
            contributions["%s.%s" % (reference, pin)] = record["value"]
        documents.extend(_documents(record))
    per_line = {}
    for pin_ref, value in contributions.items():
        reference, _, pin = pin_ref.partition(".")
        net = netlist.pin_to_net().get(pin_ref)
        per_line.setdefault(net, 0.0)
        per_line[net] += value
    return per_line, sorted(set(documents))


def _dielectric():
    with open(DIELECTRIC_PATH, encoding="utf-8") as handle:
        return json.load(handle)["relative_permittivity_max"]


def _physical_inputs():
    with open(PHYSICAL_INPUTS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def microstrip_capacitance_f_per_m(width_mm):
    """Capacitance per metre of a track over the far layer's plane."""
    from pcbqa import transmission_line

    permittivity = _dielectric()
    physical = _physical_inputs()
    thickness = physical["board_thickness_mm"]["value"]
    conductor = physical["copper_thickness_mm"]["F.Cu"]["value"]
    z0, epsilon_effective = transmission_line.microstrip_z0(
        permittivity["value"], width_mm, thickness - conductor, conductor)
    return math.sqrt(epsilon_effective) / (SPEED_OF_LIGHT_M_PER_S * z0), (
        permittivity, physical)


def bus_track_capacitance(board_module):
    """Routed copper capacitance per bus net, measured from the board."""
    import pcbnew

    board = pcbnew.LoadBoard(board_module.BOARD_PATH)
    plane_layer = board.GetLayerName(
        board.GetEnabledLayers().CuStack()[-1])
    lengths = {}
    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_VIA_T:
            continue
        net = track.GetNetname()
        if net not in netlist.BUS_NETS:
            continue
        layer = board.GetLayerName(track.GetLayer())
        width = round(pcbnew.ToMM(track.GetWidth()), 4)
        key = (net, layer, width)
        lengths[key] = lengths.get(key, 0.0) + pcbnew.ToMM(track.GetLength())
    per_net, documents = {}, None
    for (net, layer, width), length_mm in sorted(lengths.items()):
        per_metre, documents = microstrip_capacitance_f_per_m(width)
        if layer == plane_layer:
            per_metre *= COPLANAR_CAPACITANCE_MULTIPLE
        per_net[net] = per_net.get(net, 0.0) + per_metre * length_mm * 1e-3
    return per_net, documents, plane_layer


def evaluate_bus_capacitance(parameters, board_module=None):
    per_line, documents = pod_bus_capacitance(parameters)
    budget = parameters["i2c"]["modes"]["standard"]["max_bus_capacitance_f"]
    tracks, sources, plane_layer = ({}, None, None)
    if board_module is not None:
        tracks, sources, plane_layer = bus_track_capacitance(board_module)
    claims = []
    for net in sorted(per_line):
        assumptions = []
        omissions = []
        total = per_line[net]
        if board_module is None:
            knowledge = claim.LOWER_BOUND
            omissions.append({"detail": "the routed copper's capacitance is "
                              "not included; no board was measured"})
        else:
            total += tracks.get(net, 0.0)
            knowledge = claim.UPPER_BOUND
            assumptions.append(
                {"detail": "every device pin contributes its published "
                 "maximum, the routed copper is charged at the microstrip "
                 "capacitance of the highest permittivity the approved "
                 "catalog publishes, and copper on %s - which runs between "
                 "coplanar pour edges rather than over a plane - is charged "
                 "%g times that" % (plane_layer,
                                    COPLANAR_CAPACITANCE_MULTIPLE)})
        claims.append(_claim(
            "%s capacitance contributed by this board" % net, "F",
            "the pin, protection and copper capacitance this board hangs "
            "on the line, which the cable and the host share the "
            "specification's one budget with",
            total, DERIVED, documents + ["design-source"],
            _requirement("the board's own share of the bus capacitance "
                         "budget", "<=", budget["value"]),
            knowledge=knowledge, assumptions=assumptions,
            omissions=omissions, phenomenon="capacitance"))
    return {"device_f": per_line, "track_f": tracks,
            "budget_f": budget["value"], "claims": claims}


def evaluate_logic_levels(parameters):
    """The lowest low a driver may leave against the strictest receiver."""
    supply_low = netlist.RAILS["3V3"]["min_v"]
    supply_high = netlist.RAILS["3V3"]["max_v"]
    drivers, receivers = [], []
    for reference in bus_devices():
        spec = _spec(parameters, reference)
        for _net, pin in _bus_pins(reference):
            output = (spec.get("digital_outputs") or {}).get(pin)
            if output:
                drivers.append((reference, pin, output["vol_max"]))
            inputs = (spec.get("digital_inputs") or {}).get(pin)
            if inputs:
                receivers.append((reference, pin, inputs))
    host_low = netlist.HOST_CONTRACT["max_host_low_level_v"]
    worst_low = max([record["value"] for _r, _p, record in drivers]
                    + [host_low])
    worst_vil = min(record["vil_max"]["factor_of_supply"] * supply_low
                    for _r, _p, record in receivers)
    worst_vih = max(record["vih_min"]["factor_of_supply"] * supply_low
                    for _r, _p, record in receivers)
    low_margin = worst_vil - worst_low
    high_margin = supply_low - worst_vih
    documents = _documents(*[record for _r, _p, record in drivers])
    for _r, _p, record in receivers:
        documents.extend(_documents(record["vil_max"], record["vih_min"]))
    documents = sorted(set(documents))
    return {
        "worst_low_level_v": worst_low,
        "strictest_vil_v": worst_vil,
        "strictest_vih_v": worst_vih,
        "supply_range_v": [supply_low, supply_high],
        "claims": [
            _claim("bus low-level noise margin", "V",
                   "how far below the strictest receiver's low threshold the "
                   "highest low level any driver may present sits",
                   low_margin, DERIVED, documents + ["design-source"],
                   _requirement("every receiver reads a low as a low",
                                ">=", 0.0)),
            _claim("bus high-level noise margin", "V",
                   "how far above the strictest receiver's high threshold "
                   "the pull-up carries the line at the lowest supply",
                   high_margin, DERIVED, documents + ["design-source"],
                   _requirement("every receiver reads a high as a high",
                                ">=", 0.0)),
        ],
    }


# ---------------------------------------------------------------------------
# supply
# ---------------------------------------------------------------------------

def board_current(parameters):
    """Peak board current, and whether any part contributed only a typical."""
    total = 0.0
    approximate = []
    for reference, part in sorted(netlist.PARTS.items()):
        if not part["mpn"]:
            continue
        spec = parameters["parts"][part["mpn"]]
        maximum = spec.get("supply_current_max_a")
        if maximum is not None and "value" in maximum:
            total += maximum["value"]
            continue
        typical = spec.get("supply_current_typ_a")
        if typical is None:
            continue
        total += typical["value"] * UNPUBLISHED_CURRENT_DERATING
        approximate.append(reference)
    for reference in netlist.PULL_UP_REFERENCES:
        total += (netlist.RAILS["3V3"]["max_v"]
                  / _spec(parameters, reference)["resistance_ohms"]["value"])
    return total, approximate


def evaluate_supply_current(parameters):
    total, approximate = board_current(parameters)
    connector = _spec(parameters, "J1")["contact_current_max_a"]
    knowledge = claim.EXACT if not approximate else claim.UPPER_BOUND
    assumptions = ([{"detail": "no maximum supply current is published for "
                     "%s; each is charged %g times its typical, which is "
                     "assumed to bound it"
                     % (", ".join(sorted(approximate)),
                        UNPUBLISHED_CURRENT_DERATING)}]
                   if approximate else [])
    return {
        "peak_current_a": total,
        "approximate_parts": approximate,
        "claim": _claim(
            "peak board supply current", "A",
            "every fitted part's largest published supply current with both "
            "pull-ups conducting, which is what the connector and the host "
            "have to carry",
            total, DERIVED,
            _documents(connector) + ["design-source"],
            _requirement("board current within the connector's contact "
                         "rating", "<=", connector["value"]),
            knowledge=knowledge, assumptions=assumptions),
    }


def evaluate_rail_range(parameters):
    """The rail each device sees, against the range it is specified over."""
    total, _approximate = board_current(parameters)
    damping = _spec(parameters, netlist.RAIL_DAMPING_REFERENCE)
    drop = total * damping["resistance_ohms"]["value"]
    rail_min = netlist.RAILS["3V3_IN"]["min_v"] - drop
    rail_max = netlist.RAILS["3V3_IN"]["max_v"]
    claims, violations = [], []
    for reference in sorted(netlist.PARTS):
        spec = _spec(parameters, reference)
        if not spec or not spec.get("supply_pins"):
            continue
        supply = spec["supply"]
        low = supply["characterised_min_v"]
        claims.append(_claim(
            "%s supply headroom above its characterised minimum" % reference,
            "V",
            "how far the rail at this device sits above the lowest supply "
            "its datasheet characterises it at, after the damping "
            "resistor's drop at the peak board current",
            rail_min - low["value"], DERIVED,
            _documents(low) + ["design-source"],
            _requirement("every device is inside its characterised supply "
                         "range", ">=", 0.0),
            scope_level="group"))
        if rail_min < low["value"]:
            violations.append({"reference": reference, "rail_v": rail_min,
                               "minimum_v": low["value"]})
        abs_max = supply.get("abs_max_v")
        if abs_max and "value" in abs_max:
            claims.append(_claim(
                "%s supply margin below its absolute maximum" % reference,
                "V",
                "how far the highest steady rail sits below the supply "
                "voltage the device is rated to survive",
                abs_max["value"] - rail_max, DERIVED,
                _documents(abs_max) + ["design-source"],
                _requirement("no device is taken past its absolute maximum "
                             "supply", ">=", 0.0),
                scope_level="group"))
    return {"rail_min_v": rail_min, "rail_max_v": rail_max,
            "damping_drop_v": drop, "claims": claims,
            "violations": violations}


def evaluate_back_feed(parameters):
    """What a live host can push into an unpowered pod through the bus.

    The pod carries the only pull-ups, so nothing on this board can
    source current into the bus when the connector's supply is absent. A
    host that fits its own pull-ups can: the current arrives through the
    pod's pull-ups and through whatever clamp a device has between its
    bus pin and its supply, which lifts the rail with it. The claims here
    are bounded current and the pin-to-supply excursion that comes with
    it - not absence.
    """
    host = netlist.HOST_CONTRACT
    _combined, pod_only = total_pull_up_ohms(parameters)
    per_line = host["supply_nominal_v"] * (1.0 + host["supply_tolerance"]) / (
        host["min_host_pullup_ohms"] + pod_only)
    total = per_line * len(netlist.BUS_NETS)
    claims, violations, unknown = [], [], []
    for reference in bus_devices():
        spec = _spec(parameters, reference)
        if not spec.get("supply_pins"):
            continue
        rating = spec.get("pin_current_max_a")
        if rating is None:
            unknown.append(reference)
            claims.append(_claim(
                "%s pin current during a mis-ordered mate" % reference, "A",
                "the current a host's pull-ups can push into this device's "
                "bus pins before the supply contact closes",
                None, DIRECT, ["design-source"],
                _requirement("injected current within the device's pin "
                             "current rating", "<=", 0.0),
                scope_level="group"))
        else:
            claims.append(_claim(
                "%s pin current during a mis-ordered mate" % reference, "A",
                "the current a host's pull-ups can push into this device's "
                "bus pins before the supply contact closes",
                total, DERIVED, _documents(rating) + ["design-source"],
                _requirement("injected current within the device's pin "
                             "current rating", "<=", rating["value"]),
                scope_level="group"))
            if total > rating["value"]:
                violations.append({"reference": reference,
                                   "current_a": total,
                                   "limit_a": rating["value"]})
        abs_max = spec.get("pin_abs_max") or {}
        if abs_max.get("relative_to") != "supply":
            continue
        # The clamp that carries the current sits between the pin and the
        # supply, so the pin stands one forward drop above the rail it is
        # lifting. Whether that drop stays inside the pin's rating is not
        # something either datasheet answers.
        claims.append(_claim(
            "%s bus pin excursion above its supply during a mis-ordered "
            "mate" % reference, "V",
            "how far the bus pin stands above the supply pin while the "
            "device's own clamp carries the host's pull-up current into an "
            "unpowered rail",
            None, DIRECT, _documents(abs_max.get("max_offset_v"))
            + ["design-source"],
            _requirement("bus pin within its absolute maximum relative to "
                         "the supply", "<=",
                         abs_max["max_offset_v"]["value"]),
            scope_level="group"))
    return {"injected_current_a": total, "claims": claims,
            "violations": violations, "unrated_devices": unknown}


# ---------------------------------------------------------------------------
# thermal
# ---------------------------------------------------------------------------

def board_dissipation_w(parameters):
    """Steady dissipation at the declared measurement rate."""
    total = 0.0
    supply = netlist.RAILS["3V3"]["max_v"]
    for reference, part in sorted(netlist.PARTS.items()):
        if not part["mpn"]:
            continue
        spec = parameters["parts"][part["mpn"]]
        record = (spec.get("average_supply_current_1hz_typ_a")
                  or spec.get("supply_current_max_a")
                  or spec.get("supply_current_typ_a"))
        if record is None or "value" not in record:
            continue
        total += record["value"] * supply
    # A pull-up only dissipates while the line it holds is low, and the
    # bus is only driven during a transaction.
    duty = _bus_duty_cycle(parameters)
    for reference in netlist.PULL_UP_REFERENCES:
        resistance = _spec(parameters, reference)["resistance_ohms"]["value"]
        total += supply * supply / resistance * duty
    return total


def _bus_duty_cycle(parameters):
    """Fraction of the second the bus spends carrying a transaction."""
    bits = 8 * 12
    period = bits / parameters["i2c"]["modes"]["standard"]["max_scl_hz"][
        "value"]
    return min(1.0, period * MEASUREMENTS_PER_SECOND)


def neck_conductance_w_per_k(layout_module):
    """Conduction along the isolation neck: substrate plus its four traces."""
    low, high = layout_module.NOTCH_Y_MM
    length_m = (high - low) * 1e-3
    substrate = (FR4_CONDUCTIVITY_W_PER_M_K
                 * (2.0 * layout_module.NECK_HALF_WIDTH_MM * 1e-3
                    * layout_module.BOARD_THICKNESS_MM * 1e-3) / length_m)
    copper_area = (len(layout_module.NECK_TRACKS)
                   * layout_module.NECK_TRACK_WIDTH_MM * 1e-3
                   * COPPER_THICKNESS_M)
    copper = COPPER_CONDUCTIVITY_W_PER_M_K * copper_area / length_m
    return substrate + copper, substrate, copper


def _surface_conductance(area_mm2):
    return STILL_AIR_COEFFICIENT_MIN_W_PER_M2_K * 2.0 * area_mm2 * 1e-6


def evaluate_thermal_isolation(parameters, layout_module):
    """Steady rise at the humidity sensor from the board's own dissipation.

    Two nodes: the main board, where everything that dissipates is, and
    the island the sensor sits on. They exchange heat only through the
    neck, and each loses heat to still air from both faces. The island's
    rise is what the sensor reads as ambient error.
    """
    low, high = layout_module.NOTCH_Y_MM
    width = 2.0 * layout_module.BOARD_HALF_WIDTH_MM
    main_area = width * low
    island_area = width * (layout_module.BOARD_LENGTH_MM - high)
    neck, _substrate, _copper = neck_conductance_w_per_k(layout_module)
    main_to_air = _surface_conductance(main_area)
    island_to_air = _surface_conductance(island_area)
    power = board_dissipation_w(parameters)
    # Series-parallel: the island's branch is the neck then its own air.
    branch = 1.0 / (1.0 / neck + 1.0 / island_to_air)
    board_rise = power / (main_to_air + branch)
    island_rise = board_rise * branch / island_to_air
    spec = _spec(parameters, netlist.THERMAL_VICTIM)
    accuracy = spec["accuracy"]["temperature_typ_c"]
    limit = accuracy["value"] * THERMAL_RISE_FRACTION_OF_ACCURACY
    return {
        "board_dissipation_w": power,
        "neck_conductance_w_per_k": neck,
        "board_rise_k": board_rise,
        "island_rise_k": island_rise,
        "accuracy_c": accuracy["value"],
        "limit_k": limit,
        "branch_w_per_k": branch,
        "claim": _claim(
            "steady rise above ambient at the humidity sensor", "K",
            "how far the board's own dissipation lifts the isolated island "
            "the temperature and humidity sensor sits on, in still air at "
            "one measurement per second",
            island_rise, DERIVED,
            _documents(accuracy) + ["design-source"],
            _requirement("self-heating small against the sensor's own "
                         "accuracy", "<=", limit),
            knowledge=claim.UPPER_BOUND, scope_level="group",
            assumptions=[{"detail": "still air removes at least %.1f W/m2K "
                          "from both faces; less cooling would be more rise, "
                          "so the number bounds the real one from above"
                          % STILL_AIR_COEFFICIENT_MIN_W_PER_M2_K},
                         {"detail": "the board and the island are each one "
                          "isothermal node"}],
            omissions=[{"detail": "heat conducted up the cable from the host "
                        "is not modelled; it is a property of the host, not "
                        "of this board"}],
            phenomenon="functional_behavior"),
    }


def evaluate_all(layout_module=None):
    parameters = load_parameters()
    results = {
        "address_uniqueness": evaluate_address_uniqueness(parameters),
        "sink_current": evaluate_sink_current(parameters),
        "rise_time": evaluate_rise_time(parameters),
        "bus_capacitance": evaluate_bus_capacitance(
            parameters, layout_module),
        "logic_levels": evaluate_logic_levels(parameters),
        "supply_current": evaluate_supply_current(parameters),
        "rail_range": evaluate_rail_range(parameters),
        "back_feed": evaluate_back_feed(parameters),
    }
    if layout_module is not None:
        results["thermal_isolation"] = evaluate_thermal_isolation(
            parameters, layout_module)
    return results


def claims(results):
    found = []
    for entry in results.values():
        if isinstance(entry, dict):
            if "claim" in entry:
                found.append(entry["claim"])
            found.extend(entry.get("claims", []))
        elif isinstance(entry, list):
            for item in entry:
                if isinstance(item, dict) and "claim" in item:
                    found.append(item["claim"])
    return found


def summarise(results):
    rows = []
    for record in claims(results):
        rows.append({
            "identity": record["scope"]["identity"],
            "knowledge": record["knowledge"],
            "value": record["quantity"].get("value"),
            "units": record["units"],
            "requirement": (record["requirement"] or {}).get("name"),
            "verdict": claim.verdict(record)["result"],
        })
    return rows


if __name__ == "__main__":
    from . import layout

    for row in summarise(evaluate_all(layout)):
        value = row["value"]
        sys.stdout.write("%-8s %-11s %-14s %s\n" % (
            row["verdict"], row["knowledge"],
            "-" if value is None else "%.6g %s" % (value, row["units"]),
            row["identity"]))
