"""Synchronize integrated CG state to SUMO, then audit without correcting it.

Only this module advances the attached single-vehicle SUMO connection. Native
movement is overwritten by the queued endpoint, never added to model state.
The bootstrap interval is excluded and retained as an explicit time offset.
"""
from dataclasses import astuple
import math
from models.geometry import to_sumo_pose, from_sumo_pose
from models.vehicle import VehicleModel


def validate_integrated_step(step, current, sync_dt_s, model=None):
    model = model or VehicleModel.from_config()
    tol = model.p['replay_absolute_tolerance']
    if step.initial != current:
        raise ValueError('Stale/duplicate integration: initial state is not current')
    if not math.isclose(step.final.time_s-current.time_s, sync_dt_s, rel_tol=0, abs_tol=tol):
        raise ValueError('Integration time is not one synchronization interval')
    expected = model.advance(current, step.command, sync_dt_s, step.dt_s)
    if len(step.samples) != len(expected.samples) or not step.samples or step.final != step.samples[-1]:
        raise ValueError('Incomplete integration samples or inconsistent endpoint')
    for observed, reference in zip(step.samples, expected.samples):
        if any(not math.isfinite(a) or abs(a-b)>tol for a,b in zip(astuple(observed),astuple(reference))):
            raise ValueError('Integrated path differs from state/command replay (possible teleport)')


def audit_readback(raw, state, model, time_offset_s, expected_interval_acceleration=None):
    p = model.p
    x,y,psi = from_sumo_pose(raw['front_x_m'],raw['front_y_m'],raw['angle_deg'],p['length_m'])
    diagnostic = model.observe(state)
    position_error = math.hypot(x-state.x_m,y-state.y_m)
    heading_error = abs(math.atan2(math.sin(psi-state.heading_rad),math.cos(psi-state.heading_rad)))
    speed_error = abs(raw['speed_mps']-diagnostic['speed_mps'])
    time_error = abs(raw['sumo_time_s']-time_offset_s-state.time_s)
    errors=[]
    checks=(('position',position_error,p['sync_position_tolerance_m']),
            ('heading',heading_error,p['sync_heading_tolerance_rad']),
            ('speed',speed_error,p['sync_speed_tolerance_mps']),('time',time_error,p['sync_time_tolerance_s']))
    for name,error,tolerance in checks:
        if not math.isfinite(error) or error>tolerance:
            errors.append(f'SUMO {name} readback mismatch: {error}')
    acceleration_error=None
    if expected_interval_acceleration is not None:
        acceleration_error=abs(raw['acceleration_mps2']-expected_interval_acceleration)
        if not math.isfinite(acceleration_error) or acceleration_error>p['sync_acceleration_tolerance_mps2']:
            errors.append(f'SUMO interval acceleration mismatch: {acceleration_error}')
    return {'passed':not errors,'errors':errors,**raw,'physical_time_s':state.time_s,
            'sumo_time_offset_s':time_offset_s,'cg_x_m':x,'cg_y_m':y,'heading_rad':psi,
            'position_error_m':position_error,'heading_error_rad':heading_error,
            'speed_error_mps':speed_error,'time_error_s':time_error,
            'expected_interval_acceleration_mps2':expected_interval_acceleration,
            'interval_acceleration_error_mps2':acceleration_error,
            'model_a_long_mps2':diagnostic['a_long_mps2'],
            'model_a_lateral_mps2':diagnostic['a_lateral_mps2']}


class SynchronizationError(RuntimeError):
    def __init__(self,report):
        self.report=report
        super().__init__('; '.join(report['errors']))


class ExternalBridge:
    def __init__(self,connection,vehicle_id,model,initial,sync_dt_s):
        self.connection,self.vehicle_id,self.model=connection,vehicle_id,model
        self.current,self.dt=initial,sync_dt_s
        actual_dt=connection.simulation.getDeltaT()
        if not math.isclose(actual_dt,sync_dt_s,abs_tol=1e-12,rel_tol=0):
            raise ValueError(f'Wrong SUMO dt: {actual_dt} vs {sync_dt_s} seconds')
        self.time_offset=connection.simulation.getTime()-initial.time_s
        self.last_report=self.readback()
        self._require(self.last_report)

    @staticmethod
    def _require(report):
        if not report['passed']:
            raise SynchronizationError(report)

    def readback(self, state=None, expected_interval_acceleration=None):
        v,c=self.vehicle_id,self.connection
        x,y=c.vehicle.getPosition(v)
        raw={'sumo_time_s':c.simulation.getTime(),'front_x_m':x,'front_y_m':y,
             'angle_deg':c.vehicle.getAngle(v),'speed_mps':c.vehicle.getSpeed(v),
             'acceleration_mps2':c.vehicle.getAcceleration(v),
             'edge_id':c.vehicle.getRoadID(v),'lane_id':c.vehicle.getLaneID(v),
             'lane_index':c.vehicle.getLaneIndex(v),
             'colliding_vehicle_reports':c.simulation.getCollidingVehiclesNumber(),
             'teleport_starts':c.simulation.getStartingTeleportNumber()}
        report=audit_readback(raw,state or self.current,self.model,self.time_offset,expected_interval_acceleration)
        if raw['colliding_vehicle_reports'] or raw['teleport_starts']:
            report['errors'].append('SUMO collision or teleport reported')
            report['passed']=False
        return report

    def synchronize(self,step):
        validate_integrated_step(step,self.current,self.dt,self.model)
        # Detect any extra native step or pose mutation before submitting a state.
        self.last_report=self.readback()
        self._require(self.last_report)
        speed=self.model.observe(step.final)['speed_mps']
        previous_speed=self.model.observe(self.current)['speed_mps']
        x,y,angle=to_sumo_pose(step.final,self.model.p['length_m'])
        c=self.connection
        c.vehicle.setSpeed(self.vehicle_id,speed)
        c.vehicle.moveToXY(self.vehicle_id,'',-1,x,y,angle=angle,keepRoute=self.model.p['sumo_move_keep_route'])
        c.simulationStep()
        self.last_report=self.readback(step.final,(speed-previous_speed)/self.dt)
        self._require(self.last_report)
        self.current=step.final
        return self.last_report
