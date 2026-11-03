"""Run one original tape once under run_logged; prepare_demo.py must run first."""
import argparse,json,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--demo',choices=['unformed24','formed45'],required=True);a=ap.parse_args()
p=json.loads((OUT/'protocol.json').read_text());tag='D12400';runtime=Path(p['runtimes'][tag]['frozen_runtime']);dest=Path(p['run_base'])/tag/a.demo
assert not dest.exists(),'Keep old attempts immutable; use a separately prepared new run_base for reruns'
cmd=[sys.executable,str(ROOT/'scripts/run_logged.py'),'--label','D1-geometry-'+a.demo,'--timeout','600','--',sys.executable,'-B',str(runtime/'run_native_flow.py'),'--mode','transform','--seed','1','--flow','1750','--duration','1','--scenario','lane_drop','--max-time','180','--initial',str(OUT/(a.demo+'_initial.json')),'--diagnostic','--output-base',str(dest)]
raise SystemExit(subprocess.call(cmd,cwd=ROOT))
