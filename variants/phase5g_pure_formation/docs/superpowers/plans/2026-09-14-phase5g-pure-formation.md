# Phase 5G Pure Formation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a replayable 3/6/12-vehicle pure staggered-formation experiment in which ordinary 100% NOA vehicles may use locally prioritized, fully guarded lane changes, and make the 6-vehicle case the direct-debug SUMO-GUI demonstration.

**Architecture:** Clone the sealed Phase 5F formal source into a new append-only `variants/phase5g_pure_formation` version, but disable the old R5 obstacle/merge path for Phase 5G. Put local target geometry, lexicographic candidate ranking, physical priority, and private backoff in a focused `noa/formation_lane.py`; integrate it into the existing NOA/formation state machine without weakening `verify_candidate`. Add pure-formation case generation, a per-instance private-memory clock, paired experiment/replay runners, independent formation acceptance, and a root `runrun.py` workflow that generates a selected pure case and then displays its trace in SUMO-GUI.

**Tech Stack:** Python 3.12 standard library, `unittest`, immutable dataclasses, existing kinematic bicycle/Bezier/NOA/SUMO/TraCI harness, JSON/JSONL, SHA-256 evidence manifests, PowerShell durable command wrapper.

**Scope lock:** Every Phase 5G physical actor is a normal controlled formation participant. No obstacle vehicle, scripted slow leader, HDV, disturbance actor, bottleneck trigger, or raw SUMO lane/vehicle identifier may enter the controller path; lane priority comes only from the physical lane order reconstructed from visible road geometry.

---

## File map

New Phase 5G implementation files:

- `variants/phase5g_pure_formation/configs/phase5g.json`: exact switches and registered constants.
- `variants/phase5g_pure_formation/noa/formation_lane.py`: pure local geometry, ranking, priority, and private backoff.
- `variants/phase5g_pure_formation/simulation/phase5g_clock.py`: restores sealed per-vehicle Phase 5G memory.
- `variants/phase5g_pure_formation/experiments/phase5g_cases.py`: fixed and seeded feasible pure-formation cases.
- `variants/phase5g_pure_formation/experiments/phase5g.py`: paired runner and Phase 5G summaries.
- `variants/phase5g_pure_formation/experiments/phase5g_replay.py`: semantic replay and tamper rejection.
- `variants/phase5g_pure_formation/tests/phase5g_test_launcher.py`: isolated Phase 5G test selector.
- `variants/phase5g_pure_formation/tests/test_phase5g_lane.py`: local geometry and priority tests.
- `variants/phase5g_pure_formation/tests/test_phase5g_controller.py`: controller/state/safety tests.
- `variants/phase5g_pure_formation/tests/test_phase5g_cases.py`: initial-state and detector tests.
- `variants/phase5g_pure_formation/tests/test_phase5g_harness.py`: runner/replay/evidence tests.

Existing files modified only in the new variant:

- `variants/phase5g_pure_formation/noa/formation.py`: Phase 5G memory fields and pass-through to base NOA.
- `variants/phase5g_pure_formation/noa/controller.py`: optional `formation_geometry` lane-change motivation.
- `variants/phase5g_pure_formation/run.py`: `phase5g`, `phase5g-replay`, and `phase5g-demo` commands.

Root user-facing files:

- `demo/sumo_gui.py`: generate a Phase 5G trace in an isolated subprocess, then play it.
- `runrun.py`: top configuration and direct-debug entry.
- `tests/test_runrun_demo.py`: root demo regression.
- `README.md`: pure-formation demonstration instructions.

Research/evidence files:

- `docs/phase5g_pure_formation_plan.md`: preregistered experimental choices.
- `docs/phase5g_pure_formation_acceptance.md`: final factual acceptance.
- `docs/phase5g_replay_index.md`: exact replay commands and paths.
- `docs/phase5_checkpoint.md`, `docs/phase5_next_entry.md`: recovered state and next unit.

Because the repository has no `HEAD`, do not create an arbitrary initial commit during these tasks. At each checkpoint, write and verify SHA-256 manifests. If a valid `HEAD` is created separately, replace the hash-checkpoint step with the listed `git add` paths and a focused commit; never stage the whole untracked repository implicitly.

### Task 1: Verify Phase 5F and create the isolated Phase 5G source

