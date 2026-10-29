"""Paired flow study: NOA/formation transformation, straight road and lane drop."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from experiments.native_sumo import ROOT, _source_snapshot, run_case, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flows', type=float, nargs='+', default=[500, 750, 1000, 1500])
    parser.add_argument('--seeds', type=int, nargs='+', default=[1, 2, 3, 4, 5])
    parser.add_argument('--duration', type=float, default=600.)
    parser.add_argument('--output-base', type=Path)
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    base = (args.output_base or ROOT/'results/flow_attribution')/stamp
    base.mkdir(parents=True, exist_ok=False)
    source = _source_snapshot(base)
    protocol = dict(flows=args.flows, seeds=args.seeds, duration_s=args.duration,
                    max_time_s=args.duration+300, source_sha256=source,
                    wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    case_count=5*len(args.flows)*len(args.seeds),
                    cases_per_seed_flow='straight3:noa,transform; lane_drop:noa,formation,transform')
    write_json(base/'protocol.json', protocol)
    records = []
    for seed in args.seeds:
        for flow in args.flows:
            for road, modes in [('straight3', ('noa', 'transform')),
                                ('lane_drop', ('noa', 'formation', 'transform'))]:
                for mode in modes:
                    path = run_case(mode=mode, seed=seed, flow=flow, duration=args.duration,
                                    max_time=args.duration+300, scenario=road,
                                    output_base=base/f'flow_{flow:g}')
                    result = json.loads((path/'result.json').read_text(encoding='utf-8'))
                    record = dict(flow=flow, seed=seed, scenario=road, mode=mode,
                                  run_dir=str(path), status=result['status'],
                                  requested=result['requested'], completed=result['completed'],
                                  mean_travel_time_s=result['mean_travel_time_s'],
                                  collisions=result['collisions'], teleports=result['teleports'])
                    records.append(record)
                    write_json(base/'run_status.json', records)
                    for rate in args.flows:
                        write_json(base/f'flow_{rate:g}_manifest.json',
                                   dict(cases=[r['run_dir'] for r in records if r['flow']==rate]))
                    write_json(base/'manifest.json', dict(cases=[r['run_dir'] for r in records]))
                    print(json.dumps(record), flush=True)
    print(json.dumps(dict(study_dir=str(base),cases=len(records))), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
