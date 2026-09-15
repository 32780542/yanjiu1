# Phase 5G Final Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the five final-review findings without changing the approved simple local if/else formation policy or its safety behavior, then produce a clean-checkout-capable and replayable Phase 5G evidence set.

**Architecture:** Keep the no-communication controller and existing swept safety guard as the behavioral core. Add lossless guard diagnostics, a bounded input-derived launcher timeout, streaming trace evaluation/replay, and a deliberately enumerated tracked runtime closure; then regenerate evidence once per preregistered case and report engineering and scientific outcomes separately.

**Tech Stack:** Python 3.12 standard library, `unittest`, SUMO/TraCI, JSON/JSONL evidence, PowerShell, Git, and `scripts/run_logged.py`.

---

## Non-negotiable execution rules

- Resume from `docs/phase5_checkpoint.md`; use `rg` before reading or editing.
- Execute exactly one task below at a time with a fresh implementer subagent. After its tests and commit, dispatch a specification reviewer and then a code-quality reviewer. Resolve every finding and repeat the relevant review before starting the next task.
- Use TDD. Every long command goes through `scripts/run_logged.py` with a fresh label and an explicit timeout. Preserve every failed log and result prefix.
- Do not add communication, global vehicle lists/counts, true-ID priority, global slots, central allocation, obstacle vehicles, candidate scoring, or rule retuning. Controller actions and safety acceptance must remain unchanged in Tasks A–D.
- Existing external anchored packages are immutable. Compatibility is verified through their saved code snapshots; do not reseal, edit, or backfill an old package.
- Never use `git add -A`. Never add `results/`, `tmp/`, PDFs, old variants, or unrelated historical assets. Do not push.
- Unless a clean-archive step explicitly changes directory, run every command from `D:\yanjiu1\keyan1`; the root `scripts/run_logged.py` therefore owns and logs each long child.

### Task A: Preserve both guard decisions and expose the active rejection

**Files:**
- Modify: `variants/phase5g_pure_formation/noa/controller.py:232-244,390-431,570-615`
- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_controller.py:183-230,293-322`
- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_harness.py:716-764`

- [ ] **Step 1: Add RED tests for complete, lossless guard diagnostics**

Extend the lane-rejection test so a safe longitudinal request followed by a rejected lane request retains both results, and the public active guard is the lane rejection:

```python
simple = decision.diagnostics["simple_formation"]
self.assertEqual(simple["longitudinal_guard"], {
    "kind": "longitudinal", "result": SAFE,
})
self.assertEqual(simple["lane_guard"], {
    "kind": "lane_change", "result": REJECTED,
})
self.assertEqual(simple["guard"], simple["lane_guard"])
self.assertFalse(simple["guard"]["result"]["safe"])
self.assertEqual(simple["guard"]["result"]["reason"],
                 "neighbor_reachable_occupancy")
self.assertEqual(simple["guard"]["result"]["at_s"], 0.1)
self.assertEqual(simple["guard"]["result"]["checked_s"], 0.1)
```

Add the inverse cases: longitudinal rejection is still recorded when not applied; lane acceptance is recorded; an active-plan fallback records each attempted guard without changing the executed acceleration. Snapshot the returned `Actuation`/memory from the current behavior in assertions so diagnostic work cannot change decisions.

- [ ] **Step 2: Prove RED through the logged runner**

```powershell
python scripts/run_logged.py --label review-a-guard-red --timeout 180 -- python -I -B -S variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py controller
```

Expected: nonzero because `longitudinal_guard` and `lane_guard` do not exist and the current public guard incorrectly remains the safe longitudinal result after lane rejection.

- [ ] **Step 3: Implement separate diagnostic slots with a compatibility alias**

Initialize all three fields:

```python
"longitudinal_guard": None,
"lane_guard": None,
"guard": None,
```

Immediately after every simple-branch `verify_candidate` call, store the full returned mapping regardless of `safe`:

```python
simple_diagnostic["longitudinal_guard"] = {
    "kind": "longitudinal", "result": guard,
}
simple_diagnostic["guard"] = simple_diagnostic["longitudinal_guard"]
```

and:

```python
simple_diagnostic["lane_guard"] = {
    "kind": "lane_change", "result": guard,
}
simple_diagnostic["guard"] = simple_diagnostic["lane_guard"]
```

