"""Persist deliberate failures separately from normal scientific cases."""
import copy
import json
from experiments.records import atomic_json
from experiments.phase3_replay import replay_case


def run_faults(path,model,p,source_path):
    from experiments.phase3 import run_case
    from experiments.phase3_cases import cases
    path.mkdir(parents=True)
    meta = json.loads((source_path/'metadata.json').read_text())
    records = [json.loads(line) for line in (source_path/'trace.jsonl').read_text().splitlines()[:3]]
    meta['intervals'] = len(records)
    meta['case'] = {**meta['case'],'duration_s':len(records)*p['control_sync_dt_s'],
                    'purpose':'First three intervals copied from normal live source for explicit fault injection'}
    key = sorted(meta['initial'])[0]
    results = []
    for kind in ('observation','history','action','substep','truth_chain','diagnostic','readback_time','truncation'):
        data = copy.deepcopy(records)
        if kind == 'observation':
            data[0]['inputs'][key]['observation']['neighbors'][0]['relative_x_m'] += .001
        elif kind == 'history':
            data[1]['inputs'][key]['memory']['observation_history'] = []
        elif kind == 'action':
            data[0]['actions'][key]['acceleration_mps2'] += .001
        elif kind == 'substep':
            data[0]['steps'][key]['samples'][3]['y_m'] += .0001
        elif kind == 'truth_chain':
            data[1]['initial'][key]['x_m'] += .001
        elif kind == 'diagnostic':
            data[0]['diagnostics'][key][0]['a_long_mps2'] += .001
        elif kind == 'readback_time':
            data[0]['readback'][key]['sumo_time_s'] += .1
        else:
            data.pop()
        sub = path/kind
        sub.mkdir()
        atomic_json(sub/'metadata.json',meta)
        (sub/'trace.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in data),encoding='utf-8')
        report = replay_case(meta,sub/'trace.jsonl')
        atomic_json(sub/'validation.json',{'fault':kind,'detected':not report['passed'],'replay':report})
        results.append({'fault':kind,'detected':not report['passed'],'replay':report})
    collision = copy.deepcopy(cases(p)[0])
    collision['duration_s'] = .2
    keys = list(collision['initial'])
    collision['initial'][keys[1]] = dict(collision['initial'][keys[0]])
    collision['purpose'] = 'Deliberately overlapping initial bodies; detection must not change or rescue actions'
    physical = run_case(path/'overlap_failure',model,p,collision,live=False)
    detected = not physical['passed'] and physical['status']=='completed' and physical['geometry']['collision_substeps']>0
    result = {'passed':all(r['detected'] for r in results) and detected,'trace_faults':results,
              'overlap_failure_detected':detected,'overlap_case':physical,
              'meaning':'Deliberate negative tests; detection success is not a successful driving result'}
    atomic_json(path/'validation.json',result)
    return result


def replay_faults(path):
    reports = []
    for name in ('observation','history','action','substep','truth_chain','diagnostic','readback_time','truncation'):
        sub = path/name
        meta = json.loads((sub/'metadata.json').read_text())
        result = replay_case(meta,sub/'trace.jsonl')
        reports.append({'fault':name,'detected':not result['passed'],'replay':result})
    sub = path/'overlap_failure'
    meta = json.loads((sub/'metadata.json').read_text())
    overlap_replay = replay_case(meta,sub/'trace.jsonl')
    from models.kinematic import model_from_parameters
    from safety.geometry import RoadEnvelope
    from experiments.phase3_audit import geometry_report
    # Derive only this straight road envelope from the frozen boundary lines.
    # The negative overlap outcome is pairwise geometry, independent of map.
    model = model_from_parameters(meta['model_parameters'])
    records = [json.loads(line) for line in (sub/'trace.jsonl').read_text().splitlines()]
    boundaries = meta['road']['boundaries']
    xs = sorted({pt[0] for line in boundaries for pt in line})
    regions = []
    for a,b in zip(xs,xs[1:]):
        ys = [line[0][1] for line in boundaries if line[0][1]==line[1][1] and line[0][0] <= (a+b)/2 <= line[1][0]]
        if ys:
            regions.append((a,b,min(ys),max(ys)))
    geometry = geometry_report(records,model,RoadEnvelope(regions))
    return {'passed':all(r['detected'] for r in reports) and overlap_replay['passed'] and geometry['collision_substeps']>0,
            'trace_faults':reports,'overlap_numerical_replay':overlap_replay,'overlap_geometry':geometry}
