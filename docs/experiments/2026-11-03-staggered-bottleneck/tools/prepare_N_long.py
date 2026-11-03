"""Authorized frozen N with the identical reviewed L initial/network contract."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=(HERE/'prepare_L_long.py').read_text(encoding='utf-8')
source=source.replace('formation_demo_L_long','formation_demo_N_long').replace('20261103_L_long_formation_demo','20261103_N_long_formation_demo').replace('20261103_L_screen180_8/sources/L','20261103_N_screen180_8/sources/N').replace('e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a','5d21af5456e816c927116a66895db29d03fada7b28057ecef266b60a0d92a0d6').replace("tag='L2400'","tag='N2400'").replace('L same-input','N same-input')
exec(compile(source,str(__file__),'exec'),dict(__file__=str(__file__),__name__='__main__'))
