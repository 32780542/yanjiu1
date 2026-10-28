# Phase 5E Exact Feasible Speed Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the conservative-speed solver so an exactly feasible configured upper speed is returned exactly, then measure the change on the frozen R5 cases without claiming that this solves the distinct real low-speed lane-change problem.

**Architecture:** Clone the hash-verified Phase 5D source and inputs into a new immutable `variants/phase5e_exact_endpoint` directory. Change only the endpoint branch in `_comfortable_speed`; keep the strict 5 m/s lane-change gate, lateral trajectory, R5/game logic, neighbor reachable envelope, and all physical/safety parameters unchanged. Bind the plan into the experiment input manifest, run the frozen parent suite, compare it with the sealed parent, and semantically replay the new package.

**Tech Stack:** Python 3.12 standard library, `unittest`, existing NOA/SUMO research harness, JSON/SHA-256 evidence manifests.

---

### Task 1: Establish the isolated Phase 5E source

**Files:**
- Create: `tmp/phase5e_clone.py`
- Create: `variants/phase5e_exact_endpoint/clone_provenance.json`
- Create: `variants/phase5e_exact_endpoint/docs/phase5e_exact_endpoint_plan.md`

- [ ] **Step 1: Verify the frozen Phase 5D source and input hashes**

Read both formal Phase 5D manifests and assert that every `code_snapshot` and `input_snapshot` file matches its recorded SHA-256, that the two source maps are identical, and that the root Phase 5D completion package remains sealed. Save the verification output through:

```powershell
PY -I -B -S scripts/run_logged.py --label phase5e_parent_prerequisites --timeout 180 -- PY -I -B -S tmp/phase5e_verify_parent.py
```

Expected: exit 0, identical Phase 5D source maps, no hash mismatch, and `scientific_accepted=false` retained.

- [ ] **Step 2: Clone without overwriting prior variants**

The clone script must refuse an existing destination, copy the saved Phase 5D `code_snapshot` and `input_snapshot`, restore `parent_frozen_r5_cases.json` under that exact name, copy `phase5c_extension.json` separately, and record all source paths and hashes in `clone_provenance.json`.

```powershell
PY -I -B -S scripts/run_logged.py --label phase5e_isolated_snapshot --timeout 180 -- PY -I -B -S tmp/phase5e_clone.py
```

Expected: exit 0, a new `variants/phase5e_exact_endpoint`, 113 source files, 11 bound parent inputs, and no writes in Phase 5D.

### Task 2: Add the exact-endpoint regression test first

**Files:**
- Create: `variants/phase5e_exact_endpoint/tests/test_phase5e_exact_endpoint.py`
- Modify: `variants/phase5e_exact_endpoint/noa/controller.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from experiments.phase5_r5 import parameters
from noa.controller import _comfortable_speed, _stop_distance


class ExactFeasibleEndpointTests(unittest.TestCase):
    def setUp(self):
        _, _, self.p = parameters(False)

    def required(self, speed):
        return (_stop_distance(speed, 0., self.p['comfort_braking_mps2'], self.p)
                + speed / self.p['noa_speed_gain_per_s'])

    def test_exactly_feasible_upper_is_returned_exactly(self):
        upper = min(self.p['noa_target_speed_mps'], self.p['max_speed_mps'])
        self.assertEqual(_comfortable_speed(self.required(upper), self.p, 0.), upper)

    def test_infeasible_upper_retains_conservative_lower_solution(self):
        upper = min(self.p['noa_target_speed_mps'], self.p['max_speed_mps'])
        distance = self.required(upper) - 1e-6
        result = _comfortable_speed(distance, self.p, 0.)
        self.assertLess(result, upper)
        self.assertLessEqual(self.required(result), distance)
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
PY -B -m unittest tests.test_phase5e_exact_endpoint -v
```

Expected: the exact-feasible test fails because the current bisection returns `4.999999925494194` instead of `5.0`; the infeasible-upper test passes.

- [ ] **Step 3: Implement the one-branch fix**

In `_comfortable_speed`, retain the existing stopping expression and add only this precheck before bisection:

```python
    available = max(0., distance)

    def required(speed):
        stopping = _stop_distance(speed, max(0., acceleration), p['comfort_braking_mps2'], p)
        return stopping + speed / p['noa_speed_gain_per_s']

    if required(upper) <= available:
        return upper
```

Use `required(middle) <= available` in the unchanged bisection. Do not add a speed tolerance, lower the 5 m/s gate, or change a safety parameter.

- [ ] **Step 4: Run the focused tests and verify GREEN**

```powershell
PY -B -m unittest tests.test_phase5e_exact_endpoint tests.test_phase4_controller tests.test_phase5_r5_controller tests.test_phase5c_priority tests.test_phase5d_waiting_game -v
```

Expected: all selected tests pass with no skip; the exact endpoint equals 5.0 and the infeasible branch remains conservative.

### Task 3: Bind the new research unit and run affected regression

