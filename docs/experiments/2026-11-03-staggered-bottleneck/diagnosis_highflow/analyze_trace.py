"""Offline action/state accounting of three frozen-TM diagnostic runs."""
import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RUNS = ROOT / "tmp/staggered_bottleneck/diagnostic2500_20261103"


def write_csv(name, rows):
    if not rows:
        return
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def zone(x):
    return "0_640" if x < 640 else "640_800" if x < 800 else "800_1000" if x < 1000 else "1000_1200"


def analyze(mode):
    cases = list((RUNS / mode).glob("20*"))
    assert len(cases) == 1, cases
    case = cases[0]
    result = json.loads((case / "result.json").read_text())
    assert "status" in result and result["status"] != "running", result
    reasons = defaultdict(Counter)
    spatial = defaultdict(Counter)
    episodes, slow_episodes, snapshots = [], [], []
    active, slow_active = {}, {}
    private, next_private = {}, {}
    observed_reasons = Counter()
    total_frames, previous = 0, None
    max_onroad = max_low = 0
    first_slow = None
    def end_episode(episode, end, dest):
        episode["end_s"] = end
        episode["duration_s"] = end - episode["start_s"]
        if episode["duration_s"] > 0:
            episode["mean_speed_mps"] = episode.pop("speed_integral") / episode["duration_s"]
            episode["mean_command_mps"] = episode.pop("command_integral") / episode["duration_s"]
            dest.append(episode)
    with gzip.open(case / "diagnostic.jsonl.gz", "rt") as f:
        for line in f:
            frame = json.loads(line)
            total_frames += 1
            states, actions, t = frame["states"], frame["actions"], frame["time_s"]
            ordered = sorted(states, key=lambda k: (states[k]["x"], states[k]["y"], states[k]["speed"]))
            xs = [states[k]["x"] for k in ordered]
            for k in tuple(private):
                if k not in states:
                    del private[k]
                    del next_private[k]
            for k in ordered:
                own = private.setdefault(k, {})
                nxt = next_private.setdefault(k, 1)
                ego = states[k]
                for other in ordered[bisect_left(xs, ego["x"] - 100):bisect_right(xs, ego["x"] + 200)]:
                    if other != k and other not in own:
                        own[other] = nxt
                        nxt += 1
                next_private[k] = nxt
                ref = actions[k]["reference"]
                actions[k]["reference_physical_id"] = next((other for other, track in own.items() if track == ref), None) if ref is not None else None
            if previous is not None:
                old_t, old_states, old_actions = previous
                dt = t - old_t
                assert 0.09999 <= dt <= .10001
                for k, state in old_states.items():
                    action = old_actions[k]
                    reason = action["reason"]
                    z = zone(state["x"])
                    key = (reason, z, state["lane"])
                    stats = reasons[key]
                    stats["ticks"] += 1
                    observed_reasons[reason] += 1
                    stats["vehicle_s"] += dt
                    stats["speed_integral"] += state["speed"] * dt
                    stats["command_integral"] += action["speed"] * dt
                    stats["low5_vehicle_s"] += dt * (state["speed"] < 5)
                    stats["low10_vehicle_s"] += dt * (state["speed"] < 10)
                    stats["requested_lane_ticks"] += action["lane"] is not None and action["lane"] != state["lane"]
                    stats["accepted_lane_ticks"] += action["accepted"]
                    guard_rejected = (action["lane"] is not None and action["lane"] != state["lane"] and not action["accepted"]
                                      and action["pending_lane"] is None and abs(state["vy"]) <= .05)
                    stats["guard_rejected_ticks"] += guard_rejected
                    spatial_key = (int(old_t // 30) * 30, z, state["lane"])
                    sp = spatial[spatial_key]
                    sp["vehicle_s"] += dt
                    sp["speed_integral"] += state["speed"] * dt
                    sp["low5_vehicle_s"] += dt * (state["speed"] < 5)
                    sp["low10_vehicle_s"] += dt * (state["speed"] < 10)
                    for registry, dest, is_active in ((active, episodes, True), (slow_active, slow_episodes, state["speed"] < 5)):
                        old_episode = registry.get(k)
                        tag = reason if registry is active else "speed_lt_5"
                        if old_episode is not None and (not is_active or old_episode["reason"] != tag):
                            end_episode(old_episode, old_t, dest)
                            registry.pop(k)
                            old_episode = None
                        if is_active:
                            if old_episode is None:
                                old_episode = registry[k] = dict(mode=mode, vehicle_id=k, reason=tag, start_s=old_t,
                                    start_x=state["x"], start_lane=state["lane"], end_x=state["x"], end_lane=state["lane"],
                                    speed_integral=0.0, command_integral=0.0)
                            old_episode["end_x"], old_episode["end_lane"] = state["x"], state["lane"]
                            old_episode["speed_integral"] += state["speed"] * dt
                            old_episode["command_integral"] += action["speed"] * dt
                for registry, dest in ((active, episodes), (slow_active, slow_episodes)):
                    for k in tuple(registry):
                        if k not in old_states:
                            end_episode(registry.pop(k), old_t, dest)
            low_n = sum(s["speed"] < 5 for s in states.values())
            max_onroad, max_low = max(max_onroad, len(states)), max(max_low, low_n)
            if low_n and first_slow is None:
                first_slow = t
            if abs(t - round(t)) < 1e-7 and int(round(t)) % 10 == 0:
                snap = dict(mode=mode, time_s=t, onroad_n=len(states), low5_n=low_n)
                for z in ("0_640", "640_800", "800_1000", "1000_1200"):
                    for lane in range(3):
                        ss = [s for s in states.values() if zone(s["x"]) == z and s["lane"] == lane]
                        snap[f"{z}_lane{lane}_n"] = len(ss)
                        snap[f"{z}_lane{lane}_low5_n"] = sum(s["speed"] < 5 for s in ss)
                snapshots.append(snap)
            previous = t, states, actions
    last_t = previous[0]
    for registry, dest in ((active, episodes), (slow_active, slow_episodes)):
        for episode in registry.values():
            end_episode(episode, last_t, dest)
    reason_rows = []
    for (reason, z, lane), stats in sorted(reasons.items()):
        reason_rows.append(dict(mode=mode, reason=reason, zone=z, lane=lane, **stats,
                               mean_speed_mps=stats["speed_integral"] / stats["vehicle_s"],
                               mean_command_mps=stats["command_integral"] / stats["vehicle_s"]))
    spatial_rows = [dict(mode=mode, start_s=start, end_s=start + 30, zone=z, lane=lane, **stats,
                         mean_speed_mps=stats["speed_integral"] / stats["vehicle_s"])
                    for (start, z, lane), stats in sorted(spatial.items())]
    trips = json.loads((case / "trips.json").read_text())
    trip_rows = []
    for row in trips:
        trip_rows.append(dict(mode=mode, vehicle_id=row["vehicle_id"], requested_s=row["requested_s"],
                              entered_s=row["entered_s"], exited_s=row["exited_s"], initial_lane=row["lane"],
                              tt_s=None if row["exited_s"] is None else row["exited_s"] - row["entered_s"],
                              entry_wait_s=None if row["entered_s"] is None else row["entered_s"] - row["requested_s"],
                              lane_changes=row["lane_changes"]))
    summary = dict(mode=mode, case_dir=str(case), frames=total_frames, first_slow_s=first_slow,
                   max_onroad=max_onroad, max_simultaneous_low5=max_low,
                   reason_ticks=dict(observed_reasons),
                   execution=result["execution"],
                   **{k:result[k] for k in ("status", "safe", "all_completed", "requested", "departed", "completed", "actual_end_s", "mean_travel_time_s", "mean_system_time_s", "mean_entry_wait_s", "lane_changes", "lane_change_completions", "collisions", "teleports", "source_sha256")})
    for name, rows in (("reasons", reason_rows), ("spatial", spatial_rows), ("episodes", episodes),
                       ("slow_episodes", slow_episodes), ("snapshots", snapshots), ("trips", trip_rows)):
        write_csv(mode + "_" + name + ".csv", rows)
    (OUT / (mode + "_summary.json")).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ("mode", "frames", "mean_travel_time_s", "max_onroad", "max_simultaneous_low5", "execution")}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", nargs="+", default=["transform", "noa", "formation"])
    args = parser.parse_args()
    for mode in args.modes:
        analyze(mode)
