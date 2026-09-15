"""Replayable own-reference Bezier trajectory bench for the simplified model."""
from dataclasses import asdict
import math
from experiments.records import atomic_json
from experiments.phase2 import save_trace,run_sumo,audit_geometry
from experiments.phase3_replay import replay_motion_trace
from experiments.offline import compare_trajectories
from models.vehicle import VehicleState
from models.bezier import QuadraticLaneChange,bezier_command
from research.common import ROOT
from safety.geometry import RoadEnvelope


def run_bench(path,model,live=True):
    path.mkdir(parents=True)
    p = model.p
    initial = VehicleState(x_m=100,y_m=1.65,vx_mps=20)
    ref = QuadraticLaneChange(0,1.65,1.65+p['lane_width_m'],p['maneuver_duration_s'],20)
    duration = 2*p['maneuver_duration_s']
    variants,trajectories,dirs = {},{},[]
    for name,control_dt,dt in (('base',.1,.01),('sampling_half',.05,.01),('integration_half',.1,.005)):
        steps,current = [],initial
        for i in range(round(duration/control_dt)):
            action = trajectories['base'][i].command if name=='integration_half' else bezier_command(current,ref,p)
            step = model.advance(current,action,control_dt,dt)
            steps.append(step)
            current = step.final
        trajectories[name] = steps
        sub = path/name
        sub.mkdir()
        meta = {'parameters':dict(p),'initial':asdict(initial),'reference':asdict(ref),'intervals':len(steps),
                'dynamics_dt_s':dt,'control_dt_s':control_dt,
                'command_mode':'saved_base_commands' if name=='integration_half' else 'own_bezier_reference'}
        atomic_json(sub/'metadata.json',meta)
        save_trace(sub/'trace.jsonl',model,steps)
        replay = replay_motion_trace(meta,sub/'trace.jsonl')
        geometry = audit_geometry(model,steps,RoadEnvelope.from_net(ROOT/'scenarios/cai2024/bottleneck.net.xml'))
        states = [initial]+[s for step in steps for s in step.samples]
        peak = max(abs(s.y_m-ref.at(s.time_s)['y_m']) for s in states)
        terminal = abs(states[-1].y_m-ref.y_target_m)
        lateral = max(abs(model.observe(s)['a_lateral_mps2']) for s in states)
        passed = (peak<=p['max_lane_change_error_m'] and terminal<=p['terminal_lane_error_m']
                  and lateral<=p['steering_lateral_envelope_mps2']+1e-8 and replay['passed'] and geometry['passed'])
        result = {'passed':passed,'max_lateral_tracking_error_m':peak,'terminal_tracking_error_m':terminal,
                  'max_actual_lateral_acceleration_mps2':lateral,
                  'max_actual_steering_rate_radps':max(abs(b.steering_rad-a.steering_rad)/dt for a,b in zip(states,states[1:])),
                  'max_sampled_longitudinal_jerk_mps3':max(abs(model.observe(b)['a_long_mps2']-model.observe(a)['a_long_mps2'])/dt
                                                       for a,b in zip(states,states[1:])),
                  'geometry':geometry,'replay':replay,'scope':'Own prescribed Bezier lane change with simple geometric tracking; not autonomous NOA'}
        if live and name != 'integration_half':
            result['sumo'] = run_sumo(sub/'sumo',model,steps,control_dt)
            result['passed'] = result['passed'] and result['sumo']['passed']
        atomic_json(sub/'validation.json',result)
        variants[name] = result
        dirs.append(sub)
    comparisons = {}
    for name,prefix in (('sampling_half','control'),('integration_half','integration')):
        c = compare_trajectories(trajectories['base'],trajectories[name])
        c['passed'] = c['max_position_error_m']<=p[prefix+'_position_tolerance_m'] and c['max_heading_error_rad']<=p[prefix+'_heading_tolerance_rad']
        comparisons[name] = c
    result = {'passed':all(v['passed'] for v in variants.values()) and all(v['passed'] for v in comparisons.values()),
              'variants':variants,'comparisons':comparisons,
              'reference_continuity':'Two quadratic Bezier pieces: C1, curvature jumps at join; rate-limited integrated steering is continuous'}
    atomic_json(path/'validation.json',result)
    return result,dirs
