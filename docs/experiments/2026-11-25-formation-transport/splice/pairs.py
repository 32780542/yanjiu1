"""Build one compact record per matched physical input, including trace equality."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

IDENTITY = ("road", "n", "profile", "seed", "upstream_m")
SHARED = (*IDENTITY, "first_frame_s", "first_frame_sha", "max_gap_initial_m", "initial_gaps_50_100",
          "initial_gaps_100_200", "initial_gaps_over200")
MEASURES = ("completed", "collisions", "teleports", "max_speed_m_s", "first_connected_s",
            "min_max_gap_up_m", "last_max_gap_up_m", "first_whole_travel_m", "upstream_whole_hold_s",
            "downstream_whole_hold_s", "upstream_peak_size", "downstream_peak_size", "same_ids_peak",
            "net_lane_crossings", "formation_total", "formation_min_total_crossings",
            "formation_max_per_car", "formation_min_max_crossings", "transform_total",
            "transform_min_total_crossings", "transform_max_per_car", "transform_min_max_crossings")


def trace_hash(path, row):
    folder = path/"_".join(str(row[k]) for k in ("mode","road","n","profile","seed","upstream_m"))
    trace, = folder.glob("*/positions.jsonl.gz")
    with gzip.open(trace, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch",action="append",required=True,metavar="NAME=DIR")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--reference",default="base")
    p.add_argument("--require-arm")
    args=p.parse_args()
    combined={}
    versions={}
    for item in args.batch:
        label,dirname=item.split("=",1)
        path=Path(dirname)
        manifest=json.loads((path/"manifest.json").read_bytes())
        for name,identity in manifest.items():
            assert versions.setdefault(name,identity)==identity, f"{name} changed across batches"
        with (path/"summary.csv").open(newline="") as stream:
            for row in csv.DictReader(stream):
                key=(label,*(row[k] for k in IDENTITY))
                by_mode=combined.setdefault(key,{})
                assert row["mode"] not in by_mode and row["status"]=="drained"
                row["trajectory_sha"]=trace_hash(path,row)
                by_mode[row["mode"]]=row
    outputs=[]
    for (label,*_),arms in sorted(combined.items()):
        if args.require_arm and args.require_arm not in arms:
            continue
        base=arms[args.reference]
        result=dict(batch=label,**{k:base[k] for k in SHARED})
        for mode in ("base","unit","group","retained_front"):
            if mode not in arms:
                continue
            r=arms[mode]
            assert all(r[k]==base[k] for k in (*SHARED,"tape_sha"))
            if r["profile"]=="demo12":
                assert r["entry_states_sha"]==base["entry_states_sha"]
                result["entry_states_sha"]=r["entry_states_sha"]
            result.update({mode+"_"+k:r[k] for k in MEASURES})
            if mode!=args.reference:
                result[mode+"_same_full_trace"]=r["trajectory_sha"]==base["trajectory_sha"]
        outputs.append(result)
    with args.out.open("w",newline="") as stream:
        fields=list(dict.fromkeys(k for r in outputs for k in r))
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(outputs)
    print(len(outputs), "matched inputs;", sum(len(v) for v in combined.values()
          if not args.require_arm or args.require_arm in v),"completed runs.")


if __name__=="__main__":
    main()
