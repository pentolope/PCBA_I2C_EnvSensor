# Architecture — I²C Environmental Sensor Pod

**A worksheet, not a design.** Every line below is a question this board has to
answer, and none of them is answered here. Nothing in this file is a
recommendation, and the order of the sections carries no preference.

The questions were derived from [the brief](../BRIEF.md) and from what this
board is meant to stress in the benchmark:

- sensor placement
- I2C pullups
- low-power
- connector/pinout

Those are the places where a wrong answer shows up in copper.

Answer them in this file as the design is made, each answer carrying the
evidence that supports it, and record the corresponding choice against its
`OPEN-nn` entry in [board/requirements.md](../board/requirements.md). An answer
without evidence is a guess wearing a document's clothes — and this benchmark is
allowed to refuse an unsupported claim rather than invent one.

## Sensing set and device partitioning

- Which devices cover temperature, humidity, pressure and ambient light, and is one combined part or several discrete parts the better fit for this board?
- What accuracy, range and resolution does each chosen part deliver, and is that stated from its datasheet rather than assumed?
- Does any chosen part self-heat enough to bias its own or a neighbouring temperature reading, and by how much?
- Does the humidity sensor impose handling, reflow or cleaning restrictions that constrain the rest of the design?
- Are all chosen parts actually orderable in quantity, consistent with the brief's "readily available" constraint?

## I²C bus electrical design

- What is the total bus capacitance budget, counting device pin capacitance, on-board trace capacitance and whatever host-side interconnect the pod hangs off?
- What target bus speed follows from that budget, and what pull-up value satisfies both the rise-time limit and the low-level sink current of the weakest device?
- Do the pull-ups live on the pod, at the host, or optionally on the pod (fitted/DNP), and what happens when several pods share one bus?
- Are all devices' I²C logic levels compatible with the 3.3 V rail the brief fixes, or does anything need level translation?
- How are SDA and SCL routed relative to each other and to ground to keep crosstalk and coupling off the bus?

## Address allocation and coexistence

- What is the I²C address of each chosen device, and do any two collide in their default configuration?
- Where a collision exists, is it resolved by address-select strapping, a mux/bus switch, segmenting the bus, or a different part choice, and what does that cost in parts and current?
- If address straps are used, are they hard-strapped or user-selectable, and is the selection documented on the silkscreen?
- Do any chosen addresses clash with I²C reserved addresses or with devices the host may already have on the bus?
- How does a host enumerate the pod and confirm all four measurements are present?

## Host connector and pinout

- Which connector satisfies the 4-pin 3V3/GND/SDA/SCL requirement, and what argument (cost, availability, retention, mating style, existing ecosystem) selects it?
- What is the physical pin order, and is it keyed or polarised so a reversed mating is impossible?
- If a reversed or miswired connection is physically possible, what does it do to the sensors and to the host?
- Does the connector's placement conflict with the requirement to keep sensing elements exposed and away from heat?
- What current does the 3V3 pin have to carry, and is that within the connector's rating?

## Power delivery and low-power operation

- What is the pod's current draw in continuous operation and in whatever low-power mode the chosen devices offer?
- Is the connector's 3V3 used directly, or does it need filtering, a series element or local regulation, and what justifies that?
- Which devices can be duty-cycled or put in one-shot/shutdown mode, and does that require any host-controlled signal beyond the four signals the host connector carries?
- What decoupling does each device's datasheet call for, and where does it physically sit relative to that device?
- Do any leakage paths — pull-ups, address straps, indicator parts — dominate the standby current?

## Thermal design and self-heating

- What are the heat-generating parts on this board, how much do they actually dissipate, and what is the resulting temperature rise?
- How far from the temperature/humidity sensor do they need to be for that rise to be acceptable, and against what accuracy target is "acceptable" measured?
- What is the conduction path into the temperature/humidity sensor, and if the layout uses a copper pour or plane there, is it split, slotted or relieved to break that path?
- Does heat arriving from the host through the connector and whatever it mates to reach the sensor, and is that path addressed?
- How does board orientation and any enclosure change the answer?

## Ambient exposure and optical path

- What concrete mechanical means — edge placement, cutout, slot, venting, keep-out — makes the sensing elements "reasonably exposed to ambient air"?
- How long does the sensor take to track a step change in ambient temperature or humidity with that arrangement, and is that acceptable?
- Which side does the ambient light sensor face, and what is its unobstructed field of view?
- Do soldermask, silkscreen, adjacent components or the connector shadow or reflect into the light sensor?
- Is there any on-board light source, and is it shielded from the light sensor?
- Do the exposure openings conflict with mounting, handling or the board's structural integrity?

## Board outline, stackup and layout

- What outline and dimensions make this "compact" while still fitting the connector, the exposure openings and the thermal separation?
- How are mounting holes placed so they do not cut the ground return or crowd the sensors?
- What two-layer stackup — thickness, copper weight, finish — does the fabricator support at the lowest cost?
- What is the ground-return strategy on two layers — a pour, a routed return, or something else — and what do the exposure cutouts and keep-outs do to the return path under SDA and SCL?
- Which parts go on which side, and what does that imply for the number of reflow passes and the assembly cost?

## Robustness at the host connector interface

- What ESD and mechanical exposure do the connector pins realistically see, given the mating and handling model the design adopts and documents?
- Is protection added on SDA, SCL and 3V3, and if so does its capacitance fit inside the bus-capacitance budget from the I²C section?
- If the pod can be hot-plugged, can the bus be left held low or the host bus be disturbed?
- Is a shorted or swapped connection survivable, or at least non-destructive to the host?

## Bring-up, test and verification

- What is the minimum test that proves all four sensors respond at their expected addresses?
- What test points or probe access are needed on a board this small, and where do they go without disturbing the sensor exposure?
- How is the thermal-separation claim verified in hardware rather than asserted — what measurement demonstrates it?
- How is quiescent current measured on the assembled pod?
- How does this board's test flow plug into the shared PCBA_AutoDesignAndTest toolkit without adding board-specific logic to the toolkit?

## Answers still owed

All of them. See [status.md](status.md).
