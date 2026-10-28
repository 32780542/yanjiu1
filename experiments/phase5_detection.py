"""Independent, read-only detection of staggered structures in recorded frames.

No controller imports this module. Vehicle keys identify persistent members only;
the detector neither reads type/plan/slot labels nor sends its phase fit online.
"""
from collections import Counter
from itertools import combinations
import math


_EPS = 1e-8


def _components(keys, edges):
    neighbors = {key: set() for key in keys}
    for left, right in edges:
        neighbors[left].add(right)
        neighbors[right].add(left)
    remaining = set(keys)
    result = []
    while remaining:
        todo = [min(remaining)]
        component = set()
        while todo:
            key = todo.pop()
            if key in component:
                continue
            component.add(key)
            todo.extend(neighbors[key] - component)
        remaining -= component
        result.append(frozenset(component))
    return result


def _phase_fit(rows, d):
    period = 2 * d
    residues = sorted((row['x'] - row['lane'] * d) % period for row in rows)
    gaps = [(residues[(i + 1) % len(residues)] - value) % period
            for i, value in enumerate(residues)]
    if len(residues) == 1 or max(residues) - min(residues) < _EPS:
        phase = residues[0]
    else:
        cut = max(range(len(gaps)), key=lambda i: (gaps[i], -i))
        start = residues[(cut + 1) % len(residues)]
        width = period - gaps[cut]
        phase = (start + width / 2) % period
    errors, slots = {}, {}
    for row in rows:
        k = round((row['x'] - row['lane'] * d - phase) / period)
        slots[row['key']] = (row['lane'], row['lane'] + 2 * k)
        errors[row['key']] = abs(row['x'] - (phase + (row['lane'] + 2 * k) * d))
    return phase, errors, slots


def _slot_edges(slots):
    return [(left, right) for left, right in combinations(slots, 2)
            if ((slots[left][0] == slots[right][0] and
                 abs(slots[left][1] - slots[right][1]) == 2) or
                (abs(slots[left][0] - slots[right][0]) == 1 and
                 abs(slots[left][1] - slots[right][1]) == 1))]


def _measure(keys, vehicles, d, position_tolerance, speed_tolerance):
    rows = [vehicles[key] for key in sorted(keys) if key in vehicles]
    reasons = []
    if len(rows) != len(keys):
        reasons.append('member_missing')
    if len(rows) < 3:
        reasons.append('fewer_than_three_vehicles')
    if not rows:
        return None, reasons
    lanes = sorted({row['lane'] for row in rows})
    if not any(right - left == 1 for left, right in zip(lanes, lanes[1:])):
        reasons.append('no_two_adjacent_lanes')
    speed_spread = max(row['speed'] for row in rows) - min(row['speed'] for row in rows)
    if speed_spread > speed_tolerance + _EPS:
        reasons.append('speed_spread_exceeded')
    phase, errors, slots = _phase_fit(rows, d)
    if max(errors.values()) > position_tolerance + _EPS:
        reasons.append('lattice_error_exceeded')
    if len(set(slots.values())) != len(slots):
        reasons.append('duplicate_occupied_slot')
    edges = _slot_edges(slots)
    if len(_components(slots, edges)) != 1:
        reasons.append('disconnected_occupied_slots')
    min_q = min(slot[1] for slot in slots.values())
    max_q = max(slot[1] for slot in slots.values())
    # All parity-compatible sites in the group's fitted longitudinal and lane
    # envelope form the denominator. Missing entire lanes remain visible here.
    possible = {(lane, q): (lane, q)
                for lane in range(min(lanes), max(lanes) + 1)
                for q in range(min_q, max_q + 1) if (q - lane) % 2 == 0}
    possible_edges = _slot_edges(possible)
    span = max(row['front_x'] for row in rows) - min(row['rear_x'] for row in rows)
    pair_error = max((abs(abs(vehicles[left]['x'] - vehicles[right]['x']) -
                          (2 * d if slots[left][0] == slots[right][0] else d))
                      for left, right in edges), default=0.)
    result = {
        'members': sorted(keys), 'vehicle_count': len(rows), 'lanes': lanes,
        'phase_m': phase, 'max_lattice_error_m': max(errors.values()),
        'speed_spread_mps': speed_spread, 'occupied_slots': len(set(slots.values())),
        'possible_slots': len(possible),
        'slot_occupancy_fraction': len(set(slots.values())) / len(possible),
        'occupancy_edges_numerator': len(edges),
        'occupancy_edges_denominator': len(possible_edges),
        'adjacency_occupancy_completeness': len(edges) / len(possible_edges) if possible_edges else 0.,
        'road_span_m': span,
        'center_span_m': max(row['x'] for row in rows) - min(row['x'] for row in rows),
        'max_adjacent_spacing_error_m': pair_error,
    }
    return result, reasons


