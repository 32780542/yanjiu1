"""Independent physical platoon metrics for open-road position JSONL records.

Only ``time_s`` and ``states: {key: [x, y, v, a]}`` are read. Vehicle keys
track physical relationships offline; no controller roles or targets are used.
All rates are fractions, not percentages. Empty denominators produce ``None``.
"""
from bisect import bisect_left
from collections import defaultdict
import gzip
import json
import math


_EPS = 1e-9
PLATOON_METRICS = ('mean_platoon_size','max_platoon_size','participation_rate',
    'geometry_rms_m','speed_rms_mps','stable_participation_rate',
    'internal_breaks_per_100_platoon_vehicle_s')


def _frames(path, road_length):
    previous_time = None
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            frame = json.loads(line)
            time_s = float(frame["time_s"])
            if not math.isfinite(time_s) or (previous_time is not None and time_s <= previous_time):
                raise ValueError(f"Frame {line_number}: timestamps must be finite and strictly increasing")
            states = frame["states"]
            if not isinstance(states, dict):
                raise ValueError(f"Frame {line_number}: states must be a mapping")
            onroad = {}
            for key, values in states.items():
                if not isinstance(values, (list, tuple)) or len(values) != 4:
                    raise ValueError(f"Frame {line_number}: each state must contain [x,y,v,a]")
                values = tuple(float(value) for value in values)
                if not all(math.isfinite(value) for value in values):
                    raise ValueError(f"Frame {line_number}: state values must be finite")
                if 0. <= values[0] < road_length:
                    onroad[key] = values
            yield time_s, onroad
            previous_time = time_s


def _physical_graph(states, lane_count, gap, offset, lane_width,
                    position_tolerance, speed_tolerance, lane_center_tolerance):
    lanes = defaultdict(list)
    for key, (x, y, speed, _) in states.items():
        lane = math.floor(y / lane_width)
        if (0 <= lane < lane_count and
                abs(y - (lane + .5) * lane_width) <= lane_center_tolerance + _EPS):
            phase = offset if (lane_count - 1 - lane) % 2 else 0.
            lanes[lane].append((x + phase, x, key, speed))
    for rows in lanes.values():
        rows.sort()
    edges = {}

    def add_edge(left, right, geometric_error):
        if abs(left[3] - right[3]) <= speed_tolerance + _EPS:
            edges[tuple(sorted((left[2], right[2])))] = geometric_error

    for rows in lanes.values():
        for left, right in zip(rows, rows[1:]):
            error = abs(right[1] - left[1] - gap)
            if error <= position_tolerance + _EPS:
                add_edge(left, right, error)

    # Cross-lane edges align the same layer. Only actual same-lane spacing
    # links successive layers; diagonals cannot bridge a missing 30m layer.
    for source_lane, source_rows in lanes.items():
        for target_lane, target_rows in lanes.items():
            if source_lane == target_lane:
                continue
            coordinates = [row[0] for row in target_rows]
            for source in source_rows:
                index = bisect_left(coordinates,source[0])
                candidates = target_rows[max(0,index-1):index+1]
                nearest = min(candidates,key=lambda row:(abs(row[0]-source[0]),abs(row[1]-source[1]),row[2]))
                error = abs(nearest[0]-source[0])
                if error <= position_tolerance+_EPS:
                    add_edge(source,nearest,error)

    neighbors = defaultdict(set)
    for left, right in edges:
        neighbors[left].add(right)
        neighbors[right].add(left)
    groups = []
    remaining = set(neighbors)
    while remaining:
        todo = [min(remaining)]
        group = set()
        while todo:
            key = todo.pop()
            if key not in group:
                group.add(key)
                todo.extend(neighbors[key] - group)
        remaining -= group
        groups.append(group)
    return edges, groups


