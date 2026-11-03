"""Read 24 already-run cases and compare E/F with the two F factors."""
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
ROOT = REPO / "tmp/staggered_bottleneck"
SHA = {
    "E_NC": "fe6c9d6e0629358eee86dce7a46ad0068375939d5faaca0d21acebc2d64b218f",
    "F": "f3a7acba6a812196d357cdccefb707ffec88df1e744d6f4dfc77ce26d916464d",
    "F_B": "6f2ed98a4292b6e250ef7ccb1caacc3e34096a0ebadb03c713678f82c049e704",
    "F_R": "af93edeb6376bac708823e252b32a56bef1c8fb40dd11fb71395397d367906ad",
}
BATCH = {"E_NC": ("20261103_ablation180_24", "NC"), "F": ("20261103_F_screen180_10", "F"),
         "F_B": ("20261103_F_factorial180_12", "F_B"), "F_R": ("20261103_F_factorial180_12", "F_R")}
read = lambda p: json.loads(p.read_text(encoding="utf-8"))
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rows, provenance, by_key = [], [], {}
for flow in (2000, 2250, 2500):
    for seed in (1, 4):
        paired_input = None
        for candidate, (batch, label) in BATCH.items():
            record_path = ROOT / batch / "cases" / f"{label}_{flow}_{seed}_lane_drop_transform/case_record.json"
            record = read(record_path)
            assert record["status"] == "drained" and record["safe"] and record["all_completed"]
            assert record["returncode"] == 0 and record["seal_status"] == "verified"
            run = Path(record["run_dir"])
            result, inputs = read(run / "result.json"), read(run / "input.json")
            assert result["source_sha256"]["noa/native_rules.py"] == SHA[candidate]
            assert inputs["source_sha256"] == result["source_sha256"]
            for name, expected in result["source_sha256"].items():
                assert digest(run / "source" / name) == expected
            contract = {k: inputs[k] for k in ("arrivals", "physical", "speed_mode", "lane_change_mode", "insertion")}
            contract["other_sources"] = {k: v for k, v in result["source_sha256"].items() if k != "noa/native_rules.py"}
            if paired_input is None:
                paired_input = contract
            assert contract == paired_input
            assert (result["demand_duration_s"], result["max_time_s"], result["scenario"], result["mode"]) == (180, 500, "lane_drop", "transform")
            events = result["lane_completion_events"]
            count = lambda a, b, lo, hi: sum(e["from_lane"] == a and e["to_lane"] == b and lo <= e["x"] < hi for e in events)
            trips = ET.parse(run / "sumo_tripinfo.xml").getroot().findall("tripinfo")
            assert len(trips) == result["completed"] == result["requested"]
            row = dict(candidate=candidate, flow=flow, seed=seed, N=result["requested"],
                       TT=result["mean_travel_time_s"], fuel=result["fuel_g_per_km"],
                       end_s=result["actual_end_s"], LC=result["lane_change_completions"],
                       prep_1_to_0=count(1, 0, 640, 1000), prep_0_to_1=count(0, 1, 640, 1000),
                       downstream_0_to_1=count(0, 1, 1000, float("inf")),
                       arrival_0=sum(t.attrib["arrivalLane"] == "downstream_0" for t in trips),
                       arrival_1=sum(t.attrib["arrivalLane"] == "downstream_1" for t in trips),
                       local_relief_ticks=result["action_reasons"].get("local_relief", 0))
            rows.append(row)
            by_key[candidate, flow, seed] = row
            provenance.append(dict(candidate=candidate, flow=flow, seed=seed, case_record=str(record_path),
                                   case_record_sha256=digest(record_path), result_sha256=digest(run / "result.json"),
                                   input_sha256=digest(run / "input.json"), trips_sha256=digest(run / "sumo_tripinfo.xml")))

effects = []
for flow in (2000, 2250, 2500):
    for seed in (1, 4):
        e, f, b, r = (by_key[c, flow, seed]["TT"] for c in ("E_NC", "F", "F_B", "F_R"))
        effects.append(dict(flow=flow, seed=seed, E=e, F=f, B=b, R=r, B_minus_E=b-e,
                            R_minus_E=r-e, F_minus_R=f-r, F_minus_B=f-b, interaction=f-b-r+e))
for name, data in (("per_case.csv", rows), ("factorial_effects.csv", effects)):
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)
(OUT / "verification.json").write_text(json.dumps(dict(cases=24, matched_requests=True,
    common_physical_and_other_sources=True, source_files_verified=144,
    original_e_nc_equivalence="see review_direct_relief.md; no new simulation", provenance=provenance), indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(cases=24, effects=effects)))
