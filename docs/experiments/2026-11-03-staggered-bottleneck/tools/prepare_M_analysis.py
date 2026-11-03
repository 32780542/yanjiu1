"""New M-only analysis scripts; sealed L scripts remain unchanged."""
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
OLD=BASE/'formation_demo_L_long';OUT=BASE/'formation_demo_M_long'
text=(OLD/'analyze_L_long.py').read_text(encoding='utf-8').replace('L2400','M2400').replace('J2_L_registered','J2_M_registered').replace('L_vs_J2','M_vs_J2').replace('frozen_L_rules_for_audit','frozen_M_rules_for_audit')
(OUT/'analyze_M_long.py').write_text(text,encoding='utf-8')
text=(OLD/'verify_long_demo.py').read_text(encoding='utf-8')
(OUT/'verify_long_demo.py').write_text(text,encoding='utf-8')
text=(OLD/'seal_long_demo.py').read_text(encoding='utf-8').replace("['L2400-demo-','L-long-']","['M2400-demo-','M-long-']")
(OUT/'seal_long_demo.py').write_text(text,encoding='utf-8')
print({'new_M_scripts':3,'L_unchanged':True})
