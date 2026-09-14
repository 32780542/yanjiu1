# Phase 5G simple local if/else staggered-formation design

Date: 2026-09-14
Status: approved in conversation; written specification awaiting user review

## 1. Purpose

Replace the Phase 5G demonstration path's complex lane-candidate ranking,
priority game, random backoff, and repeated target reassignment with a small,
auditable set of local if/else rules. The resulting vehicles must form a
three-lane staggered formation without V2V/V2I communication, global vehicle
lists, global lane counts, global slots, or central assignment.

The formation decision is intentionally simple. The already validated base
NOA collision guard and continuous kinematic execution remain in force; their
safety work is not reimplemented inside the formation rule.

## 2. MATLAB lessons retained and rejected

The design retains three ideas verified in `D:\matlab_huipu_2000`:

- `Copy_2_of_Main.m` demonstrates that lane and longitudinal targets can be
  expressed with direct `if/elseif` rules rather than an optimizer.
- `formationControlNormal.m` defines the useful geometry: adjacent lanes are
  staggered by 15 m, while vehicles in the same lane are separated by 30 m.
- `One_Vehicle_Control.m` demonstrates direct piecewise longitudinal correction
  from position error.

The new controller does not retain the MATLAB global ordering, Hungarian
assignment, global target lattice, or centralized formation grouping. Those
mechanisms conflict with the no-communication local-self-organization scope.

## 3. Hard information boundary

Each vehicle may read only:

- its own position, speed, acceleration, heading, and current physical lane;
- road geometry visible through the existing local perception interface;
- neighboring vehicle position, speed, visible motion, dimensions, and local
  track identifier inside the existing finite perception bounds;
- its own two formation-memory values defined below.

The rule must not read or derive decisions from the global vehicle collection,
true SUMO vehicle IDs, hidden vehicle types, other vehicles' commands or
memories, a shared leader, a shared random state, global lane populations, or a
global slot table. A local track identifier may be used only to keep following
the same visible physical object; it must not determine priority.

All vehicle decisions for a simulation tick use the same frozen physical
snapshot. Actions are applied only after every vehicle has decided, so loop
ordering cannot act as hidden communication.

## 4. Fixed constants and editable demonstration parameters

The root `runrun.py` configuration section exposes at least:

```python
VEHICLE_COUNT = 6
TARGET_SPEED_MPS = 10.0
RANDOM_SEED = 1
SHOW_GUI = True

LOCAL_FORMATION_RANGE_M = 90.0
ADJACENT_LANE_GAP_M = 15.0
SAME_LANE_GAP_M = 30.0
POSITION_TOLERANCE_M = 2.0
FORMATION_ACCEL_LIMIT_MPS2 = 0.5
MAX_FORMATION_LANE_CHANGES_PER_VEHICLE = 1
```

The existing validated lane-change duration and base safety parameters remain
the defaults for trajectory generation and collision checking. They may be
exposed in `runrun.py` only if the current runner already supports them cleanly;
the formation rule must not search several durations or score several paths.

`LOCAL_FORMATION_RANGE_M` is a symmetric longitudinal subrange around the ego
vehicle. It lies within the established finite perception envelope. Objects
outside this local range do not affect formation lane counts or the rear-most
test even when other infrastructure knows that they exist.

## 5. Minimal local memory

Each vehicle stores only:

```text
reference_track_id
formation_lane_change_done
```

`reference_track_id` is empty until the vehicle selects a visible reference.
It is cleared when that object is no longer visible, no longer in front, or no
longer physically valid. `formation_lane_change_done` changes to true only
after a formation-requested lane change completes. It is not reset during the
pure-formation run. Therefore a vehicle can complete at most one active
formation lane change in this stage.

The base NOA controller may retain its already existing safety and trajectory
execution state. That state is not part of formation target selection.

## 6. Local lane-balancing rule

