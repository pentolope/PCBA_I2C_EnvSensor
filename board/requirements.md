# Requirements — I²C Environmental Sensor Pod

Two lists. The difference between them is the whole point of this file.

A **fixed requirement** is something [BRIEF.md](../BRIEF.md) asks for. Each one
below quotes the brief text that substantiates it; if a statement cannot be
quoted, it is not a requirement here. An **open decision** is a choice the brief
deliberately left to whoever designs this board.

> Missing details are design freedom, not permission to fabricate unstated user
> requirements.

Promoting a decision into a requirement is the failure this file exists to
prevent. Record a choice under the decision it answers, with the reasoning that
made it — never by adding it to the list above.

Bound to `BRIEF.md` SHA-256 `019c2710442d044925aca61fa96e84416cafc10bbb07df4bdcfe612aea375544`.

## Fixed by the brief

### REQ-01 — The board is a compact sensor pod operating from a 3.3 V supply.

Brief text:

> Create a compact 3.3 V I²C sensor pod measuring

### REQ-02 — It must measure four quantities: temperature, humidity, pressure and ambient light.

Brief text:

> measuring temperature, humidity, pressure, and ambient light.

### REQ-03 — The host interface is I²C.

Brief text:

> Create a compact 3.3 V I²C sensor pod measuring temperature, humidity, pressure, and ambient light.

### REQ-04 — The host connection is a 4-pin host connector carrying 3V3, GND, SDA and SCL — four pins, those four signals. The brief neither requires nor forbids any further connector or test access beyond it.

Brief text:

> Use a 4-pin host connector carrying 3V3, GND, SDA, and SCL

### REQ-05 — The design must include address-selection or isolation wherever it is needed so the sensors can coexist. The brief does not say whether that coexistence is on one shared bus or on segmented ones.

Brief text:

> include address-selection or isolation where needed so the sensors can coexist.

### REQ-06 — Heat-generating parts must be placed away from the temperature/humidity sensor.

Brief text:

> Keep heat-generating parts away from the temperature/humidity sensor

### REQ-07 — The sensing elements must be reasonably exposed to ambient air.

Brief text:

> make the sensing elements reasonably exposed to ambient air.

### REQ-08 — A two-layer assembly is the stated target, consistent with the metadata's likely layer count of 2; a deviation would have to be justified and documented rather than assumed.

Brief text:

> Target a low-cost two-layer assembly using readily available parts.

### REQ-09 — The design must target low cost and use readily available parts.

Brief text:

> a low-cost two-layer assembly using readily available parts.

### REQ-10 — The repository stays a consumer of the shared PCBA_AutoDesignAndTest toolkit; board-specific logic must not accumulate in the toolkit.

Brief text:

> The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.

### REQ-11 — Choices the brief leaves open must be made and documented as engineering decisions, not written up as if they were user requirements.

Brief text:

> where the brief leaves choices open, make and document reasonable engineering decisions rather than inventing hidden user requirements.

## Open — the design agent decides

### OPEN-01 — Which sensing devices to use, and whether the four measurands come from one combined part, several parts, or some mix.

The brief names the quantities to measure but no sensor part, vendor or family, and no accuracy, range or resolution targets.

*Decision:* **not yet made.**

### OPEN-02 — How address conflicts are resolved: strap/address-select pins, an I²C multiplexer or bus switch, separate bus segments, or parts chosen to have distinct addresses.

The brief requires "address-selection or isolation where needed" but names neither the mechanism nor the devices whose addresses would collide.

*Decision:* **not yet made.**

### OPEN-03 — I²C pull-up resistor value, whether the pod carries them at all (versus relying on the host), and whether they are optional/depopulatable for multi-pod buses.

The brief fixes SDA and SCL on the connector but says nothing about pull-up location, value, or how many pods may share a bus.

*Decision:* **not yet made.**

### OPEN-04 — Target bus speed and the bus-capacitance / rise-time budget, including any allowance for the length of the interconnect between pod and host.

The brief specifies I²C but no data rate, no interconnect length and no capacitance budget.

*Decision:* **not yet made.**

### OPEN-05 — Connector part, body style, pitch, orientation, keying/polarisation and mating retention — and how the pod mates at all: a cable and plug, a board-to-board or mezzanine connector, or a header into a carrier.

The brief fixes only the pin count and the four signals; it names no connector part, footprint, ecosystem or mating style, and never says how the pod is mounted or handled.

*Decision:* **not yet made.**

### OPEN-06 — Pin order and numbering on the 4-pin connector.

The brief lists the signals as 3V3, GND, SDA, SCL but does not state that this list is the physical pin order or mandate any pinout convention.

*Decision:* **not yet made.**

### OPEN-07 — Whether any local regulation, filtering or reverse/miswire protection sits between the connector 3V3 pin and the sensors, or whether the rail is used directly.

