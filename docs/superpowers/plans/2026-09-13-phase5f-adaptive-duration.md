# Phase 5F Speed-Adaptive Duration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one explicitly switchable 5/7.5/10 s low-speed lane-change candidate mechanism that uses measured speed, duration-specific kinematic floors, the actual-duration R5 horizon, and the unchanged full safety guard, then evaluate and replay it without promoting Stage 6.

**Architecture:** Hash-check and clone the sealed Phase 5E formal snapshot into `variants/phase5f_adaptive_duration`. Put deterministic duration/floor mathematics in `noa/low_speed.py`; retain a fixed compatibility path and activate the new path only for R5 plus visible lane priority. Extend the existing R5 runner/replay with an exact `fixed|adaptive_duration` policy binding, run same-source fixed/adaptive controls, and freeze all negative as well as positive outcomes.

**Tech Stack:** Python 3.12 standard library, `unittest`, existing kinematic/Bezier/NOA/SUMO harness, JSON and SHA-256 evidence manifests.

---

### Task 1: Verify Phase 5E and create the isolated Phase 5F source

**Files:**
- Create: `tmp/phase5f_verify_parent.py`
- Create: `tmp/phase5f_clone.py`
- Create: `variants/phase5f_adaptive_duration/clone_provenance.json`

- [ ] **Step 1: Write the read-only parent verifier**

The verifier must recalculate the exact manifests for:

```python
COMPLETION = ROOT / 'results/phase5e/completion_20260913T124834184236Z'
RUN = ROOT / 'variants/phase5e_exact_endpoint/results/phase5_r5/runs/20260913T121814146616Z_12a1dc15'
REPLAY = ROOT / 'variants/phase5e_exact_endpoint/results/phase5_r5/replays/20260913T122921286694Z_13a9cac5'
COMPARISON = ROOT / 'results/phase5e/comparison_20260913T1244_exact_endpoint_final'
```

It must require the known manifest SHA-256 values, 114-source equality, 17 replay cases, retained four failed prefixes including `r5_speed_floor_r5_off`, `scientific_accepted=false`, and `phase6_allowed=false`.

- [ ] **Step 2: Run the parent verifier through the durable logger**

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_parent_prerequisites --timeout 180 -- python -I -B -S tmp/phase5f_verify_parent.py
```

Expected: exit 0, no writes under `variants/phase5e_exact_endpoint` or old result packages.

- [ ] **Step 3: Clone the formal code/input snapshot without overwrite**

`tmp/phase5f_clone.py` must refuse an existing destination, copy every file from the sealed 5E run's `code_snapshot`, restore its `input_snapshot`, copy the separately frozen `phase5c_extension.json` with SHA `a21f8a4782955c4fab47ed91218b51f621f8a4d795b2d307b27f986aca4e682a`, and record source, input, case, plan, and clone-script hashes.

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_isolated_snapshot --timeout 180 -- python -I -B -S tmp/phase5f_clone.py
```

Expected: exit 0, new `variants/phase5f_adaptive_duration`, exact 114-file parent source, and no Git worktree because the repository has no `HEAD`.

### Task 2: Freeze the pre-implementation sweep and research registration

**Files:**
- Create: `tmp/phase5f_parent_sweep.py`
- Create: `docs/phase5f_adaptive_duration_plan.md`
- Create: `results/phase5f/parent_sweep_preregistered_20260913/sweep.json`

- [ ] **Step 1: Register the immutable research choices**

The plan must bind:

```json
{
  "lane_change_policy": ["fixed", "adaptive_duration"],
  "duration_candidates_s": [5.0, 7.5, 10.0],
  "selection": "shortest candidate passing model floor, R5 gate, and verify_candidate",
  "zero_speed": "reject",
  "neighbor_reachability": "unchanged",
  "safety_guard": "unchanged verify_candidate"
}
```

It must include the exact derived floors `1.3034431025565734`, `0.8689620683710490`, and `0.6517215512782867` m/s and prohibit post-result retuning.

- [ ] **Step 2: Reconstruct actual saved low-speed controls**

