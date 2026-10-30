# Final 250-case bottleneck interpretation

The immutable source is `reports/all250/report.json`, with per-case, paired, flow/scenario means and straight/drop effects in adjacent CSVs. All 250 cases and 300 requested method pairs passed the existing evaluator/audit. Each of five profiles has all five flows × five heldout seeds × two roads. The following lane-drop means equally represent the five flows and seeds. No simulation, new formation evaluator, threshold change or numerical rounding was used.

Region diagnostics retain 800≤x<1000 m, three physical lanes and [100,600) s; low speed is strictly v<5 m/s. Route TT and 640–1100 m times use their existing whole-trip/observed-gate definitions. The different spatial/time weighting means that a smaller main-segment time does not imply a higher fixed-window 800–1000 m mean speed.

| Lane-drop comparison, candidate minus reference | Δ route TT (s) | Δ system time (s) | Δ upstream 100–600 (s) | Δ main 640–1100 (s) | Δ fuel (g/km) |
|---|---:|---:|---:|---:|---:|
| base transform − base NOA | −0.00695 | +0.01765 | +0.05451 | −0.14741 | +9.29312 |
| TM NOA − base NOA | −0.02233 | −0.00405 | −0.00522 | −0.06664 | +2.33555 |
| T transform − base transform | −0.12439 | −0.13169 | −0.03749 | −0.04253 | −2.36642 |
| TM transform − base transform | −0.12372 | −0.13101 | −0.04268 | −0.03692 | −2.54906 |
| TM transform − T transform, M increment | +0.00067 | +0.00068 | −0.00519 | +0.00561 | −0.18264 |
| TM transform − TM NOA, shared following | −0.10834 | −0.10931 | +0.01705 | −0.11769 | +4.40851 |

| Same lane-drop comparison | Δ density (veh/km/lane) | Δ mean speed (m/s) | Δ low-speed exposure (vehicle-s/case) | Δ low-speed fraction (percentage points) |
|---|---:|---:|---:|---:|
| base transform − base NOA | −0.39947 | +0.76083 | −51.336 | −1.20791 |
| TM NOA − base NOA | −0.08673 | +0.08688 | −29.920 | −0.69753 |
| T transform − base transform | +0.06229 | −0.14816 | +0.344 | +0.01894 |
| TM transform − base transform | +0.07071 | −0.16499 | +0.760 | +0.02595 |
| TM transform − T transform | +0.00841 | −0.01682 | +0.416 | +0.00701 |
| TM transform − TM NOA | −0.24203 | +0.50896 | −20.656 | −0.48443 |

The original complete transform strategy already provides real local low-speed relief relative to original NOA, but upstream time and insertion waiting offset most main-segment improvement, while fuel remains higher. The mean lane-drop system time actually increases by 0.01765 s despite a 0.00695 s road-TT decrease. On straight roads, its route TT is +0.07922 s and fuel +6.01780 g/km. Thus a tidier/faster bottleneck cannot be presented as an automatic whole-system efficiency advantage.

CTH/TM lowers the old transform strategy's costs, including some full-route and main-segment time, but does **not** uniformly improve the measured bottleneck-region congestion. Relative to base transform, TM's density rises at every tested demand-flow mean and its region speed falls at every flow mean. Its 800–1100 m segment is also +0.04285 s overall. Low-speed exposure is already rare in base transform and grows slightly in T/TM. Total measured exposure across the 50 cases of each profile is base NOA 1286.1, base transform 2.7, T transform 11.3, TM NOA 538.1 and TM transform 21.7 vehicle-s; straight-road exposures are zero here. These totals are exposure, not queue duration or a new congestion index.

M's increment over T is a small extra fuel/organization-cost saving, not evidence of additional bottleneck congestion relief. Across lane-drop cases it reduces mean lane-index changes by 8.36 and physically completed changes by 7.56, saves 0.18264 g/km fuel, and leaves route TT slightly higher. At flow 1500 its TT/main time changes are +0.01115/+0.02696 s, region speed −0.10742 m/s and low-speed exposure +2.88 vehicle-s/case, while fuel improves by 0.33217 g/km. On straight roads its TT/fuel differences are −0.00560 s/−0.20270 g/km. Reduced lane changes and fuel do not prove that every neighbor braking event improved.

The correct same-longitudinal-law strategy comparison is TM transform versus TM NOA. Here the lane-drop region does improve: lower density and low-speed exposure, higher mean speed, and 640–1100 m and full-route time gains. Per-flow mean road-TT differences are −0.01260/−0.02420/−0.07884/−0.12805/−0.29802 s from 500 through 1500; fuel remains higher at every flow, by +3.03302/+4.07507/+4.63844/+5.08980/+5.20624 g/km. On straight roads the shared-following strategy comparison is TT +0.00931 s, system time +0.00834 s and fuel +3.73753 g/km. It compares complete organization/cooperation/overtaking policies; it is not a one-factor causal effect of the reported 0/1 flag.

The crossing-flow column counts first 1000 m crossings during inclusive [100,600] s, divides by 500 s and multiplies by 3600. The observed changes are small: lane-drop TM transform versus base transform −0.288 veh/h, versus T −0.576 veh/h, and versus TM NOA −1.728 veh/h. These are finite-window counts under shared requests, not capacity estimates. No capacity-increase conclusion follows.

`verification_summary_all250.json` records eligibility and ledger totals. `ledger_index_all250.csv` lists 750 compressed files with their SHA-256 and raw-source identifiers. The complete local lossless ledgers total 43,571,247 bytes: region series 16,883,201; six-gate original brackets 14,199,987; requested-vehicle gate/censor records 12,488,059. Expanded caches remain ignored. Public packaging may deduplicate gate data already in compact bundles and split by profile, while retaining exact original floats. If the public recap keeps the existing 800–1100 m result, gate 800 must be retained alongside the new 1000 m crossing evidence; the older 100/600/640/1100 brackets alone cannot reconstruct that extra segment.

The defensible conclusion is two-part: complete strategy versus its correct NOA does provide measured local bottleneck relief, with fuel and some upstream costs; the CTH/M update versus the old complete strategy mainly reduces its costs and does not establish further general bottleneck congestion relief. All claims remain limited to these demand profiles, roads, heldout seeds and fixed observation definitions.
