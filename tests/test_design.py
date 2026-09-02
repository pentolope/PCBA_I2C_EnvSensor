from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from design import (build, cost, evidence, floorplan, ksym, layout,  # noqa
                    libraries, netlist, physical, rules, schematic,
                    simulation)

TOOLKIT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
if TOOLKIT not in sys.path:
    sys.path.insert(0, TOOLKIT)

from pcbqa import claim, routing_record  # noqa: E402

MANIFEST_PATH = os.path.join(REPO_ROOT, "board", "manifest.json")


def manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class DesignSource(unittest.TestCase):
    def test_pin_assignment_is_unique(self):
        mapping = netlist.pin_to_net()
        self.assertEqual(len(mapping),
                         sum(len(pins) for pins in netlist.NETS.values()))

    def test_every_symbol_pin_is_connected_or_declared_no_connect(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        mapping = netlist.pin_to_net()
        for reference, part in sorted(netlist.PARTS.items()):
            declared = set(library.pins(part["lib_id"]))
            used = {ref.split(".", 1)[1] for ref in mapping
                    if ref.split(".", 1)[0] == reference}
            used |= {ref.split(".", 1)[1] for ref in netlist.NO_CONNECT
                     if ref.split(".", 1)[0] == reference}
            self.assertEqual(used, declared, reference)

    def test_every_address_strap_pin_sits_on_a_rail(self):
        mapping = netlist.pin_to_net()
        for reference, strap in netlist.ADDRESS_STRAPS.items():
            if strap["pin"] is None:
                continue
            net = mapping["%s.%s" % (reference, strap["pin"])]
            self.assertIn(net, strap["addresses"], reference)

    def test_the_connector_carries_exactly_the_declared_functions(self):
        mapping = netlist.pin_to_net()
        connector = {number: mapping["J1.%s" % number]
                     for number in ("1", "2", "3", "4")}
        self.assertEqual(
            sorted(connector.values()),
            sorted(netlist.CONNECTOR_FUNCTION_NETS["J1"].values()))

    def test_the_pod_carries_one_pull_up_for_each_bus_line(self):
        self.assertEqual(sorted(netlist.PULL_UP_REFERENCES.values()),
                         sorted(netlist.BUS_NETS))


class GeneratedSchematic(unittest.TestCase):
    def test_committed_schematic_matches_the_generator(self):
        self.assertEqual(read(build.schematic_path()),
                         build.generate_schematic_text())

    def test_generation_is_deterministic(self):
        self.assertEqual(build.generate_schematic_text(),
                         build.generate_schematic_text())

    def test_exported_netlist_matches_the_design_source(self):
        from design import sexpr

        out = os.path.join(REPO_ROOT, "out", "netlist-parity.net")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--output",
                        out, build.schematic_path()],
                       check=True, capture_output=True)
        tree = sexpr.parse(read(out))
        exported = {}
        for net in sexpr.find_all(sexpr.find(tree, "nets"), "net"):
            name = str(sexpr.find(net, "name")[1])
            pins = set()
            for node in sexpr.find_all(net, "node"):
                reference = str(sexpr.find(node, "ref")[1])
                pin = str(sexpr.find(node, "pin")[1])
                pins.add("%s.%s" % (reference, pin))
            exported[name] = pins
        for name, pin_refs in netlist.NETS.items():
            declared = {ref for ref in pin_refs
                        if not ref.startswith("#")}
            self.assertEqual(exported.get(name), declared, name)


