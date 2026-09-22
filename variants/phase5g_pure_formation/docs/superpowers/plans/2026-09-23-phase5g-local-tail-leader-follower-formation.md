# Phase 5G Local-Tail Leader-Follower Formation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the present Phase 5G one-change lane-balancing demo with a replayable, dynamically emitted, communication-free three-lane leader-follower formation that is assembled from the tail by simple local `if/else` rules.

**Architecture:** Keep the online rule boundary inside `noa/simple_formation.py` and `noa/controller.py`: each decision reads one frozen ego observation plus private memory, infers a connected local tail, chooses at most one adjacent lane step, and emits a direct longitudinal acceleration. Extend only the Phase 5G clock/harness, detector, and GUI path to support scheduled actor appearance and offline evidence; schedule truth, fleet truth, and final formation evaluation never enter the controller.

**Tech Stack:** Python 3 standard library, immutable dataclasses, existing kinematic/NOA model, `unittest`, JSONL evidence/replay, SUMO/TraCI GUI playback.

---

## Non-negotiable implementation constraints

- Work from `D:\yanjiu1\keyan1`; variant-local commands run from `D:\yanjiu1\keyan1\variants\phase5g_pure_formation`.
- Use test-driven development for every behavior change: write one focused failing test, run it and confirm the expected failure, implement the smallest behavior, then rerun.
- Never read `case["controlled"]`, departure schedules, simulator IDs, other actors' memory, detector output, or same-tick decisions from controller code.
- Local track labels may only preserve association with a still-visible object. They never break physical ties or determine priority.
- Preserve old result directories. Every experiment and matrix retry receives a new output directory and retains failures.
- Stage only files named by the current task. The worktree contains unrelated untracked research files.
- Use `scripts/run_logged.py` for the long regression and matrix commands, with a finite timeout and retained log.

## Task 1: Replace the simple-rule contract and private memory

**Files:**

- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_rules.py`
- Modify: `variants/phase5g_pure_formation/noa/simple_formation.py`
- Modify: `variants/phase5g_pure_formation/simulation/phase5g_clock.py`

### Step 1: Write the failing contract tests

Replace the old six-parameter/one-lane-change assertions with exact assertions for:

```python
PARAMETERS = (
    "simple_formation_component_gap_m",
    "simple_formation_middle_offset_m",
    "simple_formation_same_lane_gap_m",
    "simple_formation_position_tolerance_m",
    "simple_formation_speed_tolerance_mps",
    "simple_formation_stable_time_s",
    "simple_formation_reference_switch_gain_m",
    "simple_formation_min_lane_change_speed_mps",
    "simple_formation_target_lane_clearance_m",
)

SimpleFormationMemory(
    observation_history=(),
    own_behavior="CRUISE",
    reference_track_id=None,
    join_anchor_track_id=None,
    desired_lane_index=None,
    join_phase="FREE",
    stable_since_s=None,
)
```

Test exact finite-positive validation, the four allowed phases, optional nonnegative local track labels, a desired lane of `0`, `1`, `2`, or `None`, and backward restoration of an old `NoaMemory` row to neutral private fields. Assert there is no `formation_lane_change_done` field.

### Step 2: Run the contract tests and verify RED

Run:

```powershell
cd D:\yanjiu1\keyan1\variants\phase5g_pure_formation
python -m unittest tests.test_simple_formation_rules -v
```

Expected: failures naming the old `simple_formation_local_range_m`, `simple_formation_accel_limit_mps2`, `simple_formation_max_lane_changes`, and missing new memory fields.

### Step 3: Implement the exact immutable contract

In `noa/simple_formation.py`, replace the parameter tuple and memory subtype. Validate with exact numeric types (reject `bool`), finite positive values, phase membership, and optional fields. Keep `memory_from_dict()` backward-compatible only with a base `NoaMemory` row; do not silently translate the obsolete one-change flag into new behavior.

In `simulation/phase5g_clock.py`, validate and restore the new subtype. Update `_LANE_CHANGE_REASONS` to include `simple_formation_join` and remove the obsolete `simple_formation_balance` path only after all writers have migrated.

### Step 4: Run tests and commit

Run the same unittest command. Expected: all contract/memory tests pass; behavior tests may still fail because the old functions remain.

```powershell
git add -- variants/phase5g_pure_formation/noa/simple_formation.py variants/phase5g_pure_formation/simulation/phase5g_clock.py variants/phase5g_pure_formation/tests/test_simple_formation_rules.py
git commit -m "refactor: define local tail formation contract"
```

## Task 2: Implement local component, tail pattern, count recovery, and admission

**Files:**

- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_rules.py`
- Modify: `variants/phase5g_pure_formation/noa/simple_formation.py`

