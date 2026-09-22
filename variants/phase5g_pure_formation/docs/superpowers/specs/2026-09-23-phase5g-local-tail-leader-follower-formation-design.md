# Phase 5G local-tail leader-follower formation design

Date: 2026-09-23
Status: approved section-by-section in conversation; written specification awaiting user review

## 1. Goal

Replace the current Phase 5G simple formation behavior with a local,
communication-free three-lane leader-follower formation that works for
vehicles emitted dynamically at seeded random times, speeds, and lanes.

The required formation has two aligned outer-lane columns and one middle-lane
column shifted 15 m rearward. Vehicles in the same lane follow at 30 m. New
vehicles join at the physical tail, one at a time. The controller must use
only finite local observations and private per-vehicle memory. It must not
read a global actor list, global lane counts, true vehicle identifiers, an
offline slot table, another vehicle's memory, or same-tick actions.

This unit forms and maintains a formation. It does not perform formation
transformation, bottleneck reconstruction, obstacle avoidance experiments,
mixed-traffic negotiation, or global optimal assignment.

## 2. Physical formation geometry

Road lanes are reconstructed from visible physical road geometry. In this
document:

- `upper` means the lane with the greatest physical lateral coordinate;
- `middle` means the middle physical lane;
- `lower` means the lane with the smallest physical lateral coordinate;
- `front` means increasing road-travel coordinate.

These labels must not be obtained from a hidden SUMO lane identifier.

The target geometry is:

```text
travel direction ->

upper:   O----------------O----------------O
middle:  --------O----------------O----------------O
lower:   O----------------O----------------O
             15 m             15 m
```

The exact relations are:

- paired upper- and lower-lane vehicles have a 0 m longitudinal offset;
- each middle-lane vehicle is 15 m behind its corresponding upper-lane
  vehicle;
- successive vehicles in one lane are 30 m apart;
- the position tolerance is 2 m;
- the formed relative-speed tolerance is 1 m/s.

The upper lane is the longitudinal reference lane. Its front vehicle is the
formation leader. The lower-lane leader aligns its front with the upper-lane
leader. The middle-lane leader follows 15 m behind the upper-lane leader.

## 3. Local formation boundary

Formation membership is defined by a 50 m continuous longitudinal chain.
After sorting only currently visible physical vehicles by road-travel
coordinate, consecutive vehicles whose longitudinal separation is at most
50 m belong to the same locally connected component. A separation greater
than 50 m breaks the chain and starts a separate local formation.

This definition permits a long formation to extend beyond one vehicle's full
view: a joining decision never needs the complete component. It uses only the
visible, connected tail neighborhood. A vehicle more than 50 m behind the
front component does not react to it. If it never enters the component tail's
50 m neighborhood, it creates a new independent local formation.

The experiment layer may know the full spawn schedule for simulation and
evidence, but that information is never supplied to the controller.

## 4. Tail assembly sequence

Formation construction uses a repeated local three-vehicle sequence:

```text
1. upper
2. lower, aligned with that upper vehicle
3. middle, 15 m behind that upper vehicle
```

The next sequence begins with a new upper vehicle 15 m behind the most recent
middle vehicle. This also places it 30 m behind the preceding upper vehicle.

The first isolated vehicle in a new component is its founder and moves to the
upper lane under the hard safety gates in Section 9. Subsequent vehicles begin
joining only after entering the current formed tail's 50 m neighborhood.

The joining vehicle recognizes the next action from physical tail geometry:

```text
if the visible tail is a stable middle vehicle:
    target the upper lane, 15 m behind that middle vehicle
elif the rearmost layer has a stable upper vehicle but no aligned lower vehicle:
    target the lower lane and align with that upper vehicle
elif the rearmost layer has aligned stable upper and lower vehicles:
    target the middle lane, 15 m behind that upper vehicle
else:
    use the local count recovery rule in Section 5
```

This is a local physical pattern, not a global slot index. No controller may
compute the total fleet size or an actor's ordinal in the fleet.

If the final target lane is two lanes away, the vehicle performs two adjacent
lane changes while retaining the same final lane and anchor. It is not marked
stable in the intermediate lane. There is no lifetime limit on formation lane
changes, but one vehicle may have only one active lateral plan at a time.

