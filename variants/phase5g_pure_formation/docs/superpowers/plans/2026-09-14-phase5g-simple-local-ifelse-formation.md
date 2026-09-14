# Phase 5G Simple Local If/Else Formation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a directly runnable SUMO-GUI demonstration in which normal NOA vehicles form a safe staggered formation using only the approved nearest-ahead and local rear-most if/else rules.

**Architecture:** Add one pure `noa/simple_formation.py` module that converts an already filtered local observation into a remembered reference, a bounded longitudinal increment, and at most one adjacent-lane balancing request. An explicit `simple_formation_enabled` path in the existing NOA controller reuses the Phase 4 swept-body guard and continuous lane-change trajectory; the legacy Phase 5G candidate-ranking path remains available only when the new switch is false. The existing synchronous clock, experiment recorder, independent detector, and SUMO trace player are reused rather than reimplemented.

**Tech Stack:** Python 3.11+, standard-library `dataclasses`/`unittest`, existing kinematic model and NOA safety guard, SUMO 1.27.1/TraCI, JSON/JSONL replay records.

---

## File map

- Create `noa/simple_formation.py`: pure local observation conversion, reference selection, 15/30 m longitudinal rule, local lane counting, and two-field memory.
- Modify `noa/controller.py`: explicit simple-mode integration before the legacy Phase 5G lane branch.
- Modify `simulation/phase5g_clock.py`: restore `SimpleFormationMemory` and call the base NOA controller directly in simple mode.
- Modify `experiments/phase5g.py`: resolve simple-mode parameters, run the existing recorder/detector with the new clock path, and count the new lane-change reason.
- Modify `experiments/phase5g_replay.py`: reconstruct the exact saved simple switch and six resolved parameters during replay.
- Modify `configs/phase5g.json`: register the six fixed simple-rule parameters.
- Modify `run.py`: expose simple demo parameters to the isolated variant command.
- Create `tests/test_simple_formation_rules.py`: pure rule tests.
- Create `tests/test_simple_formation_controller.py`: controller, safety, memory, and information-isolation tests.
- Create `tests/test_simple_formation_harness.py`: parameter, CLI, clock, recording, and 3/6/12-case tests.
- Create `tests/simple_formation_test_launcher.py`: isolated focused-test selector.
- Modify root `demo/sumo_gui.py`: generate a fresh simple trace and play it in SUMO-GUI.
- Modify root `runrun.py`: replace the old menu with the approved editable simple-formation configuration and direct debug/run behavior.
- Modify root `tests/test_runrun_demo.py`: validate the new direct entry while retaining lower-level native/legacy helper coverage.
- Modify `docs/phase5_checkpoint.md` and `README.md`: record the superseding simple path, evidence, and honest scientific result.

### Task 1: Pure local rule module

**Files:**
- Create: `variants/phase5g_pure_formation/noa/simple_formation.py`
- Create: `variants/phase5g_pure_formation/tests/test_simple_formation_rules.py`
- Create: `variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py`

- [ ] **Step 1: Write failing tests for the complete public rule surface**

Create tests that instantiate physical local vehicles directly, so no simulator truth or global actor list can enter the rule:

```python
from dataclasses import replace
import unittest

from noa.contracts import NoaMemory
from noa.simple_formation import (
    LocalVehicle, SimpleFormationMemory, choose_lane, choose_reference,
    desired_gap_m, longitudinal_increment, validate_parameters,
)


P = {
    "simple_formation_local_range_m": 90.0,
    "simple_formation_adjacent_gap_m": 15.0,
    "simple_formation_same_gap_m": 30.0,
    "simple_formation_position_tolerance_m": 2.0,
    "simple_formation_accel_limit_mps2": 0.5,
    "simple_formation_max_lane_changes": 1,
}


def vehicle(track, x, lane, speed=10.0):
    return LocalVehicle(track, float(x), 1.65 + 3.3 * lane,
                        float(speed), lane)


class SimpleFormationRuleTests(unittest.TestCase):
    def test_memory_has_exactly_two_formation_fields(self):
        memory = SimpleFormationMemory((), "CRUISE")
        self.assertIsNone(memory.reference_track_id)
        self.assertFalse(memory.formation_lane_change_done)
        self.assertIsInstance(memory, NoaMemory)

    def test_held_reference_wins_and_loss_chooses_unique_nearest(self):
        rows = (vehicle(7, 25, 1), vehicle(8, 12, 2))
        self.assertEqual(choose_reference(0.0, rows, 7, 1e-9).track_id, 7)
        self.assertEqual(choose_reference(0.0, rows, 99, 1e-9).track_id, 8)

    def test_equal_nearest_distance_is_ambiguous(self):
        rows = (vehicle(7, 12, 0), vehicle(8, 12, 2))
        self.assertIsNone(choose_reference(0.0, rows, None, 1e-9))

    def test_spacing_is_adjacent_fifteen_otherwise_thirty(self):
        self.assertEqual(desired_gap_m(0, 1, P), 15.0)
        self.assertEqual(desired_gap_m(1, 1, P), 30.0)
        self.assertEqual(desired_gap_m(0, 2, P), 30.0)

    def test_longitudinal_three_branch_rule_and_cap(self):
        ref = vehicle(7, 30, 1, speed=9)
        self.assertEqual(longitudinal_increment(0, 10, 0, ref, P), 0.5)
        self.assertEqual(longitudinal_increment(20, 10, 0, ref, P), -0.5)
        ref = replace(ref, x_m=16, vx_mps=9.8)
        self.assertAlmostEqual(longitudinal_increment(0, 10, 0, ref, P), -0.2)

    def test_only_local_rearmost_selects_unique_less_populated_adjacent(self):
        rows = (
            vehicle(1, 30, 0), vehicle(2, 10, 0),
            vehicle(3, 25, 1), vehicle(4, 5, 1), vehicle(5, 0, 2),
        )
        rear = choose_lane(0, 0, rows, (1.65, 4.95, 8.25), False, P)
        front = choose_lane(20, 0, rows, (1.65, 4.95, 8.25), False, P)
        self.assertEqual((rear.target_lane_index, rear.reason),
                         (1, "unique_less_populated_adjacent"))
        self.assertEqual((front.target_lane_index, front.reason),
                         (None, "not_local_rearmost"))

    def test_equal_adjacent_counts_and_completed_change_stay(self):
        rows = (vehicle(1, 20, 0), vehicle(2, 20, 2))
        tie = choose_lane(0, 1, rows, (1.65, 4.95, 8.25), False, P)
        done = choose_lane(0, 1, rows, (1.65, 4.95, 8.25), True, P)
        self.assertEqual(tie.reason, "adjacent_count_tie")
        self.assertIsNone(tie.target_lane_index)
        self.assertEqual(done.reason, "formation_lane_change_already_done")


if __name__ == "__main__":
    unittest.main()
```

