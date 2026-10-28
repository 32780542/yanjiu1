"""基础纵向行驶：由可见间距和道路终点计算巡航、跟驰与制动。"""

import math

from models.vehicle import clip
from noa.prediction import actuator_acceleration_upper


def stop_distance(speed, acceleration, braking, parameters):
    """按响应期、制动力建立期和后续恒定制动三段计算停车距离。"""
    p = parameters
    response = p["noa_response_time_s"]
    positive = max(0.0, acceleration)
    distance = speed * response + positive * response**2 / 2
    speed += positive * response
    jerk = p["actuator_jerk_limit_mps3"]
    weaker = max(braking / 2, braking - jerk * p["acceleration_lag_s"])
    initial = max(acceleration, -weaker)
    ramp = max(0.0, (initial + weaker) / jerk)
    stop_during_ramp = (initial + math.sqrt(initial**2 + 2 * jerk * speed)) / jerk
    t = min(ramp, stop_during_ramp)
    distance += speed * t + initial * t * t / 2 - jerk * t * t * t / 6
    remaining_speed = max(0.0, speed + initial * t - jerk * t * t / 2)
    return distance + remaining_speed**2 / (2 * weaker)


def comfortable_speed(distance, parameters, acceleration=0.0):
    """用二分法反求给定间距下的速度，同时计入制动和反馈收敛距离。"""
    p = parameters
    lower, upper = 0.0, min(p["noa_target_speed_mps"], p["max_speed_mps"])
    available = max(0.0, distance)

    def required(speed):
        stopping = stop_distance(speed, max(0.0, acceleration), p["comfort_braking_mps2"], p)
        return stopping + speed / p["noa_speed_gain_per_s"]

    if required(upper) <= available:
        return upper
    while upper - lower > p["noa_geometry_tolerance_m"]:
        middle = (lower + upper) / 2
        # A speed-feedback controller does not attain its cap instantly.
        # Reserve its 1/gain settling distance as well as braking response.
        if required(middle) <= available:
            lower = middle
        else:
            upper = middle
    return lower


def response_emergency(ego, lead_speed, gap, parameters):
    """按当前闭合速度筛查响应距离；同速运动不会触发虚假停车约束。"""
    p = parameters
    closing = max(0.,ego.vx_mps-lead_speed)
    return gap <= p['noa_standstill_gap_m'] or (closing > 0 and (
        gap/closing < p['noa_emergency_ttc_s'] or
        gap < p['noa_standstill_gap_m']+stop_distance(
            closing,actuator_acceleration_upper(ego,p),abs(p['min_accel_mps2']),p)))


def _lead_gaps(ego,bodies,center_y,p):
    """同一套前向车身及观测到的切入候选，供跟驰与应急共用。"""
    for body in bodies:
        lateral_half = (
            p["width_m"]
            + abs(math.cos(body.heading)) * body.width
            + abs(math.sin(body.heading)) * body.length
        ) / 2
        # Observed lateral motion projects cut-ins over the near response time.
        lateral_now, lateral_future = (
            body.y - ego.y_m,
            body.y + body.vy * p["noa_emergency_ttc_s"] - ego.y_m,
        )
        crosses = (
            min(lateral_now, lateral_future) <= lateral_half
            and max(lateral_now, lateral_future) >= -lateral_half
        )
        overlaps_lane = abs(body.y - center_y) <= lateral_half
        if body.x < ego.x_m or not (crosses or overlaps_lane):
            continue
        body_half = (
            abs(math.cos(body.heading)) * body.length + abs(math.sin(body.heading)) * body.width
        ) / 2
        yield body,body.x-ego.x_m-p['length_m']/2-body_half


def immediate_emergency(ego,bodies,p):
    return any(response_emergency(ego,max(0.,body.vx),gap,p)
               for body,gap in _lead_gaps(ego,bodies,ego.y_m,p))


