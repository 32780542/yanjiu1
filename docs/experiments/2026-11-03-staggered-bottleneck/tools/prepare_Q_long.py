"""Authorized frozen Q; original same input and 2400m geometry contract."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=(HERE/'prepare_L_long.py').read_text(encoding='utf-8')
source=source.replace('formation_demo_L_long','formation_demo_Q_long').replace('20261103_L_long_formation_demo','20261103_Q_long_formation_demo').replace('20261103_L_screen180_8/sources/L','20261103_Q_screen180_8/sources/Q').replace('e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a','9837a67be24635102672a87b65f99a85e1ab902a1e86ac743056af6aa4ffaf41').replace("tag='L2400'","tag='Q2400'").replace('L same-input','Q same-input')
exec(compile(source,str(__file__),'exec'),dict(__file__=str(__file__),__name__='__main__'))
