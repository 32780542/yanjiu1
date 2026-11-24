"""Audit native SUMO traces. Use --cohort for a fixed batch, omit it for traffic.

Fixed batches use every frame, the 11.20 physical shape and the actual IDs in
the demand tape. A partial group's longitudinal envelope may contain no other
car. The maximum is instantaneous. Whole-cohort holds are last minus first
consecutive qualifying sample, with no extrapolation beyond either end.

Transformation endpoints are the last wholly upstream formed frame and first
wholly downstream formed frame. Formation starts at each member's first
physical position and ends when the whole cohort first forms upstream.
Settled ledgers use the last upstream / first downstream qualifying frames
with every vehicle within 0.05 m of its lane center and no recorded completion
still pending. Late movements start at the last settled whole downstream frame.
Each movement audit uses (start, end] for the same IDs at both endpoints.
The lower bounds concern the observed endpoint populations on aligned lanes.
If an endpoint shape never forms, a separate observed-population audit uses
the last whole-cohort, lane-centered sample in each region; its endpoints
may be unbalanced. It never counts as a successful transformation.
The SUMO lane index changes at the lateral midpoint. Completed commands have
a separate later timestamp and may be censored near an observation endpoint.
"""
import argparse
from collections import Counter
import gzip
import hashlib
from itertools import combinations
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

VARIANT = Path(__file__).resolve().parents[3] / "variants/phase5g_pure_formation"
sys.path.insert(0, str(VARIANT))
from experiments.complete_layers import groups_at


def road_layout(folder):
    """Read the actual network; surviving lanes must keep their physical index."""
    net = ET.parse(folder / "native.net.xml")
    ends = []
    for name in ("upstream", "downstream"):
        edge = net.find(f"./edge[@id='{name}']")
        lanes = sorted(edge.findall("lane"), key=lambda lane: int(lane.get("index")))
        for i, lane in enumerate(lanes):
            points = [tuple(map(float, pair.split(","))) for pair in lane.get("shape").split()]
            if int(lane.get("index")) != i or any(abs(y - (i+.5)*3.3) > .02 for _, y in points):
                raise ValueError("Requires the native aligned 3.3 m lane coordinate system")
        ends.append((len(lanes), float(lanes[0].get("length"))))
    for link in net.findall("./connection[@from='upstream'][@to='downstream']"):
        if link.get("fromLane") != link.get("toLane"):
            raise ValueError("Road changes a surviving lane index across the junction")
    return ends


def lane_of(y):
    return round(y / 3.3 - .5)


def centered(states, lanes):
    return all(0 <= lane_of(y) < lanes and abs(y - (lane_of(y)+.5)*3.3) <= .3
               for _, y, *_ in states.values())


def whole_shape(states, lanes):
    """11.20 adaptive spacing and tolerances, including the incomplete last row."""
    if not states or not centered(states, lanes):
        return False
    columns = [[] for _ in range(lanes)]
    speeds = []
    for x, y, speed, *_ in states.values():
        speeds.append(speed)
        columns[lane_of(y)].append(x)
    counts = list(map(len, columns))
    if max(counts) - min(counts) > 1 or max(speeds) - min(speeds) > .5:
        return False
    if lanes == 3 and counts[1] > min(counts[0], counts[2]):
        return False
    gap = 5.5 + .85 * sum(speeds) / len(speeds)
    for column in columns:
        column.sort(reverse=True)
    for phase in (range(2) if lanes == 2 else (0,)):
        origins = [x + (row + ((lane + phase) % 2) / 2) * gap
                   for lane, column in enumerate(columns) for row, x in enumerate(column)]
        if max(origins) - min(origins) <= 2.0:
            return True
    return False


def closed_windows(states, lanes, minimum, maximum):
    """Enumerate closed consecutive windows, including a physically incomplete last row."""
    if len(states) < minimum:
        return
    order = sorted(states, key=lambda k: -states[k][0])
    for size in range(min(len(order), maximum), minimum-1, -1):
        for i in range(len(order) - size + 1):
            j = i + size
            if i and states[order[i-1]][0] == states[order[i]][0]:
                continue
            if j < len(order) and states[order[j-1]][0] == states[order[j]][0]:
                continue
            candidate = {key: states[key] for key in order[i:j]}
            if whole_shape(candidate, lanes):
                yield candidate


