from __future__ import annotations

import json
import math
import os
import sys
import uuid

from . import ksym, netlist, sexpr

_TOOLKIT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest")
if _TOOLKIT not in sys.path:
    sys.path.insert(0, _TOOLKIT)

from pcbqa import headless  # noqa: E402

headless.suppress_blocking_ui()

import pcbnew  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD_PATH = os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_pcb")

FOOTPRINT_SEARCH_PATHS = (
    os.path.join(REPO_ROOT, "library"),
    "/usr/share/kicad/footprints",
)

ORIGIN_MM = (100.0, 100.0)

with open(os.path.join(REPO_ROOT, "fab", "requirements.json"),
          encoding="utf-8") as _handle:
    BOARD_THICKNESS_MM = json.load(_handle)["board_thickness_mm"]

BOARD_HALF_WIDTH_MM = 9.0
BOARD_LENGTH_MM = 40.0
NOTCH_Y_MM = (24.0, 32.0)
NECK_HALF_WIDTH_MM = 1.5
NECK_ROOT_FILLET_MM = 1.0

EDGE_WIDTH_MM = 0.1
TRACK_WIDTH_MM = 0.25
NECK_TRACK_WIDTH_MM = 0.2
#: The tightest metal-to-metal gap any selected part's land
#: pattern asks for. OPT3001 DNP0006A and the HLGA-10 both
#: place pads 0.125 mm apart; JLCPCB's published floor for
#: this process is 0.1 mm.
CLEARANCE_MM = 0.125
#: What the search is held to. The floor above exists only because
#: two land patterns need it; routed copper is not one of them.
ROUTED_CLEARANCE_MM = 0.2
EDGE_CLEARANCE_MM = 0.3
VIA_DIAMETER_MM = 0.6
VIA_DRILL_MM = 0.3
STITCH_TRACK_WIDTH_MM = 0.4
STITCH_GAP_MM = 0.35

ZONE_INSET_MM = 0.5
ZONE_TOP_Y_MM = 23.0

#: One trace per island net, spread across the neck. GND sits between the
#: two bus lines.
NECK_TRACKS = (("3V3", -1.05), ("GND", -0.35), ("SDA", 0.35),
               ("SCL", 1.05))

#: Where each island net leaves the main board. The router reaches
#: these pads; everything above them is generated.
NECK_ENTRY_Y_MM = 23.2
NECK_EXIT_Y_MM = 33.2

CONNECTOR_PIN1_MM = (-3.0, 6.5)

#: Where the neck's four lanes leave the main board. The test points sit
#: on that line so the router has a pad to reach and a probe lands on
#: exactly what crosses the neck.
NECK_ENTRY_PAD_Y_MM = 22.3
#: Where the host-interface parts stop and the sensors begin. The
#: line separates the two groups; nothing sits across it.
CONNECTOR_ZONE_TOP_MM = 14.0

#: Every pose, stated here rather than searched for.
#:
#: The KiCad Routing Tools placer was driven from the declared floorplan
#: intent in board/floorplan.json (place_seed over five seeds, then
#: place_optimize, then place_route_loop). Its best candidate graded clean
#: against that intent and still could not be routed on the signal layer
#: alone: single-layer routing failed on SDA, SCL and GND, five rounds of
#: router-guided re-quench were all rejected, and the two-layer route it
#: does complete needs six vias and drives the router to shrink one below
#: the fabrication floor this board declares. The intent schema and the
#: quench score both price airwire length and crossings; neither can say
#: "the bottom layer is a ground plane and the bus does not leave the top
#: one", which is the constraint that decides this board.
PLACEMENT = {
    "J1": CONNECTOR_PIN1_MM + (0.0,),
    "D2": (-3.4, 11.0, 0.0),
    "R3": (-1.0, 9.4, 90.0),
    "D1": (2.6, 9.5, 0.0),
    "H1": (-7.0, 12.5, 0.0),
    "H2": (7.0, 12.5, 0.0),
    "C1": (-1.0, 12.4, 90.0),
    "R1": (0.6, 16.5, 90.0),
    "R2": (2.0, 16.5, 90.0),
    "U2": (-4.6, 19.2, 0.0),
    "C3": (-7.0, 19.2, 90.0),
    "U3": (3.2, 19.2, 0.0),
    "C4": (6.0, 19.2, 90.0),
    "TP1": (-4.5, NECK_ENTRY_PAD_Y_MM, 0.0),
    "TP2": (-1.5, NECK_ENTRY_PAD_Y_MM, 0.0),
    "TP3": (1.5, NECK_ENTRY_PAD_Y_MM, 0.0),
    "TP4": (4.5, NECK_ENTRY_PAD_Y_MM, 0.0),
    "U1": (0.0, 36.0, 180.0),
    "C2": (-2.6, 34.6, 0.0),
}