Already formed vehicles retain their lanes. This unit does not reorder a
formed component for a transformation request.

## 5. Local relative lane-count recovery

When the tail pattern is temporarily malformed or incomplete, the joining
vehicle counts only unambiguously lane-associated vehicles in its visible,
50 m connected tail neighborhood. Let the counts be `U`, `M`, and `D` for the
upper, middle, and lower lanes.

The least-populated lane is selected. A tie uses the fixed physical priority:

```text
upper > lower > middle
```

Examples are:

- `0/0/0` -> upper;
- upper `1`, middle `0`, lower `0` -> lower;
- upper `1`, middle `0`, lower `1` -> middle;
- `1/1/1` -> upper for the next layer.

The recognized tail pattern in Section 4 has priority over this recovery
rule. This prevents a sliding 50 m window from losing the three-step phase.
The count rule recovers an irregular tail; it does not replace the normal
upper/lower/middle assembly cycle.

For any completed local formation of `N` vehicles, the required distribution
is:

- `N = 3k`: `k/k/k`;
- `N = 3k + 1`: the upper lane has the extra vehicle;
- `N = 3k + 2`: the upper and lower lanes have the extra vehicles.

Thus the maximum lane-count difference is at most one. The middle lane never
receives a remainder vehicle before both outer lanes.

## 6. One-at-a-time local admission

Each local formation admits at most one joining vehicle at a time. Eligibility
is derived from visible physical geometry:

1. The eligible waiting vehicle is the one longitudinally closest behind the
   stable tail, with no other waiting vehicle physically between it and the
   tail.
2. If two candidates are longitudinally equal within geometry tolerance, the
   candidate in the physically upper lane has priority.
3. If physical lane association or the priority relation is still ambiguous,
   both wait for another observation. True IDs and shared randomness are not
   used.
4. All farther waiting vehicles continue ordinary local car following.
5. A following vehicle may reconsider admission only after observing the
   previous joiner at its target lane and position with the required speed
   tolerance continuously for 1 s.

Vehicles never inspect another vehicle's `join_phase`. They infer completion
from observed position, lane, and speed.

## 7. Private memory and reference replacement

Each vehicle stores only the formation state it needs:

```text
reference_track_id
join_anchor_track_id
desired_lane_index
join_phase              # FREE, JOINING, STABILIZING, or FORMED
stable_since_s
```

Local track labels may preserve association with a currently visible physical
object. They must not determine priority or expose a true simulator ID.

References may change. Each tick, the controller compares the remembered
reference with visible valid alternatives. A new reference replaces the old
one only if its implied target position reduces absolute position error by at
least 2 m. A disappeared, invalid, or rearward reference is cleared without a
delay. This permits correction while preventing rapid reference oscillation.

Once a join maneuver starts, its final lane and join anchor remain fixed until
completion or loss of the physical anchor. Loss of the anchor causes a safe
fallback to local longitudinal following and a fresh local decision; it does
not trigger a global search.

## 8. Leader-follower longitudinal controller

The upper-lane leader has no formation reference and tracks
`TARGET_SPEED_MPS`. Other references are selected locally:

- an upper-lane follower uses the nearest valid upper-lane vehicle ahead with
  a 30 m target gap;
- a lower-lane vehicle aligns with the locally corresponding upper-lane
  vehicle by choosing the visible upper reference with the smallest implied
  target-position error;
- a middle-lane vehicle targets 15 m behind the visible upper reference with
  the smallest implied target-position error;
- when no valid upper reference is available, a lower- or middle-lane vehicle
  falls back to the nearest same-lane vehicle ahead at 30 m;
- an active joiner uses the fixed tail anchor and target from Section 4.

Formation control produces the final longitudinal request; it is not added to
the base NOA cruise acceleration. For a valid reference:

```text
position_error = target_x - ego_x
speed_offset = clip(position_error / 5, -2 m/s, +2 m/s)
desired_speed = reference_speed + speed_offset
requested_acceleration = clip(desired_speed - ego_speed,
                              -3 m/s^2, +2 m/s^2)
```

The leader uses the same acceleration limits while approaching the configured
target speed. Position regulation therefore has priority while forming, and
followers may temporarily travel up to 2 m/s faster or slower than their
reference. Once position error disappears they match reference speed and
converge to the leader's target speed. This removes the prior cancellation
between a formation increment and the NOA cruise request.