**Files:**
- Create: `tmp/phase5g_verify_and_clone.py`
- Create: `variants/phase5g_pure_formation/clone_provenance.json`

- [ ] **Step 1: Write the read-only verifier and no-overwrite clone script**

Use these exact bindings in `tmp/phase5g_verify_and_clone.py`:

```python
from hashlib import sha256
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'variants/phase5f_adaptive_duration'
FORMAL = PARENT / 'results/phase5_r5/runs/20260913T162400649059Z_207be322'
FREEZE = PARENT / 'phase5f_source_freeze.json'
DEST = ROOT / 'variants/phase5g_pure_formation'
EXPECTED_FREEZE_SHA256 = '4982d94ee84126df5e80dbe4f8c761185926fd1bbd89f4678ebd4999502acddf'

def digest(path):
    h = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

if digest(FREEZE) != EXPECTED_FREEZE_SHA256:
    raise SystemExit('Phase 5F freeze SHA-256 differs')
frozen = json.loads(FREEZE.read_text(encoding='utf-8'))
for relative, expected in frozen['source_hashes'].items():
    actual = digest(PARENT / relative)
    if actual != expected:
        raise SystemExit(f'Phase 5F source changed: {relative}')
if DEST.exists():
    raise SystemExit(f'refusing existing destination: {DEST}')
shutil.copytree(FORMAL / 'code_snapshot', DEST)
for relative in (
    'scenarios/cai2024/bottleneck.net.xml',
    'docs/noa_staggered_formation_research_plan_2026-09-10.md',
    'docs/parameter_registry.csv',
    'docs/phase4_completion_acceptance.md',
):
    source = FORMAL / 'input_snapshot' / relative
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
for relative in (
    'docs/superpowers/specs/2026-09-14-phase5g-pure-formation-design.md',
    'docs/superpowers/plans/2026-09-14-phase5g-pure-formation.md',
):
    source = ROOT / relative
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
provenance = {
    'schema': 'phase5g_clone_provenance_v1',
    'parent_freeze': FREEZE.relative_to(ROOT).as_posix(),
    'parent_freeze_sha256': digest(FREEZE),
    'formal_source_snapshot': FORMAL.relative_to(ROOT).as_posix(),
    'source_files': len(frozen['source_hashes']),
    'design_sha256': digest(ROOT / 'docs/superpowers/specs/2026-09-14-phase5g-pure-formation-design.md'),
    'plan_sha256': digest(ROOT / 'docs/superpowers/plans/2026-09-14-phase5g-pure-formation.md'),
}
(DEST / 'clone_provenance.json').write_text(
    json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(provenance, ensure_ascii=False))
```

- [ ] **Step 2: Run it through the durable wrapper**

```powershell
python -I -B -S scripts/run_logged.py --label phase5g_verify_clone --timeout 300 -- python -I -B -S tmp/phase5g_verify_and_clone.py
```

Expected: exit 0; `variants/phase5g_pure_formation` is new; its copied source has 119 files before Phase 5G additions; no file under Phase 5F or its results changes.

- [ ] **Step 3: Bind the clone checkpoint**

Create a source manifest using the existing `research.common.code_manifest()` from inside the new variant and save it under a new append-only operation directory. Expected: all entries match the formal `code_snapshot`, except `clone_provenance.json` is explicitly outside the production code manifest.

### Task 2: Preregister Phase 5G parameters and test the pure geometry primitives

**Files:**
- Create: `variants/phase5g_pure_formation/configs/phase5g.json`
- Create: `variants/phase5g_pure_formation/noa/formation_lane.py`
- Create: `variants/phase5g_pure_formation/tests/test_phase5g_lane.py`
- Create: `variants/phase5g_pure_formation/tests/phase5g_test_launcher.py`
- Create: `docs/phase5g_pure_formation_plan.md`

- [ ] **Step 1: Register the immutable values**

Write this exact JSON to `configs/phase5g.json` and bind the same values in the research plan:

```json
{
  "phase5g_enabled": true,
  "formation_lane_change_enabled": true,
  "formation_lane_stable_s": 1.0,
  "formation_lane_lock_s": 5.0,
  "formation_lane_front_margin_m": 2.0,
  "formation_lane_backoff_min_s": 0.5,
  "formation_lane_backoff_max_s": 2.0,
  "formation_lane_duration_candidates_s": [5.0, 7.5, 10.0],
  "formation_lane_min_relation_gain": 1,
  "phase5g_target_speed_mps": 10.0,
  "phase5g_initial_speed_min_mps": 8.0,
  "phase5g_initial_speed_max_mps": 12.0,
  "phase5g_duration_s": 45.0
}
```

