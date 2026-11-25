"""Test whether the receiving rule needs any memories from before ego sees the lane change."""
import argparse
from pathlib import Path
import subprocess
from private_burden_trial import ROOT,BASE,VARIANT
from slot_predecessor_trial import build


def create(out):
    build(out,"order","combined")
    simulator=out/"experiments/native_sumo.py"
    simulator.write_bytes(subprocess.check_output(["git","show",f"{BASE}:{VARIANT}/experiments/native_sumo.py"],cwd=ROOT))
    p=out/"noa/native_rules.py";s=p.read_text(encoding="utf8")
    s=s.replace("    preview_x: float | None = None\n","")
    s=s.replace(", visible_boundary_x=None","")
    s=s.replace("    preview_x = memory.preview_x if visible_boundary_x is None else visible_boundary_x - ROAD_PREVIEW\n    memory = replace(memory, preview_x=preview_x)\n","")
    s=s.replace("replace(memory, preview_x=preview_x)","memory")
    a=s.index("    previous = {track:(lane,x)");b=s.index("    if len(group) == 1:\n",a)
    s=s[:a]+"""    observed = ()
    if transforming:
        previous = {t:(lane,used) for t,lane,used in memory.observed_steps}
        observed = tuple((car.track,car.lane,used or lane!=car.lane) for car in group
                         for lane,used in [previous.get(car.track,(car.lane,False))])
"""+s[b:]
    s=s.replace("tuple(x >= memory.preview_x for _,_,x in observed) if transforming and memory.preview_x is not None else ()",
                "tuple(used for _,_,used in observed)")
    s=s.replace("    transition: bool = False\n","").replace(", transition=transforming","")
    assert "preview_x" not in s
    p.write_text(s,encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("out",type=Path);create(p.parse_args().out)
