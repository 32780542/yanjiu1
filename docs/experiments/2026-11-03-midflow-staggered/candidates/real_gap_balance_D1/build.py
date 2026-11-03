"""D1: exclude candidate itself from real target-gap neighbors; preserve D0."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
DOC=Path(__file__).resolve().parent
PARENT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance/native_rules.py'
OUT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py'
EXPECTED='afb3ecbe5a432bd2c93e16a21ac88690171266fd37e0c420bc74ea7e6146047e'
raw=PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest()==EXPECTED and not OUT.exists()
original=raw.decode('utf-8')
old='            target, _, _ = _merge_target(car, observed, lane)'
new='            target, _, _ = _merge_target(car, (c for c in observed if c.track != car.track), lane)'
assert original.count(old)==1
source=original.replace(old,new)
assert source.replace(new,old)==original
compile(source,str(OUT),'exec')
OUT.parent.mkdir(parents=True)
OUT.write_text(source,encoding='utf-8',newline='\n')
(DOC/'D0_to_D1.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile='D0/noa/native_rules.py',tofile='D1/noa/native_rules.py')),encoding='utf-8',newline='\n')
meta=dict(source_path=str(OUT),source_sha256=hashlib.sha256(source.encode()).hexdigest(),lines=len(source.splitlines()),
          parent_path=str(PARENT),parent_sha256=EXPECTED,one_line_API_self_exclusion_fix=True,
          frozen_S_blob='1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py',
          self_exclusion='candidate track excluded from target-gap neighbors for all candidates',
          no_gain_or_threshold_change=True,no_traffic_simulation=True)
(DOC/'source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False))