`docs/phase5g_pure_formation_plan.md` must state that R5 is disabled, all physical actors are controlled formation participants, official development counts are 3/6/12, and post-result retuning requires a new named version.

- [ ] **Step 2: Write failing geometry tests**

The first test class must contain these assertions:

```python
class Phase5GGeometryTests(unittest.TestCase):
    def test_phase_residual_matches_staggered_lattice(self):
        self.assertAlmostEqual(phase_residual_m(100.0, 0, 115.0, 1, 15.0), 0.0)
        self.assertAlmostEqual(phase_residual_m(100.0, 0, 130.0, 0, 15.0), 0.0)
        self.assertAlmostEqual(phase_residual_m(100.0, 0, 100.0, 2, 15.0), 0.0)
        self.assertAlmostEqual(phase_residual_m(100.0, 0, 112.0, 1, 15.0), 3.0)

    def test_rank_is_lexicographic_and_stay_wins_exact_tie(self):
        stay = LaneCandidate(0, 1.65, 100.0, None, 2, 1.0, 1.5, False)
        change = LaneCandidate(1, 4.95, 115.0, (1.0,) * 7, 3, 1.5, 2.0, True)
        tied_change = LaneCandidate(1, 4.95, 115.0, (1.0,) * 7, 2, 1.0, 1.5, True)
        self.assertIs(rank_candidates((stay, change), minimum_gain=1)[0], change)
        self.assertIs(rank_candidates((stay, tied_change), minimum_gain=1)[0], stay)
```

- [ ] **Step 3: Run the geometry selector and confirm RED**

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1\variants\phase5g_pure_formation'
python -I -B -S tests/phase5g_test_launcher.py lane
```

Expected: nonzero exit because `noa.formation_lane` or its symbols do not exist.

- [ ] **Step 4: Implement the immutable candidate and residual/ranking functions**

Use these public types and signatures:

```python
@dataclass(frozen=True, slots=True)
class LaneCandidate:
    lane_index: int
    target_y_m: float
    target_x_m: float
    reference_signature: tuple[float, ...] | None
    satisfied_relations: int
    max_residual_m: float
    residual_sum_m: float
    changes_lane: bool

def phase_residual_m(ego_x_m, ego_lane, other_x_m, other_lane, d_m):
    delta = (ego_x_m - ego_lane * d_m) - (other_x_m - other_lane * d_m)
    period = 2.0 * d_m
    return abs((delta + period / 2.0) % period - period / 2.0)

def candidate_key(candidate):
    return (-candidate.satisfied_relations, candidate.max_residual_m,
            candidate.residual_sum_m, candidate.changes_lane, -candidate.lane_index)

def rank_candidates(candidates, minimum_gain):
    rows = tuple(candidates)
    stay = min((row for row in rows if not row.changes_lane), key=candidate_key)
    eligible = tuple(row for row in rows if not row.changes_lane or
                     row.satisfied_relations >= stay.satisfied_relations + minimum_gain)
    return tuple(sorted(eligible, key=candidate_key))