The Task 1 test implementation must also add cases for no vehicle ahead, a remembered vehicle that moved behind, invalid booleans/numbers, an outer-lane vehicle considering only one adjacent lane, exclusion of `lane_index=None` from counts, and invariance when an otherwise identical vehicle is moved outside `simple_formation_local_range_m`.

- [ ] **Step 2: Add the focused isolated launcher and confirm RED**

```python
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
if len(sys.argv) != 2 or sys.argv[1] not in {"rules", "controller", "harness", "all"}:
    raise SystemExit("usage: simple_formation_test_launcher.py rules|controller|harness|all")
names = {
    "rules": ("test_simple_formation_rules.SimpleFormationRuleTests",),
    "controller": ("test_simple_formation_controller.SimpleFormationControllerTests",),
    "harness": ("test_simple_formation_harness.SimpleFormationHarnessTests",),
    "all": (
        "test_simple_formation_rules.SimpleFormationRuleTests",
        "test_simple_formation_controller.SimpleFormationControllerTests",
        "test_simple_formation_harness.SimpleFormationHarnessTests",
    ),
}
sys.path.insert(0, str(ROOT / "tests"))
suite = unittest.TestSuite(
    unittest.defaultTestLoader.loadTestsFromName(name) for name in names[sys.argv[1]]
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() and result.testsRun and not result.skipped else 1)
```

Run:

```powershell
python -I -B -S tests/simple_formation_test_launcher.py rules
```

Expected: nonzero exit with `ModuleNotFoundError: No module named 'noa.simple_formation'`.

- [ ] **Step 3: Implement the pure module with no controller or experiment imports**

The public structures and decisions are fixed as follows:

```python
from dataclasses import dataclass, fields
import math

from noa.contracts import NoaMemory, memory_from_dict as noa_memory_from_dict


@dataclass(frozen=True, slots=True)
class SimpleFormationMemory(NoaMemory):
    reference_track_id: int | None = None
    formation_lane_change_done: bool = False


@dataclass(frozen=True, slots=True)
class LocalVehicle:
    track_id: int
    x_m: float
    y_m: float
    vx_mps: float
    lane_index: int | None


@dataclass(frozen=True, slots=True)
class LaneDecision:
    target_lane_index: int | None
    reason: str
    counts: tuple[int, ...]


PARAMETERS = (
    "simple_formation_local_range_m",
    "simple_formation_adjacent_gap_m",
    "simple_formation_same_gap_m",
    "simple_formation_position_tolerance_m",
    "simple_formation_accel_limit_mps2",
    "simple_formation_max_lane_changes",
)


def validate_parameters(p):
    for name in PARAMETERS[:-1]:
        value = p.get(name)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive finite number")
    if p.get(PARAMETERS[-1]) != 1 or type(p.get(PARAMETERS[-1])) is not int:
        raise ValueError("simple_formation_max_lane_changes must be exactly 1")


def memory_from_dict(data):
    base_names = {field.name for field in fields(NoaMemory)}
    base = noa_memory_from_dict({key: value for key, value in data.items()
                                 if key in base_names})
    reference = data.get("reference_track_id")
    done = data.get("formation_lane_change_done", False)
    if reference is not None and (type(reference) is not int or reference < 0):
        raise ValueError("reference_track_id must be a nonnegative local integer or None")
    if type(done) is not bool:
        raise ValueError("formation_lane_change_done must be bool")
    return SimpleFormationMemory(
        **{field.name: getattr(base, field.name) for field in fields(NoaMemory)},
        reference_track_id=reference,
        formation_lane_change_done=done,
    )


def choose_reference(ego_x_m, vehicles, remembered_track_id, tolerance_m):
    ahead = tuple(row for row in vehicles
                  if row.lane_index is not None
                  and row.x_m > ego_x_m + tolerance_m)
    held = tuple(row for row in ahead if row.track_id == remembered_track_id)
    if len(held) == 1:
        return held[0]
    if not ahead:
        return None
    distance = min(row.x_m - ego_x_m for row in ahead)
    nearest = tuple(row for row in ahead
                    if abs((row.x_m - ego_x_m) - distance) <= tolerance_m)
    return nearest[0] if len(nearest) == 1 else None


def desired_gap_m(ego_lane, reference_lane, p):
    return (p["simple_formation_adjacent_gap_m"]
            if abs(ego_lane - reference_lane) == 1
            else p["simple_formation_same_gap_m"])


def longitudinal_increment(ego_x_m, ego_vx_mps, ego_lane, reference, p):
    error = reference.x_m - desired_gap_m(ego_lane, reference.lane_index, p) - ego_x_m
    limit = p["simple_formation_accel_limit_mps2"]
    tolerance = p["simple_formation_position_tolerance_m"]
    if error > tolerance:
        return limit
    if error < -tolerance:
        return -limit
    return max(-limit, min(limit, reference.vx_mps - ego_vx_mps))
```

