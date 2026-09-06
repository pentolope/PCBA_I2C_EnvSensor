# Toolkit requests from PCBA_I2C_EnvSensor, round 2

Written against toolkit `c17ebb5`, board `80b30dd` plus an uncommitted
manifest change (31 PASS / 25 NOT_APPLICABLE / 1 FAIL of 57 gates; the one
FAIL is `ROUTE.PROVENANCE` and section 1 is why).

Round 1 (`TOOLKIT_REQUEST.md`) asked for capability. This round is mostly
about the routing cycle, found by doing something ordinary - adding two
evidence domains to a manifest - and discovering the board could not get
back to a valid state afterwards.

Ordered by what cost the most.

---

## 1. A routing record that cannot be reproduced

`policy.py` now requires every implemented domain to be declared or declined.
Board 02 predates five of them, so settling them means editing
`board/manifest.json`. That edit fails `ROUTE.PROVENANCE`, whose own message
prescribes the remedy: *"rerun the owned search to re-record"*. The remedy
cannot be run, and if it could, it would not reproduce the board.

Four separate defects compose into that. Each needs its own fix.

### 1.1 The owned search cannot run from an adopted board

`run.py route` stages from `sources.pcb`. After `--adopt` that IS the routed
board, so the router reports `All nets are already fully connected - nothing
to route!`, takes an early return, and the wrapper refuses every attempt with
*"the router wrote no --json-out summary; an unaccounted run is not a
candidate"* (`pcbqa/route.py`, `_summary_defenses`). Three attempts, three
refusals, 0.6 s each.

The router is not silent. It prints a complete `JSON_SUMMARY_MIN` with
`status: already_connected` on that path - `_emit_summary_min` at
`py_router/route.py:1350` - and its docstring argues exactly this case:

> a step that legitimately did nothing ... must still satisfy it. A missing
> line there is indistinguishable from a crash, which is the one reading that
> would make an agent do the wrong thing.

The file write it needs - the `if json_out:` block at
`py_router/route.py:5494`, which calls `write_summary_file` - sits past the
early return at 1347, so the console line is emitted and the file is not. The
consumer reads the file.

**Done when** the `already_connected` early return writes `--json-out` with
the same tally it prints, so a search over a fully-routed board is an
accounted no-op rather than a refusal. This one lives in
`tooling/KiCadRoutingTools`, not `pcbqa`.

### 1.2 The pre-route source is not a tracked input

The search only has work to do when it starts from the board as it was before
routing. On this board that is `d9e4882b`, and it has never been committed:
eight commits touch `i2c_env_sensor.kicad_pcb` and not one of them holds that
board. The only copies are `out/*/source.kicad_pcb` inside run directories
that `.gitignore` excludes.

So `git clean -xdf` - or any fresh clone - makes this board permanently
un-re-routable, silently, with every gate still green until someone edits the
manifest and finds out.

**Done when** the routing record binds the source board as a tracked design
input the way it binds every other input, and `route --check` refuses when
that input is absent rather than when it has already been lost.

### 1.3 The search is not deterministic

Four searches, identical source, identical manifest, identical toolkit, no
tree writes between them:

| trial | accepted candidate |
|---|---|
| 1 | `797a2fdb` - byte-identical to the committed board |
| 2 | `327109756` |
| 3 | `e309fcfd` |
| 4 | `e309fcfd` |

Three outcomes from four runs. Two of the three (`797a2fdb`, `e309fcfd`) each
appear as a committed `i2c_env_sensor.kicad_pcb` in this board's own history,
which is what the oscillating hashes across the "Re-record the owned route"
commits have been recording.

The whole difference is one 0.11 mm fragment of SCL near U2 -
`(93.525 82.225)` to `(93.475 82.325)` - present as its own segment in one
candidate and merged into its neighbour in another. Electrically nothing.
Every UUID downstream of it moves with it, so the board file, the gerbers and
every digest change.

`CLAUDE.md` says the router is invoked deterministically per attempt row. Per
row it may be; the pipeline through `pcbqa.transforms` to an accepted
candidate is not, and that is the thing the record names.

This is the one that matters most. A record binding a candidate nobody can
reproduce is a receipt, not provenance: it proves a run happened, not that
this copper is what the declaration produces. It also makes re-recording an
adopted board a lottery - the honest way to re-bind a manifest is to accept
whatever the search draws, and three of the four trials above did not draw the
board that was reviewed.

**Done when** the same source, manifest and toolkit produce the same accepted
candidate, and a repeat-search self-check proves it. If some nondeterminism is
irreducible, the record should say which stage introduced it and the
acceptance should be over a canonical form that is stable across it.

### 1.4 `ROUTE.PROVENANCE` binds the whole manifest file

`pcbqa/route.py:2006` records `sha256_file(manifest.path)` and
`g_provenance.py:415` holds the tree to it. Any byte change to the manifest
invalidates the routing record - including whitespace, and including the four
blocks added here, none of which routing reads.

