"""Independent arithmetic integral/gate reconstruction and actual raw-frame checks."""
import argparse,csv,gzip,hashlib,json,math
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def output(p,rr):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    assert not a.output.exists();a.output.mkdir(parents=True)
    index=json.loads((a.report/'ledger_index.json').read_text());cases=rows(a.report/'per_case.csv');checked=[];spots=[]
    for item in index:
        case=next(r for r in cases if r['candidate']==item['candidate'] and float(r['flow'])==item['flow'] and int(r['seed'])==item['seed'] and r['mode']==item['mode'])
        ledger=Path(item['ledger_dir']);evidence=Path(item['evidence_dir']);seal=json.loads((evidence/'seal.json').read_text())
        for name,digest in item['ledger_sha256'].items():assert sha(ledger/name)==digest
        observed=vehicle=low=speed=0.;peak=0;previous=None;steps={}
        with gzip.open(ledger/'region_steps.jsonl.gz','rt') as f:
            fields=json.loads(next(f))
            for line in f:
                s=dict(zip(fields,json.loads(line)));steps[round(s['time_s'],4)]=s
                left=max(100.,s['time_s']);right=min(1800.,s['end_s'])
                if right<=left:continue
                if previous is not None:assert math.isclose(left,previous,abs_tol=1e-7)
                else:assert left==100.
                dt=right-left;observed+=dt;vehicle+=dt*s['n'];low+=dt*s['low_speed_n'];speed+=dt*s['speed_sum_mps'];peak=max(peak,s['low_speed_n']);previous=right
        assert previous==1800. and math.isclose(observed,1700.,abs_tol=1e-7)
        expected=dict(region_mean_n=vehicle/1700,region_density_veh_km_lane=vehicle/1700/.6,region_mean_speed_mps=speed/vehicle,region_low_speed_vehicle_s=low,region_low_speed_fraction=low/vehicle,region_max_simultaneous_low_speed=peak)
        gates={}
        with gzip.open(ledger/'gate_brackets.jsonl.gz','rt') as f:
            assert json.loads(next(f))==['vehicle_index','gate_m','t0','x0','t1','x1']
            for line in f:
                i,g,t0,x0,t1,x1=json.loads(line);assert (i,g) not in gates
                gates[i,g]=t0 if t1==t0 else t0+(g-x0)*(t1-t0)/(x1-x0)
        n=sum(g==1000 and 100<=t<=1800 for (_,g),t in gates.items());expected['flow_1000m_crossings']=n;expected['flow_1000m_veh_h']=n*3600/1700
        for k,v in expected.items():assert math.isclose(float(case[k]),v,rel_tol=1e-10,abs_tol=1e-7),(k,case[k],v)
        raw=Path(case['run_dir'])/'positions.jsonl.gz';assert sha(raw)==seal['originals']['positions.jsonl.gz']['sha256'];found=[]
        with gzip.open(raw,'rt') as f:
            for line in f:
                frame=json.loads(line);t=frame['time_s']
                if round(t,4) in (100.,600.,1000.,1799.9):
                    selected=[s for s in frame['states'].values() if 800<=s[0]<1000];s=steps[round(t,4)]
                    actual=[len(selected),sum(v[2]<5 for v in selected),sum(v[2] for v in selected)]
                    assert actual[0]==s['n'] and actual[1]==s['low_speed_n'] and math.isclose(actual[2],s['speed_sum_mps'],abs_tol=1e-8)
                    spots.append(dict(candidate=item['candidate'],flow=item['flow'],seed=item['seed'],time_s=t,raw_n=actual[0],raw_low_n=actual[1],raw_speed_sum_mps=actual[2],ledger_n=s['n'],ledger_low_n=s['low_speed_n'],ledger_speed_sum_mps=s['speed_sum_mps']));found.append(t)
                if t>=1799.9:break
        assert len(found)==4
        checked.append(dict(candidate=item['candidate'],flow=item['flow'],seed=item['seed'],observed_duration_s=observed,vehicle_s=vehicle,**expected,raw_sha256=seal['originals']['positions.jsonl.gz']['sha256'],raw_bytes=raw.stat().st_size,raw_spotchecks=4,originals_retained=True))
    output(a.output/'independent_integrals.csv',checked);output(a.output/'raw_spotchecks.csv',spots)
    summary=dict(report=str(a.report.resolve()),report_source_sha256={n:sha(a.report/n) for n in ['per_case.csv','paired_seeds.csv','flow_means.csv','summary.json','ledger_index.json']},independent_cases=len(checked),raw_frame_checks=len(spots),independent_no_existing_evaluator_import=True,all_ledger_integrals_and_gate_counts_match=True,all_raw_region_counts_low_counts_speed_sums_match=True,no_pruning=True)
    (a.output/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