Implement `choose_lane` exactly in the specification order: done check, rear-most check, strictly smaller adjacent count, unique minimum check, then one `LaneDecision`. It must count only `lane_index is not None` rows within `abs(row.x_m - ego_x_m) <= local_range`, add the ego to its current lane, and never invoke a safety function.

- [ ] **Step 4: Run the pure tests and static import check**

Run:

```powershell
python -I -B -S tests/simple_formation_test_launcher.py rules
python -I -B -S -c "import sys; sys.path.insert(0,'.'); import noa.simple_formation"
```

Expected: all rule tests pass; import exits 0 without output.

- [ ] **Step 5: Commit Task 1**

```powershell
git add variants/phase5g_pure_formation/noa/simple_formation.py variants/phase5g_pure_formation/tests/test_simple_formation_rules.py variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py
git commit -m "feat: add simple local formation rules"
```

### Task 2: Controller and private-memory integration

**Files:**
- Modify: `variants/phase5g_pure_formation/noa/controller.py:16,178-300,317-648`
- Modify: `variants/phase5g_pure_formation/simulation/phase5g_clock.py:11-34,141-226`
- Create: `variants/phase5g_pure_formation/tests/test_simple_formation_controller.py`

- [ ] **Step 1: Write failing controller tests using real local observations**

Add a fixture that creates `ControlInput`, three observed lane centers, `NeighborDetection` rows, and `SimpleFormationMemory`. Cover these exact outcomes:

```python
def test_no_reference_leaves_base_cruise_unchanged(self):
    decision = decide(self.control(neighbors=()), self.parameters())
    self.assertEqual(decision.diagnostics["simple_formation"]["reference_reason"],
                     "no_visible_reference")
    self.assertIsNone(decision.memory.reference_track_id)

def test_adjacent_reference_adds_only_bounded_increment(self):
    control = self.control(neighbors=(self.neighbor(7, dx=25, dy=3.3, dvx=0),))
    decision = decide(control, self.parameters())
    diag = decision.diagnostics["simple_formation"]
    self.assertEqual(diag["desired_gap_m"], 15.0)
    self.assertLessEqual(abs(diag["applied_increment_mps2"]), 0.5)

def test_rearmost_unique_lower_lane_uses_one_guarded_fixed_plan(self):
    with patch("noa.controller.verify_candidate",
               return_value={"safe": True, "reason": "fixture", "at_s": None,
                             "checked_s": 5.0}) as guard:
        decision = decide(self.unbalanced_rearmost_control(), self.parameters())
    self.assertEqual(decision.memory.lane_change_reason,
                     "simple_formation_balance")
    self.assertIsNotNone(decision.memory.plan)
    guard.assert_called()

def test_guard_rejection_keeps_lane_and_speed_control(self):
    with patch("noa.controller.verify_candidate",
               return_value={"safe": False, "reason": "blocked", "at_s": 1.0,
                             "checked_s": 1.0}):
        decision = decide(self.unbalanced_rearmost_control(), self.parameters())
    self.assertIsNone(decision.memory.plan)
    self.assertEqual(decision.diagnostics["simple_formation"]["lane_reason"],
                     "safety_rejected")
```

Also test that completion sets `formation_lane_change_done=True`, a second request is impossible, an active plan is not retargeted, emergency/base road motivation wins, hidden IDs/types cannot be supplied, and relabeling local track IDs changes no physical action when memory is relabeled consistently.

- [ ] **Step 2: Run controller selection and confirm RED**

```powershell
python -I -B -S tests/simple_formation_test_launcher.py controller
```

Expected: nonzero exit because `noa.controller.decide` has no `simple_formation_enabled` path.

- [ ] **Step 3: Add an explicit simple branch without modifying legacy selection**

At module import level, add:

```python
from noa import formation_lane, r5, simple_formation, waiting_game
from noa.simple_formation import SimpleFormationMemory
```

At the beginning of `decide`, derive two non-overlapping switches:

```python
simple_active = (p.get("phase5g_enabled") is True
                 and p.get("simple_formation_enabled") is True
                 and p.get("formation_enabled") is True
                 and not r5_enabled)
legacy_formation_lane_active = (p.get("phase5g_enabled") is True
                                and p.get("formation_lane_change_enabled") is True
                                and not simple_active and not r5_enabled)
if simple_active:
    simple_formation.validate_parameters(p)
    if not isinstance(memory, SimpleFormationMemory):
        raise ValueError("simple formation requires SimpleFormationMemory")
```

Rename only the local controller variable `formation_lane_active` to
`legacy_formation_lane_active`; do not alter the contents of the legacy branch.

