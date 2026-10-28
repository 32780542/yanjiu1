"""Physical complete layers; no controller labels or desired positions are read.

Groups include single layers, ordered front to rear, with IDs ordered highest lane
downwards. All legal closed consecutive blocks are considered; take the largest,
then the frontmost on equal length, and repeat on unoccupied rows. Only >=2 full
layers enter the main time measures; participation uses this disjoint selection. Geometry
RMS uses cross-lane phase and adjacent same-lane spacing residuals; speed RMS uses
deviation from each group's mean. Exposure uses left-held samples until the next
timestamp, with confirmation thresholds integrated inside each interval; these are
sample-based estimates, not proof of validity between samples (1s records can alias
short breaks). The last sample has no extrapolated exposure. Use separate (0,640)/(1000,1200) calls for the
3-lane upstream and 2-lane downstream, avoiding planned transformation comparisons.
"""

import gzip
import json
import math


def _pack(rows, states, lanes, gap):
    ids = tuple(v for row in rows for v in row)
    errors = [
        states[row[i]][0] - states[row[j]][0] - gap / 2 * (j % 2 - i % 2)
        for row in rows
        for i in range(lanes)
        for j in range(i + 1, lanes)
    ]
    errors += [
        states[a][0] - states[b][0] - gap for front, rear in zip(rows, rows[1:]) for a, b in zip(front, rear)
    ]
    speeds = [states[v][2] for v in ids]
    mean = sum(speeds) / len(speeds)
    return dict(
        layers=tuple(rows),
        vehicle_ids=ids,
        layer_count=len(rows),
        size=len(ids),
        x_range_m=(min(states[v][0] for v in ids), max(states[v][0] for v in ids)),
        geometry_rms_m=math.sqrt(sum(e * e for e in errors) / len(errors)),
        speed_rms_mps=math.sqrt(sum((v - mean) ** 2 for v in speeds) / len(speeds)),
    )


def groups_at(
    states, lane_count, *, gap=30.0, position_tolerance=2.0, speed_tolerance=0.5, center_tolerance=0.3
):
    """Return disjoint largest-first closed blocks, including separate single rows.

    A block's actual longitudinal envelope must contain exactly its member cars.
    Thus an unfinished tail outside it is allowed; an extra/crossing car inside is
    never discarded by selecting a subset. A missing 30m row splits the block.
    Enumerate every legal consecutive block, select longest/frontmost first, then
    repeat on the remaining rows; return the selected blocks in spatial order.
    """
    if lane_count < 2 or gap <= 0:
        raise ValueError("Require at least two lanes and a positive layer spacing")
    lanes = [
        [v for v, s in states.items() if abs(s[1] - (lane + 0.5) * 3.3) <= center_tolerance + 1e-9]
        for lane in reversed(range(lane_count))
    ]

    def closed(ids):
        low, high = min(states[v][0] for v in ids), max(states[v][0] for v in ids)
        return {v for v, s in states.items() if low <= s[0] <= high} == set(ids)

    def same_speed(ids):
        speeds = [states[v][2] for v in ids]
        return max(speeds) - min(speeds) <= speed_tolerance + 1e-9

    rows = []
    for anchor in lanes[0]:
        matches = [
            [
                v
                for v in lane
                if abs(states[v][0] - states[anchor][0] + gap / 2 * (i % 2)) <= position_tolerance + 1e-9
            ]
            for i, lane in enumerate(lanes)
        ]
        if all(len(match) == 1 for match in matches):
            row = tuple(match[0] for match in matches)
            phase = [states[v][0] + gap / 2 * (i % 2) for i, v in enumerate(row)]
            if max(phase) - min(phase) <= position_tolerance + 1e-9 and closed(row) and same_speed(row):
                rows.append(row)
    rows.sort(key=lambda row: states[row[0]][0], reverse=True)
    candidates = []
    for start in range(len(rows)):
        block, ids = [], ()
        for row in rows[start:]:
            joins = not block or all(
                abs(states[a][0] - states[b][0] - gap) <= position_tolerance + 1e-9
                for a, b in zip(block[-1], row)
            )
            if not joins or set(ids).intersection(row) or not closed(ids + row) or not same_speed(ids + row):
                break
            block.append(row)
            ids += row
            candidates.append(tuple(block))
    groups, used = [], set()
    for block in sorted(candidates, key=lambda b: (-len(b), -states[b[0][0]][0])):
        ids = {v for row in block for v in row}
        if not used.intersection(ids):
            groups.append(_pack(block, states, lane_count, gap))
            used.update(ids)
    return sorted(groups, key=lambda g: states[g["layers"][0][0]][0], reverse=True)


def _relations(groups):
    relations = {}
    for group in groups:
        rows = group["layers"]
        relations.update({("row", row): row for row in rows})
        relations.update({("edge", a, b): a + b for a, b in zip(rows, rows[1:])})
    return relations


def _mature(groups, born, time_s, hold, states, lanes, gap):
    mature = lambda key: time_s + 1e-9 >= born[key] + hold
    for group in groups:
        block = []
        for row in group["layers"]:
            valid = mature(("row", row))
            if block and (not valid or not mature(("edge", block[-1], row))):
                if len(block) >= 2:
                    yield _pack(block, states, lanes, gap)
                block = []
            if valid:
                block.append(row)
        if len(block) >= 2:
            yield _pack(block, states, lanes, gap)