### Step 1: Add focused RED tests for physical rules

Build test fixtures only from `LocalVehicle(track_id, x_m, y_m, vx_mps, lane_index)`. Cover:

- consecutive gaps `<= 50 m` remain connected and `> 50 m` split;
- stable middle tail chooses upper at `tail_x - 15`;
- upper-only tail chooses lower aligned at `tail_x`;
- aligned upper/lower tail chooses middle at `upper_x - 15`;
- malformed tail falls back to least count with physical priority upper, lower, middle (lane indices `2, 0, 1` for ascending centers);
- only the closest unblocked waiting vehicle behind the stable tail is admitted;
- an equal longitudinal position within tolerance favors the physically upper lane;
- unresolved lane or unresolved physical priority returns a wait decision;
- adding a vehicle outside the connected tail does not change the result;
- relabeling every local track consistently does not change target lane, target position, or admission.

Use a decision record with physical outputs, not global slots:

```python
@dataclass(frozen=True, slots=True)
class JoinDecision:
    target_lane_index: int | None
    target_x_m: float | None
    anchor_track_id: int | None
    reason: str
    local_counts: tuple[int, int, int]
```

### Step 2: Run and verify RED

```powershell
python -m unittest tests.test_simple_formation_rules -v
```

Expected: missing `connected_tail_neighborhood`, `infer_tail_join`, and physical admission behavior.

### Step 3: Implement minimal deterministic `if/else` helpers

Implement small pure functions in this order: `connected_tail_neighborhood`,
`lane_counts`, `infer_tail_join`, `is_next_waiting_vehicle`, and
`choose_join`. Each accepts only the ego's physical state, locally reconstructed
`LocalVehicle` rows, visible lane centers, and the validated simple parameter
mapping; each returns an immutable physical result.

Sort only by physical longitudinal coordinate and physical lateral coordinate. Never use `track_id` in a sort key except to retrieve a remembered association after the physical choice is already unique. Tail-pattern recognition takes precedence over count recovery. A two-lane final target is retained in `desired_lane_index`; the returned maneuver target is only the next adjacent index.

### Step 4: Run tests and commit

```powershell
python -m unittest tests.test_simple_formation_rules -v
git add -- variants/phase5g_pure_formation/noa/simple_formation.py variants/phase5g_pure_formation/tests/test_simple_formation_rules.py
git commit -m "feat: add local tail assembly rules"
```

Expected: all local physical-rule tests pass.

## Task 3: Implement reference selection and direct longitudinal formation control

**Files:**

- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_rules.py`
- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_controller.py`
- Modify: `variants/phase5g_pure_formation/noa/simple_formation.py`
- Modify: `variants/phase5g_pure_formation/noa/controller.py`

### Step 1: Add RED tests for leader/follower geometry

Test these exact targets:

- frontmost upper vehicle has no formation reference and targets `TARGET_SPEED_MPS`;
- an upper follower targets the nearest upper vehicle at `30 m`;
- a lower vehicle chooses the visible upper reference whose aligned target has the smallest absolute error;
- a middle vehicle chooses the visible upper reference whose `reference_x - 15 m` target has the smallest absolute error;
- lower/middle fall back to nearest same-lane front vehicle at `30 m` when no valid upper reference exists;
- an active joiner retains its anchor and final target;
- a new reference replaces a visible remembered reference only when target error improves by at least `2 m`;
- a disappeared, invalid, or rearward remembered reference clears immediately;
- direct acceleration uses:

