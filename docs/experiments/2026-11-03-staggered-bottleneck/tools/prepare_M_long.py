"""Reuse the already reviewed L contract with the authorized frozen M controller."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=(HERE/'prepare_L_long.py').read_text(encoding='utf-8')
source=source.replace('prepare_L_long.py','prepare_M_long.py').replace('formation_demo_L_long','formation_demo_M_long').replace('20261103_L_long_formation_demo','20261103_M_long_formation_demo').replace('20261103_L_screen180_8/sources/L','20261103_M_screen180_8/sources/M').replace('e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a','a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762').replace("tag='L2400'","tag='M2400'").replace('L same-input','M same-input')
exec(compile(source,str(__file__),'exec'),dict(__file__=str(__file__),__name__='__main__'))
