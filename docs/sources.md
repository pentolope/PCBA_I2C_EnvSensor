# Sources — I²C Environmental Sensor Pod

The evidence this board's design will have to cite. **Classes of document, not
documents:** the specific parts are not chosen yet, so naming a datasheet here
would be choosing one.

A number that reaches the board carries its provenance: source, document id or
URL, retrieval date, units, and the condition it applies under. A number without
that is not evidence, and no live network lookup may change a validation or
release result.

| Kind of source | What the design needs from it |
|---|---|
| Sensor datasheets for each chosen device | Supply range, quiescent and active current, I²C address and address-select options, bus timing, accuracy and self-heating figures — none of which the brief states. |
| Ambient light sensor optical characteristics and window/aperture guidance | Spectral response, field of view and cover/window transmission decide whether the light sensing element is genuinely exposed and unobstructed. |
| I²C bus specification (NXP UM10204) | Bus capacitance limits, rise-time requirements, pull-up sizing, sink current and reserved addresses back the pull-up and speed decisions. |
| Sensor vendor application notes on placement and thermal isolation | Recommended slot/cutout geometry, distance from heat sources and airflow assumptions substantiate the brief's two placement requirements. |
| Humidity/environmental sensor handling and process documents (moisture sensitivity, reflow, cleaning restrictions) | Exposed sensing elements often forbid washing or require conditioning, which constrains the low-cost assembly process. |
| PCB fabricator capability and pricing pages for a two-layer board | Minimum trace/space, drill, slot and cutout capability and finish options define what the low-cost two-layer target actually permits. |
| Connector manufacturer datasheet and mechanical drawing, for whichever mating style is chosen | Pitch, current rating, keying, mating cycles and footprint are needed to justify the 4-pin host connector choice. |
| Passive component datasheets (resistors, capacitors) | Tolerance, voltage rating and leakage matter to pull-up accuracy, decoupling and any quiescent-current claim. |
| ESD/EMC standards and protection-device data (e.g. IEC 61000-4-2 levels) | If protection is added at the host connector interface, its clamping performance and added capacitance must be traded against the bus budget. |
| Distributor stock and pricing data | The brief's "readily available" and "low-cost" constraints are only demonstrable against real availability and price, not asserted. |
| Shared PCBA_AutoDesignAndTest toolkit documentation | The repository must consume the toolkit's interfaces and test flow rather than grow board-specific logic inside it. |

## Recording a source, once one is chosen

Replace the class with the actual document — manufacturer, part number, revision
and date — and state the fact taken from it, in the units the document uses.
Keep the class row: it says why the document was needed.

JLCPCB-wide process limits are **not** recorded here. They live in the toolkit's
`profiles/jlcpcb/`, with their own provenance; this board records only its own
tighter targets and its own selected options. A limit copied into two places is
a rival threshold, and the toolkit has a gate that says so.