The brief states the pod is 3.3 V and that 3V3 arrives on the connector, but is silent on conditioning that rail.

*Decision:* **not yet made.**

### OPEN-08 — Low-power strategy: quiescent current target, sensor duty cycling or shutdown/one-shot modes, and whether anything on the pod can be powered down.

Low power is a benchmark stressor in the metadata; the brief itself states no current budget, no battery or energy source, and no duty-cycle requirement.

*Decision:* **not yet made.**

### OPEN-09 — Decoupling scheme and any bulk capacitance at the connector entry.

The brief is silent on decoupling, supply impedance and transient behaviour.

*Decision:* **not yet made.**

### OPEN-10 — How "reasonably exposed to ambient air" is achieved: placement near a board edge, cutouts/slots, venting, keep-out zones, or conformal-coat/enclosure assumptions.

The brief states the goal but prescribes no mechanical means, no enclosure, and no airflow assumption.

*Decision:* **not yet made.**

### OPEN-11 — Optical arrangement for the ambient light sensor: which side it faces, aperture or window handling, solder-mask and silkscreen clearance, and shielding from any on-board light source.

The brief requires an ambient light measurement and general ambient exposure but says nothing about the optical path, field of view or any cover.

*Decision:* **not yet made.**

### OPEN-12 — The concrete thermal-separation technique and how much separation is enough: distance, copper-pour splitting, slots or thermal relief around the temperature/humidity sensor.

The brief says to keep heat-generating parts away from that sensor but gives no distance, no self-heating limit and no accuracy target to size the separation against.

*Decision:* **not yet made.**

### OPEN-13 — Board outline, dimensions, mounting holes and any keep-out for the host mechanics.

The brief says only "compact" and gives no dimensions, mounting scheme or enclosure interface.

*Decision:* **not yet made.**

### OPEN-14 — Stackup detail beyond the layer count: board thickness, copper weight, material, surface finish and soldermask/silkscreen colours.

The brief targets a low-cost two-layer assembly, but says nothing else about the fabrication stack.

*Decision:* **not yet made.**

### OPEN-15 — ESD and fault-tolerance strategy on the exposed connector lines, including hot-plug and miswire behaviour.

The brief mentions no protection requirement and no environment or handling model; an externally accessible host connector raises the question, but how the pod mates and is handled is itself an open choice (OPEN-05).

*Decision:* **not yet made.**

### OPEN-16 — Test and bring-up provisions: test points, a scan/probe access strategy, and how the assembled pod is verified against the toolkit's test flow.

The brief states no test, calibration or programming requirement.

*Decision:* **not yet made.**

### OPEN-17 — Assembly process constraints: single- versus double-sided placement, reflow profile limits, and whether any sensor forbids washing or requires post-reflow conditioning.

The brief asks for a low-cost assembly but names no fabricator, process or cleaning regime, and the parts that would impose those limits are not yet chosen.

*Decision:* **not yet made.**

### OPEN-18 — Whether any indicator LED, silkscreen labelling or identification marking is present.

The brief is silent on indicators and marking; if one is fitted, an LED is both a heat source and a light source relative to two of the required sensors, so it interacts with the brief's two placement constraints either way.

*Decision:* **not yet made.**

## Where a decision gets recorded

1. Answer it under its `OPEN-nn` heading above, with the reasoning and the
   evidence that made the choice.
2. Set `chosen` and `rationale` on the matching entry in
   [requirements.json](requirements.json).
3. Cite the datasheet or standard in [docs/sources.md](../docs/sources.md).

A choice recorded this way stays visibly a choice. That is what lets a later
reader tell this board's engineering apart from its brief.

## Where this board is most likely to be faked

Places where a design run would be tempted to assert something it cannot
substantiate:

- Naming specific sensor ICs, a connector part, or a familiar 4-pin ecosystem as though the brief required them, or assuming a mating style (cable versus board-to-board versus header) — the brief names no part, vendor, footprint or mating method at all.
- Picking a pull-up value by habit and calling it standard, with no bus-capacitance and rise-time budget and no device sink-current check behind it.
- Claiming address coexistence is solved without listing each device's actual default address and showing whether a collision exists.
- Asserting low power with a number that has no current budget behind it; the brief sets no current, battery or duty-cycle target, so any figure must come from datasheets and a stated operating mode.
- Treating "keep heat-generating parts away" as satisfied by placement alone, with no dissipation estimate, no temperature-rise calculation and no accuracy target to judge it against.
- Treating "reasonably exposed to ambient air" as satisfied by putting the sensor near an edge, with no cutout, venting or response-time reasoning — and forgetting that the light sensor's optical path is part of the same requirement.
- Inventing board dimensions, mounting holes or an enclosure to make "compact" concrete, when the brief gives no mechanical envelope.
- Claiming parts are low-cost and readily available without checking real stock and pricing.
