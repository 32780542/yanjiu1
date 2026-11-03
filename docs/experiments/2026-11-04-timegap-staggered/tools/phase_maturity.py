"""Read the fixed 12 completed seed211 transform traces; never run SUMO."""
import argparse
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1] / 'stage'
REGIONS = {'x200_600': (200., 600.), 'x600_800': (600., 800.)}
SCOPES = {'01': (0, 1), '12': (1, 2), 'all_adjacent': (0, 1, 2)}
FLOWS = (1500, 1750, 2000)


@dataclass
class Accumulator:
    frames: int = 0
    vehicle_samples: int = 0
    adjacent_lane_opportunities: int = 0
    matched_vehicle_samples: int = 0
    matched_directed_samples: int = 0
    unique_pair_observations: int = 0
    absolute_error_sum: float = 0.
    absolute_target_sum: float = 0.
    settled_directed_samples: int = 0
    settled_absolute_error_sum: float = 0.
    moving_vehicle_samples: int = 0
    matched_pair_any_moving: int = 0


def selected_cases(path, family):
    rows = json.loads(path.read_text(encoding='utf-8'))
    cases = [r for r in rows if r['candidate'] in (family + '_200', family + '_300')
             and r['mode'] == 'transform' and r['scenario'] == 'lane_drop'
             and r['seed'] == 211 and int(r['flow']) in FLOWS]
    keys = [(r['candidate'], int(r['flow'])) for r in cases]
    expected = {(family + '_' + str(info), flow) for info in (200, 300) for flow in FLOWS}
    if len(cases) != 6 or set(keys) != expected:
        raise ValueError(f'{family}: expected exactly the six fixed seed211 cases; found {keys}')
    for row in cases:
        run = Path(row['run_dir'])
        if row.get('returncode') is None or not (run / 'result.json').is_file():
            raise ValueError(f'Case not terminal: {run}')
        row = row.copy()
        row['manifest_path'] = str(path)
        yield row