def _candidates(vehicles, d, position_tolerance, speed_tolerance):
    """Enumerate O(N^2) phase/speed windows, then connected occupied sites."""
    period = 2 * d
    residue = {key: (row['x'] - row['lane'] * d) % period for key, row in vehicles.items()}
    proposed = set()
    for start in sorted(set(residue.values())):
        phase_keys = [key for key, value in residue.items()
                      if (value - start) % period <= 2 * position_tolerance + _EPS]
        for min_speed in sorted({vehicles[key]['speed'] for key in phase_keys}):
            speed_keys = [key for key in phase_keys
                          if min_speed - _EPS <= vehicles[key]['speed'] <= min_speed + speed_tolerance + _EPS]
            if len(speed_keys) < 3:
                continue
            _, _, slots = _phase_fit([vehicles[key] for key in speed_keys], d)
            counts = Counter(slots.values())
            # Ambiguous duplicate slots cannot be used to inflate a group.
            slots = {key: slot for key, slot in slots.items() if counts[slot] == 1}
            for component in _components(slots, _slot_edges(slots)):
                if len(component) >= 3:
                    proposed.add(component)
    valid = set()
    for keys in proposed:
        _, reasons = _measure(keys, vehicles, d, position_tolerance, speed_tolerance)
        if not reasons:
            valid.add(keys)
    # Retain maximal current components; existing subsets are independently
    # revalidated by detect_frames, preserving their actual member duration.
    return {keys for keys in valid if not any(keys < other for other in valid)}


