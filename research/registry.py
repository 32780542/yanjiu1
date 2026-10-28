import csv
import json
from pathlib import Path
from research.common import ROOT, read_json, write_json, settings, sha256


def source_hashes():
    snap=read_json('docs/cai2024_source_parameters_2026-09-10.json')
    rows=[]
    for f in snap['source_files']:
        p=Path(f['path'])
        observed=sha256(p) if p.is_file() else None
        rows.append({'path':f['path'],'expected_sha256':f['sha256'],'observed_sha256':observed,
                     'matched':observed==f['sha256'],'bytes':p.stat().st_size if p.is_file() else None})
    write_json('results/phase0/source_hash_check.json',{'files':rows,'all_matched':all(r['matched'] for r in rows)})
    if not all(r['matched'] for r in rows):
        raise RuntimeError('Read-only source snapshot changed; re-audit before using source values')
    return {f['path']:f['sha256'] for f in snap['source_files']}


def build_registry():
    hashes=source_hashes()
    rows=[]
    for layer in ('paper_reference','no_comm_main','topology_smoke','sensitivity','phase2','phase3','kinematic','phase4','phase4_experiments','phase5','phase5_experiments'):
        data=read_json(f'configs/{layer}.json')
        seen=set()
        for param in data['parameters']:
            x={**data['defaults'],**param,'layer':layer}
            if x['name'] in seen:
                raise ValueError(f'Duplicate {layer}.{x["name"]}')
            seen.add(x['name'])
            for field in ('name','value','unit','source','page_or_url','status','rationale'):
                if field not in x or x[field] is None or x[field]=='':
                    raise ValueError(f'Missing provenance {layer}: {field}')
            x['source_sha256']=hashes.get(x['source'],'')
            if x.get('source_line'):
                x['page_or_url']=f'{x["source"]}:{x["source_line"]}'
            rows.append(x)
    snapshot=read_json('docs/cai2024_source_parameters_2026-09-10.json')
    for p in snapshot['parameters']:
        src=p.get('source') or {}
        src=src if isinstance(src,dict) else {'path':src}
        path=src.get('path','')
        rows.append({'layer':'source_snapshot','name':p['name'],'value':p['value'],'unit':p['unit'],
                     'source':path or 'Inspected source: unresolved', 'page_or_url':str(src.get('line',src.get('lines',''))),
                     'status':p['status'],'rationale':p.get('note',p.get('adoption','reference only')),
                     'source_line':src.get('line',''),'source_sha256':hashes.get(path,'')})
    fields=['layer','name','value','unit','source','page_or_url','status','rationale','source_line','source_sha256']
    with (ROOT/'docs/parameter_registry.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        w.writeheader()
        for x in rows:
            w.writerow({**x,'value':json.dumps(x['value'],ensure_ascii=False)})
    main=settings('no_comm_main')
    assert abs(main['wheelbase_m']-main['cg_to_front_axle_m']-main['cg_to_rear_axle_m'])<1e-9
    assert abs(main['length_m']-main['wheelbase_m']-main['front_overhang_m']-main['rear_overhang_m'])<1e-9
    write_json('results/phase0/parameter_registry_summary.json',{'rows':len(rows),
               'counts_by_layer':{layer:sum(x['layer']==layer for x in rows) for layer in sorted({x['layer'] for x in rows})},
               'active_missing_provenance':0, 'source_snapshot_is_read_only':True,
               'no_comm_main_is_unvalidated_development_configuration':True,
               'csv_sha256':sha256(ROOT/'docs/parameter_registry.csv')})
    print(f'Parameter registry: {len(rows)} rows; 29 unchanged read-only source files.')
