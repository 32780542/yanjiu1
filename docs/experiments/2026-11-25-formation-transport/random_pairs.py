"""Create a per-initial-condition comparison from random_cohorts.py's run CSV."""
import argparse
from bisect import bisect_left, bisect_right
import csv
import gzip
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def visibility(run, n):
    """Geometrical raw-observation windows, conditioned on the full cohort being present."""
    config = json.loads((run/"input.json").read_bytes())
    upstream = ET.parse(run/"native.net.xml").find("./edge[@id='upstream']/lane")
    boundary = float(upstream.get("length"))
    preview = config["case"]["road_observation_m"]
    totals = {side: [0,0] for side in ("upstream","downstream")}
    report = json.loads((run.parent/"measure.json").read_bytes())
    at_first_shape = {side+"_full_views_at_first_shape":None for side in totals}
    initial = {}
    with gzip.open(run/"positions.jsonl.gz", "rt") as stream:
        for index, frame in enumerate(map(json.loads, stream)):
            xs = sorted(s[0] for s in frame["states"].values())
            if len(xs)!=n:
                continue
            full_views = max(0, bisect_right(xs,xs[0]+100.)-bisect_left(xs,xs[-1]-200.))
            if index == 0:
                sizes = [bisect_right(xs,x+200.)-bisect_left(xs,x-100.) for x in xs]
                initial = dict(full_views=full_views,min_count=min(sizes),max_count=max(sizes))
            side = "upstream" if xs[-1]<boundary-preview else "downstream" if xs[0]>=boundary else None
            if side:
                totals[side][0] += full_views
                totals[side][1] += len(xs)
                if frame["time_s"] == report[side]["first_whole_s"]:
                    at_first_shape[side+"_full_views_at_first_shape"] = full_views
    result = {side+"_full_view_pct": round(100*h/t,3) if t else None for side,(h,t) in totals.items()}
    result.update(at_first_shape)
    return initial, result


def compare(source, output, include_visibility=False, tail_events=False):
    with source.open(encoding="utf-8", newline="") as stream:
        runs = list(csv.DictReader(stream))
    groups = {}
    for row in runs:
        key = tuple(row[k] for k in ("road","n","spacing","seed"))
        if row["model"] in groups.setdefault(key, {}):
            raise ValueError(f"Duplicate {row['model']} for {key}")
        groups[key][row["model"]] = row
    rows = []
    for key, pair in groups.items():
        a, b = pair["base"], pair["candidate"]
        row = dict(zip(("road","n","spacing","seed"), key))
        row.update(request_sha256=a["request_sha256"], first_frame_sha256=a["first_frame_sha256"],
                   paired_full_first_frame=a["paired_full_first_frame"],
                   both_match_request=a["initial_matches_request"]==b["initial_matches_request"]=="True")
        for field in ("status","collisions","teleports","whole_both","same_ids_peak",
                      "upstream_whole_hold_s","downstream_whole_hold_s","lane_changes"):
            row["base_"+field], row["candidate_"+field] = a[field], b[field]
        if include_visibility:
            views = []
            for name, run in pair.items():
                first, stats = visibility(source.parent/run["run"],int(run["n"]))
                views.append(first)
                row[name+"_completed"] = run["completed"]
                row.update({name+"_"+k: v for k,v in stats.items()})
            if views[0]!=views[1]:
                raise ValueError(f"Initial sight windows differ for {key}")
            row.update({"initial_"+k: v for k,v in views[0].items()})
        if tail_events:
            for name, run in pair.items():
                report = json.loads((source.parent/run["run"]).parent.joinpath("measure.json").read_bytes())
                tail = report["after_last_downstream_shape_events"]
                row[name+"_whole_run_completions"] = run["lane_change_completions"]
                row[name+"_last_off_center_count"] = len(report["last_off_center_ids"])
                for kind in ("midpoint","completed"):
                    row[name+"_after_last_shape_"+kind] = tail[kind]["total"] if tail else None
        row["candidate_minus_base_lane_changes"] = int(b["lane_changes"])-int(a["lane_changes"])
        for stage in ("formation","transform","observed_population"):
            for stat in ("bound_total","actual_total","excess_total","bound_max","actual_max","excess_max"):
                field = stage+"_"+stat
                row["base_"+field], row["candidate_"+field] = a[field], b[field]
            for stat in ("excess_total","excess_max"):
                field = stage+"_"+stat
                row["candidate_minus_base_"+field] = int(b[field])-int(a[field]) if a[field] and b[field] else None
        rows.append(row)
    with output.open("w",newline="",encoding="utf-8") as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--visibility", action="store_true", help="Read raw trajectories in the run CSV's directory")
    parser.add_argument("--tail-events", action="store_true", help="Also report physical crossings after the last full shape")
    args = parser.parse_args()
    compare(args.source,args.output,args.visibility,args.tail_events)
