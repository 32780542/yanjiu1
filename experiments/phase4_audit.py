"""Offline evidence analysis, never fed back to any NOA decision."""
from dataclasses import asdict, replace
import json
import math
from models.vehicle import VehicleState
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from perception.road import ego_point, in_box
from noa.contracts import memory_from_dict
from noa.controller import decide
from experiments.phase3_replay import compare_tree


def isolation_rows(records, model, parameters, policy, road, controlled):
    kinds=('identity_order','hidden_type','future_plan','outside_state')
    sensors={(key,kind):IdealSensor(parameters,road) for key in controlled for kind in kinds}
    stride=parameters['phase4_isolation_stride']
    if type(stride) is not int or stride<1:
        raise ValueError('Isolation audit stride must be a positive integer')
    for index,record in enumerate(records):
        cars=tuple(TruthVehicle(k,VehicleState(**s),model.p['length_m'],model.p['width_m'],
                               model.observe(VehicleState(**s))['a_long_mps2']) for k,s in record['initial'].items())
        for key in controlled:
            own=next(v for v in cars if v.key==key)
            for kind in kinds:
                ego_key=key
                if kind=='identity_order':
                    rename=lambda k:'counterfactual_'+str(len(k))+'_'+k[::-1]
                    ego_key=rename(key)
                    changed=tuple(replace(v,key=rename(v.key)) for v in reversed(cars))
                elif kind=='hidden_type':
                    changed=tuple(replace(v,hidden_type='NOA' if i%2 else 'HDV') for i,v in enumerate(cars))
                elif kind=='future_plan':
                    changed=tuple(replace(v,future_plan=('unavailable',index,i,'brake_then_merge')) for i,v in enumerate(cars))
                else:
                    changed=tuple(v for v in cars if in_box(ego_point(v.state.x_m,v.state.y_m,own.state),parameters))
                    far=replace(own.state,x_m=own.state.x_m+10000+index)
                    changed += (TruthVehicle('unobservable_counterfactual',far,10,2.5,hidden_type='HDV'),)
                observed=sensors[key,kind].sample(ego_key,WorldFrame(changed))
                if index%stride and index!=len(records)-1:
                    continue
                own_memory=memory_from_dict(record['inputs'][key]['memory'])
                control=replace(observed,memory=replace(own_memory,observation_history=observed.memory.observation_history))
                decision=decide(control,policy)
                identical=True
                try:
                    compare_tree(record['inputs'][key],asdict(control),model.p['replay_absolute_tolerance'])
                    compare_tree(record['decisions'][key],asdict(decision),model.p['replay_absolute_tolerance'])
                except ValueError:
                    identical=False
                sensitive=False
                if kind=='hidden_type':
                    empty=replace(control,observation=replace(control.observation,neighbors=()))
                    sensitive=decide(empty,policy).action!=decision.action
                yield {'interval':index,'ego':key,'mutation':kind,'mutated_frame':[asdict(v) for v in changed],
                       'input':asdict(control),'decision':asdict(decision),'identical':identical,
                       'visible_removal_changes_action':sensitive}


def isolation_audit(records,model,p,policy,road,controlled,path):
    comparisons,sensitive,errors=0,0,[]
    with path.open('w',encoding='utf-8') as handle:
        for row in isolation_rows(records,model,p,policy,road,controlled):
            handle.write(json.dumps(row,allow_nan=False)+'\n')
            comparisons+=1
            sensitive+=row['visible_removal_changes_action']
            if not row['identical']:
                errors.append({k:row[k] for k in ('interval','ego','mutation')})
    return {'passed':comparisons>0 and not errors,'comparisons':comparisons,'mismatches':errors,
            'visible_neighbor_removal_changes_action':sensitive,'sample_stride_intervals':p['phase4_isolation_stride'],
            'scope':'All sensor histories rebuilt; sampled decisions use the same own memory under hidden-field and outside-state changes'}


def percentile(values,fraction):
    return sorted(values)[min(len(values)-1,math.ceil(fraction*len(values))-1)] if values else 0.