def sample(t, states):
    return {k: (t, lane_of(car[1])) for k, car in states.items()}


def population(snapshot, lanes):
    counts = Counter(lane for _, lane in snapshot.values())
    return [counts[i] for i in range(lanes)]


class Region:
    def __init__(self, lanes, members, motions):
        self.lanes, self.members = lanes, members
        self.motions = motions
        self.first = self.last = self.onset = None
        self.first_settled = self.last_settled = None
        self.episodes = []
        self.present_intervals = []
        self.was_together = False
        self.peak = self.peak_evidence = self.best = None
        self.max_present = 0
        self.last_centered = None

    def observe(self, t, states):
        self.max_present = max(self.max_present, len(states))
        together = bool(self.members) and states.keys() == self.members
        if together:
            if not self.was_together:
                self.present_intervals.append([t, t])
            self.present_intervals[-1][1] = t
        self.was_together = together
        if together and centered(states, self.lanes):
            self.last_centered = sample(t, states)
        full = together and len(states) >= 2 and whole_shape(states, self.lanes)
        if full:
            self.last = sample(t, states)
            if self.onset is None:
                self.episodes.append(dict(start=self.last, end=self.last, first_settled=None, last_settled=None))
            episode = self.episodes[-1]
            episode["end"] = self.last
            if self.first is None:
                self.first = self.last
            if all(abs(s[1] - (lane_of(s[1])+.5)*3.3) <= .05 and
                   not any(begin <= t < end for begin, end in self.motions[k])
                   for k, s in states.items()):
                self.last_settled = self.last
                if self.first_settled is None:
                    self.first_settled = self.last
                if episode["first_settled"] is None:
                    episode["first_settled"] = self.last
                episode["last_settled"] = self.last
            if self.onset is None:
                self.onset = t
            if self.best is None or t - self.onset > self.best[1] - self.best[0]:
                self.best = (self.onset, t)
        else:
            self.onset = None
        size = self.peak or 0
        candidate = states if full and len(states) > size else next(
            closed_windows(states, self.lanes, max(2, size+1), len(states)), None)
        if candidate:
            self.peak = len(candidate)
            self.peak_evidence = dict(time_s=t, ids=sorted(candidate),
                                      counts=population(sample(t, candidate), self.lanes))

    def report(self):
        intervals = []
        for ep in self.episodes:
            times = {key: next(iter(snap.values()))[0] if snap else None for key, snap in ep.items()}
            intervals.append(dict(start_s=times["start"], end_s=times["end"],
                hold_s=round(times["end"]-times["start"], 6), lane_counts=population(ep["start"], self.lanes),
                first_settled_s=times["first_settled"], last_settled_s=times["last_settled"]))
        together_s = round(sum(end-start for start, end in self.present_intervals), 6)
        whole_s = round(sum(ep["hold_s"] for ep in intervals), 6)
        return dict(max_present=self.max_present, all_present_intervals_s=self.present_intervals,
                    all_present_total_s=together_s, formed_pct_while_all_present=100*whole_s/together_s if together_s else None,
                    peak_size=self.peak or 0, peak=self.peak_evidence,
                    whole_hold_s=round(self.best[1]-self.best[0], 6) if self.best else 0.,
                    whole_hold_interval_s=self.best,
                    whole_episodes=intervals, whole_total_s=whole_s,
                    first_whole_s=next(iter(self.first.values()))[0] if self.first else None,
                    last_whole_s=next(iter(self.last.values()))[0] if self.last else None)


