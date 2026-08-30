# PCBA_I2C_EnvSensor — I²C Environmental Sensor Pod

**Benchmark ID:** 02  
**Difficulty:** 1/5  
**Brief detail:** 2/5  
**Category:** sensor  
**Likely layer count:** 2  
**Primary stressors:** sensor placement, I2C pullups, low-power, connector/pinout

## Design brief

Create a compact 3.3 V I²C sensor pod measuring temperature, humidity, pressure, and ambient light. Use a 4-pin host connector carrying 3V3, GND, SDA, and SCL, and include address-selection or isolation where needed so the sensors can coexist. Keep heat-generating parts away from the temperature/humidity sensor and make the sensing elements reasonably exposed to ambient air. Target a low-cost two-layer assembly using readily available parts.

## Benchmark intent

This brief is intentionally one member of a heterogeneous PCBA-autodesign benchmark. Treat stated requirements as authoritative; where the brief leaves choices open, make and document reasonable engineering decisions rather than inventing hidden user requirements. The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.
