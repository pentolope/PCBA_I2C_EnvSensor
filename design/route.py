from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

from . import build, layout, netlist

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest"))

from pcbqa import routing_record  # noqa: E402

REPO_ROOT = layout.REPO_ROOT
CANDIDATE_ROOT = os.path.join(REPO_ROOT, "candidates")
CANDIDATE_NAME = "route-current"
PROVENANCE_PATH = os.path.join(REPO_ROOT, "generated", "routing.json")

MANIFEST = os.path.join(REPO_ROOT, "board", "manifest.json")
VALIDATOR = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest",
                         "run.py")

#: The ground plane and the four island lanes are generated. The supply
#: pour is generated too, but the search still routes 3V3: a signal
#: track crossing the board splits the pour, and only tracks can hold
#: the supply together once it does.
ROUTED_NETS = ("3V3_IN", "3V3", "SDA", "SCL")

ROUTER_OPTIONS = (
    "--track-width", str(layout.TRACK_WIDTH_MM),
    "--clearance", str(layout.ROUTED_CLEARANCE_MM),
    "--via-size", str(layout.VIA_DIAMETER_MM),
    "--via-drill", str(layout.VIA_DRILL_MM),
    "--board-edge-clearance", str(layout.EDGE_CLEARANCE_MM),
    "--hole-to-hole-clearance", "0.3",
    "--same-net-pad-clearance", "0.3",
)

# The router is deterministic for a fixed input, so a bare retry explores
# nothing. Each attempt varies the net-ordering strategy instead, which is
# what actually produces a different candidate.
ATTEMPT_ORDERINGS = ("mps", "inside_out", "original")
MAX_ATTEMPTS = len(ATTEMPT_ORDERINGS)

SNAP_TOLERANCE_MM = 0.25
TOUCH_TOLERANCE_MM = 0.01


def _krt():
    from pcbqa import krt
    return krt


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _summary(text):
    for line in text.splitlines():
        if line.strip().startswith("JSON_SUMMARY_MIN:"):
            return json.loads(line.split("JSON_SUMMARY_MIN:", 1)[1])
    return {}