The comment defends the breadth honestly ("the resolved plan does not carry
every rule the acceptance read"), and fail-closed is the right default. But
the granularity has no escape: with 1.1 and 1.2 in place there is no
reconciliation short of a full re-route, and with 1.3 a re-route is not
value-neutral. The three together turn a manifest edit into a design change.

**Done when** either the binding is over what acceptance actually read - the
resolved plan plus the gate policy blocks the acceptance set names - or there
is an explicit re-bind that re-runs the recorded acceptance against the
current manifest over the adopted copper, and records that it did. A re-judge
is not a re-search; `--replay` already almost is this (see 4).

---

## 2. `THERMAL.*` is all-or-nothing, so one part costs the domain

`THERMAL.BOARD_RISE` is the gate this board wants: a 2-D steady-state solve
over real per-cell copper coverage. It would measure what the isolation neck
actually does, replacing the board's own two-node isothermal lump in
`design/rules.py`.

It cannot be reached. It requires `thermal.parts`, and declaring
`thermal.parts` also runs `THERMAL.DERATING` and `THERMAL.JUNCTION`, which
fail any part with no `theta_ja` + `junction_max_c` ("an unknown junction is
not a cool one"). LPS22HB publishes no thermal resistance at all - zero
occurrences in the frozen datasheet. Declaring the domain without U2 would
state a dissipation inventory that omits a real source, which is what
`THERMAL.DISSIPATION` exists to catch.

Both refusals are correct. The result is still that a board dissipating
25.6 uW in total cannot get a board-rise solve because one sensor's vendor
does not publish a number the solve does not use.

**Done when** `THERMAL.BOARD_RISE` can be declared from an inventory alone -
dissipation per part, which this board has for every part - with the
junction-path gates NOT_APPLICABLE until `theta_ja`/`junction_max_c` are
declared. Coverage of the inventory is what board-rise needs; a per-part
junction verdict is a different question.

## 3. `CURRENT.*` has no verdict below the basis window

Peak board current is 4.0 mA. `ampacity.required_area_mm2` computes the
section the declared curve demands for it and refuses, because the answer is
below the fitted window. Taking IPC-2221 external at a 1 mil2 floor, 4 mA
needs about 0.008 mil2, and no rise inside the window escapes it: reaching
1 mil2 would take a 0.0035 C rise. The window is the board's to declare, but
its lower edge is a property of the published curve, not a choice.

Refusing to extrapolate is right. But the two directions are not symmetric.
Being outside the window on the *capacity* side ("what does this section
carry") is genuinely unanswerable. Being outside it on the *required area*
side is a bound: needing less copper than the smallest section the curve was
fitted over means every conductor the process can make already exceeds it.
That is decidable, and conservative.

As it stands, any low-power board must decline the whole domain, which reads
identically to a board that never looked.

**Done when** a required area below the fitted window resolves as PASS with
a stated basis - "below the smallest section the declared curve covers, and
therefore below the smallest the process can produce" - rather than as a
refusal, with the fitted floor named in the verdict.

## 4. `--replay` is spelled two ways and scoped narrower than it reads

`run.py:19` documents `[--replay <run-dir>]`. The parser at `run.py:1240`
accepts only `--replay=<run-dir>`; the space form exits with `unknown option
for route: --replay`. Straight bug.

Scope: the help says "re-judge a recorded run's candidates through the current
transforms without re-searching", which reads like the reconciliation path for
1.4. It is not one - it refuses any manifest change outside
`routing.transforms`, and its record keeps the original run's
`manifest_sha256` as what the candidates were judged against
(`pcbqa/route.py:2308`). Replay is a re-judge of an earlier binding, not a
re-bind to the current one.

**Done when** the two spellings agree, and the help says what replay is for -
transform changes only - so it is not mistaken for the missing re-bind.

## 5. Physical inputs are restated per domain instead of cited

`current.physical_inputs` takes a path to `fab/physical_inputs.json` and reads
the parameter records out of it, digests and all. `pdn.copper_thickness_mm`
takes a bare number map and `thermal.board_rise.copper_thickness_mm` a bare
number - so declaring PDN meant typing `0.04064` twice into the manifest,
where the frozen approved-evidence record with its catalog digest already sits
one file away.

Same for `pdn.via_resistance_ohm`: the toolkit has
`ampacity.barrel_cross_section_mm2` and `barrel_resistance_ohm`, and the
approved catalog publishes `hole_plating_thickness_um` with its own caveat
("an AVERAGE hole plating thickness, not a guaranteed minimum wall"). The
board had to compute 1.534 mOhm by hand and drop both the derivation and the
caveat on the floor.

**Done when** every physical input a domain needs can be cited from
`physical_inputs` the way `current` cites it, and a barrel resistance can be
derived from the catalog plating figure carrying that figure's own knowledge
level, instead of being restated as a bare number with no provenance.

## 6. Still not byte-reproducible: three files carry wall-clock

Carried over from round 1 (6c), now the only thing standing between this board
and a fully reproducible build. Export normalization landed and it works - 14
of 17 artifacts, gerbers and drills and BOM and CPL and the zip, are
byte-identical across rebuilds. The three that are not:

- `generated/release/reports/drc.json`, `.../erc.json` - KiCad's own `date`
- `generated/release/fabrication.json` - `generated_utc` (`build.py:625`)

So a no-op rebuild always dirties the tree and always shows up as a diff in a
release-refresh commit.

**Done when** report timestamps are normalized on the way in the way every
other export now is, and `generated_utc` is either dropped from the digested
document or excluded from what the digest covers.

---

## Landed since round 1

Closure staleness now names what moved: `ARCH.PROVENANCE` reported
`changed_inputs: ["<configuration>"]`, which is exactly request 7/8 and it
turned a half-hour of guessing into one line. `PDN.*` and
`NET.REFERENCE_CONTINUITY` both ran first time against real copper and gave
real numbers - 0.219 mV worst rail drop, 16.83 mm worst unreferenced run.
`run.py gates --missing` and `run.py claims` between them make it possible to
ask a board what it has not decided, which is how this round's work started.