Lane counts include the ego vehicle and visible physical vehicles within
`LOCAL_FORMATION_RANGE_M`. Only an unambiguous physical lane affiliation is
used for counting. A vehicle straddling a lane boundary remains present in the
collision guard but is excluded from the formation count until its lane is
unambiguous.

The vehicle considers only directly adjacent, physically available lanes. The
decision is:

```text
if an emergency or mandatory road maneuver is active:
    do not request a formation lane change
elif formation_lane_change_done is true:
    keep the current lane
elif this vehicle is not the local rear-most vehicle in its current lane:
    keep the current lane
elif no adjacent lane has a smaller local count:
    keep the current lane
elif two adjacent lanes tie for the smallest smaller count:
    keep the current lane
else:
    choose the unique less-populated adjacent lane
    if the base safety guard accepts its one continuous lane-change trajectory:
        execute that lane change without changing its target mid-maneuver
    else:
        keep the current lane and continue ordinary longitudinal control
```

"Local rear-most" means that no visible, unambiguously same-lane vehicle lies
behind the ego within `LOCAL_FORMATION_RANGE_M`. The strict count comparison is
`current_count > target_count`; a difference of one is sufficient. This is
required for a local `3/2/1` distribution to evolve toward `2/2/2` through
adjacent one-lane moves. A `2/2/2` distribution produces no balancing request.

There is no fallback to a second target lane after a tie or a rejected safety
check. That omission is deliberate: it keeps the decision deterministic and
prevents a hidden candidate-ranking system.

## 7. Nearest-ahead staggered-reference rule

Reference selection is independent for every vehicle:

```text
if the remembered reference is still visible, valid, and ahead:
    keep it
elif at least one valid vehicle is visible ahead:
    select the vehicle with the smallest positive longitudinal distance
else:
    clear the reference and use ordinary target-speed cruise
```

No reference is chosen by ID, vehicle type, intended maneuver, or global rank.
If two objects have exactly equal longitudinal distance within the existing
geometry tolerance, the formation reference is considered ambiguous and no
new reference is selected on that tick. The base safety controller still
reacts to both objects.

For a valid reference, the effective ego lane is the committed target lane
during an accepted lane change and otherwise the current lane. Desired
reference-point spacing is:

```text
if abs(reference_lane - effective_ego_lane) == 1:
    desired_gap = 15 m
else:
    desired_gap = 30 m
```

The second branch covers the same lane and the two outer lanes. This is the
local form of the alternating 15/30 m staggered geometry; it does not construct
or index a lattice.

Let `target_x = reference_x - desired_gap` in the road's increasing travel
coordinate and `error = target_x - ego_x`. The formation contribution is:

```text
if error > POSITION_TOLERANCE_M:
    request a small positive longitudinal correction
elif error < -POSITION_TOLERANCE_M:
    request a small negative longitudinal correction
else:
    match the visible reference speed without a position correction
```

The magnitude of the formation correction is capped by
`FORMATION_ACCEL_LIMIT_MPS2`. The base NOA following and emergency output
always has higher authority. With no reference, the formation contribution is
zero and the vehicle cruises toward `TARGET_SPEED_MPS`.

## 8. Safety and continuous execution

Formation logic produces at most one lane target and one longitudinal
correction. It does not decide that a maneuver is safe.

A formation lane request executes only when the existing Phase 4 base safety
guard confirms all of the following for the single configured continuous
trajectory:

- current-lane departure and target-lane entry remain within road bounds;
- target-lane front and rear clearance remain safe;
- visible-neighbor bounded motion does not intersect the ego body or swept
  body over the maneuver;
- the continuous kinematic controls respect the established physical limits.

An unsafe request becomes "stay in lane" and is checked again on a later
control tick. The vehicle does not stop solely to wait for formation. During an
accepted lane change, the formation layer cannot replace the target or start a
second maneuver. Emergency handling may override or safely terminate formation
behavior according to the base controller.

## 9. Code boundary

Implementation will be confined to the Phase 5G pure-formation variant and the
root demonstration entry:

