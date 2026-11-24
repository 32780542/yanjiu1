"""Reproduce the whole-component anchor gate from the archived moment controller."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from pose_anchor_trial import edit,run
from run_study import OPTIONAL,REQUIRED

HERE=Path(__file__).resolve().parent


def prepare(out):
    out.mkdir(parents=True,exist_ok=False);dst=out/"frozen/component";digest={}
    with zipfile.ZipFile(HERE/"nearest_segment_base.zip") as archive:
        for name in (*REQUIRED,*OPTIONAL):
            f=dst/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(archive.read(name))
            if name=="noa/native_rules.py":
                old="    if not transforming:\n        forward_anchor = min("
                new="""    complete_component = (ego.x + FRONT_VIEW - group[0].x >= GROUP_GAP
                          and group[-1].x - (ego.x - REAR_VIEW) >= GROUP_GAP)
    if not transforming and complete_component:
        forward_anchor = min("""
                f.write_text(edit(f.read_text(encoding="utf8"),old,new),encoding="utf8")
            digest[name]=hashlib.sha256(f.read_bytes()).hexdigest()
        (out/"frozen/measure.py").write_bytes(archive.read("measure.py"))
    (dst/"tmp").mkdir()
    (out/"manifest.json").write_text(json.dumps({"component":digest},indent=2),encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("out",type=Path)
    p.add_argument("--prepare",action="store_true");p.add_argument("--workers",type=int,default=5);a=p.parse_args()
    if a.prepare:prepare(a.out.resolve())
    else:run(a.out.resolve(),a.workers,("component",))