The last guard for the action currently under consideration is the compatibility `guard`; therefore a lane rejection cannot be published as a safe longitudinal guard. Preserve `safe`, `reason`, `at_s`, and `checked_s` verbatim. Do not change the acceleration, plan, memory transition, rule order, or safety call arguments.

- [ ] **Step 4: Verify current and saved-schema replay compatibility**

Keep the existing `guard` field so current consumers accept both old single-guard and new dual-guard diagnostics. Extend the outer replay test to assert replay dispatches through the sealed `code_snapshot` for an old-schema fixture; it must not import current controller semantics into that replay. Also replay the existing immutable anchored six-car package by literal path if present:

```powershell
python scripts/run_logged.py --label review-a-current-tests --timeout 300 -- python -I -B -S variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py all
python scripts/run_logged.py --label review-a-phase5g-regression --timeout 600 -- python -I -B -S variants/phase5g_pure_formation/tests/phase5g_test_launcher.py all
python scripts/run_logged.py --label review-a-old-snapshot-replay --timeout 900 -- python -I -B -S variants/phase5g_pure_formation/run.py phase5g-replay --run-dir variants/phase5g_pure_formation/results/phase5g/simple_demo/20260914T185222941842Z_ae97e081
```

Expected: both suites pass with no skips; the old anchored package replays from its snapshot and no old file changes. If that literal external package is absent, record the absence in the log and rely on the committed synthetic saved-snapshot test; do not recreate it under the old name.

- [ ] **Step 5: Commit and pass both review gates**

```powershell
git add variants/phase5g_pure_formation/noa/controller.py variants/phase5g_pure_formation/tests/test_simple_formation_controller.py variants/phase5g_pure_formation/tests/test_simple_formation_harness.py
git commit -m "fix: preserve simple guard rejection evidence"
```

Spec review gate: verify separate results exist for every executed guard and public `guard` selects lane rejection over earlier longitudinal safety. Quality review gate: verify no behavioral diff, no lossy result projection, and old snapshot replay remains isolated.

### Task B: Make the direct entry robust in a clean layout

**Files:**
- Modify: `demo/sumo_gui.py:216-288,1534-1586,2047-2060`
- Modify: `tests/test_runrun_demo.py:264-296,1114-1170,1565-1595`
- Modify: `variants/phase5g_pure_formation/experiments/phase5g.py:203-226,1282-1365`
- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_harness.py:348-443`

- [ ] **Step 1: Add RED timeout and clean-layout tests**

Add a pure-function contract:

```python
self.assertEqual(gui.simple_generation_timeout_s(45.0, 3), 198)
self.assertEqual(gui.simple_generation_timeout_s(45.0, 6), 306)
self.assertEqual(gui.simple_generation_timeout_s(45.0, 12), 522)
self.assertGreater(gui.simple_generation_timeout_s(45.0, 12), 411.375)
```

Patch the process runner and assert `timeout` equals this function, not `180`. Add a `TemporaryDirectory` project layout with required config, SUMO stubs, network, and variant entry but no `variants/phase5g_pure_formation/results`; `check_simple_environment` must return successfully, create no directory, and start no process. Add a harness test showing normal `run_phase5g_demo` safely creates a missing validated `results/...` output base, while an escaped output path still fails before writes.

- [ ] **Step 2: Prove RED**

```powershell
python scripts/run_logged.py --label review-b-entry-red --timeout 240 -- python -B -m unittest discover -s tests -p test_runrun_demo.py -v
python scripts/run_logged.py --label review-b-output-red --timeout 240 -- python -I -B -S variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py harness
```

Expected: timeout assertions fail and `--check` rejects the missing results directory.

- [ ] **Step 3: Implement the pure timeout formula and boundary**

Use no filesystem or process state:

```python
def simple_generation_timeout_s(duration_s: float, vehicle_count: int) -> int:
    budget = math.ceil(90.0 + 0.8 * duration_s * vehicle_count)
    if budget > 3600:
        raise ValueError("simple formation生成预算超过3600秒支持边界")
    return max(180, budget)