- add `variants/phase5g_pure_formation/noa/simple_formation.py` for the pure
  local if/else rules;
- minimally connect it in
  `variants/phase5g_pure_formation/noa/controller.py` behind an explicit simple
  formation mode;
- point root `runrun.py` at the simple pure-formation demonstration;
- add focused tests under
  `variants/phase5g_pure_formation/tests/`;
- leave `noa/formation_lane.py`, prior formal records, and prior evidence
  directories present but outside the new demonstration call path.

The new rule module must not import experiment recorders, independent
detectors, global clocks, or scenario truth. Its inputs are an ego state, one
already filtered local observation, the two formation-memory values, and the
explicit rule parameters.

## 10. Failure behavior

- No visible forward reference: cruise normally.
- Remembered reference disappears or moves behind: clear it and apply the
  nearest-ahead rule.
- Equal-distance new references: select none on that tick.
- Equal-population adjacent lanes: stay in lane.
- Target-lane safety rejection: stay in lane and keep moving longitudinally.
- Formation lane change already completed: do not initiate another formation
  lane change.
- Emergency or mandatory road action: base NOA overrides formation.
- A case does not form: save the failure and its reason; do not relax safety,
  insert an obstacle, or assign global slots to force success.

## 11. Tests

Focused unit tests must establish:

1. no forward reference gives zero formation correction and target-speed
   cruise remains available;
2. a valid remembered reference is held rather than repeatedly replaced;
3. loss of the remembered reference selects the unique nearest visible vehicle
   ahead;
4. an equal-distance ambiguity selects no new reference;
5. adjacent-lane reference spacing is exactly 15 m;
6. same-lane and two-outer-lane reference spacing is exactly 30 m;
7. positive, negative, and in-tolerance position errors take the three stated
   longitudinal branches and respect the 0.5 m/s^2 default cap;
8. a non-rear-most vehicle cannot request a formation lane change;
9. a local rear-most vehicle may choose a uniquely less-populated adjacent
   lane when the base guard accepts it;
10. equal adjacent counts, unsafe clearance, and an already completed formation
    lane change all produce "stay";
11. changing out-of-range vehicles, true IDs, or hidden vehicle types does not
    change the action for identical ego state, local observation, and memory;
12. all agents decide from a frozen tick and cannot observe another agent's
    same-tick action.

Integration cases remain 3, 6, and 12 normal NOA vehicles on the three-lane
upstream road. The primary six-vehicle case starts with a safe non-formed local
`3/2/1` distribution. It contains no obstacle vehicle, scripted slow leader,
background traffic, or nonparticipating physical vehicle.

## 12. Acceptance and replay

An independent detector, not the controller, determines formation. The primary
six-vehicle target is:

- evolve from the registered `3/2/1` initial distribution toward `2/2/2` using
  local one-lane moves;
- complete at least one formation-requested lane change;
- satisfy the independent 15/30 m staggered relation tolerance as one connected
  local component within 30 s;
- maintain the detected structure for at least 10 s;
- recover to the target-speed neighborhood after forming;
- have no collision, teleport, nonphysical jump, or repeated formation lane
  change.

The three-vehicle case checks the smallest cross-lane relation. The twelve-
vehicle case checks that more than one local chain can form or records why a
single connected component did not form. No general convergence guarantee is
claimed.

Each run uses a fresh result directory and stores only the necessary replay
bundle: resolved top-level configuration, random seed, environment/version
metadata, trajectory, formation decisions, lane-change events, independent
detection result, and terminal reason. A replay consumes the saved resolved
configuration and seed. Successes and failures are both retained; no old run
is overwritten.

## 13. Explicit exclusions

This unit does not study obstacles, slow scripted leaders, HDVs, mixed traffic,
bottleneck reconstruction, efficiency improvement, energy savings, game
theory, random backoff, global convergence, or globally optimal assignment.
It demonstrates and measures only whether the approved minimal local rules can
form and maintain a safe pure-NOA staggered structure in the registered small
cases.
