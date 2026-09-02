from __future__ import annotations

import os
import sys

from . import netlist

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY_NAME = netlist.LIBRARY_NAME
SYMBOL_LIB_PATH = os.path.join(REPO_ROOT, "library",
                               LIBRARY_NAME + ".kicad_sym")
FOOTPRINT_DIR = os.path.join(REPO_ROOT, "library", LIBRARY_NAME + ".pretty")
SYM_LIB_TABLE = os.path.join(REPO_ROOT, "sym-lib-table")
FP_LIB_TABLE = os.path.join(REPO_ROOT, "fp-lib-table")

GENERATOR = "i2c-env-sensor-design-source"
SYMBOL_LIB_VERSION = "20251024"
FOOTPRINT_VERSION = "20260206"

OPT3001_SYMBOL_NAME = "OPT3001DNP"
OPT3001_DATASHEET = "https://www.ti.com/lit/ds/symlink/opt3001.pdf"

#: SBOS681C table "Pin Functions", in package pin order. Pin 7 is the
#: exposed pad DNP0006A note 3 requires to be soldered down.
OPT3001_PINS = (
    ("1", "VDD", "power_in", "left"),
    ("2", "ADDR", "input", "left"),
    ("3", "GND", "power_in", "left"),
    ("7", "EP", "passive", "left"),
    ("6", "SDA", "bidirectional", "right"),
    ("4", "SCL", "input", "right"),
    ("5", "INT", "open_collector", "right"),
)

OPT3001_FOOTPRINT_NAME = "Texas_USON-6-1EP_2x2mm_P0.65mm_EP0.65x1.35mm"

#: DNP0006A "LAND PATTERN EXAMPLE": six 0.5 x 0.25 mm lands on a 0.65 mm
#: pitch spanning 1.9 mm, and a 0.65 x 1.35 mm thermal land. The stencil
#: example shrinks the thermal aperture to 0.62 x 1.25 mm, 88% of the land
#: by area; PASTE_MARGIN_MM reproduces that coverage with one uniform inset.
OPT3001_PAD_SIZE_MM = (0.50, 0.25)
OPT3001_PAD_PITCH_MM = 0.65
OPT3001_PAD_SPAN_MM = 1.90
OPT3001_EP_SIZE_MM = (0.65, 1.35)
OPT3001_EP_PASTE_MARGIN_MM = -0.025
OPT3001_BODY_MM = (2.1, 2.1)
OPT3001_COURTYARD_MARGIN_MM = 0.15


def _font():
    return ("\n\t\t\t\t(effects\n\t\t\t\t\t(font\n"
            "\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)")


def _symbol_property(key, value, index, hide):
    hidden = "\n\t\t\t(hide yes)" if hide else ""
    return ('\t\t(property "%s" "%s"\n\t\t\t(at 0 %.2f 0)%s\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
            '\t\t\t\t)\n\t\t\t)\n\t\t)'
            % (key, value, 12.7 - 2.54 * index, hidden))


def _pin_text(kind, x, y, angle, name, number):
    return ('\t\t\t(pin %s line\n\t\t\t\t(at %.2f %.2f %d)\n'
            '\t\t\t\t(length 2.54)\n'
            '\t\t\t\t(name "%s"%s\n\t\t\t\t)\n'
            '\t\t\t\t(number "%s"%s\n\t\t\t\t)\n\t\t\t)'
            % (kind, x, y, angle, name, _font(), number, _font()))


def opt3001_symbol_text():
    left = [pin for pin in OPT3001_PINS if pin[3] == "left"]
    right = [pin for pin in OPT3001_PINS if pin[3] == "right"]
    half = 2.54 * (max(len(left), len(right)) - 1) / 2.0
    lines = [
        '(kicad_symbol_lib',
        '\t(version %s)' % SYMBOL_LIB_VERSION,
        '\t(generator "%s")' % GENERATOR,
        '\t(generator_version "10.0")',
        '\t(symbol "%s"' % OPT3001_SYMBOL_NAME,
        '\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)',
        '\t\t(exclude_from_sim no)',
        '\t\t(in_bom yes)',
        '\t\t(on_board yes)',
        _symbol_property("Reference", "U", 0, False),
        _symbol_property("Value", OPT3001_SYMBOL_NAME, 1, False),
        _symbol_property("Footprint",
                         "%s:%s" % (LIBRARY_NAME, OPT3001_FOOTPRINT_NAME),
                         2, True),
        _symbol_property("Datasheet", OPT3001_DATASHEET, 3, True),
        _symbol_property("ki_fp_filters", OPT3001_FOOTPRINT_NAME, 4, True),
        '\t\t(symbol "%s_0_1"' % OPT3001_SYMBOL_NAME,
        '\t\t\t(rectangle',
        '\t\t\t\t(start -7.62 %.2f)' % (half + 2.54),
        '\t\t\t\t(end 7.62 %.2f)' % (-half - 2.54),
        '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
        '\t\t\t\t\t(type default)\n\t\t\t\t)',
        '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)',
        '\t\t\t)',
        '\t\t)',
        '\t\t(symbol "%s_1_1"' % OPT3001_SYMBOL_NAME,
    ]
    for index, (number, name, kind, _side) in enumerate(left):
        lines.append(_pin_text(kind, -10.16, half - 2.54 * index, 0,
                               name, number))
    for index, (number, name, kind, _side) in enumerate(right):
        lines.append(_pin_text(kind, 10.16, half - 2.54 * index, 180,
                               name, number))
    lines.extend(['\t\t)', '\t)', ')'])
    return "\n".join(lines) + "\n"