def load_rules(run, index):
    name = 'formal211_frozen_rules_' + str(index)
    spec = importlib.util.spec_from_file_location(name, run / 'source/noa/native_rules.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def consume(row, index):
    run = Path(row['run_dir'])
    rules = load_rules(run, index)
    trips = json.loads((run / 'trips.json').read_bytes())
    initial_lane = {v['vehicle_id']: v['lane'] for v in trips}
    lane_events = {v['vehicle_id']: sorted(v['lane_events'], key=lambda e: e['time_s']) for v in trips}
    event_times = {key: [e['time_s'] for e in events] for key, events in lane_events.items()}
    stats = {(region, scope): Accumulator() for region in REGIONS for scope in SCOPES}
    previous, previous_t = {}, None
    with gzip.open(run / 'positions.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            frame = json.loads(line)
            time, states = frame['time_s'], frame['states']
            if time >= 600.:
                break
            if time < 100.:
                previous, previous_t = states, time
                continue
            cars = {}
            moving = {}
            for track, (key, values) in enumerate(states.items()):
                event_index = bisect_right(event_times[key], time)
                lane = lane_events[key][event_index - 1]['to_lane'] if event_index else initial_lane[key]
                vy = ((values[1] - previous[key][1]) / (time - previous_t)
                      if key in previous and previous_t is not None else 0.)
                # positions[3] is longitudinal acceleration, never lateral velocity.
                car = rules.Vehicle(track, values[0], values[1], values[2], lane, vy=vy)
                cars[key] = car
                moving[key] = abs(vy) > .1 or abs(car.y - (lane + .5) * rules.LANE_WIDTH) > .15
            lanes = {lane: sorted((key for key, car in cars.items() if car.lane == lane),
                                  key=lambda key: cars[key].x) for lane in range(3)}
            coordinates = {lane: [cars[key].x for key in keys] for lane, keys in lanes.items()}
            nearest_cache = {}

            def nearest(key, lane):
                cache_key = key, lane
                if cache_key not in nearest_cache:
                    car = cars[key]
                    xs = coordinates[lane]
                    candidates = lanes[lane][bisect_left(xs, car.x - 50.):bisect_right(xs, car.x + 50.)]
                    # Same physical tie key and mutual50 rule as the frozen controller.
                    nearest_cache[cache_key] = min(candidates, key=lambda other: (
                        abs(rules._pair_error(car, cars[other], 3)[0]),
                        abs(cars[other].x - car.x), cars[other].x, cars[other].y,
                        cars[other].speed, cars[other].vy), default=None)
                return nearest_cache[cache_key]

            for region, (low, high) in REGIONS.items():
                actors = [key for key, car in cars.items() if low <= car.x < high]
                for scope, scope_lanes in SCOPES.items():
                    acc = stats[region, scope]
                    acc.frames += 1
                    unique, unique_moving = set(), set()
                    for key in actors:
                        car = cars[key]
                        if car.lane not in scope_lanes:
                            continue
                        acc.vehicle_samples += 1
                        acc.moving_vehicle_samples += moving[key]
                        matched = False
                        for lane in (car.lane - 1, car.lane + 1):
                            if lane not in scope_lanes:
                                continue
                            acc.adjacent_lane_opportunities += 1
                            peer_key = nearest(key, lane)
                            if peer_key is None or nearest(peer_key, car.lane) != key:
                                continue
                            peer = cars[peer_key]
                            matched = True
                            error = abs(rules._pair_error(car, peer, 3)[0])
                            mean_speed = (car.speed + peer.speed) / 2
                            target = abs(rules._physical_phase(peer, 3, mean_speed)
                                         - rules._physical_phase(car, 3, mean_speed))
                            acc.matched_directed_samples += 1
                            acc.absolute_error_sum += error
                            acc.absolute_target_sum += target
                            pair = frozenset((key, peer_key))
                            unique.add(pair)
                            if moving[key] or moving[peer_key]:
                                unique_moving.add(pair)
                            else:
                                acc.settled_directed_samples += 1
                                acc.settled_absolute_error_sum += error
                        acc.matched_vehicle_samples += matched
                    acc.unique_pair_observations += len(unique)
                    acc.matched_pair_any_moving += len(unique_moving)
            previous, previous_t = states, time
    result = json.loads((run / 'result.json').read_bytes())
    output = []
    for (region, scope), a in stats.items():
        output.append(dict(method=row['candidate'], information_m=int(row['candidate'].rsplit('_', 1)[1]),
            flow=int(row['flow']), seed=211, mode='transform', target_phase='zero' if row['candidate'].startswith('P') else 'dynamic_half_D',
            region=region, pair_scope=scope, time_from_s=100, time_to_exclusive_s=600,
            frames=a.frames, vehicle_samples=a.vehicle_samples,
            adjacent_lane_opportunities=a.adjacent_lane_opportunities,
            matched_vehicle_samples=a.matched_vehicle_samples,
            matched_vehicle_fraction=ratio(a.matched_vehicle_samples, a.vehicle_samples),
            matched_directed_samples=a.matched_directed_samples,
            unique_pair_observations=a.unique_pair_observations,
            phase_mae_m=ratio(a.absolute_error_sum, a.matched_directed_samples),
            mean_abs_target_phase_m=ratio(a.absolute_target_sum, a.matched_directed_samples),
            settled_directed_samples=a.settled_directed_samples,
            phase_mae_neither_moving_m=ratio(a.settled_absolute_error_sum, a.settled_directed_samples),
            moving_vehicle_samples=a.moving_vehicle_samples,
            moving_vehicle_fraction=ratio(a.moving_vehicle_samples, a.vehicle_samples),
            matched_pair_any_moving=a.matched_pair_any_moving,
            matched_pair_any_moving_fraction=ratio(a.matched_pair_any_moving, a.unique_pair_observations),
            run_status=result.get('status'), safe=result.get('safe'), all_completed=result.get('all_completed'),
            run=str(run), source_kind='new_formal211_raw', manifest=row['manifest_path']))
    print(json.dumps(dict(method=row['candidate'], flow=row['flow'], seed=211,
                          frames=next(iter(stats.values())).frames, run=str(run)), ensure_ascii=False), flush=True)
    return output


def write_report(rows):
    aggregate = [r for r in rows if r['pair_scope'] == 'all_adjacent']
    c12 = [r for r in aggregate if r['method'].startswith('C12')]
    p12 = [r for r in aggregate if r['method'].startswith('P12')]
    c_up = [r['phase_mae_m'] for r in c12 if r['region'] == 'x200_600']
    c_near = [r['phase_mae_m'] for r in c12 if r['region'] == 'x600_800']
    p_up = [r['phase_mae_m'] for r in p12 if r['region'] == 'x200_600']
    p_near = [r['phase_mae_m'] for r in p12 if r['region'] == 'x600_800']
    max_motion_difference = max(abs(r['phase_mae_m'] - r['phase_mae_neither_moving_m']) for r in aggregate)
    lines = ['# 固定seed211的正式局部相位过程', '',
        '预先固定seed211，仅消费C12/P12 transform的两种道路可见范围×三流量，共12条正式raw。'
        '这是单种子的代表过程，不能替代五种子交通主统计。NOA的0状态不在这里解释为形成。', '',
        f'**这组正式持续流中，进入缩道前仍有数米相位残差。** C12前段MAE为{min(c_up):.3f}–{max(c_up):.3f}m，'
        f'近段为{min(c_near):.3f}–{max(c_near):.3f}m；P12对应为{min(p_up):.3f}–{max(p_up):.3f}m、'
        f'{min(p_near):.3f}–{max(p_near):.3f}m。没有据此声明整队已完成目标几何，也不以局部互选MAE替代全排序交替或实际D/半D。'
        '两法目标不同，不能仅凭两列MAE的绝对大小排序交通收益。', '',
        '时间严格为`[100,600)` s，按本车位置分别取`[200,600)`、`[600,800)` m。'
        '各自冻结源的`_pair_error`与mutual50决定匹配；C12目标为动态半D，P12目标为0，均使用实际y插值。'
        '车辆帧不是独立车辆；MAE按有向匹配加权，双方都在区域时关系计两次，覆盖为至少获得一个互选关系的车辆帧比例。', '',
        'lane由trips的实际lane_events重建，vy由连续positions的y差分重建；第四列是纵向加速度。'
        '双方无横移沿用`.1m/s/.15m`的实际执行判据，未设置新的形成门。600–800m已混合接入与运动传播，'
        '对300m道路可见范围尤其不能称为全部未知道路的纯形成区。', '',
        '数据：[formal211_phase_maturity.csv](formal211_phase_maturity.csv)。CSV另列01/12、匹配机会、去重关系、横移比例和逐run来源；没有读取其他正式种子或重扫开发raw。', '']
    for region, label in (('x200_600', '200–600m'), ('x600_800', '600–800m')):
        lines += ['## ' + label, '', '| 方法/可见范围 | 流量 | phase MAE(m) | 获匹配车辆帧 | 双方无横移MAE(m) | 车辆帧 / 有向匹配 |',
                  '| --- | ---: | ---: | ---: | ---: | --- |']
        for r in rows:
            if r['region'] != region or r['pair_scope'] != 'all_adjacent':
                continue
            lines.append(f"| {r['method']} | {r['flow']} | {r['phase_mae_m']:.6f} | {r['matched_vehicle_fraction']:.2%} | {r['phase_mae_neither_moving_m']:.6f} | {r['vehicle_samples']} / {r['matched_directed_samples']} |")
        lines.append('')
    lines += ['## 解释与数据可用范围', '',
        f'剔除任一方实际横移后，所有24个方法/信息/流量/区域组合的MAE变化均不超过{max_motion_difference:.3f}m；'
        '数米残差仍保留，不能把它全部归因于横移混合。600–800m同时含较晚形成与缩道接入，保留该混合含义。'
        '各run均有5000个正式时间帧，原状态和安全/排空字段也保留在CSV中。', '',
        '先前dev201的C12/P12值只见[既有消费表](C12_P12_phase_maturity_comparison.csv)，本次未重读开发raw。'
        '其种子和窗口长度不同，不作为本次正式211的成对对照。', '',
        '必要脚本为[../tools/phase_maturity.py](../tools/phase_maturity.py)，仅用标准库和各run的冻结rules，不依赖其他tmp helper。'
        '随仓库保留的是脚本、读数CSV与说明；固定211这12条原轨迹在本机保留用于后续时空图，完整全路raw不全量入Git。'
        '从原轨迹复算需要CSV run列对应的positions.jsonl.gz、trips.json、result.json与source/noa/native_rules.py；汇总表不能替代这些逐帧输入。', '',
        '在研究仓库根目录复现：', '', '```powershell',
        'python -X utf8 -B scripts/run_logged.py --label formal211_phase_maturity --timeout 1200 -- python -X utf8 -B docs/experiments/2026-11-04-timegap-staggered/tools/phase_maturity.py --c12-manifest tmp/staggered_bottleneck/20261104_formal600_main_drop_211_215_r01/manifest.json --p12-manifest tmp/staggered_bottleneck/20261104_formal600_parallel_drop_211_215_r01/manifest.json',
        '```', '']
    (OUT / 'formal211_phase_maturity.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--c12-manifest', type=Path, default=ROOT / 'tmp/staggered_bottleneck/20261104_formal600_main_drop_211_215_r01/manifest.json')
    parser.add_argument('--p12-manifest', type=Path, required=True)
    args = parser.parse_args()
    args.c12_manifest = args.c12_manifest if args.c12_manifest.is_absolute() else ROOT / args.c12_manifest
    args.p12_manifest = args.p12_manifest if args.p12_manifest.is_absolute() else ROOT / args.p12_manifest
    cases = list(selected_cases(args.c12_manifest, 'C12')) + list(selected_cases(args.p12_manifest, 'P12'))
    cases.sort(key=lambda r: (r['candidate'].split('_')[0], int(r['candidate'].split('_')[1]), int(r['flow'])))
    rows = []
    for index, case in enumerate(cases):
        rows.extend(consume(case, index))
    path = OUT / 'formal211_phase_maturity.csv'
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_report(rows)
    print(json.dumps(dict(csv=str(path), runs=len(cases), rows=len(rows)), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