def driving_metrics(records, model, p, case):
    actors={}
    for key in case['controlled']:
        states=[VehicleState(**records[0]['initial'][key])]
        states += [VehicleState(**s) for r in records for s in r['steps'][key]['samples']]
        diagnostics=[model.observe(s) for s in states]
        actual_jerk=[(b['a_long_mps2']-a['a_long_mps2'])/(t.time_s-s.time_s)
                     for a,b,s,t in zip(diagnostics,diagnostics[1:],states,states[1:])]
        drive_jerk=[(t.a_drive_mps2-s.a_drive_mps2)/(t.time_s-s.time_s) for s,t in zip(states,states[1:])]
        steering_rate=[(t.steering_rad-s.steering_rad)/(t.time_s-s.time_s) for s,t in zip(states,states[1:])]
        modes=[r['decisions'][key]['memory']['own_behavior'] for r in records]
        # Count physically completed lane-center changes, independent of controller self-report.
        stable_lane=None
        lane_changes=[]
        for state in states:
            lane=round((state.y_m-model.p['lane_width_m']/2)/model.p['lane_width_m'])
            center=model.p['lane_width_m']*(lane+.5)
            if abs(state.y_m-center)<=.15 and abs(state.heading_rad)<=.05:
                if stable_lane is not None and lane!=stable_lane:
                    lane_changes.append({'time_s':state.time_s,'from_lane':stable_lane,'to_lane':lane})
                stable_lane=lane
        tracking=[]
        for r in records:
            own=r['decisions'][key]['memory']
            plan=own.get('plan')
            if isinstance(plan,dict) and all(name in plan for name in ('start_s','y_start_m','y_target_m','duration_s','speed_mps')):
                from models.bezier import QuadraticLaneChange
                reference=QuadraticLaneChange(**plan)
                for raw in r['steps'][key]['samples']:
                    tracking.append(abs(raw['y_m']-reference.at(raw['time_s'])['y_m']))
        final=states[-1]
        max_jerk=max(map(abs,actual_jerk),default=0.)
        comfort=(max(d['a_long_mps2'] for d in diagnostics)<=model.p['comfort_accel_mps2']+p['phase4_numeric_slack']
                 and min(d['a_long_mps2'] for d in diagnostics)>=-model.p['comfort_braking_mps2']-p['phase4_numeric_slack']
                 and max_jerk<=model.p['comfort_jerk_mps3']+p['phase4_numeric_slack']
                 and max(abs(d['a_lateral_mps2']) for d in diagnostics)<=model.p['comfort_lateral_accel_mps2']+p['phase4_numeric_slack'])
        checks={}
        req=case['requirements']
        if 'min_final_speed_mps' in req: checks['min_final_speed']=final.vx_mps>=req['min_final_speed_mps']
        if 'max_final_speed_mps' in req: checks['max_final_speed']=final.vx_mps<=req['max_final_speed_mps']
        if 'min_final_x_m' in req: checks['min_final_x']=final.x_m>=req['min_final_x_m']
        if 'max_final_x_m' in req: checks['max_final_x']=final.x_m<=req['max_final_x_m']
        if 'max_final_y_m' in req: checks['max_final_y']=final.y_m<=req['max_final_y_m']
        if 'final_y_m' in req: checks['final_y']=abs(final.y_m-req['final_y_m'])<=.15
        if 'minimum_speed_below_mps' in req: checks['stopped']=min(s.vx_mps for s in states)<=req['minimum_speed_below_mps']
        if 'modes_any' in req: checks['required_behavior']=bool(set(modes)&set(req['modes_any']))
        if 'min_lane_changes' in req: checks['completed_lane_changes']=len(lane_changes)>=req['min_lane_changes']
        if 'no_lane_change_before_s' in req:
            threshold=req['no_lane_change_before_s']
            initial_y=states[0].y_m
            checks['fast_rear_gap_rejected']=all(abs(s.y_m-initial_y)<.3 for s in states if s.time_s<threshold)
        if req.get('neighbor_count_decreases'):
            counts=[len(r['inputs'][key]['observation']['neighbors']) for r in records]
            checks['range_exit_observed']=counts[-1]<counts[0]
        tracking_needed=any(r['decisions'][key]['memory'].get('plan') is not None for r in records)
        actors[key]={'requirement_checks':checks,'requirements_passed':all(checks.values()),'modes':sorted(set(modes)),
                     'mode_counts':{m:modes.count(m) for m in sorted(set(modes))},'lane_changes':lane_changes,
                     'final':asdict(final),'min_speed_mps':min(s.vx_mps for s in states),
                     'max_speed_mps':max(s.vx_mps for s in states),'min_actual_acceleration_mps2':min(d['a_long_mps2'] for d in diagnostics),
                     'max_actual_acceleration_mps2':max(d['a_long_mps2'] for d in diagnostics),
                     'max_actual_lateral_acceleration_mps2':max(abs(d['a_lateral_mps2']) for d in diagnostics),
                     'max_actual_jerk_mps3':max_jerk,'max_actuator_jerk_mps3':max(map(abs,drive_jerk),default=0.),
                     'max_steering_rate_radps':max(map(abs,steering_rate),default=0.),'comfort_passed':comfort,
                     'tracking_samples':len(tracking),'tracking_max_m':max(tracking,default=0.),
                     'tracking_p95_m':percentile(tracking,.95),'tracking_passed':(not tracking_needed or bool(tracking)) and max(tracking,default=0.)<=p['phase4_tracking_max_m'] and percentile(tracking,.95)<=p['phase4_tracking_p95_m']}
    return {'actors':actors,'requirements_passed':all(a['requirements_passed'] for a in actors.values()),
            'comfort_passed':all(a['comfort_passed'] for a in actors.values()),'tracking_passed':all(a['tracking_passed'] for a in actors.values())}
