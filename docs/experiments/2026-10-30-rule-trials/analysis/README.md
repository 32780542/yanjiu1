# Saved-run analyzer

This standalone Python script uses only the standard library. It reads saved evidence; it neither imports controllers nor starts SUMO. The historical complete-layer detector is never called. `experiments/complete_layers.py` is only one of the recorder's source snapshots whose bytes are checked.

```powershell
python docs/experiments/2026-10-30-rule-trials/analysis/analyze_trials.py --manifest PATH_TO_MANIFEST.json --output OUTPUT_DIRECTORY
```

The manifest must be a JSON list. Each record must contain `candidate`, `stage`, `flow`, `seed`, `scenario`, `mode`, and `run_dir`. Candidate labels are preserved verbatim; the reference label is `base`. Modes `noa` and `transform` produce the within-candidate comparison. Relative run directories resolve against the manifest directory. The analyzer enforces the agreed 600 s demand / 900 s maximum trial config, without modifying the protocol.

Every run should contain:

- `input.json`: the recorder's `case`, `arrivals`, complete `physical` mapping, speed/lane-change modes, positions sampling step and source hash mapping.
- `result.json`: matching config/hash mapping, final status/safety/completion counts, SUMO version, direct full-road statistics and the `formation_state` summary.
- `trips.json`: original trip rows, including `vehicle_id`, entered/exited times, and original demand identities. No derived complete-layer table is used.
- `positions.jsonl.gz`: original `time_s`, `states[id]=[x,y,speed,acceleration]`, and integer `formation_states[id]=0|1` frames.
- `sumo_command.json` and every file listed in `source_sha256`, under `source/`.

All snapshots must match their recorded SHA-256 values, and the input/result hash maps must agree. Paired runs must have identical arrivals, physical settings, config except mode, SUMO version/command, and non-rule source hashes. Run-local command paths are normalized to compare commands. Across candidates only `noa/native_rules.py` may differ; within one candidate its NOA and transform snapshots must be identical. A failed provenance check keeps the row and blocks its paired deltas.

Outputs:

| File | Contents |
|---|---|
| `per_case.csv` | Every manifest record, direct result metrics, independent flag audit, segment eligibility counts, issues |
| `paired.csv` | Candidate minus base in the same mode; transform minus NOA within the same candidate |
| `paired_aggregates.csv` | Mean seed-paired differences within stage/flow/scenario/mode; entire group suppressed when any pair is invalid |
| `segment_vehicles.csv` | Each original vehicle's upstream/bottleneck crossing times, eligibility and exclusion reason |
| `analysis.json` | All tables, definitions and interpretation warnings |
| `report.md` | Compact readable aggregate table and case issues |

The primary flag columns come directly from `result.json`. The independent audit uses a left-constant integral of all reported 0/1 flags between recorded times, and the same unthresholded continuous-1 episodes. `mean_episode_s` is the existing mean continuous-1 duration. Participants are total reported participants, not the size of one platoon.

Upstream time means the observed front-position crossing from x=100 to 600 m; bottleneck time is x=640 to 1100 m. Crossings interpolate linearly only within two consecutive observations of the same vehicle that bracket the threshold. There is no extrapolation, whole-group gate, whole-window requirement or additional geometric condition. Each vehicle needs both segment crossings and a recorded road entry; the run's safety/completion status is separate. Per-case means use each run's eligible vehicles; paired segment means/differences use only the intersection of vehicle IDs eligible in both runs. Missing crossings do not remove another vehicle or suppress unrelated full-road metrics.

Full-road TT/system time/fuel and entry wait remain the recorder's direct eligible metrics. Completed/departed subset values on failed or incomplete cases are retained as descriptive columns. Unsafe, incomplete, missing, mismatched or unauditable runs have no paired deltas. An aggregate with a bad pair is suppressed instead of silently averaging only successful seeds. A metric missing from any otherwise valid pair also has no aggregate mean.

Candidate versus base estimates the whole candidate rule change within one mode. T-minus-base includes the changed following law. Within the same T or TM candidate, NOA and transform share that longitudinal law; their remaining differences include organization, cooperative merging and overtaking policy. This is a complete-strategy comparison. TM-transform minus T-transform isolates the incremental fill-cost rule under the same new following. Original base NOA remains separately visible. M/R reuse base NOA explicitly; an absent same-candidate NOA table row is not a failed simulation. Segment eligibility and the tested demand are stated with each table.

Fixture verification:

```powershell
python docs/experiments/2026-10-30-rule-trials/analysis/test_analyze_trials.py
```

The tests create tiny valid/unsafe/invalid saved-run fixtures and never launch SUMO. The byte-identical repository log runner was copied to `tmp/literature_trials/analysis/scripts/run_logged.py` so all test operations stay under the analyzer's assigned directory. Red/green evidence is retained in `tmp/literature_trials/analysis/results/operations/`.
