"""Per-vehicle first measured downstream rows, not a simultaneous fleet state."""
import csv
import gzip
from pathlib import Path
import statistics as st

OUT=Path(__file__).resolve().parent
selected=[];summaries=[]
for name in ['unformed24','formed45']:
    rows=list(csv.DictReader(gzip.open(OUT/(name+'_geometry.csv.gz'),'rt')))
    ids=sorted({r['vehicle_id'] for r in rows})
    for cutoff in [1000,1100]:
        subset=[dict(demo=name,first_observed_cutoff_x_m=cutoff,
            **next(r for r in rows if r['vehicle_id']==k and int(r['lane'])<2 and float(r['x_m'])>=cutoff)) for k in ids]
        selected.extend(subset)
        errors=[float(r['front_gap_minus_cth_D_m']) for r in subset if r['front_id']]
        speeds=[float(r['speed_mps']) for r in subset]
        summaries.append(dict(demo=name,cutoff_x_m=cutoff,requested=len(ids),with_actual_front=len(errors),
            without_actual_front=len(ids)-len(errors),speed_min=min(speeds),speed_median=st.median(speeds),speed_max=max(speeds),
            cth_error_min=min(errors),cth_error_median=st.median(errors),cth_error_max=max(errors)))
for name,rows in [('per_vehicle_downstream.csv',selected),('per_vehicle_downstream_summary.csv',summaries)]:
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print({'observations':len(selected),'summary_rows':len(summaries)})