```python
error = target_x_m - ego_x_m
speed_offset = clip(error / 5.0, -2.0, 2.0)
desired_speed = reference_speed_mps + speed_offset
acceleration = clip(desired_speed - ego_speed_mps, -3.0, 2.0)
```

- the direct result replaces, rather than adds to, the base NOA cruise result.

### Step 2: Run and verify RED

```powershell
python -m unittest tests.test_simple_formation_rules tests.test_simple_formation_controller -v
```

Expected: old nearest-front logic and additive `longitudinal_increment()` assertions fail.

### Step 3: Implement reference/target records and direct request

Add immutable `FormationTarget` and pure selectors to `simple_formation.py`. Return a semantic role, target position, reference speed, and local reference label. In `controller.py`, retain `_longitudinal()` only for immediate lead/emergency detection; when the formation target is valid and no immediate emergency is active, set `accel` directly from `formation_acceleration` using the selected target and current ego speed. Leader acceleration is `clip(target_speed - ego_speed, -3, 2)`.

Diagnostics must state `role`, `target_x_m`, `position_error_m`, `reference_track_id`, `reference_reason`, `requested_acceleration_mps2`, and `emergency_override`; exclude global count, slot, optimizer, or game fields.

### Step 4: Run tests and commit

```powershell
python -m unittest tests.test_simple_formation_rules tests.test_simple_formation_controller -v
git add -- variants/phase5g_pure_formation/noa/simple_formation.py variants/phase5g_pure_formation/noa/controller.py variants/phase5g_pure_formation/tests/test_simple_formation_rules.py variants/phase5g_pure_formation/tests/test_simple_formation_controller.py
git commit -m "feat: add direct leader follower control"
```

## Task 4: Replace conservative formation guards with the approved hard gates

**Files:**

- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_controller.py`
- Modify: `variants/phase5g_pure_formation/noa/simple_formation.py`
- Modify: `variants/phase5g_pure_formation/noa/controller.py`

### Step 1: Add RED controller tests

Patch `verify_candidate` to reject and prove that an otherwise valid formation lane change still starts. Separately assert:

- speed `< 5 m/s` blocks a new formation lane change;
- a visible target-lane vehicle with center distance `< 8 m` blocks it;
- exactly `8 m` is permitted when bodies do not overlap;
- target outside visible road is blocked;
- current body overlap or immediate current-lane emergency uses NOA braking;
- an active lateral plan keeps its final lane target when a hard gap appears and applies longitudinal safety response;
- a destination two lanes away completes as two adjacent plans;
- after completing one formation lane change, a later physical decision may start another;
- stability requires continuous lane/position/speed validity for `1 s` and resets on any failed sample.

### Step 2: Run and verify RED

```powershell
python -m unittest tests.test_simple_formation_controller -v
```

Expected: old calls to `verify_candidate`, obsolete one-change completion, and guard diagnostics cause failures.

### Step 3: Implement only the approved gates

Add `target_lane_clear` using current visible, unambiguously lane-associated centers. Do not call `verify_candidate()` from any `simple_active` longitudinal, new-plan, or active-plan branch. Keep vehicle-model clipping and lateral controller bounds unchanged. Retain `memory.plan` until the current adjacent maneuver completes; if `desired_lane_index` differs from the reached lane, re-evaluate the next adjacent step on a later tick.

Update join phases as follows:

```text
FREE -> JOINING when the first adjacent plan/longitudinal join starts
JOINING -> STABILIZING when final lane is reached
STABILIZING -> FORMED after 1 continuous second inside all tolerances
STABILIZING -> JOINING when a tolerance is lost
anchor loss -> FREE with safe same-lane following
```

### Step 4: Run tests and commit

```powershell
python -m unittest tests.test_simple_formation_controller -v
git add -- variants/phase5g_pure_formation/noa/simple_formation.py variants/phase5g_pure_formation/noa/controller.py variants/phase5g_pure_formation/tests/test_simple_formation_controller.py
git commit -m "feat: enforce minimal formation safety gates"
```

## Task 5: Generate deterministic dynamic departure cases

**Files:**

- Modify: `variants/phase5g_pure_formation/tests/test_phase5g_cases.py`
- Modify: `variants/phase5g_pure_formation/experiments/phase5g_cases.py`

### Step 1: Add RED schedule tests

Assert support for counts `3, 4, 5, 6, 7, 8, 12`, byte-identical schedules for equal seeds, changed schedule for a different seed, and exact bounds:

```text
inter-departure interval: 2.5..4.0 s
initial speed: 8.0..12.0 m/s
lane: one of the three physical centers
first departure: 0.0 s
```

Assert every actor row has `scheduled_departure_s`, `actual_departure_s=None`, an exact `VehicleState` template, and a stable offline physical ordinal. `case["initial"]` contains only actors due at time zero; all actors remain in `case["controlled"]` and have independent initial memory. Validate that a future actor is absent from initial collision/gap audits.

### Step 2: Run and verify RED

```powershell
python -m unittest tests.test_phase5g_cases -v
```

Expected: count validation and old all-at-time-zero schema fail.

### Step 3: Implement schedule generation

Replace lane templates and `_bases()` with a seeded sequential departure generator. Quantize scheduled time upward to the `0.1 s` control clock so actor states enter a common frozen frame. Use random choices only offline. Put spawn truth under `case["departures"]`; never add it to policy parameters or observations. Compute minimum valid duration as last scheduled departure plus the 30 s deadline and 10 s hold.

Keep canonical JSON, digest, bundle validation, independent memory creation, and failure-before-write behavior.

### Step 4: Run tests and commit

```powershell
python -m unittest tests.test_phase5g_cases -v
git add -- variants/phase5g_pure_formation/experiments/phase5g_cases.py variants/phase5g_pure_formation/tests/test_phase5g_cases.py
git commit -m "feat: generate replayable dynamic departures"
```

## Task 6: Add dynamic actor activation to the frozen Phase 5G clock and trace

**Files:**

- Modify: `variants/phase5g_pure_formation/tests/test_phase5g_cases.py`
- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_harness.py`
- Modify: `variants/phase5g_pure_formation/simulation/phase5g_clock.py`
- Modify: `variants/phase5g_pure_formation/experiments/phase5g.py`
- Modify: `variants/phase5g_pure_formation/experiments/phase5g_replay.py`

### Step 1: Add RED clock and replay tests

Test a three-actor schedule at `0.0`, `2.5`, and `3.0 s`:

- only the first actor exists before `2.5 s`;
- due actors are installed before the frame is frozen;
- all actors decided on a tick read the same pre-decision world frame;
- no actor sees a same-tick action;
- actor sets only grow and never lose a departed actor;
- `actual_departure_s` is recorded once at activation;
- replay restores the same activation times, decisions, records, and failure boundary;
- pending actors receive no sensor and no decision before activation.

### Step 2: Run and verify RED

```powershell
python -m unittest tests.test_phase5g_cases tests.test_simple_formation_harness -v
```

Expected: `NoaClock`'s fixed actor-set invariant rejects the dynamic fixture.

### Step 3: Implement Phase5G-only activation

Do not weaken `NoaClock` for earlier phases. In `Phase5GClock`, restore all private memories but pass only time-zero actors to the superclass. Before each `super().tick()`:

1. derive current clock time from the active frozen states;
2. activate every due row in stable physical-ordinal order;
3. set the activated state time to the current tick and record that as actual departure;
4. create its `IdealSensor` and install its already-restored private memory;
5. rebuild the active controlled tuple and immutable state mapping;
6. call the unchanged freeze/observe-all/decide-all/integrate-all/commit protocol.