#: What the declared intent locks, which for a stated placement is
#: everything: the grade in board/floorplan.json judges the placement, it
#: does not produce it.
LOCKED_REFERENCES = tuple(sorted(PLACEMENT))


#: Everything at or above this line is on the far side of the neck.
ISLAND_Y_MM = NOTCH_Y_MM[0]


def poses():
    return dict(PLACEMENT)


def to_board(x_mm, y_mm):
    return (ORIGIN_MM[0] + x_mm, ORIGIN_MM[1] - y_mm)


def _vector(x_mm, y_mm):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def _point(x_mm, y_mm):
    return _vector(*to_board(x_mm, y_mm))


def outline_vertices():
    half = BOARD_HALF_WIDTH_MM
    low, high = NOTCH_Y_MM
    neck = NECK_HALF_WIDTH_MM
    return [
        (-half, 0.0), (half, 0.0), (half, low),
        (neck, low), (neck, high), (half, high),
        (half, BOARD_LENGTH_MM), (-half, BOARD_LENGTH_MM),
        (-half, high), (-neck, high), (-neck, low), (-half, low),
    ]


#: Indices into outline_vertices() where the board turns through 270
#: degrees. A router bit cannot cut a sharp inside corner, and a sharp one
#: would concentrate bending stress at the root of the isolation neck.
NECK_ROOT_VERTICES = (3, 4, 9, 10)


def _unit(dx, dy):
    length = math.hypot(dx, dy) or 1.0
    return (dx / length, dy / length)


def _fillet(points, radii, steps=8):
    out = []
    count = len(points)
    for index, point in enumerate(points):
        radius = radii.get(index, 0.0)
        if radius <= 0.0:
            out.append(point)
            continue
        previous = points[(index - 1) % count]
        following = points[(index + 1) % count]
        ux, uy = _unit(previous[0] - point[0], previous[1] - point[1])
        vx, vy = _unit(following[0] - point[0], following[1] - point[1])
        half_angle = math.acos(max(-1.0, min(1.0, ux * vx + uy * vy))) / 2.0
        offset = radius / math.tan(half_angle)
        bx, by = _unit(ux + vx, uy + vy)
        centre = (point[0] + bx * radius / math.sin(half_angle),
                  point[1] + by * radius / math.sin(half_angle))
        start = (point[0] + ux * offset, point[1] + uy * offset)
        end = (point[0] + vx * offset, point[1] + vy * offset)
        a0 = math.atan2(start[1] - centre[1], start[0] - centre[0])
        a1 = math.atan2(end[1] - centre[1], end[0] - centre[0])
        while a1 - a0 > math.pi:
            a1 -= 2.0 * math.pi
        while a0 - a1 > math.pi:
            a1 += 2.0 * math.pi
        for step in range(steps + 1):
            angle = a0 + (a1 - a0) * step / steps
            out.append((centre[0] + radius * math.cos(angle),
                        centre[1] + radius * math.sin(angle)))
    return out


def outline_points():
    radii = {index: NECK_ROOT_FILLET_MM for index in NECK_ROOT_VERTICES}
    return _fillet(outline_vertices(), radii)


def _footprint_dir(footprint):
    library, _, name = footprint.partition(":")
    for base in FOOTPRINT_SEARCH_PATHS:
        candidate = os.path.join(base, library + ".pretty")
        if os.path.isfile(os.path.join(candidate, name + ".kicad_mod")):
            return candidate, name
    raise FileNotFoundError(footprint)


_PIN_NAMES = {}


def _pin_name(lib_id, number):
    if lib_id not in _PIN_NAMES:
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        _PIN_NAMES[lib_id] = {
            key: pins[0].name for key, pins in library.pins(lib_id).items()}
    return _PIN_NAMES[lib_id].get(number, "")


