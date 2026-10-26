# Phase 5G live formation and evaluation implementation plan

> **For agentic workers:** implement one independently verifiable unit at a time, with a failing test before each behavior change.

**Goal:** Show each computed formation step immediately in SUMO-GUI, remove the deadline and hold success gates, repair local rules, and measure formation across 2, 3, and 4 lanes.

**Architecture:** Preserve the isolated Phase5G controller and sealed record source. Stream completed model frames to a parent GUI process with one acknowledgment per visual step. Keep physical formation, safety, and record validity as separate outcomes. Generalize road geometry and layer occupancy from three lanes to a configured lane count without giving the controller global information.

**Tech Stack:** Python 3.12, unittest, TraCI/SUMO, JSONL records.

---

### Unit 1: Success definition and duration

**Files:** `demo/sumo_gui.py`, `variants/phase5g_pure_formation/experiments/phase5g.py`, `variants/phase5g_pure_formation/experiments/phase5_detection.py`, adjacent tests.

- [ ] Write tests that accept a run ending after the last scheduled departure and recognize orderly geometry after one second regardless of formation time.
- [ ] Run the tests and record the expected failures.
- [ ] Remove the 30 s and 10 s dynamic-demo gates; retain a fixed observation end and report censored nonformation.
- [ ] Run focused detector and demo tests, then update the checkpoint.

### Unit 2: Local formation rules

**Files:** `variants/phase5g_pure_formation/noa/simple_formation.py`, `noa/controller.py`, `tests/test_layered_formation.py`, relevant controller tests and design specification.

- [ ] Test occupied preferred slot, a separate component beyond 50 m, and active joining under nonemergency NOA headway braking; observe failures.
- [ ] Select a visibly empty legal slot, restrict decisions to the physical component, and apply formation acceleration under the existing hard safety checks.
- [ ] Run focused tests and report each new rule to the user.

### Unit 3: Live GUI lockstep

**Files:** `demo/sumo_gui.py`, `variants/phase5g_pure_formation/experiments/phase5g.py`, `run.py`, `tests/test_runrun_demo.py`.

- [ ] Test GUI-first launch, first-frame behavior, one model tick per GUI step, ACK blocking, and failure-prefix preservation; observe failures.
- [ ] Stream flushed frames from the isolated model process, wait for parent ACK, and render them through one stateful TraCI step function.
- [ ] Verify a short real GUI run and sealed source loading.

### Unit 4: Lane-count and parameter experiments

**Files:** Phase5G scheduler, controller, detector, road builder, demo configuration, experiment harness, and adjacent tests.

- [ ] Test 2, 3, and 4 lane geometry with alternating 15 m lane phases and 30 m same-lane period; observe failures.
- [ ] Add constant-width roads and per-lane demand 300, 600, and 900 vehicles/hour, paired seeds, fixed observation horizon, parameter variants, and independent metrics.
- [ ] Execute the preregistered matrix, preserve every failed run, and publish machine-readable results plus a limitations-aware analysis.

### Unit 5: Delivery

**Files:** `README.md`, design specification, `docs/phase5_checkpoint.md`, evaluation protocol and results.

- [ ] Document each added rule, formulas and denominators, live-run instructions, actual matrix outcomes, and external metric sources.
- [ ] Run affected regression and exact replay checks; inspect the Git diff; commit the completed work.
