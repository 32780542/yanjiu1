"""D: real-gap opportunities and projected resource load; frozen S only."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[5]
DOC=Path(__file__).resolve().parent
BLOB='1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py'
EXPECTED='8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f'
OUT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance/native_rules.py'
raw=subprocess.check_output(['git','show',BLOB],cwd=ROOT)
assert hashlib.sha256(raw).hexdigest()==EXPECTED and not OUT.exists()
original=raw.decode('utf-8')
old_fill=original[original.index('def _fill('):original.index('def _mandatory_priority(')]
cost=old_fill[old_fill.index('    observed = (ego, *rows)'):old_fill.index('    choices = []')]
fill='''def _fill(ego, rows, lanes, future=False):
    """实际gap执行机会使局部车道资源计数平方和严格下降；不设全局格点。"""
    cars = tuple(c for c in _component(ego, rows) if abs(c.x - ego.x) <= 90.0)
    counts = [0] * lanes
    for car in cars:
        resource = car.lane
        if abs(car.vy) > 0.1:
            lateral = car.y / LANE_WIDTH - 0.5
            resource = max(0, min(2, ceil(lateral) if car.vy > 0 else floor(lateral)))
        resource = min(resource, 1) if future else resource
        if resource < lanes:
            counts[resource] += 1
'''+cost+'''    choices = []
    for car in cars:
        if car.lane >= lanes or abs(car.vy) >= 0.1:
            continue
        for lane in (car.lane - 1, car.lane + 1):
            if not 0 <= lane < lanes or 2 * (counts[lane] - counts[car.lane] + 1) >= 0:
                continue
            target, _, _ = _merge_target(car, observed, lane)
            if abs(target - car.x) > GAP or not _clear(car, observed, lane):
                continue
            cost = response_cost(car, lane)
            if cost is not None:
                score = (cost, -car.x, abs(target - car.x), -target, -car.lane, -lane,
                         car.y, car.speed, car.vy)
                choices.append((score, car, lane))
    if not choices:
        return None
    _, car, lane = min(choices, key=lambda item: item[0])
    return lane if car.track == ego.track else None


'''
source=original.replace(old_fill,fill)
source=source.replace('from math import sqrt\n','from math import sqrt, ceil, floor\n')
old='    lanes = 2 if drop_x is not None and ego.x >= drop_x else 3\n'
new='''    receiving = preparing or (mode == "transform" and drop_x is not None and any(
        c.lane == 2 and abs(c.x - ego.x) <= 90.0 and drop_x - 360.0 <= c.x <= drop_x
        for c in rows))
'''+old
assert source.count(old)==1
source=source.replace(old,new)
source=source.replace('future_lanes = 2 if preparing and mode == "transform" else lanes',
                      'future_lanes = 2 if receiving and mode == "transform" else lanes')
source=source.replace('(preparing and memory.lane_target == 2)',
                      '(receiving and memory.lane_target == 2)')
source=source.replace('        lane = _fill(ego, rows, 2 if preparing else lanes)',
                      '        lane = _fill(ego, rows, 2 if receiving else lanes, receiving and mode == "transform")')
before={n.name:ast.dump(n) for n in ast.parse(original).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
changed=[n.name for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and ast.dump(n)!=before.get(n.name)]
assert changed==['_fill','_decide']
compile(source,str(OUT),'exec')
OUT.parent.mkdir(parents=True)
OUT.write_text(source,encoding='utf-8',newline='\n')
(DOC/'native_rules.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile='S/noa/native_rules.py',tofile='D/noa/native_rules.py')),encoding='utf-8',newline='\n')
meta=dict(source_path=str(OUT),source_sha256=hashlib.sha256(source.encode()).hexdigest(),lines=len(source.splitlines()),
          frozen_S_blob=BLOB,parent_sha256=EXPECTED,changed_functions=changed,
          candidate='real gap and projected future-resource balance',
          added_memory_parameters_waiting_or_safety_gate=False,no_traffic_simulation=True)
(DOC/'source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False))
