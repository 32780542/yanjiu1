"""Read measured cohort crossings at x=1000; no simulation or controller calls."""
import argparse
import csv
import gzip
import json
from pathlib import Path
from statistics import mean


def summarize(frames, trips, vehicle_ids):
    first, previous, crossing = {}, {}, {}
    stopped, stop_samples = set(), 0
    vehicle_ids = set(vehicle_ids)
    for frame in frames:
        time = frame['time_s']
        for key, (x, y, speed, _) in frame['states'].items():
            if key not in vehicle_ids:
                continue
            first.setdefault(key, (time, x, speed))
            if key in previous and key not in crossing:
                before_t, before_x = previous[key]
                if before_x < 1000. <= x:
                    crossing[key] = before_t + (time - before_t) * (1000. - before_x) / (x - before_x)
            previous[key] = time, x
            # Same descriptive sample exposure used in the traffic report.
            if 900. <= x < 1000. and abs(y - 8.25) <= .15 and speed < .1:
                stopped.add(key)
                stop_samples += 1
    events = {trip['vehicle_id']: trip.get('lane_completion_events', []) for trip in trips}
    rows = []
    for key in sorted(vehicle_ids):
        observed = first.get(key)
        t0, x0, v0 = observed if observed is not None else (None, None, None)
        free = t0 + (1000. - x0) / 28.8 if observed is not None else None
        passed = crossing.get(key)
        completed = events.get(key, [])
        rows.append(dict(vehicle_id=key, first_time_s=t0, first_x_m=x0, first_speed_mps=v0,
                         free_crossing_time_s=free, crossing_time_s=passed,
                         bottleneck_delay_s=passed - free if passed is not None else None,
                         lane_completions_to_bottleneck=sum(event['x'] <= 1000. for event in completed),
                         lane_completions_full_observation=len(completed)))
    all_crossed = len(crossing) == len(vehicle_ids)
    summary = dict(cohort_count=len(vehicle_ids), observed_count=len(first), crossed_count=len(crossing),
                   mean_crossing_time_s=mean(crossing.values()) if all_crossed else None,
                   last_crossing_time_s=max(crossing.values()) if all_crossed else None,
                   mean_bottleneck_delay_s=mean(row['bottleneck_delay_s'] for row in rows) if all_crossed else None,
                   first_measured_mean_x_m=mean(value[1] for value in first.values()) if first else None,
                   first_measured_min_x_m=min((value[1] for value in first.values()), default=None),
                   first_measured_max_x_m=max((value[1] for value in first.values()), default=None),
                   ending_stop_vehicles=len(stopped), ending_stop_sample_vehicle_s=.1 * stop_samples,
                   lane_completions_to_bottleneck=sum(row['lane_completions_to_bottleneck'] for row in rows),
                   lane_completions_full_observation=sum(row['lane_completions_full_observation'] for row in rows))
    return summary, rows


def read_case(trial):
    protocol = json.loads((trial / 'protocol.json').read_text(encoding='utf-8'))
    initial = json.loads(Path(protocol['initial']).read_text(encoding='utf-8'))
    runs = list((trial / 'run').glob('*/positions.jsonl.gz'))
    if len(runs) != 1:
        raise ValueError('Expected exactly one measured run in ' + str(trial))
    run = runs[0].parent
    trips = json.loads((run / 'trips.json').read_text(encoding='utf-8'))
    result = json.loads((run / 'result.json').read_text(encoding='utf-8'))
    with gzip.open(runs[0], 'rt', encoding='utf-8') as stream:
        summary, rows = summarize((json.loads(line) for line in stream), trips, (c['id'] for c in initial))
    mode = protocol.get('mode')
    if mode is None:
        command = protocol['command']
        mode = command[command.index('--mode') + 1]
    summary.update(mode=mode, initial=protocol['initial'], rules=protocol['rules'],
                   run_dir=str(run.resolve()), bottleneck_m=1000, observation_exit_m=protocol['exit_m'])
    summary.update({key: result[key] for key in (
        'status', 'safe', 'all_completed', 'requested', 'completed', 'collisions', 'teleports')})
    return summary, rows


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append', required=True, help='LABEL=geometry_trial output directory')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    summaries, vehicles = [], []
    for case in args.case:
        label, path = case.split('=', 1)
        summary, rows = read_case(Path(path))
        summaries.append(dict(case=label, **summary))
        vehicles.extend(dict(case=label, **row) for row in rows)
    args.output.mkdir(parents=True, exist_ok=False)
    write_csv(args.output / 'summary.csv', summaries)
    write_csv(args.output / 'per_vehicle.csv', vehicles)
    (args.output / 'summary.json').write_text(json.dumps(summaries, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