```

Validate finite numeric inputs, `d_m > 0`, exact integer lane indices, exact boolean `changes_lane`, and `minimum_gain >= 1`; booleans must not pass as integers.

- [ ] **Step 5: Run the geometry selector and confirm GREEN**

Expected: all `Phase5GGeometryTests` pass with zero skips.

### Task 3: TDD local target generation and physical conflict priority

**Files:**
- Modify: `variants/phase5g_pure_formation/noa/formation_lane.py`
- Modify: `variants/phase5g_pure_formation/tests/test_phase5g_lane.py`

- [ ] **Step 1: Add failing target and priority tests**

Cover these exact public results:

```python
self.assertEqual(target_spacing_m(candidate_lane=1, reference_lane=1, d_m=15.0), 30.0)
self.assertEqual(target_spacing_m(candidate_lane=1, reference_lane=0, d_m=15.0), 15.0)
self.assertIsNone(target_spacing_m(candidate_lane=2, reference_lane=0, d_m=15.0))
self.assertEqual(priority_relation(100.0, 0, 101.0, 1, False, False, 2.0), 'yield_upper_lane')
self.assertEqual(priority_relation(105.0, 0, 100.0, 1, False, False, 2.0), 'ego_visible_front')
self.assertEqual(priority_relation(100.0, 0, 103.0, 1, False, False, 2.0), 'yield_visible_front')
self.assertEqual(priority_relation(100.0, 0, 100.0, 1, True, False, 2.0), 'yield_entered')
self.assertEqual(priority_relation(100.0, 0, 100.0, 1, False, True, 2.0), 'yield_visible_inward_motion')
```

Also test translation invariance, neighbor-order invariance, changed actor labels/hidden types, ambiguous lane association, and two-view antisymmetry for every non-ambiguous pair.

- [ ] **Step 2: Run the lane selector and confirm RED**

Expected: failures name `target_spacing_m`, `visible_lane_candidates`, or `priority_relation`.

- [ ] **Step 3: Implement target generation and priority**

Use this precedence exactly:

```python
def priority_relation(ego_x, ego_lane, peer_x, peer_lane,
                      peer_entered, peer_inward, front_margin_m):
    if peer_entered:
        return 'yield_entered'
    if peer_inward:
        return 'yield_visible_inward_motion'
    if peer_x > ego_x + front_margin_m:
        return 'yield_visible_front'
    if ego_x > peer_x + front_margin_m:
        return 'ego_visible_front'
    if peer_lane > ego_lane:
        return 'yield_upper_lane'
    if ego_lane > peer_lane:
        return 'ego_upper_lane'
    return 'ambiguous'
```

`visible_lane_candidates(control, road, parameters)` must:

1. reconstruct each visible body's physical lane from `road.centers_m` and reject unstable/equidistant association;
2. consider only current and adjacent target lanes;
3. use only forward references and `30 m` same-lane or `15 m` adjacent-lane targets;
4. compute satisfied relation count and residuals against current visible bodies;
5. include one explicit stay candidate;
6. return immutable candidates without calling `verify_candidate` or reading labels/types/IDs.

- [ ] **Step 4: Confirm GREEN and bind a module hash**

Expected: every lane test passes; `rg -n "vehicle.*id|type|intent|global|slot" noa/formation_lane.py` finds no decision input. Save the source SHA-256 in the operation result.

### Task 4: TDD Phase 5G memory, private backoff, and controller integration

**Files:**
- Modify: `variants/phase5g_pure_formation/noa/formation.py`
- Modify: `variants/phase5g_pure_formation/noa/controller.py`
- Modify: `variants/phase5g_pure_formation/noa/formation_lane.py`
- Create: `variants/phase5g_pure_formation/tests/test_phase5g_controller.py`

- [ ] **Step 1: Add failing memory and controller tests**

Require `FormationMemory` to add only these Phase 5G fields:

```python
formation_lane_signature: tuple | None = None
formation_lane_since_s: float | None = None
formation_lane_lock_until_s: float | None = None
formation_lane_rng_state: int | None = None
formation_lane_draw_count: int = 0
formation_lane_backoff_until_s: float | None = None
```

Tests must assert JSON round-trip identity; invalid timestamps and non-`uint64` state rejection; one draw per ambiguous episode; no draw for an unambiguous priority; candidate change resets the 1 s timer; stable candidate reaches `PREPARE_LC`; 5 s lock blocks a reverse; formation off is action-identical to the copied Phase 5F baseline; R5 remains disabled; and `verify_candidate.safe == false` never creates a plan.

- [ ] **Step 2: Run controller tests and confirm RED**

```powershell
python -I -B -S tests/phase5g_test_launcher.py controller
```

Expected: nonzero exit on missing fields and missing `formation_geometry` path.

- [ ] **Step 3: Implement private SplitMix64 backoff**

Use the existing algorithm constants but separate Phase 5G fields:

```python
MASK64 = (1 << 64) - 1

def draw_uniform(state):
    state = (state + 0x9E3779B97F4A7C15) & MASK64
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    word = z ^ (z >> 31)
    return state, word, word / float(1 << 64)
