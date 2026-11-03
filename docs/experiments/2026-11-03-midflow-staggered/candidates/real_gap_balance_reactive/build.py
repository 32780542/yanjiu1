"""DR: delete D1's anticipatory pi mapping line, preserving every other byte."""
import difflib
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
DOC=Path(__file__).resolve().parent
PARENT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py'
OUT=ROOT/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_reactive/native_rules.py'
EXPECTED='2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a'
raw=PARENT.read_bytes()
assert hashlib.sha256(raw).hexdigest()==EXPECTED and not OUT.exists()
original=raw.decode('utf-8')
line='        resource = min(resource, 1) if future else resource\n'
assert original.count(line)==1
source=original.replace(line,'')
compile(source,str(OUT),'exec')
OUT.parent.mkdir(parents=True)
OUT.write_text(source,encoding='utf-8',newline='\n')
(DOC/'D1_to_DR.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile='D1/noa/native_rules.py',tofile='DR/noa/native_rules.py')),encoding='utf-8',newline='\n')
meta=dict(source_path=str(OUT),source_sha256=hashlib.sha256(source.encode()).hexdigest(),lines=len(source.splitlines()),
          parent_path=str(PARENT),parent_sha256=EXPECTED,one_line_removed='future pi resource mapping',
          retained='receiving trigger, measured y/vy projection, target lanes, longitudinal phase, actual gap and safety',
          no_traffic_simulation=True)
(DOC/'source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False))
