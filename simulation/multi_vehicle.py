"""Synchronous physical platform, not a traffic coordinator.

Freeze -> sense all -> independent pure actions -> integrate all -> queue all
endpoints -> exactly one SUMO step -> audit all. Audits never change commands.
Any partial failure terminates the instance; no retry, correction or fallback.
"""
from dataclasses import asdict
import math
from types import MappingProxyType
from models.geometry import to_sumo_pose
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from perception.probe import probe_action
from simulation.external_bridge import ExternalBridge, validate_integrated_step


class FleetBridge:
    def __init__(self, connection, initial, model, sync_dt_s):
        WorldFrame(tuple(TruthVehicle(k,s,model.p['length_m'],model.p['width_m']) for k,s in initial.items()))
        self.connection, self.model, self.dt = connection, model, sync_dt_s
        self._bridges = {}
        self.initial_reports = {k:{'passed':False,'status':'not_read','errors':['Bootstrap readback not reached']}
                                for k in sorted(initial)}
        for key,state in sorted(initial.items()):
            try:
                b = ExternalBridge(connection,key,model,state,sync_dt_s)
                self._bridges[key], self.initial_reports[key] = b, b.last_report
            except BaseException as exc:
                self.initial_reports[key] = getattr(exc,'report',{'passed':False,'status':'readback_exception',
                                                    'errors':[f'{type(exc).__name__}: {exc}']})
                exc.fleet_initial_reports = self.initial_reports
                raise
        self.time_offset = next(iter(self._bridges.values())).time_offset
        self.last_reports, self.failed, self.advances = {}, False, 0
        self.readback_phase = 'bootstrap'

    def _capture(self,key,bridge,state=None,acceleration=None):
        try:
            self.last_reports[key] = bridge.readback(state,acceleration)
        except BaseException as exc:
            self.last_reports[key] = {'passed':False,'status':'readback_exception',
                                      'errors':[f'{type(exc).__name__}: {exc}']}
            raise

    def _begin_readback(self,phase):
        self.readback_phase = phase
        self.last_reports = {k:{'passed':False,'status':'not_read','errors':['Readback not reached']}
                             for k in self._bridges}

    def synchronize(self, steps):
        if self.failed:
            raise RuntimeError('Fleet bridge terminated after failure')
        self.last_reports, self.readback_phase = {}, 'integration_validation'
        try:
            if set(steps) != set(self._bridges):
                raise ValueError('Every frozen vehicle needs exactly one integrated step')
            # Complete validation before the first mutation of SUMO.
            for key,b in self._bridges.items():
                validate_integrated_step(steps[key],b.current,self.dt,self.model)
            self._begin_readback('precommit')
            for key,b in self._bridges.items():
                self._capture(key,b)
            for key,b in self._bridges.items():
                b._require(self.last_reports[key])
            self.last_reports, self.readback_phase = {}, 'commit'
            for key,b in self._bridges.items():
                final = steps[key].final
                x,y,angle = to_sumo_pose(final,self.model.p['length_m'])
                self.connection.vehicle.setSpeed(key,self.model.observe(final)['speed_mps'])
                self.connection.vehicle.moveToXY(key,'',-1,x,y,angle=angle,keepRoute=self.model.p['sumo_move_keep_route'])
            self.connection.simulationStep()
            self.advances += 1
            # Obtain every report before checking; failure evidence includes all cars.
            self._begin_readback('postcommit')
            for key,b in self._bridges.items():
                self._capture(key,b,steps[key].final,
                    (self.model.observe(steps[key].final)['speed_mps']-self.model.observe(b.current)['speed_mps'])/self.dt)
            for key,b in self._bridges.items():
                b._require(self.last_reports[key])
            for key,b in self._bridges.items():
                b.current, b.last_report = steps[key].final, self.last_reports[key]
            return self.last_reports
        except BaseException:
            self.failed = True
            raise


class MultiVehicleClock:
    def __init__(self, initial, model, road, parameters):
        self.model, self.p = model, MappingProxyType(dict(parameters))
        self.dt, self.dynamics_dt = self.p['control_sync_dt_s'], self.p['dynamics_dt_s']
        if not math.isclose(self.dt,self.p['perception_dt_s'],abs_tol=1e-12,rel_tol=0):
            raise ValueError('Phase 3 requires synchronous control/perception sampling')
        self.states = MappingProxyType(dict(initial))
        self._frame()
        self._sensors = {k:IdealSensor(self.p,road) for k in initial}
        # This is the complete immutable configuration passed to the probe.
        names = ('length_m','width_m','comfort_braking_mps2','comfort_accel_mps2')
        self._probe_parameters = MappingProxyType({k:v for k,v in parameters.items() if k.startswith('probe_') or k in names})
        self.failed, self.last_record = False, None

    def _frame(self):
        return WorldFrame(tuple(TruthVehicle(k,s,self.model.p['length_m'],self.model.p['width_m'],
                                             self.model.observe(s)['a_long_mps2']) for k,s in self.states.items()))

    def tick(self, bridge=None, order=None):
        if self.failed:
            raise RuntimeError('Physical clock terminated after failure')
        keys = tuple(order) if order is not None else tuple(sorted(self.states))
        self.last_record = {'status':'running','initial':{k:asdict(s) for k,s in sorted(self.states.items())}}
        try:
            if len(keys) != len(self.states) or set(keys) != set(self.states):
                raise ValueError('Control order must contain each local agent exactly once')
            frame = self._frame()
            inputs = {k:self._sensors[k].sample(k,frame) for k in keys}
            self.last_record['inputs'] = {k:asdict(inputs[k]) for k in sorted(keys)}
            actions = {k:probe_action(inputs[k],self._probe_parameters) for k in keys}
            self.last_record['actions'] = {k:asdict(actions[k]) for k in sorted(keys)}
            steps = {k:self.model.advance(self.states[k],actions[k],self.dt,self.dynamics_dt) for k in keys}
            self.last_record['steps'] = {k:asdict(steps[k]) for k in sorted(keys)}
            self.last_record['diagnostics'] = {k:[self.model.observe(s) for s in steps[k].samples] for k in sorted(keys)}
            self.last_record['readback'] = bridge.synchronize(steps) if bridge is not None else None
            self.states = MappingProxyType({k:steps[k].final for k in sorted(keys)})
            self.last_record['status'] = 'completed'
            return self.last_record
        except BaseException as exc:
            self.failed = True
            self.last_record.update(status='failed',error=f'{type(exc).__name__}: {exc}')
            if bridge is not None:
                self.last_record['readback'] = bridge.last_reports
                self.last_record['readback_phase'] = bridge.readback_phase
            raise