```

The experiment assigns initial states independently of simulator IDs and carries the state with the physical instance during counterfactual relabeling.

- [ ] **Step 4: Pass the complete FormationMemory to base NOA only when Phase 5G is active**

In `noa/formation.py`, preserve the old `_base_memory` behavior unless both `phase5g_enabled` and `formation_lane_change_enabled` are exact `True`. In that enabled path pass the `FormationMemory` instance to `noa.controller.decide`, so its preparation/backoff fields survive; all disabled paths retain copied behavior.

- [ ] **Step 5: Add the formation motivation after higher-priority NOA needs**

In `noa/controller.py`, retain emergency, observed lane end, and real slow-lead decisions ahead of formation. Only when there is no higher-priority motivation, no active plan, no cooldown/lock, and Phase 5G is enabled:

1. build and rank local candidates;
2. evaluate physical competitor priority;
3. maintain/reset the 1 s candidate timer;
4. try durations `5.0`, `7.5`, `10.0` in order using measured ego speed;
5. call unchanged `verify_candidate` for each;
6. commit the first safe duration only at an existing behavior tick;
7. set `lane_change_reason='formation_geometry'`;
8. on completion set `formation_lane_lock_until_s = time_s + 5.0`.

Record candidate geometry, rank key, priority reason, backoff state, every duration guard, selected duration, timer, lock, and fallback in diagnostics.

- [ ] **Step 6: Confirm GREEN and run inherited controller regressions**

Run Phase 5G controller tests, then the inherited Phase 4/5/5C/5F controller classes. Expected: all pass, zero skips; the new path is nonvacuous in at least one test; no old safety assertion is weakened.

### Task 5: Build fixed and seeded pure-formation cases

**Files:**
- Create: `variants/phase5g_pure_formation/experiments/phase5g_cases.py`
- Create: `variants/phase5g_pure_formation/simulation/phase5g_clock.py`
- Create: `variants/phase5g_pure_formation/tests/test_phase5g_cases.py`

- [ ] **Step 1: Write failing case-contract tests**

Require case dictionaries to contain `name`, `duration_s`, `initial`, `controlled`, `scripts`, `initial_memories`, `private_rng_provenance`, `purpose`, and `expected_lane_changes`. Assert:

- all physical actors are controlled and `scripts == {}`;
- supported counts are exactly 3, 6, and 12;
- the main 6-car distribution is `[3, 2, 1]` before formation and expected `[2, 2, 2]` after success;
- every initial body is nonoverlapping and passes the dynamic minimum-gap checker;
- the first frame does not satisfy whole-cohort detection;
- repeated seed generation is byte-identical;
- unsupported counts and invalid speeds fail before writing a bundle;
- changing actor keys while carrying physical states/memories together does not change the generated physical rows.

- [ ] **Step 2: Run case tests and confirm RED**

Expected: missing `experiments.phase5g_cases` and `simulation.phase5g_clock` failures.

- [ ] **Step 3: Implement fixed cases and feasible seeded generation**

Use the visible upstream centers `(1.65, 4.95, 8.25)`, duration 45 s, and these fixed main rows:

```python
MAIN_SIX = (
    ('v0', 100.0, 1.65, 10.0),
    ('v1', 145.0, 1.65, 9.5),
    ('v2', 190.0, 1.65, 10.5),
    ('v3', 122.0, 4.95, 10.5),
    ('v4', 167.0, 4.95, 9.5),
    ('v5', 108.0, 8.25, 10.0),
)
```

Before freezing, the case test must independently verify that this exact set is collision-free and not already a detected whole formation. If it fails either property, stop and revise the design document before changing the rows; do not tune them after viewing a successful/failed formal trajectory.

For seeded 3/6/12 rows, use `random.Random(seed)`, fixed lane-count templates `(1,1,1)`, `(3,2,1)`, `(4,4,4)`, longitudinal bases spaced at least 36 m within `[80, 260]`, bounded jitter `[-4,4] m`, and speeds uniformly in `[8,12] m/s`. Reject/resample the complete set if swept body overlap, dynamic-gap failure, or initial detector success occurs; cap attempts at 1000 and raise a descriptive error.

- [ ] **Step 4: Restore per-instance Phase 5G memory**

`Phase5GClock` must subclass `FormationClock`, require `clock_schema='phase5g_pure_formation_v1'`, validate exact actor keys and full `FormationMemory` fields, and restore a separate immutable memory per controlled vehicle when formation is enabled. In `off` mode it must require every Phase 5G field in the frozen memory to have its neutral default, then construct `NoaMemory` from inherited fields only. It must reject shared object identity, missing seeds in `lane_priority` mode, boolean seeds, extra fields, hash mismatch, and schema mismatch.

- [ ] **Step 5: Confirm GREEN and freeze development/holdout seeds**

Freeze development seeds `[101, 102, 103]` and holdout seeds `[5101, 5102, 5103, 5104, 5105]` in `phase5g_cases_frozen.json` before any holdout execution. Expected: exact reload reproduces all bytes and rejects a resealed generator/source/physical mutation.

### Task 6: Build the paired runner, independent acceptance, and replay

**Files:**
- Create: `variants/phase5g_pure_formation/experiments/phase5g.py`
- Create: `variants/phase5g_pure_formation/experiments/phase5g_replay.py`
- Create: `variants/phase5g_pure_formation/tests/test_phase5g_harness.py`
- Modify: `variants/phase5g_pure_formation/run.py`

- [ ] **Step 1: Write failing harness tests**

Tests must require exactly three modes:

```python
MODES = {
    'off': {'formation_enabled': False, 'formation_lane_change_enabled': False},
    'longitudinal': {'formation_enabled': True, 'formation_lane_change_enabled': False},
    'lane_priority': {'formation_enabled': True, 'formation_lane_change_enabled': True},
}
```

Assert identical physical input and model/safety/perception parameters across modes; R5 false in every mode; result directories never overwrite; partial failures retain case index and trace prefix; replay recomputes decisions, integrations, detection, lane changes, speed recovery, and final acceptance; and resealed mode/config/source/memory/action/detection tampering is rejected.

- [ ] **Step 2: Run harness tests and confirm RED**

Expected: missing runner/replay/CLI failures.

- [ ] **Step 3: Implement runner parameters and summaries**

`parameters(mode, target_speed_mps=10.0)` must merge existing kinematic/Phase 3/Phase 4/Phase 5 settings with `configs/phase5g.json`, set `r5_enabled=False`, and validate the exact mode before creating a `RunRecord`.

For every variant, save:

```python
{
    'whole_cohort_formation_success': detection['whole_cohort_success'],
    'formed_time_s': formed_time,
    'held_time_s': held_time,
    'completed_lane_changes': completed_lane_changes,
    'formation_lane_changes': formation_lane_changes,
    'final_lane_counts': final_lane_counts,
    'minimum_speed_mps': minimum_speed,
    'final_speed_spread_mps': final_speed_spread,
    'speed_recovered': speed_recovered,
    'collision_count': collision_count,
    'geometry_passed': geometry_passed,
    'comfort_passed': comfort_passed,
}
```

The main 6-car `lane_priority` variant passes scientifically only when all design success conditions hold, including `[2,2,2]`, at least one formation-requested completed lane change, formation by 30 s, and the 10 s post-confirmation hold. An `off` or `longitudinal` success remains factual and must not be hidden.

- [ ] **Step 4: Add isolated CLI commands**

Extend `run.py` choices with `phase5g`, `phase5g-replay`, `phase5g-formal`, and `phase5g-demo`. Require an explicit frozen `--case-file` for `phase5g` and `phase5g-formal`, explicit `--run-dir` for replay, and validated `--vehicle-count`, `--seed`, `--target-speed-mps`, `--duration-s`, and `--output-base` for demo. `phase5g-formal` must call `run_phase5g()` once and pass its returned literal `Path` directly to `replay_run()`; it exits nonzero unless replay passes and never resolves through `latest.json` or directory time. `phase5g-demo` runs only one `lane_priority` case and labels it non-formal.

- [ ] **Step 5: Implement semantic replay and confirm GREEN**

Replay must use the saved code/input source, restore every own memory, reproduce only produced evidence for partial records, and compare floats under inherited replay tolerances. Expected: all Phase 5G harness tests pass; a one-field tamper fails with the exact path named.

### Task 7: Make `runrun.py` directly generate and display pure formation

**Files:**
- Modify: `demo/sumo_gui.py`
- Modify: `runrun.py`
- Modify: `tests/test_runrun_demo.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing root demo tests**