def possible_tail_bounds(counts, target_lanes):
    """Enumerate all balanced terminal populations in the observed lane coordinates."""
    n = sum(counts)
    q, r = divmod(n, target_lanes)
    source = [i for i, amount in enumerate(counts) for _ in range(amount)]
    choices = []
    for extra in combinations(range(target_lanes), r):
        target = [q + int(i in extra) for i in range(target_lanes)]
        slots = [i for i, amount in enumerate(target) for _ in range(amount)]
        hops = [abs(i-j) for i, j in zip(source, slots)]
        choices.append((max(hops), sum(hops), target))
    outer = [c for c in choices if target_lanes != 3 or c[2][1] <= min(c[2][0], c[2][2])]
    def summarize(candidates):
        best_max, best_total_given_max, _ = min(candidates)
        best_total = min(cost for _, cost, _ in candidates)
        return dict(min_total_crossings=best_total, min_max_crossings=best_max,
                    min_total_given_min_max=best_total_given_max,
                    min_total_targets=[t for _, cost, t in candidates if cost == best_total],
                    joint_lexicographic_targets=[t for worst, cost, t in candidates
                                                 if (worst, cost) == (best_max, best_total_given_max)])
    return dict(free_balanced_tail=summarize(choices), three_lane_outer_first=summarize(outer))


def moves(start, end, trips, width, target_lanes=None):
    if not start or not end or start.keys() != end.keys():
        return None
    a, b = population(start, width), population(end, width)
    cut_bounds = [abs(sum(a[:i]) - sum(b[:i])) for i in range(1, width)]
    ranked_a = sorted(lane for t, lane in start.values())
    ranked_b = sorted(lane for t, lane in end.values())
    per_id_net = sum(abs(start[k][1]-end[k][1]) for k in start)
    data = dict(start_time_range_s=[min(t for t, l in start.values()), max(t for t, l in start.values())],
                end_time_range_s=[min(t for t, l in end.values()), max(t for t, l in end.values())],
                start_counts=a, end_counts=b, min_total_crossings=sum(cut_bounds),
                min_max_crossings=max(abs(x-y) for x, y in zip(ranked_a, ranked_b)),
                per_cut_lower_bounds=cut_bounds, assigned_net_crossings=per_id_net)
    if target_lanes is not None:
        data.update(possible_tail_bounds(a, target_lanes))
    for field, label in (("lane_events", "midpoint"), ("lane_completion_events", "completed")):
        hops = Counter()
        mismatches = []
        for k, (t0, first_lane) in start.items():
            t1, last_lane = end[k]
            if t1 < t0:
                raise ValueError("Inverted observation interval")
            lane = first_lane
            valid = True
            for event in trips[k][field]:
                if t0 < event["time_s"] <= t1:
                    before, after = event["from_lane"], event["to_lane"]
                    valid &= before == lane and abs(before-after) == 1
                    hops[k] += abs(after-before)
                    lane = after
            if lane != last_lane or not valid:
                mismatches.append(k)
        data[label] = dict(total=sum(hops.values()), max_per_car=max(hops.values(), default=0),
                           vehicles_moving=sum(n > 0 for n in hops.values()),
                           vehicles_multiple=sum(n > 1 for n in hops.values()),
                           hops_by_id={k: hops[k] for k in sorted(start)}, mismatch_ids=sorted(mismatches),
                           excess_over_population_min=None if mismatches else sum(hops.values())-sum(cut_bounds))
    return data


def remaining_events(start, last_seen, trips):
    """Count late observations even when a vehicle exits before centering again."""
    if not start or start.keys() != last_seen.keys():
        return None
    data = {}
    for field, name in (("lane_events", "midpoint"), ("lane_completion_events", "completed")):
        by_id = {k: sum(abs(e["to_lane"]-e["from_lane"]) for e in trips[k][field]
                        if start[k][0] < e["time_s"] <= last_seen[k][0]) for k in start}
        data[name] = dict(total=sum(by_id.values()), max_per_car=max(by_id.values()),
                          moving_ids=sorted(k for k, count in by_id.items() if count))
    return data


