from __future__ import annotations

import os

PROJECT_NAME = "i2c_env_sensor"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LIBRARY_NAME = "EnvSensorPod"

SYMBOL_LIBRARY_PATHS = (
    os.path.join(_REPO_ROOT, "library"),
    "/usr/share/kicad/symbols",
)


def _part(lib_id, footprint, value, mpn=None, manufacturer=None, lcsc=None,
          datasheet="", in_bom=True, on_board=True):
    return {
        "lib_id": lib_id,
        "footprint": footprint,
        "value": value,
        "mpn": mpn,
        "manufacturer": manufacturer,
        "lcsc": lcsc,
        "datasheet": datasheet,
        "in_bom": in_bom,
        "on_board": on_board,
    }


PARTS = {
    "J1": _part(
        "Connector_Generic:Conn_01x04",
        "Connector_JST:JST_PH_S4B-PH-K_1x04_P2.00mm_Horizontal",
        "PH_4P_Header_3V3_I2C", "S4B-PH-K-S(LF)(SN)", "JST", "C157926"),
    "U1": _part(
        "Sensor_Humidity:SHT4x",
        "Sensor_Humidity:Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad",
        "SHT40-AD1B-R3", "SHT40-AD1B-R3", "Sensirion", "C2848306"),
    "U2": _part(
        "Sensor_Pressure:LPS22HB",
        "Package_LGA:ST_HLGA-10_2x2mm_P0.5mm_LayoutBorder3x2y",
        "LPS22HBTR", "LPS22HBTR", "STMicroelectronics", "C94049"),
    "U3": _part(
        "EnvSensorPod:OPT3001DNP",
        "EnvSensorPod:Texas_USON-6-1EP_2x2mm_P0.65mm_EP0.65x1.35mm",
        "OPT3001DNPR", "OPT3001DNPR", "Texas Instruments", "C90462"),
    "D1": _part(
        "Power_Protection:TPD2E2U06DRL", "Package_TO_SOT_SMD:SOT-553",
        "TPD2E2U06DRLR", "TPD2E2U06DRLR", "Texas Instruments", "C1972959"),
    "D2": _part(
        "EnvSensorPod:TPD1E10B06",
        "EnvSensorPod:Texas_X1SON-2_1.1x0.7mm_P0.7mm",
        "TPD1E10B06DPYR", "TPD1E10B06DPYR", "Texas Instruments", "C48260"),
    "R1": _part("Device:R", "Resistor_SMD:R_0402_1005Metric", "2.7k",
                "0402WGF2701TCE", "UNI-ROYAL(Uniroyal Elec)", "C25885"),
    "R2": _part("Device:R", "Resistor_SMD:R_0402_1005Metric", "2.7k",
                "0402WGF2701TCE", "UNI-ROYAL(Uniroyal Elec)", "C25885"),
    "R3": _part("Device:R", "Resistor_SMD:R_0402_1005Metric", "4R7",
                "0402WGF470KTCE", "UNI-ROYAL(Uniroyal Elec)", "C25121"),
    "C1": _part("Device:C", "Capacitor_SMD:C_0603_1608Metric", "1uF",
                "CL10A105KB8NNNC", "Samsung Electro-Mechanics", "C15849"),
    "C2": _part("Device:C", "Capacitor_SMD:C_0402_1005Metric", "100nF",
                "CL05B104KO5NNNC", "Samsung Electro-Mechanics", "C1525"),
    "C3": _part("Device:C", "Capacitor_SMD:C_0402_1005Metric", "100nF",
                "CL05B104KO5NNNC", "Samsung Electro-Mechanics", "C1525"),
    "C4": _part("Device:C", "Capacitor_SMD:C_0402_1005Metric", "100nF",
                "CL05B104KO5NNNC", "Samsung Electro-Mechanics", "C1525"),
}

for _index, _net in enumerate(("3V3", "GND", "SDA", "SCL"), start=1):
    PARTS["TP%d" % _index] = _part(
        "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.0mm",
        "TestPoint", in_bom=False)

for _index in range(1, 3):
    PARTS["H%d" % _index] = _part(
        "Mechanical:MountingHole",
        "MountingHole:MountingHole_2.2mm_M2_DIN965",
        "MountingHole_M2", in_bom=False, on_board=True)

for _index in range(1, 4):
    PARTS["#FLG%d" % _index] = _part(
        "power:PWR_FLAG", "", "PWR_FLAG", in_bom=False, on_board=False)


