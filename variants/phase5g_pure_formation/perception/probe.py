"""Pure deterministic information-flow probe, NOT a NOA/safety controller.

No imports of truth, files, simulator APIs or evaluation. No road-coordinate,
track-ID priority, clock-based cooperation, random or cross-car mutable state.
"""
from models.vehicle import Actuation


def probe_action(control_input, parameters):
    ego, obs = control_input.ego, control_input.observation
    if ego.time_s != obs.time_s or obs.road.measurement_time_s != ego.time_s:
        raise ValueError('Control input timestamp mismatch')
    acceleration = parameters['probe_speed_gain_per_s']*(parameters['probe_target_speed_mps']-ego.vx_mps)
    for n in obs.neighbors:
        if n.measurement_time_s != ego.time_s:
            raise ValueError('Neighbor timestamp mismatch')
        if n.relative_x_m > 0 and abs(n.relative_y_m) <= (parameters['width_m']+n.width_m)/2:
            gap = n.relative_x_m-(parameters['length_m']+n.length_m)/2
            target = parameters['probe_standstill_gap_m']+parameters['probe_headway_s']*ego.vx_mps
            acceleration = min(acceleration, parameters['probe_gap_gain_per_s2']*(gap-target)
                               + parameters['probe_relative_speed_gain_per_s']*n.relative_vx_mps)
    return Actuation(max(-parameters['comfort_braking_mps2'],
                         min(parameters['comfort_accel_mps2'], acceleration)), 0.)
