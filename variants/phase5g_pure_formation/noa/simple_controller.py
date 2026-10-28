"""当前编队执行流程：选补位车、保持锚点、计算纵向动作、逐车道换道。

几何规则见 simple_formation.py；此模块把规则结果转为本车动作和私有记忆。
"""

from dataclasses import replace
import math

from models.bezier import QuadraticLaneChange
from models.vehicle import Actuation, clip
from noa.contracts import NoaDecision
from noa.driving import stop_distance, immediate_emergency
from noa.prediction import actuator_acceleration_upper, lateral_command, reference_target
from noa import simple_formation


def road_stop_required(ego, lane_end_x, p):
    """可见道路剩余距离进入停车范围时，接管编队纵向请求。"""
    available = (
        lane_end_x
        - ego.x_m
        - p["length_m"] / 2
        - p["noa_body_margin_m"]
        - p["noa_standstill_gap_m"]
    )
    stopping = stop_distance(
        ego.vx_mps, actuator_acceleration_upper(ego, p), p["comfort_braking_mps2"], p
    )
    capture = (
        ego.vx_mps <= p["noa_stop_capture_speed_mps"]
        and available
        <= p["noa_stop_capture_gap_m"] + p["noa_headway_s"] * p["noa_stop_capture_speed_mps"]
    )
    return available <= stopping or capture


def body_overlap(ego, bodies, lane_center, p):
    """检查放在指定车道中心的本车是否与可见车身重叠。"""
    for body in bodies:
        lateral_half = (
            p["width_m"]
            + abs(math.cos(body.heading)) * body.width
            + abs(math.sin(body.heading)) * body.length
        ) / 2
        longitudinal_half = (
            p["length_m"]
            + abs(math.cos(body.heading)) * body.length
            + abs(math.sin(body.heading)) * body.width
        ) / 2
        if abs(body.y - lane_center) < lateral_half and abs(body.x - ego.x_m) < longitudinal_half:
            return True
    return False


def hard_gate(ego, ego_row, rows, centers, next_lane, final_lane, bodies, p):
    """按道路、车速、当前车身和目标车道净空的次序检查换道。"""
    if (
        final_lane is None
        or type(final_lane) is not int
        or not 0 <= final_lane < len(centers)
        or next_lane is None
        or not 0 <= next_lane < len(centers)
        or abs(next_lane - ego_row.lane_index) != 1
    ):
        return "road"
    if ego.vx_mps < p["simple_formation_min_lane_change_speed_mps"]:
        return "speed"
    if body_overlap(ego, bodies, ego.y_m, p):
        return "body"
    if not simple_formation.target_lane_clear(ego_row, rows, next_lane, p):
        return "clearance"
    if body_overlap(ego, bodies, centers[next_lane], p):
        return "body"
    return "clear"