Use `experiments.phase5_r5_audit._control`, `noa.road.reconstruct`, `_longitudinal`, `r5.assess_candidate`, and `verify_candidate` on the sealed three-vehicle traces. Select the documented clear-speed records closest to 0.03235983596892728, 1.7011622665415613, and 1.849397485095146 m/s, plus saved records closest to 4.511 and 5.0 m/s. Do not mutate memory or execute `decide`.

- [ ] **Step 3: Run and seal the sweep before production edits**

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_parent_low_speed_sweep --timeout 300 -- python -I -B -S tmp/phase5f_parent_sweep.py
```

Expected: one append-only result containing, for every state and duration, the measured state hash, derived floor, peak reference acceleration, R5 reason/blocking state, guard reason, requested longitudinal acceleration, and safe boolean. No success is required.

### Task 3: TDD the deterministic low-speed candidate mathematics

**Files:**
- Create: `variants/phase5f_adaptive_duration/tests/test_phase5f_low_speed.py`
- Create: `variants/phase5f_adaptive_duration/tests/phase5f_test_launcher.py`
- Create: `variants/phase5f_adaptive_duration/noa/low_speed.py`
- Create: `variants/phase5f_adaptive_duration/configs/phase5f.json`

- [ ] **Step 1: Write failing mathematical boundary tests**

Create a launcher that inserts the variant root into `sys.path`, changes to the variant root, and maps the exact arguments `math`, `controller`, and `harness` to the corresponding Phase 5F test classes. The tests must import the wished-for API:

```python
from noa.low_speed import candidate_profiles, peak_reference_lateral_accel, steering_speed_floor

self.assertAlmostEqual(peak_reference_lateral_accel(5., self.p), .528)
self.assertAlmostEqual(steering_speed_floor(5., self.p), 1.3034431025565734)
self.assertEqual([x['duration_s'] for x in candidate_profiles(1.7, self.p)], [5., 7.5, 10.])
self.assertEqual(candidate_profiles(.65, self.p), [])
self.assertEqual(candidate_profiles(0., self.p), [])
```

Also require finite, positive, strictly increasing durations, the first duration equal to the inherited 5 s value, and every peak below `comfort_lateral_accel_mps2`.

- [ ] **Step 2: Run RED and confirm missing-module/API failures**

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1\variants\phase5f_adaptive_duration'
python -I -B -S scripts/run_logged.py --label phase5f_low_speed_math_red --timeout 120 -- python -I -B -S tests/phase5f_test_launcher.py math
```

Expected: nonzero because `noa.low_speed` does not exist, not because of test collection or import-path errors.

- [ ] **Step 3: Implement only the tested mathematics**

```python
def peak_reference_lateral_accel(duration_s, p):
    return 4.0 * p['lane_width_m'] / duration_s**2

def steering_speed_floor(duration_s, p):
    return math.sqrt(
        peak_reference_lateral_accel(duration_s, p)
        * p['wheelbase_m'] / math.tan(p['max_steering_rad'])
    )

def candidate_profiles(speed_mps, p):
    if speed_mps <= 0.:
        return []
    result = []
    for duration in validated_durations(p):
        peak = peak_reference_lateral_accel(duration, p)
        floor = steering_speed_floor(duration, p)
        if peak <= p['comfort_lateral_accel_mps2'] and speed_mps >= floor:
            result.append({'duration_s': duration, 'speed_floor_mps': floor,
                           'peak_reference_lateral_accel_mps2': peak})
    return result
```

- [ ] **Step 4: Run GREEN**

Run the same launcher. Expected: all mathematical tests pass, with no warning or skip.

### Task 4: TDD controller selection and actual-duration R5 assessment

**Files:**
- Modify: `variants/phase5f_adaptive_duration/tests/test_phase5f_low_speed.py`
- Modify: `variants/phase5f_adaptive_duration/noa/controller.py`
- Modify: `variants/phase5f_adaptive_duration/noa/r5.py`

- [ ] **Step 1: Write failing controller tests**

Using the real Phase 5C/R5 fixtures and `unittest.mock.patch`, require:

```python
self.assertEqual(selected_plan.duration_s, 7.5)  # 5 s guard rejected, 7.5 s safe
self.assertEqual(selected_plan.speed_mps, control.ego.vx_mps)
self.assertIsNone(all_rejected.memory.plan)
self.assertIsNone(all_rejected.memory.prepare_since_s)
```