Add `departures` and `active_actors` to each trace record without exposing either to `ControlInput`. Update record validation, physical-row checks, hashes, replay, and metadata to accept monotonic actor subsets instead of requiring the final cohort on every row.

For this dynamic demo, trace generation is the local deterministic model (`live=False`); SUMO is the renderer. Preserve the existing live fixed-case path for historical cases rather than inventing a new online bridge protocol.

### Step 4: Run tests and commit

```powershell
python -m unittest tests.test_phase5g_cases tests.test_simple_formation_harness -v
git add -- variants/phase5g_pure_formation/simulation/phase5g_clock.py variants/phase5g_pure_formation/experiments/phase5g.py variants/phase5g_pure_formation/experiments/phase5g_replay.py variants/phase5g_pure_formation/tests/test_phase5g_cases.py variants/phase5g_pure_formation/tests/test_simple_formation_harness.py
git commit -m "feat: activate scheduled formation vehicles"
```

## Task 7: Replace offline success detection with dynamic per-component evaluation

**Files:**

- Modify: `variants/phase5g_pure_formation/tests/test_phase5_detection.py`
- Modify: `variants/phase5g_pure_formation/experiments/phase5_detection.py`
- Modify: `variants/phase5g_pure_formation/experiments/phase5g.py`

### Step 1: Add RED detector tests

Cover:

- actors appearing over time without `member_missing` before departure;
- component split at a consecutive longitudinal gap `> 50 m` and join at `<= 50 m`;
- lane distributions for counts 3 through 8 and 12;
- upper/lower aligned within `2 m`;
- middle `15 +/- 2 m` behind its corresponding upper;
- same-lane follower gap `30 +/- 2 m`;
- component speed spread `<= 1 m/s`;
- deadline measured from the last actual departure, not recording start;
- continuous 10 s hold after complete formation;
- simultaneous conflicting admission detected from recorded join diagnostics;
- empty, partial, collided, road-departed, missing, teleported, and nonphysical-jump traces fail explicitly.

### Step 2: Run and verify RED

```powershell
python -m unittest tests.test_phase5_detection -v
```

Expected: fixed-cohort and recording-start deadline assertions fail.

### Step 3: Implement independent dynamic evaluation

At every frame, derive physical lanes from `y_m`, sort present centers by `x_m`, split on gaps above `50 m`, and measure each component without reading controller role labels. Match geometry by physical positions, not actor ordinals. Track the complete final cohort only after the last actual departure. Confirm the default intended component by 30 s after that time and require 10 more seconds of uninterrupted validity.

Update `evaluate_trace()` summary fields to include scheduled/actual departure maps, component history, lane counts, maximum geometric errors, speed spread, admission conflicts, and exact failure reasons.

### Step 4: Run tests and commit

```powershell
python -m unittest tests.test_phase5_detection -v
git add -- variants/phase5g_pure_formation/experiments/phase5_detection.py variants/phase5g_pure_formation/experiments/phase5g.py variants/phase5g_pure_formation/tests/test_phase5_detection.py
git commit -m "feat: evaluate dynamic formation components"
```

## Task 8: Update the CLI, GUI replay, and editable `runrun.py`

**Files:**

