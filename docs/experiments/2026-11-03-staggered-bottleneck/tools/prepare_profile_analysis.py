"""Reuse reviewed L tools for one newly authorized frozen small-demo profile."""
import argparse
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--label',choices=['N','Q','LP0','LT','S'],required=True);a=parser.parse_args()
BASE=Path(__file__).resolve().parent.parent;OLD=BASE/'formation_demo_L_long';OUT=BASE/('formation_demo_'+a.label+'_long');tag=a.label+'2400'
text=(OLD/'analyze_L_long.py').read_text(encoding='utf-8').replace('L2400',tag).replace('J2_L_registered','J2_'+a.label+'_registered').replace('L_vs_J2',a.label+'_vs_J2').replace('frozen_L_rules_for_audit','frozen_'+a.label+'_rules_for_audit')
(OUT/('analyze_'+a.label+'_long.py')).write_text(text,encoding='utf-8')
(OUT/'verify_long_demo.py').write_bytes((OLD/'verify_long_demo.py').read_bytes())
text=(OLD/'seal_long_demo.py').read_text(encoding='utf-8').replace("['L2400-demo-','L-long-']",repr([tag+'-demo-',a.label+'-long-']))
(OUT/'seal_long_demo.py').write_text(text,encoding='utf-8')
print({'profile':a.label,'new_scripts':3,'L_unchanged':True})