def paired_peak(path, up, down, up_end, down_start, down_end):
    """Largest unchanged ID set qualifying on both sides, even for a partial success."""
    def evidence(a, b):
        return dict(size=len(a), ids=sorted(a), upstream_time_s=next(iter(a.values()))[0],
                    downstream_time_s=next(iter(b.values()))[0],
                    upstream_counts=population(a, up.lanes), downstream_counts=population(b, down.lanes))

    if up.last and down.first:
        return evidence(up.last, down.first)
    upper = min(up.peak or 0, down.peak or 0)
    best = dict(size=0, ids=[])
    upstream_snapshots = {}
    if upper < 2:
        return best
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            t, states = frame["time_s"], frame["states"]
            before = {k:s for k, s in states.items() if 0 <= s[0] < up_end}
            after = {k:s for k, s in states.items() if down_start <= s[0] < down_end}
            minimum = max(2, best["size"]+1)
            for group in closed_windows(before, up.lanes, minimum, upper):
                upstream_snapshots[frozenset(group)] = sample(t, group)
            for group in closed_windows(after, down.lanes, minimum, upper):
                snapshot = upstream_snapshots.get(frozenset(group))
                if snapshot:
                    best = evidence(snapshot, sample(t, group))
                    if best["size"] == upper:
                        return best
                    break
    return best


def flow_sample(states, lanes):
    """11.20 whole-second, two-or-more complete layers at fixed 30 m spacing."""
    # groups_at anchors its foremost car on the highest lane. The native
    # four-lane formation leads on even-numbered lanes; allow both on two lanes.
    views = [states] if lanes % 2 or lanes == 2 else []
    if lanes % 2 == 0:
        views.append({k: (s[0], lanes*3.3-s[1], *s[2:]) for k, s in states.items()})
    members = set()
    peak = 0
    for view in views:
        for group in groups_at(view, lanes):
            if group["layer_count"] >= 2:
                members.update(group["vehicle_ids"])
                peak = max(peak, group["size"])
    return len(members), peak