Replace the old default assertions with:

```python
self.assertEqual(runrun.VEHICLE_COUNT, 6)
self.assertEqual(runrun.RANDOM_SEED, 1)
self.assertEqual(runrun.TARGET_SPEED_MPS, 10.0)
self.assertTrue(runrun.ALLOW_LANE_CHANGE)
self.assertEqual(runrun.SIMULATION_DURATION_S, 45.0)
```

Add tests that 3/6/12 are accepted, other counts fail before subprocess launch, `--check` does not launch GUI or the experiment, normal `main([])` calls `run_pure_formation_demo` directly without a menu, child nonzero exit is preserved in metadata, generated trace is hash-verified before playback, and a user-closed GUI remains a clean `user_closed` result.

- [ ] **Step 2: Run root tests and confirm RED**

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -I -B -S scripts/run_logged.py --label phase5g_runrun_red --timeout 180 -- python -I -B -S -m unittest tests.test_runrun_demo -v
```

Expected: nonzero exit because the new config fields and direct workflow do not exist.

- [ ] **Step 3: Extend `DemoConfig` and add `run_pure_formation_demo`**

The workflow must:

1. validate SUMO-GUI, network, variant `run.py`, count, seed, speed, duration, and GUI delay;
2. allocate a timestamp-and-token path such as `results/demo_runs/20260914T120000000000Z_deadbeef` before launching anything;
3. invoke the Phase 5G variant in an isolated subprocess with the exact top-level values;
4. save child stdout/stderr, command, return code, config snapshot, and source hashes;
5. parse the child-emitted run path and verify its `evidence_hashes.json`;
6. load the generated case trace and play it through the existing owned GUI session;
7. preserve `completed`, `failed`, `interrupted`, or `user_closed` without overwriting an earlier attempt.

Use `subprocess.run` for trace generation and the existing `OwnedGuiSession` for playback; never import the variant's `noa` package into the root interpreter.

- [ ] **Step 4: Simplify `runrun.py` to a direct debug entry**

Use this top configuration exactly:

```python
VEHICLE_COUNT = 6
RANDOM_SEED = 1
TARGET_SPEED_MPS = 10.0
ALLOW_LANE_CHANGE = True
SIMULATION_DURATION_S = 45.0
GUI_DELAY_MS = 50
START_PAUSED = False
AUTO_ZOOM = True
WAIT_BEFORE_CLOSE = True
```

`main([])` prints the configuration and calls `run_pure_formation_demo`; `main(['--check'])` performs read-only checks; all other flags raise `ValueError`. Keep `_debug_friendly_entry()` UTF-8 and friendly Chinese error behavior.

- [ ] **Step 5: Confirm GREEN and update README**

Expected: all `tests.test_runrun_demo` tests pass. README must explain that the demo computes a new non-formal Phase 5G run from the top constants, then opens SUMO-GUI to display it; it must not describe the trace as a live LLM controller or formal scientific run.

### Task 8: Run affected regression and freeze the tested source

**Files:**
- Create: `variants/phase5g_pure_formation/phase5g_source_freeze.json`

- [ ] **Step 1: Run Phase 5G tests through the durable wrapper**

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1\variants\phase5g_pure_formation'
python -I -B -S scripts/run_logged.py --label phase5g_unit_integration --timeout 900 -- python -I -B -S tests/phase5g_test_launcher.py all
```