class GeneratedLibraries(unittest.TestCase):
    def test_committed_libraries_match_the_generator(self):
        for path, text in libraries.artifacts().items():
            self.assertEqual(read(path), text, path)

    def test_the_generated_symbol_carries_the_declared_pins(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        pins = library.pins("%s:%s" % (netlist.LIBRARY_NAME,
                                       libraries.OPT3001_SYMBOL_NAME))
        self.assertEqual(sorted(pins),
                         sorted(number for number, _n, _k, _s
                                in libraries.OPT3001_PINS))

    def test_the_generated_footprint_matches_the_recorded_land_pattern(self):
        recorded = rules.load_parameters()["parts"]["OPT3001DNPR"][
            "land_pattern"]["recommended"]
        generated = {number: (x, y, w, h)
                     for number, x, y, w, h in libraries.opt3001_pads()}
        self.assertEqual(sorted(generated),
                         sorted(pad["number"] for pad in recorded))
        for pad in recorded:
            x, y, w, h = generated[pad["number"]]
            self.assertAlmostEqual(x, pad["x"], places=4)
            self.assertAlmostEqual(y, pad["y"], places=4)
            self.assertAlmostEqual(w, pad["w"], places=4)
            self.assertAlmostEqual(h, pad["h"], places=4)


class GeneratedBoard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pcbnew

        cls.pcbnew = pcbnew
        cls.board = pcbnew.LoadBoard(layout.BOARD_PATH)
        cls.parameters = rules.load_parameters()

    def _design_xy(self, position):
        return (self.pcbnew.ToMM(position.x) - layout.ORIGIN_MM[0],
                layout.ORIGIN_MM[1] - self.pcbnew.ToMM(position.y))

    def _footprint(self, reference):
        return self.board.FindFootprintByReference(reference)

    def _body_box(self, reference):
        """The part's own body, from its datasheet, not its silkscreen."""
        spec = self.parameters["parts"][netlist.PARTS[reference]["mpn"]]
        width, height = spec["package"]["body_mm"]["value"]
        footprint = self._footprint(reference)
        centre = self._design_xy(footprint.GetPosition())
        angle = math.radians(footprint.GetOrientationDegrees())
        half_x = (abs(width * math.cos(angle))
                  + abs(height * math.sin(angle))) / 2.0
        half_y = (abs(width * math.sin(angle))
                  + abs(height * math.cos(angle))) / 2.0
        return (centre[0] - half_x, centre[1] - half_y,
                centre[0] + half_x, centre[1] + half_y)

    @staticmethod
    def _overlaps(first, second):
        return not (first[2] <= second[0] or second[2] <= first[0]
                    or first[3] <= second[1] or second[3] <= first[1])

    def _height_mm(self, reference):
        part = netlist.PARTS[reference]
        if not part["mpn"]:
            return 0.0
        spec = self.parameters["parts"].get(part["mpn"])
        if not spec:
            return 0.0
        return spec["package"]["height_max_mm"]["value"]

    def test_every_on_board_part_is_placed(self):
        placed = {fp.GetReference() for fp in self.board.GetFootprints()}
        declared = {reference for reference, part in netlist.PARTS.items()
                    if part["on_board"] and part["footprint"]}
        self.assertEqual(placed, declared)

    def test_generation_is_byte_reproducible(self):
        import tempfile

        with tempfile.TemporaryDirectory() as scratch:
            first = layout.write(os.path.join(scratch, "a.kicad_pcb"))
            second = layout.write(os.path.join(scratch, "b.kicad_pcb"))
            self.assertEqual(read(first), read(second))

    def test_the_board_carries_one_ground_plane(self):
        planes = [zone for zone in self.board.Zones()
                  if zone.GetNetname() == "GND"]
        self.assertEqual(len(planes), 1)
        self.assertEqual(self.board.GetLayerName(planes[0].GetLayer()),
                         "B.Cu")

    def test_the_ground_plane_is_one_connected_region(self):
        plane = next(zone for zone in self.board.Zones()
                     if zone.GetNetname() == "GND")
        filled = plane.GetFilledPolysList(plane.GetFirstLayer())
        self.assertEqual(filled.OutlineCount(), 1)

    def test_only_the_declared_lanes_cross_the_isolation_neck(self):
        low, high = layout.NOTCH_Y_MM
        middle = (low + high) / 2.0
        crossing = {}
        for track in self.board.GetTracks():
            if track.Type() == self.pcbnew.PCB_VIA_T:
                continue
            start = self._design_xy(track.GetStart())
            end = self._design_xy(track.GetEnd())
            if min(start[1], end[1]) <= middle <= max(start[1], end[1]):
                crossing.setdefault(track.GetNetname(), []).append(
                    round(self.pcbnew.ToMM(track.GetWidth()), 4))
        self.assertEqual(sorted(crossing),
                         sorted(name for name, _x in layout.NECK_TRACKS))
        for net, widths in crossing.items():
            self.assertEqual(widths, [layout.NECK_TRACK_WIDTH_MM], net)

    def test_no_pour_reaches_the_isolated_island(self):
        low, _high = layout.NOTCH_Y_MM
        for zone in self.board.Zones():
            for layer in zone.GetLayerSet().CuStack():
                box = zone.GetFilledPolysList(layer).BBox()
                top = layout.ORIGIN_MM[1] - self.pcbnew.ToMM(box.GetTop())
                self.assertLess(top, low, zone.GetNetname())

    def test_no_copper_under_the_humidity_sensor_but_its_own_pads(self):
        sensor = self._footprint(netlist.THERMAL_VICTIM)
        body = self._body_box(netlist.THERMAL_VICTIM)
        pad_boxes = []
        for pad in sensor.Pads():
            box = pad.GetBoundingBox()
            low = self._design_xy(
                self.pcbnew.VECTOR2I(box.GetLeft(), box.GetBottom()))
            high = self._design_xy(
                self.pcbnew.VECTOR2I(box.GetRight(), box.GetTop()))
            pad_boxes.append((low[0], low[1], high[0], high[1]))
        for track in self.board.GetTracks():
            if track.Type() == self.pcbnew.PCB_VIA_T:
                start = end = self._design_xy(track.GetPosition())
            else:
                start = self._design_xy(track.GetStart())
                end = self._design_xy(track.GetEnd())
            reach = self.pcbnew.ToMM(track.GetWidth()) / 2.0
            box = (min(start[0], end[0]) - reach,
                   min(start[1], end[1]) - reach,
                   max(start[0], end[0]) + reach,
                   max(start[1], end[1]) + reach)
            if not self._overlaps(box, body):
                continue
            self.assertTrue(
                any(self._overlaps(box, pad) for pad in pad_boxes),
                "copper crosses the sensor body")

    def test_nothing_taller_stands_in_the_light_sensor_field(self):
        spec = self.parameters["parts"][netlist.PARTS["U3"]["mpn"]]
        ratio = spec["sensing_opening"]["obstruction_distance_per_height"][
            "value"]
        sensor = self._footprint("U3")
        centre = self._design_xy(sensor.GetPosition())
        for footprint in self.board.GetFootprints():
            reference = footprint.GetReference()
            if reference == "U3":
                continue
            height = self._height_mm(reference)
            if height <= 0.0:
                continue
            other = self._design_xy(footprint.GetPosition())
            distance = math.hypot(other[0] - centre[0], other[1] - centre[1])
            self.assertGreaterEqual(distance, ratio * height, reference)

    def test_every_sensing_opening_is_clear_of_other_parts(self):
        for reference in netlist.EXPOSED_SENSORS:
            opening = self._body_box(reference)
            for footprint in self.board.GetFootprints():
                other = footprint.GetReference()
                if other == reference or not netlist.PARTS[other]["mpn"]:
                    continue
                self.assertFalse(
                    self._overlaps(self._body_box(other), opening),
                    "%s covers %s's sensing opening" % (other, reference))

    def test_the_humidity_sensor_is_the_farthest_part_from_the_connector(self):
        connector = self._design_xy(self._footprint("J1").GetPosition())
        distances = {}
        for footprint in self.board.GetFootprints():
            position = self._design_xy(footprint.GetPosition())
            distances[footprint.GetReference()] = math.hypot(
                position[0] - connector[0], position[1] - connector[1])
        farthest = max(distances, key=distances.get)
        self.assertEqual(farthest, netlist.THERMAL_VICTIM)

    def test_cable_strain_is_reacted_by_through_hole_retention(self):
        connector = self._footprint("J1")
        for pad in connector.Pads():
            self.assertEqual(pad.GetAttribute(),
                             self.pcbnew.PAD_ATTRIB_PTH,
                             pad.GetNumber())

    def test_pin_one_is_marked_in_silkscreen(self):
        texts = [item for item in self.board.GetDrawings()
                 if item.Type() == self.pcbnew.PCB_TEXT_T
                 and self.board.GetLayerName(item.GetLayer()) == "F.Silkscreen"]
        self.assertTrue(any(item.GetText() == "1" for item in texts))

    def test_the_through_hole_count_is_within_the_declared_allowance(self):
        through_hole = 0
        for footprint in self.board.GetFootprints():
            if any(pad.GetAttribute() == self.pcbnew.PAD_ATTRIB_PTH
                   for pad in footprint.Pads()):
                through_hole += 1
        self.assertLessEqual(
            through_hole,
            netlist.ASSEMBLY_POLICY["max_through_hole_soldered_parts"])

    def test_every_footprint_covers_its_recorded_terminals(self):
        for reference, part in sorted(netlist.PARTS.items()):
            if not part["mpn"]:
                continue
            spec = self.parameters["parts"][part["mpn"]]
            terminals = spec["land_pattern"].get("terminals")
            if not terminals:
                continue
            footprint = self._footprint(reference)
            pads = {}
            for pad in footprint.Pads():
                if pad.GetNumber():
                    pads.setdefault(pad.GetNumber(), []).append(pad)
            for terminal in terminals:
                self.assertIn(terminal["number"], pads,
                              "%s pad %s" % (reference, terminal["number"]))


class ElectricalRules(unittest.TestCase):
    #: Every claim this board cannot decide, and nothing else. Each is a
    #: mis-ordered mating question no datasheet in evidence answers.
    OPEN = {
        "U2 pin current during a mis-ordered mate",
        "U1 bus pin excursion above its supply during a mis-ordered mate",
        "U2 bus pin excursion above its supply during a mis-ordered mate",
    }

    @classmethod
    def setUpClass(cls):
        cls.results = rules.evaluate_all(layout)
        cls.rows = rules.summarise(cls.results)

    def test_no_claim_fails(self):
        failed = [row for row in self.rows if row["verdict"] == "FAIL"]
        self.assertEqual(failed, [])

    def test_the_undecided_claims_are_exactly_the_known_open_ones(self):
        unknown = {row["identity"] for row in self.rows
                   if row["verdict"] != "PASS"}
        self.assertEqual(unknown, self.OPEN)

    def test_every_claim_carries_a_requirement(self):
        for record in rules.claims(self.results):
            self.assertIsNotNone(record["requirement"],
                                 record["scope"]["identity"])

    def test_an_undecided_claim_carries_no_number(self):
        for record in rules.claims(self.results):
            if record["knowledge"] == claim.UNKNOWN:
                self.assertEqual(record["quantity"], {})

    def test_no_two_fitted_devices_answer_the_same_address(self):
        addresses = self.results["address_uniqueness"]["addresses"]
        self.assertEqual(len(set(addresses.values())), len(addresses))
        self.assertEqual(self.results["address_uniqueness"]["violations"], [])

    def test_the_pod_carries_the_whole_bus_within_the_capacitance_budget(self):
        entry = self.results["bus_capacitance"]
        for net, value in entry["device_f"].items():
            self.assertLess(value + entry["track_f"].get(net, 0.0),
                            entry["budget_f"], net)

    def test_the_rise_time_holds_in_every_mode_the_board_declares(self):
        modes = {row["mode"] for row in self.results["rise_time"]}
        self.assertEqual(modes,
                         set(netlist.HOST_CONTRACT["declared_bus_modes"]))
        for row in self.results["rise_time"]:
            self.assertLessEqual(row["rise_time_s"], row["limit_s"],
                                 row["mode"])

    def test_the_sink_current_stays_inside_every_declared_low_level(self):
        self.assertEqual(self.results["sink_current"]["violations"], [])

    def test_self_heating_is_small_against_the_sensor_accuracy(self):
        entry = self.results["thermal_isolation"]
        self.assertLessEqual(entry["island_rise_k"], entry["limit_k"])

    def test_the_isolation_neck_is_the_only_conduction_path_modelled(self):
        neck, substrate, copper = rules.neck_conductance_w_per_k(layout)
        self.assertAlmostEqual(neck, substrate + copper)
        self.assertGreater(copper, substrate)


class FrozenEvidence(unittest.TestCase):
    def test_index_matches_the_committed_documents(self):
        self.assertEqual(evidence.verify(), [])

    def test_index_is_current(self):
        self.assertEqual(evidence.load_index(), evidence.compute_index())

    def test_every_cited_document_is_frozen(self):
        known = set(evidence.load_index()["documents"])
        parameters = rules.load_parameters()

        def walk(node):
            if isinstance(node, dict):
                document = node.get("document")
                if isinstance(document, str):
                    self.assertIn(document, known)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(parameters)

    def test_every_parameter_record_names_a_selected_part(self):
        selected = {part["mpn"] for part in netlist.PARTS.values()
                    if part["mpn"]}
        self.assertEqual(set(rules.load_parameters()["parts"]), selected)

    def test_every_frozen_document_applies_to_a_selected_part(self):
        selected = {part["mpn"] for part in netlist.PARTS.values()
                    if part["mpn"]}
        for name, entry in evidence.load_index()["documents"].items():
            applies = set(entry["applies_to"])
            self.assertTrue(applies & selected, name)


class BomAndSupply(unittest.TestCase):
    def test_every_bom_part_is_in_the_frozen_catalogue(self):
        catalogue = cost.load_catalog()["parts"]
        for code in cost.line_items():
            self.assertIn(code, catalogue)

    def test_catalogue_entries_match_the_selected_parts(self):
        catalogue = cost.load_catalog()["parts"]
        for reference, part in netlist.PARTS.items():
            if not part["lcsc"]:
                continue
            entry = catalogue[part["lcsc"]]
            self.assertEqual(entry["mpn"], part["mpn"], reference)
            self.assertEqual(entry["manufacturer"], part["manufacturer"],
                             reference)

    def test_the_catalogue_carries_no_part_the_board_does_not_use(self):
        self.assertEqual(set(cost.load_catalog()["parts"]),
                         set(cost.line_items()))

    def test_cost_decreases_with_build_quantity(self):
        totals = [cost.bom_cost(quantity)["per_board_usd"]
                  for quantity in cost.DEFAULT_BUILD_QUANTITIES]
        self.assertEqual(totals, sorted(totals, reverse=True))

    def test_stock_supports_a_production_build(self):
        limits = cost.stock_limited_boards()
        self.assertGreaterEqual(min(limits.values()),
                                max(cost.DEFAULT_BUILD_QUANTITIES))


class FabricationInputs(unittest.TestCase):
    def test_the_declared_minima_are_what_the_layout_uses(self):
        with open(os.path.join(REPO_ROOT, "fab", "requirements.json"),
                  encoding="utf-8") as handle:
            requirements = json.load(handle)
        self.assertLessEqual(requirements["min_space_mm"],
                             layout.CLEARANCE_MM)
        self.assertLessEqual(requirements["min_track_mm"],
                             layout.NECK_TRACK_WIDTH_MM)
        self.assertLessEqual(requirements["min_drill_mm"],
                             layout.VIA_DRILL_MM)
        self.assertLessEqual(requirements["min_via_diameter_mm"],
                             layout.VIA_DIAMETER_MM)

    def test_the_selection_is_feasible_and_rejects_nothing(self):
        with open(os.path.join(REPO_ROOT, "fab", "selection.json"),
                  encoding="utf-8") as handle:
            selection = json.load(handle)
        self.assertTrue(selection["feasible"])
        self.assertEqual(selection["rejections"], [])

    def test_the_frozen_physical_inputs_still_agree_with_the_catalog(self):
        self.assertEqual(physical.verify(), [])

    def test_the_frozen_physical_inputs_are_regenerable(self):
        with open(physical.PHYSICAL_PATH, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), physical.resolve())

    def test_the_frozen_dielectric_is_regenerable(self):
        with open(physical.DIELECTRIC_PATH, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle),
                             physical.highest_dielectric_constant())

    def test_the_layer_count_matches_the_declared_stackup(self):
        with open(os.path.join(REPO_ROOT, "fab", "requirements.json"),
                  encoding="utf-8") as handle:
            requirements = json.load(handle)
        self.assertEqual(len(manifest()["stackup"]["expected"]),
                         requirements["copper_layers"])


class SimulationInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.declared = manifest()["simulation"]["stages"]

    def test_every_declared_scenario_exists_and_is_current(self):
        simulation.write()
        for stage, paths in self.declared.items():
            for relative in paths:
                self.assertTrue(os.path.isfile(
                    os.path.join(REPO_ROOT, relative)), relative)

    def test_the_generator_is_deterministic(self):
        parameters = simulation.parameters()
        first = simulation.rail_mating_scenario(parameters)
        second = simulation.rail_mating_scenario(parameters)
        self.assertEqual(first, second)

    def test_every_required_stage_is_declared(self):
        required = manifest()["simulation"]["required_stages"]
        self.assertEqual(sorted(required), sorted(self.declared))

    def test_thresholds_come_from_the_frozen_parameters(self):
        parameters = simulation.parameters()
        scenario = simulation.receiver_high_level_scenario(parameters)
        threshold = scenario["measurements"][0]["assertion"]["value"]
        expected = (simulation.receiver_vih_factor(parameters)
                    * netlist.RAILS["3V3"]["min_v"])
        self.assertAlmostEqual(threshold, expected)

    def test_passive_values_come_from_the_frozen_parameters(self):
        parameters = simulation.parameters()
        scenario = simulation.rail_mating_scenario(parameters)
        values = {element["name"]: element.get("value")
                  for element in scenario["elements"]}
        self.assertAlmostEqual(values["RDAMP"],
                               simulation.rail_damping_ohms(parameters))
        self.assertAlmostEqual(values["CBULK"],
                               simulation.bulk_capacitance_f(parameters))

    def test_every_ideal_element_declares_what_it_stands_in_for(self):
        parameters = simulation.parameters()
        for scenario in (simulation.bus_rise_time_scenario(parameters),
                         simulation.receiver_high_level_scenario(parameters),
                         simulation.rail_mating_scenario(parameters)):
            named = {element["name"] for element in scenario["elements"]}
            self.assertEqual(set(scenario["assumptions"]), named,
                             scenario["name"])

    def test_the_extracted_model_is_referenced_by_its_manifest_alias(self):
        aliases = set(manifest()["simulation"]["extracted_models"]["paths"])
        self.assertIn(simulation.EXTRACTED_MODEL_ALIAS, aliases)
        parameters = simulation.parameters()
        scenario = simulation.rail_mating_scenario(
            parameters, simulation.EXTRACTED_MODEL_ALIAS)
        models = {element["model"] for element in scenario["elements"]
                  if element["kind"] == "model_instance"}
        self.assertEqual(models, {simulation.EXTRACTED_MODEL_ALIAS})


