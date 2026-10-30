# Final traffic evidence

Five profile archives preserve every byte of the 750 lossless measured/derived traffic ledgers from the 250 heldout cases. Each also contains its 50 small case cache records. Raw positions are not copied. `PUBLIC_MANIFEST.json` hashes every published file; profile manifests give every tar member's SHA-256/bytes and a case index. `case_index.json` resolves the original case identifiers and cache paths in the unchanged report/CSV files to public bundle members.

Run from a repository checkout, without SUMO or original run directories:

```powershell
python -B docs/experiments/2026-10-30-rule-trials/traffic_evidence/verify_public.py --output verification.json
```

The verifier checks all file/member hashes, recreates only three ledger files for one case at a time in a temporary directory, and calls the already implemented pure `verify_ledgers` function from the frozen wrapper. It reconstructs the original region-window exposure/density/speed/low-speed statistics, gate brackets, per-vehicle segments, crossing count/rate and route/system/entry-wait times. It then checks every paired difference and paired mean against the saved report. It never follows `case_dir`/`ledger_dir` back to the original runs and never invokes `evaluate_case`, `load_case`, a controller or SUMO. The existing evaluator modules in the checkout must match the saved method-source hashes; their snapshots are included in `method_sources/`.

Fuel and lane-count columns remain tied to the original input/result/trips/source identifiers in each `case.json` and the report. Their original JSON evidence already exists in the companion case bundles; this traffic package does not duplicate it or invent fuel reconstruction from positions.

`report.json` and the CSVs are exact copies of the final all250 report. `FINAL_INTERPRETATION.md`, `METHOD.md`, `verification_summary_all250.json` and the complete ledger index accompany them. The fixed definitions remain 800≤x<1000 m, three lanes, [100,600) s, v<5 m/s, and inclusive first-1000 m crossings over [100,600] s / 500 s × 3600. The observed crossing flow is not a capacity estimate. All six gates are retained, including 800 m for the existing 800–1100 m segment.

`package_evidence.py` records how the already verified caches were packaged. It preserves inner gzip bytes and uses deterministic outer archive headers; it does not recalculate traffic metrics or alter old reports/caches.
