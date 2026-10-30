# Independent heldout-results review

Reviewed the completed original 250-case manifest `tmp/literature_trials/batches/20261030T010842083890Z_heldout/manifest.json`. No simulation, source/test modification, parameter selection, or Git operation was performed. This report is the only file created during this results review.

## Independent primary-data checks

For every case, recomputed mean TT from each original `trips.json` as mean(exited_s − entered_s), system time as mean(exited_s − requested_s), entry waiting as mean(entered_s − requested_s), fuel as Σfuel_mg / Σdistance_m (numerically g/km), and lane-index changes/completed lateral moves from original trip events. All six metrics match each original `result.json` and the completed main analyzer's `heldout250_analysis/per_case.csv`; no numerical discrepancies were found within 1e−8 absolute / 1e−10 relative tolerance.

All 250 cases are recorded safe and drained, with completed=requested and every original trip complete. Every saved source file matches its declared SHA-256 in both result and input. The five common source files have one identical hash each across all 250 cases; only the intended rule-source hash varies (base `ac1c5aba…`, T `046f00aa…`, TM `65142b44…`). For each of 50 flow/seed/road keys, all five profiles have identical original arrivals, physical parameters, execution modes, and insertion configuration.

An additional independent streaming integration read **1,602,184 original position frames** across all 250 cases. It integrated the preceding frame's direct binary flags over each actual time interval and reconstructed continuous-1 episodes at flag transitions/disappearance. There were zero invalid flag frames and zero discrepancies from original `result.json` formation-state statistics; maximum absolute difference was 7.11e−15. This did not use complete-layer detection or the main analyzer's integration function.

## Paired results

Each road has 25 matched cases: five flows × five heldout seeds. All rows below are candidate minus reference, equal-weight case means; with this balanced design this also gives each flow and seed equal weight. Participation changes are percentage points, not relative percentages. LC denotes lane-index changes.

| Comparison | Road | Δ TT (s) | Δ fuel (g/km) | Δ LC/case | Δ participation (pp) | Δ mean continuous-1 (s) |
|---|---|---:|---:|---:|---:|---:|
| T − original formation | 3→2 | −0.124392 | −2.366423 | −31.08 | −0.085452 | +0.466016 |
| T − original formation | straight | −0.019171 | −0.964358 | −27.40 | −0.321476 | +0.306600 |
| TM − T | 3→2 | +0.000669 | −0.182636 | −8.36 | −0.076750 | −0.037557 |
| TM − T | straight | −0.005602 | −0.202700 | −5.00 | +0.014579 | +0.145358 |
| TM − original formation | 3→2 | −0.123723 | −2.549059 | −39.44 | −0.162202 | +0.428459 |
| TM − original formation | straight | −0.024773 | −1.167058 | −32.40 | −0.306897 | +0.451958 |

The stated primary bottleneck-report comparisons reproduce independently from original trips, including TM−T drop TT +0.000668693 s and fuel −0.182635978 g/km, TM−original formation drop TT −0.123723399 s and fuel −2.549058841 g/km. This review did not independently recompute regional density or low-speed vehicle-seconds; the bottleneck evaluator's reported density/low-speed tradeoffs must still be retained in interpretation.

M's added fuel benefit occurs in 19/25 drop cases and 20/25 straight cases. Every flow's five-seed fuel mean and every seed's five-flow fuel mean decreases on both roads. The small magnitudes matter: at flow 500 the straight-road mean reduction is only 0.001589 g/km. Drop TT improves in 12/25 cases and worsens in 13/25; straight TT improves in 13/25 and worsens in 12/25. Thus M does not establish a robust TT improvement.

Fewer lane changes and longer state episodes are also not universal. Drop LC decreases in 17/25 cases (two ties), straight in 14/25 (one tie). Seed 13's five-flow mean LC increases by 4.2/case on drop and 9.2/case on straight despite lower fuel. Drop mean continuous-1 decreases in 15/25 cases; straight increases in 18/25. M's drop flow means decrease continuous-1 at 500/750/1000/1250 and increase it at 1500. These are small, mixed relation-duration tradeoffs, not uniform retention improvement.

## Adoption interpretation

Keeping TM is defensible as two concise, cohesive mechanisms: T has the separately tested damping mechanism and larger heldout fuel gains; M adds a modest, repeatable average fuel reduction and fewer average lane changes. Its aggregate TT cost at the drop is negligible in this experiment, but it should be presented as a tradeoff rather than a Pareto improvement or better bottleneck discharge. Five independent seeds and finite tested flows do not establish universal improvement or statistical significance. No additional evidence was found that makes this limited adoption unsound.

Compared with original formation, TM improves **mean continuous-1 duration**, while participation rate decreases on both roads. Do not summarize both metrics as unqualified improved retention.

The matched-following reference remains essential. TM formation minus TM NOA gives drop TT −0.108344 s and fuel **+4.408513 g/km**, and straight TT **+0.009309 s** and fuel **+3.737534 g/km**. New NOA minus original NOA gives fuel +2.335552 / +1.113209 g/km on drop/straight, respectively. Therefore the changes improve the existing formation controller's fuel use; they do not show that formation is generally more efficient than its NOA reference. Remaining policy differences prevent interpreting formation−NOA as one isolated formation subrule.