class DeclaredContracts(unittest.TestCase):
    def test_manifest_declares_the_generated_sources(self):
        sources = manifest()["sources"]
        self.assertEqual(sources["schematic"],
                         os.path.basename(build.schematic_path()))
        self.assertEqual(sources["project"],
                         os.path.basename(build.project_path()))
        self.assertEqual(sources["pcb"],
                         os.path.basename(layout.BOARD_PATH))

    def test_the_connector_contract_matches_the_netlist(self):
        mapping = netlist.pin_to_net()
        for contract in manifest()["connector_contracts"]:
            reference = contract["reference"]
            for pin, expected in contract["pin_map"].items():
                self.assertEqual(mapping.get("%s.%s" % (reference, pin)),
                                 expected, "%s.%s" % (reference, pin))

    def test_the_routing_acceptance_set_excludes_artifact_gates(self):
        acceptance = set(manifest()["routing"]["acceptance_gates"])
        artifact_gates = {"ARCH.CONTENTS", "ARCH.PROVENANCE",
                          "BOM.NATIVE_PARITY", "CPL.NATIVE_PARITY",
                          "STACK.GERBER_PARITY", "PROV.REPORT_FRESHNESS"}
        self.assertEqual(acceptance & artifact_gates, set())

    def test_every_mandatory_gate_passed_in_the_last_validation(self):
        with open(os.path.join(REPO_ROOT, "generated", "release",
                               "validation.json"), encoding="utf-8") as handle:
            report = json.load(handle)
        statuses = {gate["gate"]: gate["status"]
                    for gate in report["gates"]}
        for gate in manifest()["release_profile"]["mandatory_gates"]:
            self.assertEqual(statuses.get(gate), "PASS", gate)

    def test_the_declared_clearance_floor_is_what_a_land_pattern_needs(self):
        floor = manifest()["checks"]["drc"]["constraint_floor"]["rules"][
            "min_clearance"]
        self.assertEqual(floor, layout.CLEARANCE_MM)
        self.assertLess(layout.CLEARANCE_MM, layout.ROUTED_CLEARANCE_MM)


