"""Measure the same two-layer staggered geometry at fixed or speed-dependent spacing."""
import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def memberships(states, lanes):
    """Closed consecutive two-layer windows. Each car counts at most once per rule."""
    ordered = sorted(states, key=lambda k: -states[k][0])
    fixed, scaled = set(), set()
    width = 2 * lanes
    for first in range(len(ordered) - width + 1):
        stop = first + width
        block = ordered[first:stop]
        if ((first and states[ordered[first-1]][0] == states[block[0]][0]) or
                (stop < len(ordered) and states[ordered[stop]][0] == states[block[-1]][0])):
            continue
        columns = [[] for _ in range(lanes)]
        speeds = []
        for k in block:
            x, y, v, _ = states[k]
            lane = round(y / 3.3 - .5)
            if not 0 <= lane < lanes or abs(y - 3.3*(lane+.5)) > .3:
                break
            columns[lane].append(x)
            speeds.append(v)
        if any(len(c) != 2 for c in columns) or max(speeds)-min(speeds) > .5:
            continue
        for ids, gap in ((fixed, 30.), (scaled, 5.5 + .85*sum(speeds)/width)):
            for phase in (range(2) if lanes == 2 else (0,)):
                roots = [x + (row + ((lane+phase)%2)/2)*gap
                         for lane,col in enumerate(columns) for row,x in enumerate(col)]
                if max(roots) - min(roots) <= 2.0 + 1e-9:
                    ids.update(block)
                    break
    return fixed, scaled


def segment_run(folder, seconds=600, period=1.):
    inputs = json.loads((folder / "input.json").read_bytes())
    net = ET.parse(folder / "native.net.xml")
    upstream = net.findall("./edge[@id='upstream']/lane")
    downstream = net.findall("./edge[@id='downstream']/lane")
    boundary = float(upstream[0].get("length"))
    regions = (("upstream",len(upstream)), ("downstream",len(downstream)))
    duration = inputs["case"]["demand_duration_s"]
    dt = inputs["positions_step_s"]
    ticks = round(period / dt)
    if ticks < 1 or abs(ticks*dt-period) > 1e-9:
        raise ValueError("Observation interval must be a multiple of the recorded step")
    stats = {}
    with gzip.open(folder / "positions.jsonl.gz","rt",encoding="utf8") as frames:
        for record in frames:
            frame = json.loads(record)
            t = frame["time_s"]
            if t > duration or round(t/dt) % ticks:
                continue
            epoch = int((t-1e-8)//seconds)
            for region, lanes in regions:
                s = {k:v for k,v in frame["states"].items()
                     if (v[0] < boundary-200 if region == "upstream" else v[0] >= boundary)}
                fixed, scaled = memberships(s, lanes)
                c = stats.setdefault((epoch,region),Counter())
                c["vehicle_samples"] += len(s)
                c["fixed_members"] += len(fixed)
                c["scaled_members"] += len(scaled)
                c["scaled_only"] += len(scaled-fixed)
                c["fixed_only"] += len(fixed-scaled)
                c["sum_speed"] += sum(v[2] for v in s.values())
    for (epoch,region), c in sorted(stats.items()):
        n = c["vehicle_samples"]
        yield dict(start_s=epoch*seconds,end_s=min(duration,(epoch+1)*seconds),region=region,
                   samples=n,avg_speed_mps=c["sum_speed"]/n if n else None,
                   fixed_pct=100*c["fixed_members"]/n if n else None,
                   scaled_pct=100*c["scaled_members"]/n if n else None,
                   scaled_only=c["scaled_only"], fixed_only=c["fixed_only"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path)
    parser.add_argument("batches",nargs="+",type=Path)
    parser.add_argument("--bin",type=int,default=600)
    parser.add_argument("--period",type=float,default=1.)
    args=parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    writer = None
    with args.output.open("x",encoding="utf8",newline="") as dest:
        for batch in args.batches:
            with (batch/"summary.csv").open(encoding="utf8") as src:
                for case in csv.DictReader(src):
                    for row in segment_run(root/case["run_dir"],args.bin,args.period):
                        record=dict(batch=batch.name,road=case["road"],seed=case["seed"],flow=case["flow"],
                                    result_sha256=case["result_sha256"],**row)
                        if writer is None:
                            writer=csv.DictWriter(dest,record)
                            writer.writeheader()
                        writer.writerow(record)


if __name__ == "__main__":
    main()
