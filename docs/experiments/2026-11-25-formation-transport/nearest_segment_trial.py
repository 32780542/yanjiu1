"""Freeze mutual-nearest visible segment anchoring on the odd-phase controller."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import shutil
from pose_anchor_trial import edit,run
from run_study import REQUIRED,OPTIONAL

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
MODES=("moment","nearest")


def _nearest_segment_anchor(group, rows):
    """Rear segment may close its forward gap if both segments choose that edge."""
    front_x, rear_x = group[0].x, group[-1].x
    ahead = sorted(c.x for c in rows if c.x > front_x)
    if not ahead:
        return None
    gap = ahead[0] - front_x
    previous_x = max((c.x for c in rows if c.x < rear_x), default=-float("inf"))
    if gap > rear_x - previous_x:
        return None
    next_gap = next((b - a for a, b in zip(ahead, ahead[1:])
                     if b - a > GROUP_GAP), float("inf"))
    return ahead[0] if gap < next_gap else None


def prepare(out,source,evaluator):
    out.mkdir(parents=True,exist_ok=False);manifest={}
    for mode in MODES:
        dst=out/"frozen"/mode
        for name in (*REQUIRED,*OPTIONAL):
            to=dst/name;to.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/name,to)
        (dst/"tmp").mkdir()
        if mode=="nearest":
            f=dst/"noa/native_rules.py";s=f.read_text(encoding="utf8")
            s=edit(s,"def _transport(",inspect.getsource(_nearest_segment_anchor)+"\n\ndef _transport(")
            s=edit(s,"        forward_anchor = min((c.x for c in rows if c.x > group[0].x), default=None)",
                   "        forward_anchor = _nearest_segment_anchor(group, rows)")
            f.write_text(s,encoding="utf8")
        manifest[mode]={k:hashlib.sha256((dst/k).read_bytes()).hexdigest() for k in (*REQUIRED,*OPTIONAL)}
    shutil.copyfile(evaluator,out/"frozen/measure.py")
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("out",type=Path)
    p.add_argument("--prepare",action="store_true");p.add_argument("--workers",type=int,default=5)
    p.add_argument("--source",type=Path,default=ROOT/"tmp/nov25-odd-phase-dev/frozen/moment")
    p.add_argument("--evaluator",type=Path,default=ROOT/"tmp/nov25-odd-phase-dev/frozen/measure.py")
    a=p.parse_args()
    if a.prepare:prepare(a.out.resolve(),a.source.resolve(),a.evaluator.resolve())
    else:run(a.out.resolve(),a.workers,MODES)
