"""Add paired E comparisons and descriptive raw cross-lane tables; no classifier."""
import csv
import gzip
import json
from pathlib import Path
import runpy
import statistics as st

BASE=Path(__file__).resolve().parent.parent
H=BASE/'formation_demo_H'
HEADWAY=(30-5.5)/28.8

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write(p,rr):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)

for tag in ['J2','JT2']:
    out=BASE/('formation_demo_'+tag)
    source=(H/'compare_E_H.py').read_text(encoding='utf-8')
    source=source.replace('E/H','E/'+tag).replace('E_H','E_'+tag).replace("'H'","'"+tag+"'")
    source=source.replace('E versus H','E versus '+tag)
    source=source.replace('H_n=',tag+'_n=')
    script=out/('compare_E_'+tag+'.py');assert not script.exists()
    script.write_text(source,encoding='utf-8',newline='\n')
    runpy.run_path(str(script),run_name='__main__')
    frames={}
    for result in json.loads((out/'demo_results.json').read_text()):
        with gzip.open(Path(result['case_dir'])/'diagnostic.jsonl.gz','rt') as f:
            frames[result['demo']]={r['time_s']:r for r in map(json.loads,f)}
    cross=[]
    for source_table in ['snapshot_states.csv','tail_window_states.csv','per_vehicle_downstream.csv']:
        for row in read(out/source_table):
            ss=frames[row['demo']][float(row['time_s'])]['states']
            for lane in range(3):
                peer=row[f'adj_lane{lane}_id']
                if not peer:continue
                speed=float(row['speed_mps']);peer_speed=ss[peer]['speed'];dx=float(row[f'adj_lane{lane}_signed_dx_m'])
                cross.append(dict(source_table=source_table,demo=row['demo'],time_s=row['time_s'],
                    cutoff_x_m=row.get('first_observed_cutoff_x_m',''),vehicle_id=row['vehicle_id'],
                    x_m=row['x_m'],lane=row['lane'],speed_mps=speed,peer_id=peer,peer_lane=lane,
                    peer_speed_mps=peer_speed,raw_signed_dx_m=dx,reference_15_m=15.,
                    reference_D_pair_mean_speed_half_m=(5.5+HEADWAY*(speed+peer_speed)/2)/2))
    write(out/'cross_lane_pair_references.csv',cross)
    compact=[]
    for result in json.loads((out/'demo_results.json').read_text()):
        name=result['demo'];tail=result['last_vehicle_1100_s']
        rr=[r for r in read(out/'snapshot_states.csv') if r['demo']==name and float(r['time_s'])==tail]
        vv=[float(r['speed_mps']) for r in rr];ee=[float(r['front_gap_minus_cth_D_m']) for r in rr if r['front_id']]
        dx=[float(r[f'adj_lane{1-int(r["lane"])}_signed_dx_m']) for r in rr if int(r['lane'])<2 and r[f'adj_lane{1-int(r["lane"])}_id']]
        compact.append(dict(version=tag,demo=name,TT_s=result['mean_travel_time_s'],end_s=result['actual_end_s'],
            last1100_s=tail,remaining_n=len(rr),front_n=len(ee),v_min=min(vv),v_max=max(vv),
            error_min=min(ee),error_median=st.median(ee),error_max=max(ee),raw_cross_signed_dx_m=json.dumps(dx),
            lane_change_completions=result['lane_change_completions'],
            closing_observed=result['ending_lane_observed_vehicles'],closing_completed=result['ending_lane_completed_before_drop']))
    write(out/'tail_compact_summary.csv',compact)
    print(json.dumps(compact))
