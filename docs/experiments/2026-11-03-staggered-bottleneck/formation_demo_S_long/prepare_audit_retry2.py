"""Preserve the empty-event writer failure; handle zero observed events honestly."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
old=OUT/'analyze_S_long.py';text=old.read_text(encoding='utf-8')
retained=OUT/'audit_attempt1';retained.mkdir(exist_ok=False)
for name in ['all_finite_view_bridge_witness_events.csv','J2_S_registered_comparison.csv']:
    p=OUT/name
    if p.exists():(retained/name).write_bytes(p.read_bytes())
(retained/'failed_tool.py').write_bytes(old.read_bytes())
(retained/'failure.json').write_text(json.dumps(dict(operation='20261103T073303556098Z_S-long-witness-audit_fad0b006',reason='Zero qualified witness events; empty CSV writer assumed rr[0]',simulation_or_controller_failure=False,failed_tool_sha256=hashlib.sha256(old.read_bytes()).hexdigest()),indent=2)+'\n',encoding='utf-8')
text=text.replace("w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)","fields=list(rr[0]) if rr else next(csv.reader((OUT.parent/'formation_demo_L_long'/name).open(encoding='utf-8-sig',newline='')))\n        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rr)")
(OUT/'analyze_S_long_retry2.py').write_text(text,encoding='utf-8')
print({'retained_attempt1':str(retained),'new_tool':'analyze_S_long_retry2.py','only_empty_event_writing_fixed':True})
