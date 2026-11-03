# Frozen paired experiments

`runner.py` freezes the ten required runtime/configuration files from
`177f7a32088fb69efcc94d9acb72863e7e00e787`. An unqualified candidate name uses
that commit's TM rules; `NAME=path/to/native_rules.py` replaces only the rule file.
Production sources are never edited. Each output directory must be new and below
`tmp/staggered_bottleneck`. Every case has a separate `run_logged.py` operation,
worker log, input/result/trips/source records, and final case record.
All planned case output names are checked for collisions before any batch
directory or worker is created, including collisions from rounded float flows.

From the repository root, for example:

```powershell
python -B scripts/run_logged.py --label staggered-example --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate TM --stage example --flows 1250 1750 --seeds 1 4 --scenarios straight3 lane_drop --modes transform --duration 180 --max-time 500 --jobs 4 --output tmp/staggered_bottleneck/NEW_NAME --prune-raw
```

`seal_case.py` directly reuses the previous round's `compact_evidence.py` and
`analysis/bottleneck_trials.py`. It runs compact verification with original hash
and selected-field checks, traffic ledger reconstruction, and a second offline
verification. Only after these checks does `--prune-raw` unlink the two exact
`positions.jsonl.gz` / `events.jsonl.gz` paths inside the owned new batch. All
targets and hashes are checked before either unlink. Failed sealing retains the
raw files and writes `seal_error.log`. No recursive cleanup is performed.

The compact bundle contains byte-exact original JSON and all six simulation
sources, every direct 0/1 frame, and observed crossing brackets. The traffic
directory preserves the existing measured-region and crossing ledgers. Full
positions/events are hash-indexed, and are absent after successful pruning.
Selected-field/hash evidence does not reconstruct the complete original trace.

To recheck an already pruned case, use its `evidence` directory:

```powershell
python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/seal_case.py verify tmp/staggered_bottleneck/BATCH/cases/CASE/evidence
```

Traffic verification still imports the hash-pinned older repository methods;
those dependencies must be retained when publishing. Each compact tarball also
contains its own standalone verifier. This tool does not invoke the historical
formation detector or SUMO during verification.

To verify and analyze one or several complete batches:

```powershell
python -B scripts/run_logged.py --label staggered-example-analysis --timeout 600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/BATCH1 tmp/staggered_bottleneck/BATCH2 --output tmp/staggered_bottleneck/NEW_ANALYSIS
```

Outputs are `per_case.csv`, `paired.csv`, and `summary.json`. Duplicate
candidate/flow/seed/scenario/mode identities, even across different stages, are
errors. Missing reference cases and unsuccessful cases stay visible as rejected
pairs. Every protocol task is matched to its manifest and byte-exact original
input/result/trips, request digest, and frozen source hashes. Missing/unplanned
cases and protocol mismatches remain visible and ineligible. Default pairs are TM transform minus TM NOA and each candidate minus TM
at the same mode. Source, demand, parameter and eligibility checks and all paired
differences reuse the existing methods; no averaging is introduced.

The published [100,600) s region window, 800–1000 m region, three lanes and
5 m/s low-speed threshold are unchanged. Short runs retain measured partial
exposure in the original `region_window` ledger, while formal incomplete-window
metrics remain null. Such partial exposure is not a full-window comparison or a
capacity measurement. Direct flag participants are not one platoon's size.

The baseline load180 batch is `20261103_TM_load180_32`; do not repeat it.
Its verified analysis is `20261103_TM_load180_32_analysis`.