Convert the already filtered observation with a pure adapter in
`noa/simple_formation.py`:

```python
vehicles = simple_formation.local_vehicles(control, road, p)
reference = simple_formation.choose_reference(
    ego.x_m, vehicles, memory.reference_track_id,
    p["noa_geometry_tolerance_m"],
)
```

The adapter must transform the `NeighborDetection` ego-frame position and
velocity to world coordinates, preserve only `track_id`, and associate a lane
only when the entire observed vehicle width fits one visible lane strip within
the geometry tolerance. It must not call the sensor, clock, detector, or global
state.

- [ ] **Step 4: Apply the longitudinal branch once, below base emergency/motivation**

Use one fixed hold trajectory to certify the proposed acceleration:

```python
if simple_active and not emergency and motivation is None and memory.plan is None:
    if reference is None:
        memory = replace(memory, reference_track_id=None)
        simple_diag.update(reference_reason="no_visible_reference")
    else:
        effective_lane = simple_formation.lane_index(
            road.current_center_m, road.centers_m, p["noa_geometry_tolerance_m"])
        increment = simple_formation.longitudinal_increment(
            ego.x_m, ego.vx_mps, effective_lane, reference, p)
        proposed = clip(accel + increment,
                        max(p["min_accel_mps2"], -p["comfort_braking_mps2"]),
                        min(p["max_accel_mps2"], p["comfort_accel_mps2"]))
        hold = QuadraticLaneChange(
            ego.time_s, road.current_center_m, road.current_center_m,
            p["noa_lane_change_duration_s"],
            max(ego.vx_mps, p["noa_min_lane_change_speed_mps"]),
        )
        guard = verify_candidate(control, hold, road, proposed, p)
        memory = replace(memory, reference_track_id=reference.track_id)
        if guard["safe"]:
            accel = proposed
            simple_diag["applied_increment_mps2"] = proposed - simple_diag["base_acceleration_mps2"]
        else:
            simple_diag["reference_reason"] = "longitudinal_safety_rejected"
```

Record only explicit simple diagnostics: enabled, reference track ID, desired
gap, target position error, raw/applied increment, local counts, lane reason,
and the one guard result. Do not emit candidate arrays, scores, rank keys,
priority games, random draws, weights, or target lattices.

- [ ] **Step 5: Add the single lane request after higher-priority NOA choices**

Immediately before the legacy formation-lane block, execute:

```python
if simple_active and not emergency and motivation is None and not cooldown:
    current_lane = simple_formation.lane_index(
        road.current_center_m, road.centers_m, p["noa_geometry_tolerance_m"])
    lane_choice = simple_formation.choose_lane(
        ego.x_m, current_lane, vehicles, road.centers_m,
        memory.formation_lane_change_done, p,
    )
    simple_diag.update(local_lane_counts=lane_choice.counts,
                       lane_reason=lane_choice.reason)
    if lane_choice.target_lane_index is not None:
        target_y = road.centers_m[lane_choice.target_lane_index]
        duration = p["noa_lane_change_duration_s"]
        if ego.vx_mps < steering_speed_floor(duration, p):
            simple_diag["lane_reason"] = "fixed_plan_speed_too_low"
        else:
            plan = QuadraticLaneChange(ego.time_s, ego.y_m, target_y,
                                       duration, ego.vx_mps)
            guard = verify_candidate(control, plan, road, accel, p)
            simple_diag["lane_guard"] = guard
            if guard["safe"]:
                memory = replace(memory, plan=plan, target_y_m=target_y,
                                 prepare_since_s=ego.time_s,
                                 lane_change_reason="simple_formation_balance")
                action = Actuation(accel, lateral_command(
                    ego, reference_target(plan, ego.time_s), p))
                return NoaDecision(action, replace(memory, own_behavior="EXECUTE_LC"),
                                   {**diagnostics, "simple_formation": simple_diag})
            simple_diag["lane_reason"] = "safety_rejected"
```

On completion of a plan whose saved reason is
`simple_formation_balance`, set `formation_lane_change_done=True`. During an
active plan, retain the controller's current one-plan execution branch and
return before any new simple lane choice.

- [ ] **Step 6: Restore the two-field memory through the Phase 5G clock**

In `simulation/phase5g_clock.py`, add `simple_formation_enabled` to the checked
boolean switches and route simple decisions directly to `noa.controller.decide`:

```python
from noa.controller import decide as noa_decide
from noa.simple_formation import SimpleFormationMemory, memory_from_dict as simple_memory_from_dict

def _decide(self, control):
    return noa_decide(control, self.policy) if self.p["simple_formation_enabled"] \
        else super()._decide(control)
```

When the simple switch is true, restore each controlled actor through
`simple_memory_from_dict`; otherwise preserve the existing Phase 5G restoration
byte-for-byte. Extend the accepted lane-change reasons with
`simple_formation_balance`. Do not require or draw a private RNG seed in simple
mode.

- [ ] **Step 7: Run controller tests and inherited focused regression**

```powershell
python -I -B -S tests/simple_formation_test_launcher.py controller
python -I -B -S tests/phase5g_test_launcher.py controller
python -I -B -S tests/phase5g_test_launcher.py lane
```

Expected: all selected tests pass, with no skips. The legacy lane tests prove
that the old code remains available when `simple_formation_enabled=False`.

- [ ] **Step 8: Commit Task 2**