A joining vehicle becomes locally stable only after all of the following hold
continuously for 1 s:

- it is at the selected lane center within the existing lane-completion
  tolerance;
- longitudinal position error is at most 2 m;
- reference-relative speed is at most 1 m/s;
- no emergency longitudinal condition is active.

## 9. Minimal formation safety gates

Formation behavior bypasses the current conservative neighbor-reachable
occupancy guard. It must not reject a formation action merely because a
neighbor could hypothetically take any bounded acceleration or lateral action
over the full maneuver horizon.

The following hard gates remain mandatory:

- do not start a formation lane change below 5 m/s;
- do not start a formation lane change when any currently visible vehicle in
  the target lane has a longitudinal center distance below 8 m;
- do not start or continue a lateral target outside the visible physical road;
- retain actual body-overlap prevention and the existing immediate emergency
  braking response for a dangerously close current-lane lead;
- retain physical acceleration, braking, steering, steering-rate, jerk, and
  vehicle-model bounds.

No conservative reachable-set `verify_candidate` result is required for a
normal formation maneuver. The 8 m rule is the approved simple target-lane
gap check adapted from `D:\matlab_huipu_2000\isLaneChangeGapSafe.m`; the
reference implementation uses `max(minSafeGap, 8)`. The 50 m component rule
and 15 m formation gap are adapted from the MATLAB formation grouping and
`formationControl.m` geometry without carrying over its global assignment.

If a hard gate becomes active during an already started lane change, the final
lane target is not switched. The existing immediate NOA longitudinal safety
response controls speed while the lateral controller retains the fixed target,
avoiding a sudden reverse maneuver while straddling lanes.

## 10. Seeded dynamic departures

The Phase 5G experiment creates a replayable departure schedule from a private
experiment seed. For every physical vehicle it records:

- departure time;
- initial physical lane;
- initial speed;
- stable physical row ordinal used only by the offline generator.

The default demonstration parameters are:

```python
VEHICLE_COUNT = 12
RANDOM_SEED = 1
DEPART_INTERVAL_MIN_S = 2.5
DEPART_INTERVAL_MAX_S = 4.0
INITIAL_SPEED_MIN_MPS = 8.0
INITIAL_SPEED_MAX_MPS = 12.0
FORMATION_JOIN_RANGE_M = 50.0
TARGET_SPEED_MPS = 10.0
MIDDLE_LANE_OFFSET_M = 15.0
SAME_LANE_GAP_M = 30.0
MIN_FORMATION_LANE_CHANGE_SPEED_MPS = 5.0
HARD_LANE_CHANGE_GAP_M = 8.0
SIMULATION_DURATION_S = 90.0
```

Departure lanes, speeds, and intervals vary with the seed. Equal seeds produce
byte-identical schedules. A vehicle does not exist in the physical snapshot or
any local observation before its scheduled departure. SUMO may delay physical
insertion only when required to avoid an initial overlap; the actual insertion
time is recorded and used for evaluation.

The default interval yields approximately 25-40 m of travel at 10 m/s, so the
default run normally builds one component. Larger user-configured intervals
may produce independent components, which are evaluated separately rather
than being forced to catch one another.

## 11. Synchronous data flow and information boundary

Each simulation tick follows this order:

```text
apply scheduled departures
-> freeze one common physical snapshot
-> build a separate finite local observation for every present vehicle
-> compute every decision from that frozen snapshot and private memory
-> apply all actions together
-> advance the physical model
-> record truth and local diagnostics
```

Decision loop order must not expose another vehicle's same-tick action.
Scenario generation, truth logging, and offline detection may use global data,
but controller modules may not import or query them.

## 12. Code boundaries

Implementation is confined to the Phase 5G variant and the root demonstration
path:

- `noa/simple_formation.py`: local component, tail pattern, count recovery,
  admission priority, reference selection, and private formation state;
- `noa/controller.py`: direct formation longitudinal control, hard gates,
  adjacent lane-plan progression, and base emergency fallback;
- `experiments/phase5g_cases.py`: deterministic dynamic departure schedules;
- `experiments/phase5g.py`: actor insertion, frozen-tick execution, evidence,
  and replay metadata;