class DeclaredFloorplan(unittest.TestCase):
    def test_committed_intent_matches_the_generator(self):
        with open(floorplan.INTENT_PATH, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle),
                             floorplan.intent(rules.load_parameters()))

    def test_every_placed_part_belongs_to_a_declared_block(self):
        declared = set()
        for block in floorplan.intent(rules.load_parameters())["blocks"]:
            declared.update(block["refs"])
        placed = {reference for reference, part in netlist.PARTS.items()
                  if part["on_board"] and part["footprint"]
                  and not reference.startswith(("TP", "H"))}
        self.assertEqual(placed, declared)

    def test_the_board_grades_clean_against_the_declared_intent(self):
        from pcbqa import krt

        resolved = krt.resolve()
        completed = subprocess.run(
            [sys.executable,
             os.path.join(resolved["path"], "py_tools", "check_floorplan.py"),
             layout.BOARD_PATH, "--intent", floorplan.INTENT_PATH],
            capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout[-2000:])


class RoutingProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, "generated", "routing.json"),
                  encoding="utf-8") as handle:
            cls.record = json.load(handle)

    def test_record_satisfies_the_toolkit_contract(self):
        routing_record.validate(self.record)

    def test_a_candidate_was_accepted(self):
        self.assertIsNotNone(self.record["accepted_attempt"])

    def test_every_attempt_started_from_the_same_source(self):
        for attempt in self.record["attempts"]:
            self.assertEqual(attempt["source_sha256"],
                             self.record["source_sha256"])

    def test_every_post_router_transform_is_declared(self):
        for attempt in self.record["attempts"]:
            for stage in attempt["stages"]:
                if stage["produced_by"] != routing_record.TRANSFORM:
                    continue
                self.assertTrue(stage["transform"].strip())
                self.assertIn("effects", stage)

    def test_the_planes_and_lanes_were_not_left_to_the_router(self):
        context = self.record["context"]
        self.assertNotIn("GND", context["routed_nets"])
        self.assertEqual(set(context["generated_nets"]),
                         {name for name, _x in layout.NECK_TRACKS})


class TestSuiteIsWhole(unittest.TestCase):
    def test_every_declared_test_runs(self):
        source = read(os.path.abspath(__file__))
        declared = {line.split("(")[0].strip()[len("def "):]
                    for line in source.splitlines()
                    if line.strip().startswith("def test_")}
        loaded = set()
        for suite in unittest.defaultTestLoader.loadTestsFromModule(
                sys.modules[__name__]):
            for case in suite:
                loaded.add(case.id().rsplit(".", 1)[1])
        self.assertEqual(declared, loaded)


if __name__ == "__main__":
    unittest.main()