```powershell
git add variants/phase5g_pure_formation/noa/controller.py variants/phase5g_pure_formation/simulation/phase5g_clock.py variants/phase5g_pure_formation/tests/test_simple_formation_controller.py
git commit -m "feat: integrate simple formation controller"
```

### Task 3: Registered parameters, isolated CLI, and replayable runner

**Files:**
- Modify: `variants/phase5g_pure_formation/configs/phase5g.json`
- Modify: `variants/phase5g_pure_formation/experiments/phase5g.py:38-76,236-270,471-524,721-788,1146-1194`
- Modify: `variants/phase5g_pure_formation/experiments/phase5g_replay.py:46-96`
- Modify: `variants/phase5g_pure_formation/run.py:52-108`
- Create: `variants/phase5g_pure_formation/tests/test_simple_formation_harness.py`

- [ ] **Step 1: Write RED tests for parameter isolation and CLI forwarding**

The harness tests must assert:

```python
def test_simple_parameters_change_only_the_registered_simple_switch_and_values(self):
    model, physical, policy = phase5g.parameters(
        "lane_priority", 10.0, simple_rules=True,
        simple_overrides={
            "simple_formation_local_range_m": 90.0,
            "simple_formation_adjacent_gap_m": 15.0,
            "simple_formation_same_gap_m": 30.0,
            "simple_formation_position_tolerance_m": 2.0,
            "simple_formation_accel_limit_mps2": 0.5,
            "simple_formation_max_lane_changes": 1,
        },
    )
    self.assertTrue(physical["simple_formation_enabled"])
    self.assertTrue(policy["simple_formation_enabled"])
    self.assertFalse(physical["r5_enabled"])
    self.assertEqual(physical["simple_formation_max_lane_changes"], 1)

def test_demo_uses_simple_rules_without_expanding_formal_mode_registry(self):
    self.assertEqual(tuple(phase5g.MODES), ("off", "longitudinal", "lane_priority"))
    with patch("experiments.phase5g.run_variant", return_value=self.fake_result()) as run:
        path = phase5g.run_phase5g_demo(
            vehicle_count=6, seed=1, target_speed_mps=10.0, duration_s=45.0,
            output_base=self.output, live=False,
            simple_formation_local_range_m=90.0,
            simple_formation_adjacent_gap_m=15.0,
            simple_formation_same_gap_m=30.0,
            simple_formation_position_tolerance_m=2.0,
            simple_formation_accel_limit_mps2=0.5,
            simple_formation_max_lane_changes=1,
        )
    self.assertTrue(run.call_args.args[2]["simple_formation_enabled"])
    self.assertTrue(path.is_dir())
```

Also assert invalid count, bool-as-number, nonfinite values, zero/negative values,
and max lane changes other than exactly one fail before a result directory is
created. Patch `run_phase5g_demo` in the isolated CLI test and assert every CLI
value is forwarded exactly once.

- [ ] **Step 2: Confirm harness RED**

```powershell
python -I -B -S tests/simple_formation_test_launcher.py harness
```

Expected: nonzero exit because `parameters` and `run_phase5g_demo` do not yet
accept the simple rule arguments.

- [ ] **Step 3: Register the exact parameter object**

Add these keys to `configs/phase5g.json` with JSON numeric values:

```json
"simple_formation_local_range_m": 90.0,
"simple_formation_adjacent_gap_m": 15.0,
"simple_formation_same_gap_m": 30.0,
"simple_formation_position_tolerance_m": 2.0,
"simple_formation_accel_limit_mps2": 0.5,
"simple_formation_max_lane_changes": 1
```

Do not remove or rename legacy parameters, because historical formal replay
loads them from saved snapshots.

- [ ] **Step 4: Extend `parameters` without adding a fourth formal mode**

Use this public signature:

```python
def parameters(mode: str, target_speed_mps: float = 10.0, *,
               simple_rules: bool = False,
               simple_overrides: Mapping[str, object] | None = None):
```

Require `type(simple_rules) is bool`. When false, set
`simple_formation_enabled=False` and reject nonempty overrides. When true,
validate an override dictionary containing exactly the six `PARAMETERS` names,
merge it over the registered defaults, and copy the resolved values plus the
switch into both `physical` and `policy`. Keep `_MODE_SPECS` and `MODES`
unchanged.

In `run_variant`, reconstruct expected parameters from the simple switch and
the six resolved values already present in `physical`, then retain the existing
exact `compare_tree` checks. Convert initial memory rows to the two-field schema
before hashing and creating `Phase5GClock` when simple mode is active.

In `experiments/phase5g_replay.py::_validate_metadata`, perform the same exact
reconstruction from saved metadata rather than assuming legacy parameters:

```python
from noa import simple_formation

simple = metadata.get("parameters", {}).get("simple_formation_enabled") is True
overrides = ({name: metadata["parameters"][name]
              for name in simple_formation.PARAMETERS} if simple else None)
model, physical, policy = parameters(
    mode, target, simple_rules=simple, simple_overrides=overrides,
)
```

The existing exact tree comparison, source hashes, memory hash, trace replay,
and tamper rejection remain unchanged after parameter reconstruction.

- [ ] **Step 5: Make the non-formal demo explicitly simple**

Extend `run_phase5g_demo` with six keyword-only simple arguments, call
`parameters(..., simple_rules=True, simple_overrides=resolved)`, and record this
metadata:

