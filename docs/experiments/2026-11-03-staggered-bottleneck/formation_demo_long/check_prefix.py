"""Compare physical trajectories before the first original-road vehicle exit."""
import csv
import gzip
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
rr=[]
for run in json.loads((OUT/'demo_results.json').read_text()):
    original_folder=OUT.parent/('formation_demo' if run['version']=='E2400' else 'formation_demo_J2')
    original=next(r for r in json.loads((original_folder/'demo_results.json').read_text()) if r['demo']==run['demo'])
    def frames(case):
        with gzip.open(Path(case)/'diagnostic.jsonl.gz','rt') as f:return {r['time_s']:r for r in map(json.loads,f)}
    before=frames(original['case_dir']);after=frames(run['case_dir']);n=run['initial_n']
    first_exit=next(t for t,f in before.items() if len(f['states'])<n)
    times=[t for t in before if t<first_exit]
    maxima=dict(x=0.,y=0.,speed=0.);exact=0
    for t in times:
        a,b=before[t]['states'],after[t]['states'];assert set(a)==set(b)
        exact+=a==b
        for key in maxima:maxima[key]=max(maxima[key],max(abs(a[k][key]-b[k][key]) for k in a))
    trips=json.loads((Path(original['case_dir'])/'trips.json').read_text())
    rr.append(dict(version=run['version'],demo=run['demo'],original_first_exited_s=min(r['exited_s'] for r in trips),
        original_first_missing_initial_frame_s=first_exit,
        compared_frames=len(times),physically_exact_frames=exact,
        max_abs_x_delta_m=maxima['x'],max_abs_y_delta_m=maxima['y'],max_abs_speed_delta_mps=maxima['speed']))
with (OUT/'original_road_prefix_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
print(json.dumps(rr))