def execute(
    control,
    p,
    road,
    bodies,
    memory,
    diagnostics,
    accel,
    emergency,
    end_x,
    *,
    longitudinal,
    completed_simple=False
):
    """在同一物理时刻完成候选判断、锚点跟踪、纵向控制和横向执行。"""
    ego = control.ego
    detail = diagnostics["simple_formation"]
    rows = simple_formation.local_vehicles(control, road, p)
    centers = road.centers_m
    ego_lane = centers.index(road.current_center_m)
    ego_row = simple_formation.LocalVehicle(
        0,
        ego.x_m,
        ego.y_m,
        ego.vx_mps,
        ego_lane,
        ego.vx_mps * math.sin(ego.heading_rad) + ego.vy_mps * math.cos(ego.heading_rad),
    )
    active_plan = memory.plan is not None and memory.lane_change_reason == "simple_formation_join"
    next_lane = None

    # 1. 自由车辆按四层占位选择候选，并累计连续稳定时间。
    if memory.join_phase in ("FREE", "FORMED") and not active_plan and not completed_simple:
        previous_reference = memory.reference_track_id
        following = simple_formation.choose_formation_target(ego_row, rows, centers, memory, p)
        window = simple_formation.layered_window(ego_row, rows, centers, p)
        fill = simple_formation.choose_layered_fill(ego_row, rows, centers, p)
        detail["local_layers"] = tuple(
            tuple(row is not None for row in layer) for layer in window.layers
        )
        detail["layer_stable"] = window.consistent and not window.crossing and window.speed_stable
        detail["local_counts"] = fill.local_counts
        detail["lane_reason"] = fill.reason
        final = fill.target_lane_index
        if final is None or emergency:
            memory = replace(
                memory,
                desired_lane_index=None,
                join_anchor_track_id=None,
                stable_since_s=None,
                stable_window_signature=None,
            )
            if emergency:
                detail["lane_reason"] = "emergency_priority"
        else:
            next_lane = ego_lane + (1 if final > ego_lane else -1)
            gate = hard_gate(ego, ego_row, rows, centers, next_lane, final, bodies, p)
            detail["hard_gate"] = gate
            if gate != "clear":
                memory = replace(
                    memory,
                    desired_lane_index=None,
                    join_anchor_track_id=None,
                    stable_since_s=None,
                    stable_window_signature=None,
                )
                detail["lane_reason"] = "hard_gate_" + gate
            else:
                same = (
                    memory.desired_lane_index == final
                    and memory.join_anchor_track_id == fill.anchor_track_id
                    and previous_reference == following.reference_track_id
                    and memory.stable_window_signature == window.signature
                    and memory.stable_since_s is not None
                )
                since = memory.stable_since_s if same else ego.time_s
                if ego.time_s - since >= p["simple_formation_stable_time_s"]:
                    memory = replace(
                        memory,
                        join_phase="JOINING",
                        desired_lane_index=final,
                        join_anchor_track_id=fill.anchor_track_id,
                        stable_since_s=None,
                        stable_window_signature=None,
                    )
                else:
                    memory = replace(
                        memory,
                        desired_lane_index=final,
                        join_anchor_track_id=fill.anchor_track_id,
                        stable_since_s=since,
                        stable_window_signature=window.signature,
                    )
                    detail["lane_reason"] = "layer_stabilizing"
    # 2. 进入补位后固定本车锚点；锚点消失或槽位被占时重新判断。
    target = simple_formation.choose_formation_target(ego_row, rows, centers, memory, p)
    if (
        memory.join_phase in ("JOINING", "STABILIZING")
        and memory.join_anchor_track_id is None
        and memory.desired_lane_index == 2
    ):
        target = simple_formation.FormationTarget(
            "upper_leader", None, None, p["noa_target_speed_mps"], 2, None, "founder_target"
        )
    final_visible = type(memory.desired_lane_index) is int and 0 <= memory.desired_lane_index < len(
        centers
    )
    target_occupied = (
        memory.join_phase in ("JOINING", "STABILIZING")
        and final_visible
        and not active_plan
        and ego_lane == memory.desired_lane_index
        and target.target_x_m is not None
        and any(
            row.lane_index == memory.desired_lane_index
            and abs(row.x_m - target.target_x_m) <= p["simple_formation_position_tolerance_m"]
            for row in rows
        )
    )
    release_reason = (
        "join_target_occupied"
        if target_occupied
        else (
            target.reason
            if target.reason in ("join_anchor_lost", "join_anchor_invalid", "join_state_incomplete")
            else None
        )
    )
    if (
        memory.join_phase in ("JOINING", "STABILIZING")
        and final_visible
        and release_reason is not None
    ):
        memory = replace(
            memory,
            join_phase="FREE",
            desired_lane_index=None,
            join_anchor_track_id=None,
            stable_since_s=None,
            stable_window_signature=None,
            reference_track_id=None,
            plan=None,
            target_y_m=None,
            lane_change_reason="",
        )
        target = simple_formation.FormationTarget(
            "no_target", None, None, None, None, None, release_reason
        )
        active_plan = False
        detail["lane_reason"] = release_reason
        accel, _, current_gap, emergency, current_reason = longitudinal(
            ego, bodies, road.current_center_m, end_x, p
        )
        diagnostics["lead_gap_m"] = current_gap
        diagnostics["reason"] = current_reason
        detail["emergency_override"] = emergency
    memory = replace(memory, reference_track_id=target.reference_track_id)
    requested = simple_formation.formation_acceleration(ego_row, target, p)
    detail.update(
        role=target.role,
        target_x_m=target.target_x_m,
        position_error_m=(None if target.target_x_m is None else target.target_x_m - ego.x_m),
        reference_track_id=target.reference_track_id,
        reference_reason=target.reason,
        target_lane_index=target.target_lane_index,
        reference_lane_index=target.reference_lane_index,
        requested_acceleration_mps2=requested,
    )
    # 3. 编队纵向请求依次服从紧急制动、道路终点和模型边界。
    immediate = immediate_emergency(ego, bodies, p)
    if active_plan:
        immediate = immediate or body_overlap(ego, bodies, memory.plan.y_target_m, p)
    emergency = emergency or immediate
    state = "EMERGENCY" if emergency else "CRUISE"
    if emergency:
        accel = min(accel, p["min_accel_mps2"])
        detail["emergency_override"] = True
        if not active_plan:
            detail["lane_reason"] = "emergency_priority"
    elif requested is not None:
        accel = requested
    if end_x is not None and road_stop_required(ego, end_x, p):
        road_accel, _, _, road_emergency, road_reason = longitudinal(
            ego, (), road.current_center_m, end_x, p
        )
        if road_accel <= accel:
            accel = road_accel
            detail["road_end_override"] = True
            detail["road_end_reason"] = road_reason
            diagnostics["reason"] = road_reason
        if road_emergency:
            state = "EMERGENCY"
            detail["emergency_override"] = True
            detail["road_end_reason"] = road_reason
            diagnostics["reason"] = road_reason
    accel = clip(accel, p["min_accel_mps2"], p["max_accel_mps2"])

    # 4. 逐条相邻车道执行换道，到位并稳定后记为 FORMED。
    final = memory.desired_lane_index
    if memory.join_phase in ("JOINING", "STABILIZING"):
        if final is None or type(final) is not int or not 0 <= final < len(centers):
            detail["hard_gate"] = "road"
        elif ego_lane == final:
            aligned = abs(ego.y_m - centers[final]) <= p["noa_completion_lateral_error_m"]
            position_ok = (
                target.target_x_m is None
                or abs(target.target_x_m - ego.x_m) <= p["simple_formation_position_tolerance_m"]
            )
            reference_speed = (
                p["noa_target_speed_mps"]
                if target.reference_speed_mps is None
                else target.reference_speed_mps
            )
            speed_ok = (
                abs(ego.vx_mps - reference_speed) <= p["simple_formation_speed_tolerance_mps"]
            )
            if aligned and position_ok and speed_ok and state != "EMERGENCY":
                since = memory.stable_since_s
                if since is None:
                    since = ego.time_s
                phase = (
                    "FORMED"
                    if ego.time_s - since >= p["simple_formation_stable_time_s"]
                    else "STABILIZING"
                )
                memory = replace(memory, join_phase=phase, stable_since_s=since)
                detail["lane_reason"] = "formed" if phase == "FORMED" else "stabilizing"
            else:
                memory = replace(memory, join_phase="JOINING", stable_since_s=None)
                detail["lane_reason"] = "stability_reset"
        elif not active_plan and not completed_simple and state != "EMERGENCY":
            memory = replace(memory, join_phase="JOINING", stable_since_s=None)
            next_lane = ego_lane + (1 if final > ego_lane else -1)
            gate = hard_gate(ego, ego_row, rows, centers, next_lane, final, bodies, p)
            detail["hard_gate"] = gate
            if gate == "clear":
                plan = QuadraticLaneChange(
                    ego.time_s,
                    ego.y_m,
                    centers[next_lane],
                    p["noa_lane_change_duration_s"],
                    ego.vx_mps,
                )
                memory = replace(
                    memory,
                    plan=plan,
                    target_y_m=centers[next_lane],
                    lane_change_reason="simple_formation_join",
                )
                active_plan = True
                detail["lane_reason"] = "simple_formation_join"
            else:
                detail["lane_reason"] = "hard_gate_" + gate
        elif ego_lane != final:
            memory = replace(memory, join_phase="JOINING", stable_since_s=None)
    if active_plan:
        plan = memory.plan
        next_lane = next(
            (
                i
                for i, value in enumerate(centers)
                if abs(value - plan.y_target_m) <= p["noa_geometry_tolerance_m"]
            ),
            None,
        )
        detail["lane_reason"] = (
            "simple_formation_join" if plan.start_s == ego.time_s else "active_simple_plan"
        )
        lateral = reference_target(plan, ego.time_s)
        state = "EMERGENCY" if state == "EMERGENCY" else "EXECUTE_LC"
    else:
        lateral = {"y_m": road.current_center_m, "vy_mps": 0.0, "ay_mps2": 0.0}
    detail.update(
        final_desired_lane_index=memory.desired_lane_index,
        next_lane_index=next_lane,
        join_phase=memory.join_phase,
        stable_since_s=memory.stable_since_s,
    )
    return NoaDecision(
        Actuation(accel, lateral_command(ego, lateral, p)),
        replace(memory, own_behavior=state),
        diagnostics,
    )