def detect_frames(frames, d=15.0, lane_width=3.3, position_tolerance=2.0,
                  speed_tolerance=1.0, persistence_s=5.0,
                  formation_deadline_s=30.0, hold_s=10.0):
    """Return sampled geometry, persistent member intervals, and strict success.

    Confirm formation after persistence_s of continuously valid sampled geometry.
    Strict success requires the complete recorded cohort confirmed by 30 seconds
    from recording start, then held another 10 seconds. See phase5_detector.md.
    """
    parameters = {'d_m': d, 'lane_width_m': lane_width,
                  'position_tolerance_m': position_tolerance,
                  'speed_tolerance_mps': speed_tolerance,
                  'persistence_s': persistence_s, 'formation_deadline_s': formation_deadline_s,
                  'hold_after_confirmation_s': hold_s,
                  'max_sample_gap_s': .1, 'body_length_m': 4., 'body_width_m': 1.8}
    if not all(math.isfinite(value) and value > 0 for value in parameters.values()):
        raise ValueError('Detector parameters must be positive and finite')
    if position_tolerance >= d / 2:
        raise ValueError('Position tolerance must be smaller than d/2 for an unambiguous lattice')
    frames = list(frames)
    times = [float(frame['time_s']) for frame in frames]
    if not all(math.isfinite(time) for time in times):
        raise ValueError('Frame times must be finite')
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError('Frame times must be strictly increasing')
    sample_step = min((round(right - left, 10) for left, right in zip(times, times[1:])), default=.1)
    parameters['max_sample_gap_s'] = min(.1, sample_step)
    cohort = sorted({key for frame in frames for key in frame['states']})
    active, candidates, measured_frames = {}, [], []
    gaps = 0

    def close(keys, reason):
        item = active.pop(keys)
        item['end_reason'] = reason
        item['duration_s'] = round(item['end_time_s'] - item['start_time_s'], 10)
        item['formation_confirmed'] = item['duration_s'] + _EPS >= persistence_s
        item['formed_time_s'] = round(item['start_time_s'] + persistence_s, 10) if item['formation_confirmed'] else None
        item['held_time_s'] = (round(item['formed_time_s'] + hold_s, 10)
                               if item['formation_confirmed'] and item['duration_s'] + _EPS >= persistence_s + hold_s else None)
        item['formation_by_deadline'] = bool(item['formation_confirmed'] and
            item['formed_time_s'] <= times[0] + formation_deadline_s + _EPS)
        item['geometric_hold_10s_from_start'] = item['duration_s'] + _EPS >= hold_s
        item['whole_cohort'] = item['members'] == cohort
        item['success'] = item['formation_by_deadline'] and item['held_time_s'] is not None
        item['failure_reasons'] = []
        if not item['formation_confirmed']:
            item['failure_reasons'].append('persistence_too_short')
        elif not item['formation_by_deadline']:
            item['failure_reasons'].append('formation_deadline_missed')
        if item['formation_confirmed'] and item['held_time_s'] is None:
            item['failure_reasons'].append('hold_after_confirmation_too_short')
        candidates.append(item)

    previous_time = None
    for time, frame in zip(times, frames):
        if previous_time is not None and time - previous_time > parameters['max_sample_gap_s'] + _EPS:
            gaps += 1
            for keys in list(active):
                close(keys, 'sample_gap')
        vehicles = {}
        for key, state in frame['states'].items():
            x, y, vx = (float(state[name]) for name in ('x_m', 'y_m', 'vx_mps'))
            vy, heading = float(state.get('vy_mps', 0.)), float(state.get('heading_rad', 0.))
            if not all(math.isfinite(value) for value in (x, y, vx, vy, heading)):
                raise ValueError('Vehicle geometry and velocity must be finite')
            half_span = 2 * abs(math.cos(heading)) + .9 * abs(math.sin(heading))
            vehicles[key] = {'key': key, 'x': x, 'lane': math.floor(y / lane_width),
                             'speed': math.hypot(vx, vy), 'front_x': x + half_span,
                             'rear_x': x - half_span}
        proposed = _candidates(vehicles, d, position_tolerance, speed_tolerance) | set(active)
        groups = []
        for keys in sorted(proposed, key=lambda keys: (-len(keys), sorted(keys))):
            measurement, reasons = _measure(keys, vehicles, d, position_tolerance, speed_tolerance)
            if reasons:
                if keys in active:
                    close(keys, 'geometry_or_membership_lost')
                continue
            groups.append(measurement)
            if keys not in active:
                active[keys] = {'members': sorted(keys), 'start_time_s': time, 'end_time_s': time,
                                'max_lattice_error_m': 0., 'max_speed_spread_mps': 0.,
                                'min_adjacency_occupancy_completeness': 1., 'max_road_span_m': 0.}
            item = active[keys]
            item['end_time_s'] = time
            item['max_lattice_error_m'] = max(item['max_lattice_error_m'], measurement['max_lattice_error_m'])
            item['max_speed_spread_mps'] = max(item['max_speed_spread_mps'], measurement['speed_spread_mps'])
            item['min_adjacency_occupancy_completeness'] = min(item['min_adjacency_occupancy_completeness'],
                                                             measurement['adjacency_occupancy_completeness'])
            item['max_road_span_m'] = max(item['max_road_span_m'], measurement['road_span_m'])
        _, fleet_reasons = _measure(frozenset(cohort), vehicles, d, position_tolerance, speed_tolerance)
        covered = {key for group in groups for key in group['members']}
        measured_frames.append({'time_s': time, 'groups': groups,
            'fleet_coverage_fraction': len(covered) / len(cohort) if cohort else 0.,
            'largest_group_fraction': max((len(group['members']) / len(cohort) for group in groups), default=0.),
            'fleet_failure_reasons': fleet_reasons,
            'fleet_road_span_m': (max(row['front_x'] for row in vehicles.values()) -
                                  min(row['rear_x'] for row in vehicles.values())) if vehicles else 0.})
        previous_time = time
    for keys in list(active):
        close(keys, 'recording_end')
    candidates.sort(key=lambda item: (item['start_time_s'], -len(item['members']), item['members']))
    intervals = [item for item in candidates if item['formation_confirmed']]
    local_success = any(item['success'] for item in intervals)
    success = any(item['success'] and item['whole_cohort'] for item in intervals)
    reasons = []
    if not frames:
        reasons.append('empty_recording')
    elif not intervals:
        reasons.append('no_persistent_local_group')
    elif not local_success:
        reasons.append('no_local_group_met_deadline_and_hold')
    if frames and not success:
        reasons.append('whole_cohort_milestone_not_met')
    return {'schema_version': 1, 'offline_only': True, 'parameters': parameters,
            'cohort_members': cohort, 'cohort_size': len(cohort), 'frame_count': len(frames),
            'sampling_gap_count': gaps, 'success': success, 'whole_cohort_success': success,
            'local_success': local_success, 'failure_reasons': reasons,
            'intervals': intervals, 'candidate_intervals': candidates, 'frames': measured_frames}