Capture every `verify_candidate` plan and assert durations are visited in ascending order until the first safe candidate. Test that 1.7 and 1.85 m/s can reach the guard, zero and sub-floor speeds cannot, fixed mode never reaches the adaptive branch, and R5-off/lane-priority-off decisions equal the sealed fixed behavior.

- [ ] **Step 2: Write the failing R5 horizon test**

Construct the same local observation with two candidates differing only in duration. Put a relative-speed participant outside the 5 s radius but inside the 10 s radius and assert `assess_candidate` includes it only for the 10 s candidate.

- [ ] **Step 3: Run RED**

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_controller_red --timeout 180 -- python -I -B -S tests/phase5f_test_launcher.py controller
```

Expected: assertions fail because the old 5 m/s gate prevents low-speed construction and `r5.py` uses the fixed duration.

- [ ] **Step 4: Implement the minimal switched path**

Add `diagnostics['candidate_evaluations'] = []`. Define the enabled condition exactly as:

```python
adaptive = (p.get('phase5f_enabled', False) and r5_enabled
            and p.get('r5_lane_priority_enabled', False))
```

For fixed mode keep the existing single 5 s candidate with `max(ego.vx_mps, noa_min_lane_change_speed_mps)`. For adaptive mode iterate `candidate_profiles(ego.vx_mps, p)`, construct each plan with measured positive speed, call the current R5 advance/gate and unchanged `verify_candidate`, append complete diagnostics, and stop at the first safe candidate. Do not change `_longitudinal`, active-plan verification, emergency behavior, safety parameters, or formation code.

In `r5.assess_candidate`, replace only:

```python
abs(b.vx-evx) * p['noa_lane_change_duration_s']
```

with:

```python
abs(b.vx-evx) * candidate.duration_s
```

- [ ] **Step 5: Run GREEN and compatibility tests**

Run the controller launcher, then the inherited Phase 5E endpoint, Phase 5C priority, Phase 5D waiting-game, and R5 controller tests. Expected: zero failures/errors/skips; fixed decisions remain exact.

### Task 5: TDD exact runner, CLI, input, and replay binding

**Files:**
- Create: `variants/phase5f_adaptive_duration/tests/test_phase5f_harness.py`
- Modify: `variants/phase5f_adaptive_duration/experiments/phase5_r5.py`
- Modify: `variants/phase5f_adaptive_duration/experiments/phase5_r5_replay.py`
- Modify: `variants/phase5f_adaptive_duration/run.py`

- [ ] **Step 1: Write failing harness tests**

Require `lane_change_policy` in `parameters`, `run_phase5_r5`, and metadata; accept only `fixed` and `adaptive_duration`; bind `configs/phase5f.json`, the design, implementation plan, and `docs/phase5f_adaptive_duration_plan.md` in `INPUTS`; enable Phase 5F only for R5-on plus lane-priority-on; and require replay to reject a resealed metadata/index/policy mutation.

- [ ] **Step 2: Run harness RED**

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_harness_red --timeout 180 -- python -I -B -S tests/phase5f_test_launcher.py harness
```

Expected: failure because the new CLI/policy/input binding is absent.

- [ ] **Step 3: Implement the exact policy binding**

Use these signatures:

```python
def parameters(enabled, lane_priority=True, waiting_policy='fixed', lane_change_policy='fixed'):
def expected_variants(cases, sampling, waiting_policy='fixed', lane_change_policy='fixed'):
def run_phase5_r5(case_file, base=None, live=True, sampling=True,
                  waiting_policy='fixed', lane_change_policy='fixed'):
```

Store `lane_change_policy` in top metadata and each applicable expected-variant spec. Replay must read the source metadata, rebuild the same expected variants and parameters, and compare them exactly. `run.py` must expose `--lane-change-policy fixed|adaptive_duration` with default `fixed`.

- [ ] **Step 4: Run harness GREEN**

Expected: unit round-trip and all tamper cases pass, no skip.

### Task 6: Run affected regression and freeze tested source

**Files:**
- Create: `tmp/phase5f_regression.py`
- Create: `variants/phase5f_adaptive_duration/phase5f_source_freeze.json`

- [ ] **Step 1: Select all affected inherited tests**

