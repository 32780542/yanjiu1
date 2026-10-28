import csv
import json
import math
import sys
import xml.etree.ElementTree as ET
from research.common import ROOT, settings, read_json, write_json, sha256, code_manifest
from research.demand import generate, assign_types, probability
from research.network import SCENARIO, validate_tree
from research.registry import source_hashes


def verify():
    source_hashes()
    network=validate_tree(ET.parse(SCENARIO/'bottleneck.net.xml').getroot())
    errors=list(network['errors'])
    smoke,paper,main=[settings(x) for x in ('topology_smoke','paper_reference','no_comm_main')]
    demand_reports=[]
    for q in paper['flow_levels_per_lane_hour']:
        base=SCENARIO/'demand'/f'q{q}_seed{smoke["seed"]}'
        expected=generate(q,smoke['seed'],smoke['demand_duration_s'],smoke['demand_dt_s'])
        with base.with_suffix('.csv').open(newline='',encoding='utf-8') as f:
            raw=list(csv.DictReader(f))
        loaded=[dict(vehicle_id=r['vehicle_id'], planned_depart_s=float(r['planned_depart_s']),
                     depart_lane=int(r['depart_lane']), type_uniform=float(r['type_uniform'])) for r in raw]
        if loaded != expected:
            errors.append(f'Demand byte-decoded replay differs q={q}')
        types=list(csv.DictReader(base.with_suffix('.types.csv').open(encoding='utf-8',newline='')))
        if [r['hidden_type'] for r in types] != [r['hidden_type'] for r in assign_types(expected,smoke['hidden_noa_fraction'])]:
            errors.append(f'Hidden type tape differs q={q}')
        routes=ET.parse(base.with_suffix('.rou.xml')).getroot()
        vehicles=routes.findall('vehicle')
        route_records=[(x.get('id'),float(x.get('depart')),int(x.get('departLane'))) for x in vehicles]
        if route_records!=[(x['vehicle_id'],x['planned_depart_s'],x['depart_lane']) for x in expected]:
            errors.append(f'Route plan mismatch q={q}')
        if routes.find('route').get('edges')!='upstream downstream':
            errors.append(f'Wrong route q={q}')
        vtype=routes.find('vType')
        for key,value in [('length',4),('width',main['width_m']),('mass',1500),('maxSpeed',33.3),('emergencyDecel',10)]:
            if float(vtype.get(key))!=value:
                errors.append(f'Explicit vehicle setting wrong: {key}')
        if {x.get('type') for x in vehicles}!={'native_probe'}:
            errors.append('Topology smoke must not masquerade as NOA controller')
        n_trials=round(smoke['demand_duration_s']/smoke['demand_dt_s'])
        p=probability(q,smoke['demand_dt_s'])
        per_lane=[sum(r['depart_lane']==i for r in expected) for i in range(3)]
        demand_reports.append({'q_per_lane_hour':q,'q_total_hour':q*3,'probability':p,
                               'expected_count_per_lane':n_trials*p,'counts_per_lane':per_lane,
                               'planned_count':len(expected),'realized_rates_per_lane_hour':[x*3600/smoke['demand_duration_s'] for x in per_lane],
                               'count_z_scores':[(x-n_trials*p)/math.sqrt(n_trials*p*(1-p)) for x in per_lane],
                               'replay_exact':loaded==expected,'csv_sha256':sha256(base.with_suffix('.csv'))})
    # Do not allow legacy source path / parent project to enter the import search path.
    parent=ROOT.parent.resolve()
    bad_paths=[]
    for p in sys.path:
        resolved=__import__('pathlib').Path(p).resolve()
        if resolved==parent or (resolved.is_relative_to(parent) and not resolved.is_relative_to(ROOT)):
            bad_paths.append(str(resolved))
    if bad_paths:
        errors.append(f'Unexpected parent module search paths: {bad_paths}')
    result={'passed':not errors,'errors':errors,'network':network,'demands':demand_reports,
            'import_paths':sys.path,'code_and_config_hashes':code_manifest(),
            'limitations':['No controller implemented','No complete sensor simulation','No external dynamics yet','No traffic or energy effect estimate']}
    write_json('results/phase1/foundation_verification.json',result)
    print(json.dumps({'passed':not errors,'errors':errors,'planned_counts':[x['planned_count'] for x in demand_reports]}))
    if errors:
        raise RuntimeError('Foundation verification failed')