```python
{
    "purpose": "Non-formal simple local if/else formation GUI source trace",
    "schema": "phase5g_simple_demo_v1",
    "formal": False,
    "mode": "lane_priority",
    "simple_formation_enabled": True,
    "vehicle_count": vehicle_count,
    "seed": seed,
    "target_speed_mps": float(target_speed_mps),
    "duration_s": duration,
    "simple_parameters": resolved,
}
```

Update the trace source hash list to include `noa/simple_formation.py` and the
approved simple design/plan files. The formal paired suite continues to call
`parameters` with `simple_rules=False`.

- [ ] **Step 6: Count the simple lane-change reason factually**

Change the derived lane event classification from a single literal to:

```python
FORMATION_LANE_REASONS = frozenset({
    "formation_geometry",
    "simple_formation_balance",
})
```

Use membership in this set for `formation_lane_changes`. Do not change collision,
geometry, speed recovery, 30-second formation, or 10-second hold definitions.

- [ ] **Step 7: Add isolated CLI flags**

Add parser options with the approved defaults:

```python
parser.add_argument("--local-formation-range-m", type=positive_finite, default=90.0)
parser.add_argument("--adjacent-lane-gap-m", type=positive_finite, default=15.0)
parser.add_argument("--same-lane-gap-m", type=positive_finite, default=30.0)
parser.add_argument("--position-tolerance-m", type=positive_finite, default=2.0)
parser.add_argument("--formation-accel-limit-mps2", type=positive_finite, default=0.5)
parser.add_argument("--max-formation-lane-changes", type=int, choices=(1,), default=1)
```

Forward them only from the `phase5g-demo` branch. Keep the required isolated
invocation `python -I -B -S run.py phase5g-demo ...`.

- [ ] **Step 8: Run harness and inherited clock/case tests**

```powershell
python -I -B -S tests/simple_formation_test_launcher.py harness
python -I -B -S tests/phase5g_test_launcher.py cases
python -I -B -S tests/phase5g_test_launcher.py harness
```

Expected: all selected tests pass without skips; the formal mode registry still
contains exactly the original three entries.

- [ ] **Step 9: Commit Task 3**

```powershell
git add variants/phase5g_pure_formation/configs/phase5g.json variants/phase5g_pure_formation/experiments/phase5g.py variants/phase5g_pure_formation/experiments/phase5g_replay.py variants/phase5g_pure_formation/run.py variants/phase5g_pure_formation/tests/test_simple_formation_harness.py
git commit -m "feat: add replayable simple formation demo"
```

### Task 4: Scientific small-case acceptance without forced success

**Files:**
- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_harness.py`

- [ ] **Step 1: Add tests for the registered physical inputs**

Assert the six-car main case contains exactly six controlled normal vehicles,
no scripts, lane counts `[3, 2, 1]`, a collision-free initial state, and no
initial whole-cohort formation. Assert seeded 3/6/12 inputs contain no obstacle
or background actor. Do not change `MAIN_SIX` merely to make the new rule pass.

```python
def test_main_case_is_unformed_safe_three_two_one_without_scripts(self):
    _, physical, _ = phase5g.parameters("lane_priority", simple_rules=True,
                                        simple_overrides=self.simple_values)
    case = cases.main_six_case(physical)
    self.assertEqual(len(case["controlled"]), 6)
    self.assertEqual(case["scripts"], {})
    lanes = [round(row["y_m"] / 3.3) for row in case["initial"].values()]
    self.assertEqual([lanes.count(i) for i in range(3)], [3, 2, 1])
    self.assertTrue(cases.validate_initial(case["initial"], physical)["passed"])
