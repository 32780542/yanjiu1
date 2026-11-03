"""Recover private-reference identities for offline evaluation only; controllers unchanged."""
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RUNS = ROOT / "tmp/staggered_bottleneck/diagnostic2500_20261103"


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def decode(frame, private, next_private):
    s, a = frame["states"], frame["actions"]
    ordered = sorted(s, key=lambda k: (s[k]["x"], s[k]["y"], s[k]["speed"]))
    xs = [s[k]["x"] for k in ordered]
    for k in ordered:
        own = private.setdefault(k, {})
        nxt = next_private.setdefault(k, 1)
        for other in ordered[bisect_left(xs, s[k]["x"] - 100):bisect_right(xs, s[k]["x"] + 200)]:
            if other != k and other not in own:
                own[other] = nxt; nxt += 1
        next_private[k] = nxt
        ref = a[k]["reference"]
        a[k]["reference_id"] = next((other for other, track in own.items() if track == ref), None) if ref is not None else None


examples, pairs, mode_summaries, helper_events = [], [], [], []
times = {100, 103.2, 103.5, 104, 105, 106, 108, 110, 115, 120, 134.5, 135, 140, 145, 150, 150.1,
         155, 160, 164.7, 165, 170, 180, 185, 190, 195, 196.8, 196.9, 197, 200, 210, 240, 300}
ids = {"v2_00529", "v2_00485", "v1_00525", "v2_00619", "v2_00646", "v0_00785", "v1_00841", "v2_01068"}
for mode in ["transform", "noa", "formation"]:
    case = next((RUNS / mode).glob("20*"))
    private, next_private = {}, {}
    counts = Counter(); pair_active = {}; pair_list = []
    with gzip.open(case / "diagnostic.jsonl.gz", "rt") as f:
        for line in f:
            frame = json.loads(line); t = frame["time_s"]; states, actions = frame["states"], frame["actions"]
            decode(frame, private, next_private)
            current_pairs = {}
            for k, action in actions.items():
                state = states[k]; ref = action["reference_id"]; rs = states.get(ref)
                if action["reason"] == "open_gap":
                    counts["open_gap_ticks"] += 1
                    if rs is not None and state["lane"] == 1 and rs["lane"] == 2:
                        counts["lane1_receiving_lane2_ticks"] += 1
                        gap = rs["x"] - state["x"]
                        if gap < 8 - 1e-8:
                            counts["receiving_gap_below_8_ticks"] += 1
                        if action["target_x"] < state["x"]:
                            counts["receiving_target_behind_ticks"] += 1
                        if action["speed"] < .01:
                            counts["receiving_command_nearzero_ticks"] += 1
                        if rs["x"] >= 999.99 and rs["speed"] < .01 and gap < 8 - 1e-8:
                            counts["terminal_incoming_receiver_too_close_ticks"] += 1
                            pair = (ref, k)
                            current_pairs[pair] = (gap, state, action, actions[ref])
                if action["reason"] in ("prepare_room", "make_room"):
                    helper_events.append(dict(mode=mode, time_s=t, vehicle_id=k, x=state["x"], lane=state["lane"],
                        actual_speed=state["speed"], command_speed=action["speed"], reason=action["reason"],
                        requested_lane=action["lane"], accepted=action["accepted"], target_x=action["target_x"]))
                if t in times and k in ids:
                    lane0 = sorted((v for v in states if v != k and states[v]["lane"] == 0), key=lambda v: abs(states[v]["x"] - state["x"]))[:2]
                    lane1 = sorted((v for v in states if v != k and states[v]["lane"] == 1), key=lambda v: abs(states[v]["x"] - state["x"]))[:2]
                    examples.append(dict(mode=mode, time_s=t, vehicle_id=k, **state, reason=action["reason"],
                        command_speed=action["speed"], safety_cap=action["safe_speed_cap_mps"], target_x=action["target_x"],
                        requested_lane=action["lane"], accepted=action["accepted"], pending_lane=action["pending_lane"],
                        reference_id=ref, reference_x=None if rs is None else rs["x"],
                        reference_speed=None if rs is None else rs["speed"], reference_lane=None if rs is None else rs["lane"],
                        reference_reason=None if ref not in actions else actions[ref]["reason"],
                        nearest_lane0=json.dumps([(v, states[v]["x"]-state["x"], states[v]["speed"]) for v in lane0]),
                        nearest_lane1=json.dumps([(v, states[v]["x"]-state["x"], states[v]["speed"]) for v in lane1])))
            for pair in tuple(pair_active):
                if pair not in current_pairs:
                    ep = pair_active.pop(pair); ep["end_s"] = t; ep["duration_s"] = t - ep["start_s"]; pair_list.append(ep)
            for pair, (gap, state, action, incoming_action) in current_pairs.items():
                ep = pair_active.setdefault(pair, dict(mode=mode, incoming_id=pair[0], receiver_id=pair[1], start_s=t,
                    initial_gap_m=gap, min_gap_m=gap, max_gap_m=gap, incoming_reason=incoming_action["reason"],
                    receiver_start_x=state["x"], receiver_end_x=state["x"], zero_command_ticks=0))
                ep["min_gap_m"] = min(ep["min_gap_m"], gap); ep["max_gap_m"] = max(ep["max_gap_m"], gap)
                ep["receiver_end_x"] = state["x"]; ep["zero_command_ticks"] += action["speed"] < .01
    for pair, ep in pair_active.items():
        ep["end_s"] = t; ep["duration_s"] = t - ep["start_s"]; pair_list.append(ep)
    mode_summaries.append(dict(mode=mode, **counts))
    pairs.extend(pair_list)
write_csv("event_excerpts.csv", examples)
write_csv("terminal_receiver_episodes.csv", pairs)
write_csv("helper_events.csv", helper_events)
(OUT / "receiver_counts.json").write_text(json.dumps(mode_summaries, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(dict(event_rows=len(examples), receiver_pair_episodes=len(pairs), helper_events=len(helper_events)), ensure_ascii=False))
