"""Run the full 28.8 m/s control-by-road sensitivity on frozen Current sources."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import itertools
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from run_shared_physics import FILES, NATIVE, ROOT, digest, read_json, write_json


RUNS = ROOT / 'tmp/staggered_bottleneck'
REFERENCE = RUNS / '20261118_current60_r01'
RULES = 'noa/native_rules.py'
CAP = 28.8
FLOWS = (1500, 1750, 2000)
SEEDS = (311, 312, 313, 314, 315)
SCENARIOS = ('lane_drop', 'straight3')
MODES = ('noa', 'transform')
KEYS = ('flow', 'seed', 'scenario', 'mode')
RUNNER_EDITS = (
    (b'    maxSpeed=33.3,', b'    maxSpeed=28.8,'),
    (b'            speed="33.3",', b'            speed="28.8",'),
    (b'                        executed_speed = min(33.3,', b'                        executed_speed = min(28.8,'),
    (b'                        conn.vehicle.setSpeed(key, executed_speed)',
     b'                        execution["peak_controller_request_mps"] = max(\n'
     b'                            execution["peak_controller_request_mps"], command.speed)\n'
     b'                        execution["peak_setspeed_request_mps"] = max(\n'
     b'                            execution["peak_setspeed_request_mps"], executed_speed)\n'
     b'                        conn.vehicle.setSpeed(key, executed_speed)'),
)
RULE_EDIT = (b'CRUISE, MAX_SPEED = 28.8, 33.3', b'CRUISE, MAX_SPEED = 28.8, 28.8')


def changed(raw, edits):
    for old, new in edits:
        assert raw.count(old) == 1, old
        if b'\r\n' in raw:
            new = new.replace(b'\n', b'\r\n')
        raw = raw.replace(old, new, 1)
    return raw


def freeze(batch):
    expected = read_json(REFERENCE / 'protocol.json')['sources']['Current']
    source = batch / 'source'
    (source / 'tmp').mkdir(parents=True)
    hashes = {}
    for name in FILES:
        raw = (REFERENCE / 'sources/Current' / name).read_bytes()
        assert digest(raw) == expected[name]
        if name == NATIVE:
            raw = changed(raw, RUNNER_EDITS)
        if name == RULES:
            raw = changed(raw, (RULE_EDIT,))
        dest = source / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        hashes[name] = digest(raw)
    assert {name for name in hashes if hashes[name] != expected[name]} == {NATIVE, RULES}
    return hashes, expected


def fixed_geometry(file):
    root = ET.parse(file).getroot()
    lane_speeds = [float(lane.attrib.pop('speed')) for lane in root.iter('lane')]
    return ET.tostring(root), lane_speeds


def verify(run, record, base, hashes):
    source, original = (read_json(p / 'input.json') for p in (run, base))
    assert set(source) == set(original)
    assert all(source[k] == original[k] for k in source if k not in ('source_sha256', 'physical'))
    assert dict(original['physical'], maxSpeed=CAP) == source['physical']
    assert all(req['speed'] == CAP for req in source['arrivals'])
    tracked = source['source_sha256']
    assert record['source_sha256'] == tracked
    assert tracked and all(sha == hashes[name] == digest((run / 'source' / name).read_bytes())
                           for name, sha in tracked.items())
    for file in ('positions.jsonl.gz', 'events.jsonl.gz', 'trips.json', 'sumo_tripinfo.xml'):
        assert (run / file).stat().st_size > 0
    actual_type = ET.parse(run / 'native.rou.xml').getroot().find('vType')
    assert actual_type is not None
    assert actual_type.attrib == {'id': 'CAV_ICV', **{k: str(v) for k, v in source['physical'].items()}}
    geom, speeds = fixed_geometry(run / 'native.net.xml')
    geom_ref, _ = fixed_geometry(base / 'native.net.xml')
    assert geom == geom_ref and speeds and max(speeds) == CAP
    requests = [record['execution'][key] for key in ('peak_controller_request_mps', 'peak_setspeed_request_mps')]
    assert all(speed <= CAP + 1e-9 for speed in requests)
    return dict(controller_peak_mps=requests[0], set_speed_peak_mps=requests[1], lane_speed_peak_mps=max(speeds),
                tape_sha256=digest(json.dumps(source['arrivals'], sort_keys=True).encode('utf-8')))


def inspect(folder, task, hashes, worker_exit):
    task.update(worker_exit=worker_exit, verified=False)
    try:
        result, = folder.glob('*/result.json')
        record = read_json(result)
        assert record['status'] != 'starting'
        task.update(run=str(result.parent), **{key: record.get(key) for key in (
            'status', 'safe', 'all_completed', 'requested', 'completed', 'collisions', 'teleports',
            'mean_system_time_s', 'mean_travel_time_s', 'mean_entry_wait_s', 'fuel_g_per_km', 'error')})
        task.update(verify(result.parent, record, Path(task['baseline']), hashes))
        task['verified'] = True
    except (AssertionError, KeyError, ValueError, OSError, ET.ParseError) as error:
        task['verification_error'] = f'{type(error).__name__}: {error}'
    return task


def execute(batch, task, hashes):
    flow, seed, scenario, mode = (task[k] for k in KEYS)
    folder = batch / 'cases' / f'Cap288_{flow}_{seed}_{scenario}_{mode}'
    folder.mkdir(parents=True)
    command = [sys.executable, '-B', str(ROOT / 'scripts/run_logged.py'), '--label',
               f'n18-cap288-{flow}-{seed}-{scenario}-{mode}', '--timeout', '1500', '--',
               sys.executable, '-X', 'utf8', '-B', str(batch / 'source/run_native_flow.py'),
               '--scenario', scenario, '--mode', mode, '--flow', str(flow), '--seed', str(seed),
               '--duration', '600', '--max-time', '1200', '--output-base', str(folder)]
    with (folder / 'worker.log').open('wb') as log:
        worker = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    return inspect(folder, task, hashes, worker.returncode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--resume-from', type=Path, help='Reuse verified runs from this read-only prior batch.')
    args = parser.parse_args()
    batch = args.output.resolve()
    assert batch.parent == RUNS and not batch.exists() and args.jobs >= 1
    batch.mkdir()
    hashes, original_hashes = freeze(batch)
    reference = {(r['flow'], r['seed'], r['scenario'], r['mode']): r['run_dir']
                 for r in read_json(REFERENCE / 'manifest.json')}
    tasks = [dict(flow=f, seed=s, scenario=r, mode=m, baseline=reference[f, s, r, m])
             for r, f, s, m in itertools.product(SCENARIOS, FLOWS, SEEDS, MODES)]
    rows = []
    reused = set()
    prior = args.resume_from.resolve() if args.resume_from else None
    if prior:
        protocol = read_json(prior / 'protocol.json')
        assert protocol['tasks'] == tasks and protocol['source_sha256'] == hashes
        assert protocol['reference_sha256'] == original_hashes and protocol['cap_mps'] == CAP
        manifest = {tuple(r[k] for k in KEYS): r for r in read_json(prior / 'manifest.json')}
        for task in tasks:
            key = tuple(task[k] for k in KEYS)
            row = manifest.get(key)
            folder = prior / 'cases' / ('Cap288_' + '_'.join(map(str, key)))
            if row and row.get('run'):
                folder = Path(row['run']).parent
            log = folder / 'worker.log'
            try:
                worker = read_json(log)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            if worker.get('returncode') != 0:
                continue
            recovered = inspect(folder, task.copy(), hashes, worker['returncode'])
            if recovered['verified']:
                rows.append(recovered)
                reused.add(key)
    write_json(batch / 'protocol.json', dict(tasks=tasks, baseline=str(REFERENCE), source_sha256=hashes,
        reference_sha256=original_hashes, jobs=args.jobs, duration_s=600, max_time_s=1200, cap_mps=CAP,
        resumed_from=str(prior) if prior else None, reused=len(rows),
        order='Lane drop before straight. Original 33.3 trials are not rerun.', preserve_raw=True))
    fields = ('flow', 'seed', 'scenario', 'mode', 'status', 'safe', 'all_completed', 'worker_exit', 'verified',
              'verification_error', 'mean_system_time_s')
    write_json(batch / 'manifest.json', rows)
    missing = [t for t in tasks if tuple(t[k] for k in KEYS) not in reused]
    print(f'Reused {len(rows)}, running {len(missing)} with {args.jobs} workers', flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(execute, batch, task.copy(), hashes) for task in missing]
        for done in as_completed(futures):
            row = done.result()
            rows.append(row)
            write_json(batch / 'manifest.json', rows)
            print(json.dumps({key: row.get(key) for key in fields}), flush=True)
    return int(not all(r['worker_exit'] == 0 and r['verified'] and r['safe'] and r['all_completed'] for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