def _floating_net(board, reference, number):
    lib_id = netlist.PARTS[reference]["lib_id"]
    name = "unconnected-(%s-%s-Pad%s)" % (
        reference, _pin_name(lib_id, number).replace("/", "{slash}"), number)
    existing = board.GetNetInfo().GetNetItem(name)
    if existing is not None and existing.GetNetCode() != 0:
        return existing
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    return net


def _load(board, reference, part, x, y, rotation, pin_net, nets):
    library_dir, name = _footprint_dir(part["footprint"])
    footprint = pcbnew.FootprintLoad(library_dir, name)
    if footprint is None:
        raise RuntimeError("could not load " + part["footprint"])
    library = part["footprint"].partition(":")[0]
    footprint.SetFPID(pcbnew.LIB_ID(library, name))
    footprint.SetPosition(_point(x, y))
    footprint.SetOrientationDegrees(rotation)
    footprint.SetReference(reference)
    footprint.SetValue(part["value"])
    footprint.Reference().SetLayer(pcbnew.F_Fab)
    footprint.Value().SetLayer(pcbnew.F_Fab)
    for key, value in (("MPN", part["mpn"]), ("LCSC", part["lcsc"]),
                       ("Manufacturer", part["manufacturer"])):
        if not value:
            continue
        footprint.SetField(key, value)
        for field in footprint.GetFields():
            if field.GetName() == key:
                field.SetLayer(pcbnew.F_Fab)
                field.SetVisible(False)
    if not part["in_bom"]:
        footprint.SetExcludedFromBOM(True)
    # Every pose comes from this file, so a move made in KiCad would be
    # discarded by the next regeneration. Saying so in the board is what
    # the declared floorplan's must_lock asks for.
    footprint.SetLocked(True)
    for pad in footprint.Pads():
        number = pad.GetNumber()
        if not number:
            continue
        net_name = pin_net.get("%s.%s" % (reference, number))
        if net_name:
            pad.SetNet(nets[net_name])
        else:
            pad.SetNet(_floating_net(board, reference, number))
    board.Add(footprint)
    return footprint


def _nets(board):
    created = {}
    for name in sorted(netlist.NETS):
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        created[name] = net
    return created


def _design_settings(board):
    board.SetCopperLayerCount(2)
    settings = board.GetDesignSettings()
    settings.m_TrackMinWidth = pcbnew.FromMM(0.15)
    settings.m_ViasMinSize = pcbnew.FromMM(0.45)
    settings.m_MinThroughDrill = pcbnew.FromMM(0.3)
    settings.m_CopperEdgeClearance = pcbnew.FromMM(EDGE_CLEARANCE_MM)
    settings.m_HoleClearance = pcbnew.FromMM(0.25)
    settings.m_HoleToHoleMin = pcbnew.FromMM(0.25)
    settings.m_ViasMinAnnularWidth = pcbnew.FromMM(0.1)
    settings.m_MinClearance = pcbnew.FromMM(CLEARANCE_MM)
    default_class = settings.m_NetSettings.GetDefaultNetclass()
    default_class.SetClearance(pcbnew.FromMM(CLEARANCE_MM))
    default_class.SetTrackWidth(pcbnew.FromMM(TRACK_WIDTH_MM))
    default_class.SetViaDiameter(pcbnew.FromMM(VIA_DIAMETER_MM))
    default_class.SetViaDrill(pcbnew.FromMM(VIA_DRILL_MM))


def _add_outline(board):
    points = outline_points()
    closed = points + [points[0]]
    for start, end in zip(closed, closed[1:]):
        if start == end:
            continue
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetStart(_point(*start))
        shape.SetEnd(_point(*end))
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetWidth(pcbnew.FromMM(EDGE_WIDTH_MM))
        board.Add(shape)


def zone_outline_points():
    half = BOARD_HALF_WIDTH_MM - ZONE_INSET_MM
    return [(-half, ZONE_INSET_MM), (half, ZONE_INSET_MM),
            (half, ZONE_TOP_Y_MM), (-half, ZONE_TOP_Y_MM)]


def _add_plane(board, net, layer):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(net)
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in zone_outline_points():
        bx, by = to_board(x, y)
        outline.Append(pcbnew.FromMM(bx), pcbnew.FromMM(by))
    # A track crossing the board splits the pour, and a fill region no
    # pad reaches is copper the net does not own. Dropping those keeps
    # the plane's connectivity a property of the design rather than of
    # wherever the router happened to run.
    zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    zone.SetAssignedPriority(0)
    zone.SetLocalClearance(pcbnew.FromMM(CLEARANCE_MM))
    zone.SetMinThickness(pcbnew.FromMM(0.2))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetThermalReliefGap(pcbnew.FromMM(0.3))
    zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))
    board.Add(zone)
    return zone


