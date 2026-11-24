"""Sample ego assignment gaps from physically centered SUMO vehicle observations."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]


def sample_run(folder, row, stride, sample_every, rules, staggered):
    net = ET.parse(folder / "native.net.xml")
    approach = float(net.find("./edge[@id='upstream']/lane").get("length"))
    before, after = int(row["road"][0]), int(row["road"][-1])
    bins = {k: dict(attempts=0, centered=0, matched=0, different=0, refined=0,
                    slot=[], step=[], proposal_step=[]) for k in ("formation", "preview", "downstream")}
    with gzip.open(folder / "positions.jsonl.gz", "rt") as trace:
        for frame_index, line in enumerate(trace):
            if frame_index % stride:
                continue
            frame = json.loads(line)
            cars = sorted((rules.Vehicle(i, x, y, v, round(y / rules.LANE_WIDTH - .5),
                                         time=frame["time_s"])
                           for i, (x, y, v, _) in enumerate(frame["states"].values())),
                          key=lambda c: (c.x, c.lane))
            # Rotate the sampled rank each observation instead of always taking the head.
            for ego in cars[(frame_index // stride) % sample_every::sample_every]:
                stage = ("downstream" if ego.x >= approach else
                         "preview" if ego.x >= approach - rules.ROAD_PREVIEW else "formation")
                out = bins[stage]
                out["attempts"] += 1
                peers = [c for c in cars if c is not ego and -rules.REAR_VIEW <= c.x-ego.x <= rules.FRONT_VIEW]
                group = list(reversed(rules._local_group(ego, peers)))
                lanes = before if stage == "formation" else after
                if len(group) == 1 and stage != "formation" and lanes == 2:
                    front = min((c for c in peers if 0 < c.x-ego.x <= rules.REAR_VIEW),
                                key=lambda c: (c.x, c.lane), default=None)
                    if front is not None:
                        group = [front, ego]
                if any(abs(c.y - (c.lane + .5)*rules.LANE_WIDTH) > .3 for c in group):
                    continue
                out["centered"] += 1
                if len(group) < 2:
                    continue
                out["matched"] += 1
                target = staggered.choose_target(group.index(ego), group, lanes,
                    rules.desired_spacing(statistics.mean(c.speed for c in group)),
                    head_clipped=group[0].x - ego.x > rules.FRONT_VIEW - rules.GROUP_GAP,
                    tail_clipped=ego.x - group[-1].x > rules.REAR_VIEW - rules.GROUP_GAP,
                    sensor_bounds=(ego.x-rules.REAR_VIEW, ego.x+rules.FRONT_VIEW))
                out["slot"].append(target.gap)
                out["step"].append(target.step_gap)
                if target.lane != ego.lane:
                    out["proposal_step"].append(target.step_gap)
                    out["different"] += 1
                    out["refined"] += target.refined
    for stage, data in bins.items():
        record = {k: row.get(k) for k in ("road", "seed", "flow", "cohort", "result_sha256")}
        record.update(stage=stage, sample_period_s=stride*.1, rank_stride=sample_every)
        for key, val in data.items():
            if not isinstance(val, list):
                record[key] = val
                continue
            finite = sorted(x for x in val if math.isfinite(x))
            record[key+"_infinite"] = len(val)-len(finite)
            record[key+"_zero"] = sum(x == 0 for x in finite)
            record[key+"_finite_median_m2"] = statistics.median(finite) if finite else None
        yield record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("batch", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--ticks", type=int, default=50)
    ap.add_argument("--rank-stride", type=int, default=4)
    ap.add_argument("--cohorts", default="stream,chain24")
    args = ap.parse_args()
    if args.ticks < 1 or args.rank_stride < 1:
        ap.error("Sampling strides must be positive")
    source = (args.batch / "source").resolve()
    sys.path.insert(0, str(source))
    from noa import native_rules, staggered, transport
    manifest = json.loads((args.batch / "manifest.json").read_bytes())["files"]
    for module in (native_rules, staggered, transport):
        path = Path(module.__file__).resolve()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[path.relative_to(source).as_posix()]
    with (args.batch / "summary.csv").open(encoding="utf8") as rows, args.output.open("x", newline="", encoding="utf8") as dest:
        writer = None
        for row in csv.DictReader(rows):
            if row.get("cohort") and row["cohort"] not in args.cohorts.split(","):
                continue
            for record in sample_run(ROOT / row["run_dir"], row, args.ticks, args.rank_stride, native_rules, staggered):
                if writer is None:
                    writer = csv.DictWriter(dest, record)
                    writer.writeheader()
                writer.writerow(record)


if __name__ == "__main__":
    main()
