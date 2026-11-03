"""DP: set D1 longitudinal phase_speed to zero, retaining lateral organization."""
import difflib
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
DOC=Path(__file__).resolve().parent
PARENT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py'
OUT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_phase_off/native_rules.py'
EXPECTED='2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a'
raw=PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest()==EXPECTED and not OUT.exists()
original=raw.decode('utf-8')
old='    phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))'
assert original.count(old)==1
source=original.replace(old,'    phase_speed = 0.0')
compile(source,str(OUT),'exec')
OUT.parent.mkdir(parents=True)
OUT.write_text(source,encoding='utf-8',newline='\n')
(DOC/'D1_to_DP.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile='D1/noa/native_rules.py',tofile='DP/noa/native_rules.py')),encoding='utf-8',newline='\n')
meta=dict(source_path=str(OUT),source_sha256=hashlib.sha256(source.encode()).hexdigest(),lines=len(source.splitlines()),
          parent_path=str(PARENT),parent_sha256=EXPECTED,one_line_replaced='phase_speed = 0.0',
          controller='longitudinal phase off with active lateral organization retained',
          retained='relationship flag, future resource load, active fill, actual gap, safety; no ordinary overtake added',
          no_traffic_simulation=True)
(DOC/'source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False))
