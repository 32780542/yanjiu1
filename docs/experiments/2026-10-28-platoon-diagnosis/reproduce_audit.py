import collections
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'runrun.py').is_file())
sys.path.insert(0, str(ROOT / 'variants/phase5g_pure_formation'))
from experiments.platoon_metrics import _frames, _physical_graph
from experiments.phase5_detection import _physical_rows, _physical_components, _component_measurement

source = ROOT / 'variants/phase5g_pure_formation/results/continuous_traffic_v3/20261028T100105100032Z'
rows = []
for directory in sorted(source.glob('demand_*')):
    settings = json.loads((directory / 'input.json').read_text(encoding='utf-8'))['case']
    counts = collections.Counter()
    same_gaps = []
    first_match = None
    first_full = None
    for time_s, states in _frames(directory / 'positions.jsonl.gz', 1200.):
        edges, groups = _physical_graph(states, 3, 30., 15., 3.3, 2., .5, .3)
        counts['vehicle_samples'] += len(states)
        counts['at_cruise_samples'] += sum(abs(s[2]-28.8)<.01 for s in states.values())
        for group in groups:
            counts[f'matched_size_{len(group)}'] += 1
            lanes = {int(states[key][1] / 3.3) for key in group}
            counts['matched_samples'] += 1
            counts['matched_vehicle_samples'] += len(group)
            if len(lanes) == len(group):
                counts['single_layer_samples'] += 1
            if lanes == {0, 2} and len(group) == 2:
                counts['outer_pair_samples'] += 1
            if first_match is None:
                first_match = dict(time_s=time_s, states={key:states[key] for key in sorted(group)})
        for a, b in edges:
            counts['same_lane_edges' if int(states[a][1]/3.3)==int(states[b][1]/3.3) else 'cross_lane_edges'] += 1
        physical = _physical_rows({key:dict(x_m=s[0], y_m=s[1], vx_mps=s[2]) for key,s in states.items()},3.3,3)
        for component in _physical_components(physical,50.):
            measured = _component_measurement(component,middle_offset_m=15.,same_lane_gap_m=30.,
                position_tolerance_m=2.,speed_tolerance_mps=1.,lane_count=3)
            if not measured['failure_reasons']:
                counts['complete_component_samples'] += 1
                counts[f'complete_component_size_{len(component)}'] += 1
                counts['complete_component_vehicle_samples'] += len(component)
                if first_full is None:
                    first_full=dict(time_s=time_s, members=[r['key'] for r in component],counts=measured['lane_counts'])
        for lane in range(3):
            xs=sorted(s[0] for s in states.values() if abs(s[1]-(lane+.5)*3.3)<=.3)
            same_gaps.extend(b-a for a,b in zip(xs,xs[1:]))
    trips=json.loads((directory/'trips.json').read_text(encoding='utf-8'))
    result=dict(**settings, counts=dict(counts),
        same_lane_gap_min_m=min(same_gaps,default=None),
        same_lane_gap_median_m=statistics.median(same_gaps) if same_gaps else None,
        completed_lane_changes=sum(t['lane_changes'] for t in trips), first_match=first_match,
        first_full=first_full, source_sha256={name:hashlib.sha256((directory/name).read_bytes()).hexdigest()
            for name in ('input.json','positions.jsonl.gz','trips.json')})
    rows.append(result)
    print(directory.name, dict(counts), 'lane_changes',result['completed_lane_changes'],flush=True)
output=ROOT/'tmp/noa_group_structure_audit.json'
output.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(output)

from noa.simple_formation import (LocalVehicle, SimpleFormationMemory,
    choose_formation_target, formation_acceleration, choose_layered_fill, layered_window)
p=json.loads((source/'demand_L3_q2000_v28.8_d30_s1_on/input.json').read_text(encoding='utf-8'))['policy']
ego=LocalVehicle(0,100.,8.25,28.8,2)
front=LocalVehicle(1,160.48,8.25,28.8,2)
bridge=LocalVehicle(2,145.48,4.95,28.8,1)
examples=[]
for neighbors in ((front,),(front,bridge)):
    centers=(1.65,4.95,8.25)
    target=choose_formation_target(ego,neighbors,centers,SimpleFormationMemory((),'CRUISE'),p)
    window=layered_window(ego,neighbors,centers,p)
    fill=choose_layered_fill(ego,neighbors,centers,p)
    acceleration=formation_acceleration(ego,target,p)
    assert abs(target.target_x_m-130.48)<1e-6 and acceleration==0.
    examples.append(dict(neighbor_count=len(neighbors),position_error_m=target.target_x_m-ego.x_m,
        acceleration_mps2=acceleration,reference_reason=target.reason,
        layer_consistent=window.consistent,fill_reason=fill.reason))
(ROOT/'tmp/noa_group_rule_examples.json').write_text(json.dumps(examples,indent=2)+'\n',encoding='utf-8')
print('Rule examples:',examples)
