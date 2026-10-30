# Frozen-trial bottleneck diagnostics

`docs/experiments/2026-10-30-rule-trials/analysis/bottleneck_trials.py` calls the existing `experiments.bottleneck_attribution.evaluate_case` once per sealed case. That evaluator calls the existing `native_comparison.load_case`. A declared direct local-state schema is required before entry, so the historical formation evaluator is not used. No simulation or controller execution is involved.

The existing definitions are retained: six measured gates at 100/600/640/800/1000/1100 m; route TT/system/entry wait and segments 100–600, 640–1100, 800–1100 m; region 800≤x<1000 m with three physical lanes; region window [100,600) s; low speed strictly below 5 m/s; vehicle-time-weighted mean speed; and first 1000 m crossings in inclusive [100,600] s divided by 500 s and multiplied by 3600. The crossing flow is observed window flow, **not bottleneck capacity**. The evaluator's existing audit, censoring and all-requested-vehicle requirements remain unchanged. No new admission or formation thresholds are introduced.

The original direct `result.json` fuel and lane-change metrics are carried alongside the evaluator's recomputed traffic metrics. Lane-index transitions and physically completed lateral changes remain separate. Pair deltas are candidate minus reference. Base/TM transform-minus-NOA compares complete strategies with the same longitudinal law; TM-minus-T transform is M's increment conditional on CTH. Cross-version base/T/TM differences retain their distinct source hashes and cannot all be attributed to organization.

Pairs require eligible cases, identical request digests, identical physical/SUMO parameter digests, and identical non-rule source digests. Within-candidate pairs also require identical complete source hash maps. The existing native audit checks saved snapshot bytes and input/result/trip identities. Unsafe, incomplete or censored cases remain in per-case output; affected pairs and their attempted-seed aggregate groups have no performance differences. Five equally represented flows are retained in the heldout design. Straight/drop effects use the existing lane_drop-minus-straight definition for each profile and input.

Each immutable per-case cache contains:

- `case.json`: evaluator outputs, raw input/result/trips/positions SHA-256, saved source hashes, evaluator/wrapper hashes, ledger hashes and reconstruction checks.
- `region_steps.jsonl.gz`: header followed by lossless arrays `[time_s,end_s,n,low_speed_n,speed_sum_mps]` for the original measured, adjacent-step exposure ledger. Other step quantities follow from these existing fields.
- `gate_brackets.jsonl.gz`: header followed by `[vehicle_index,gate_m,t0,x0,t1,x1]`, retaining original adjacent measurement endpoints. Exact first-observation gates use a degenerate bracket.
- `vehicles.json.gz`: original requested-vehicle identities, request/entry/exit observations, evaluator gate/censor statuses and segment records. Vehicle indices in the bracket ledger index this list.

The wrapper reads back the ledgers and reconstructs the existing region-window results, all observed gate times, all vehicle segment times and the window crossing count using the evaluator's existing tolerances. Numeric JSON arrays round-trip original floating-point measurements without rounding. Cached inputs are sealed; cache reuse checks file sizes/timestamps, evaluator hashes and compressed ledger hashes. The original raw-file SHA values remain recorded for a later independent check. A changed cached input/evaluator is rejected rather than overwriting prior evidence.

Reports under `reports/TAG/` are immutable. `per_case.csv`, `paired.csv`, flow/scenario `paired_means.csv`, `overall_paired_means.csv`, `scenario_effects.csv`, `scenario_effect_means.csv` and `report.json` share the same cases and caches. The report saves its selected manifest snapshot and source-manifest SHA. Selected profiles must each have all 50 heldout records before a report is built.

```powershell
python -B docs/experiments/2026-10-30-rule-trials/analysis/bottleneck_trials.py --manifest tmp/literature_trials/batches/20261030T010842083890Z_heldout/manifest.json --output tmp/literature_trials/bottleneck_analysis --profiles base_noa base_transform T_transform --tag base_T150
```

When all five profiles are sealed, omit `--profiles` and use a fresh tag. The base/T case caches are reused. The original evaluator's 14 regression contracts passed in operation `20261030T013930097206Z_existing_bottleneck_contracts_pathfixed_a3f6afa3`; the earlier runner attempt lacked the variant on PYTHONPATH and is retained as an environment failure. The single-case real-data pilot `20261030T014133288111Z_bottleneck_pilot_88a5ac31` passed the existing audit and every ledger reconstruction check. Full simulation regressions remain outside this analysis task.
