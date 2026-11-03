"""Create new J2/JT2 demo folders by exact adaptation of sealed E/H protocol."""
from pathlib import Path
import runpy

BASE=Path(__file__).resolve().parent.parent
original=(BASE/'formation_demo_H/prepare_demo.py').read_text(encoding='utf-8')
for tag,expected in [
    ('J2','895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689'),
    ('JT2','b415daca538202594a1b12fc768ed3a60a9c30a2f37221625ef1bf3be331df48')]:
    out=BASE/('formation_demo_'+tag)
    assert not out.exists()
    out.mkdir()
    text=original.replace('Prepare H demos','Prepare '+tag+' demos')
    text=text.replace('20261103_H_screen180_8/sources/H','20261103_J2_JT2_screen180_16/sources/'+tag)
    text=text.replace('20261103_H_formation_demo','20261103_'+tag+'_formation_demo')
    text=text.replace('bfd3080c166f63d07e401a9f106a27ae82c1dbcb7df96d92eb4b922c39d51a4e',expected)
    text=text.replace('H / ',tag+' / ').replace('H and E',tag+' and E')
    script=out/'prepare_demo.py'
    script.write_text(text,encoding='utf-8',newline='\n')
    runpy.run_path(str(script),run_name='__main__')
    runpy.run_path(str(out/'check_initial_equilibrium.py'),run_name='__main__')