```

- [ ] **Step 2: Run one offline six-car attempt and retain its result regardless of outcome**

```powershell
$sixOutput = & python -I -B -S run.py phase5g-demo --offline --vehicle-count 6 --seed 1 --target-speed-mps 10 --duration-s 45 --output-base results/phase5g/simple_demo
if ($LASTEXITCODE -ne 0) { $sixOutput; exit $LASTEXITCODE }
$sixJson = $sixOutput | Where-Object { $_.Trim() } | Select-Object -Last 1 | ConvertFrom-Json
$sixRun = [System.IO.Path]::GetFullPath([string]$sixJson.path)
Write-Output "SIX_RUN=$sixRun"
```

Expected: exit 0 if recording completes and print one literal `SIX_RUN=...`
path. Keep `$sixRun` in the same PowerShell session for Steps 3 and 5; do not
reuse `latest.json` as scientific evidence.

- [ ] **Step 3: Inspect the independent outputs, not controller self-report**

For `$sixRun`, verify `case/detection.json`, `case/lane_changes.json`,
`case/speed_recovery.json`, `case/geometry.json`, and `case/validation.json` are
present. Record these exact facts in the test or checkpoint:

```powershell
$casePath = Join-Path $sixRun 'case'
$required = 'detection.json','lane_changes.json','speed_recovery.json','geometry.json','validation.json'
$missing = $required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $casePath $_) -PathType Leaf) }
if ($missing) { throw "missing six-car evidence: $($missing -join ', ')" }
Get-Content -LiteralPath (Join-Path $casePath 'validation.json') -Raw
```

```text
whole_cohort_formation_success
formed_time_s
held_time_s
formation_lane_changes
final_lane_counts
minimum_speed_mps
speed_recovered
collision_count
geometry_passed
comfort_passed
```

If the main case fails any scientific gate, keep the run and stop tuning in
this task. Report the failed condition before proposing a separately approved
rule change; do not add slots, obstacles, candidate scores, or relaxed safety.

- [ ] **Step 4: Run the 3- and 12-vehicle diagnostic cases**

```powershell
$threeOutput = & python -I -B -S run.py phase5g-demo --offline --vehicle-count 3 --seed 1 --target-speed-mps 10 --duration-s 45 --output-base results/phase5g/simple_demo
if ($LASTEXITCODE -ne 0) { $threeOutput; exit $LASTEXITCODE }
$threeRun = [System.IO.Path]::GetFullPath([string](($threeOutput | Where-Object { $_.Trim() } | Select-Object -Last 1 | ConvertFrom-Json).path))
$twelveOutput = & python -I -B -S run.py phase5g-demo --offline --vehicle-count 12 --seed 1 --target-speed-mps 10 --duration-s 45 --output-base results/phase5g/simple_demo
if ($LASTEXITCODE -ne 0) { $twelveOutput; exit $LASTEXITCODE }
$twelveRun = [System.IO.Path]::GetFullPath([string](($twelveOutput | Where-Object { $_.Trim() } | Select-Object -Last 1 | ConvertFrom-Json).path))
Write-Output "THREE_RUN=$threeRun"
Write-Output "TWELVE_RUN=$twelveRun"
```

Expected: both recordings finish or preserve an explicit failed prefix. A
12-car disconnected result is reportable and is not converted into a passing
single component by changing the detector.

- [ ] **Step 5: Replay the exact six-car run**

```powershell
python -I -B -S run.py phase5g-replay --run-dir $sixRun
```

Expected: replay exits 0 and reproduces the saved action and detection records.
The parameter and memory reconstruction added in Tasks 2 and 3 must make this
work without a permissive schema fallback.

- [ ] **Step 6: Commit Task 4 tests**

```powershell
git add variants/phase5g_pure_formation/tests/test_simple_formation_harness.py
git commit -m "test: verify simple formation small cases"
```

### Task 5: Direct `runrun.py` SUMO-GUI demonstration

**Files:**
- Modify: `demo/sumo_gui.py:19-127,186-195,231-333,557-698`
- Modify: `runrun.py:1-134`
- Modify: `tests/test_runrun_demo.py:18-60,355-429`

- [ ] **Step 1: Write RED tests for the new top configuration and direct dispatch**

Add a separate immutable configuration so native and legacy playback helpers
remain testable:

```python
expected = gui.SimpleFormationDemoConfig(
    vehicle_count=6,
    target_speed_mps=10.0,
    random_seed=1,
    simulation_duration_s=45.0,
    show_gui=True,
    gui_delay_ms=40,
    auto_zoom=True,
    wait_before_close=True,
    local_formation_range_m=90.0,
    adjacent_lane_gap_m=15.0,
    same_lane_gap_m=30.0,
    position_tolerance_m=2.0,
    formation_accel_limit_mps2=0.5,
    max_formation_lane_changes_per_vehicle=1,
)
self.assertEqual(runrun.build_config(), expected)
```

Replace the old menu-dispatch expectation with:

```python
with patch.object(runrun, "run_simple_formation_demo") as demo:
    self.assertEqual(runrun.main([], output_fn=lambda line: None), 0)
demo.assert_called_once_with(expected, input_fn=unittest.mock.ANY,
                             output_fn=unittest.mock.ANY)
```

`main(["--check"])` must call only `check_simple_environment`; it must not start
a subprocess or GUI. Invalid flags must retain a clear Chinese error.

- [ ] **Step 2: Run the root test selection and confirm RED**

```powershell
python -I -B -m unittest tests.test_runrun_demo.EntrypointTests -v
```

Expected: nonzero exit because the simple configuration and direct runner do
not exist.

- [ ] **Step 3: Add a validated simple GUI configuration**

In `demo/sumo_gui.py`, define `SimpleFormationDemoConfig` with the fields and
defaults from Step 1. `validate_simple_config` must:

- accept vehicle counts exactly 3, 6, or 12;
- reject bools in numeric fields and all nonfinite/nonpositive values;
- require the maximum formation lane changes to be exactly one;
- require `simulation_duration_s` to be a whole multiple of 0.1 s;
- resolve `sumo-gui.exe`, TraCI, the bottleneck network, and
  `variants/phase5g_pure_formation/run.py` without reading a Phase 5F run;
- perform no process creation and no result-directory creation.

- [ ] **Step 4: Generate a fresh simple trace in an isolated subprocess**

Build one argument list without shell interpolation:

```python
command = [
    sys.executable, "-I", "-B", "-S", str(paths.variant_run),
    "phase5g-demo", "--offline",
    "--vehicle-count", str(config.vehicle_count),
    "--seed", str(config.random_seed),
    "--target-speed-mps", format_number(config.target_speed_mps),
    "--duration-s", format_number(config.simulation_duration_s),
    "--output-base", "results/phase5g/simple_gui_sources",
    "--local-formation-range-m", format_number(config.local_formation_range_m),
    "--adjacent-lane-gap-m", format_number(config.adjacent_lane_gap_m),
    "--same-lane-gap-m", format_number(config.same_lane_gap_m),
    "--position-tolerance-m", format_number(config.position_tolerance_m),
    "--formation-accel-limit-mps2", format_number(config.formation_accel_limit_mps2),
    "--max-formation-lane-changes",
    str(config.max_formation_lane_changes_per_vehicle),
]
```

Run with `subprocess.run(command, cwd=paths.variant_root, capture_output=True,
text=True, encoding="utf-8", timeout=180, check=False)`. Parse only the final
nonempty stdout line as JSON and require its `path` to resolve below the variant
`results` directory. Load `case/metadata.json`, `case/validation.json`, and
`case/trace.jsonl` into the existing `TraceSource`; actors come from the saved
case's controlled list. A failed generator raises a Chinese `RuntimeError` that
includes the exit code and saved stderr, without opening SUMO-GUI.

- [ ] **Step 5: Play the fresh trace and save playback metadata**

`run_simple_formation_demo` must print the resolved configuration, generate the
trace, and then:

```python
if not config.show_gui:
    output_fn(f"轨迹已生成：{source.case_dir.parent}")
    return source.case_dir.parent
