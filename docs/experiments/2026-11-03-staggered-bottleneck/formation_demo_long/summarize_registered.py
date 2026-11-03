"""Keep event-level min/max CTH evidence at every preregistered whole-fleet frame."""
import csv
import gzip
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
with (OUT/'snapshot_states.csv').open(encoding='utf-8-sig',newline='') as f:states=list(csv.DictReader(f))
events=[]
for run in json.loads((OUT/'demo_results.json').read_text()):
    with gzip.open(Path(run['case_dir'])/'diagnostic.jsonl.gz','rt') as f:frames={r['time_s']:r for r in map(json.loads,f)}
    for t in run['registered_downstream_times_s']:
        rr=[r for r in states if r['version']==run['version'] and r['demo']==run['demo'] and float(r['time_s'])==t and r['front_id']]
        for name,fn in [('min',min),('max',max)]:
            r=fn(rr,key=lambda r:float(r['front_gap_minus_cth_D_m']));a=frames[t]['actions'][r['vehicle_id']]
            events.append(dict(extreme=name,**r,command_speed_mps=a['speed'],actual_following_reference_private_track=a['reference']))
with (OUT/'registered_cth_extreme_events.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(events[0]));w.writeheader();w.writerows(events)
print(json.dumps([r for r in events if r['anchor_offset_s']=='15.0' and r['extreme']=='max']))