def _add_track(board, start, end, layer, net, width_mm=TRACK_WIDTH_MM):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetWidth(pcbnew.FromMM(width_mm))
    board.Add(track)
    return track


def _add_via(board, position, net):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(position)
    via.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(VIA_DIAMETER_MM))
    via.SetDrill(pcbnew.FromMM(VIA_DRILL_MM))
    via.SetNet(net)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(via)
    return via


def pad_of(footprint, number):
    for pad in footprint.Pads():
        if pad.GetNumber() == number:
            return pad
    raise KeyError("%s has no pad %s" % (footprint.GetReference(), number))


def pad_xy(footprint, number):
    position = pad_of(footprint, number).GetPosition()
    return (pcbnew.ToMM(position.x) - ORIGIN_MM[0],
            ORIGIN_MM[1] - pcbnew.ToMM(position.y))


def _route(board, net, points, width_mm=TRACK_WIDTH_MM, layer=None):
    layer = pcbnew.F_Cu if layer is None else layer
    for start, end in zip(points, points[1:]):
        if start == end:
            continue
        _add_track(board, _point(*start), _point(*end), layer, net, width_mm)


def _neck_entry_pads(footprints):
    """The pad each island net leaves the main board from."""
    return {"SDA": pad_xy(footprints["TP3"], "1"),
            "SCL": pad_xy(footprints["TP4"], "1"),
            "3V3": pad_xy(footprints["TP1"], "1"),
            "GND": pad_xy(footprints["TP2"], "1")}


def island_routes(footprints):
    """Every island net's copper, from its entry pad to its last pad.

    Generated rather than searched for. Copper is the dominant conduction
    path along the neck, so the count and the width of these traces are
    the thermal isolation: a router that widened or doubled one would
    silently change the humidity sensor's steady-state error.
    """
    entry = _neck_entry_pads(footprints)
    u1, c2 = footprints["U1"], footprints["C2"]
    lane = dict((name, x) for name, x in NECK_TRACKS)
    routes = {}
    for name in lane:
        routes[name] = [[entry[name], (lane[name], NECK_ENTRY_Y_MM),
                         (lane[name], NECK_EXIT_Y_MM)]]
    routes["3V3"].append([(lane["3V3"], NECK_EXIT_Y_MM),
                          (lane["3V3"], 33.6), (-3.6, 34.2), (-3.6, 34.6),
                          pad_xy(c2, "1"), (-3.11, 36.4), pad_xy(u1, "3")])
    routes["GND"].append([(lane["GND"], NECK_EXIT_Y_MM),
                          (lane["GND"], 34.6), pad_xy(c2, "2")])
    routes["GND"].append([(-1.6, 34.6), (-1.6, 35.6), pad_xy(u1, "4")])
    routes["SDA"].append([(lane["SDA"], NECK_EXIT_Y_MM), (1.8, 34.4),
                          (1.8, 35.6), pad_xy(u1, "1")])
    routes["SCL"].append([(lane["SCL"], NECK_EXIT_Y_MM), (2.6, 34.4),
                          (2.6, 36.4), pad_xy(u1, "2")])
    return routes


def _route_island(board, footprints, nets):
    for name, paths in sorted(island_routes(footprints).items()):
        for path in paths:
            _route(board, nets[name], path, NECK_TRACK_WIDTH_MM)


#: Each entry ties one or more ground pads on the signal layer down to
#: the plane, through a via placed where nothing else is. Stated rather
#: than searched: the middle of a two-layer board is the only channel the
#: signals have, and a tie-down parked in it is a wall - which is exactly
#: what an unaided search produced.
GROUND_TAPS = (
    (4.3, 9.0, ("D1.4",), 0.4),
    (-5.2, 11.0, ("D2.1",), 0.4),
    (0.2, 13.2, ("C1.2",), 0.4),
    (-7.0, 20.9, ("C3.2",), 0.4),
    (6.0, 20.9, ("C4.2",), 0.4),
    (-5.9, 17.5, ("U2.3",), 0.25),
    (-3.3, 17.5, ("U2.5",), 0.25),
    (-4.35, 21.0, ("U2.8", "U2.9"), 0.25),
    (1.6, 18.55, ("U3.3",), 0.25),
    (3.2, 21.0, ("U3.7",), 0.3),
    (-1.5, 21.2, ("TP2.1",), 0.4),
)


