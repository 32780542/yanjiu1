# Phase 5F Speed-Adaptive Duration Design

## Status and approval

This design turns the already published `docs/phase5_next_entry.md` into one independently acceptable Stage 5 research unit. The user approved that entry by asking to continue the research after the 5E delivery. Git has no `HEAD`, so this design cannot be committed; it will instead be SHA-256-bound into the Phase 5F experiment inputs and final evidence package.

## Research question

When local lane priority is already enabled and an ego vehicle has a genuine lane-change motivation below 5 m/s, does a finite set of speed-adaptive lane-change durations contain a candidate that passes the existing local competition gate and the unchanged full-horizon `verify_candidate` safety check? A safe candidate may be executed, but one completion is not formation, recovery, mutual exclusion, fairness, traffic benefit, or a general safety proof.

Phase 5F remains inside Stage 5. Stage 6/7/8 stay closed unless the pre-existing scientific criteria are independently satisfied.

## Considered approaches

1. **Duration-only diagnostic with the 5 m/s initiation gate unchanged.** This can report hypothetical guard results but cannot test actual low-speed initiation. It is useful as a pre-implementation sweep, not as the implementation.
2. **Recommended: a finite speed-and-duration candidate set behind an explicit Phase 5F switch.** Try the frozen durations 5.0, 7.5, and 10.0 s, use the measured ego speed rather than a synthetic 5 m/s reference speed, reject candidates that violate a derived kinematic lower bound, and pass every remaining candidate through the existing R5 gate and `verify_candidate`. Select only the shortest actually safe candidate. This isolates one mechanism and preserves failure.
3. **Directly lower `noa_min_lane_change_speed_mps` and keep the 5 s trajectory.** This confounds the old gate with an unqualified threshold change, gives no evidence for why the new value is controllable, and risks bypassing the model/safety chain. It is excluded.

## Frozen candidate set and derived lower bounds

For lane width `W`, wheelbase `L`, maximum steering `delta_max`, and duration `T`, the two-segment quadratic reference has peak lateral acceleration

`a_ref,max(T) = 4 W / T^2`.

The kinematic bicycle cannot produce more than `v^2 tan(delta_max) / L` at the hard steering limit. A necessary, not sufficient, reference-tracking condition is therefore

`v >= sqrt(4 W L / (T^2 tan(delta_max)))`.

With the frozen values `W=3.3 m`, `L=2.7 m`, and `delta_max=40 deg`, the exact pre-registered floors are:

| Duration | Peak reference lateral acceleration | Necessary speed floor |
|---:|---:|---:|
| 5.0 s | 0.528 m/s^2 | 1.3034431025565734 m/s |
| 7.5 s | 0.23466666666666666 m/s^2 | 0.8689620683710490 m/s |
| 10.0 s | 0.132 m/s^2 | 0.6517215512782867 m/s |

All three reference peaks are below the unchanged 2 m/s^2 comfort limit. These inequalities only decide whether a candidate may be checked. They do not certify tracking, road containment, neighbor clearance, or comfort. Zero speed remains rejected by the existing `own_actuator_unobservable_at_stop` rule, and speeds below every duration-specific floor produce no candidate.

## Architecture and control flow

The new isolated version is `variants/phase5f_adaptive_duration`, cloned without overwrite from the sealed 5E formal source and input snapshots. The parent 5E directory and every old result remain read-only.

`noa/low_speed.py` owns only deterministic candidate mathematics: validation of the exact duration tuple, peak reference acceleration, per-duration necessary speed floor, and the admissible duration list. It reads only passed parameters and measured ego speed.

`noa/controller.py` retains the old path byte-for-byte when Phase 5F is disabled, when R5 is disabled, or when visible lane priority is disabled. In the enabled path it:

1. requires the same motivation, cooldown, emergency, road, and local-observation conditions;
2. evaluates durations in the frozen ascending order 5.0, 7.5, 10.0 s;
3. creates each admissible `QuadraticLaneChange` with the measured positive ego speed;
4. evaluates R5 competition for that candidate;
5. calls the unchanged `verify_candidate` with the existing longitudinal request;
6. selects the first candidate that is both locally unblocked and guard-safe;
7. preserves `PREPARE_LC`, behavior-tick commit, active-plan re-verification, emergency fallback, and completion semantics.

Diagnostics record every duration, measured speed, derived floor, reference peak, R5 reason, guard reason, requested acceleration, and selected duration. An empty safe set is an explicit result, not a forced pass.

`noa/r5.py` must use `candidate.duration_s` rather than the old fixed 5 s value when computing the relative-speed competition radius. Otherwise a 7.5/10 s candidate would be assessed over an incorrectly short local-contention horizon. This changes only the enabled candidate being assessed; the disabled 5E compatibility path remains fixed at its 5 s candidate.

`configs/phase5f.json` registers the switch and exact duration tuple. `experiments/phase5_r5.py`, its replay, and `run.py` expose an explicit `--lane-change-policy fixed|adaptive_duration`. The fixed mode reconstructs the 5E behavior from the new source; the adaptive mode activates Phase 5F only for `r5_enabled=true` and `r5_lane_priority_enabled=true` variants. R5-off and priority-waiting controls remain fixed baselines.

## Pre-implementation sweep

Before production code changes, a read-only diagnostic reconstructs real saved controls from the fixed/minimax/Stackelberg three-vehicle traces at the documented clear speeds near 0.032, 1.701, and 1.849 m/s, plus the documented 4.511 m/s and exact 5.0 m/s boundaries. It evaluates 5/7.5/10 s candidates using the 5E source, unchanged longitudinal request, reconstructed road, current R5 assessment, and unchanged `verify_candidate`.

The sweep records model-floor rejection, R5 blocking, road, neighbor, and guard results separately. It is descriptive and cannot authorize implementation success. The output is frozen before the first production edit.

## Tests

TDD starts with tests that fail because Phase 5F does not exist:

- exact duration validation and the three derived floors;
- zero speed and below-floor rejection;
- real 1.70/1.85/4.511/5.0 m/s admissibility boundaries;
- every constructed duration reaches the real `verify_candidate` unless model/R5 rejection occurs;
- shortest safe duration selection and fall-through to longer safe durations;
- no safe candidate means no prepare or plan;
- fixed mode, R5-off mode, and lane-priority-off mode preserve 5E decisions;
- R5 relative-speed radius uses the actual candidate duration;
- CLI, input binding, run metadata, expected variants, and standard replay reconstruct the lane-change policy exactly.

After RED/GREEN, run the affected inherited controller/R5/record/replay tests with zero skips and freeze the tested source. Unaffected 5E evidence is reused rather than rerunning every earlier suite.

## Formal experiment and evidence

Three packages are pre-registered:

1. the 5C extension cases in `fixed` mode, providing a same-source 5E-compatible control;
2. the same extension cases in `adaptive_duration` mode, testing the real three-vehicle low-speed case;
3. the original eight-case/17-variant set in `adaptive_duration` mode, checking broader regressions including the speed-floor collision case.

Each package gets the standard semantic replay. The comparison binds source, input, case, road, private-state, and parameter hashes and reports per actor: motivation, eligibility, candidate counts and durations, R5/guard rejection reasons, first prepare, first commit, completion, minimum/mean/final speed, comfort/tracking, native SUMO warnings, and formation intervals.

## Acceptance and failure handling

Engineering delivery requires RED/GREEN evidence, affected regression with no failure/error/skip, immutable source/input manifests, all declared formal attempts started or explicitly retained as prefixes, standard replay of every package, and a hash-exact completion manifest.

Scientific acceptance is not implied by engineering delivery. Collisions, guard rejection, no completion, poor tracking, or no formation remain failures. No result may be rescued by shrinking neighbor reachability, suppressing SUMO warnings, changing comfort/hard limits, reading hidden vehicle type or private intent, using true IDs, communication, global slots, or central scheduling.