def evaluate_platoons(path, lane_count, gap, offset=15., *, lane_width=3.3,
                      position_tolerance=2., speed_tolerance=.5,
                      lane_center_tolerance=.3, stable_duration_s=5.,
                      road_length=1200., max_sample_gap_s=1.01):
    """Measure disjoint physical components with at least two vehicles.

    For adjacent accepted timestamps, the preceding observed state is held
    over their interval. The final frame has no invented tail duration.
    Stable endpoint exposure starts only after its same edge has lasted
    ``stable_duration_s``; overlapping supporting edges never double count a
    vehicle. Gaps longer than ``max_sample_gap_s`` have no exposure and reset
    continuity. Disappearing/unobserved endpoints and the recording end are
    censored. An edge lost while both endpoints remain on road is a break.

    Geometry RMS is edge-time weighted relative-position error. Speed RMS is
    vehicle-time weighted deviation from each component's mean speed.
    """
    if isinstance(lane_count, bool) or not isinstance(lane_count, int) or lane_count < 1:
        raise ValueError("lane_count must be a positive integer")
    parameters = dict(gap_m=gap, offset_m=offset, lane_width_m=lane_width,
                      position_tolerance_m=position_tolerance, speed_tolerance_mps=speed_tolerance,
                      lane_center_tolerance_m=lane_center_tolerance,
                      stable_duration_s=stable_duration_s, road_length_m=road_length,
                      max_sample_gap_s=max_sample_gap_s)
    if not all(math.isfinite(value) for value in parameters.values()):
        raise ValueError("All parameters must be finite")
    if any(value <= 0. for value in (gap, lane_width, stable_duration_s, road_length, max_sample_gap_s)):
        raise ValueError("Gap, dimensions, duration and sample limit must be positive")
    if any(value < 0. for value in (offset, position_tolerance, speed_tolerance, lane_center_tolerance)):
        raise ValueError("Offsets and tolerances must be nonnegative")
    if offset >= gap:
        raise ValueError("offset must be smaller than the same-lane gap")

    vehicle_seconds = platoon_vehicle_seconds = platoon_seconds = stable_vehicle_seconds = 0.
    edge_seconds = geometry_squared = speed_squared = observed_duration_s = 0.
    frame_count = internal_breaks = censored_edges = sampling_gap_count = 0
    max_platoon_size = None
    previous = None
    starts = {}
    first_time = last_time = None

    for time_s, states in _frames(path, road_length):
        frame_count += 1
        first_time = time_s if first_time is None else first_time
        last_time = time_s
        edges, groups = _physical_graph(states, lane_count, gap, offset, lane_width,
                                        position_tolerance, speed_tolerance, lane_center_tolerance)
        if groups:
            current_max = max(map(len, groups))
            max_platoon_size = current_max if max_platoon_size is None else max(max_platoon_size, current_max)
        if previous is not None:
            prev_time, prev_states, prev_edges, prev_groups = previous
            dt = time_s - prev_time
            if dt > max_sample_gap_s + _EPS:
                sampling_gap_count += 1
                censored_edges += len(prev_edges)
                starts = {}
            else:
                observed_duration_s += dt
                vehicle_seconds += len(prev_states) * dt
                count = sum(map(len, prev_groups))
                platoon_vehicle_seconds += count * dt
                platoon_seconds += len(prev_groups) * dt
                edge_seconds += len(prev_edges) * dt
                geometry_squared += sum(error * error for error in prev_edges.values()) * dt
                for group in prev_groups:
                    mean_speed = sum(prev_states[key][2] for key in group) / len(group)
                    speed_squared += sum((prev_states[key][2] - mean_speed) ** 2 for key in group) * dt

                # Every vehicle contributes at most dt, even when several
                # supporting edges mature at different times in this interval.
                stable_from = {}
                for edge in prev_edges:
                    confirmation = max(prev_time, starts[edge] + stable_duration_s)
                    if confirmation < time_s:
                        for key in edge:
                            stable_from[key] = min(stable_from.get(key, time_s), confirmation)
                stable_vehicle_seconds += sum(time_s - start for start in stable_from.values())

                for edge in prev_edges.keys() - edges.keys():
                    if all(key in states for key in edge):
                        internal_breaks += 1
                    else:
                        censored_edges += 1
                starts = {edge: start for edge, start in starts.items() if edge in edges}
        for edge in edges:
            starts.setdefault(edge, time_s)
        previous = time_s, states, edges, groups

    if previous is not None:
        censored_edges += len(previous[2])
    return dict(
        mean_platoon_size=platoon_vehicle_seconds / platoon_seconds if platoon_seconds else None,
        max_platoon_size=max_platoon_size,
        participation_rate=platoon_vehicle_seconds / vehicle_seconds if vehicle_seconds else None,
        geometry_rms_m=math.sqrt(geometry_squared / edge_seconds) if edge_seconds else None,
        speed_rms_mps=math.sqrt(speed_squared / platoon_vehicle_seconds) if platoon_vehicle_seconds else None,
        stable_participation_rate=stable_vehicle_seconds / vehicle_seconds if vehicle_seconds else None,
        internal_breaks_per_100_platoon_vehicle_s=(100. * internal_breaks / platoon_vehicle_seconds
                                                 if platoon_vehicle_seconds else None),
        vehicle_seconds=vehicle_seconds, platoon_vehicle_seconds=platoon_vehicle_seconds,
        platoon_seconds=platoon_seconds, stable_vehicle_seconds=stable_vehicle_seconds,
        edge_seconds=edge_seconds, internal_breaks=internal_breaks, censored_edges=censored_edges,
        frame_count=frame_count, observed_duration_s=observed_duration_s,
        sampling_gap_count=sampling_gap_count, first_time_s=first_time, last_time_s=last_time,
        parameters={"lane_count": lane_count, **parameters},
    )
