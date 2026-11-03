"""Frozen LP0 from validation31, no longitudinal phase feedback."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;root=HERE.parents[3]
frozen=root/'tmp/staggered_bottleneck/20261103_validation31_LP0_10/sources/LP0'
h=hashlib.sha256((frozen/'noa/native_rules.py').read_bytes()).hexdigest();assert h.startswith('64a134') and h.endswith('5eb4')
assert json.loads((frozen/'freeze.json').read_text(encoding='utf-8'))['sha256']['noa/native_rules.py']==h
source=(HERE/'prepare_L_long.py').read_text(encoding='utf-8')
source=source.replace('formation_demo_L_long','formation_demo_LP0_long').replace('20261103_L_long_formation_demo','20261103_LP0_long_formation_demo').replace('20261103_L_screen180_8/sources/L','20261103_validation31_LP0_10/sources/LP0').replace('e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a',h).replace("tag='L2400'","tag='LP02400'").replace('L same-input','LP0 same-input')
exec(compile(source,str(__file__),'exec'),dict(__file__=str(__file__),__name__='__main__'))