The selector must include the new math/controller/harness tests and inherited controller, priority, R5, record, case, replay, formation, and endpoint tests. It must reject an empty/duplicate selection, create the variant-local `tmp`, record every test ID, and hash source before and after.

- [ ] **Step 2: Run the affected suite once**

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_affected_regression --timeout 1200 -- python -I -B -S tmp/phase5f_regression.py
```

Expected: exit 0, zero failure/error/skip and identical source before/after. Any fixture or compatibility failure is retained in its first attempt and corrected with a new wrapper directory.

- [ ] **Step 3: Freeze the successful source**

Copy the successful attempt manifest to `phase5f_source_freeze.json` only if every selected test passed and current source still matches it. Because Git has no `HEAD`, this hash freeze replaces unavailable commit checkpoints.

### Task 7: Execute the three formal packages and semantic replays

**Files:**
- Create: the append-only `RunRecord` directory printed by each command under `variants/phase5f_adaptive_duration/results/phase5_r5/runs`
- Create: the append-only `RunRecord` directory printed by each replay under `variants/phase5f_adaptive_duration/results/phase5_r5/replays`

- [ ] **Step 1: Run the same-source fixed extension control**

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_extension_fixed --timeout 1800 -- python -I -B -S run.py phase5-r5 --case-file phase5c_extension.json --lane-change-policy fixed
```

- [ ] **Step 2: Run the adaptive extension**

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_extension_adaptive_duration --timeout 1800 -- python -I -B -S run.py phase5-r5 --case-file phase5c_extension.json --lane-change-policy adaptive_duration
```

- [ ] **Step 3: Run the adaptive original eight-case set**

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_original_adaptive_duration --timeout 1800 -- python -I -B -S run.py phase5-r5 --case-file parent_frozen_r5_cases.json --lane-change-policy adaptive_duration
```

Every native collision, teleport, comfort failure, incomplete case, or guard rejection remains in the package. Do not tune after any of these runs.

- [ ] **Step 4: Standard-replay every package**

For each exact run path returned by Steps 1--3, assign its absolute value to `$RUN_PATH`, and use a distinct literal label (`phase5f_semantic_replay_extension_fixed`, `phase5f_semantic_replay_extension_adaptive`, or `phase5f_semantic_replay_original_adaptive`):

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_semantic_replay_extension_fixed --timeout 1800 -- python -I -B -S run.py phase5-r5-replay --run-dir $RUN_PATH
```

Expected: all started variants reconstruct semantically, source before equals source after, and failed prefixes remain failed prefixes.

### Task 8: Compare, report, and bind the final delivery

**Files:**
- Create: `tmp/phase5f_compare.py`
- Create: `tmp/phase5f_save_acceptance.py`
- Create: `docs/phase5f_adaptive_duration_acceptance.md`
- Create: `docs/phase5f_replay_index.md`
- Modify: `docs/phase5_next_entry.md`
- Modify: `docs/phase5_checkpoint.md`
- Create: the append-only timestamped completion directory returned by `tmp/phase5f_save_acceptance.py` under `results/phase5f`

- [ ] **Step 1: Build the exact paired comparison**

Bind the fixed/adaptive extension and 5E/adaptive-original run/replay manifests. Report all pre-registered candidate, guard, plan, completion, speed, comfort, tracking, warning, failure-prefix, and formation fields. Full-window metrics are `null` when either side is incomplete.

- [ ] **Step 2: Write acceptance and replay documents**

State separately: implementation/test delivery, candidate feasibility, actual vehicle completion, formation/recovery evidence, scientific acceptance, and Phase 6 authorization. Include exact commands, paths, hashes, failed attempts, and limitations.

- [ ] **Step 3: Seal the final package**

The binder must verify exact source/input hashes, all run/replay/comparison manifests, regression totals, no changed source, document links, registered parameter deltas, and exact completion file set before writing its own `evidence_hashes.json`.

- [ ] **Step 4: Run fresh completion verification**

Run the focused new tests and a read-only manifest verifier after the checkpoint update. Confirm no Phase 5/SUMO process remains. Read and follow `verification-before-completion` and `finishing-a-development-branch` before claiming completion; no merge/PR menu is actionable until this repository has an initial Git commit.
