"""Build independent two-sided group-gap variants and run the same native sparse fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from pose_anchor_trial import edit, run
from run_study import OPTIONAL, REQUIRED

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MODES = ("pair", "mass", "mutual")


def prepare(out, source, evaluator):
    out.mkdir(parents=True,exist_ok=False)
    manifest = {}
    for mode in MODES:
        dst = out/"frozen"/mode
        for name in (*REQUIRED,*OPTIONAL):
            target = dst/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/name,target)
        (dst/"tmp").mkdir()
        path = dst/"noa/native_rules.py"
        code = path.read_text(encoding="utf8")
        helper = """def _external_shift(group, rows):
    # Two measured front-to-tail gaps. A uniform chain has zero interior force.
    front, rear = group[0], group[-1]
    ahead = min((c for c in rows if c.x > front.x), key=lambda c:(c.x,c.lane), default=None)
    behind = max((c for c in rows if c.x < rear.x), key=lambda c:(c.x,c.lane), default=None)
    def excess(a, b):
        separation = a.x - b.x
        spacing = desired_spacing((a.speed + b.speed) / 2)
        return max(0., separation - spacing)
    push = excess(ahead, front) if ahead is not None else 0.
    pull = excess(rear, behind) if behind is not None else 0.
    return (push - pull) / 2


"""
        if mode == "mass":
            helper = helper.replace(" / 2\n"," / (2 * len(group))\n")
        if mode == "mutual":
            helper = helper.replace("        spacing = ", "        if separation > REAR_VIEW:\n            return 0.\n        spacing = ")
        code = edit(code,"def _transport(",helper+"def _transport(")
        code = edit(code,"    from noa.staggered import anchored_x, choose_target","    from noa.staggered import choose_target")
        old = """    forward_anchor = None
    if not transforming:
        forward_anchor = min((c.x for c in rows if c.x > group[0].x), default=None)
"""
        code = edit(code,old,"    shift = 0. if transforming else _external_shift(group, rows)\n")
        code = edit(code,"        if forward_anchor is not None and command.reference is None and command.lane is None:",
                    "        if shift and command.reference is None and command.lane is None:")
        code = edit(code,"            x = anchored_x(ego.x, ego.x, desired_spacing(ego.speed), forward_anchor)",
                    "            x = ego.x + shift")
        code = edit(code,"                           forward_anchor=forward_anchor, opened_lanes=opened if opened < lanes else None)",
                    "                           opened_lanes=opened if opened < lanes else None)\n    if shift:\n        target = replace(target, x=target.x + shift)")
        path.write_text(code,encoding="utf8")
        manifest[mode] = {name:hashlib.sha256((dst/name).read_bytes()).hexdigest() for name in (*REQUIRED,*OPTIONAL)}
    shutil.copyfile(evaluator,out/"frozen/measure.py")
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out",type=Path)
    p.add_argument("--prepare",action="store_true")
    p.add_argument("--source",type=Path,default=ROOT/"tmp/nov25study/topology_product_demo/source")
    p.add_argument("--evaluator",type=Path,default=ROOT/"tmp/nov25-open-subflow/frozen/measure.py")
    p.add_argument("--workers",type=int,default=3)
    args = p.parse_args()
    if args.prepare:
        prepare(args.out.resolve(),args.source.resolve(),args.evaluator.resolve())
    else:
        run(args.out.resolve(),args.workers,MODES)