- Modify: `tests/test_runrun_demo.py`
- Modify: `demo/sumo_gui.py`
- Modify: `runrun.py`
- Modify: `variants/phase5g_pure_formation/run.py`
- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_harness.py`

### Step 1: Add RED entry/GUI tests

Assert the editable defaults are exactly:

```python
VEHICLE_COUNT = 12
TARGET_SPEED_MPS = 10.0
RANDOM_SEED = 1
DEPART_INTERVAL_MIN_S = 2.5
DEPART_INTERVAL_MAX_S = 4.0
INITIAL_SPEED_MIN_MPS = 8.0
INITIAL_SPEED_MAX_MPS = 12.0
FORMATION_JOIN_RANGE_M = 50.0
MIDDLE_LANE_OFFSET_M = 15.0
SAME_LANE_GAP_M = 30.0
MIN_FORMATION_LANE_CHANGE_SPEED_MPS = 5.0
HARD_LANE_CHANGE_GAP_M = 8.0
SIMULATION_DURATION_S = 90.0
```

Test count acceptance for `3..60`, interval/speed ordering, duration after final departure, exact bools, positive finite rule values, and validation before output creation. Verify `runrun.py --check` and editor/debug invocation still use one immutable `SimpleFormationDemoConfig`.

Create a two-frame GUI fixture where the second actor first appears in frame two. Assert `play_algorithm()` calls `vehicle.add()` only at first appearance, never at time zero, and subsequently uses `moveToXY`. Reject actor disappearance, unrecorded appearance, duplicate departure, nonmonotonic time, or state time mismatch before starting SUMO.

### Step 2: Run and verify RED

```powershell
cd D:\yanjiu1\keyan1
python -m unittest tests.test_runrun_demo -v
cd variants\phase5g_pure_formation
python -m unittest tests.test_simple_formation_harness -v
```

Expected: old fixed count/config fields and first-frame actor loading fail.

### Step 3: Implement dynamic entry and playback

Change `SimpleFormationDemoConfig`, strict metadata bindings, subprocess command, and variant CLI arguments to the new fields. Remove `MAX_FORMATION_LANE_CHANGES`, `FORMATION_ACCEL_LIMIT_MPS2`, and the obsolete 90 m local-range setting from the editable path.

In `_preflight_simple_trace()`, validate monotonic actor-set growth against `case["departures"]` and freeze each frame. In `play_algorithm()`, create a vehicle on its first recorded frame, then position it; do not synthesize pre-departure vehicles. Retain replay trust anchors, bounded streaming reads, unique run directories, GUI close handling, and failure-prefix preservation.

Update the startup text to describe a three-lane leader-follower formation, not the old generic staggered/one-change rule.

### Step 4: Run tests and commit

```powershell
cd D:\yanjiu1\keyan1
python -m unittest tests.test_runrun_demo -v
cd variants\phase5g_pure_formation
python -m unittest tests.test_simple_formation_harness -v
cd D:\yanjiu1\keyan1
git add -- runrun.py demo/sumo_gui.py tests/test_runrun_demo.py variants/phase5g_pure_formation/run.py variants/phase5g_pure_formation/tests/test_simple_formation_harness.py
git commit -m "feat: run dynamic formation from runrun"
```

## Task 9: Add the fixed validation matrix and retain every result

**Files:**

- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_harness.py`
- Modify: `variants/phase5g_pure_formation/experiments/phase5g.py`
- Modify: `variants/phase5g_pure_formation/run.py`
- Create: `variants/phase5g_pure_formation/experiments/phase5g_matrix.py`

### Step 1: Add RED matrix-runner tests

Test that the exact matrix is counts `3, 6, 12` crossed with seeds `1..5`, that all 15 runs execute even after an earlier failure, that each gets a unique append-only directory, and that the aggregate reports achieved pass rate and all failure reasons without filtering. Add a separate long-gap case whose two components are both retained and never forcibly merged.

### Step 2: Run and verify RED

```powershell
python -m unittest tests.test_simple_formation_harness -v
```

Expected: matrix command/aggregate is absent.

### Step 3: Implement runner and CLI

`phase5g_matrix.py` calls the same dynamic demo path used by `runrun.py`, always with `live=False`, catches per-run ordinary exceptions only after their failed artifacts are finalized, and writes one aggregate JSON containing run paths, replay status, scientific status, pass count, total count, and failure reasons. Add `phase5g-simple-matrix` to variant `run.py`; do not make it the default GUI path.

### Step 4: Run the unit tests and commit

```powershell
python -m unittest tests.test_simple_formation_harness -v
git add -- variants/phase5g_pure_formation/experiments/phase5g_matrix.py variants/phase5g_pure_formation/experiments/phase5g.py variants/phase5g_pure_formation/run.py variants/phase5g_pure_formation/tests/test_simple_formation_harness.py
git commit -m "feat: retain fixed formation validation matrix"
```