```

The domain remains validated duration and counts `{3, 6, 12}`. This gives 522 s for 12 vehicles × 45 s, over the measured 411.375 s with 110.625 s margin. Use the result in `subprocess.run` and report the computed value in timeout errors.

- [ ] **Step 4: Separate read-only validation from append-only output creation**

In `validate_simple_config`, require `variant_root` and `variant_run`, but do not require or create `variant_results`; return its resolved future path. Thus `runrun.py --check` remains zero-write. In the normal generator, retain `_validated_output_base` as the containment boundary and let `RunRecord.__enter__` create only the resolved run ancestry. Reject files, reparse points, project/workspace roots, and escaped paths before creation.

- [ ] **Step 5: Run logged verification and side-effect checks**

```powershell
python scripts/run_logged.py --label review-b-root-tests --timeout 300 -- python -B -m unittest discover -s tests -p test_runrun_demo.py -v
python scripts/run_logged.py --label review-b-harness --timeout 300 -- python -I -B -S variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py harness
python scripts/run_logged.py --label review-b-check --timeout 120 -- python runrun.py --check
```

Expected: pass with no skips; compare before/after directory and process inventories in the test and prove `--check` created nothing.

- [ ] **Step 6: Commit and pass both review gates**

```powershell
git add demo/sumo_gui.py tests/test_runrun_demo.py variants/phase5g_pure_formation/experiments/phase5g.py variants/phase5g_pure_formation/tests/test_simple_formation_harness.py
git commit -m "fix: make simple launcher clean-layout safe"
```

Spec review gate: verify the 12-car budget is 522 s, check mode is zero-write, and only the normal generator may create its contained output base. Quality review gate: verify the formula is deterministic/bounded and path validation cannot create outside variant `results`/allowed Temp.

### Task C: Stream generation evaluation and replay

**Files:**
- Modify: `variants/phase5g_pure_formation/experiments/phase5g.py:565-794,868-1015`
- Modify: `variants/phase5g_pure_formation/experiments/phase5g_replay.py:154-259,262-367`
- Modify: `variants/phase5g_pure_formation/experiments/phase5.py:35-41`
- Modify: `variants/phase5g_pure_formation/experiments/phase4_audit.py:77-143`
- Modify: `variants/phase5g_pure_formation/tests/test_simple_formation_harness.py`

- [ ] **Step 1: Add RED semantic, read-discipline, prefix, and memory tests**

Create a synthetic 12-car, 450-interval JSONL fixture by writing one row at a time. Assert:

```python
with patch.object(Path, "read_text", side_effect=reject_trace_read_text):
    streamed = phase5g.evaluate_trace(trace_path, case, model, physical,
                                       live=False)
