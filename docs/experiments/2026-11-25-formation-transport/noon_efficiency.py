"""Recompute on-road journey, fuel and upstream traffic state for the paired 1200 s runs."""
import csv
import gzip
import json
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from math import isclose
from pathlib import Path
from statistics import mean
from xml.etree import ElementTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
METHODS = ("ref", "hold", "noa")
ROADS = ("3to2", "4to3")
FLOWS = (1500,1750,2000)
SEEDS = (11261,11262)


def read(path):
    return json.loads(path.read_bytes())


def measure(cell):
    method, road, flow, seed = cell
    row = read(ROOT/"tmp/nov25study"/f"noon_{method}_1200"/f"{road}_s{seed}_q{flow}"/"row.json")
    folder = ROOT/row["run_dir"]
    result, config, trips = (read(folder/name) for name in ("result.json","input.json","trips.json"))
    assert result["status"] == "drained" and result["completed"] == result["requested"] == len(trips)
    assert result["collisions"] == result["teleports"] == 0
    travel = mean(v["exited_s"]-v["entered_s"] for v in trips)
    fuel = sum(v["fuel_mg"] for v in trips)/sum(v["distance_m"] for v in trips)
    assert isclose(travel, result["mean_travel_time_s"], abs_tol=1e-7)
    assert isclose(fuel, result["fuel_g_per_km"], rel_tol=1e-7)
    cut = float(ElementTree.parse(folder/"native.nod.xml").find(".//node[@id='bottleneck']").get("x"))
    watch = config["case"]["road_observation_m"]
    frames = observations = 0
    speeds = 0.
    with gzip.open(folder/"positions.jsonl.gz","rt",encoding="utf8") as trace:
        for frame in map(json.loads, trace):
            if frame["time_s"] > result["demand_duration_s"]:
                break
            frames += 1
            for x, _, v, *_ in frame["states"].values():
                if cut-watch <= x < cut:
                    observations += 1
                    speeds += v
    return dict(method=method,road=road,flow=flow,seed=seed,completed=len(trips),
                travel_s=travel,fuel_g_km=fuel,approach_count=observations/frames,
                approach_speed_mps=speeds/observations,frames=frames,vehicle_samples=observations,
                approach_start_m=cut-watch,approach_end_m=cut,run_dir=row["run_dir"])


def write(name, rows):
    with (HERE/name).open("w", encoding="utf8", newline="") as f:
        writer=csv.DictWriter(f,list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact", action="store_true", help="Include the exact minimum-reuse assignment")
    args = parser.parse_args()
    methods = (*METHODS, "minimum") if args.exact else METHODS
    with ProcessPoolExecutor(3) as pool:
        rows=list(pool.map(measure, product(methods,ROADS,FLOWS,SEEDS)))
    write("noon_road_runs.csv",rows)
    summary=[]
    for road,flow,method in product(ROADS,FLOWS,methods):
        subset=[r for r in rows if (r["road"],r["flow"],r["method"])==(road,flow,method)]
        assert len(subset)==len(SEEDS)
        summary.append(dict(road=road, flow=flow, method=method, seeds=len(subset),
                            cars=sum(r["completed"] for r in subset),
                            **{key:mean(r[key] for r in subset) for key in
                               ("travel_s","fuel_g_km","approach_count","approach_speed_mps")}))
    write("noon_road_summary.csv",summary)


if __name__ == "__main__":
    main()