## Task 10: Run focused integration, full regression, and research acceptance

**Files:**

- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_harness.py`
- Modify: `docs/phase5_checkpoint.md`
- Create: `variants/phase5g_pure_formation/docs/phase5g_local_tail_acceptance.md`

### Step 1: Add deterministic integration cases

Add offline integration tests for counts `3, 4, 5, 6, 7, 8, 12` and the long-gap two-component case. Assert collision/road containment, all departures, lane balance, outer alignment, `15/30 m` geometry, speed spread, sequential admission, deadline/hold, and complete evidence. These tests must use the real clock/controller/detector with no patched decisions.

### Step 2: Run focused suites with retained logs

From the variant directory:

```powershell
python ..\..\scripts\run_logged.py --label phase5g_local_tail_focused --timeout 1200 -- python -m unittest tests.test_simple_formation_rules tests.test_simple_formation_controller tests.test_phase5g_cases tests.test_phase5_detection tests.test_simple_formation_harness -v
```

Expected: zero failures/errors and a log path under `tmp`/the configured log location.

From the project root:

```powershell
python scripts\run_logged.py --label runrun_dynamic_gui_tests --timeout 600 -- python -m unittest tests.test_runrun_demo -v
```

Expected: zero failures/errors.

### Step 3: Run the complete variant and root regressions

```powershell
cd D:\yanjiu1\keyan1\variants\phase5g_pure_formation
python ..\..\scripts\run_logged.py --label phase5g_full_regression --timeout 1800 -- python -I -B -S run.py test
cd D:\yanjiu1\keyan1
python scripts\run_logged.py --label repository_full_regression --timeout 1800 -- python -m unittest discover -s tests -v
```

Expected: zero failures/errors. If an inherited unrelated test fails, preserve the complete log, identify it separately, and do not describe the suite as passing.

### Step 4: Run and replay the fixed matrix

```powershell
cd D:\yanjiu1\keyan1\variants\phase5g_pure_formation
python ..\..\scripts\run_logged.py --label phase5g_local_tail_matrix --timeout 3600 -- python -I -B -S run.py phase5g-simple-matrix --offline --output-base results/phase5g/local_tail_matrix
```

Expected scientific result: 15/15 runs pass plus the separate gap case. If fewer pass, retain all run directories and report the exact fraction and failure reasons; do not tune against only failing seeds and rerun under the same evidence label.

### Step 5: Manual default GUI smoke

Run from the project root:

```powershell
python runrun.py --check
python runrun.py
```

Verify that vehicles visibly appear over time, no obstacle vehicles exist, outer heads align, middle heads sit 15 m behind, the lane counts settle to `4/4/4`, and the GUI remains open according to `WAIT_BEFORE_CLOSE`.

### Step 6: Write acceptance and checkpoint evidence

In `variants/phase5g_pure_formation/docs/phase5g_local_tail_acceptance.md`, record:

- exact commit and source hashes;
- each command, exit code, log path, and test count;
- all 15 matrix result paths and the gap-case path;
- achieved pass rate and any retained failure reasons;
- default-run departure schedule, actual departure times, formed time, hold interval, lane counts, maximum geometry errors, speed spread, and collision/teleport counts;
- information-boundary audit proving controller imports and diagnostics contain no schedule/global-slot/global-count truth;
- deviations from the approved design, if any.

Update `docs/phase5_checkpoint.md` with implementation status, tests, failures, and the next entry point.

### Step 7: Final diff/evidence verification and commit

```powershell
git diff --check
git status --short
git add -- docs/phase5_checkpoint.md variants/phase5g_pure_formation/docs/phase5g_local_tail_acceptance.md variants/phase5g_pure_formation/tests/test_simple_formation_harness.py
git commit -m "docs: accept local tail formation research"
```

Do not claim completion until the final diff check, focused suites, replay, matrix, and full regressions have current successful evidence, or the acceptance report explicitly states the retained failures.