def _tap_grounds(board, footprints, nets):
    for x, y, pad_refs, width in GROUND_TAPS:
        position = _point(x, y)
        _add_via(board, position, nets["GND"])
        for pad_ref in pad_refs:
            reference, _, number = pad_ref.partition(".")
            pad = pad_of(footprints[reference], number)
            _add_track(board, pad.GetPosition(), position, pcbnew.F_Cu,
                       nets["GND"], width)


def _pin_one_marker(board, footprint):
    pad = pad_of(footprint, "1")
    position = pad.GetPosition()
    text = pcbnew.PCB_TEXT(board)
    text.SetText("1")
    text.SetLayer(pcbnew.F_SilkS)
    text.SetPosition(pcbnew.VECTOR2I(
        position.x - pcbnew.FromMM(2.8), position.y))
    text.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
    text.SetTextThickness(pcbnew.FromMM(0.15))
    board.Add(text)
    return text


def build(placed=None):
    placed = poses() if placed is None else placed
    board = pcbnew.CreateEmptyBoard()
    _design_settings(board)
    nets = _nets(board)
    pin_net = netlist.pin_to_net()

    footprints = {}
    for reference, (x, y, rotation) in sorted(placed.items()):
        footprints[reference] = _load(
            board, reference, netlist.PARTS[reference], x, y, rotation,
            pin_net, nets)

    _add_outline(board)
    _add_plane(board, nets["GND"], pcbnew.B_Cu)
    _route_island(board, footprints, nets)
    _tap_grounds(board, footprints, nets)
    _pin_one_marker(board, footprints["J1"])
    return board, footprints


#: Item kinds whose order in the file carries no meaning. Everything
#: before the first of them - the version, the layer table, the setup and
#: the net declarations - keeps the order KiCad wrote it in.
_ORDERED_ITEMS = ("footprint", "gr_line", "gr_arc", "gr_circle", "gr_rect",
                  "gr_poly", "gr_text", "segment", "arc", "via", "zone",
                  "dimension", "group", "image")

_UUID_NAMESPACE = uuid.UUID("8f1c2d64-5e73-5a19-b0c8-2d47e6a91b35")


def _strip_uuids(node):
    if not isinstance(node, list):
        return node
    return [_strip_uuids(item) for item in node
            if not (isinstance(item, list) and item and item[0] == "uuid")]


def _assign_uuids(node, path):
    """Give every item a UUID derived from where it sits in the file.

    KiCad mints a random UUID for each object it creates and then writes
    the objects out in an order that follows those UUIDs, so the same
    design source produces a different file on every run - and a router
    reading it takes a different path. Deriving each UUID from the item's
    canonical content makes the generated board a function of the design
    source alone, which is what lets a later failure be reproduced.
    """
    if not isinstance(node, list):
        return
    counter = {}
    for index, item in enumerate(node):
        if not isinstance(item, list) or not item:
            continue
        if item[0] == "uuid":
            digest = sexpr.dump(_strip_uuids(node))
            item[1] = sexpr.Quoted(
                str(uuid.uuid5(_UUID_NAMESPACE, path + "|" + digest)))
            continue
        key = str(item[0])
        counter[key] = counter.get(key, 0) + 1
        _assign_uuids(item, "%s/%s[%d]" % (path, key, counter[key]))


def canonicalise(path):
    with open(path, encoding="utf-8") as handle:
        tree = sexpr.parse(handle.read())
    first = next((index for index, item in enumerate(tree)
                  if isinstance(item, list) and item
                  and str(item[0]) in _ORDERED_ITEMS), len(tree))
    head, tail = tree[:first], tree[first:]
    tail.sort(key=lambda item: (str(item[0]),
                                sexpr.dump(_strip_uuids(item))))
    tree = head + tail
    _assign_uuids(tree, "")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(sexpr.dump(tree) + "\n")
    return path


def fill_zones(board):
    """Cache the pour in the file, so the board describes its own copper."""
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    board.BuildConnectivity()
    return board


def write(path=None):
    path = BOARD_PATH if path is None else path
    board, _ = build()
    fill_zones(board)
    pcbnew.SaveBoard(path, board)
    return canonicalise(path)


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