- `experiments/phase5_detection.py`: offline dynamic-membership and independent
  per-component formation evaluation;
- `demo/sumo_gui.py`: dynamic actor playback and strict artifact validation;
- root `runrun.py`: editable configuration and debug-friendly entry;
- focused tests under `variants/phase5g_pure_formation/tests/` and root
  demonstration tests under `tests/`.

Prior result directories remain immutable. New runs always use new output
directories. Prior Phase 5F and legacy Phase 5G mechanisms remain available as
historical evidence but stay outside the new demonstration call path.

## 13. Test-first requirements

Implementation follows red-green-refactor. Production behavior is changed
only after a focused test has failed for the expected missing behavior.

Local-rule tests cover:

- a 50 m link joins a component and a separation above 50 m splits it;
- stable middle tail -> upper, upper-only tail -> lower, aligned outer tail ->
  middle;
- malformed tails use local counts and the upper/lower/middle tie priority;
- the nearest waiting vehicle acts first and an equal-position tie favors the
  physical upper lane;
- ambiguous association waits without using IDs;
- no out-of-range vehicle, hidden type, or true ID changes a local decision.

Control tests cover:

- upper, lower, and middle target geometry;
- reference replacement only after at least 2 m improvement;
- direct formation acceleration cannot be cancelled by cruise acceleration;
- speeds below 5 m/s and target-lane gaps below 8 m return to the safety path;
- an otherwise valid formation lane change bypasses reachable-occupancy
  rejection;
- a two-lane destination completes as two adjacent maneuvers;
- no lifetime one-change limit remains;
- only one local joiner acts while a prior join is unfinished;
- 1 s physical stability releases the next vehicle.

Dynamic-execution tests cover:

- deterministic schedule generation and different-seed variation;
- actors are absent before departure and present afterward;
- all decisions use a frozen tick;
- dynamic traces and failures replay with identical decisions;
- SUMO playback creates vehicles at recorded times rather than at time zero;
- `runrun.py` remains directly runnable, debugger-friendly, and validates all
  editable parameters before creating an output directory.

Integration tests cover vehicle counts 3, 4, 5, 6, 7, 8, and 12, including the
approved remainder distributions. Counts 3, 6, and 12 run seeds 1 through 5.
They check collision, road containment, physical continuity, lane balance,
leader alignment, 15/30 m geometry, speed convergence, sequential admission,
and evidence completeness. A separate gap case verifies two independent
components when the departure gap exceeds 50 m.

After focused tests pass, the affected existing simple-formation, controller,
Phase 5G harness/replay, root GUI, baseline, and full repository test suites
must pass with zero failures and errors.

## 14. Independent evaluation and completion criteria

The offline detector must support vehicles that appear during the run. It may
use truth only after decisions are recorded. It partitions current vehicles by
the 50 m continuous-chain definition and evaluates each component separately.

For the default run, completion requires:

- all 12 scheduled vehicles physically depart;
- all vehicles belong to the intended locally connected component;
- lane counts satisfy the approved `3k`, `3k+1`, or `3k+2` distribution;
- aligned outer references have at most 2 m longitudinal error;
- middle references have `15 +/- 2 m` offset from the upper lane;
- same-lane followers have `30 +/- 2 m` gap;
- component speed spread is at most 1 m/s;
- no simultaneous conflicting admission occurs;
- no collision, road departure, teleport, missing actor, or nonphysical jump
  occurs;
- the complete formation is confirmed within 30 s after the last actual
  vehicle departure and then remains valid for another 10 s.

The fixed random validation matrix is 3, 6, and 12 vehicles for seeds 1-5.
Every run is retained, including failures. Passing the default demonstration
does not permit deleting or filtering a failed seed. A claim that random
departures form successfully requires the fixed matrix and its replays to
pass; otherwise the exact achieved success rate and failure reasons are
reported.

## 15. Explicit exclusions

This implementation does not add V2V/V2I messages, a central coordinator,
global lane populations, global formation slots, true-ID priority, shared
randomness, optimizer-based assignment, game-theoretic negotiation, obstacle
vehicles, scripted slow vehicles, mixed traffic, or formation transformation.
It does not claim general convergence beyond the approved three-lane,
finite-local-view, sequential-tail-admission assumptions.
