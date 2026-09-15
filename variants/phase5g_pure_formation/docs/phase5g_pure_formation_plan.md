# Phase 5G Pure Formation Research Plan

## Approved specification inputs

- `docs/superpowers/specs/2026-09-14-phase5g-pure-formation-design.md` — SHA-256 `233824da02501a844c8254cca2ee5aaa300cfdde34f286a0e850a3df31ae6bde`
- `docs/superpowers/plans/2026-09-14-phase5g-pure-formation.md` — SHA-256 `365e441bf2165be04eb988bdc200d0c5302974758a7735bcce089bc18bb63b19`

## Pre-registered protocol

Phase 5G is a pure 100% NOA formation study. R5 is disabled. Every physical
actor is a controlled formation participant. The planned formation counts are
3, 6, and 12. There are no obstacles, scripts, HDV, or bottleneck actors.
Safety lane changes are permitted by the study design, but this Task 2 only
registers their parameters and supplies pure geometry primitives; it does not
connect a lane-change controller.

The only registered parameter source is
`configs/phase5g.json`, with these fixed values:

| Parameter | Value |
| --- | --- |
| `phase5g_enabled` | `true` |
| `formation_lane_change_enabled` | `true` |
| `formation_lane_stable_s` | `1.0` s |
| `formation_lane_lock_s` | `5.0` s |
| `formation_lane_front_margin_m` | `2.0` m |
| `formation_lane_backoff_min_s` | `0.5` s |
| `formation_lane_backoff_max_s` | `2.0` s |
| `formation_lane_duration_candidates_s` | `[5.0, 7.5, 10.0]` s |
| `formation_lane_min_relation_gain` | `1` |
| `phase5g_target_speed_mps` | `10.0` m/s |
| `phase5g_initial_speed_min_mps` | `8.0` m/s |
| `phase5g_initial_speed_max_mps` | `12.0` m/s |
| `phase5g_duration_s` | `45.0` s |

Post-result retuning is not permitted under this version. Any change requires
a newly named version with a separately pre-registered configuration and plan.

## Task 2 geometry contract

The lane primitive is deterministic and local: it ranks a candidate first by
the number of satisfied relations, then by maximum residual, residual sum,
whether it changes lane, and descending lane index. `rank_candidates` selects
the best stay candidate using that key. A change candidate is eligible only
when it improves satisfied relations by at least the registered minimum gain.
When more than one stay candidate is supplied, the deterministic best stay is
used rather than treating the input as ambiguous. A reference signature is
either absent or seven finite numeric fields; its final two fields are positive
length and width.

Candidates with exactly identical sorting keys retain their input order. This
exact-tie case is therefore not claimed to be permutation-invariant.
