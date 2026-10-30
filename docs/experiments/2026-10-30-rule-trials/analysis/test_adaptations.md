# CTH/TM test adaptations

Only four authorized test files and `tests/archived_rules_source.py` changed. The exact source/test patch is `test_adaptations.patch`; this change does not install a controller, modify Git state, or run SUMO.

Two equal-speed fixtures in `test_native_rules.py` now place the front at the specified distance `D*(v) = 5.5 + (24.5/28.8) v`. The two recorded body-following checks in `test_head_group_rules.py` retain their original physical states and actual-front identity, and use `front.x - D*(ego.speed)` as the expected target. Speed assertions and all numerical tolerances remain exact as before. The independent specification constants are written explicitly in the tests.

The two full-controller H equivalence tests in `test_common_pair.py` and the frozen-P equivalence test in `test_formation_state.py` now exercise the immutable state-enabled base from the existing public `docs/experiments/2026-10-29-local-formation-state/evidence.tar.gz`. The helper reads member `current_source/noa/native_rules.py` without extracting files and verifies SHA-256 `ac1c5aba082130718c81a23eb2c7bc9708caa8dae6b138baea951d07e735ee7d` before executing it in an independent module namespace. H/P source hash pins and all expected control/memory assertions remain unchanged. Random coverage remains seed 600 × 2 modes × 80 cases, seed 800 × 160 NOA cases, and seed 20261029 × 3 modes × 300 cases: 1220 historical cases in total.

Every other test still exercises the live controller, including the H phase-geometry comparison, actual-front selection, safety caps, visibility, private tracks, lane-completion feedback, NOA zero flags and direct continuous-1 statistics.

Pure validation used `validate_test_adaptations.py` to inject a chosen controller in memory and run 79 rule/state checks, including the two function-style ending-lane tests. It never calls a simulation test.

| Source / test state | Tests | Failures | Errors |
|---|---:|---:|---:|
| TM before adaptations | 79 | 7 | 0 |
| TM after adaptations | 79 | 0 | 0 |
| T after adaptations | 79 | 0 | 0 |
| Published fixed-gap base after adaptations, expected red | 79 | exactly 4 CTH assertions | 0 |

TM's validated SHA-256 is `65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317`. The base's four failures are deliberate evidence that the updated tests distinguish the new law; the three archived equivalence checks pass. The full 206-test command and SUMO/GUI checks remain for the parent after source adoption.

Evidence is saved in `test_adaptations_before_TM.json`, `test_adaptations_after_TM.json`, `test_adaptations_after_T.json`, `test_adaptations_after_base_expected_red.json`, and `test_adaptations_evidence.json`. `archive_loader_checks.json` confirms independent module globals and rejection of tampered source before execution. Durable runner logs are under `tmp/literature_trials/analysis/results/operations/` with labels `cth_tests_before_TM`, `cth_tests_after_TM`, `cth_tests_after_T`, and `cth_tests_after_base_expected_red`.