```

When `show_gui=True`, allocate a fresh root
`results/demo_runs/*_simple_formation_*` directory, write the existing external
vehicle route and SUMO configuration, start an owned GUI session, and call the
existing `play_algorithm`. Save generation source path, resolved config,
playback statistics, collision/teleport counts, and terminal status. Preserve
the existing cleanup behavior for normal completion, user window closure,
keyboard interruption, and startup failure.

- [ ] **Step 6: Replace the root menu with direct debug/run behavior**

The top of `runrun.py` must contain only ordinary editable constants and Chinese
comments. `build_config` copies them into `SimpleFormationDemoConfig`.
`main([])` prints one short description and calls `run_simple_formation_demo`
immediately. Keep `--check` as the only accepted CLI flag. Keep the existing
UTF-8 stream reconfiguration and `_debug_friendly_entry`, so clicking an
editor's Run or Debug button behaves the same as `python runrun.py`.

- [ ] **Step 7: Run root tests and environment check**

```powershell
python -I -B -m unittest tests.test_runrun_demo -v
python runrun.py --check
```

Expected: all root demo tests pass without skips; the check reports the simple
variant entry, network, `sumo-gui.exe`, and TraCI path and does not start SUMO.

- [ ] **Step 8: Commit Task 5**

```powershell
git add demo/sumo_gui.py runrun.py tests/test_runrun_demo.py
git commit -m "feat: run simple formation from runrun"
```

### Task 6: Full verification, replay evidence, and checkpoint

**Files:**
- Modify: `docs/phase5_checkpoint.md`
- Modify: `README.md`

- [ ] **Step 1: Run syntax and focused suites through the logged runner**

Use fresh labels for every command:

```powershell
python scripts/run_logged.py --label simple-formation-compile --timeout 120 -- python -I -B -S -m compileall -q noa simulation experiments tests
python scripts/run_logged.py --label simple-formation-focused --timeout 300 -- python -I -B -S tests/simple_formation_test_launcher.py all
python scripts/run_logged.py --label simple-formation-phase5g-regression --timeout 600 -- python -I -B -S tests/phase5g_test_launcher.py all
```

Expected: every command exits 0; focused and inherited suites run at least one
test and report no failures, errors, or skips. Preserve each printed operation
directory.

- [ ] **Step 2: Run affected inherited project regression**

```powershell
python scripts/run_logged.py --label simple-formation-root-demo-tests --timeout 300 -- python -I -B -m unittest tests.test_runrun_demo -v
python scripts/run_logged.py --label simple-formation-phase4-regression --timeout 600 -- python -I -B -S run.py test
```

If the full inherited `run.py test` exposes a pre-existing unrelated failure,
save it and separate it from failures caused by the changed files. Do not call
the task complete while a changed-path regression fails.

- [ ] **Step 3: Generate the final fresh 3/6/12 evidence set**

Run the three Task 4 commands again with a new output base
`results/phase5g/simple_final`. Save literal returned paths and do not replace a
failed run with an unrecorded retry. Replay the six-car path explicitly.

- [ ] **Step 4: Perform the user-facing non-GUI launch check**

```powershell
python runrun.py --check
```

Then run one debug-equivalent trace generation by setting `SHOW_GUI=False` in a
temporary in-memory test patch, not by editing the committed default. Verify a
fresh trace path is returned and contains the saved resolved top configuration.

- [ ] **Step 5: Update checkpoint and README with only verified facts**

Record:

- approved design commit and implementation commits;
- exact changed files;
- exact logged operation directories and exit codes;
- literal 3/6/12 run paths;
- six-car replay result;
- independent formation, hold, lane-change, speed, collision, geometry, and
  comfort facts;
- any scientific failure and its unchanged safety rejection reason;
- `runrun.py` direct/debug instructions and editable parameter names;
- the next research entrance, without claiming traffic-efficiency or energy
  benefit.

- [ ] **Step 6: Review the implementation diff before the final commit**

```powershell
git diff --check
git status --short
git diff --stat HEAD
```

Expected: no whitespace errors; only planned source, tests, and documentation
are staged for the final commit. Results remain untracked/ignored evidence and
are not committed unless the repository's existing policy explicitly tracks a
small index file.

- [ ] **Step 7: Commit documentation and verification record**

```powershell
git add docs/phase5_checkpoint.md README.md
git commit -m "docs: record simple formation verification"
```

- [ ] **Step 8: Final completion gate**

Run `git log --oneline -8` and `git status --short`. Report separately:

1. engineering completion: focused tests, affected regression, direct-entry
   check, exact replay, collision/geometry/comfort status;
2. scientific outcome: whether the independent six-car 30 s formation plus
   10 s hold gate actually passed;
3. limitations: 3/12-car behavior and any retained failure.

Do not push to GitHub unless the user explicitly requests a push after reviewing
the completed local commits.
