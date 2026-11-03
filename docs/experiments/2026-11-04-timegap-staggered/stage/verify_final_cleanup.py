"""Read-only source delta and paired Command/Memory verification for final files."""
import hashlib
import importlib.util
from dataclasses import asdict
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'tmp/staggered_bottleneck/candidates'


def cleaned(text):
    return (text.replace('GAP = LENGTH + STANDSTILL + HEADWAY * CRUISE\n', '')
            .replace('def _phase(lane, lanes, speed=CRUISE):', 'def _phase(lane, speed=CRUISE):')
            .replace('_phase(lower, lanes, speed)', '_phase(lower, speed)')
            .replace('_phase(upper, lanes, speed)', '_phase(upper, speed)')
            .replace('def _pair_error(car, peer, lanes, phase_boundary=None):', 'def _pair_error(car, peer, lanes):')
            .replace('def _following(ego, rows, lanes=3, phase_boundary=None):', 'def _following(ego, rows, lanes=3):'))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


all_text = {}
for family, parent in (('final', 'C8_relations'), ('final_parallel', 'parallel_relations')):
    for preview in (200, 300):
        old_path = BASE / f'20261104_{parent}_{preview}/native_rules.py'
        path = BASE / f'20261104_{family}_{preview}/native_rules.py'
        old_text, text = old_path.read_text(encoding='utf-8'), path.read_text(encoding='utf-8')
        assert cleaned(old_text) == text
        old, new = load(old_path, f'old_{family}_{preview}'), load(path, f'new_{family}_{preview}')
        rng = random.Random(73019)
        old_memory, new_memory = old.Memory(), new.Memory()
        for i in range(500):
            lane = i % 3
            x = rng.uniform(600., 1100.)
            speed = rng.choice((0., 5., 20., 28.8, 33.3))
            pending = lane - 1 if lane and i % 11 == 0 else None
            ego = old.Vehicle(0, x, (lane + .5) * 3.3, speed, lane, pending_lane=pending)
            rows = []
            for track in range(1, 9):
                other_lane = rng.randrange(3)
                vy = rng.choice((0., 0., 0., -.4, .4))
                rows.append(old.Vehicle(track, x + rng.uniform(-100., 200.),
                                        (other_lane + .5) * 3.3, rng.choice((0., 10., 20., 28.8)),
                                        other_lane, vy=vy))
            mode = ('noa', 'formation', 'transform')[i % 3]
            drop = None if i % 4 == 0 else 1000.
            new_ego = new.Vehicle(**asdict(ego))
            new_rows = tuple(new.Vehicle(**asdict(c)) for c in rows)
            a, old_memory = old.decide(ego, tuple(rows), old_memory, mode, drop)
            b, new_memory = new.decide(new_ego, new_rows, new_memory, mode, drop)
            assert asdict(a) == asdict(b), (family, preview, i, asdict(a), asdict(b))
            assert asdict(old_memory) == asdict(new_memory), (family, preview, i)
        all_text[family, preview] = text
        print(f'{family}_{preview}: 500 paired Command+Memory frames identical (including flags/NOA)')
        print(f'{path} | lines={len(text.splitlines())} | SHA256={hashlib.sha256(path.read_bytes()).hexdigest()}')

for preview in (200, 300):
    assert (all_text['final', preview]
            .replace('    return desired_spacing(speed) / 2 if lane % 2 else 0.\n', '    return 0.\n')
            .replace('        q = current.x - d / 2\n', '        q = current.x\n')) == all_text['final_parallel', preview]
for family in ('final', 'final_parallel'):
    assert all_text[family, 200].replace('ROAD_PREVIEW = 200.', 'ROAD_PREVIEW = 300.') == all_text[family, 300]
print('PASS: only authorized cleanup; 2000 paired frames; matched geometry/preview deltas exact.')
