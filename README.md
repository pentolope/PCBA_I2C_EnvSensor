# I²C Environmental Sensor Pod

A compact 3.3 V I²C sensor pod for temperature, humidity, pressure and ambient light on a 4-pin 3V3/GND/SDA/SCL host connector.

This repository holds the design problem for a compact 3.3 V I²C environmental sensor pod that measures temperature, humidity, pressure and ambient light and connects to a host through a 4-pin connector carrying 3V3, GND, SDA and SCL. The brief fixes the measurands, the supply rail, the bus type, the connector pin count and signal set, the need for address-selection or isolation where needed so the sensors can coexist, two placement constraints (heat-generating parts away from the temperature/humidity sensor, sensing elements reasonably exposed to ambient air), and it sets a low-cost two-layer assembly from readily available parts as the target. Everything else is open: no sensor parts, connector part, footprint or mating style, pull-up values, bus speed, current budget, board outline, stackup detail, protection scheme or test strategy is named. This is a detail-2 brief, so most of the architecture and all component selection belong to the design agent, which must make and document those choices rather than treat them as pre-decided.

> **This board has not been designed.** There is no schematic, no layout and no
> part selection here — only the brief, a reading of the brief, and the
> scaffolding a design run needs. That is the intended state of this repository,
> not a gap in it.

## What the brief fixes, and what it leaves open

The brief pins down 11 requirements and deliberately leaves
18 decisions to whoever designs the board. The `Source` column says
which is which: `brief` is quoted from [BRIEF.md](BRIEF.md), `metadata` comes
from the benchmark catalogue, and `open` means the brief does not fix it.

| Aspect | Value | Source |
|---|---|---|
| Function | Compact I²C sensor pod measuring temperature, humidity, pressure and ambient light | brief |
| Supply rail | 3.3 V | brief |
| Host interface | I²C (SDA/SCL) to a host | brief |
| Host connector | 4-pin, carrying 3V3, GND, SDA and SCL; connector type/part/pitch not fixed | brief |
| Bus coexistence | Address-selection or isolation included where needed so the sensors can coexist | brief |
| Thermal placement | Heat-generating parts kept away from the temperature/humidity sensor | brief |
| Sensing-element exposure | Sensing elements reasonably exposed to ambient air | brief |
| Cost and part availability | Low-cost assembly using readily available parts | brief |
| Assembly target | Two-layer assembly, stated by the brief as the target | brief |
| Likely layer count | 2 | metadata |
| Benchmark class | Category: sensor; difficulty 1/5; brief detail 2/5 | metadata |
| Primary stressors | sensor placement, I2C pullups, low-power, connector/pinout | metadata |
| Sensor devices and part numbers | Not fixed by the brief — design agent's choice | open |
| Board outline, dimensions and mounting | Not fixed by the brief beyond "compact" — design agent's choice | open |
| Connector mating style (cable, board-to-board, header into a carrier) | Not fixed by the brief, which names only the pin count and the four signals — design agent's choice | open |

The full split, with the verbatim brief text substantiating every fixed
requirement, is in [board/requirements.md](board/requirements.md) and
machine-readably in [board/requirements.json](board/requirements.json).

**Missing details are design freedom, not permission to fabricate unstated user
requirements.** A choice the brief left open is recorded as a decision, with its
reasoning — never promoted into a requirement.

## Benchmark position

| | |
|---|---|
| Benchmark id | 2 of 32 |
| Category | sensor |
| Difficulty | 1 / 5 |
| Brief detail | 2 / 5 |
| Likely layer count | 2 |
| Primary stressors | sensor placement, I2C pullups, low-power, connector/pinout |

This is a difficulty 1/5 board with a sparse brief (detail 2/5), which tests whether an agent can produce a clean, buildable two-layer sensor design without inventing requirements the brief never stated. The named stressors — sensor placement, I2C pullups, low-power and connector/pinout — are exactly the four places where a plausible-sounding but unsubstantiated answer is easy to write: thermal and airflow separation for the temp/humidity element, a pull-up value justified by an actual bus-capacitance and rise-time budget, current draw claimed against a real datasheet, and a connector choice that is argued rather than copied from a familiar 4-pin ecosystem. It also checks discipline about multi-device I²C addressing, since the brief requires the sensors to coexist but names no devices and no addresses.

This repository is one of thirty-two. The suite, the protocol and the results
live in [PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench).

## Repository layout

| Path | Contents |
|---|---|
| `BRIEF.md` | the supplied brief — authoritative, preserved byte for byte, never edited |
| `board/requirements.md` | what the brief fixes, what it leaves open, and where decisions get recorded |
| `board/requirements.json` | the same split, machine-readable, each fixed requirement bound to brief text |
| `board/manifest.template.json` | the toolkit's minimum manifest, pre-filled for this board |
| `board/toolchain.json` | where this board's build finds KiCad and the router |
| `benchmark/metadata.json` | the supplied catalogue entry — category, difficulty, detail, stressors |
| `docs/architecture.md` | the decisions this board must make, as questions, unanswered |
| `docs/sources.md` | the classes of evidence the design will have to cite |
| `docs/status.md` | what exists, what does not, and what is deliberately absent |
| `candidates/` | disposable search output, ignored by Git |
| `.claude/skills/` | the accountability-review skill [CLAUDE.md](CLAUDE.md) requires before a push |
| `tooling/PCBA_AutoDesignAndTest` | the shared verification/routing/release toolkit, as a pinned submodule |

## Getting the repository

The toolkit is a submodule and carries KiCad Routing Tools as a submodule of its
own, so clone recursively:

```bash
git clone --recursive https://github.com/pentolope/PCBA_I2C_EnvSensor.git
```

```bash
git submodule update --init --recursive
```

## Designing the board

Generic verification, routing and release logic is **not** written here. It is
consumed from `tooling/PCBA_AutoDesignAndTest`, which is board-agnostic by
construction and must stay that way; this repository owns the board and nothing
else. Start from
[the toolkit's onboarding guide](tooling/PCBA_AutoDesignAndTest/examples/onboarding.md),
and see [CLAUDE.md](CLAUDE.md) for the rules a design run works under.

```bash
python3 tooling/PCBA_AutoDesignAndTest/run.py preflight
```

## Brief integrity

`BRIEF.md` SHA-256 `019c2710442d044925aca61fa96e84416cafc10bbb07df4bdcfe612aea375544`

Every quotation in `board/requirements.json` is bound to those exact bytes. If
the brief ever changes, the bindings are stale by construction — which is the
point of recording the digest.