self.assertEqual(streamed, phase5g.evaluate_records(short_rows, case, model, physical))
```

Instrument the trace opener and require a documented bounded number of sequential scans (at most four), never `read_text().splitlines()`. Measure only the evaluation/replay call with `tracemalloc`; require peak Python allocation below 64 MiB for the 342.30 MiB-class fixture. Add a failed-tail fixture and assert the completed physical prefix, hashes, lifecycle fields, and derived artifacts match current semantics.

- [ ] **Step 2: Prove RED**

```powershell
python scripts/run_logged.py --label review-c-stream-red --timeout 300 -- python -I -B -S variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py harness
```

Expected: current generation holds `records`, replay calls `_records`, and the memory/read-discipline tests fail.

- [ ] **Step 3: Introduce a re-openable physical-record iterator**

Implement a generator that opens the JSONL normally, parses one nonblank line at a time, applies `_record_is_physical`, yields it, and releases it before reading the next. It must preserve a failed physical tail when `commit_applied` is true. Track counts during the write loop only; remove `records.append(...)` and compute all post-run facts from the already flushed trace.

- [ ] **Step 4: Make evaluation bounded-memory without changing outputs**

Add `evaluate_trace(trace_path, case, model, physical, *, live)` using no more than four sequential scans:

1. build only compact sampled formation frames and the last state for detection/speed;
2. feed a fresh iterator directly to `geometry_report`;
3. compute per-actor driving accumulators in one pass (states, modes, tracking values, extrema) through a streaming-compatible helper in `phase4_audit.py`;
4. compute lane-change and speed facts from streaming per-actor/summary state.

Rewrite `frames_from_records` so it consumes an iterable without first materializing records. Keep `evaluate_records` as a small-fixture compatibility wrapper over the same aggregation logic. Preserve every JSON field, numeric definition, hash, scientific gate, exact replay comparison, and failed-prefix lifecycle result.

- [ ] **Step 5: Remove replay materialization**

Delete `_records`. `replay_variant` first performs the existing line-by-line exact decision/integration replay, then calls `evaluate_trace` for independent derived evidence. It must never call `Path.read_text` or `splitlines` on `trace.jsonl`; metadata and small JSON files may still use strict whole-file reads. Do not weaken manifests or exact `compare_tree` checks.

- [ ] **Step 6: Run focused and inherited verification**

```powershell
python scripts/run_logged.py --label review-c-stream-tests --timeout 600 -- python -I -B -S variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py all
python scripts/run_logged.py --label review-c-phase5g-tests --timeout 900 -- python -I -B -S variants/phase5g_pure_formation/tests/phase5g_test_launcher.py all
python scripts/run_logged.py --label review-c-root-tests --timeout 300 -- python -B -m unittest discover -s tests -p test_runrun_demo.py -v
```

Expected: exact semantic fixtures pass, failed prefix remains replayable, peak stays under 64 MiB, and no selected test is skipped.

- [ ] **Step 7: Commit and pass both review gates**

```powershell
git add variants/phase5g_pure_formation/experiments/phase5g.py variants/phase5g_pure_formation/experiments/phase5g_replay.py variants/phase5g_pure_formation/experiments/phase5.py variants/phase5g_pure_formation/experiments/phase4_audit.py variants/phase5g_pure_formation/tests/test_simple_formation_harness.py
git commit -m "perf: stream phase5g trace evaluation"
```

Spec review gate: verify generation and replay never retain all full records, read passes are bounded, hashes/exact replay are unchanged, and failed prefixes survive. Quality review gate: inspect iterator closure/error propagation and ensure compact aggregates cannot alias mutable trace objects.

### Task D: Commit the minimal runnable Phase 5G baseline

**Files:**
- Create: `scripts/audit_runtime_closure.py`
- Create: `tests/test_phase5g_tracked_baseline.py`
- Add to Git, without modifying content: only the proven runtime/test closure under top-level and `variants/phase5g_pure_formation/`

- [ ] **Step 1: Implement the closure audit and derive the minimal closure before staging anything**

Seed the audit with `runrun.py`, `demo/sumo_gui.py`, `configs/tools.json`, `scripts/run_logged.py`, the Phase 5G `run.py`, `SOURCE_FILES`, `INPUTS`, `configs/phase5g.json`, `scenarios/cai2024/bottleneck.net.xml`, the two test launchers, and focused simple/root tests. Use `rg` for literal paths/settings calls and an AST import walk for local `Import`/`ImportFrom`; include each resolved `.py`, package `__init__.py`, referenced JSON/XML/CSV/design/plan file, and tests imported by launchers. Print the exact closure in the logged output and write the same reviewed, repo-relative, newline-delimited paths to `tmp/phase5g-runtime-closure.txt`.

```powershell
python scripts/run_logged.py --label review-d-closure-audit --timeout 180 -- python -I -B -S scripts/audit_runtime_closure.py --output tmp/phase5g-runtime-closure.txt --entry runrun.py --entry variants/phase5g_pure_formation/run.py --launcher variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py --launcher variants/phase5g_pure_formation/tests/phase5g_test_launcher.py
```

Create `scripts/audit_runtime_closure.py`, test it in `tests/test_phase5g_tracked_baseline.py`, and include it in the closure. The script must reject unresolved local imports and any selected path under `results`, `tmp`, PDF files, old `variants`, or unrelated archived assets.

- [ ] **Step 2: Add RED tracked-closure tests**

The test obtains `git ls-files -z`, recomputes the exact dependency closure, and asserts every required path is tracked and every forbidden prefix/suffix is absent. It must initially report the missing baseline rather than silently reading untracked files.

```python
self.assertFalse(required - tracked, sorted(required - tracked))
self.assertFalse({p for p in tracked if p.startswith("results/")})
self.assertFalse({p for p in tracked if "/results/" in p or "/tmp/" in p})
self.assertFalse({p for p in tracked if p.lower().endswith(".pdf")})
```

- [ ] **Step 3: Prove RED, then stage only the audited list**

```powershell
python scripts/run_logged.py --label review-d-baseline-red --timeout 180 -- python -B -m unittest discover -s tests -p test_phase5g_tracked_baseline.py -v
git status --short
```

Review `tmp/phase5g-runtime-closure.txt` line by line, confirm it exactly matches the logged closure, then use that explicit pathspec list; never use a glob or `git add -A`:

```powershell
Get-Content -LiteralPath tmp/phase5g-runtime-closure.txt
git add --pathspec-from-file=tmp/phase5g-runtime-closure.txt
git diff --cached --name-only
```

Fail if the staged list contains `results`, `tmp`, `.pdf`, any variant other than `phase5g_pure_formation`, or unrelated history.

- [ ] **Step 4: Verify a true Git archive, not the dirty workspace**

Export the staged index as a temporary tree, archive that exact tree, expand it beneath a fresh system Temp directory, and run there:

```powershell
$reviewTree = (git write-tree).Trim()
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$reviewArchive = Join-Path ([System.IO.Path]::GetTempPath()) ("phase5g-review-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $reviewArchive | Out-Null
git archive --format=tar $reviewTree | tar -xf - -C $reviewArchive
Push-Location $reviewArchive
python runrun.py --check
python -I -B -S -c "from pathlib import Path; import os,sys; root=Path('variants/phase5g_pure_formation').resolve(); os.chdir(root); sys.path.insert(0,str(root)); import experiments.phase5g,experiments.phase5g_replay,noa.controller,simulation.phase5g_clock"
python -B -m unittest discover -s tests -p test_runrun_demo.py -v
python -I -B -S variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py all
Pop-Location
```

Expected: check, imports, and focused short tests pass from the archive with no dependency on an untracked workspace file. `--check` must not create `results`; normal short generation in a Temp output may create only its validated append-only prefix.

- [ ] **Step 5: Commit and pass both review gates**

```powershell
git commit -m "build: track runnable phase5g baseline"
```

Spec review gate: compare the staged list to the computed import/source-hash closure and confirm all required files and only allowed scopes are present. Quality review gate: independently run the archive test and inspect for machine secrets, generated evidence, reparse points, PDFs, old variants, and accidental historical assets.

### Task E: Regenerate final evidence and update the checkpoint

**Files:**
- Modify: `README.md`
- Modify: `docs/phase5_checkpoint.md`

- [ ] **Step 1: Prove the final-review evidence closure is RED**

Before generating anything, require the final checkpoint to name all five remediations and all fresh evidence obligations:

```powershell
rg -n "longitudinal_guard|lane_guard|522 s|zero-write|64 MiB|simple_final_review|SHOW_GUI=False" README.md docs/phase5_checkpoint.md
```

Expected: nonzero because at least one remediation/evidence marker is absent. This is the documentation acceptance RED; do not manufacture paths or outcomes to make it pass.

- [ ] **Step 2: Run complete logged regression**

```powershell
python scripts/run_logged.py --label review-e-compile --timeout 180 -- python -I -B -S -m compileall -q variants/phase5g_pure_formation/noa variants/phase5g_pure_formation/simulation variants/phase5g_pure_formation/experiments variants/phase5g_pure_formation/tests demo tests
python scripts/run_logged.py --label review-e-simple-all --timeout 900 -- python -I -B -S variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py all
python scripts/run_logged.py --label review-e-phase5g-all --timeout 1200 -- python -I -B -S variants/phase5g_pure_formation/tests/phase5g_test_launcher.py all
python scripts/run_logged.py --label review-e-root-demo --timeout 600 -- python -B -m unittest discover -s tests -p test_runrun_demo.py -v
python scripts/run_logged.py --label review-e-root-regression --timeout 1200 -- python -I -B -S run.py test
```

Expected: all changed-path suites pass with tests run and no skips. Preserve and distinguish any unrelated inherited failure; do not close the task while a changed-path regression fails.

- [ ] **Step 3: Generate exactly one fresh 3/6/12 evidence run each**

Use output base `results/phase5g/simple_final_review`. Run in order and record each literal returned path; never select or retry by scientific outcome:

```powershell
python scripts/run_logged.py --label review-e-final-3 --timeout 900 -- python -I -B -S variants/phase5g_pure_formation/run.py phase5g-demo --offline --vehicle-count 3 --seed 1 --target-speed-mps 10 --duration-s 45 --output-base results/phase5g/simple_final_review
$sixOperationOutput = & python scripts/run_logged.py --label review-e-final-6 --timeout 1200 -- python -I -B -S variants/phase5g_pure_formation/run.py phase5g-demo --offline --vehicle-count 6 --seed 1 --target-speed-mps 10 --duration-s 45 --output-base results/phase5g/simple_final_review
if ($LASTEXITCODE -ne 0) { $sixOperationOutput; exit $LASTEXITCODE }
$sixOperation = [System.IO.Path]::GetFullPath([string](($sixOperationOutput | Select-Object -Last 1 | ConvertFrom-Json).path))
$sixRun = [System.IO.Path]::GetFullPath([string](((Get-Content -LiteralPath (Join-Path $sixOperation 'stdout.log') | Where-Object { $_.Trim() } | Select-Object -Last 1 | ConvertFrom-Json).path)))
Write-Output "SIX_RUN=$sixRun"
python scripts/run_logged.py --label review-e-final-12 --timeout 1800 -- python -I -B -S variants/phase5g_pure_formation/run.py phase5g-demo --offline --vehicle-count 12 --seed 1 --target-speed-mps 10 --duration-s 45 --output-base results/phase5g/simple_final_review
```

If one run fails, preserve that prefix and stop evidence generation for review rather than replacing it with another seed/run.

- [ ] **Step 4: Replay the exact six-car path and analyze guard rejections**

```powershell
python scripts/run_logged.py --label review-e-final-6-replay --timeout 1200 -- python -I -B -S variants/phase5g_pure_formation/run.py phase5g-replay --run-dir $sixRun
```

Keep this step in the same PowerShell session as Step 3. PowerShell expands `$sixRun` before `run_logged.py` starts, so the operation metadata records the exact absolute run path rather than `latest.json`. Stream-scan its trace and record counts by `kind`, `safe`, and `reason`, plus `at_s`/`checked_s` completeness. Specifically verify lane `safety_rejected` rows expose a rejected public lane guard rather than a safe longitudinal guard. Do not alter rules in response to the counts.

- [ ] **Step 5: Verify the 12-car direct launcher path and peak memory**

Run `python runrun.py --check`, then use an in-memory patch of `runrun.SHOW_GUI=False`, `VEHICLE_COUNT=12`, and `SIMULATION_DURATION_S=45.0`; do not edit committed defaults. Route this through a logged test/helper and assert the subprocess receives the 522 s timeout and returns a fresh trusted trace. Measure generation post-processing and replay peak Python memory with `tracemalloc`; record the observed peak and require it below the Task C 64 MiB ceiling.

- [ ] **Step 6: Implement the evidence documentation from verified facts only**

Update `README.md` and `docs/phase5_checkpoint.md` with commits, changed files, exact log directories/exit codes, literal 3/6/12 paths, exact six replay, guard rejection counts and field completeness, memory peaks, and direct Run/Debug instructions. Preserve every old negative result and limitation. Report separately:

1. engineering: execution/replay, collision, geometry, comfort, entry/check, memory;
2. science: actual 30 s formation + 10 s hold result and speed recovery;
3. limitations: 3/12 behavior, unchanged local-rule/safety constraints, and any failure.

Do not claim traffic efficiency, energy benefit, or formation success unless the independent evidence passes those exact gates.

- [ ] **Step 7: Run logged documentation verification, commit, and pass both review gates**

```powershell
git diff --check
git status --short
git diff --stat HEAD
python scripts/run_logged.py --label review-e-doc-closure --timeout 120 -- python -B -m unittest discover -s tests -p test_phase5g_tracked_baseline.py -v
rg -n "longitudinal_guard|lane_guard|522 s|zero-write|64 MiB|simple_final_review|SHOW_GUI=False" README.md docs/phase5_checkpoint.md
git add README.md docs/phase5_checkpoint.md
git commit -m "docs: record final phase5g remediation evidence"
git log --oneline -12
git status --short
```

Spec review gate: trace every final-review finding to a passing test/log/evidence field and verify one-and-only-one new run per size. Quality review gate: independently check literal paths, replay output, memory measurement method, unchanged old evidence, and engineering/science separation.

After both gates pass, run the `verification-before-completion` workflow and an overall `requesting-code-review` pass across Tasks A–E. Report local commits and the GitHub remote status, but do not push to GitHub.