def opt3001_pads():
    """(number, centre_x_mm, centre_y_mm, size_x_mm, size_y_mm)."""
    offset = (OPT3001_PAD_SPAN_MM - OPT3001_PAD_SIZE_MM[0]) / 2.0
    rows = (-OPT3001_PAD_PITCH_MM, 0.0, OPT3001_PAD_PITCH_MM)
    placed = []
    for index, number in enumerate(("1", "2", "3")):
        placed.append((number, -offset, rows[index]) + OPT3001_PAD_SIZE_MM)
    for index, number in enumerate(("6", "5", "4")):
        placed.append((number, offset, rows[index]) + OPT3001_PAD_SIZE_MM)
    placed.append(("7", 0.0, 0.0) + OPT3001_EP_SIZE_MM)
    return placed


def opt3001_footprint_text():
    body_x, body_y = (value / 2.0 for value in OPT3001_BODY_MM)
    court_x = body_x + OPT3001_COURTYARD_MARGIN_MM
    court_y = body_y + OPT3001_COURTYARD_MARGIN_MM
    parts = [
        '(footprint "%s"' % OPT3001_FOOTPRINT_NAME,
        '\t(version %s)' % FOOTPRINT_VERSION,
        '\t(generator "%s")' % GENERATOR,
        '\t(generator_version "10.0")',
        '\t(layer "F.Cu")',
        '\t(descr "Texas Instruments DNP0006A land pattern, SBOS681C '
        'drawing 4221434/C")',
        '\t(tags "USON DNP optical ambient light")',
        '\t(attr smd)',
        '\t(property "Reference" "REF**"\n\t\t(at 0 -1.9 0)\n'
        '\t\t(layer "F.SilkS")\n\t\t(uuid "00000000-0000-0000-0000-'
        '000000000001")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.6 0.6)\n'
        '\t\t\t\t(thickness 0.1)\n\t\t\t)\n\t\t)\n\t)',
        '\t(property "Value" "%s"\n\t\t(at 0 1.9 0)\n'
        '\t\t(layer "F.Fab")\n\t\t(uuid "00000000-0000-0000-0000-'
        '000000000002")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.6 0.6)\n'
        '\t\t\t\t(thickness 0.1)\n\t\t\t)\n\t\t)\n\t)'
        % OPT3001_FOOTPRINT_NAME,
    ]
    for layer, half_x, half_y, thickness in (
            ("F.CrtYd", court_x, court_y, 0.05),
            ("F.Fab", body_x, body_y, 0.1)):
        parts.append(
            '\t(fp_rect\n\t\t(start %.3f %.3f)\n\t\t(end %.3f %.3f)\n'
            '\t\t(stroke\n\t\t\t(width %.2f)\n\t\t\t(type default)\n\t\t)\n'
            '\t\t(fill none)\n\t\t(layer "%s")\n\t)'
            % (-half_x, -half_y, half_x, half_y, thickness, layer))
    parts.append(
        '\t(fp_circle\n\t\t(center %.3f %.3f)\n\t\t(end %.3f %.3f)\n'
        '\t\t(stroke\n\t\t\t(width 0.12)\n\t\t\t(type default)\n\t\t)\n'
        '\t\t(fill solid)\n\t\t(layer "F.SilkS")\n\t)'
        % (-court_x - 0.2, -court_y, -court_x - 0.14, -court_y))
    for number, x, y, size_x, size_y in opt3001_pads():
        paste = ''
        if number == "7":
            paste = ('\n\t\t(solder_paste_margin %.3f)'
                     % OPT3001_EP_PASTE_MARGIN_MM)
        parts.append(
            '\t(pad "%s" smd rect\n\t\t(at %.3f %.3f)\n\t\t(size %.3f %.3f)\n'
            '\t\t(layers "F.Cu" "F.Paste" "F.Mask")%s\n\t)'
            % (number, x, y, size_x, size_y, paste))
    parts.append(')')
    return "\n".join(parts) + "\n"


def sym_lib_table_text():
    return ('(sym_lib_table\n\t(version 7)\n'
            '\t(lib (name "%s")(type "KiCad")'
            '(uri "${KIPRJMOD}/library/%s.kicad_sym")(options "")'
            '(descr ""))\n)\n' % (LIBRARY_NAME, LIBRARY_NAME))


def fp_lib_table_text():
    return ('(fp_lib_table\n\t(version 7)\n'
            '\t(lib (name "%s")(type "KiCad")'
            '(uri "${KIPRJMOD}/library/%s.pretty")(options "")'
            '(descr ""))\n)\n' % (LIBRARY_NAME, LIBRARY_NAME))


def artifacts():
    return {
        SYMBOL_LIB_PATH: opt3001_symbol_text(),
        os.path.join(FOOTPRINT_DIR, OPT3001_FOOTPRINT_NAME + ".kicad_mod"):
            opt3001_footprint_text(),
        SYM_LIB_TABLE: sym_lib_table_text(),
        FP_LIB_TABLE: fp_lib_table_text(),
    }


def write():
    os.makedirs(FOOTPRINT_DIR, exist_ok=True)
    written = []
    for path, text in artifacts().items():
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        written.append(path)
    return sorted(written)


if __name__ == "__main__":
    for path in write():
        sys.stdout.write(path + "\n")
