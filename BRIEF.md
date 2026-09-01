# PCBA_I2C_EnvSensor — I²C Environmental Sensor Pod
## Design brief

Create a compact 3.3 V I²C sensor pod measuring temperature, humidity, pressure, and ambient light. Use a 4-pin host connector carrying 3V3, GND, SDA, and SCL, and include address-selection or isolation where needed so the sensors can coexist. Keep heat-generating parts away from the temperature/humidity sensor and make the sensing elements reasonably exposed to ambient air. Target a low-cost two-layer assembly using readily available parts.

## Functional requirements

- All four measurands shall be readable over the one I²C bus, with no physical change to the board between readings.
- Combined or separate sensor devices both qualify, provided each runs from the connector's 3V3, reports over I²C, and covers the intended ambient range.

## Power and bus electrical

- 3V3 at the connector is the only supply input; any further rail derives from it, and peak board current shall be documented.
- 100 kHz is the minimum bus rate; board, cable and host capacitance shall stay inside the specification's 400 pF, with any on-board pull-ups meeting rise-time and I_OL limits alongside the host's.

## Addressing and coexistence

- No two devices reachable at once may answer the same 7-bit address in any configuration the board ships in.
- Collisions shall be resolved by address strapping or by an isolation device that powers up leaving the host bus usable.

## Connector and protection

- Four positions carrying exactly 3V3, GND, SDA and SCL, pin 1 marked in silkscreen, keyed or else undamaged by a reversed mating.
- Cable strain shall be reacted by connector retention, not by the sensor packages or their joints.
- ESD protection shall fit inside the capacitance budget above; live mating shall not damage a device, stick the bus, or back-power the board via SDA or SCL.

## Placement, thermal isolation and ambient exposure

- The humidity opening, pressure port and optical aperture shall be left clear, nothing taller in the optical field, and reached by air that has not crossed a dissipating part.
- The temperature/humidity sensor shall sit as far as practical from dissipating parts and from the connector, which carries host heat up the cable, with copper into its region kept to what its circuit needs.
- In still air at the intended sample rate, its steady-state rise above ambient shall be small against the sensor's own accuracy.

## Manufacturing, test and bring-up

- Two copper layers, standard FR-4 stackup and finish, no blind or buried vias or filled via-in-pad, every part distributor-stocked in production quantity.
- The reflow profile shall suit each fitted package, and washing shall be omitted where a fitted sensor forbids it.
- Over the host connector alone, a bus scan shall find every fitted device at its documented address and nothing else, each returning an in-range reading that responds to stimulus.

## Open choices

- One combined temperature/humidity/pressure device or separate parts, the class of ambient-light device, and whether coexistence uses fixed addresses, strapping or an isolation device.
- Whether pod or host provides the pull-ups, the connector family and orientation, the outline and mounting, and how the temperature/humidity sensor is thermally isolated.
