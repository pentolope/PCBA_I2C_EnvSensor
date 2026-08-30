# Benchmark entry — board 2 of 32

[metadata.json](metadata.json) is the supplied catalogue entry for this board,
preserved byte for byte from the seed pack. It is the same record that appears
in `boards_index.json` in
[PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench), and the two must agree.

| | |
|---|---|
| Repository | `PCBA_I2C_EnvSensor` |
| Board id | `i2c_env_sensor` |
| Category | sensor |
| Difficulty | 1 / 5 |
| Brief detail | 2 / 5 |
| Likely layer count | 2 |
| Primary stressors | sensor placement, I2C pullups, low-power, connector/pinout |

`difficulty` is how hard the board is. `detail` is how much of it the brief
states — and a low `detail` is not a low bar. A detail-1 brief leaves the
architecture open on purpose, and an agent that fills the silence with invented
user requirements has failed the board more thoroughly than one that designs it
badly.

This is a difficulty 1/5 board with a sparse brief (detail 2/5), which tests whether an agent can produce a clean, buildable two-layer sensor design without inventing requirements the brief never stated. The named stressors — sensor placement, I2C pullups, low-power and connector/pinout — are exactly the four places where a plausible-sounding but unsubstantiated answer is easy to write: thermal and airflow separation for the temp/humidity element, a pull-up value justified by an actual bus-capacitance and rise-time budget, current draw claimed against a real datasheet, and a connector choice that is argued rather than copied from a familiar 4-pin ecosystem. It also checks discipline about multi-device I²C addressing, since the brief requires the sensors to coexist but names no devices and no addresses.

## What goes here

Compact results only: metrics, verdicts, and the commit each was measured at.
The evidence for a result is the artefact the toolkit recomputes, not a summary
of it.

Routing search output, candidate pools, build trees and field-solver dumps do
**not** go here. They are ignored by [.gitignore](../.gitignore) and are
regenerated from what is committed. Thirty-two repositories share one benchmark
clone; weight here is paid thirty-two times.

## Protocol

The attempt protocol is defined once, in the umbrella repository, so that
thirty-two boards cannot drift into thirty-two protocols. See
[PCBA_AutoDesignAndTest_Bench/BENCHMARK.md](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench/blob/main/BENCHMARK.md).