**Files:**
- Create: `docs/phase5e_exact_endpoint_plan.md`
- Modify: `variants/phase5e_exact_endpoint/experiments/phase5_r5.py`
- Modify: `variants/phase5e_exact_endpoint/tests/test_phase5d_waiting_game.py`
- Test: `variants/phase5e_exact_endpoint/tests/test_phase5e_exact_endpoint.py`

- [ ] **Step 1: Bind the Phase 5E plan as an explicit input**

Append `docs/phase5e_exact_endpoint_plan.md` to the existing `INPUTS` tuple and add this assertion to the Phase 5E test file:

```python
    def test_phase5e_plan_is_a_bound_experiment_input(self):
        from experiments.phase5_r5 import INPUTS
        self.assertIn('docs/phase5e_exact_endpoint_plan.md', INPUTS)
```

- [ ] **Step 2: Run the affected regression through the logged wrapper**

Before selection, create the variant-local `tmp` directory expected by inherited tests. Update the inherited Phase 5D fixed-policy compatibility assertion so Phase 5E default and explicit `fixed` remain byte-for-byte equal, while any difference from sealed 5C is restricted to speeds 4.9/5.0 m/s, positive longitudinal acceleration no larger than `noa_geometry_tolerance_m`, with identical memory, diagnostics, and steering.

```powershell
PY -I -B -S scripts/run_logged.py --label phase5e_affected_regression --timeout 900 -- PY -B -m unittest tests.test_phase5e_exact_endpoint tests.test_phase4_controller tests.test_phase4_completion tests.test_phase4_records tests.test_phase5_r5_controller tests.test_phase5_r5_cases tests.test_phase5_r5_records tests.test_phase5_r5_replay tests.test_phase5c_priority tests.test_phase5c_cases tests.test_phase5d_waiting_game tests.test_phase5d_harness
```

Expected: exit 0, zero failure/error/skip, source hashes stable during the test command. Reuse the sealed Phase 5D 347-test evidence for unaffected modules; do not rerun older live vehicle suites.

### Task 4: Run the frozen experiment and standard replay

**Files:**
- Create: `variants/phase5e_exact_endpoint/results/phase5_r5/runs/<new-run>/...`
- Create: `variants/phase5e_exact_endpoint/results/phase5_r5/replays/<new-replay>/...`
- Create: `results/phase5e/<comparison>/...`

- [ ] **Step 1: Run the complete frozen eight-case parent suite once**

```powershell
PY -I -B -S scripts/run_logged.py --label phase5e_formal_exact_endpoint --timeout 1800 -- PY -I -B -S run.py phase5-r5 --case-file parent_frozen_r5_cases.json --waiting-policy fixed
```

Expected: a new append-only run package. Any native SUMO/driving failure remains a retained prefix; program completion is not scientific acceptance.

- [ ] **Step 2: Run the saved package's standard semantic replay**

```powershell
PY -I -B -S scripts/run_logged.py --label phase5e_exact_endpoint_semantic_replay --timeout 1800 -- PY -I -B -S run.py phase5-r5-replay --run-dir ABSOLUTE_NEW_RUN
```

Expected: every started variant, including retained failed prefixes, replays with unchanged source and inputs; validation errors and unstarted lists are reported exactly.

- [ ] **Step 3: Compare with the sealed fixed-policy parent**

The comparison must bind exact old/new source hashes and report, separately for OFF and ON: first `PREPARE_LC`, first committed plan, completed lane changes, minimum/mean/final speed, time below 5 m/s, candidate/guard rejection reasons, formation intervals, and raw failure-prefix status. It must explicitly distinguish the endpoint case from real low-speed observations around 1.7--1.85 m/s.

Expected scientific interpretation: the endpoint defect is either removed or not; no formation/traffic benefit is inferred from that engineering fact.

### Task 5: Freeze evidence and update the checkpoint

**Files:**
- Create: `docs/phase5e_exact_endpoint_acceptance.md`
- Create: `docs/phase5e_replay_index.md`
- Modify: `docs/phase5_next_entry.md`
- Modify: `docs/phase5_checkpoint.md`
- Create: `variants/phase5e_exact_endpoint/phase5e_source_freeze.json`
- Create: `results/phase5e/completion_<timestamp>/acceptance.json`

- [ ] **Step 1: Record verified facts and limitations**

The acceptance report must state the old/new exact solver values, all parameter changes (expected: none), source/input hashes, focused regression totals, experiment/replay status, observed vehicle outcomes, all failed conditions, and whether Phase 6 remains closed.

- [ ] **Step 2: Save a replay index and immutable delivery manifest**

Store exact commands, wrapper paths, exit codes, elapsed times, result paths, SHA-256 values, and retained errors. Verify the completion directory's declared file set equals the actual file set and every declared SHA-256 matches.

- [ ] **Step 3: Set the next Phase 5 entry from evidence**

If the exact endpoint is fixed but the real low-speed case remains below 5 m/s, the next unit is a separately preregistered speed-adaptive/longer-duration lane-change candidate. It must preserve the original local observation, neighbor reachability, collision, comfort, and model guards; no hidden communication, vehicle-class truth, ID priority, or global scheduling is allowed.
