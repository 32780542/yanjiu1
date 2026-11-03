"""Authorized frozen S; identical original initial and extended-road contract."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=(HERE/'prepare_L_long.py').read_text(encoding='utf-8')
source=source.replace('formation_demo_L_long','formation_demo_S_long').replace('20261103_L_long_formation_demo','20261103_S_long_formation_demo').replace('20261103_L_screen180_8/sources/L','20261103_S_screen180_8/sources/S').replace('e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a','8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f').replace("tag='L2400'","tag='S2400'").replace('L same-input','S same-input')
exec(compile(source,str(__file__),'exec'),dict(__file__=str(__file__),__name__='__main__'))
