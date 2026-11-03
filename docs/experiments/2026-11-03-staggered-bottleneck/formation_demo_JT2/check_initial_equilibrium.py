"""Read-only exact initial following-request check; no simulation."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys

OUT=Path(__file__).resolve().parent
protocol=json.loads((OUT/'protocol.json').read_text())
source=Path(protocol['frozen_runtime'])/'noa/native_rules.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()==protocol['rules_sha256']
spec=importlib.util.spec_from_file_location('demo_E_equilibrium',source)
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
rows=json.loads((OUT/'formed45_initial.json').read_text());checks=[]
for i,r in enumerate(rows):
    ego=module.Vehicle(0,r['x'],(r['lane']+.5)*3.3,r['speed'],r['lane'])
    neighbors=tuple(module.Vehicle(j+1,s['x'],(s['lane']+.5)*3.3,s['speed'],s['lane']) for j,s in enumerate(rows)
                    if j!=i and -100<=s['x']-r['x']<=200)
    command=module._following(ego,neighbors,3,640)
    assert abs(command[0]-28.8)<1e-12
    checks.append(dict(id=r['id'],x=r['x'],lane=r['lane'],following_requested_speed_mps=command[0]))
result=dict(rules_sha256=protocol['rules_sha256'],outer_range=[35,455],middle_range=[20,440],
    outer_leads_middle_m=15,all_45_following_requests_equal_28_8=True,checks=checks)
(OUT/'initial_equilibrium_check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print({'vehicles':len(checks),'following_requests_equal_28_8':True})
