"""BC matched non-staggered control from frozen B; immutable source checks."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
DOC=Path(__file__).resolve().parent
PARENT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_capacity_spacing/native_rules.py'
OUT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_capacity_spacing_control/native_rules.py'
EXPECTED='7d749ba8919efbf06efc0abd43846dee4c13b886e81019ae89c0f0116a1553d2'
raw=PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest()==EXPECTED and not OUT.exists()
original=raw.decode('utf-8')
start=original.index('    cars = (ego, *rows)',original.index('def _following('))
end=original.index('\n\ndef _merge_target(',start)
source=original[:start]+'    return following\n'+original[end:]
old='    if not organized:\n        formation_state = 0'
assert source.count(old)==1
source=source.replace(old,'    formation_state = 0')
start=source.index('    if organized and not memory.joining:',source.index('def _decide('))
end=source.index('    if mode == "noa":',start)
source=source[:start]+source[end:]
source=source.replace('    if mode == "noa":\n        front = min(',
                      '    if mode in ("noa", "transform"):\n        front = min(')
before={n.name:ast.dump(n) for n in ast.parse(original).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
changed=[n.name for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and ast.dump(n)!=before.get(n.name)]
assert changed==['_following','_decide']
compile(source,str(OUT),'exec')
OUT.parent.mkdir(parents=True)
OUT.write_text(source,encoding='utf-8',newline='\n')
(DOC/'B_to_BC.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile='B/noa/native_rules.py',tofile='BC/noa/native_rules.py')),encoding='utf-8',newline='\n')
meta=dict(source_path=str(OUT),source_sha256=hashlib.sha256(source.encode()).hexdigest(),lines=len(source.splitlines()),
          parent_path=str(PARENT),parent_sha256=EXPECTED,changed_functions_from_B=changed,
          frozen_S_blob='1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py',
          controller='same capacity reference without active staggered organization',
          retain='B base CTH, side-witness bridge, real gap execution, ordinary NOA overtake in transform',
          remove='phase speed feedback, freefill; formation_state always 0',
          no_traffic_simulation=True)
(DOC/'source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False))