def measure(folder, cohort=False, preview=200.):
    folder = Path(folder)
    config = json.loads((folder / "input.json").read_bytes())
    result = json.loads((folder / "result.json").read_bytes())
    trip_rows = json.loads((folder / "trips.json").read_bytes())
    trips = {r["vehicle_id"]: r for r in trip_rows}
    arrivals = config["arrivals"]
    ids = {a["vehicle_id"] for a in arrivals}
    if len(ids) != len(arrivals) or ids != trips.keys() or len(ids) != result["requested"]:
        raise ValueError("Input demand IDs, trip IDs and requested count disagree")
    (up_lanes, cut), (dn_lanes, length) = road_layout(folder)
    if not 0 <= preview < cut:
        raise ValueError("Preview distance must be within the upstream edge")
    motions = {k: [(e["requested_s"], e["time_s"]) for e in tr["lane_completion_events"]]
               for k, tr in trips.items()} if cohort else {}
    regions = [Region(n, ids, motions) for n in (up_lanes, dn_lanes)]
    first_seen, entered_down = {}, {}
    last_seen, last_off_center = {}, set()
    off_center_entry = set()
    stats = [Counter(), Counter()]
    last_t = None
    dt = config["positions_step_s"]
    with gzip.open(folder / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            t, all_states = frame["time_s"], frame["states"]
            if last_t is not None and abs(t-last_t-dt) > 1e-6:
                raise ValueError(f"Missing or out-of-order sample at {t} s")
            last_t = t
            if not ids.issuperset(all_states):
                raise ValueError("Unknown ID in positions trace")
            up = {k: s for k, s in all_states.items() if 0 <= s[0] < cut-preview}
            down = {k: s for k, s in all_states.items() if cut <= s[0] < cut+length}
            for k, s in down.items():
                entered_down.setdefault(k, lane_of(s[1]))
            if cohort:
                for k, s in all_states.items():
                    last_seen[k] = (t, lane_of(s[1]))
                    if abs(s[1] - (lane_of(s[1])+.5)*3.3) <= .3:
                        last_off_center.discard(k)
                    else:
                        last_off_center.add(k)
                    if k not in first_seen:
                        first_seen.update(sample(t, {k:s}))
                        if not centered({k:s}, up_lanes):
                            off_center_entry.add(k)
            for reg, states, counter in zip(regions, (up, down), stats):
                if cohort:
                    reg.observe(t, states)
                if abs(t-round(t)) < 1e-6:
                    members, peak = flow_sample(states, reg.lanes)
                    counter["vehicle_samples"] += len(states)
                    counter["formed_vehicle_samples"] += members
                    counter["peak_multilayer_size"] = max(peak, counter["peak_multilayer_size"])
    traffic_keys = ("status", "completed", "requested", "departed", "pending_final", "onroad_final",
                    "collisions", "teleports", "safe", "mean_travel_time_s", "mean_system_time_s",
                    "mean_entry_wait_s", "exit_flow_veh_h", "fuel_g_per_km", "lane_changes",
                    "lane_change_completions", "performance_comparison_eligible")
    data = {k: result.get(k) for k in traffic_keys}
    data.update(scenario=result["scenario"], arrivals_sha256=hashlib.sha256(
        json.dumps(arrivals, sort_keys=True).encode()).hexdigest(), positions_step_s=dt,
        upstream_lanes=up_lanes, downstream_lanes=dn_lanes,
        upstream_interval_m=[0., cut-preview], downstream_interval_m=[cut, cut+length],
        downstream_first_observation_counts=[list(entered_down.values()).count(i) for i in range(dn_lanes)],
        downstream_first_observation_outside_lanes=sum(i not in range(dn_lanes) for i in entered_down.values()),
        missing_at_downstream=len(ids)-len(entered_down))
    for region, counter in zip(("upstream", "downstream"), stats):
        total, formed = counter["vehicle_samples"], counter["formed_vehicle_samples"]
        data[region+"_sampled_geometry"] = dict(vehicle_samples=total, formed_vehicle_samples=formed,
            peak_multilayer_size=counter["peak_multilayer_size"],
            formed_pct=100*formed/total if total else None)
    if cohort:
        up, down = regions
        width = max(up_lanes, dn_lanes)
        data.update(upstream=up.report(), downstream=down.report(),
                    paired_peak=paired_peak(folder / "positions.jsonl.gz", up, down, cut-preview, cut, cut+length),
                    missing_from_trajectory=sorted(ids-first_seen.keys()), off_center_entry=sorted(off_center_entry),
                    formation_moves=moves(first_seen, up.first, trips, width, up_lanes) if not off_center_entry else None,
                    transform_moves=moves(up.last, down.first, trips, width, dn_lanes),
                    settled_formation_moves=moves(first_seen, up.first_settled, trips, width, up_lanes)
                        if not off_center_entry else None,
                    settled_transform_moves=moves(up.last_settled, down.first_settled, trips, width, dn_lanes),
                    after_last_downstream_shape_events=remaining_events(down.last_settled, last_seen, trips),
                    after_last_downstream_shape_moves=moves(down.last_settled, last_seen, trips, width)
                        if not last_off_center else None, last_off_center_ids=sorted(last_off_center))
        if data["transform_moves"] is None:
            data["observed_population_moves"] = moves(up.last_centered, down.last_centered, trips, width)
        for name, reg, start in (("upstream", up, first_seen if not off_center_entry else None),
                                 ("downstream", down, up.last_settled)):
            for output, episode in zip(data[name]["whole_episodes"], reg.episodes):
                output["moves_to_first_settled_s"] = moves(start, episode["first_settled"], trips, width, reg.lanes)
                output["moves_while_settled_endpoints"] = moves(episode["first_settled"],
                                                                 episode["last_settled"], trips, width)
    data["transport_certificates"] = result.get("transport_certificates")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--cohort", action="store_true", help="Fixed batch, all requested IDs")
    parser.add_argument("--preview", type=float, default=200., help="Exclude approach from upstream geometry (m)")
    args = parser.parse_args()
    print(json.dumps(measure(args.folder, args.cohort, args.preview), indent=2))
