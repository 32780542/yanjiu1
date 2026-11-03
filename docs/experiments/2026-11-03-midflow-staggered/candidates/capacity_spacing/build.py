"""Build B from a fixed read-only Git S blob; never overwrite candidate output."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
COMMIT = '1aa86344af2a269053cd4fcda9d58168697daf17'
BLOB = 'variants/phase5g_pure_formation/noa/native_rules.py'
OUT = ROOT / 'tmp/staggered_bottleneck/candidates/midflow_capacity_spacing/native_rules.py'
EXPECTED = '8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f'
raw = subprocess.run(['git','show',COMMIT+':'+BLOB],cwd=ROOT,check=True,stdout=subprocess.PIPE).stdout
assert hashlib.sha256(raw).hexdigest() == EXPECTED and not OUT.exists()
original = raw.decode('utf-8')
source = original


def change(old, new):
    global source
    assert source.count(old) == 1, old
    source = source.replace(old, new)


change('def _phase(lane, lanes):\n    return GAP / 2 if lane % 2 else 0.0',
       'def _phase(lane, lanes, scale=1.0):\n    return (GAP / 2 if lane % 2 else 0.0) * scale')
change('def _physical_phase(car, lanes):\n',
       'def _physical_phase(car, lanes, transition=None):\n    scale = 1.5 if transition is not None and car.x < transition else 1.0\n')
change('    return _phase(lower, lanes) + (lateral - lower) * (_phase(upper, lanes) - _phase(lower, lanes))',
       '    return _phase(lower, lanes, scale) + (lateral - lower) * (_phase(upper, lanes, scale) - _phase(lower, lanes, scale))')
change('def _pair_error(car, peer, lanes, phase_boundary=None):',
       'def _pair_error(car, peer, lanes, phase_boundary=None, transition=None):')
change('    phase = _physical_phase(peer, 3) - _physical_phase(car, 3)',
       '    phase = _physical_phase(peer, 3, transition) - _physical_phase(car, 3, transition)')
change('def _front_following(ego, rows, distance=50.0):',
       'def _front_following(ego, rows, distance=50.0, scale=1.0):')
change('    target = front.x - LENGTH - STANDSTILL - HEADWAY * ego.speed',
       '    target = (front.x - LENGTH - STANDSTILL - HEADWAY * ego.speed if scale == 1.0\n              else front.x - scale * (LENGTH + STANDSTILL + HEADWAY * ego.speed))')
change('def _following(ego, rows, lanes, phase_boundary=None):',
       'def _following(ego, rows, lanes, phase_boundary=None, transition=None):')
change('    following = _front_following(ego, rows)\n',
       '    scale = 1.5 if transition is not None and ego.x < transition else 1.0\n    following = _front_following(ego, rows, scale=scale)\n')
change('        extended = _front_following(ego, rows, 2 * GAP)',
       '        extended = _front_following(ego, rows, 2 * GAP * scale, scale)')
change('            and abs(c.x + _physical_phase(c, 3) - _physical_phase(ego, 3) - (front.x - GAP)) <= 2.0',
       '            and abs(c.x + _physical_phase(c, 3, transition) - _physical_phase(ego, 3, transition) - (front.x - GAP * scale)) <= 2.0')
source = source.replace('_pair_error(car, c, lanes, phase_boundary)', '_pair_error(car, c, lanes, phase_boundary, transition)')
source = source.replace('_pair_error(ego, peer, lanes, phase_boundary)', '_pair_error(ego, peer, lanes, phase_boundary, transition)')
change('def _fill(ego, rows, lanes):', 'def _fill(ego, rows, lanes, scale=1.0):')
start, end = source.index('def _fill('), source.index('def _mandatory_priority(')
fill = source[start:end]
fill = fill.replace('    component = _component(ego, rows)', '    gap = GAP * scale\n    component = _component(ego, rows)')
fill = fill.replace('<= 90.0)', '<= 90.0 * scale)')
fill = fill.replace('return _phase(lane, lanes)', 'return _phase(lane, lanes, scale)')
fill = fill.replace('/ GAP) * GAP', '/ gap) * gap')
fill = fill.replace('near + k * GAP', 'near + k * gap')
fill = fill.replace('center - 60.0 <= c.x <= center + 30.0', 'center - 60.0 * scale <= c.x <= center + 30.0 * scale')
fill = fill.replace('abs(car.x - target) <= GAP', 'abs(car.x - target) <= gap')
source = source[:start] + fill + source[end:]
change('    organized = mode != "noa"\n',
       '    organized = mode != "noa"\n    transition = drop_x - 360.0 if mode == "transform" and drop_x is not None else None\n')
change('            drop_x - 360.0 if mode == "transform" and drop_x is not None else drop_x,\n',
       '            drop_x - 360.0 if mode == "transform" and drop_x is not None else drop_x,\n            transition,\n')
change('        lane = _fill(ego, rows, 2 if preparing else lanes)',
       '        scale = 1.5 if transition is not None and ego.x < transition else 1.0\n        lane = _fill(ego, rows, 2 if preparing else lanes, scale)')
before = {n.name: ast.dump(n) for n in ast.parse(original).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
changed = [n.name for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and ast.dump(n) != before.get(n.name)]
assert changed == ['_phase','_physical_phase','_pair_error','_front_following','_following','_fill','_decide']
assert len(source.splitlines()) < 510
compile(source, str(OUT), 'exec')
OUT.parent.mkdir(parents=True)
OUT.write_text(source, encoding='utf-8', newline='\n')
(DOC/'native_rules.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile='S/noa/native_rules.py',tofile='B/noa/native_rules.py')),encoding='utf-8',newline='\n')
meta = dict(source_path=str(OUT),source_sha256=hashlib.sha256(source.encode()).hexdigest(),lines=len(source.splitlines()),
            parent_blob=COMMIT+':'+BLOB,parent_sha256=EXPECTED,changed_functions=changed,
            scale='3/2 upstream of drop_x-360, otherwise 1; transform map only',
            no_new_memory_parameters_waiting_or_safety_gate=True,no_traffic_simulation=True)
(DOC/'source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False))
