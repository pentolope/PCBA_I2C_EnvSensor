# Toolkit requests from PCBA_I2C_EnvSensor

Written against toolkit `3516aa6`, board `077ac8f` (23 PASS / 13
NOT_APPLICABLE / 0 FAIL, 74 board tests, 3 claims deliberately undecided).

Everything here is board-agnostic: the board supplies parameters and policy,
the toolkit supplies the measurement and the verdict. Each entry states what
this board had to do without it, and what would count as done.

Ordered by what cost the most.

---

## 1. Analytic extraction beyond DC resistance

`extract.py` says plainly that it claims no capacitance and no inductance.
So a board that needs either computes it itself.

This board's bus-capacitance claim - the one the 400 pF I2C budget turns on -
is board-owned microstrip arithmetic in `design/rules.py`
(`microstrip_capacitance_f_per_m`, `bus_track_capacitance`), reading
`pcbqa.transmission_line.microstrip_z0` and a frozen Dk. The toolkit measured
the copper; the board decided what the copper meant. That is the wrong side of
the line: every board with a capacitance, coupling or delay budget will
reimplement this, and each one can get it wrong privately.

**Done when** `extract` emits, per net or per ElectricalPath, capacitance and
inductance per unit length, characteristic impedance and propagation delay,
each as a `pcbqa.claim` record naming its model, the stackup fields consumed,
and the geometry it could not account for. A board should be able to delete
its own microstrip code and keep the same claim.

Depends on a physical stackup being available, which for a 2-layer board it
now is (`compose_two_layer_stackup`).

## 2. Post-layout re-run of a pre-layout scenario

`SIM.STAGE_COVERAGE` checks that each declared stage has a scenario. It cannot
check that a post-layout scenario is *the same question* as its pre-layout
counterpart with extracted interconnect substituted, because nothing links
them.

This board declares four scenarios; only `rail_mating` exists in both stages,
and the pairing is a naming convention, not a fact the toolkit knows. The
scenario whose subject is most geometry-dependent - bus rise time - is
pre-layout only, because the only extractable quantity was resistance.

**Done when** a scenario can declare that it supersedes another with named
extracted models substituted, and a gate reports the pre/post delta per
measurement, failing when a post-layout value crosses a limit its pre-layout
twin met. The interesting artifact is the delta, not the second verdict.

## 3. Assembly process compatibility

There is no gate that reads an assembly policy. This board declares
`ASSEMBLY_POLICY` in `design/netlist.py` with four fields; exactly one
(`max_through_hole_soldered_parts`) is checked, by a board test.

`components/parameters.json` records `OPT3001DNPR.cleaning_recommended = true`
from its datasheet, while the board declares `cleaning_process:
no_clean_no_wash` because the humidity sensor's membrane forbids a wash. That
is a real conflict between a part's stated requirement and the board's stated
process, sitting in committed data, and nothing objects to it. No part records
a peak reflow temperature at all, so "the reflow profile shall suit each
fitted package" - a brief requirement - rests on nothing.

**Done when** a gate takes a board-declared assembly policy (reflow passes,
peak profile, sides, cleaning process, hand-soldered exceptions) and
per-part declared process requirements, and fails on any fitted part whose
requirement the policy violates - with an explicit per-part waiver mechanism,
since "cleaning recommended" is advice and "no wash" is a prohibition, and a
board must be able to say which wins and why.

## 4. Part lifecycle and availability as claims

Nothing in the toolkit records that a part is Active, or that its status could
not be established. Verification here was manual: vendor addenda plus the
JLCPCB parts API.

Nine of ten parts came back Active or buyable. `LPS22HBTR` did not, because
st.com is unreachable from this machine - and there is nowhere to put that.
It is the most expensive line on the BOM and its lifecycle is unknown, and the
board still validates clean, because unknown lifecycle is not a thing the
toolkit can hold. Unknown is not PASS everywhere else in this system.

Stock is the same shape: `C90462` caps this design at 3316 boards, a number
that exists only in my working notes.

**Done when** a board can declare a per-part lifecycle and availability record
with provenance and a retrieval date, frozen the way fabricator evidence is
frozen, and a gate compares declared build quantity against declared stock and
treats an unestablished lifecycle as unknown rather than absent. Live lookup
must not reach a verdict; the freeze is the point.

## 5. A board-facing claim harness

`pcbqa/claim.py` is the right shape and boards cannot easily use it. This one
hand-rolled 757 lines in `design/rules.py`: `_claim`, `_evidence`,
`_requirement`, ten evaluators, `evaluate_all`, `summarise`.

Two consequences. Board claims are not gates - they are asserted by
`tests/test_design.py`, so `validate` and `release-check` never see them.
And the three deliberately-undecided claims live in a Python set named
`ElectricalRules.OPEN` in a test file, which is not board policy in any sense
the toolkit can read. Section 32 requires unresolved claims to be explicitly
permitted or blocking; this board can only express that in a test constant.