Expected: every new test passes with zero failure/error/skip.

- [ ] **Step 2: Run the affected inherited suite**

Select all inherited motion, NOA, formation, R5, records, detection, replay, and Phase 5C/5F tests affected by the changed files. Expected: at least the 240 tests in the Phase 5F freeze plus every new Phase 5G test; zero failure, zero error, zero skip.

- [ ] **Step 3: Re-run root demo tests and static information-boundary audit**

Run `tests.test_runrun_demo`, then scan production decision modules for filesystem, simulator-ID, type, intent, communication, global list, and slot-table access. Expected: root tests pass and no forbidden controller input is found.

- [ ] **Step 4: Freeze only after source stability is proven**

Create `phase5g_source_freeze.json` containing selected test IDs/counts, command/result hashes, every production/test/config source hash, parent clone hash, design hash, plan hash, and changed-file list. Recalculate the manifest after writing it and require the production source to remain unchanged before any formal run.

### Task 9: Execute fixed development gates and freeze formal inputs

**Files:**
- Create: append-only directories under `variants/phase5g_pure_formation/results/phase5g/development`
- Create: `variants/phase5g_pure_formation/phase5g_cases_frozen.json`

- [ ] **Step 1: Run the offline six-car geometry audit**

Verify the initial main case is safe, not already formed, and contains locally generated stay/change candidates. Verify a hand-constructed ideal 2/2/2 terminal frame passes the unchanged independent detector. Expected: both negative-initial and positive-target checks pass before vehicle execution.

