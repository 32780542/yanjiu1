"""持续交通的车辆守恒、行程时间与同区间油耗统计。"""

from statistics import mean


def summarize_trips(trips, demand_duration_s, recording_end_s):
    rows = list(trips)
    entered = [r for r in rows if r["entered_s"] is not None]
    completed = [r for r in entered if r["exited_s"] is not None]
    all_completed = len(completed) == len(rows) and bool(rows)
    released = sum(r["requested_s"] < recording_end_s-1e-9 for r in rows)
    window_complete = recording_end_s >= demand_duration_s-1e-9
    distance = sum(r["distance_m"] for r in rows)
    fuel = sum(r["fuel_mg"] for r in rows)
    vehicle_seconds = sum(r["onroad_s"] for r in rows)
    exits_in_window = sum(r["exited_s"] <= demand_duration_s for r in completed)
    entries_in_window = sum(r["entered_s"] <= demand_duration_s for r in entered)
    return dict(requested=len(rows), entered=len(entered), completed=len(completed),
        all_completed=all_completed, requested_until_end=released,
        not_yet_requested_final=len(rows)-released, window_complete=window_complete,
        pending_final=released-len(entered),
        onroad_final=len(entered)-len(completed), recording_end_s=recording_end_s,
        entered_by_600s=entries_in_window if window_complete else None,
        exited_by_600s=exits_in_window if window_complete else None,
        pending_at_600s=len(rows)-entries_in_window if window_complete else None,
        onroad_at_600s=entries_in_window-exits_in_window if window_complete else None,
        exit_flow_veh_h=3600*exits_in_window/demand_duration_s if window_complete else None,
        mean_entry_wait_s=mean(r["entered_s"]-r["requested_s"] for r in entered) if all_completed else None,
        mean_travel_time_s=mean(r["exited_s"]-r["entered_s"] for r in completed) if all_completed else None,
        mean_system_time_s=mean(r["exited_s"]-r["requested_s"] for r in completed) if all_completed else None,
        network_mean_speed_mps=distance/vehicle_seconds if vehicle_seconds else None,
        total_distance_km=distance/1000, total_fuel_kg=fuel/1e6,
        fuel_g_per_km=fuel/distance if distance else None,
        mean_fuel_rate_mg_s=fuel/vehicle_seconds if vehicle_seconds else None,
        clearance_after_600s_s=(max(0., max(r["exited_s"] for r in completed)-demand_duration_s)
                               if all_completed else None))