def longitudinal(ego, bodies, center_y, lane_end_x, parameters):
    """组合巡航、可见前车和道路终点约束，返回加速度与当前安全状态。"""
    p, speed = parameters, ego.vx_mps
    half_dt = p["control_sync_dt_s"] / 2
    feedback_speed = clip(speed + ego.acceleration_mps2 * half_dt, 0.0, p["max_speed_mps"])
    actuator_upper = actuator_acceleration_upper(ego, p)
    acceleration = p["noa_speed_gain_per_s"] * (
        min(p["noa_target_speed_mps"], p["max_speed_mps"]) - feedback_speed
    )
    closest, closest_gap = None,None
    emergency = immediate_emergency(ego,bodies,p)
    for body,gap in _lead_gaps(ego,bodies,center_y,p):
        if closest_gap is None or gap < closest_gap:
            closest, closest_gap = body, gap
    reason = "cruise"
    if closest is not None:
        gap, lead_speed = closest_gap, max(0.0, closest.vx)
        feedback_gap = gap + (lead_speed - speed) * half_dt
        desired = p["noa_standstill_gap_m"] + p["noa_headway_s"] * feedback_speed
        follow = p["noa_gap_gain_per_s2"] * (feedback_gap - desired) - p[
            "noa_relative_speed_gain_per_s"
        ] * (feedback_speed - lead_speed)
        acceleration, reason = min(acceleration, follow), "visible_lead"
        emergency = emergency or response_emergency(ego,lead_speed,gap,p)
        if lead_speed <= p['noa_stop_release_speed_mps']:
            safe_speed = comfortable_speed(feedback_gap-p['noa_standstill_gap_m'],p,actuator_upper)
            acceleration = min(acceleration,p['noa_speed_gain_per_s']*(safe_speed-feedback_speed))
        if (
            speed <= p["noa_stop_release_speed_mps"]
            and lead_speed <= p["noa_stop_release_speed_mps"]
            and gap <= p["noa_standstill_gap_m"]
        ):
            acceleration = min(acceleration, 0.0)
        if (
            lead_speed <= p["noa_stop_release_speed_mps"]
            and speed <= p["noa_stop_capture_speed_mps"]
            and gap
            <= p["noa_stop_capture_gap_m"] + p["noa_headway_s"] * p["noa_stop_capture_speed_mps"]
        ):
            # Initiate the terminal speed-feedback profile in a fixed local
            # capture region, then hold until the observed lead moves/leaves.
            acceleration = min(
                acceleration,
                -p["noa_stop_speed_gain_per_s"] * speed - p["noa_stop_terminal_braking_mps2"],
            )
    if lane_end_x is not None:
        gap = (
            lane_end_x
            - ego.x_m
            - p["length_m"] / 2
            - p["noa_body_margin_m"]
            - p["noa_standstill_gap_m"]
        )
        # A visible physical lane end is a stationary virtual target. Merely
        # releasing a braking-distance trigger at low speed causes repeated
        # restarts into a blocked endpoint; continuous gap feedback avoids it.
        # The comfortable stop target stays upstream of the hard screening
        # boundary, leaving a spatial reserve for terminal tracking error.
        virtual_follow = p["noa_speed_gain_per_s"] * (
            comfortable_speed(
                gap - speed * half_dt - p["noa_stop_position_reserve_m"], p, actuator_upper
            )
            - feedback_speed
        )
        acceleration = min(acceleration, virtual_follow)
        reason = "observed_lane_end_approach"
        if virtual_follow < 0:
            reason = "observed_lane_end_braking"
        if (
            speed <= p["noa_stop_capture_speed_mps"]
            and gap
            <= p["noa_stop_capture_gap_m"] + p["noa_headway_s"] * p["noa_stop_capture_speed_mps"]
        ):
            acceleration = min(
                acceleration,
                -p["noa_stop_speed_gain_per_s"] * speed - p["noa_stop_terminal_braking_mps2"],
            )
            reason = "observed_lane_end_hold"
        if gap <= stop_distance(speed, actuator_upper, abs(p["min_accel_mps2"]), p):
            emergency = True
    if emergency:
        acceleration = min(acceleration, p["min_accel_mps2"])
    else:
        # Taper before the speed boundary: a finite weak tail eventually stops
        # through the unchanged integrator, without zeroing actuator or speed.
        acceleration = max(
            acceleration,
            -p["noa_stop_speed_gain_per_s"] * speed - p["noa_stop_terminal_braking_mps2"],
        )
        acceleration = clip(acceleration, -p["comfort_braking_mps2"], p["comfort_accel_mps2"])
    return (
        clip(acceleration, p["min_accel_mps2"], p["max_accel_mps2"]),
        closest,
        closest_gap,
        emergency,
        reason,
    )