- [ ] **Step 2: Run fixed 3/6/12 development cases**

```powershell
python -I -B -S scripts/run_logged.py --label phase5g_fixed_development --timeout 3600 -- python -I -B -S run.py phase5g --case-file phase5g_cases_development.json
```

Expected engineering gate: all three modes finish or retain explicit failure prefixes; no collision/teleport/abnormal disappearance. Scientific gate: the main 6-car lane-priority mode meets every success condition. If it does not, stop before holdout, preserve the run, diagnose one mechanism, and write a new approved design version before changing registered rules or numbers.

- [ ] **Step 3: Freeze formal cases only after the fixed gate passes**

Write `phase5g_cases_frozen.json` with the fixed cases, development seeds `[101,102,103]`, holdout seeds `[5101,5102,5103,5104,5105]`, full private memories, generator/source/config hashes, and the exact three-mode registry. Loader must reproduce identical bytes and reject overwrite.

### Task 10: Run formal paired packages, replay, and acceptance

**Files:**
- Create: append-only formal runs under `variants/phase5g_pure_formation/results/phase5g/runs`
- Create: append-only replays under `variants/phase5g_pure_formation/results/phase5g/replays`
- Create: `docs/phase5g_pure_formation_acceptance.md`
- Create: `docs/phase5g_replay_index.md`
- Modify: `docs/phase5_checkpoint.md`
- Modify: `docs/phase5_next_entry.md`
- Modify: `README.md`

- [ ] **Step 1: Execute the frozen matrix and its exact replay once**

```powershell
python -I -B -S scripts/run_logged.py --label phase5g_formal_and_replay --timeout 14400 -- python -I -B -S run.py phase5g-formal --case-file phase5g_cases_frozen.json
```

Expected: one immutable run package binds source, cases, modes, parameters, private states, SUMO/TraCI, commands, all traces, failure prefixes, detection, lane changes, speed recovery, geometry, comfort, and conclusion. The same process emits its literal run/replay paths, and semantic replay passes every produced record and derived summary.

- [ ] **Step 2: Run the direct-debug smoke check**

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -I -B -S runrun.py --check
```

Expected: exit 0; reports SUMO-GUI, the Phase 5G variant, supported count, network, and TraCI source without starting a process. Then perform one user-visible `runrun.py` GUI smoke run and save its metadata; closing the window is not a scientific failure.

- [ ] **Step 3: Write factual acceptance and recovery entry**

The acceptance report must distinguish engineering delivery, fixed main-case success, holdout success rate, 3/12-car observations, baseline/longitudinal/lane-priority differences, safety/comfort, and limitations. It must state Phase 5 failure if the 6-car main case or required replay fails; one successful illustration is not a general guarantee.

`phase5_checkpoint.md` must bind the source/case/run/replay/acceptance hashes and point to one next unit. `phase5_next_entry.md` must not reopen obstacles, HDV, or bottleneck work unless the user separately authorizes that scope.

- [ ] **Step 4: Record Git state without staging unrelated files**

Run:

```powershell
git remote -v
git status --short --branch
```

Expected: origin remains `https://github.com/32780542/biyesheji1`; because no initial `HEAD` exists, report hash-frozen deliverables rather than claiming a commit or push. If a `HEAD` has been created independently, stage only the Phase 5G paths enumerated in this plan and commit with `feat: add pure formation lane priority experiment`.

## Stop conditions

Stop and preserve evidence instead of continuing when any of these occurs:

- the Phase 5F freeze or formal source differs before clone;
- the fixed main 6-car case is initially formed or physically unsafe;
- controller output depends on actor label, hidden type, SUMO lane ID, other memory, or update order;
- a candidate bypasses `verify_candidate` or alters its envelope;
- the fixed main 6-car lane-priority case fails the scientific gate;
- a formal input/source changes after freeze;
- replay cannot reconstruct a produced trace or derived conclusion.

Any rule, threshold, initial row, seed split, duration set, detector condition, or safety change after one of these failures requires a new named design/specification cycle. Preserve the failed package and never reuse its directory.
