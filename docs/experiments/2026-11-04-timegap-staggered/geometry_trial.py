"""Run original formation tapes with a frozen rule file and a longer observation road."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'docs/experiments/2026-11-03-staggered-bottleneck/formation_demo_D1'
BASE = '177f7a32088fb69efcc94d9acb72863e7e00e787'
FILES = ('experiments/native_sumo.py', 'experiments/global_reference.py',
         'experiments/complete_layers.py', 'noa/native_rules.py', 'run_native_flow.py',
         'research/common.py', 'configs/tools.json', 'experiments/__init__.py',
         'noa/__init__.py', 'research/__init__.py')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rules', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--demo', choices=('unformed24', 'formed45'), required=True)
    p.add_argument('--scenario', choices=('straight3', 'lane_drop'), required=True)
    p.add_argument('--exit-m', type=int, default=2400)
    a = p.parse_args()
    if a.exit_m < 1200:
        p.error('The observation exit must be at least 1200 m.')
    assert not a.output.exists(), 'Keep earlier attempts; choose a new output.'
    source = a.output / 'source'
    for name in FILES:
        raw = a.rules.read_bytes() if name == 'noa/native_rules.py' else subprocess.check_output(
            ['git', 'show', BASE + ':variants/phase5g_pure_formation/' + name], cwd=ROOT)
        if name == 'experiments/native_sumo.py':
            text = raw.decode()
            assert text.count('("exit", 1200)') == text.count('retained, 1000, 1200)') == 1
            raw = text.replace('("exit", 1200)', f'("exit", {a.exit_m})').replace(
                'retained, 1000, 1200)', f'retained, 1000, {a.exit_m})').encode()
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    tape = OLD / (a.demo + '_initial.json')
    command = [sys.executable, '-X', 'utf8', '-B', str(source / 'run_native_flow.py'),
               '--mode', 'transform', '--flow', '1750', '--seed', '1', '--duration', '1',
               '--max-time', '240', '--scenario', a.scenario, '--initial', str(tape),
               '--diagnostic', '--output-base', str(a.output / 'run')]
    protocol = {'demo': a.demo, 'scenario': a.scenario, 'rules': str(a.rules),
                'initial': str(tape), 'exit_m': a.exit_m, 'bottleneck_m': 1000,
                'purpose': 'formation geometry; not a traffic-efficiency comparison', 'command': command}
    (a.output / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n', encoding='utf-8')
    raise SystemExit(subprocess.call(command, cwd=ROOT))


if __name__ == '__main__':
    main()