NETS = {
    "3V3_IN": ["J1.2", "D2.2", "R3.1", "#FLG1.1"],
    "3V3": ["R3.2", "U1.3", "U2.1", "U2.6", "U2.10", "U3.1", "U3.2",
            "R1.1", "R2.1",
            "C1.1", "C2.1", "C3.1", "C4.1", "TP1.1", "#FLG3.1"],
    "GND": ["J1.1", "U1.4", "U2.3", "U2.5", "U2.8", "U2.9",
            "U3.3", "U3.7", "D1.4", "D2.1",
            "C1.2", "C2.2", "C3.2", "C4.2", "TP2.1", "#FLG2.1"],
    "SDA": ["J1.3", "U1.1", "U2.4", "U3.6", "D1.3", "R1.2", "TP3.1"],
    "SCL": ["J1.4", "U1.2", "U2.2", "U3.4", "D1.5", "R2.2", "TP4.1"],
}

NO_CONNECT = ("U2.7", "U3.5", "D1.1", "D1.2")


#: The pin each device samples to select its address, and the address it
#: answers at for each level of that pin. A device with no strap pin has a
#: single entry keyed by its only address.
ADDRESS_STRAPS = {
    "U1": {"pin": None, "addresses": {None: 0x44}},
    "U2": {"pin": "5", "addresses": {"GND": 0x5C, "3V3": 0x5D}},
    "U3": {"pin": "2", "addresses": {"GND": 0x44, "3V3": 0x45}},
}

#: Interface contract the host must satisfy. The pod carries the only bus
#: pull-ups, so a host pull-up is optional; if fitted it must not take the
#: parallel combination below the sink limit any bus device is rated for.
HOST_CONTRACT = {
    "supply_nominal_v": 3.3,
    "supply_tolerance": 0.05,
    "min_host_pullup_ohms": 2200.0,
    "max_host_low_level_v": 0.4,
    "bus_capacitance_limit_f": 400e-12,
    "min_bus_frequency_hz": 100e3,
    #: The specification modes this board claims to work in.
    "declared_bus_modes": ("standard",),
    "max_rise_time_s": 1000e-9,
    "sink_current_limit_a": 3e-3,
    #: One metre of ordinary four-way cable, as a hot-plug source. The
    #: pod cannot measure what it is plugged into, so the inductance and
    #: resistance that set the mating transient are assumed here and the
    #: rail damping is designed against them.
    "cable_inductance_h": 1e-6,
    "cable_resistance_ohm": 0.2,
}

#: The series element between the connector and the pod rail. Its value
#: is what damps the mating transient of the cable inductance into the
#: pod's bulk capacitance.
RAIL_DAMPING_REFERENCE = "R3"

RAILS = {
    "3V3_IN": {"min_v": (HOST_CONTRACT["supply_nominal_v"]
                         * (1.0 - HOST_CONTRACT["supply_tolerance"])),
               "max_v": (HOST_CONTRACT["supply_nominal_v"]
                         * (1.0 + HOST_CONTRACT["supply_tolerance"]))},
    "3V3": {"min_v": (HOST_CONTRACT["supply_nominal_v"]
                      * (1.0 - HOST_CONTRACT["supply_tolerance"])),
            "max_v": (HOST_CONTRACT["supply_nominal_v"]
                      * (1.0 + HOST_CONTRACT["supply_tolerance"]))},
    "GND": {"min_v": 0.0, "max_v": 0.0},
}

NODE_VOLTAGE_RANGES = {
    "SDA": {"min_v": 0.0, "max_v": RAILS["3V3"]["max_v"]},
    "SCL": {"min_v": 0.0, "max_v": RAILS["3V3"]["max_v"]},
}

BUS_NETS = ("SDA", "SCL")

PULL_UP_REFERENCES = {"R1": "SDA", "R2": "SCL"}

BULK_CAPACITOR_REFERENCES = ("C1", "C2", "C3", "C4")

ASSEMBLY_POLICY = {
    "reflow_passes": 1,
    "placement_sides": 1,
    "max_through_hole_soldered_parts": 1,
    "cleaning_process": "no_clean_no_wash",
}

CONNECTOR_FUNCTION_NETS = {
    "J1": {"GND": "GND", "3V3": "3V3_IN", "SDA": "SDA", "SCL": "SCL"},
}

#: One acquisition of every measurand per second, the rate the thermal and
#: current claims are evaluated at.
SAMPLE_RATE_HZ = 1.0

#: Humidity, pressure and illuminance are read through the sensing openings
#: of these parts; nothing may obstruct them.
EXPOSED_SENSORS = ("U1", "U2", "U3")

#: The part whose reading the board's own dissipation would corrupt.
THERMAL_VICTIM = "U1"


def pin_to_net():
    mapping = {}
    for net_name, pin_refs in NETS.items():
        for pin_ref in pin_refs:
            if pin_ref in mapping:
                raise ValueError(
                    "pin %s assigned to both %s and %s"
                    % (pin_ref, mapping[pin_ref], net_name))
            mapping[pin_ref] = net_name
    for pin_ref in NO_CONNECT:
        if pin_ref in mapping:
            raise ValueError(
                "pin %s is both no-connect and on net %s"
                % (pin_ref, mapping[pin_ref]))
    return mapping
