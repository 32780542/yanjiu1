"""Read fixed 45-car traces with the same geometry criteria as C12."""
import gzip
import json
from pathlib import Path
from statistics import mean
import sys

for trial in map(Path, sys.argv[1:]):
    diagnostic, = (trial / "run").glob("*/diagnostic.jsonl.gz")
    result = json.loads(diagnostic.with_name("result.json").read_bytes())
    trips = json.loads(diagnostic.with_name("trips.json").read_bytes())
    first = last = None
    errors = {}
    with gzip.open(diagnostic, "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            time = frame["time_s"]
            cars = sorted(frame["states"].values(), key=lambda c: c["x"])
            if len(cars) != 45:
                continue
            pairs = list(zip(cars, cars[1:]))
            centered = all(c["lane"] < 2 and abs(c["vy"]) < .05
                           and abs(c["y"] - (c["lane"] + .5) * 3.3) < .05 for c in cars)
            alternate = centered and all(a["lane"] != b["lane"] for a, b in pairs)
            if alternate:
                error = mean(abs(b["x"] - a["x"] - (5.5 + .85 * (a["speed"] + b["speed"]) / 2) / 2)
                             for a, b in pairs)
                if first is None:
                    first = time
                last = time
                if time in (70., 80., 100.):
                    errors[str(time)] = error
    print(json.dumps(dict(trial=trial.name, safe=result["safe"], status=result["status"],
        completed=result["completed"], first_alternating_s=first, last_alternating_s=last,
        error_m=errors, lane_changes=sum(len(t["lane_completion_events"]) for t in trips))))
