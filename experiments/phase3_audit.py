"""Offline-only evaluation. None of these global results return to a controller."""
from dataclasses import asdict, replace
from itertools import combinations
import json
import math
from models.vehicle import VehicleState
from models.geometry import body_from_state
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from perception.probe import probe_action
from safety.geometry import swept_collision, swept_outside


def geometry_report(records,model,road):
    outside, collisions, regime = [], [], []
    samples = 0
    for record in records:
        previous = {k:body_from_state(VehicleState(**v),model.p) for k,v in record['initial'].items()}
        for i in range(len(next(iter(record['steps'].values()))['samples'])):
            current = {k:body_from_state(VehicleState(**v['samples'][i]),model.p) for k,v in record['steps'].items()}
            time = next(iter(record['steps'].values()))['samples'][i]['time_s']
            for key,body in current.items():
                samples += 1
                if swept_outside(road,previous[key],body,model.p['sweep_max_depth']):
                    outside.append((time,key))
                diagnostic = record['diagnostics'][key][i]
                if diagnostic.get('outside_linear_tire_regime',False) or diagnostic.get('outside_kinematic_lateral_envelope',False):
                    regime.append((time,key))
            for a,b in combinations(sorted(current),2):
                if swept_collision(previous[a],current[a],previous[b],current[b],model.p['sweep_max_depth']):
                    collisions.append((time,a,b))
            previous = current
    return {'passed':not outside and not collisions and not regime,'vehicle_substeps':samples,
            'outside_substeps':len(outside),'collision_substeps':len(collisions),'outside_model_envelope_substeps':len(regime),
            'outside_events':outside,'collision_events':collisions,'model_envelope_events':regime,
            'scope':'Conservative sweep of linearly interpolated substep poses; no corrective feedback or continuous-time guarantee'}


def isolation_audit(records, model, parameters, road, path):
    """Replay complete local histories under independent hidden-field mutations."""
    kinds = ('identity_order','hidden_type','future_plan','outside_state')
    sensors = {(key,kind):IdealSensor(parameters,road) for key in records[0]['initial'] for kind in kinds}
    comparisons, errors, sensitive = 0, [], 0
    with path.open('w',encoding='utf-8') as handle:
        for index,record in enumerate(records):
            cars = tuple(TruthVehicle(key,VehicleState(**s),model.p['length_m'],model.p['width_m'],
                         model.observe(VehicleState(**s))['a_long_mps2']) for key,s in record['initial'].items())
            for key in sorted(record['initial']):
                own = next(v for v in cars if v.key == key)
                for kind in kinds:
                    ego_key = key
                    if kind == 'identity_order':
                        ego_key = 'renamed_'+str(len(key))+key[::-1]
                        altered = tuple(replace(v,key='renamed_'+str(len(v.key))+v.key[::-1]) for v in reversed(cars))
                    elif kind == 'hidden_type':
                        altered = tuple(replace(v,hidden_type='HDV' if i%2 else 'NOA') for i,v in enumerate(cars))
                    elif kind == 'future_plan':
                        altered = tuple(replace(v,future_plan=('unavailable_intent',index,i,'brake_then_merge')) for i,v in enumerate(cars))
                    else:
                        # Also perturb/remove existing outside targets, not just
                        # append an unused field. The filter uses ego geometry.
                        from perception.road import ego_point, in_box
                        altered_list = []
                        for v in cars:
                            x,y = ego_point(v.state.x_m,v.state.y_m,own.state)
                            inside = in_box((x,y),parameters)
                            if inside:
                                altered_list.append(v)
                        far = replace(own.state,x_m=own.state.x_m+10000+index,vy_mps=.7)
                        altered = tuple(altered_list)+(TruthVehicle('external_unobservable',far,12,2.5,hidden_type='HDV'),)
                    inp = sensors[key,kind].sample(ego_key,WorldFrame(altered))
                    if kind == 'hidden_type':
                        baseline_input = inp
                    action = probe_action(inp,parameters)
                    equal = (asdict(inp) == record['inputs'][key] and asdict(action) == record['actions'][key])
                    comparisons += 1
                    if not equal:
                        errors.append({'interval':index,'ego':key,'mutation':kind})
                    handle.write(json.dumps({'interval':index,'ego':key,'mutation':kind,
                        'mutated_frame': [asdict(v) for v in altered],
                        'input':asdict(inp),'action':asdict(action),'identical':equal},allow_nan=False)+'\n')
                # Positive control: remove currently observed neighbors while
                # preserving same ego/history. At least one action must react.
                if probe_action(baseline_input,parameters) != probe_action(
                        replace(baseline_input,observation=replace(baseline_input.observation,neighbors=())),parameters):
                    sensitive += 1
    return {'passed':not errors,'comparisons':comparisons,'mismatches':errors,
            'visible_neighbor_removal_changes_action':sensitive,
            'scope':'Equal current allowed measurements and full local histories; mutations do not change physical future trajectories'}


def compare_records(base, other):
    def states(records):
        output = {}
        for r in records:
            for key,step in r['steps'].items():
                for s in (step['initial'],)+tuple(step['samples']):
                    output[key,round(s['time_s'],9)] = s
        return output
    a,b = states(base),states(other)
    shared = set(a)&set(b)
    pos = max(math.hypot(a[k]['x_m']-b[k]['x_m'],a[k]['y_m']-b[k]['y_m']) for k in shared)
    heading = max(abs(a[k]['heading_rad']-b[k]['heading_rad']) for k in shared)
    return {'max_position_error_m':pos,'max_heading_error_rad':heading,'common_vehicle_time_points':len(shared)}
