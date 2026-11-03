"""Prepare H demos with byte-identical E inputs and identical plotting/geometry logic."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
E=OUT.parent/'formation_demo'
RUNTIME=ROOT/'tmp/staggered_bottleneck/20261103_H_screen180_8/sources/H'
EXPECTED='bfd3080c166f63d07e401a9f106a27ae82c1dbcb7df96d92eb4b922c39d51a4e'
assert hashlib.sha256((RUNTIME/'noa/native_rules.py').read_bytes()).hexdigest()==EXPECTED
for name in ['unformed24_initial.json','formed45_initial.json','downstream_first_observations.py','check_initial_equilibrium.py']:
    assert not (OUT/name).exists()
    (OUT/name).write_bytes((E/name).read_bytes())
raw=(E/'analyze_and_plot.py').read_text(encoding='utf-8')
source=raw.replace("RUNS=ROOT/'tmp/staggered_bottleneck/20261103_E_formation_demo'", "RUNS=ROOT/'tmp/staggered_bottleneck/20261103_H_formation_demo'").replace('E / ','H / ')
assert source!=raw and source.replace("RUNS=ROOT/'tmp/staggered_bottleneck/20261103_H_formation_demo'", "RUNS=ROOT/'tmp/staggered_bottleneck/20261103_E_formation_demo'").replace('H / ','E / ')==raw
(OUT/'analyze_and_plot.py').write_text(source,encoding='utf-8',newline='\n')
protocol=json.loads((E/'protocol.json').read_text())
protocol.update(frozen_runtime=str(RUNTIME),rules_sha256=EXPECTED,
    reference_input_source=str(E),comparison='H and E use byte-identical initial JSONs; source rules are the only behavioral change',
    plotting_logic_equal_after_label_path_substitution=True,
    E_plot_tool_sha256=hashlib.sha256((E/'analyze_and_plot.py').read_bytes()).hexdigest(),
    source_sha256={str(p.relative_to(RUNTIME)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [RUNTIME/'run_native_flow.py',RUNTIME/'experiments/native_sumo.py',RUNTIME/'noa/native_rules.py',RUNTIME/'research/common.py']})
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'runtime':str(RUNTIME),'rules_sha256':EXPECTED,'same_input_bytes':True,'same_plot_geometry_logic':True}))
