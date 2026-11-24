"""Freeze and run endpoint-only mutual or extended upstream gap requests."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import shutil

from pose_anchor_trial import edit, run
from run_study import OPTIONAL, REQUIRED

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MODES = ("endpoint", "extended")


def _endpoint_shift(ego, rows, forward_reach):
    """Use the immediately adjacent physical endpoint on each side of ego."""
    own = (ego.x, ego.lane)
    ahead = behind = None
    for car in rows:
        key = (car.x, car.lane)
        if key == own:
            return 0.
        if key > own and (ahead is None or key < (ahead.x, ahead.lane)):
            ahead = car
        if key < own and (behind is None or key > (behind.x, behind.lane)):
            behind = car

    def excess(other, reach):
        if other is None:
            return 0.
        gap = abs(other.x - ego.x)
        if not GROUP_GAP < gap <= reach:
            return 0.
        if sum(c.x == other.x and c.lane == other.lane for c in rows) != 1:
            return 0.
        return max(0., gap - desired_spacing((ego.speed + other.speed) / 2))

    return (excess(ahead, forward_reach) - excess(behind, REAR_VIEW)) / 2


def prepare(out, base, evaluator, modes):
    out.mkdir(parents=True,exist_ok=False)
    manifest = {}
    for mode in modes:
        dst=out/"frozen"/mode
        for name in (*REQUIRED,*OPTIONAL):
            target=dst/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(base/name,target)
        (dst/"tmp").mkdir()
        if mode == "baseline":
            manifest[mode]={name:hashlib.sha256((dst/name).read_bytes()).hexdigest() for name in (*REQUIRED,*OPTIONAL)}
            continue
        path=dst/"noa/native_rules.py"
        code=path.read_text(encoding="utf8")
        code=edit(code,"def _transport(",inspect.getsource(_endpoint_shift)+"\n\ndef _transport(")
        code=edit(code,"    from noa.staggered import anchored_x, choose_target",
                  "    from noa.staggered import choose_target")
        original="""    forward_anchor = None
    if not transforming:
        forward_anchor = min((c.x for c in rows if c.x > group[0].x), default=None)
"""
        reach="REAR_VIEW" if mode=="endpoint" else "FRONT_VIEW"
        code=edit(code,original,f"    shift = 0. if transforming else _endpoint_shift(ego, rows, {reach})\n")
        code=edit(code,"        if forward_anchor is not None and command.reference is None and command.lane is None:",
                  "        if shift and command.reference is None and command.lane is None:")
        code=edit(code,"            x = anchored_x(ego.x, ego.x, desired_spacing(ego.speed), forward_anchor)",
                  "            x = ego.x + shift")
        code=edit(code,"                           forward_anchor=forward_anchor, opened_lanes=opened if opened < lanes else None)",
                  "                           opened_lanes=opened if opened < lanes else None)\n    if shift:\n        target = replace(target, x=target.x + shift)")
        path.write_text(code,encoding="utf8")
        manifest[mode]={name:hashlib.sha256((dst/name).read_bytes()).hexdigest() for name in (*REQUIRED,*OPTIONAL)}
    shutil.copyfile(evaluator,out/"frozen/measure.py")
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("out",type=Path)
    p.add_argument("--prepare",action="store_true")
    p.add_argument("--source",type=Path,default=ROOT/"tmp/nov25study/topology_product_demo/source")
    p.add_argument("--evaluator",type=Path,default=ROOT/"tmp/nov25-open-subflow/frozen/measure.py")
    p.add_argument("--baseline",action="store_true",help="Exact unmodified source only")
    p.add_argument("--workers",type=int,default=4);a=p.parse_args()
    modes=("baseline",) if a.baseline else MODES
    if a.prepare: prepare(a.out.resolve(),a.source.resolve(),a.evaluator.resolve(),modes)
    else: run(a.out.resolve(),a.workers,modes)
