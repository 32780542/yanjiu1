"""Measure speed exposure, delay, and discharge in paired frozen speed-cap trials."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import itertools
import json
from functools import partial
from pathlib import Path
from statistics import mean

from run_current_speedcap import CAP, FLOWS, KEYS, MODES, REFERENCE, SCENARIOS, SEEDS, fixed_geometry, verify
from run_shared_physics import ROOT, digest, read_json, write_json


def trajectory_metrics(path, end_s):
    above = road_n = road_fast = near_n = near_fast = near_slow = 0
    road_sum = near_sum = 0.0
    samples = frames = 0
    max_speed = 0.0
    previous = {}
    crossings = set()
    saw_fast = set()
    peak_queue = 0
    first_queue = None
    sustained_ticks = 0
    with gzip.open(path, 'rt', encoding='utf-8') as trace:
        for line in trace:
            frame = json.loads(line)
            now = frame['time_s']
            frames += 1
            assert abs(now - frames * .1) < 1e-8
            queue = 0
            samples += len(frame['states'])
            for vid, (x, _y, speed, _a) in frame['states'].items():
                max_speed = max(max_speed, speed)
                fast = speed > CAP + 1e-9
                if fast:
                    above += 1
                    saw_fast.add(vid)
                if not 99.9 <= now <= 600.1:
                    continue
                prior = previous.get(vid)
                previous[vid] = (now, x)
                if prior is not None:
                    t0, x0 = prior
                    if now - t0 <= .1000001 and x0 < 1000 <= x:
                        crossing_t = t0 + (1000 - x0) * (now - t0) / (x - x0)
                        if 100 <= crossing_t < 600:
                            crossings.add(vid)
                if not 100 <= now < 600:
                    continue
                road_n += 1
                road_sum += speed
                road_fast += fast
                if 800 <= x < 1000:
                    near_n += 1
                    near_sum += speed
                    near_fast += fast
                    if speed < 5:
                        near_slow += 1
                        queue += 1
            if 100 <= now < 600:
                peak_queue = max(peak_queue, queue)
                sustained_ticks = sustained_ticks + 1 if queue >= 3 else 0
                if first_queue is None and sustained_ticks >= 30:
                    first_queue = round(now - 2.9, 1)

    assert abs(frames * .1 - end_s) < 1e-8 and samples > 0
    return dict(
        trajectory_samples=samples,
        actual_peak_speed_mps=max_speed,
        ever_above_cruise_vehicle_n=len(saw_fast),
        all_above_cruise_vehicle_s=above * .1,
        road_above_cruise_fraction=road_fast / road_n,
        road_mean_speed_mps=road_sum / road_n,
        bottleneck_above_cruise_fraction=near_fast / near_n,
        bottleneck_mean_speed_mps=near_sum / near_n,
        bottleneck_low_speed_vehicle_s=near_slow * .1,
        peak_low_speed_vehicles=peak_queue,
        first_sustained_queue_s=first_queue,
        crossing_1000_n=len(crossings),
        crossing_1000_rate_veh_h=len(crossings) * 7.2,
    )


def case(run):
    result = read_json(run / 'result.json')
    trips = read_json(run / 'trips.json')
    arrivals = [trip['exited_s'] for trip in trips if trip['exited_s'] is not None]
    assert len(arrivals) == result['completed']
    return dict(path=run.relative_to(ROOT).as_posix(), **{f: result[f] for f in (
        'safe', 'all_completed', 'collisions', 'teleports', 'requested', 'completed',
        'mean_system_time_s', 'mean_travel_time_s', 'mean_entry_wait_s', 'fuel_g_per_km',
        'actual_end_s')},
        completed_by_600=sum(t <= 600 for t in arrivals),
        **trajectory_metrics(run / 'positions.jsonl.gz', result['actual_end_s']))


MEASURES = ('mean_system_time_s', 'mean_travel_time_s', 'mean_entry_wait_s', 'fuel_g_per_km',
            'bottleneck_low_speed_vehicle_s', 'crossing_1000_rate_veh_h', 'completed_by_600',
            'road_mean_speed_mps', 'bottleneck_mean_speed_mps', 'road_above_cruise_fraction',
            'bottleneck_above_cruise_fraction')


def means(index):
    output = {}
    for flow in FLOWS:
        flow_means = {}
        for cap in ('original33_3', 'cap28_8'):
            op = {}
            for road in SCENARIOS:
                measures = {}
                for mode in MODES:
                    measures[mode] = {k: mean(index[flow, s, road, mode][cap][k] for s in SEEDS)
                                      for k in MEASURES}
                measures['transform_minus_noa'] = {k: measures['transform'][k] - measures['noa'][k]
                                                   for k in MEASURES}
                op[road] = measures
            op['road_did_transform_minus_noa'] = {
                k: op['lane_drop']['transform_minus_noa'][k] - op['straight3']['transform_minus_noa'][k]
                for k in MEASURES}
            flow_means[cap] = op
        output[flow] = flow_means
    return output


def paired_case(row, *, cap_sources, original_sources):
    assert row['worker_exit'] == 0 and row['verified'], row
    base, capped = (Path(row[k]) for k in ('baseline', 'run'))
    audited = verify(capped, read_json(capped / 'result.json'), base, cap_sources)
    assert all(row[k] == value for k, value in audited.items())
    for run, limit in ((base, 33.3), (capped, CAP)):
        inputs = read_json(run / 'input.json')
        assert inputs['physical']['maxSpeed'] == limit
        assert set(fixed_geometry(run / 'native.net.xml')[1]) == {limit}
        assert digest(json.dumps(inputs['arrivals'], sort_keys=True).encode()) == row['tape_sha256']
        if run == base:
            for name, sha in inputs['source_sha256'].items():
                assert digest((run / 'source' / name).read_bytes()) == sha == original_sources[name]
        result = read_json(run / 'result.json')
        assert tuple(result[k] for k in ('flow_veh_h_lane', 'seed', 'scenario', 'mode')) == tuple(row[k] for k in KEYS)
    pair = dict(original33_3=case(base), cap28_8=case(capped))
    assert pair['cap28_8']['actual_peak_speed_mps'] <= CAP + 1e-9
    assert pair['cap28_8']['all_above_cruise_vehicle_s'] == 0
    assert pair['cap28_8']['requested'] == pair['original33_3']['requested']
    return {**{k: row[k] for k in (*KEYS, 'tape_sha256', 'controller_peak_mps',
                                   'set_speed_peak_mps', 'lane_speed_peak_mps')}, **pair}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--baseline-only', action='store_true', help='Read current 2000/311 for both roads and modes.')
    mode.add_argument('--batch', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    assert not args.output.exists()
    rows = []
    if args.baseline_only:
        for row in read_json(REFERENCE / 'manifest.json'):
            if row['flow'] == 2000 and row['seed'] == 311:
                rows.append(dict(scenario=row['scenario'], mode=row['mode'], **case(Path(row['run_dir']))))
        assert len(rows) == 4
        write_json(args.output, rows)
        return
    manifest = read_json(args.batch / 'manifest.json')
    assert len(manifest) == 60
    protocol = read_json(args.batch / 'protocol.json')
    paired = partial(paired_case, cap_sources=protocol['source_sha256'], original_sources=protocol['reference_sha256'])
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(paired, manifest))
    index = {tuple(x[k] for k in KEYS): x for x in rows}
    assert set(index) == set(itertools.product(FLOWS, SEEDS, SCENARIOS, MODES))
    for flow, seed in itertools.product(FLOWS, SEEDS):
        assert len({index[flow, seed, road, mode]['tape_sha256']
                    for road, mode in itertools.product(SCENARIOS, MODES)}) == 1
    write_json(args.output, dict(source_sha256=protocol['source_sha256'], reference_sha256=protocol['reference_sha256'],
                                  cases=[index[k] for k in sorted(index)], means=means(index)))


if __name__ == '__main__':
    main()