**Done when** a board registers evaluators, the toolkit runs them, and a gate
reports the claim matrix - with manifest policy naming which undecided claims
are permitted and which block, so `release-check` refuses a new unknown that
nobody has accepted.

## 6. Generated-board infrastructure the toolkit should own

Three things every generated board needs, all written from scratch here:

- **Canonical PCB serialisation.** KiCad mints random UUIDs and writes objects
  in UUID order, so regenerating a board changes byte order, which changed
  router behaviour and made routing irreproducible. `design/layout.py`
  `canonicalise()` re-sorts and derives every UUID from
  `uuid5(namespace, path + canonical_content_without_uuids)`. This is not
  board-specific in any way.
- **Post-route hygiene.** `ROUTE.GEOMETRY_HYGIENE` judges dangling tracks,
  duplicate geometry and net crossings; nothing fixes them. `design/route.py`
  `tidy()` snaps endpoints onto same-net via centres, prunes dangling tracks
  while protecting load-bearing ones, and splits a track where another ends
  mid-span. Every generated board needs exactly this, and each one will get
  the load-bearing case wrong differently.
- **Deterministic fabrication export.** A no-op rebuild rewrites 11 gerbers
  because KiCad stamps a creation time into each. I had to diff with the
  timestamp filtered out to establish that no copper had moved. A reviewer
  cannot see that at a glance, and neither can a gate.

**Done when** canonicalisation and post-route hygiene are toolkit operations
recording what they changed, and a rebuild that changes no design input
produces byte-identical artifacts.

## 7. Closure staleness should distinguish what changed

`<toolkit>` is a source-closure member, so any toolkit commit invalidates every
committed board artifact in the bench. Correct in principle. In practice one
toolkit change that altered no engineering value required rebuild-and-recommit
on three boards, and the fourth is still release-blocked by it.

The rebuilds were mechanical and their diffs were digests and timestamps. That
is a lot of ceremony to prove nothing changed, and ceremony that expensive
gets skipped.

**Done when** either the closure separates "the implementation moved" from
"the implementation moved in a way that could change this result", or there is
a batch operation that rebuilds and revalidates every board whose only stale
input is the toolkit pin, so the cost of a toolkit commit is one command.

## 8. Make a closure mismatch say what differs

`ARCH.PROVENANCE` reports two digests. `closure.current()` already returns the
member map and the fabrication record keeps only the aggregate.

A rare `test_rebuilding_and_recommitting_makes_it_releasable_again` failure in
the selftest cost a long investigation that ended without a confirmed cause -
the member map would have answered it immediately. Board-side, the same
opacity means "your artifacts are stale" never says which input moved.

**Done when** the fabrication record stores the member map and the gate reports
which members differ, recorded against current.

## 9. Orientation registry: lower the barrier, not the bar

`CPL.ORIENTATION` is the gate that catches a rotated part at assembly, and
this board did not opt in. Three of its ten parts are polarised fine-pitch
sensors where JLCPCB's convention differs from KiCad's - exactly the case the
gate exists for.

The barrier is that the registry must be re-derivable from frozen library
evidence, which is real per-board work, and the gate is all-or-nothing: no
registry, no coverage. So the board with the most to gain opts out.

**Done when** the toolkit can derive candidate offsets from footprint geometry
and part data and emit a reviewable registry for a human to accept, so opting
in costs a review rather than a build.

## 10. Smaller things

- `toolkit_identity()` records a *failed* `git status` as a clean tree:
  `working_tree_dirty` stays `None` and `closure.py` renders `None` as
  `"clean"`. Its own docstring says git being unable to answer is a refusal.
- Gates should never name a layer count. `FAB.LAYER_IDENTITY` claimed "four
  copper layers" in its title and both outcome messages while checking
  whatever the manifest declared; a 2-layer board would have passed with a
  false statement. Fixed in `3516aa6`; worth a hygiene check so it cannot
  return.
- The brief requires a bus scan over the connector finding every fitted device
  at its documented address. That is a PHYSICAL_TEST-class requirement with
  nowhere to be declared, so it is verified by nothing and recorded nowhere.
- JLCPCB's assembly preview is an external, manual release dependency. Section
  25 says such steps should be recorded as dependencies rather than silently
  assumed; there is no place to record one.

---

## Fixed during this board's work

For the maintainer's benefit, so these are not requested twice:

- 2-layer boards had no physical stackup at all - the impedance page publishes
  constructions only for the layer counts JLCPCB offers impedance control on,
  which start at four. The capabilities page states a dielectric constant for
  a 2-layer laminate and nothing read it. Now parsed, and a 2-layer
  construction is composed at the point of use and labelled as composed
  (`a8c0c68`, `65a3b7e`, `e125763`, `3516aa6`).
- `run.py gates` no longer fails when a requirement names alternatives.