def evaluate_layers(
    path,
    lane_count,
    region=(0.0, 1200.0),
    *,
    confirm_s=1.0,
    stable_s=5.0,
    gap=30.0,
    position_tolerance=2.0,
    speed_tolerance=0.5,
    center_tolerance=0.3,
):
    """Evaluate gzip JSONL {time_s, states: {id: [x,y,v,a]}} in [low,high).

    Formation and stability ages attach to physical within-row/adjacent-row
    relationships, so a new tail does not reset a formed prefix. Break counts
    concern relations that have participated in confirmed multi-layer exposure.
    A disappearance at a spatial boundary is censored; missing IDs are censored
    only if last x+v*dt reaches that boundary. Remaining relations are censored at
    recording end. Counts are relations, not vehicles or whole-group episodes.
    """
    if region[0] >= region[1] or not 0 <= confirm_s <= stable_s:
        raise ValueError("Require ordered region and 0 <= confirm_s <= stable_s")
    result = dict(
        observation_seconds=0.0,
        vehicle_seconds=0.0,
        formed_vehicle_seconds=0.0,
        multilayer_group_seconds=0.0,
        raw_single_layer_vehicle_seconds=0.0,
        stable_vehicle_seconds=0.0,
        stable_multilayer_group_seconds=0.0,
        raw_unassigned_vehicle_seconds=0.0,
        internal_relation_breaks=0,
        boundary_censored_relations=0,
        end_censored_relations=0,
    )
    born, eligible, previous = {}, set(), None
    geometry = speed = 0.0
    peak = None
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            time_s, all_states = float(frame["time_s"]), frame["states"]
            states = {v: s for v, s in all_states.items() if region[0] <= s[0] < region[1]}
            groups = groups_at(
                states,
                lane_count,
                gap=gap,
                position_tolerance=position_tolerance,
                speed_tolerance=speed_tolerance,
                center_tolerance=center_tolerance,
            )
            relations = _relations(groups)
            if previous is not None:
                start, old_states, old_groups, old_relations = previous
                if time_s <= start:
                    raise ValueError("Position timestamps must strictly increase")
                dt = time_s - start
                result["observation_seconds"] += dt
                result["vehicle_seconds"] += len(old_states) * dt
                result["raw_single_layer_vehicle_seconds"] += (
                    sum(g["size"] for g in old_groups if g["layer_count"] == 1) * dt
                )
                result["raw_unassigned_vehicle_seconds"] += (
                    len(old_states) - sum(g["size"] for g in old_groups)
                ) * dt
                cuts = sorted(
                    {start, time_s}
                    | {b + h for b in born.values() for h in (confirm_s, stable_s) if start < b + h < time_s}
                )
                for left, right in zip(cuts, cuts[1:]):
                    weight = right - left
                    formed = list(
                        _mature(old_groups, born, (left + right) / 2, confirm_s, old_states, lane_count, gap)
                    )
                    for group in formed:
                        exposure = group["size"] * weight
                        result["formed_vehicle_seconds"] += exposure
                        result["multilayer_group_seconds"] += weight
                        geometry += group["geometry_rms_m"] ** 2 * exposure
                        speed += group["speed_rms_mps"] ** 2 * exposure
                        peak = max(peak or 0, group["size"])
                    eligible.update(_relations(formed))
                    for group in _mature(
                        old_groups, born, (left + right) / 2, stable_s, old_states, lane_count, gap
                    ):
                        result["stable_vehicle_seconds"] += group["size"] * weight
                        result["stable_multilayer_group_seconds"] += weight
                for key in (old_relations.keys() - relations.keys()) & eligible:

                    def outside(v):
                        x = (
                            all_states[v][0]
                            if v in all_states
                            else (old_states[v][0] + old_states[v][2] * dt)
                        )
                        return not region[0] <= x < region[1]

                    field = (
                        "boundary_censored_relations"
                        if any(outside(v) for v in old_relations[key])
                        else "internal_relation_breaks"
                    )
                    result[field] += 1
                eligible.intersection_update(relations)
            born = {key: born.get(key, time_s) for key in relations}
            previous = time_s, states, groups, relations
    formed_s, vehicle_s = result["formed_vehicle_seconds"], result["vehicle_seconds"]
    result.update(
        mean_multilayer_size=(
            formed_s / result["multilayer_group_seconds"] if result["multilayer_group_seconds"] else None
        ),
        peak_multilayer_size=peak,
        formation_participation_rate=formed_s / vehicle_s if vehicle_s else None,
        stable_participation_rate=result["stable_vehicle_seconds"] / vehicle_s if vehicle_s else None,
        geometry_rms_m=math.sqrt(geometry / formed_s) if formed_s else None,
        speed_rms_mps=math.sqrt(speed / formed_s) if formed_s else None,
        end_censored_relations=len(born.keys() & eligible),
        confirmation_seconds=confirm_s,
        stability_hold_seconds=stable_s,
        region_m=tuple(region),
        lane_count=lane_count,
    )
    result["internal_breaks_per_100_formed_vehicle_s"] = (
        100 * result["internal_relation_breaks"] / formed_s if formed_s else None
    )
    return result
