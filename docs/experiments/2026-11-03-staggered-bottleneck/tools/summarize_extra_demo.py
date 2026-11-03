"""Fixed +20/+25 actual-state facts for an authorized small demo folder."""
import argparse,ast,csv,gzip,json,statistics
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);a=parser.parse_args()
OUT=a.folder.resolve();base=OUT.parent
node=next(n for n in ast.parse((base/'formation_demo/analyze_and_plot.py').read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='geometry')
env={'HEADWAY':(30-5.5)/28.8};exec(compile(ast.Module(body=[node],type_ignores=[]),'original_geometry','exec'),env)
rr=[];states=[];continuous=[]
for run in json.loads((OUT/'demo_results.json').read_text()):
    case=Path(run['case_dir']);anchor=run['anchor_last_first1000_s'];initial=json.loads((OUT/(run['demo']+'_initial.json')).read_text());ids={r['id'] for r in initial}
    with gzip.open(case/'diagnostic.jsonl.gz','rt') as f:ff=list(map(json.loads,f))
    for f in ff:
        offset=round(f['time_s']-anchor,1)
        if not (anchor<=f['time_s']<run['first_actual_exit_s']) and offset not in [20.,25.]:continue
        gg=env['geometry'](f['time_s'],f['states'],f['actions']);errors=[r['front_gap_minus_cth_D_m'] for r in gg if r['front_id'] is not None]
        dx=[r[f'adj_lane{i}_signed_dx_m'] for r in gg for i in range(3) if r[f'adj_lane{i}_id'] is not None];speeds=[r['speed_mps'] for r in gg]
        row=dict(version=run['version'],demo=run['demo'],time_s=f['time_s'],anchor_offset_s=offset,onroad_n=len(gg),initial_n=len(ids),all_initial_present=set(f['states'])==ids,any_initial_exit_at_or_before_t=f['time_s']>=run['first_actual_exit_s'],
            cth_front_n=len(errors),cth_error_min=min(errors) if errors else None,cth_error_median=statistics.median(errors) if errors else None,cth_error_max=max(errors) if errors else None,
            raw_dx_min=min(dx) if dx else None,raw_dx_median=statistics.median(dx) if dx else None,raw_dx_max=max(dx) if dx else None,
            v_min=min(speeds) if speeds else None,v_median=statistics.median(speeds) if speeds else None,v_max=max(speeds) if speeds else None)
        if f['time_s']<run['first_actual_exit_s']:assert row['all_initial_present'];continuous.append(row)
        if offset in [20.,25.]:
            rr.append(row);states.extend(dict(version=run['version'],demo=run['demo'],anchor_offset_s=offset,**r) for r in gg)
def write(n,rows):
    with (OUT/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
assert len(rr)==4
write('fixed_extra_20_25_summary.csv',rr);write('fixed_extra_20_25_states.csv',states);write('all_pre_exit_frame_statistics.csv',continuous)
print(json.dumps(rr))