def _route_once(resolved, candidate, attempt, placed_pcb):
    stage_dir = os.path.join(candidate, "attempt-%02d" % attempt)
    os.makedirs(stage_dir, exist_ok=True)
    source_pcb = os.path.join(stage_dir, "source.kicad_pcb")
    shutil.copy(placed_pcb, source_pcb)
    shutil.copy(os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_pro"),
                os.path.join(stage_dir, "source.kicad_pro"))
    routed_pcb = os.path.join(stage_dir, "routed.kicad_pcb")
    command = [sys.executable,
               os.path.join(resolved["path"], "py_router", "route.py"),
               source_pcb, routed_pcb, "--nets"] + list(ROUTED_NETS) \
        + list(ROUTER_OPTIONS) \
        + ["--ordering", ATTEMPT_ORDERINGS[attempt - 1]]
    completed = subprocess.run(command, capture_output=True, text=True)
    summary = _summary(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError("the router did not run: rc=%s\n%s"
                           % (completed.returncode,
                              completed.stderr[-2000:]))
    if summary.get("failed"):
        # An incomplete route is a rejected candidate, not a broken tool:
        # the next attempt reorders the search and tries again, and this
        # one stays in the record as an attempt that did not connect.
        return {
            "attempt": attempt,
            "source_sha256": digest(source_pcb),
            "accepted": False,
            "stages": [{"stage": "routed", "produced_by": "router",
                        "sha256": digest(routed_pcb)}],
            "context": {"router_summary": summary,
                        "ordering": ATTEMPT_ORDERINGS[attempt - 1]},
            "board": None,
        }
    tidied_pcb = os.path.join(stage_dir, "tidied.kicad_pcb")
    shutil.copy(routed_pcb, tidied_pcb)
    transform = tidy(tidied_pcb)
    return {
        "attempt": attempt,
        "source_sha256": digest(source_pcb),
        "accepted": False,
        "stages": [
            {"stage": "routed", "produced_by": "router",
             "sha256": digest(routed_pcb)},
            {"stage": "tidied", "produced_by": "transform",
             "sha256": digest(tidied_pcb),
             "transform": "snap track endpoints onto same-net via centres; "
                          "prune dangling track ends, keeping any removal "
                          "only while connectivity is unchanged; split a "
                          "track where another track's end lands in the "
                          "middle of it, so the junction is an endpoint of "
                          "both; refill the zones so the pour is knocked "
                          "out around the copper the router added",
             "effects": transform,
             "parameters": {"snap_tolerance_mm": SNAP_TOLERANCE_MM,
                            "touch_tolerance_mm": TOUCH_TOLERANCE_MM}},
        ],
        "context": {"router_summary": summary,
                    "ordering": ATTEMPT_ORDERINGS[attempt - 1]},
        "board": tidied_pcb,
    }


#: Candidate acceptance judges the toolkit's design gate class - every gate
#: that judges the design itself, expanded by the toolkit so the selection
#: cannot rot as gates are added - plus ROUTE.PROVENANCE, whose record this
#: loop writes before judging, so the record-board agreement is judged per
#: candidate exactly as it was under the hand-written list.
ACCEPTANCE_SELECTION = "design,ROUTE.PROVENANCE"


def _gates_pass():
    """Judge the design, not the release artifacts.

    The fabrication outputs are generated FROM the board a search has not
    finished choosing, so gates over those artifacts are stale by
    construction during routing and would reject every candidate. The
    manifest names the subset that judges the design itself; everything
    else is judged once, afterwards, by a full validate.
    """
    completed = subprocess.run(
        [sys.executable, VALIDATOR, "validate", MANIFEST,
         "--only=" + ACCEPTANCE_SELECTION],
        capture_output=True, text=True, cwd=REPO_ROOT)
    return completed.returncode == 0


def _write_record(placed_pcb, attempts, accepted, krt, resolved):
    record = {
        "kind": routing_record.KIND,
        "source_sha256": digest(placed_pcb),
        "attempts": attempts,
        "accepted_attempt": accepted["attempt"] if accepted else None,
        "adopted_sha256": (digest(layout.BOARD_PATH) if accepted else None),
        "context": {
            "router": krt.provenance(resolved["path"], sys.executable),
            "resolution": resolved,
            "routed_nets": list(ROUTED_NETS),
            "generated_nets": [name for name, _x in layout.NECK_TRACKS],
            "options": list(ROUTER_OPTIONS),
            "reproducibility": "the router is not bit-reproducible; "
                               "candidates are generated until one passes "
                               "the board gates and every attempt is "
                               "recorded here",
        },
    }
    routing_record.validate(record)
    os.makedirs(os.path.dirname(PROVENANCE_PATH), exist_ok=True)
    with open(PROVENANCE_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    return record


def run():
    from . import simulation
    krt = _krt()
    resolved = krt.resolve()
    candidate = os.path.join(CANDIDATE_ROOT, CANDIDATE_NAME)
    shutil.rmtree(candidate, ignore_errors=True)
    os.makedirs(candidate, exist_ok=True)
    layout.write()
    placed_pcb = os.path.join(candidate, "placed.kicad_pcb")
    shutil.copy(layout.BOARD_PATH, placed_pcb)

    attempts = []
    accepted = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = _route_once(resolved, candidate, attempt, placed_pcb)
        entry = {key: value for key, value in result.items() if key != "board"}
        if result["board"] is None:
            attempts.append(entry)
            continue
        shutil.copy(result["board"], layout.BOARD_PATH)
        build.write_project()
        # Everything derived from the board is regenerated before the
        # candidate is judged, so the acceptance run judges one coherent
        # state rather than this candidate's copper beside the previous
        # candidate's extracted models.
        simulation.write()
        # The record must describe the board the gates are about to judge,
        # ROUTE.PROVENANCE included, so it is written before the judgement
        # and rewritten if the candidate is rejected.
        entry["accepted"] = True
        _write_record(placed_pcb, attempts + [entry], entry, krt, resolved)
        if _gates_pass():
            accepted = entry
            attempts.append(entry)
            break
        entry["accepted"] = False
        attempts.append(entry)

    if accepted is None:
        shutil.copy(placed_pcb, layout.BOARD_PATH)
        build.write_project()
        simulation.write()
        _write_record(placed_pcb, attempts, None, krt, resolved)
        raise RuntimeError(
            "no routing candidate passed the board gates in %d attempts; "
            "the placed, unrouted board has been restored so no failing "
            "copper stays in the tree" % MAX_ATTEMPTS)
    return layout.BOARD_PATH, PROVENANCE_PATH


def _endpoints(track):
    return (track.GetStart(), track.GetEnd())


def _supported(point, track, board, vias, tracks, epsilon):
    for via in vias:
        if via.GetNetCode() != track.GetNetCode():
            continue
        centre = via.GetPosition()
        if math.hypot(point.x - centre.x, point.y - centre.y) <= epsilon:
            return True
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetCode() != track.GetNetCode():
                continue
            if pad.HitTest(point, 0):
                return True
    for other in tracks:
        if str(other.m_Uuid) == str(track.m_Uuid):
            continue
        if other.GetNetCode() != track.GetNetCode():
            continue
        if other.Type() == pcbnew.PCB_VIA_T:
            continue
        if other.GetLayer() != track.GetLayer():
            continue
        if other.HitTest(point, int(epsilon)):
            return True
    return False


def _endpoint_support(board, point, net_code, epsilon):
    """Whether a track end lands on something with an end of its own."""
    for track in board.GetTracks():
        if track.GetNetCode() != net_code:
            continue
        if track.Type() == pcbnew.PCB_VIA_T:
            centre = track.GetPosition()
            if math.hypot(point.x - centre.x, point.y - centre.y) <= epsilon:
                return True
            continue
        for other in (track.GetStart(), track.GetEnd()):
            if other == point:
                continue
            if math.hypot(point.x - other.x, point.y - other.y) <= epsilon:
                return True
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetCode() == net_code and pad.HitTest(point, 0):
                return True
    return False


def _projection(track, point):
    start, end = track.GetStart(), track.GetEnd()
    dx, dy = end.x - start.x, end.y - start.y
    length_squared = float(dx * dx + dy * dy)
    if length_squared == 0.0:
        return None, None
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_squared
    if not 0.0 < t < 1.0:
        return None, None
    foot = pcbnew.VECTOR2I(int(round(start.x + t * dx)),
                           int(round(start.y + t * dy)))
    return foot, math.hypot(point.x - foot.x, point.y - foot.y)


def bond_junctions(board):
    """Split a track where another track's end lands in the middle of it.

    A router that finishes a net by running into the side of existing
    copper leaves an end that is electrically connected but is nobody's
    endpoint, which reads as a dangling end. Splitting the crossed track
    at that point makes the junction explicit without moving any copper.
    """
    bonded = 0
    for _ in range(64):
        split = None
        tracks = [t for t in board.GetTracks()
                  if t.Type() != pcbnew.PCB_VIA_T]
        for track in tracks:
            for point in (track.GetStart(), track.GetEnd()):
                if _endpoint_support(board, point, track.GetNetCode(),
                                     pcbnew.FromMM(TOUCH_TOLERANCE_MM)):
                    continue
                for other in tracks:
                    if str(other.m_Uuid) == str(track.m_Uuid):
                        continue
                    if other.GetNetCode() != track.GetNetCode():
                        continue
                    if other.GetLayer() != track.GetLayer():
                        continue
                    foot, distance = _projection(other, point)
                    if foot is None:
                        continue
                    if distance > other.GetWidth() / 2.0:
                        continue
                    split = (track, point, other, foot)
                    break
                if split:
                    break
            if split:
                break
        if split is None:
            break
        track, point, other, foot = split
        tail = pcbnew.PCB_TRACK(board)
        tail.SetStart(foot)
        tail.SetEnd(other.GetEnd())
        tail.SetLayer(other.GetLayer())
        tail.SetWidth(other.GetWidth())
        tail.SetNet(other.GetNet())
        board.Add(tail)
        other.SetEnd(foot)
        if point == track.GetStart():
            track.SetStart(foot)
        else:
            track.SetEnd(foot)
        board.BuildConnectivity()
        bonded += 1
    return bonded


def tidy(path):
    board = pcbnew.LoadBoard(path)
    epsilon = pcbnew.FromMM(TOUCH_TOLERANCE_MM)
    snapped = 0
    for _ in range(4):
        vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
        moved = 0
        for track in board.GetTracks():
            if track.Type() == pcbnew.PCB_VIA_T:
                continue
            for get, set_ in ((track.GetStart, track.SetStart),
                              (track.GetEnd, track.SetEnd)):
                point = get()
                for via in vias:
                    if via.GetNetCode() != track.GetNetCode():
                        continue
                    centre = via.GetPosition()
                    distance = math.hypot(point.x - centre.x,
                                          point.y - centre.y)
                    if epsilon < distance <= pcbnew.FromMM(SNAP_TOLERANCE_MM):
                        set_(centre)
                        moved += 1
                        break
        snapped += moved
        if not moved:
            break

    removed = 0
    load_bearing = set()
    for _ in range(256):
        board.BuildConnectivity()
        baseline = board.GetConnectivity().GetUnconnectedCount(True)
        vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
        tracks = [t for t in board.GetTracks()
                  if t.Type() != pcbnew.PCB_VIA_T]
        victim = None
        for track in tracks:
            if str(track.m_Uuid) in load_bearing:
                continue
            if track.GetLength() == 0:
                victim = track
                break
            if all(_supported(point, track, board, vias, tracks, epsilon)
                   for point in _endpoints(track)):
                continue
            victim = track
            break
        if victim is None:
            break
        identity = str(victim.m_Uuid)
        board.Remove(victim)
        board.BuildConnectivity()
        if board.GetConnectivity().GetUnconnectedCount(True) > baseline:
            # Copper something depends on: it stays, and the scan moves
            # on rather than stopping at the first thing it may not take.
            board.Add(victim)
            board.BuildConnectivity()
            load_bearing.add(identity)
            continue
        removed += 1
    bonded = bond_junctions(board)

    # The router adds copper the pour was not knocked out around, so the
    # fill is recomputed here rather than left describing earlier copper.
    layout.fill_zones(board)
    pcbnew.SaveBoard(path, board)
    layout.canonicalise(path)
    return {"endpoints_snapped": snapped,
            "dangling_tracks_removed": removed,
            "junctions_bonded": bonded,
            "zones_refilled": len(list(board.Zones()))}


if __name__ == "__main__":
    for written in run():
        sys.stdout.write(written + "\n")
