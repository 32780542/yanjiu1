"""Synchronous physics, each NOA sees only its own sensor and own memory."""
from dataclasses import asdict, replace
import math
from types import MappingProxyType
from models.vehicle import Actuation
from models.bezier import QuadraticLaneChange, bezier_command
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from noa.contracts import NoaMemory
from noa.controller import decide


class ReplayBoundary(RuntimeError):
    """Stop reconstruction before an operation absent from retained evidence."""


def script_action(state, script, model_parameters):
    """Exogenous bench vehicle, depending only on own state and frozen schedule."""
    target = script['speed_steps'][0][1]
    for time, speed in script['speed_steps']:
        if state.time_s >= time-1e-9:
            target = speed
    acceleration = model_parameters['speed_tracking_gain_per_s']*(target-state.vx_mps)
    acceleration = max(-model_parameters['comfort_braking_mps2'], min(model_parameters['comfort_accel_mps2'], acceleration))
    if 'acceleration_steps' in script:
        for time, command in script['acceleration_steps']:
            if state.time_s >= time-1e-9:
                acceleration = command
    steering = 0.
    if 'lane_change' in script:
        reference=QuadraticLaneChange(**script['lane_change'])
        # Frozen exogenous event times have the same equality semantics at
        # either sampling period. Only the controller's evaluation time is
        # canonicalized; the physical state and preset schedule are unchanged.
        evaluation_time=state.time_s
        for event in (reference.start_s,reference.start_s+reference.duration_s/2,reference.start_s+reference.duration_s):
            if math.isclose(evaluation_time,event,abs_tol=1e-9,rel_tol=0.):
                evaluation_time=event
        steering = bezier_command(replace(state,time_s=evaluation_time),reference,model_parameters).steering_rad
    return Actuation(acceleration,steering)


class NoaClock:
    def __init__(self, initial, model, road, parameters, policy_parameters, controlled, scripts):
        self.model, self.p = model, MappingProxyType(dict(parameters))
        self.policy = MappingProxyType(dict(policy_parameters))
        self.dt, self.integration_dt = self.p['control_sync_dt_s'], self.p['dynamics_dt_s']
        if not math.isclose(self.dt,self.p['perception_dt_s'],abs_tol=1e-12,rel_tol=0):
            raise ValueError('Control and ideal observation must use the same clock')
        self._check_features()
        self.controlled = tuple(sorted(controlled))
        if len(set(controlled))!=len(controlled) or set(controlled)&set(scripts) or set(controlled)|set(scripts)!=set(initial):
            raise ValueError('Each vehicle needs exactly one independent actor')
        self.scripts = dict(scripts)
        for script in scripts.values():
            for name in ('speed_steps','acceleration_steps'):
                rows=script.get(name,[])
                if name=='speed_steps' and not rows:
                    raise ValueError('Script must declare its own target speed')
                if any(len(row)!=2 or not all(math.isfinite(v) for v in row) for row in rows):
                    raise ValueError('Nonfinite script schedule')
                if any(a[0]>=b[0] for a,b in zip(rows,rows[1:])):
                    raise ValueError('Script schedule times must increase')
        self.states = MappingProxyType(dict(initial))
        self._frame()
        self.sensors = {key:IdealSensor(self.p,road) for key in self.controlled}
        self.memories = {key:self._initial_memory() for key in self.controlled}
        self.failed, self.last_record = False, None

    def _check_features(self):
        if self.p['formation_enabled'] or self.p['communication_enabled']:
            raise ValueError('Phase4 requires formation and communication off')

    def _initial_memory(self):
        return NoaMemory((), 'CRUISE')

    def _decide(self, control):
        return decide(control, self.policy)

    def _frame(self):
        return WorldFrame(tuple(TruthVehicle(key,state,self.model.p['length_m'],self.model.p['width_m'],
                                            self.model.observe(state)['a_long_mps2']) for key,state in self.states.items()))

    def tick(self, bridge=None, order=None, stop_before=None):
        if self.failed:
            raise RuntimeError('NOA clock terminated after failure')
        keys=tuple(sorted(self.states)) if order is None else tuple(order)
        self.last_record={'status':'running','initial':{k:asdict(v) for k,v in sorted(self.states.items())}}
        record=self.last_record
        stage,actor='order',None
        def enter(name,key=None):
            nonlocal stage,actor
            stage,actor=name,key
            if stop_before==(stage,actor):
                raise ReplayBoundary('Reached retained execution boundary')
        try:
            enter('order')
            if len(keys)!=len(self.states) or set(keys)!=set(self.states):
                raise ValueError('Every vehicle must advance exactly once')
            enter('frame')
            frame=self._frame()
            inputs={}
            record['inputs']={}
            for key in keys:
                if key in self.sensors:
                    enter('observation',key)
                    sample=self.sensors[key].sample(key,frame)
                    memory=replace(self.memories[key],observation_history=sample.memory.observation_history)
                    inputs[key]=replace(sample,memory=memory)
                    record['inputs'][key]=asdict(inputs[key])
            record['inputs']={k:asdict(inputs[k]) for k in sorted(inputs)}
            decisions={}
            record['decisions']={}
            for key in keys:
                if key in inputs:
                    enter('decision',key)
                    decisions[key]=self._decide(inputs[key])
                    record['decisions'][key]=asdict(decisions[key])
            record['decisions']={k:asdict(decisions[k]) for k in sorted(decisions)}
            actions={}
            record['actions']={}
            for key in keys:
                enter('action',key)
                actions[key]=decisions[key].action if key in decisions else script_action(self.states[key],self.scripts[key],self.model.p)
                record['actions'][key]=asdict(actions[key])
            record['actions']={k:asdict(actions[k]) for k in sorted(actions)}
            steps={}
            record['steps'],record['diagnostics']={},{}
            for key in keys:
                enter('integration',key)
                steps[key]=self.model.advance(self.states[key],actions[key],self.dt,self.integration_dt)
                record['steps'][key]=asdict(steps[key])
                enter('diagnostics',key)
                record['diagnostics'][key]=[self.model.observe(s) for s in steps[key].samples]
            record['steps']={k:asdict(steps[k]) for k in sorted(steps)}
            record['diagnostics']={k:record['diagnostics'][k] for k in sorted(steps)}
            enter('synchronization')
            record['readback']=bridge.synchronize(steps) if bridge else None
            enter('commit')
            self.states=MappingProxyType({k:steps[k].final for k in sorted(steps)})
            self.memories={k:decisions[k].memory for k in sorted(decisions)}
            record['status']='completed'
            return record
        except BaseException as exc:
            self.failed=True
            record.update(status='failed',error=f'{type(exc).__name__}: {exc}',failure_stage=stage,failure_actor=actor)
            if bridge and stage=='synchronization':
                record.update(readback=bridge.last_reports,readback_phase=bridge.readback_phase)
            raise
